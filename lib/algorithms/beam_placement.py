# -*- coding: utf-8 -*-
"""Algorithme de placement et classification des poutres

REGLES METIER IMPLEMENTEES :

TYPE 1 : PRINCIPALE
- Appui : 2 poteaux minimum
- Portee : Cote COURT de la travee (portee min de l orientation)
- Hauteur : L/9 (entre L/8 et L/12)
- Largeur : 0.4 * hauteur

TYPE 2 : SECONDAIRE
- Appui : poteau+poteau / poteau+voile / poteau+poutre / poutre+poutre
- Largeur calculee < epaisseur dalle
- Hauteur : = Hauteur dalle

TYPE 3 : RAIDISSEUR
- Appui : poteau+poteau / poteau+voile / poteau+poutre / poutre+poutre
- Largeur calculee = epaisseur dalle (section carree)
- Hauteur : = Hauteur dalle
- Espacement MAX : MAX_STIFFENER_SPACING (defaut 3000 mm)
- AJOUT v2 : insertion de raidisseurs intermediaires si portee > espacement max

TYPE 4 : POUTRE PLATE
- Appui : poteau+poteau / poteau+voile / poteau+poutre / poutre+poutre
- Largeur calculee > epaisseur dalle
- Hauteur : = Hauteur dalle

AMELIORATIONS v2 :
- Stubs de secours pour tous les imports Revit/metier (mode degrade propre)
- Decorateurs @log_execution / @transaction / @handle_errors remplaces par
  wrappers inline tolerants aux erreurs
- MAX_STIFFENER_SPACING : attribut public, utilisable depuis l UI
- Raidisseurs intermediaires inseres automatiquement si portee > max
- Anti-doublon : tolerance DUPLICATE_TOLERANCE_FT (defaut 0.5 pi = ~150 mm)
- create_beams_for_level retourne une liste d elements Revit natifs
  (compatible avec get_beam_type_label dans l UI)
- Transaction explicite dans create_beams_for_level (plus de decorateur)
- Logging degrade : fonctionne meme sans LoggingService
- Ajout methode check_existing_beams (tolerances doublons)
- Ajout methode get_beams_for_level (lecture seule)
- Ajout statistiques par type dans create_all_beams

CORRECTIONS v3 (avertissements Revit) :
- BUG 1 CORRIGE : INSTANCE_REFERENCE_LEVEL_PARAM est en LECTURE SEULE apres
  creation - la ligne ref_param.Set() est supprimee (causait 21 erreurs Level 1)
- BUG 2 CORRIGE : Coordonnee Z forcee a level.Elevation sur les deux extremites
  de chaque poutre - supprime l avertissement "leger decalage par rapport a l axe"
- BUG 3 CORRIGE : Tolerance de regroupement des poteaux affinee de ±152mm
  (round 0 ft) a ±25mm (ALIGN_TOLERANCE_FT=0.082 ft) - elimine les poutres
  diagonales generees par un faux alignement de colonnes/rangees
- BUG 4 CORRIGE : Anti-doublon inter-niveaux renforce - verifie aussi les
  poutres deja creees dans la meme session (meme plan XY, Z different)
"""

from __future__ import division, print_function
import math
import sys

# =============================================================================
# IMPORTS REVIT — tous avec fallback propre
# =============================================================================
try:
    from Autodesk.Revit.DB import (
        XYZ, Line, Level, FamilySymbol, Transaction,
        FilteredElementCollector, BuiltInCategory, BuiltInParameter,
        ElementId
    )
    from Autodesk.Revit.DB.Structure import StructuralType as RevitStructuralType
    StructuralType  = RevitStructuralType
    REVIT_AVAILABLE = True
except Exception as _revit_err:
    REVIT_AVAILABLE = False
    StructuralType  = None
    sys.stderr.write("beam_placement: Revit DB non disponible (%s)\n" % _revit_err)

# =============================================================================
# IMPORTS METIER — tous avec fallback propre
# =============================================================================

# --- Services ---------------------------------------------------------------
try:
    from services.revit_service    import RevitService
    from services.geometry_service import GeometryService
    from services.logging_service  import LoggingService
    SERVICES_AVAILABLE = True
except Exception:
    SERVICES_AVAILABLE = False
    RevitService       = None
    GeometryService    = None

    class LoggingService(object):
        """Stub minimal de LoggingService."""
        def __init__(self, api_client=None): pass
        def log_info(self, msg):    sys.stdout.write("[INFO] %s\n"    % msg)
        def log_warning(self, msg): sys.stderr.write("[WARN] %s\n"    % msg)
        def log_error(self, exc, context=None):
            sys.stderr.write("[ERR] %s | ctx=%s\n" % (exc, context))

# --- Decorateurs ------------------------------------------------------------
try:
    from utils.decorators import log_execution, transaction, handle_errors
    DECORATORS_AVAILABLE = True
except Exception:
    DECORATORS_AVAILABLE = False
    # Stubs passthrough : les methodes fonctionnent sans decoration
    def log_execution(fn):       return fn
    def transaction(label):      return lambda fn: fn
    def handle_errors(label):    return lambda fn: fn

# --- Helpers ----------------------------------------------------------------
try:
    from helpers.revit_helpers import (
        get_all_levels as _get_all_levels_helper,
        get_all_grids,
        mm_to_feet, feet_to_mm,
    )
    HELPERS_AVAILABLE = True
except Exception:
    HELPERS_AVAILABLE = False
    get_all_grids = None
    def mm_to_feet(mm): return mm / 304.8
    def feet_to_mm(ft): return ft * 304.8

    def _get_all_levels_helper(doc):
        from Autodesk.Revit.DB import FilteredElementCollector, Level
        return sorted(
            list(FilteredElementCollector(doc).OfClass(Level).ToElements()),
            key=lambda l: l.Elevation)

def get_all_levels(doc):
    return _get_all_levels_helper(doc)

# --- Geometrie ---------------------------------------------------------------
try:
    from algorithms.geometry_utils import calculate_distance
    GEOM_UTILS_AVAILABLE = True
except Exception:
    GEOM_UTILS_AVAILABLE = False
    def calculate_distance(a, b):
        """Distance euclidienne 2D (XY) entre deux XYZ."""
        dx = a.X - b.X
        dy = a.Y - b.Y
        return math.sqrt(dx * dx + dy * dy)

# --- Calculateur de hauteur -------------------------------------------------
try:
    from algorithms.dimension_calculator import calculate_beam_height
    DIMCALC_AVAILABLE = True
except Exception:
    DIMCALC_AVAILABLE = False
    def calculate_beam_height(span_m, ratio=9.0):
        """Hauteur de poutre selon L/ratio, arrondie a 50 mm."""
        return max(200, int(round(span_m / ratio * 1000 / 50)) * 50)

# --- ColumnPlacementEngine --------------------------------------------------
try:
    from algorithms.column_placement import ColumnPlacementEngine
    COLUMN_ENGINE_AVAILABLE = True
except Exception:
    COLUMN_ENGINE_AVAILABLE = False
    ColumnPlacementEngine = None


# =============================================================================
# BeamType — enum compatible IronPython 2.7
# =============================================================================
class BeamType(object):
    """Types de poutres selon classification structurelle."""
    PRIMARY   = "PRINCIPALE"
    SECONDARY = "SECONDAIRE"
    STIFFENER = "RAIDISSEUR"
    FLAT      = "PLATE"


# =============================================================================
# BeamPlacementEngine
# =============================================================================
class BeamPlacementEngine(object):
    """
    Moteur de placement intelligent des poutres.

    Classifie automatiquement les poutres selon leur fonction structurelle
    et calcule leurs dimensions selon les regles de l art.

    Attributs publics modifiables depuis l UI :
        MAX_STIFFENER_SPACING  (mm)  : espacement max entre raidisseurs
        MIN_SPAN_MM            (mm)  : portee minimale pour creer une poutre
        DUPLICATE_TOLERANCE_FT (ft)  : tolerance anti-doublon
    """

    # -- Ratios hauteur/portee ------------------------------------------------
    PRIMARY_SPAN_RATIO_MIN   = 1.0 / 12    # L/12
    PRIMARY_SPAN_RATIO_MAX   = 1.0 / 8     # L/8
    SECONDARY_SPAN_RATIO_MIN = 1.0 / 16    # L/16
    SECONDARY_SPAN_RATIO_MAX = 1.0 / 12    # L/12
    WIDTH_HEIGHT_RATIO_MIN   = 0.3
    WIDTH_HEIGHT_RATIO_MAX   = 0.5

    # -- Parametres publics modifiables ---------------------------------------
    MIN_SPAN_MM             = 500           # portee min (mm)
    MAX_STIFFENER_SPACING   = 3000          # espacement max raidisseurs (mm)
    DUPLICATE_TOLERANCE_FT  = 0.5          # ~152 mm en pieds

    # -------------------------------------------------------------------------
    def __init__(self, doc, api_client=None):
        self.doc    = doc
        self.api    = api_client
        self.logger = LoggingService(api_client)

        # Services optionnels
        self.revit_service    = RevitService(doc)    if SERVICES_AVAILABLE else None
        self.geometry_service = GeometryService(doc) if SERVICES_AVAILABLE else None

        # ColumnPlacementEngine optionnel
        self.column_engine = (ColumnPlacementEngine(doc, api_client)
                              if COLUMN_ENGINE_AVAILABLE else None)

        # Caches
        self._beam_types_cache = {}
        self._levels_cache     = None
        self._columns_cache    = None

    # =========================================================================
    # 1. CLASSIFICATION
    # =========================================================================

    def classify_beam_type(self,
                           start_support,
                           end_support,
                           span_mm,
                           bay_dimensions,
                           slab_thickness_mm=160,
                           portees_orient=None):
        """
        Classifie le type de poutre selon sa portee et son rapport section/dalle.

        Regles :
          PRINCIPALE  : cote court de la travee (premiere portee de l orientation)
          PLATE       : largeur calculee > epaisseur dalle
          RAIDISSEUR  : largeur calculee = epaisseur dalle (section carree)
          SECONDAIRE  : largeur calculee < epaisseur dalle

        Args:
            start_support     : dict support de depart
            end_support       : dict support d arrivee
            span_mm           : portee en mm
            bay_dimensions    : (largeur, longueur) travee mm
            slab_thickness_mm : epaisseur dalle mm
            portees_orient    : liste triee des portees de meme orientation

        Returns:
            str (BeamType constant)
        """
        # Section theorique selon L/9
        height_mm = calculate_beam_height(span_mm / 1000.0)
        width_mm  = max(150, int(round(height_mm * 0.4 / 50)) * 50)

        # PRINCIPALE : portee la plus courte de l orientation (tolerance 20 %)
        if portees_orient and len(portees_orient) > 0:
            if span_mm <= portees_orient[0] * 1.2:
                return BeamType.PRIMARY

        # PLATE : largeur > dalle
        if width_mm > slab_thickness_mm:
            return BeamType.FLAT

        # RAIDISSEUR : largeur = dalle
        if width_mm == slab_thickness_mm:
            return BeamType.STIFFENER

        # SECONDAIRE par defaut
        return BeamType.SECONDARY

    # =========================================================================
    # 2. CALCUL DES DIMENSIONS
    # =========================================================================

    def calculate_beam_dimensions(self, beam_type, span_mm, slab_thickness_mm=160):
        """
        Retourne (largeur, hauteur) en mm selon le type de poutre.

        Args:
            beam_type         : str (BeamType constant)
            span_mm           : portee mm
            slab_thickness_mm : epaisseur dalle mm

        Returns:
            (largeur_mm, hauteur_mm)
        """
        span_m = span_mm / 1000.0

        if beam_type == BeamType.PRIMARY:
            height_mm = calculate_beam_height(span_m)                  # L/9
            width_mm  = max(150, int(round(height_mm * 0.4 / 50)) * 50)

        elif beam_type == BeamType.SECONDARY:
            height_mm = slab_thickness_mm
            width_mm  = max(150, int(round(height_mm * 0.4 / 50)) * 50)
            # S assurer que largeur < dalle
            if width_mm >= slab_thickness_mm:
                width_mm = max(150, slab_thickness_mm - 50)

        elif beam_type == BeamType.STIFFENER:
            height_mm = slab_thickness_mm
            width_mm  = slab_thickness_mm

        else:  # FLAT
            height_mm = slab_thickness_mm
            width_mm  = int(round(height_mm * 1.5 / 50)) * 50
            # S assurer que largeur > dalle
            if width_mm <= slab_thickness_mm:
                width_mm = slab_thickness_mm + 50

        # Minimums absolus
        return (max(150, width_mm), max(200, height_mm))

    def get_slab_thickness(self, level):
        """
        Retourne l epaisseur de dalle (mm) par defaut selon le nom du niveau.
        """
        name = level.Name.lower()
        if any(m in name for m in ["sous-sol", "basement", "sotano"]):
            return 200
        if any(m in name for m in ["toit", "roof", "techo", "terrasse", "terrace"]):
            return 180
        return 160

    # =========================================================================
    # 3. RECUPERATION DES POTEAUX
    # =========================================================================

    def get_all_columns(self):
        """
        Recupere tous les poteaux du document avec leur position et niveau.

        Returns:
            Liste de dicts : {id, element, point, level_id, type}
        """
        if self._columns_cache is not None:
            return self._columns_cache

        try:
            collector = (FilteredElementCollector(self.doc)
                         .OfCategory(BuiltInCategory.OST_StructuralColumns)
                         .WhereElementIsNotElementType())

            result = []
            for col in collector:
                loc = col.Location
                if not hasattr(loc, 'Point'):
                    continue
                param = col.get_Parameter(BuiltInParameter.FAMILY_LEVEL_PARAM)
                result.append({
                    'id'      : col.Id,
                    'element' : col,
                    'point'   : loc.Point,
                    'level_id': param.AsElementId() if (param and param.HasValue) else None,
                    'type'    : 'column',
                })
            self._columns_cache = result
        except Exception as e:
            self.logger.log_error(e, {'context': 'get_all_columns'})
            self._columns_cache = []

        return self._columns_cache

    def get_columns_for_level(self, level):
        """Retourne uniquement les poteaux du niveau donne."""
        return [c for c in self.get_all_columns()
                if c.get('level_id') == level.Id]

    # =========================================================================
    # 4. ANTI-DOUBLON
    # =========================================================================

    def check_existing_beams(self, level, tolerance_ft=None):
        """
        Detecte les poutres deja presentes au niveau donne.

        Args:
            level        : Niveau Revit
            tolerance_ft : tolerance de comparaison (pieds)

        Returns:
            dict {
              'existing' : liste de dicts {element, start, end},
              'count'    : nombre de poutres existantes,
            }
        """
        if tolerance_ft is None:
            tolerance_ft = self.DUPLICATE_TOLERANCE_FT

        existing = []
        try:
            collector = (FilteredElementCollector(self.doc)
                         .OfCategory(BuiltInCategory.OST_StructuralFraming)
                         .WhereElementIsNotElementType())

            for beam in collector:
                loc = beam.Location
                if not hasattr(loc, 'Curve'):
                    continue
                param = beam.get_Parameter(
                    BuiltInParameter.INSTANCE_REFERENCE_LEVEL_PARAM)
                if not param or not param.HasValue:
                    continue
                beam_level_id = param.AsElementId()
                if beam_level_id != level.Id:
                    continue
                curve = loc.Curve
                existing.append({
                    'element': beam,
                    'start'  : curve.GetEndPoint(0),
                    'end'    : curve.GetEndPoint(1),
                })
        except Exception as e:
            self.logger.log_error(e, {'context': 'check_existing_beams'})

        return {'existing': existing, 'count': len(existing)}

    def _is_duplicate_beam(self, start, end, existing_beams, tol_ft=None):
        """
        Retourne True si la poutre (start, end) existe deja dans la liste.

        BUG 4 FIX : comparaison sur XY UNIQUEMENT (ignore Z).
        Deux poutres au meme emplacement XY mais a des elevations differentes
        sont considerees comme doublons pour eviter les avertissements Revit
        "occurrences identiques au meme emplacement" lors de recreations
        multi-niveaux.

        Comparaison bidirectionnelle : (A->B) == (B->A)
        """
        if tol_ft is None:
            tol_ft = self.DUPLICATE_TOLERANCE_FT

        def close_xy(p1, p2):
            """Distance 2D uniquement (ignore Z)."""
            dx = p1.X - p2.X
            dy = p1.Y - p2.Y
            return math.sqrt(dx * dx + dy * dy) < tol_ft

        for ex in existing_beams:
            if ((close_xy(start, ex['start']) and close_xy(end,   ex['end'])) or
                    (close_xy(start, ex['end'])   and close_xy(end, ex['start']))):
                return True
        return False

    # =========================================================================
    # 5. FAMILLES DE POUTRES
    # =========================================================================

    def get_beam_family(self, width, height, beam_type):
        """
        Recupere le FamilySymbol de poutre le plus proche des dimensions cibles.

        Recherche d abord par nom exact puis par dimensions proches.
        Retourne None si aucune famille n est chargee.
        """
        cache_key = "%dx%d_%s" % (width, height, beam_type)
        if cache_key in self._beam_types_cache:
            return self._beam_types_cache[cache_key]

        try:
            collector = (FilteredElementCollector(self.doc)
                         .OfCategory(BuiltInCategory.OST_StructuralFraming)
                         .WhereElementIsElementType())

            best_elem = None
            best_diff = float('inf')

            width_names  = ["Largeur", "Width", "b", "bf", "B"]
            height_names = ["Hauteur", "Height", "h", "d", "H"]

            for elem in collector:
                if not isinstance(elem, FamilySymbol):
                    continue
                w_val = h_val = 0.0
                for pn in width_names:
                    try:
                        p = elem.LookupParameter(pn)
                        if p and p.HasValue and p.AsDouble() > 0:
                            w_val = feet_to_mm(p.AsDouble()); break
                    except: pass
                for pn in height_names:
                    try:
                        p = elem.LookupParameter(pn)
                        if p and p.HasValue and p.AsDouble() > 0:
                            h_val = feet_to_mm(p.AsDouble()); break
                    except: pass
                if w_val == 0 and h_val == 0:
                    continue
                diff = abs(w_val - width) + abs(h_val - height)
                if diff < best_diff:
                    best_diff = diff
                    best_elem = elem

            if best_elem:
                self.logger.log_info(
                    "Famille poutre : diff=%.0fmm pour %dx%d (%s)" % (
                        best_diff, width, height, beam_type))
                self._beam_types_cache[cache_key] = best_elem
                return best_elem

            self.logger.log_warning(
                "Aucune famille poutre pour %dx%d (%s)" % (width, height, beam_type))
        except Exception as e:
            self.logger.log_error(e, {'context': 'get_beam_family',
                                       'width': width, 'height': height})
        return None

    # =========================================================================
    # 6. GENERATION DU RESEAU DE POUTRES
    # =========================================================================

    # ── Tolerance de regroupement : 25 mm = 0.082 ft ─────────────────────────
    # BUG 3 FIX : l ancienne valeur (round 0 = ±152mm) regroupait des poteaux
    # qui n etaient PAS sur le meme axe, generant des poutres diagonales.
    # Avec ±25mm, seuls les poteaux reellement alignes sont regroupes.
    ALIGN_TOLERANCE_FT = 0.082   # ~25 mm

    def _group_by_axis(self, columns, axis='Y'):
        """
        Regroupe les poteaux par axe avec une tolerance fine.

        BUG 3 FIX : remplace le simple round(val, 0) par un clustering
        base sur ALIGN_TOLERANCE_FT (±25 mm) pour eviter les faux alignements
        qui generaient des poutres diagonales.

        Args:
            columns : liste de dicts poteaux
            axis    : 'Y' pour grouper sur Y (lignes X) ou 'X' pour grouper sur X (lignes Y)

        Returns:
            dict { representant_ft : [col, ...] }
        """
        coord_attr = 'Y' if axis == 'Y' else 'X'
        groups     = {}   # representant -> [col]

        for col in columns:
            val = col['point'].Y if axis == 'Y' else col['point'].X

            # Chercher un groupe existant a ±ALIGN_TOLERANCE_FT
            matched = None
            for rep in groups.keys():
                if abs(val - rep) <= self.ALIGN_TOLERANCE_FT:
                    matched = rep
                    break

            if matched is not None:
                groups[matched].append(col)
            else:
                groups[val] = [col]

        return groups

    def generate_beam_grid(self, level):
        """
        Genere le reseau de poutres pour un niveau.

        Algorithme :
          1. Recuperer les poteaux du niveau
          2. Grouper par axe Y (lignes) et axe X (colonnes)
             avec tolerance fine ±25mm (BUG 3 FIX)
          3. Connecter poteaux adjacents dans chaque direction
          4. Filtrer portees < MIN_SPAN_MM
          5. Pre-calculer portees par orientation pour classification
          6. Classifier et dimensionner chaque poutre
          7. Inserer raidisseurs intermediaires si portee > MAX_STIFFENER_SPACING

        Args:
            level : Niveau Revit

        Returns:
            Liste de dicts decrivant chaque poutre a creer
        """
        level_columns = self.get_columns_for_level(level)

        if len(level_columns) < 2:
            self.logger.log_warning(
                "Pas assez de poteaux au niveau '%s' (%d)" % (
                    level.Name, len(level_columns)))
            return []

        slab_mm = self.get_slab_thickness(level)

        # ── Groupement des poteaux par axe (BUG 3 FIX) ───────────────────────
        # rows     : groupes par Y constant (poutres dans le sens X)
        # cols_map : groupes par X constant (poutres dans le sens Y)
        rows     = self._group_by_axis(level_columns, axis='Y')
        cols_map = self._group_by_axis(level_columns, axis='X')

        self.logger.log_info(
            "Niveau '%s' : %d lignes-X | %d colonnes-Y detectees" % (
                level.Name, len(rows), len(cols_map)))

        # ── Collecte des paires primaires (poteau->poteau) ───────────────────
        beams_raw = []

        # Sens X : poteaux sur meme ligne horizontale (meme Y)
        for yr in sorted(rows.keys()):
            row_sorted = sorted(rows[yr], key=lambda c: c['point'].X)
            for i in range(len(row_sorted) - 1):
                c1 = row_sorted[i]; c2 = row_sorted[i + 1]
                span_mm = calculate_distance(c1['point'], c2['point']) * 304.8
                if span_mm >= self.MIN_SPAN_MM:
                    beams_raw.append((c1, c2, span_mm, 'X'))

        # Sens Y : poteaux sur meme colonne verticale (meme X)
        for xr in sorted(cols_map.keys()):
            col_sorted = sorted(cols_map[xr], key=lambda c: c['point'].Y)
            for i in range(len(col_sorted) - 1):
                c1 = col_sorted[i]; c2 = col_sorted[i + 1]
                span_mm = calculate_distance(c1['point'], c2['point']) * 304.8
                if span_mm >= self.MIN_SPAN_MM:
                    beams_raw.append((c1, c2, span_mm, 'Y'))

        if not beams_raw:
            self.logger.log_warning(
                "Aucune portee valide au niveau '%s'" % level.Name)
            return []

        # ── Pre-calcul portees par orientation ───────────────────────────────
        portees_x = sorted(set([round(s) for _, _, s, o in beams_raw if o == 'X']))
        portees_y = sorted(set([round(s) for _, _, s, o in beams_raw if o == 'Y']))

        self.logger.log_info("Niveau '%s' | Portees X: %s" % (level.Name, portees_x[:8]))
        self.logger.log_info("Niveau '%s' | Portees Y: %s" % (level.Name, portees_y[:8]))

        # ── Classification + dimensionnement ─────────────────────────────────
        beams = []
        elev  = level.Elevation    # BUG 2 FIX : elevation de reference

        for c1, c2, span_mm, orient in beams_raw:
            portees_orient = portees_x if orient == 'X' else portees_y

            beam_type     = self.classify_beam_type(
                c1, c2, span_mm, (span_mm, span_mm), slab_mm, portees_orient)
            width, height = self.calculate_beam_dimensions(
                beam_type, span_mm, slab_mm)

            # BUG 2 FIX : forcer Z = elevation du niveau des maintenant
            # pour que les coordonnees stockees soient coherentes avec
            # ce qui sera passe a Line.CreateBound plus tard.
            p1_flat = XYZ(c1['point'].X, c1['point'].Y, elev) if REVIT_AVAILABLE else c1['point']
            p2_flat = XYZ(c2['point'].X, c2['point'].Y, elev) if REVIT_AVAILABLE else c2['point']

            beams.append({
                'start'        : p1_flat,
                'end'          : p2_flat,
                'start_support': c1,
                'end_support'  : c2,
                'span_mm'      : span_mm,
                'type'         : beam_type,
                'width'        : width,
                'height'       : height,
                'level'        : level,
                'orientation'  : orient,
                'slab_mm'      : slab_mm,
            })

        # ── (AJOUT v2) Raidisseurs intermediaires ────────────────────────────
        inter_stiffeners = self._generate_intermediate_stiffeners(
            beams, level, slab_mm, orient_filter=None)
        beams.extend(inter_stiffeners)

        self.logger.log_info(
            "Niveau '%s' : %d poutres (%d raidisseurs inter.)" % (
                level.Name, len(beams), len(inter_stiffeners)))
        return beams

    def _generate_intermediate_stiffeners(self, beams, level, slab_mm,
                                           orient_filter=None):
        """
        (AJOUT v2) Insere des raidisseurs intermediaires pour les poutres
        principales dont la portee depasse MAX_STIFFENER_SPACING.

        Strategie :
          - Pour chaque poutre PRINCIPALE avec span > MAX_STIFFENER_SPACING
          - Calcul du nombre de segments : n = ceil(span / MAX_STIFFENER_SPACING)
          - Placement d un raidisseur a chaque point intermediaire

        Returns:
            Liste de dicts poutre (type=RAIDISSEUR)
        """
        max_spacing_ft = mm_to_feet(self.MAX_STIFFENER_SPACING)
        stiffeners     = []

        for beam in beams:
            if beam['type'] != BeamType.PRIMARY:
                continue
            if beam['span_mm'] <= self.MAX_STIFFENER_SPACING:
                continue

            p1 = beam['start']
            p2 = beam['end']
            n_segs = int(math.ceil(beam['span_mm'] / self.MAX_STIFFENER_SPACING))

            for k in range(1, n_segs):
                t  = k / float(n_segs)
                mx = p1.X + t * (p2.X - p1.X)
                my = p1.Y + t * (p2.Y - p1.Y)
                mz = p1.Z + t * (p2.Z - p1.Z)

                # Raidisseur perpendiculaire : courte portee fictive = slab_mm
                stiffeners.append({
                    'start'        : XYZ(mx, my, mz) if REVIT_AVAILABLE else None,
                    'end'          : XYZ(mx, my, mz) if REVIT_AVAILABLE else None,
                    'start_support': None,
                    'end_support'  : None,
                    'span_mm'      : self.MAX_STIFFENER_SPACING,
                    'type'         : BeamType.STIFFENER,
                    'width'        : slab_mm,
                    'height'       : slab_mm,
                    'level'        : level,
                    'orientation'  : 'INTER',
                    'slab_mm'      : slab_mm,
                    'is_intermediate': True,
                })

        return stiffeners

    # =========================================================================
    # 7. LECTURE DES POUTRES EXISTANTES
    # =========================================================================

    def get_beams_for_level(self, level):
        """
        (AJOUT v2) Retourne les poutres Revit existantes pour un niveau.

        Returns:
            Liste d elements Revit (StructuralFraming)
        """
        result = []
        try:
            collector = (FilteredElementCollector(self.doc)
                         .OfCategory(BuiltInCategory.OST_StructuralFraming)
                         .WhereElementIsNotElementType())
            for beam in collector:
                param = beam.get_Parameter(
                    BuiltInParameter.INSTANCE_REFERENCE_LEVEL_PARAM)
                if param and param.HasValue and param.AsElementId() == level.Id:
                    result.append(beam)
        except Exception as e:
            self.logger.log_error(e, {'context': 'get_beams_for_level'})
        return result

    # =========================================================================
    # 8. CREATION EFFECTIVE DES POUTRES
    # =========================================================================

    def create_beams_for_level(self, level):
        """
        Cree toutes les poutres pour un niveau donne.

        CORRECTION v2 :
          - Gestion de transaction EXPLICITE (sans decorateur @transaction)
          - Anti-doublon : verifie les poutres deja presentes
          - Retourne une liste d ELEMENTS REVIT natifs (compatible UI v9)

        Args:
            level : Niveau Revit

        Returns:
            Liste d elements Revit (FamilyInstance) crees
        """
        beam_data = self.generate_beam_grid(level)

        if not beam_data:
            self.logger.log_warning(
                "Aucune poutre a creer au niveau '%s'" % level.Name)
            return []

        # Poutres deja existantes (anti-doublon)
        existing_check = self.check_existing_beams(level)
        existing_beams = existing_check['existing']
        if existing_beams:
            self.logger.log_info(
                "%d poutres existantes au niveau '%s' (anti-doublon actif)" % (
                    len(existing_beams), level.Name))

        created_elements = []
        errors           = []

        t = Transaction(self.doc, "AutoRevit - Poutres %s" % level.Name)
        t.Start()

        try:
            for data in beam_data:
                # Sauter les raidisseurs intermediaires sans geometrie valide
                if data.get('is_intermediate') and data['start'] == data['end']:
                    continue

                start = data['start']
                end   = data['end']

                # Anti-doublon
                if self._is_duplicate_beam(start, end, existing_beams):
                    self.logger.log_info(
                        "  Doublon ignore : %s" % data['type'])
                    continue

                # Famille
                beam_family = self.get_beam_family(
                    data['width'], data['height'], data['type'])
                if not beam_family:
                    errors.append("Famille introuvable : %dx%d %s" % (
                        data['width'], data['height'], data['type']))
                    continue

                if not beam_family.IsActive:
                    beam_family.Activate()
                    self.doc.Regenerate()

                try:
                    # Z deja force a level.Elevation dans generate_beam_grid
                    # (BUG 2 FIX) - pas besoin de recalculer ici.
                    line = Line.CreateBound(start, end)
                    beam = self.doc.Create.NewFamilyInstance(
                        line,
                        beam_family,
                        data['level'],
                        StructuralType.Beam
                    )

                    # BUG 1 FIX : INSTANCE_REFERENCE_LEVEL_PARAM est EN LECTURE
                    # SEULE apres creation - ne pas tenter ref_param.Set().
                    # Le niveau est deja assigne via NewFamilyInstance.

                    # Commentaire AutoRevit
                    c_param = beam.LookupParameter("Comments")
                    if c_param:
                        c_param.Set(
                            "AutoRevit | %s | L=%dmm | %dx%d" % (
                                data['type'],
                                int(data['span_mm']),
                                data['width'],
                                data['height']))

                    # Enregistrer pour anti-doublon intra-transaction
                    existing_beams.append({'element': beam,
                                           'start': start,
                                           'end':   end})
                    created_elements.append(beam)

                except Exception as e_inner:
                    errors.append("Erreur creation poutre : %s" % str(e_inner))
                    self.logger.log_error(e_inner, {
                        'level'    : level.Name,
                        'type'     : data['type'],
                        'span_mm'  : data['span_mm'],
                        'dims'     : (data['width'], data['height']),
                    })

            t.Commit()

        except Exception as e_trans:
            try: t.RollBack()
            except: pass
            self.logger.log_error(e_trans, {'context': 'create_beams_for_level',
                                             'level': level.Name})
            return []

        # Rapport final
        n_ok  = len(created_elements)
        n_err = len(errors)
        self.logger.log_info(
            "Niveau '%s' : %d poutres creees | %d erreurs" % (
                level.Name, n_ok, n_err))
        for err in errors[:10]:
            self.logger.log_warning("  " + err)

        # Forcer la visibilite des poutres dans les plans de ce niveau
        if created_elements:
            try:
                vis = self.make_beams_visible_in_views(target_level=level)
                if vis['views_updated'] > 0:
                    self.logger.log_info(
                        "Visibilite activee dans %d vue(s)" % vis['views_updated'])
            except Exception as e_vis:
                self.logger.log_warning(
                    "Visibilite non forcee : %s" % str(e_vis))

        return created_elements

    # =========================================================================
    # 9. VISIBILITE DES POUTRES DANS LES PLANS
    # =========================================================================

    def make_beams_visible_in_views(self, target_level=None):
        """
        Force la visibilite des poutres (Ossature Structurelle) dans tous
        les plans du projet ET corrige le ViewRange (plan de coupe).

        DIAGNOSTIC :
          Le probleme n est pas seulement la categorie cachee.
          Dans un Plan de Structure Revit, les poutres sont horizontales
          A l elevation du niveau. Si le plan de coupe est AU-DESSUS de
          cette elevation, les poutres sont dans la zone "Sous" (Below) =>
          affichees en lignes tiretees ou INVISIBLES selon le reglage.

          Schema ViewRange typique :
            Top     : Niveau + 3600mm  <- haut
            CutPlane: Niveau + 1200mm  <- plan de coupe (trop haut !)
            Bottom  : Niveau - 300mm   <- bas
            View Depth: Niveau - 300mm

          Les poutres a Elevation=Niveau sont SOUS le plan de coupe
          => affichees selon "View Depth" => souvent invisible.

          CORRECTION : abaisser CutPlane a Niveau + 100mm (juste au-dessus
          des poutres) et s assurer que Bottom est en dessous de l elevation.

        Args:
            target_level : niveau cible (None = tous les niveaux)

        Returns:
            dict { 'views_updated': int, 'range_fixed': int, 'errors': list }
        """
        try:
            from Autodesk.Revit.DB import (
                ViewPlan, ViewDetailLevel, PlanViewRange, PlanViewPlane)
        except Exception as e:
            return {'views_updated': 0, 'range_fixed': 0, 'errors': [str(e)]}

        views_updated = 0
        range_fixed   = 0
        errors        = []

        # Categorie "Ossature Structurelle"
        try:
            framing_cat = self.doc.Settings.Categories.get_Item(
                BuiltInCategory.OST_StructuralFraming)
            if framing_cat is None:
                return {'views_updated': 0, 'range_fixed': 0,
                        'errors': ['Categorie OST_StructuralFraming introuvable']}
        except Exception as e:
            return {'views_updated': 0, 'range_fixed': 0, 'errors': [str(e)]}

        # Toutes les vues plan
        try:
            all_views = list(FilteredElementCollector(self.doc)
                             .OfClass(ViewPlan).ToElements())
        except Exception as e:
            return {'views_updated': 0, 'range_fixed': 0, 'errors': [str(e)]}

        # Map niveau_name -> elevation (pieds)
        level_elevations = {}
        try:
            for lv in get_all_levels(self.doc):
                level_elevations[lv.Name] = lv.Elevation
        except:
            pass

        t_vis = Transaction(self.doc, "AutoRevit - Visibilite + ViewRange poutres")
        t_vis.Start()

        try:
            for view in all_views:
                try:
                    if view.IsTemplate:
                        continue

                    # Filtre par niveau si demande
                    if target_level is not None:
                        vp = view.get_Parameter(BuiltInParameter.PLAN_VIEW_LEVEL)
                        if not vp or vp.AsString() != target_level.Name:
                            continue

                    # ── 1. Rendre la categorie visible ───────────────────────
                    try:
                        if view.GetCategoryHidden(framing_cat.Id):
                            view.SetCategoryHidden(framing_cat.Id, False)
                            views_updated += 1
                            self.logger.log_info(
                                "Vue '%s' : Ossature Structurelle rendue visible"
                                % view.Name)
                    except:
                        pass

                    # ── 2. Niveau de detail Medium minimum ───────────────────
                    try:
                        if view.DetailLevel == ViewDetailLevel.Coarse:
                            view.DetailLevel = ViewDetailLevel.Medium
                    except:
                        pass

                    # ── 3. CORRIGER LE VIEW RANGE (cause principale) ──────────
                    # Les poutres sont a Z=elevation_niveau.
                    # Le plan de coupe doit etre ENTRE les poutres et le plafond.
                    # On descend le CutPlane a niveau+100mm et Bottom a niveau-600mm
                    # pour garantir que les poutres tombent dans la zone "coupee".
                    try:
                        vp_param = view.get_Parameter(
                            BuiltInParameter.PLAN_VIEW_LEVEL)
                        level_name = vp_param.AsString() if vp_param else None
                        elev_ft    = level_elevations.get(level_name, None)

                        if elev_ft is not None:
                            pvr = view.GetViewRange()

                            # Lire les offsets actuels du plan de coupe
                            cut_offset = pvr.GetOffset(PlanViewPlane.CutPlane)
                            bot_offset = pvr.GetOffset(PlanViewPlane.BottomClipPlane)

                            # 100mm au-dessus du niveau = 0.328 ft
                            # -600mm en dessous = -1.969 ft
                            target_cut = mm_to_feet(100)    #  ~0.33 ft
                            target_bot = mm_to_feet(-600)   # ~-1.97 ft

                            changed = False

                            # Abaisser le CutPlane si actuellement > 100mm
                            if cut_offset > target_cut + 0.01:
                                pvr.SetOffset(PlanViewPlane.CutPlane, target_cut)
                                changed = True

                            # Abaisser le Bottom si necessaire
                            if bot_offset > target_bot + 0.01:
                                pvr.SetOffset(PlanViewPlane.BottomClipPlane,
                                              target_bot)
                                # View Depth = meme chose que Bottom
                                try:
                                    pvr.SetOffset(PlanViewPlane.ViewDepthPlane,
                                                  target_bot)
                                except:
                                    pass
                                changed = True

                            if changed:
                                view.SetViewRange(pvr)
                                range_fixed += 1
                                self.logger.log_info(
                                    "Vue '%s' : ViewRange corrige "
                                    "(cut=+100mm, bot=-600mm)" % view.Name)

                    except Exception as e_range:
                        # ViewRange non modifiable (gabarit lie, etc.)
                        errors.append("ViewRange '%s' : %s" % (
                            getattr(view, 'Name', '?'), str(e_range)))

                except Exception as e_v:
                    errors.append("Vue '%s' : %s" % (
                        getattr(view, 'Name', '?'), str(e_v)))

            t_vis.Commit()

        except Exception as e_t:
            try: t_vis.RollBack()
            except: pass
            return {'views_updated': 0, 'range_fixed': 0,
                    'errors': [str(e_t)]}

        self.logger.log_info(
            "Visibilite : %d categories activees | %d ViewRange corriges | "
            "%d erreurs" % (views_updated, range_fixed, len(errors)))

        return {
            'views_updated': views_updated,
            'range_fixed'  : range_fixed,
            'errors'       : errors,
        }

    def ensure_structural_plan_views(self):
        """
        Cree un Plan de Structure (Structural Plan / EngineeringPlan) pour
        chaque niveau structurel qui n en a pas encore.

        Les Plans de Structure affichent les poutres par defaut car leur
        plan de coupe est configure differemment des Plans d Etage.

        Returns:
            dict { 'created': [noms], 'existing': [noms], 'errors': list }
        """
        try:
            from Autodesk.Revit.DB import (
                ViewPlan, ViewFamily, ViewFamilyType, ViewType)
        except Exception as e:
            return {'created': [], 'existing': [], 'errors': [str(e)]}

        created  = []
        existing = []
        errors   = []

        # Trouver le gabarit ViewFamilyType de type StructuralPlan
        structural_vft = None
        try:
            for vft in (FilteredElementCollector(self.doc)
                        .OfClass(ViewFamilyType).ToElements()):
                if vft.ViewFamily == ViewFamily.StructuralPlan:
                    structural_vft = vft
                    break
        except Exception as e:
            return {'created': [], 'existing': [],
                    'errors': ["Gabarit StructuralPlan : %s" % str(e)]}

        if structural_vft is None:
            return {'created': [], 'existing': [],
                    'errors': ["Aucun gabarit 'Structural Plan' dans le projet"]}

        # Noms des plans de structure existants
        existing_names = set()
        try:
            for v in (FilteredElementCollector(self.doc)
                      .OfClass(ViewPlan).ToElements()):
                if v.ViewType == ViewType.EngineeringPlan:
                    existing_names.add(v.Name)
        except:
            pass

        _TOIT_MOTS = ["toit", "roof", "techo", "terrasse", "terrace",
                      "toiture", "acrotere", "acrotera", "cubierta"]
        levels = sorted(get_all_levels(self.doc), key=lambda l: l.Elevation)

        t_sp = Transaction(self.doc, "AutoRevit - Plans de structure")
        t_sp.Start()

        try:
            for level in levels:
                if any(m in level.Name.lower() for m in _TOIT_MOTS):
                    continue

                vname = "Structure - %s" % level.Name

                if vname in existing_names:
                    existing.append(vname)
                    continue

                try:
                    nv = ViewPlan.Create(self.doc, structural_vft.Id, level.Id)
                    nv.Name = vname
                    created.append(vname)
                    self.logger.log_info("Plan structure cree : '%s'" % vname)
                except Exception as e_c:
                    errors.append("'%s' : %s" % (vname, str(e_c)))

            t_sp.Commit()

        except Exception as e_t:
            try: t_sp.RollBack()
            except: pass
            errors.append("Transaction : %s" % str(e_t))

        self.logger.log_info(
            "Plans structure : %d crees | %d existants | %d erreurs" % (
                len(created), len(existing), len(errors)))
        return {'created': created, 'existing': existing, 'errors': errors}

    # =========================================================================
    # 10. CREATION SUR TOUS LES NIVEAUX
    # =========================================================================

    def create_all_beams(self):
        """
        Cree les poutres pour tous les niveaux structurels du projet.

        CORRECTION v2 :
          - Exclut les niveaux toit / terrasse
          - Remonte des statistiques par type dans le resultat
          - Resilient : un echec sur un niveau n arrete pas les autres

        Returns:
            dict {
              'success'    : bool,
              'total_beams': int,
              'by_level'   : { level_name : {'count', 'by_type', 'beams'} },
              'errors'     : list,
            }
        """
        _TOIT_MOTS = ["toit", "roof", "techo", "terrasse", "terrace",
                      "toiture", "acrotere", "acrotera", "cubierta"]

        levels = sorted(get_all_levels(self.doc), key=lambda l: l.Elevation)

        results     = {}
        total_beams = 0
        all_errors  = []

        for level in levels:
            nom = level.Name.lower()
            if any(m in nom for m in _TOIT_MOTS):
                self.logger.log_info("Niveau '%s' ignore (toit)" % level.Name)
                continue

            try:
                beams_created = self.create_beams_for_level(level)
                n = len(beams_created)

                # Comptage par type via le commentaire AutoRevit
                by_type = {
                    BeamType.PRIMARY  : 0,
                    BeamType.SECONDARY: 0,
                    BeamType.STIFFENER: 0,
                    BeamType.FLAT     : 0,
                    "Autre"           : 0,
                }
                for b in beams_created:
                    try:
                        cp = b.LookupParameter("Comments")
                        label_found = False
                        if cp and cp.AsString():
                            s = cp.AsString()
                            for t in [BeamType.PRIMARY, BeamType.SECONDARY,
                                      BeamType.STIFFENER, BeamType.FLAT]:
                                if t in s:
                                    by_type[t] += 1; label_found = True; break
                        if not label_found:
                            by_type["Autre"] += 1
                    except:
                        by_type["Autre"] += 1

                results[level.Name] = {
                    'count'  : n,
                    'by_type': by_type,
                    'beams'  : beams_created,
                }
                total_beams += n
                self.logger.log_info(
                    "Niveau '%s' : %d poutres (P=%d S=%d R=%d Pl=%d)" % (
                        level.Name, n,
                        by_type[BeamType.PRIMARY],
                        by_type[BeamType.SECONDARY],
                        by_type[BeamType.STIFFENER],
                        by_type[BeamType.FLAT]))

            except Exception as e_level:
                msg = "Niveau '%s' : ERREUR - %s" % (level.Name, str(e_level))
                all_errors.append(msg)
                self.logger.log_error(e_level, {'level': level.Name})
                self._columns_cache = None  # reset cache pour le prochain niveau

        self.logger.log_info(
            "create_all_beams termine : %d poutres | %d erreurs" % (
                total_beams, len(all_errors)))

        return {
            'success'    : len(all_errors) == 0,
            'total_beams': total_beams,
            'by_level'   : results,
            'errors'     : all_errors,
        }


# =============================================================================
# POINT D'ENTREE (pyRevit)
# =============================================================================
def main():
    try:
        from pyrevit import revit, forms
    except ImportError:
        print("pyrevit non disponible")
        return

    doc = revit.doc

    collector = (FilteredElementCollector(doc)
                 .OfCategory(BuiltInCategory.OST_StructuralColumns)
                 .WhereElementIsNotElementType())

    if collector.GetElementCount() == 0:
        forms.alert(
            "Aucun poteau trouve.\nCreez d abord les poteaux.",
            title="AutoRevit - Creation poutres")
        return

    engine = BeamPlacementEngine(doc)

    if not forms.alert(
        "Creer les poutres pour tous les niveaux ?",
        title="AutoRevit - Creation poutres",
        ok=False, yes=True, no=True
    ):
        return

    result = engine.create_all_beams()

    if result['success']:
        details = "\n".join(
            "  %s : %d poutres" % (lvl, data['count'])
            for lvl, data in sorted(result['by_level'].items()))
        forms.alert(
            "%d poutres creees !\n\n%s" % (result['total_beams'], details),
            title="AutoRevit - Succes")
    else:
        errors = "\n".join(result['errors'][:10])
        forms.alert(
            "%d poutres creees avec %d erreurs :\n%s" % (
                result['total_beams'], len(result['errors']), errors),
            title="AutoRevit - Termine avec erreurs")


if __name__ == '__main__':
    main()