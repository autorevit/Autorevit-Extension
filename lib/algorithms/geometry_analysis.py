# -*- coding: utf-8 -*-
"""Analyse géométrique avancée pour les algorithmes de placement

Fonctions d'analyse spatiale :
- Détection de travées et panneaux
- Analyse de continuité structurelle
- Détection de conflits et collisions
- Optimisation de placement
- Analyse de portées et charges
"""

import math
from collections import defaultdict

# Compatibilité IronPython 2.7 / Python 3
try:
    from typing import List, Dict, Tuple, Optional, Set
except ImportError:
    pass

try:
    from itertools import combinations
except ImportError:
    pass

from Autodesk.Revit.DB import (
    XYZ, Line, Curve, CurveLoop, Face,
    FilteredElementCollector, BuiltInCategory,
    Solid, GeometryElement, GeometryInstance, Options,
    IntersectionResultArray, SetComparisonResult,
    Transform, BoundingBoxXYZ, Element,
    FamilyInstance, Wall, Floor, Level,
    Grid, LocationCurve, BuiltInParameter
)

from helpers.revit_helpers import mm_to_feet, feet_to_mm
from algorithms.geometry_utils import (
    calculate_distance,
    calculate_centroid,
    get_bounding_rectangle,
    sort_points_clockwise,
    is_point_on_line,
    project_point_on_curve
)


class GeometryAnalyzer(object):
    """
    Analyseur géométrique avancé pour la structure.

    Fournit des méthodes d'analyse spatiale pour :
    - Détection automatique des travées
    - Analyse des réseaux de poutres
    - Détection de conflits entre éléments
    - Optimisation du placement
    - Calcul de surfaces et volumes
    """

    def __init__(self, doc):
        """
        Initialise l'analyseur géométrique.

        Args:
            doc: Document Revit actif
        """
        self.doc = doc
        self.options = Options()
        self.options.ComputeReferences = True
        self.options.DetailLevel = 0  # Coarse
        self.options.IncludeNonVisibleObjects = False

    # -------------------------------------------------------------------------
    # 1. ANALYSE DES TRAVÉES ET PANNEAUX
    # -------------------------------------------------------------------------

    def analyze_bay_network(self, level):
        """
        Analyse complète du réseau de travées à un niveau.

        Args:
            level: Niveau à analyser

        Returns:
            Dictionnaire avec toutes les informations de travées
        """
        result = {
            'level': level.Name,
            'elevation_mm': feet_to_mm(level.Elevation),
            'bays': [],
            'columns': [],
            'beams': [],
            'grids': [],
            'statistics': {}
        }

        grids = self._get_grids_at_level(level)
        result['grids'] = self._analyze_grids(grids)

        columns = self._get_columns_at_level(level)
        result['columns'] = self._analyze_columns(columns)

        beams = self._get_beams_at_level(level)
        result['beams'] = self._analyze_beams(beams)

        if grids:
            bays = self._detect_bays_from_grids(grids)
        else:
            bays = self._detect_bays_from_columns(columns)

        result['bays'] = bays

        bay_areas   = [b['area_m2']   for b in bays]
        bay_max_sp  = [b['max_span_m'] for b in bays]
        bay_min_sp  = [b['min_span_m'] for b in bays]

        result['statistics'] = {
            'bay_count':         len(bays),
            'column_count':      len(columns),
            'beam_count':        len(beams),
            'grid_count':        len(grids),
            'total_area_m2':     sum(bay_areas),
            'avg_bay_area_m2':   sum(bay_areas) / max(len(bays), 1),
            'max_span_m':        max(bay_max_sp) if bay_max_sp else 0,
            'min_span_m':        min(bay_min_sp) if bay_min_sp else 0,
        }

        return result

    def _get_grids_at_level(self, level):
        collector = FilteredElementCollector(self.doc).OfClass(Grid)
        grids = []
        for grid in collector:
            try:
                curve = grid.Curve
                start = curve.GetEndPoint(0)
                end   = curve.GetEndPoint(1)
                min_z = min(start.Z, end.Z)
                max_z = max(start.Z, end.Z)
                if min_z <= level.Elevation <= max_z:
                    grids.append(grid)
            except:
                pass
        return grids

    def _get_columns_at_level(self, level):
        """Récupère les poteaux au niveau donné."""
        collector = (FilteredElementCollector(self.doc)
                     .OfCategory(BuiltInCategory.OST_StructuralColumns)
                     .WhereElementIsNotElementType())

        columns = []
        level_elevation = level.Elevation
        tolerance = mm_to_feet(100)

        for column in collector:
            try:
                lvl_param = column.get_Parameter(
                    BuiltInParameter.FAMILY_LEVEL_PARAM
                )
                if lvl_param and lvl_param.AsElementId() == level.Id:
                    columns.append(column)
            except:
                pass

        return columns

    def _get_beams_at_level(self, level):
        """Récupère les poutres au niveau donné."""
        collector = (FilteredElementCollector(self.doc)
                     .OfCategory(BuiltInCategory.OST_StructuralFraming)
                     .WhereElementIsNotElementType())

        beams = []
        for beam in collector:
            ref_level = beam.get_Parameter(
                BuiltInParameter.INSTANCE_REFERENCE_LEVEL_PARAM
            )
            if ref_level and ref_level.AsElementId() == level.Id:
                beams.append(beam)

        return beams

    def _analyze_grids(self, grids):
        """Analyse les grilles et leurs propriétés."""
        result = []

        for grid in grids:
            curve = grid.Curve
            start = curve.GetEndPoint(0)
            end = curve.GetEndPoint(1)

            result.append({
                'id':   grid.Id.IntegerValue,
                'name': grid.Name,
                'start': {'x': start.X, 'y': start.Y, 'z': start.Z},
                'end':   {'x': end.X,   'y': end.Y,   'z': end.Z},
                'length_mm': feet_to_mm(curve.Length),
            })

        return result

    def _analyze_columns(self, columns):
        """Analyse les poteaux et leurs propriétés."""
        result = []

        for column in columns:
            location = column.Location
            point = location.Point if hasattr(location, 'Point') else None

            width    = column.LookupParameter("Largeur") or column.LookupParameter("Width")
            height   = column.LookupParameter("Hauteur") or column.LookupParameter("Height")
            material = column.LookupParameter("Matériau") or column.LookupParameter("Material")
            comments_p = column.LookupParameter("Comments")

            result.append({
                'id':       column.Id.IntegerValue,
                'point':    {'x': point.X, 'y': point.Y, 'z': point.Z} if point else None,
                'width_mm': feet_to_mm(width.AsDouble())    if width    else 0,
                'height_mm': feet_to_mm(height.AsDouble())  if height   else 0,
                'material': material.AsString()              if material else "Béton",
                'comments': comments_p.AsString()            if comments_p else "",
            })

        return result

    def _analyze_beams(self, beams):
        """Analyse les poutres et leurs propriétés."""
        result = []

        for beam in beams:
            location = beam.Location
            if not isinstance(location, LocationCurve):
                continue

            curve = location.Curve
            start = curve.GetEndPoint(0)
            end   = curve.GetEndPoint(1)

            width  = beam.LookupParameter("Largeur") or beam.LookupParameter("Width")
            height = beam.LookupParameter("Hauteur") or beam.LookupParameter("Height")

            comments = beam.LookupParameter("Comments")
            beam_type = "SECONDAIRE"
            if comments:
                comment_str = comments.AsString() or ""
                if "PRINCIPALE" in comment_str:
                    beam_type = "PRINCIPALE"
                elif "RAIDISSEUR" in comment_str:
                    beam_type = "RAIDISSEUR"
                elif "PLATE" in comment_str:
                    beam_type = "PLATE"

            result.append({
                'id':       beam.Id.IntegerValue,
                'start':    {'x': start.X, 'y': start.Y, 'z': start.Z},
                'end':      {'x': end.X,   'y': end.Y,   'z': end.Z},
                'length_mm': feet_to_mm(curve.Length),
                'width_mm':  feet_to_mm(width.AsDouble())  if width  else 0,
                'height_mm': feet_to_mm(height.AsDouble()) if height else 0,
                'type':      beam_type,
                'span_m':    feet_to_mm(curve.Length) / 1000,
            })

        return result

    def _detect_bays_from_grids(self, grids):
        """Détecte les travées à partir du réseau de grilles."""
        bays = []

        h_grids = []
        v_grids = []

        for grid in grids:
            curve = grid.Curve
            direction = curve.Direction

            if abs(direction.X) > abs(direction.Y):
                h_grids.append(grid)
            else:
                v_grids.append(grid)

        h_grids.sort(key=lambda g: g.Curve.GetEndPoint(0).Y)
        v_grids.sort(key=lambda g: g.Curve.GetEndPoint(0).X)

        for i in range(len(h_grids) - 1):
            for j in range(len(v_grids) - 1):
                h1 = h_grids[i]
                h2 = h_grids[i + 1]
                v1 = v_grids[j]
                v2 = v_grids[j + 1]

                y1 = h1.Curve.GetEndPoint(0).Y
                y2 = h2.Curve.GetEndPoint(0).Y
                x1 = v1.Curve.GetEndPoint(0).X
                x2 = v2.Curve.GetEndPoint(0).X

                corners = [
                    XYZ(x1, y1, 0),
                    XYZ(x2, y1, 0),
                    XYZ(x2, y2, 0),
                    XYZ(x1, y2, 0),
                ]

                width_m  = feet_to_mm(abs(x2 - x1)) / 1000
                length_m = feet_to_mm(abs(y2 - y1)) / 1000
                min_span = min(width_m, length_m)

                bays.append({
                    'id':          "B{0}_{1}".format(i, j),
                    'grid_h1':     h1.Name,
                    'grid_h2':     h2.Name,
                    'grid_v1':     v1.Name,
                    'grid_v2':     v2.Name,
                    'corners':     [{'x': c.X, 'y': c.Y, 'z': c.Z} for c in corners],
                    'width_m':     round(width_m, 2),
                    'length_m':    round(length_m, 2),
                    'area_m2':     round(width_m * length_m, 2),
                    'min_span_m':  min_span,
                    'max_span_m':  max(width_m, length_m),
                    'aspect_ratio': round(max(width_m, length_m) / max(min_span, 0.001), 2),
                })

        return bays

    def _detect_bays_from_columns(self, columns):
        """Détecte les travées à partir du réseau de poteaux."""
        bays = []

        if len(columns) < 4:
            return bays

        points = []
        for col in columns:
            try:
                location = col.Location
                if hasattr(location, 'Point'):
                    points.append({'point': location.Point, 'id': col.Id.IntegerValue})
                elif hasattr(location, 'Curve'):
                    pt = location.Curve.GetEndPoint(0)
                    points.append({'point': pt, 'id': col.Id.IntegerValue})
            except:
                pass
        sys.stderr.write("DEBUG points trouvés: %d\n" % len(points))
        
        
        
        x_coords = sorted(set(round(p['point'].X, 1) for p in points))
        y_coords = sorted(set(round(p['point'].Y, 1) for p in points))
        
        sys.stderr.write("DEBUG x_coords: %s\n" % str(x_coords))
        sys.stderr.write("DEBUG y_coords: %s\n" % str(y_coords))
        import sys
        for p in points:
            sys.stderr.write("DEBUG point: X=%.3f Y=%.3f Z=%.3f\n" % (p['point'].X, p['point'].Y, p['point'].Z))
        
        for i in range(len(x_coords) - 1):
            for j in range(len(y_coords) - 1):
                x1 = x_coords[i]
                x2 = x_coords[i + 1]
                y1 = y_coords[j]
                y2 = y_coords[j + 1]

                corners_xy = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

                has_all_corners = True
                corner_points = []

                for cx, cy in corners_xy:
                    found = False
                    for p in points:
                        if abs(p['point'].X - cx) < 0.5 and abs(p['point'].Y - cy) < 0.5:
                            found = True
                            corner_points.append(p['point'])
                            break
                    if not found:
                        has_all_corners = False
                        break

                if has_all_corners:
                    width_m  = feet_to_mm(abs(x2 - x1)) / 1000.0
                    length_m = feet_to_mm(abs(y2 - y1)) / 1000.0

                    bays.append({
                        'id':         "B_{0}_{1}".format(i, j),
                        'corners':    [{'x': c.X, 'y': c.Y, 'z': c.Z} for c in corner_points],
                        'width_m':    round(width_m, 2),
                        'length_m':   round(length_m, 2),
                        'area_m2':    round(width_m * length_m, 2),
                        'min_span_m': min(width_m, length_m),
                        'max_span_m': max(width_m, length_m),
                    })

        return bays

    # -------------------------------------------------------------------------
    # 2. ANALYSE DE CONTINUITÉ STRUCTURELLE
    # -------------------------------------------------------------------------

    def analyze_structural_continuity(self, level):
        """
        Analyse la continuité structurelle à un niveau.

        Args:
            level: Niveau à analyser

        Returns:
            Rapport de continuité
        """
        result = {
            'level':              level.Name,
            'vertical_alignment': [],
            'beam_continuity':    [],
            'missing_supports':   [],
            'recommendations':    [],
        }

        upper_level = self._get_next_level(level)
        if upper_level:
            current_columns = self._get_columns_at_level(level)
            upper_columns   = self._get_columns_at_level(upper_level)

            for col in current_columns:
                loc = col.Location
                if not hasattr(loc, 'Point'):
                    continue

                found = False
                for ucol in upper_columns:
                    uloc = ucol.Location
                    if hasattr(uloc, 'Point'):
                        dist = calculate_distance(loc.Point, uloc.Point)
                        if dist < mm_to_feet(100):
                            found = True
                            break

                if not found:
                    result['vertical_alignment'].append({
                        'column_id': col.Id.IntegerValue,
                        'location':  {'x': loc.Point.X, 'y': loc.Point.Y, 'z': loc.Point.Z},
                        'issue':     'Poteau non prolongé au niveau supérieur',
                    })

        beams = self._get_beams_at_level(level)
        beam_groups = defaultdict(list)

        for beam in beams:
            location = beam.Location
            if isinstance(location, LocationCurve):
                curve = location.Curve
                start = curve.GetEndPoint(0)
                end   = curve.GetEndPoint(1)

                if abs(start.Y - end.Y) < 0.01:
                    key = "H_{0}".format(round(start.Y, 3))
                else:
                    key = "V_{0}".format(round(start.X, 3))

                beam_groups[key].append({
                    'id':    beam.Id.IntegerValue,
                    'start': start,
                    'end':   end,
                    'curve': curve,
                })

        for axis, group in beam_groups.items():
            if len(group) < 2:
                continue

            if axis.startswith('H'):
                group.sort(key=lambda b: b['start'].X)
            else:
                group.sort(key=lambda b: b['start'].Y)

            for i in range(len(group) - 1):
                beam1 = group[i]
                beam2 = group[i + 1]
                gap   = calculate_distance(beam1['end'], beam2['start'])

                if gap > mm_to_feet(50):
                    result['beam_continuity'].append({
                        'beam1_id':       beam1['id'],
                        'beam2_id':       beam2['id'],
                        'gap_mm':         round(feet_to_mm(gap), 0),
                        'recommendation': 'Prolonger la poutre ou ajouter un insert',
                    })

        for beam in beams:
            location = beam.Location
            if not isinstance(location, LocationCurve):
                continue

            curve = location.Curve
            start = curve.GetEndPoint(0)
            end   = curve.GetEndPoint(1)

            if not self._has_support_at_point(start, level):
                result['missing_supports'].append({
                    'beam_id':  beam.Id.IntegerValue,
                    'end':      'start',
                    'location': {'x': start.X, 'y': start.Y, 'z': start.Z},
                })

            if not self._has_support_at_point(end, level):
                result['missing_supports'].append({
                    'beam_id':  beam.Id.IntegerValue,
                    'end':      'end',
                    'location': {'x': end.X, 'y': end.Y, 'z': end.Z},
                })

        if result['vertical_alignment']:
            result['recommendations'].append(
                "Ajouter {0} poteaux pour assurer la continuité verticale".format(
                    len(result['vertical_alignment']))
            )

        if result['beam_continuity']:
            result['recommendations'].append(
                "Corriger {0} discontinuités de poutres".format(
                    len(result['beam_continuity']))
            )

        if result['missing_supports']:
            result['recommendations'].append(
                "Ajouter des appuis pour {0} extrémités de poutres".format(
                    len(result['missing_supports']))
            )

        return result

    def _get_next_level(self, current_level):
        """Récupère le niveau supérieur."""
        collector = FilteredElementCollector(self.doc).OfClass(Level)

        levels = []
        for level in collector:
            if level.Elevation > current_level.Elevation:
                levels.append(level)

        if levels:
            return min(levels, key=lambda l: l.Elevation)

        return None

    def _has_support_at_point(self, point, level):
        """Vérifie si un point a un support (poteau ou mur)."""
        tolerance = mm_to_feet(200)

        columns = self._get_columns_at_level(level)
        for col in columns:
            location = col.Location
            if hasattr(location, 'Point'):
                if calculate_distance(point, location.Point) < tolerance:
                    return True

        walls = self._get_walls_at_level(level)
        for wall in walls:
            location = wall.Location
            if isinstance(location, LocationCurve):
                if is_point_on_line(point, location.Curve, tolerance_mm=200):
                    return True

        return False

    def _get_walls_at_level(self, level):
        """Récupère les murs au niveau donné."""
        collector = FilteredElementCollector(self.doc).OfClass(Wall)

        walls = []
        level_elevation = level.Elevation

        for wall in collector:
            if wall.LevelId == level.Id:
                walls.append(wall)
            else:
                bbox = wall.get_BoundingBox(None)
                if bbox and bbox.Min.Z <= level_elevation <= bbox.Max.Z:
                    walls.append(wall)

        return walls

    # -------------------------------------------------------------------------
    # 3. DÉTECTION DE COLLISIONS
    # -------------------------------------------------------------------------

    def detect_clashes(self, categories1, categories2, tolerance_mm=50):
        """
        Détecte les collisions entre deux listes de catégories d'éléments.

        Args:
            categories1:   Première liste de catégories (BuiltInCategory)
            categories2:   Deuxième liste de catégories (BuiltInCategory)
            tolerance_mm:  Tolérance de détection

        Returns:
            Liste des collisions détectées
        """
        clashes = []
        tolerance_feet = mm_to_feet(tolerance_mm)

        elements1 = self._get_elements_by_categories(categories1)
        elements2 = self._get_elements_by_categories(categories2)

        for elem1 in elements1:
            bbox1 = elem1.get_BoundingBox(None)
            if not bbox1:
                continue

            for elem2 in elements2:
                if elem1.Id == elem2.Id:
                    continue

                bbox2 = elem2.get_BoundingBox(None)
                if not bbox2:
                    continue

                if self._bounding_boxes_intersect(bbox1, bbox2, tolerance_feet):
                    if self._elements_intersect(elem1, elem2):
                        clashes.append({
                            'element1_id':       elem1.Id.IntegerValue,
                            'element1_category': elem1.Category.Name,
                            'element2_id':       elem2.Id.IntegerValue,
                            'element2_category': elem2.Category.Name,
                            'severity':          self._evaluate_clash_severity(elem1, elem2),
                            'bbox1':             self._bbox_to_dict(bbox1),
                            'bbox2':             self._bbox_to_dict(bbox2),
                        })

        return clashes

    def _get_elements_by_categories(self, categories):
        """Récupère les éléments de plusieurs catégories."""
        elements = []

        for cat in categories:
            collector = (FilteredElementCollector(self.doc)
                         .OfCategory(cat)
                         .WhereElementIsNotElementType())
            elements.extend(list(collector))

        return elements

    def _bounding_boxes_intersect(self, bbox1, bbox2, tolerance=0):
        """Vérifie si deux bounding boxes s'intersectent."""
        return not (
            bbox1.Max.X + tolerance < bbox2.Min.X or
            bbox1.Min.X - tolerance > bbox2.Max.X or
            bbox1.Max.Y + tolerance < bbox2.Min.Y or
            bbox1.Min.Y - tolerance > bbox2.Max.Y or
            bbox1.Max.Z + tolerance < bbox2.Min.Z or
            bbox1.Min.Z - tolerance > bbox2.Max.Z
        )

    def _elements_intersect(self, elem1, elem2):
        """Vérifie si deux éléments s'intersectent géométriquement."""
        geo1 = elem1.Geometry[self.options]
        geo2 = elem2.Geometry[self.options]

        if not geo1 or not geo2:
            return False

        solids1 = self._get_solids_from_geometry(geo1)
        solids2 = self._get_solids_from_geometry(geo2)

        for solid1 in solids1:
            for solid2 in solids2:
                try:
                    result = solid1.Intersect(solid2)
                    if result != Solid.SolidIntersectionResult.NonIntersecting:
                        return True
                except Exception:
                    pass

        return False

    def _get_solids_from_geometry(self, geo):
        """Extrait les solides d'un objet Geometry."""
        solids = []

        for obj in geo:
            if isinstance(obj, Solid) and obj.Volume > 0:
                solids.append(obj)
            elif isinstance(obj, GeometryInstance):
                instance_geo = obj.GetInstanceGeometry()
                solids.extend(self._get_solids_from_geometry(instance_geo))

        return solids

    def _evaluate_clash_severity(self, elem1, elem2):
        """Évalue la sévérité d'une collision."""
        cat1 = elem1.Category.Name
        cat2 = elem2.Category.Name

        if ("Poteaux" in cat1 and "Poutres" in cat2) or \
           ("Poutres" in cat1 and "Poteaux" in cat2):
            return "CRITIQUE"

        if "Dalles" in cat1 or "Dalles" in cat2:
            return "MAJEURE"

        return "MINEURE"

    def _bbox_to_dict(self, bbox):
        """Convertit un bounding box en dictionnaire."""
        return {
            'min':    {'x': bbox.Min.X, 'y': bbox.Min.Y, 'z': bbox.Min.Z},
            'max':    {'x': bbox.Max.X, 'y': bbox.Max.Y, 'z': bbox.Max.Z},
            'center': {
                'x': (bbox.Min.X + bbox.Max.X) / 2,
                'y': (bbox.Min.Y + bbox.Max.Y) / 2,
                'z': (bbox.Min.Z + bbox.Max.Z) / 2,
            },
        }

    # -------------------------------------------------------------------------
    # 4. OPTIMISATION DE PLACEMENT
    # -------------------------------------------------------------------------

    def optimize_column_placement(self, level, existing_columns=None):
        """
        Optimise le placement des poteaux à un niveau.

        Args:
            level:            Niveau à optimiser
            existing_columns: Poteaux existants (optionnel)

        Returns:
            Suggestions d'optimisation
        """
        suggestions = []

        if not existing_columns:
            existing_columns = self._get_columns_at_level(level)

        if len(existing_columns) < 2:
            return suggestions

        points = []
        for col in existing_columns:
            location = col.Location
            if hasattr(location, 'Point'):
                points.append({'point': location.Point, 'id': col.Id.IntegerValue})

        max_spacing = mm_to_feet(4000)
        min_spacing = mm_to_feet(2000)

        for i in range(len(points) - 1):
            for j in range(i + 1, len(points)):
                dist = calculate_distance(points[i]['point'], points[j]['point'])

                if dist > max_spacing:
                    suggestions.append({
                        'type':            'ADD_COLUMN',
                        'between':         [points[i]['id'], points[j]['id']],
                        'distance_mm':     round(feet_to_mm(dist), 0),
                        'recommendation':  'Ajouter un poteau intermédiaire',
                        'max_allowed_mm':  4000,
                    })
                elif dist < min_spacing:
                    suggestions.append({
                        'type':               'MERGE_COLUMNS',
                        'columns':            [points[i]['id'], points[j]['id']],
                        'distance_mm':        round(feet_to_mm(dist), 0),
                        'recommendation':     'Poteaux trop proches, fusionner ou déplacer',
                        'min_recommended_mm': 2000,
                    })

        return suggestions

    def optimize_beam_sections(self, level):
        """
        Optimise les sections de poutres à un niveau.

        Args:
            level: Niveau à optimiser

        Returns:
            Suggestions d'optimisation
        """
        suggestions = []
        beams = self._get_beams_at_level(level)

        for beam in beams:
            location = beam.Location
            if not isinstance(location, LocationCurve):
                continue

            span_m = feet_to_mm(location.Curve.Length) / 1000
            width  = beam.LookupParameter("Largeur") or beam.LookupParameter("Width")
            height = beam.LookupParameter("Hauteur") or beam.LookupParameter("Height")

            if not width or not height:
                continue

            current_height_mm = feet_to_mm(height.AsDouble())

            if span_m > 0:
                optimal_height = (span_m / 9) * 1000
                optimal_height = round(optimal_height / 50) * 50

                diff = abs(current_height_mm - optimal_height)

                if diff > 50:
                    suggestions.append({
                        'beam_id':           beam.Id.IntegerValue,
                        'current_height_mm': round(current_height_mm, 0),
                        'optimal_height_mm': optimal_height,
                        'span_m':            round(span_m, 2),
                        'recommendation':    "Ajuster hauteur de {0} à {1}mm".format(
                                                round(current_height_mm, 0), optimal_height),
                        'gain_potentiel':    "{0}mm".format(round(diff, 0)),
                    })

        return suggestions

    # -------------------------------------------------------------------------
    # 5. CALCUL DE SURFACES ET VOLUMES
    # -------------------------------------------------------------------------

    def calculate_floor_area(self, level):
        """
        Calcule la surface de plancher d'un niveau.

        Args:
            level: Niveau à analyser

        Returns:
            Surfaces et statistiques
        """
        floors = (FilteredElementCollector(self.doc)
                  .OfClass(Floor)
                  .WhereElementIsNotElementType())

        total_area = 0
        floor_areas = []

        for floor in floors:
            if floor.LevelId == level.Id:
                param = floor.get_Parameter(BuiltInParameter.HOST_AREA_COMPUTED)
                if param:
                    area_m2 = param.AsDouble() * 0.092903  # sqft → m²
                    total_area += area_m2

                    floor_areas.append({
                        'id':           floor.Id.IntegerValue,
                        'area_m2':      round(area_m2, 2),
                        'thickness_mm': self._get_floor_thickness(floor),
                    })

        openings_area = self._calculate_openings_area(level)

        return {
            'level':                level.Name,
            'total_gross_area_m2':  round(total_area, 2),
            'net_area_m2':          round(total_area - openings_area, 2),
            'openings_area_m2':     round(openings_area, 2),
            'floor_count':          len(floor_areas),
            'floors':               floor_areas,
        }

    def _get_floor_thickness(self, floor):
        """Récupère l'épaisseur d'une dalle."""
        param = floor.get_Parameter(BuiltInParameter.FLOOR_ATTR_DEFAULT_THICKNESS_PARAM)
        if param:
            return round(feet_to_mm(param.AsDouble()), 0)
        return 0

    def _calculate_openings_area(self, level):
        """Calcule la surface des ouvertures dans les dalles."""
        # TODO: Implémenter détection des ouvertures
        return 0

    # -------------------------------------------------------------------------
    # 6. RAPPORT GLOBAL
    # -------------------------------------------------------------------------

    def generate_full_report(self):
        """
        Génère un rapport complet d'analyse structurelle.

        Returns:
            Rapport complet pour tous les niveaux
        """
        levels = list(
            FilteredElementCollector(self.doc)
            .OfClass(Level)
            .WhereElementIsNotElementType()
        )
        levels = sorted(levels, key=lambda l: l.Elevation)

        report = {
            'project_name':  self.doc.Title,
            'levels':        [],
            'summary':       {},
            'clashes':       [],
            'recommendations': [],
        }

        total_columns = 0
        total_beams   = 0
        total_area    = 0

        for level in levels:
            level_analysis = self.analyze_bay_network(level)
            report['levels'].append(level_analysis)

            total_columns += level_analysis['statistics']['column_count']
            total_beams   += level_analysis['statistics']['beam_count']
            total_area    += level_analysis['statistics']['total_area_m2']

        structural_categories = [
            BuiltInCategory.OST_StructuralColumns,
            BuiltInCategory.OST_StructuralFraming,
            BuiltInCategory.OST_StructuralFoundation,
            BuiltInCategory.OST_Walls,
        ]

        architectural_categories = [
            BuiltInCategory.OST_Doors,
            BuiltInCategory.OST_Windows,
            BuiltInCategory.OST_GenericModel,
        ]

        clashes = self.detect_clashes(structural_categories, architectural_categories)
        report['clashes'] = clashes

        critical_clashes = [c for c in clashes if c['severity'] == 'CRITIQUE']

        report['summary'] = {
            'level_count':          len(levels),
            'total_columns':        total_columns,
            'total_beams':          total_beams,
            'total_floor_area_m2':  round(total_area, 2),
            'total_clashes':        len(clashes),
            'critical_clashes':     len(critical_clashes),
        }

        if critical_clashes:
            report['recommendations'].append(
                "Résoudre {0} collisions critiques".format(len(critical_clashes))
            )

        return report


# -----------------------------------------------------------------------------
# Fonction d'entrée pour les boutons pyRevit
# -----------------------------------------------------------------------------

def main():
    """Point d'entrée pour l'analyse géométrique depuis l'interface Revit."""
    from pyrevit import revit, forms, output as pyrevit_output

    doc = revit.doc

    options = [
        "Analyse complete du projet",
        "Analyse par niveau",
        "Detection de collisions",
        "Optimisation placement poteaux",
        "Optimisation sections poutres",
    ]

    selected = forms.SelectFromList.show(
        options,
        title="AutoRevit - Analyse géométrique",
        button_name='Analyser',
        multiselect=False,
        width=500
    )

    if not selected:
        return

    analyzer = GeometryAnalyzer(doc)
    out = pyrevit_output.get_output()

    choice = selected[0]

    if choice == options[0]:
        report = analyzer.generate_full_report()

        out.print_md("# Rapport d'analyse structurelle")
        out.print_md("**Projet:** {0}".format(report['project_name']))
        out.print_md("**Niveaux:** {0}".format(report['summary']['level_count']))
        out.print_md("**Poteaux:** {0}".format(report['summary']['total_columns']))
        out.print_md("**Poutres:** {0}".format(report['summary']['total_beams']))
        out.print_md("**Surface totale:** {0} m²".format(report['summary']['total_floor_area_m2']))
        out.print_md("**Collisions:** {0} (critiques: {1})".format(
            report['summary']['total_clashes'],
            report['summary']['critical_clashes']
        ))

        if report['recommendations']:
            out.print_md("\n## Recommandations")
            for rec in report['recommendations']:
                out.print_md("- {0}".format(rec))

    elif choice == options[1]:
        levels = list(FilteredElementCollector(doc)
                      .OfClass(Level)
                      .WhereElementIsNotElementType())
        level_names = [l.Name for l in levels]

        level_name = forms.SelectFromList.show(
            level_names,
            title="Sélectionner un niveau",
            button_name='Analyser'
        )

        if level_name:
            selected_name = level_name[0]
            level = [l for l in levels if l.Name == selected_name][0]
            analysis = analyzer.analyze_bay_network(level)

            out.print_md("# Analyse du niveau {0}".format(selected_name))
            out.print_md("**Altitude:** {0:.0f} mm".format(analysis['elevation_mm']))
            out.print_md("**Travées:** {0}".format(analysis['statistics']['bay_count']))
            out.print_md("**Poteaux:** {0}".format(analysis['statistics']['column_count']))
            out.print_md("**Poutres:** {0}".format(analysis['statistics']['beam_count']))
            out.print_md("**Surface:** {0:.0f} m²".format(analysis['statistics']['total_area_m2']))
            out.print_md("**Portée max:** {0:.1f} m".format(analysis['statistics']['max_span_m']))

    elif choice == options[2]:
        structural = [
            BuiltInCategory.OST_StructuralColumns,
            BuiltInCategory.OST_StructuralFraming,
            BuiltInCategory.OST_StructuralFoundation,
            BuiltInCategory.OST_Walls,
        ]

        architectural = [
            BuiltInCategory.OST_Doors,
            BuiltInCategory.OST_Windows,
            BuiltInCategory.OST_GenericModel,
            BuiltInCategory.OST_MechanicalEquipment,
        ]

        clashes = analyzer.detect_clashes(structural, architectural)

        if clashes:
            out.print_md("# {0} collisions détectées".format(len(clashes)))

            for clash in clashes[:20]:
                severity = clash['severity']
                if severity == 'CRITIQUE':
                    icon = "[CRITIQUE]"
                elif severity == 'MAJEURE':
                    icon = "[MAJEURE]"
                else:
                    icon = "[MINEURE]"

                out.print_md(
                    "{0} **{1}** (ID:{2}) vs **{3}** (ID:{4}) - {5}".format(
                        icon,
                        clash['element1_category'], clash['element1_id'],
                        clash['element2_category'], clash['element2_id'],
                        severity
                    )
                )

            if len(clashes) > 20:
                out.print_md("... et {0} autres collisions".format(len(clashes) - 20))
        else:
            out.print_md("Aucune collision détectée !")


if __name__ == '__main__':
    main()