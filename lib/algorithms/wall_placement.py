# -*- coding: utf-8 -*-
"""Algorithme de placement des voiles et detection d'ouvertures

REGLES METIER IMPLEMENTEES :

1. DETECTION OUVERTURES
   - Scanner portes et fenetres
   - Identifier positions sur axe mur
   - Generer trumeaux entre ouvertures

2. SEGMENTATION
   - Diviser mur entre ouvertures
   - Creer voiles separes
   - Linteaux automatiques au-dessus

3. EPAISSEUR
   - Selon hauteur et charges
   - Min 15cm (voiles courants)
   - Min 20cm (voiles porteurs)
   - Min 25cm (sous-sol, refend)

CORRECTIONS v2.0 :
- Suppression des decorateurs @transaction et @log_execution
  (la transaction est geree par l'UI create_walls.py)
- Suppression de @handle_errors (idem)
- Correction imports geometry_utils (ajout get_rectangle_from_points,
  find_intermediate_points)
- Methodes create_walls_for_level et create_all_walls sans decorateurs
"""

import math

# Compatibilite IronPython 2.7 / Python 3
try:
    from typing import List, Dict, Tuple, Optional
except Exception:
    pass

try:
    from enum import Enum
except Exception:
    class Enum(object):
        pass

from Autodesk.Revit.DB import (
    XYZ, Line, Wall, Level, FamilySymbol,
    FilteredElementCollector, BuiltInCategory,
    BuiltInParameter,
    Curve, CurveLoop, LocationCurve,
    ElementId, Transaction
)

from services.revit_service    import RevitService
from services.geometry_service import GeometryService
from services.logging_service  import LoggingService

from helpers.revit_helpers import (
    get_all_levels, mm_to_feet, feet_to_mm,
    get_all_walls, get_all_doors, get_all_windows
)

from algorithms.geometry_utils import (
    calculate_distance,
    is_point_on_line,
    offset_point,
    project_point_on_curve,
    get_rectangle_from_points,
    find_intermediate_points,
    get_wall_orientation,
    segment_length_mm,
    points_are_collinear,
    get_wall_axis_direction,
    clamp_param,
)


try:
    from enum import Enum as _Enum

    class WallType(_Enum):
        """Types de voiles selon fonction"""
        SHEAR     = "VOILE_PORTEUR"
        RETAINING = "VOILE_SOUTENEMENT"
        PARTITION = "CLOISON"
        CORE      = "VOILE_NOYAU"

except Exception:
    class WallType(object):
        SHEAR     = "VOILE_PORTEUR"
        RETAINING = "VOILE_SOUTENEMENT"
        PARTITION = "CLOISON"
        CORE      = "VOILE_NOYAU"


class WallPlacementEngine(object):
    """
    Moteur de placement intelligent des voiles.

    Analyse les murs architecturaux, detecte les ouvertures,
    segmente et convertit en voiles structurels avec dimensions appropriees.

    IMPORTANT : Ne pas appeler create_walls_for_level() ou create_all_walls()
    depuis l'interieur d'une Transaction Revit deja ouverte.
    La gestion de la transaction est assuree par l'appelant (UI).
    """

    # Epaisseurs minimales selon usage (mm)
    MIN_THICKNESS = {
        'standard':     150,
        'load_bearing': 200,
        'basement':     250,
        'core':         300,
        'retaining':    300,
    }

    # Dimensions minimales linteaux (mm)
    LINTEL_MIN_HEIGHT = 200
    LINTEL_BEARING    = 200

    # Longueur minimale d'un segment de voile (mm)
    MIN_SEGMENT_LENGTH_MM = 200

    def __init__(self, doc, api_client=None):
        """
        Initialise le moteur de placement des voiles.

        Args:
            doc        : Document Revit actif
            api_client : Client API optionnel
        """
        self.doc              = doc
        self.api              = api_client
        self.revit_service    = RevitService(doc)
        self.geometry_service = GeometryService(doc)
        self.logger           = LoggingService(api_client)

        self._wall_types_cache = {}
        self._levels_cache     = None

    # -------------------------------------------------------------------------
    # 1. DETECTION DES OUVERTURES
    # -------------------------------------------------------------------------

    def detect_openings_on_wall(self, wall_line, level):
        """
        Detecte toutes les ouvertures (portes/fenetres) sur un mur.

        Args:
            wall_line : Ligne du mur (Curve)
            level     : Niveau concerne

        Returns:
            Liste des ouvertures avec positions et dimensions
        """
        openings = []

        doors   = get_all_doors(self.doc)
        windows = get_all_windows(self.doc)

        for door in doors:
            opening_data = self._check_opening_on_wall(door, wall_line, level, 'door')
            if opening_data:
                openings.append(opening_data)

        for window in windows:
            opening_data = self._check_opening_on_wall(window, wall_line, level, 'window')
            if opening_data:
                openings.append(opening_data)

        openings.sort(key=lambda o: o['position'])
        return openings

    def _check_opening_on_wall(self, element, wall_line, level, element_type):
        """
        Verifie si un element d'ouverture appartient a ce mur.

        Args:
            element      : Element Revit (porte/fenetre)
            wall_line    : Ligne du mur (Curve)
            level        : Niveau
            element_type : 'door' ou 'window'

        Returns:
            Donnees de l'ouverture ou None
        """
        try:
            location = element.Location
            if not location:
                return None

            if hasattr(location, 'Point'):
                point = location.Point
            else:
                return None

            if element.LevelId and element.LevelId != level.Id:
                return None

            projected, param = project_point_on_curve(point, wall_line)

            if not projected or not is_point_on_line(point, wall_line, tolerance_mm=100):
                return None

            width_param = element.get_Parameter(BuiltInParameter.DOOR_WIDTH)
            if not width_param:
                width_param = element.get_Parameter(BuiltInParameter.WINDOW_WIDTH)

            height_param = element.get_Parameter(BuiltInParameter.DOOR_HEIGHT)
            if not height_param:
                height_param = element.get_Parameter(BuiltInParameter.WINDOW_HEIGHT)

            sill_height_param = element.get_Parameter(
                BuiltInParameter.INSTANCE_SILL_HEIGHT_PARAM
            )

            width_mm       = feet_to_mm(width_param.AsDouble())       if width_param       else 900
            height_mm      = feet_to_mm(height_param.AsDouble())      if height_param      else 2100
            sill_height_mm = feet_to_mm(sill_height_param.AsDouble()) if sill_height_param else 0

            return {
                'id':             element.Id,
                'type':           element_type,
                'point':          projected,
                'position':       param,
                'width_mm':       width_mm,
                'height_mm':      height_mm,
                'sill_height_mm': sill_height_mm,
                'element':        element,
            }
        except Exception as e:
            self.logger.log_debug(
                "_check_opening_on_wall erreur : %s" % str(e)
            )
            return None

    # -------------------------------------------------------------------------
    # 2. SEGMENTATION DES MURS
    # -------------------------------------------------------------------------

    def create_wall_segments(self, wall_line, level, next_level,
                             openings, is_load_bearing=True):
        """
        Segmente un mur en voiles entre les ouvertures.

        Args:
            wall_line       : Ligne du mur original (Curve)
            level           : Niveau de base
            next_level      : Niveau superieur (pour hauteur)
            openings        : Liste des ouvertures detectees
            is_load_bearing : True si mur porteur

        Returns:
            Liste des segments de voile a creer
        """
        segments = []

        if next_level:
            wall_height_mm = feet_to_mm(next_level.Elevation - level.Elevation)
        else:
            wall_height_mm = 3000

        thickness = self.calculate_wall_thickness(wall_height_mm, is_load_bearing, level)

        start_point = wall_line.GetEndPoint(0)
        end_point   = wall_line.GetEndPoint(1)

        # Pas d'ouvertures -> voile plein
        if not openings:
            seg_len = segment_length_mm(start_point, end_point)
            if seg_len >= self.MIN_SEGMENT_LENGTH_MM:
                segments.append({
                    'start':           start_point,
                    'end':             end_point,
                    'level':           level,
                    'next_level':      next_level,
                    'height_mm':       wall_height_mm,
                    'thickness':       thickness,
                    'is_load_bearing': is_load_bearing,
                    'has_openings':    False,
                })
            return segments

        sorted_openings = sorted(openings, key=lambda o: o['position'])
        curve_length    = wall_line.Length  # en feet

        # -- Segment avant la premiere ouverture --
        first_op  = sorted_openings[0]
        sp        = 0.0
        ep        = clamp_param(
            first_op['position'] - (first_op['width_mm'] / 2.0) / feet_to_mm(curve_length)
        )

        if sp < ep:
            p1 = wall_line.Evaluate(sp, True)
            p2 = wall_line.Evaluate(ep, True)
            if segment_length_mm(p1, p2) >= self.MIN_SEGMENT_LENGTH_MM:
                segments.append(self._make_segment(
                    p1, p2, level, next_level, wall_height_mm, thickness, is_load_bearing
                ))

        # -- Segments entre ouvertures --
        for i in range(len(sorted_openings) - 1):
            cur_op  = sorted_openings[i]
            next_op = sorted_openings[i + 1]

            sp = clamp_param(
                cur_op['position']  + (cur_op['width_mm']  / 2.0) / feet_to_mm(curve_length)
            )
            ep = clamp_param(
                next_op['position'] - (next_op['width_mm'] / 2.0) / feet_to_mm(curve_length)
            )

            if sp < ep:
                p1 = wall_line.Evaluate(sp, True)
                p2 = wall_line.Evaluate(ep, True)
                if segment_length_mm(p1, p2) >= self.MIN_SEGMENT_LENGTH_MM:
                    segments.append(self._make_segment(
                        p1, p2, level, next_level, wall_height_mm, thickness, is_load_bearing
                    ))

        # -- Segment apres la derniere ouverture --
        last_op = sorted_openings[-1]
        sp = clamp_param(
            last_op['position'] + (last_op['width_mm'] / 2.0) / feet_to_mm(curve_length)
        )
        ep = 1.0

        if sp < ep:
            p1 = wall_line.Evaluate(sp, True)
            p2 = wall_line.Evaluate(ep, True)
            if segment_length_mm(p1, p2) >= self.MIN_SEGMENT_LENGTH_MM:
                segments.append(self._make_segment(
                    p1, p2, level, next_level, wall_height_mm, thickness, is_load_bearing
                ))

        return segments

    def _make_segment(self, p1, p2, level, next_level,
                      height_mm, thickness, is_load_bearing):
        """Cree un dictionnaire de segment."""
        return {
            'start':           p1,
            'end':             p2,
            'level':           level,
            'next_level':      next_level,
            'height_mm':       height_mm,
            'thickness':       thickness,
            'is_load_bearing': is_load_bearing,
            'has_openings':    False,
        }

    # -------------------------------------------------------------------------
    # 3. CALCUL DE L'EPAISSEUR
    # -------------------------------------------------------------------------

    def calculate_wall_thickness(self, height_mm, is_load_bearing, level):
        """
        Calcule l'epaisseur appropriee du voile.

        Args:
            height_mm       : Hauteur du voile (mm)
            is_load_bearing : True si voile porteur
            level           : Niveau concerne

        Returns:
            Epaisseur en mm (int)
        """
        if self._is_basement(level):
            thickness = self.MIN_THICKNESS['basement']
        elif is_load_bearing:
            thickness = self.MIN_THICKNESS['load_bearing']
        else:
            thickness = self.MIN_THICKNESS['standard']

        if height_mm > 5000:
            thickness = max(thickness, 300)
        elif height_mm > 3000:
            thickness = max(thickness, 200)

        thickness = int(round(thickness / 10.0)) * 10
        return thickness

    def _is_basement(self, level):
        """Verifie si le niveau est un sous-sol."""
        name_lower = level.Name.lower()
        return (
            "sous-sol" in name_lower or
            "basement"  in name_lower or
            "ss"        in name_lower
        )

    # -------------------------------------------------------------------------
    # 4. CREATION DES LINTEAUX (log uniquement)
    # -------------------------------------------------------------------------

    def create_lintels(self, opening, wall_thickness, level, next_level):
        """
        Journalise le besoin d'un linteau au-dessus d'une ouverture.

        Args:
            opening        : Donnees de l'ouverture
            wall_thickness : Epaisseur du voile (mm)
            level          : Niveau de base
            next_level     : Niveau superieur

        Returns:
            None
        """
        lintel_height = max(
            self.LINTEL_MIN_HEIGHT,
            int(opening['height_mm'] * 0.1)
        )
        lintel_width = opening['width_mm'] + 2 * self.LINTEL_BEARING

        self.logger.log_info(
            "Linteau requis : {0}mm x {1}mm au-dessus de {2}".format(
                lintel_width, lintel_height, opening['type']
            )
        )
        return None

    # -------------------------------------------------------------------------
    # 5. RECUPERATION DU TYPE DE MUR
    # -------------------------------------------------------------------------

    def get_wall_type(self, thickness_mm, is_structural=True):
        """
        Recupere le type de mur le plus adapte a l'epaisseur demandee.

        Args:
            thickness_mm  : Epaisseur en mm
            is_structural : True pour mur structurel

        Returns:
            WallType Revit ou None
        """
        cache_key = "{0}_{1}".format(
            thickness_mm,
            'structural' if is_structural else 'architectural'
        )

        if cache_key in self._wall_types_cache:
            return self._wall_types_cache[cache_key]

        collector = (FilteredElementCollector(self.doc)
                     .OfClass(Wall)
                     .WhereElementIsElementType())

        thickness_feet = mm_to_feet(thickness_mm)
        best_match     = None
        best_diff      = float('inf')

        for wall_type in collector:
            try:
                comp_structure = wall_type.GetCompoundStructure()
                if comp_structure:
                    width = comp_structure.GetWidth()
                    diff  = abs(width - thickness_feet)
                    if diff < best_diff:
                        best_diff  = diff
                        best_match = wall_type
            except:
                pass

        # Fallback : premier type disponible
        if best_match is None:
            best_match = collector.FirstElement()

        self._wall_types_cache[cache_key] = best_match
        return best_match

    # -------------------------------------------------------------------------
    # 6. CREATION DES VOILES POUR UN NIVEAU
    #    SANS decorateur @transaction (gere par l'UI)
    # -------------------------------------------------------------------------

    def create_walls_for_level(self, level, next_level=None,
                               convert_arch_walls=True):
        """
        Cree les voiles pour un niveau donne.

        ATTENTION : Doit etre appele a l'interieur d'une Transaction
        deja ouverte par l'appelant (UI). Ne pas appeler depuis un contexte
        sans transaction active.

        Args:
            level              : Niveau de base
            next_level         : Niveau superieur
            convert_arch_walls : Convertir les murs architecturaux existants

        Returns:
            Liste des voiles crees (dicts)
        """
        created_walls = []

        if not convert_arch_walls:
            self.logger.log_info(
                "create_walls_for_level : convert_arch_walls=False, rien a faire."
            )
            return created_walls

        arch_walls = get_all_walls(self.doc)

        for arch_wall in arch_walls:
            try:
                # Filtrer par niveau - LevelId ou WALL_BASE_CONSTRAINT
                wall_level_id = arch_wall.LevelId
                if wall_level_id == ElementId.InvalidElementId:
                    base_param = arch_wall.get_Parameter(
                        BuiltInParameter.WALL_BASE_CONSTRAINT
                    )
                    if base_param and base_param.HasValue:
                        wall_level_id = base_param.AsElementId()
                if wall_level_id != level.Id:
                    continue

                location = arch_wall.Location
                if not isinstance(location, LocationCurve):
                    continue

                wall_line = location.Curve

                # Longueur minimale
                if feet_to_mm(wall_line.Length) < self.MIN_SEGMENT_LENGTH_MM:
                    continue

                # Porteur ?
                is_load_bearing = False
                structural_usage = arch_wall.get_Parameter(
                    BuiltInParameter.WALL_STRUCTURAL_USAGE_PARAM
                )
                if structural_usage and structural_usage.HasValue:
                    is_load_bearing = structural_usage.AsInteger() != 0

                # Detection ouvertures
                openings = self.detect_openings_on_wall(wall_line, level)

                # Segmentation
                segments = self.create_wall_segments(
                    wall_line, level, next_level, openings, is_load_bearing
                )

                for segment in segments:
                    wall_type = self.get_wall_type(segment['thickness'], True)
                    if not wall_type:
                        self.logger.log_info(
                            "Aucun type de mur trouve pour epaisseur %d mm" % segment['thickness']
                        )
                        continue

                    try:
                        line = Line.CreateBound(
                            segment['start'], segment['end']
                        )

                        new_wall = Wall.Create(
                            self.doc,
                            line,
                            wall_type.Id,
                            level.Id,
                            mm_to_feet(segment['height_mm']),
                            0.0,    # offset base
                            False,  # flip
                            True    # structural
                        )

                        # Commentaire automatique
                        comments_p = new_wall.LookupParameter("Comments")
                        if comments_p:
                            comments_p.Set(
                                "AutoRevit - Voile {0} - e={1}mm".format(
                                    'porteur' if segment['is_load_bearing'] else 'non porteur',
                                    segment['thickness']
                                )
                            )

                        created_walls.append({
                            'element':         new_wall,
                            'id':              new_wall.Id,
                            'line':            (segment['start'], segment['end']),
                            'thickness':       segment['thickness'],
                            'height':          segment['height_mm'],
                            'is_load_bearing': segment['is_load_bearing'],
                        })

                        # Log linteaux
                        for opening in openings:
                            self.create_lintels(
                                opening,
                                segment['thickness'],
                                level,
                                next_level
                            )

                    except Exception as e:
                        self.logger.log_error(e, {
                            'level':   level.Name,
                            'segment': str(segment.get('thickness')),
                        })

            except Exception as e:
                self.logger.log_error(e, {
                    'level':   level.Name,
                    'wall_id': str(arch_wall.Id) if arch_wall else 'inconnu',
                })

        self.logger.log_info(
            "{0} voiles crees au niveau {1}".format(len(created_walls), level.Name)
        )
        return created_walls

    # -------------------------------------------------------------------------
    # 7. CREATION DES VOILES POUR TOUS LES NIVEAUX
    #    SANS decorateur @transaction (gere par l'UI)
    # -------------------------------------------------------------------------

    def create_all_walls(self):
        """
        Cree les voiles pour tous les niveaux du projet.

        ATTENTION : Doit etre appele a l'interieur d'une Transaction
        deja ouverte par l'appelant (UI). Ne pas ouvrir de nouvelle
        transaction ici.

        Returns:
            dict :
                success     : bool
                total_walls : int
                by_level    : dict { nom_niveau: { count, walls } }
        """
        try:
            levels = get_all_levels(self.doc)
            levels = sorted(levels, key=lambda l: l.Elevation)

            results     = {}
            total_walls = 0

            for i in range(len(levels)):
                current_level = levels[i]
                next_level    = levels[i + 1] if i < len(levels) - 1 else None

                walls = self.create_walls_for_level(current_level, next_level)

                results[current_level.Name] = {
                    'count': len(walls),
                    'walls': walls,
                }
                total_walls += len(walls)

            self.logger.log_info(
                "Creation terminee : {0} voiles au total".format(total_walls)
            )

            return {
                'success':     True,
                'total_walls': total_walls,
                'by_level':    results,
            }

        except Exception as e:
            self.logger.log_error(e, {'context': 'create_all_walls'})
            return {
                'success':     False,
                'total_walls': 0,
                'by_level':    {},
                'message':     str(e),
            }


# -----------------------------------------------------------------------------
# Fonction d'entree pour les boutons pyRevit (mode autonome)
# -----------------------------------------------------------------------------

def main():
    """Point d'entree principal pour l'execution depuis l'interface Revit."""
    from pyrevit import revit, forms
    from Autodesk.Revit.DB import Transaction

    doc = revit.doc

    options = [
        "Convertir tous les murs architecturaux en voiles",
        "Creer uniquement les voiles porteurs",
        "Analyser seulement (sans creer)",
    ]

    selected = forms.SelectFromList.show(
        options,
        title="AutoRevit - Creation voiles",
        button_name='Continuer',
        multiselect=False
    )

    if not selected:
        return

    analyze_only = (selected[0] == options[2])
    engine = WallPlacementEngine(doc)

    if analyze_only:
        levels  = get_all_levels(doc)
        report  = []
        for level in levels:
            arch_walls  = get_all_walls(doc)
            level_walls = [w for w in arch_walls if w.LevelId == level.Id]
            for wall in level_walls:
                location = wall.Location
                if isinstance(location, LocationCurve):
                    openings = engine.detect_openings_on_wall(location.Curve, level)
                    report.append({
                        'level':          level.Name,
                        'wall_id':        wall.Id.IntegerValue,
                        'openings_count': len(openings),
                        'orientation':    get_wall_orientation(wall),
                    })

        forms.alert(
            "Analyse terminee : {0} murs analyses".format(len(report)),
            title="Rapport d'analyse"
        )

    else:
        if forms.alert(
            "Creer les voiles pour tous les niveaux ?",
            title="AutoRevit - Creation voiles",
            ok=False, yes=True, no=True
        ):
            # Transaction geree ici en mode autonome
            t = Transaction(doc, "AutoRevit - Creer voiles")
            t.Start()
            try:
                result = engine.create_all_walls()
                t.Commit()
                if result['success']:
                    forms.alert(
                        "{0} voiles crees avec succes !".format(result['total_walls']),
                        title="Succes"
                    )
                else:
                    forms.alert(
                        "Erreur : {0}".format(result.get('message', 'Inconnue')),
                        title="Erreur"
                    )
            except Exception as e:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                forms.alert("Erreur : " + str(e), title="Erreur")


if __name__ == '__main__':
    main()