# -*- coding: utf-8 -*-
"""Algorithme de dimensionnement et placement des fondations

RÈGLES MÉTIER IMPLÉMENTÉES :

TYPE 1 : SEMELLE FILANTE
- Condition : Sous mur porteur
- Largeur : 2 × largeur mur (minimum)
- Profondeur : Variable selon sol
- Armatures : Treillis soudé ST25

TYPE 2 : SEMELLE ISOLÉE
- Condition : Sous poteau seul
- Forme : Carrée ou rectangulaire
- Dimension : Selon charge et sol
- Épaisseur : >= 25cm

TYPE 3 : SEMELLE ENGRÊNÉE
- Condition : Poteaux proches (< 2m)
- Forme : Continue rectangulaire
- Économique si poteaux rapprochés

TYPE 4 : RADIER
- Condition : Sol médiocre ou charges élevées
- Surface complète du bâtiment
- Épaisseur : >= 30cm
"""

import math
import re

# Compatibilité IronPython 2.7 / Python 3
try:
    from typing import List, Dict, Tuple, Optional
except Exception as _revit_import_err:
    pass

try:
    from enum import Enum as _BaseEnum

    class FoundationType(_BaseEnum):
        """Types de fondations selon configuration"""
        STRIP    = "SEMELLE_FILANTE"
        ISOLATED = "SEMELLE_ISOLEE"
        COMBINED = "SEMELLE_ENGRENEE"
        RAFT     = "RADIER"
        PILE     = "PIEUX"

except Exception as _revit_import_err:
    class FoundationType(object):
        """Types de fondations (fallback IronPython 2.7)"""
        STRIP    = "SEMELLE_FILANTE"
        ISOLATED = "SEMELLE_ISOLEE"
        COMBINED = "SEMELLE_ENGRENEE"
        RAFT     = "RADIER"
        PILE     = "PIEUX"

from Autodesk.Revit.DB import (
    XYZ, Line, Wall, FamilyInstance, FamilySymbol,
    FilteredElementCollector, BuiltInCategory,
    BuiltInParameter,
    Level, Curve, LocationCurve, LocationPoint
    )

from services.revit_service import RevitService
from services.geometry_service import GeometryService
from services.logging_service import LoggingService
from utils.decorators import log_execution, transaction, handle_errors
from helpers.revit_helpers import (
    get_all_levels, mm_to_feet, feet_to_mm,
    get_all_columns, get_all_walls
)
from algorithms.geometry_utils import (
    calculate_distance,
    get_rectangle_from_points,
    calculate_centroid
)


class FoundationPlacementEngine(object):
    """
    Moteur de dimensionnement et placement des fondations.

    Implémente les règles métier pour :
    - Détection automatique du type de fondation adapté
    - Dimensionnement selon charges et nature du sol
    - Placement sous poteaux et murs porteurs
    - Optimisation par semelles engrênées
    """

    # Paramètres sol par défaut (à remplacer par données géotechniques)
    DEFAULT_SOIL_CAPACITY    = 0.2   # MPa (200 kPa - sol moyen)
    DEFAULT_CONCRETE_STRENGTH = 25   # MPa (C25/30)

    # Coefficients de dimensionnement
    STRIP_WIDTH_FACTOR    = 2.0
    ISOLATED_WIDTH_FACTOR = 1.5
    COMBINED_MAX_DISTANCE = 2000   # 2m max pour semelle engrênée

    # Dimensions minimales (mm)
    MIN_STRIP_WIDTH      = 400
    MIN_ISOLATED_SIZE    = 600
    MIN_RAFT_THICKNESS   = 300
    MIN_FOOTING_THICKNESS = 250

    def __init__(self, doc, api_client=None):
        """
        Initialise le moteur de placement des fondations.

        Args:
            doc:        Document Revit actif
            api_client: Client API optionnel
        """
        self.doc              = doc
        self.api              = api_client
        self.revit_service    = RevitService(doc)
        self.geometry_service = GeometryService(doc)
        self.logger           = LoggingService(api_client)

        self._footing_families_cache = {}
        self._levels_cache           = None
        self._soil_capacity          = self.DEFAULT_SOIL_CAPACITY

    # -------------------------------------------------------------------------
    # 1. CHARGEMENT DES DONNÉES SOL
    # -------------------------------------------------------------------------

    def load_soil_data(self, project_id=None):
        """
        Charge les données géotechniques depuis l'API.

        Args:
            project_id: ID du projet (optionnel)

        Returns:
            Dictionnaire des paramètres sol
        """
        if self.api:
            try:
                # TODO: Récupérer depuis API
                pass
            except Exception as e:
                self.logger.log_warning(
                    "Impossible de charger données sol: {0}".format(e)
                )

        return {
            'soil_capacity_mpa':   self.DEFAULT_SOIL_CAPACITY,
            'soil_type':           'moyen',
            'frost_depth_mm':      800,
            'water_table_depth_mm': 3000,
        }

    # -------------------------------------------------------------------------
    # 2. ANALYSE DU TYPE DE FONDATION
    # -------------------------------------------------------------------------

    def analyze_foundation_type(self, element, nearby_elements):
        """
        Détermine le type de fondation approprié pour un élément.

        Args:
            element:          Élément supporté (dict poteau ou mur)
            nearby_elements:  Éléments voisins (list)

        Returns:
            FoundationType recommandé
        """
        element_type = element.get('type')

        if element_type == 'wall' and element.get('is_load_bearing', False):
            return FoundationType.STRIP

        if element_type == 'column':
            close_columns = []
            for other in nearby_elements:
                if other.get('type') == 'column' and other['id'] != element['id']:
                    distance = calculate_distance(
                        element['point'],
                        other['point']
                    ) * 304.8  # feet → mm

                    if distance < self.COMBINED_MAX_DISTANCE:
                        close_columns.append({
                            'element':  other,
                            'distance': distance,
                        })

            if len(close_columns) >= 1:
                return FoundationType.COMBINED

            return FoundationType.ISOLATED

        return FoundationType.ISOLATED

    def find_nearby_columns(self, column, radius_mm=2000):
        """
        Trouve les poteaux à proximité d'un poteau donné.

        Args:
            column:    Poteau de référence (dict)
            radius_mm: Rayon de recherche (mm)

        Returns:
            Liste des poteaux proches
        """
        nearby       = []
        all_columns  = get_all_columns(self.doc)
        column_point = column['point']
        radius_feet  = mm_to_feet(radius_mm)

        for other in all_columns:
            if other['id'] == column['id']:
                continue

            distance = calculate_distance(column_point, other['point'])
            if distance <= radius_feet:
                entry = dict(other)
                entry['distance_mm'] = distance * 304.8
                nearby.append(entry)

        return nearby

    # -------------------------------------------------------------------------
    # 3. CALCUL DES CHARGES
    # -------------------------------------------------------------------------

    def calculate_column_load(self, column):
        """
        Calcule la charge approximative descendante sur un poteau.

        Args:
            column: Données du poteau (dict)

        Returns:
            Charge en kN
        """
        section_param = column['element'].LookupParameter("Section Dimensions")
        if section_param:
            section_str = section_param.AsString() or ""
            match = re.search(r'(\d+)x(\d+)', section_str)
            if match:
                width = int(match.group(1))
                return (width * width / 1.0e6) * 15 * 4 * 1000

        return 500.0  # 500 kN par défaut

    def calculate_wall_load(self, wall):
        """
        Calcule la charge approximative sur un mur.

        Args:
            wall: Données du mur (dict)

        Returns:
            Charge linéique en kN/m
        """
        # TODO: Implémenter calcul réel
        return 150.0

    # -------------------------------------------------------------------------
    # 4. DIMENSIONNEMENT DES SEMELLES
    # -------------------------------------------------------------------------

    def calculate_foundation_dimensions(self, element,
                                        foundation_type, soil_data):
        """
        Calcule les dimensions de la fondation.

        Args:
            element:         Élément supporté (dict)
            foundation_type: Type de fondation (FoundationType)
            soil_data:       Données géotechniques (dict)

        Returns:
            Dictionnaire des dimensions (mm)
        """
        soil_capacity = soil_data.get(
            'soil_capacity_mpa', self.DEFAULT_SOIL_CAPACITY
        )

        ft = foundation_type
        ft_val = ft if isinstance(ft, str) else getattr(ft, 'value', str(ft))

        if "FILANTE" in ft_val:
            wall_thickness = element.get('thickness', 200)
            width = max(
                self.MIN_STRIP_WIDTH,
                int(wall_thickness * self.STRIP_WIDTH_FACTOR)
            )
            thickness = max(
                self.MIN_FOOTING_THICKNESS,
                int(width * 0.4)
            )
            return {
                'width':     width,
                'thickness': thickness,
                'length':    None,
                'type':      'strip',
            }

        elif "ISOLEE" in ft_val:
            load_kN  = self.calculate_column_load(element)
            area_mm2 = (load_kN * 1000) / soil_capacity
            side_mm  = math.sqrt(area_mm2)
            side_mm  = int(round(side_mm / 50.0)) * 50
            side_mm  = max(self.MIN_ISOLATED_SIZE, side_mm)
            thickness = max(
                self.MIN_FOOTING_THICKNESS,
                int(side_mm * 0.3)
            )
            thickness = int(round(thickness / 50.0)) * 50
            return {
                'width':     side_mm,
                'length':    side_mm,
                'thickness': thickness,
                'type':      'isolated',
            }

        elif "ENGRENEE" in ft_val:
            return {
                'width':     1200,
                'length':    2500,
                'thickness': 400,
                'type':      'combined',
            }

        elif "RADIER" in ft_val:
            return {
                'thickness': self.MIN_RAFT_THICKNESS,
                'type':      'raft',
            }

        return {}

    # -------------------------------------------------------------------------
    # 5. RÉCUPÉRATION DES FAMILLES DE FONDATIONS
    # -------------------------------------------------------------------------

    def get_footing_family(self, dimensions, foundation_type):
        """
        Récupère la famille de fondation appropriée.

        Args:
            dimensions:      Dimensions calculées (dict)
            foundation_type: Type de fondation (FoundationType)

        Returns:
            FamilySymbol ou None
        """
        cache_key = "{0}_{1}x{2}".format(
            foundation_type,
            dimensions.get('width', 0),
            dimensions.get('length', 0)
        )

        if cache_key in self._footing_families_cache:
            return self._footing_families_cache[cache_key]

        ft_val = (foundation_type.value
                  if hasattr(foundation_type, 'value')
                  else str(foundation_type))

        collector = (FilteredElementCollector(self.doc)
                     .OfCategory(BuiltInCategory.OST_StructuralFoundation)
                     .OfClass(FamilySymbol))

        if "ISOLEE" in ft_val:
            for symbol in collector:
                if "isolée" in symbol.Name.lower() or "isolee" in symbol.Name.lower():
                    self._footing_families_cache[cache_key] = symbol
                    return symbol

        elif "ENGRENEE" in ft_val:
            for symbol in collector:
                if "engrênée" in symbol.Name.lower() or "engrenee" in symbol.Name.lower():
                    self._footing_families_cache[cache_key] = symbol
                    return symbol

        default_type = collector.FirstElement()
        self._footing_families_cache[cache_key] = default_type
        return default_type

    # -------------------------------------------------------------------------
    # 6. CRÉATION DES FONDATIONS
    # -------------------------------------------------------------------------

    @log_execution
    @transaction("Création des semelles isolées")
    @handle_errors("Erreur lors de la création des semelles isolées")
    def create_isolated_footing(self, column, dimensions, level):
        """
        Crée une semelle isolée sous un poteau.

        Args:
            column:     Données du poteau (dict)
            dimensions: Dimensions calculées (dict)
            level:      Niveau de fondation

        Returns:
            FamilyInstance créée, ou None
        """
        try:
            footing_type = self.get_footing_family(dimensions, FoundationType.ISOLATED)
            if not footing_type:
                return None

            if not footing_type.IsActive:
                footing_type.Activate()

            column_point = column['point']
            footing_point = XYZ(
                column_point.X,
                column_point.Y,
                level.Elevation
            )

            footing = self.doc.Create.NewFamilyInstance(
                footing_point,
                footing_type,
                level
.Footing
            )

            width_param     = (footing.LookupParameter("Largeur") or
                               footing.LookupParameter("Width"))
            length_param    = (footing.LookupParameter("Longueur") or
                               footing.LookupParameter("Length"))
            thickness_param = (footing.LookupParameter("Épaisseur") or
                               footing.LookupParameter("Thickness"))

            if width_param:
                width_param.Set(mm_to_feet(dimensions['width']))
            if length_param:
                length_param.Set(mm_to_feet(dimensions['length']))
            if thickness_param:
                thickness_param.Set(mm_to_feet(dimensions['thickness']))

            c_param = footing.LookupParameter("Comments")
            if c_param:
                c_param.Set(
                    "AutoRevit - Semelle isolée - {0}x{1}x{2}mm".format(
                        dimensions['width'],
                        dimensions['length'],
                        dimensions['thickness']
                    )
                )

            return footing

        except Exception as e:
            self.logger.log_error(e, {
                'column':     column.get('id'),
                'dimensions': dimensions,
            })
            return None

    @log_execution
    @transaction("Création des semelles filantes")
    @handle_errors("Erreur lors de la création des semelles filantes")
    def create_strip_foundation(self, wall, dimensions, level):
        """
        Crée une semelle filante sous un mur.

        Args:
            wall:       Données du mur (dict)
            dimensions: Dimensions calculées (dict)
            level:      Niveau de fondation

        Returns:
            Liste des semelles créées
        """
        created = []

        try:
            wall_element = wall['element']
            location     = wall_element.Location

            if not isinstance(location, LocationCurve):
                return created

            wall_line   = location.Curve
            start_point = wall_line.GetEndPoint(0)
            end_point   = wall_line.GetEndPoint(1)

            footing_type = self.get_footing_family(dimensions, FoundationType.STRIP)
            if not footing_type:
                return created

            if not footing_type.IsActive:
                footing_type.Activate()

            line = Line.CreateBound(
                XYZ(start_point.X, start_point.Y, level.Elevation),
                XYZ(end_point.X,   end_point.Y,   level.Elevation)
            )

            footing = self.doc.Create.NewFamilyInstance(
                line,
                footing_type,
                level
.Footing
            )

            width_param     = (footing.LookupParameter("Largeur") or
                               footing.LookupParameter("Width"))
            thickness_param = (footing.LookupParameter("Épaisseur") or
                               footing.LookupParameter("Thickness"))

            if width_param:
                width_param.Set(mm_to_feet(dimensions['width']))
            if thickness_param:
                thickness_param.Set(mm_to_feet(dimensions['thickness']))

            c_param = footing.LookupParameter("Comments")
            if c_param:
                c_param.Set(
                    "AutoRevit - Semelle filante - L={0}mm - l={1}mm e={2}mm".format(
                        int(feet_to_mm(wall_line.Length)),
                        dimensions['width'],
                        dimensions['thickness']
                    )
                )

            created.append(footing)

        except Exception as e:
            self.logger.log_error(e, {
                'wall':       wall.get('id'),
                'dimensions': dimensions,
            })

        return created

    @log_execution
    @transaction("Création des semelles engrênées")
    @handle_errors("Erreur lors de la création des semelles engrênées")
    def create_combined_footing(self, columns, dimensions, level):
        """
        Crée une semelle engrênée pour plusieurs poteaux proches.

        Args:
            columns:    Liste des poteaux à fonder ensemble (list de dict)
            dimensions: Dimensions calculées (dict)
            level:      Niveau de fondation

        Returns:
            FamilyInstance créée, ou None
        """
        try:
            points   = [col['point'] for col in columns]
            centroid = calculate_centroid(points)

            footing_type = self.get_footing_family(dimensions, FoundationType.COMBINED)
            if not footing_type:
                return None

            if not footing_type.IsActive:
                footing_type.Activate()

            footing_point = XYZ(centroid.X, centroid.Y, level.Elevation)

            footing = self.doc.Create.NewFamilyInstance(
                footing_point,
                footing_type,
                level
.Footing
            )

            width_param     = (footing.LookupParameter("Largeur") or
                               footing.LookupParameter("Width"))
            length_param    = (footing.LookupParameter("Longueur") or
                               footing.LookupParameter("Length"))
            thickness_param = (footing.LookupParameter("Épaisseur") or
                               footing.LookupParameter("Thickness"))

            if width_param:
                width_param.Set(mm_to_feet(dimensions['width']))
            if length_param:
                length_param.Set(mm_to_feet(dimensions['length']))
            if thickness_param:
                thickness_param.Set(mm_to_feet(dimensions['thickness']))

            c_param = footing.LookupParameter("Comments")
            if c_param:
                c_param.Set(
                    "AutoRevit - Semelle engrênée - {0} poteaux - {1}x{2}x{3}mm".format(
                        len(columns),
                        dimensions['width'],
                        dimensions['length'],
                        dimensions['thickness']
                    )
                )

            return footing

        except Exception as e:
            self.logger.log_error(e, {
                'columns_count': len(columns),
                'dimensions':    dimensions,
            })
            return None

    @log_execution
    @transaction("Création de toutes les fondations")
    @handle_errors("Erreur lors de la création des fondations")
    def create_all_foundations(self):
        """
        Crée toutes les fondations pour le projet.

        Returns:
            Dictionnaire des résultats
        """
        levels = get_all_levels(self.doc)
        if not levels:
            return {'success': False, 'message': 'Aucun niveau trouvé'}

        foundation_level = sorted(levels, key=lambda l: l.Elevation)[0]

        soil_data = self.load_soil_data()

        results = {
            'isolated': [],
            'strip':    [],
            'combined': [],
            'raft':     None,
        }

        # --- Poteaux ---
        columns           = get_all_columns(self.doc)
        processed_columns = set()

        for column in columns:
            col_id = column['id']
            if col_id in processed_columns:
                continue

            nearby = self.find_nearby_columns(column)

            if len(nearby) >= 1:
                group = [column] + nearby
                for col in group:
                    processed_columns.add(col['id'])

                dimensions = self.calculate_foundation_dimensions(
                    column, FoundationType.COMBINED, soil_data
                )

                footing = self.create_combined_footing(
                    group, dimensions, foundation_level
                )

                if footing:
                    results['combined'].append({
                        'id':         footing.Id,
                        'columns':    [c['id'].IntegerValue for c in group],
                        'dimensions': dimensions,
                    })
            else:
                dimensions = self.calculate_foundation_dimensions(
                    column, FoundationType.ISOLATED, soil_data
                )

                footing = self.create_isolated_footing(
                    column, dimensions, foundation_level
                )

                if footing:
                    results['isolated'].append({
                        'id':         footing.Id,
                        'column_id':  col_id.IntegerValue,
                        'dimensions': dimensions,
                    })
                    processed_columns.add(col_id)

        # --- Murs porteurs ---
        walls = get_all_walls(self.doc)

        for wall in walls:
            structural_param = wall.get_Parameter(
                BuiltInParameter.WALL_STRUCTURAL_USAGE_PARAM
            )

            if structural_param and structural_param.AsInteger() != 0:
                wall_data = {
                    'id':             wall.Id,
                    'element':        wall,
                    'type':           'wall',
                    'thickness':      self._get_wall_thickness(wall),
                    'is_load_bearing': True,
                }

                dimensions = self.calculate_foundation_dimensions(
                    wall_data, FoundationType.STRIP, soil_data
                )

                footings = self.create_strip_foundation(
                    wall_data, dimensions, foundation_level
                )

                for footing in footings:
                    results['strip'].append({
                        'id':         footing.Id,
                        'wall_id':    wall.Id.IntegerValue,
                        'dimensions': dimensions,
                    })

        total = (
            len(results['isolated']) +
            len(results['strip'])    +
            len(results['combined'])
        )

        self.logger.log_info(
            "Création terminée : {0} fondations créées".format(total)
        )

        return {
            'success':           True,
            'total_foundations': total,
            'details':           results,
        }

    def _get_wall_thickness(self, wall):
        """Récupère l'épaisseur d'un mur en mm."""
        comp_structure = wall.GetCompoundStructure()
        if comp_structure:
            return int(feet_to_mm(comp_structure.GetWidth()))
        return 200


# -----------------------------------------------------------------------------
# Fonction d'entrée pour les boutons pyRevit
# -----------------------------------------------------------------------------

def main():
    """Point d'entrée principal pour l'exécution depuis l'interface Revit."""
    from pyrevit import revit, forms

    doc     = revit.doc
    columns = get_all_columns(doc)
    walls   = get_all_walls(doc)

    if len(columns) == 0 and len(walls) == 0:
        forms.alert(
            "Aucun poteau ou mur trouvé. Créez d'abord la structure.",
            title="AutoRevit - Création fondations"
        )
        return

    options = [
        "Créer toutes les fondations automatiquement",
        "Semelles isolées uniquement",
        "Semelles filantes uniquement",
        "Analyser seulement",
    ]

    selected = forms.SelectFromList.show(
        options,
        title="AutoRevit - Création fondations",
        button_name='Continuer',
        multiselect=False
    )

    if not selected:
        return

    engine = FoundationPlacementEngine(doc)

    if selected[0] == options[3]:
        soil_data = engine.load_soil_data()
        report    = []

        for column in columns:
            load   = engine.calculate_column_load(column)
            nearby = engine.find_nearby_columns(column)

            report.append({
                'type':            'Poteau',
                'id':              column['id'].IntegerValue,
                'charge_kN':       round(load, 0),
                'poteaux_proches': len(nearby),
                'fondation':       'engrênée' if len(nearby) >= 1 else 'isolée',
            })

        for wall in walls:
            if engine._get_wall_thickness(wall) > 0:
                report.append({
                    'type':         'Mur porteur',
                    'id':           wall.Id.IntegerValue,
                    'charge_kN/m':  150,
                    'fondation':    'filante',
                })

        forms.alert(
            "Analyse terminée : {0} éléments à fonder".format(len(report)),
            title="Rapport d'analyse"
        )

    else:
        mode = selected[0]

        if forms.alert(
            "Créer les fondations ?\nMode: {0}".format(mode),
            title="AutoRevit - Création fondations",
            ok=False,
            yes=True,
            no=True
        ):
            result = engine.create_all_foundations()

            if result['success']:
                forms.alert(
                    "{0} fondations créées avec succès !\n\n"
                    "Semelles isolées: {1}\n"
                    "Semelles filantes: {2}\n"
                    "Semelles engrênées: {3}".format(
                        result['total_foundations'],
                        len(result['details']['isolated']),
                        len(result['details']['strip']),
                        len(result['details']['combined'])
                    ),
                    title="Succès"
                )
            else:
                forms.alert(
                    "Erreur : {0}".format(result.get('message', 'Inconnue')),
                    title="Erreur"
                )


if __name__ == '__main__':
    main()