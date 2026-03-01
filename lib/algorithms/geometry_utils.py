# -*- coding: utf-8 -*-
"""Utilitaires geometriques pour AutoRevit v3.1
Version adaptee pour coherence avec CleanupEngine

Fonctions utilitaires pour :
- Calculs de distances, intersections, projections
- Transformation de points et courbes
- Detection de formes geometriques
- Conversion d'unites (synchronise avec CleanupEngine)
- Tri et organisation spatiale
- [v3.1] Fonctions supplementaires pour WallPlacementEngine

CORRECTION v3.1 :
- Ajout de get_project_origin_from_elements() : detecte l'origine reelle
  du batiment depuis les murs/planchers, independamment de (0,0)
- get_project_bbox_from_grids() inchangee (utilisee pour analyser les grilles)
- Toute creation de grille doit utiliser get_project_origin_from_elements()
  comme point de depart, pas les coordonnees absolues (0,0)

AJOUTS v3.2 (WallPlacementEngine) :
- get_rectangle_from_points()     : rectangle englobant depuis liste de points
- find_intermediate_points()      : points intermediaires sur une courbe
- get_wall_orientation()          : orientation H/V d'un mur
- segment_length_mm()             : longueur d'un segment en mm
- points_are_collinear()          : teste si des points sont alignes
- get_wall_axis_direction()       : vecteur directeur d'un mur
"""

from __future__ import division, print_function
import math
from collections import defaultdict

from Autodesk.Revit.DB import (
    XYZ, Line, Curve, CurveLoop, Plane,
    Transform, BoundingBoxXYZ, IntersectionResultArray,
    SetComparisonResult, Grid, Level, Element,
    FilteredElementCollector, Wall, Floor
)

# ---------------------------------------------------------------------
# CONSTANTES SYNCHRONISEES AVEC CleanupEngine
# ---------------------------------------------------------------------

class Tolerances:
    """Tolerances synchronisees avec le CleanupEngine du script principal"""
    DUPLICATE_ELEV_MM     = 50.0
    DUPLICATE_GRID_MM     = 50.0
    GAP_MIN_M             = 0.30
    GAP_MAX_M             = 20.0
    ELEV_NEGATIVE_LIMIT_M = -0.5
    MIN_GRID_LENGTH_M     = 2.0
    DIAG_MIN_DEG          = 10.0
    DIAG_MAX_DEG          = 80.0
    POINT_ON_LINE_MM      = 10.0


# ---------------------------------------------------------------------
# CONVERSIONS D'UNITES
# ---------------------------------------------------------------------

def mm_to_feet(mm):
    return mm / 304.8

def feet_to_mm(feet):
    return feet * 304.8

def m_to_feet(m):
    return m / 0.3048

def feet_to_m(feet):
    return feet * 0.3048


# ---------------------------------------------------------------------
# NOUVEAU : DETECTION DE L'ORIGINE REELLE DU PROJET
# ---------------------------------------------------------------------

def get_project_origin_from_elements(doc):
    """
    Detecte automatiquement l'origine reelle du batiment pour N'IMPORTE QUEL projet.

    Contrairement a (0, 0) qui est l'origine absolue Revit, cette fonction
    cherche la position reelle des elements modelises (murs, planchers)
    et retourne le coin bas-gauche du batiment comme point d'origine.

    Utilisation obligatoire pour toute creation de grilles :
        origin = get_project_origin_from_elements(doc)
        x_grille = origin['x_min_m'] + offset_x_m
        y_grille = origin['y_min_m'] + offset_y_m

    Args:
        doc: Document Revit actif

    Returns:
        dict avec :
            x_min_m, y_min_m  : coin bas-gauche du batiment (metres)
            x_max_m, y_max_m  : coin haut-droite (metres)
            cx_m, cy_m        : centre du batiment (metres)
            largeur_m         : largeur totale (metres)
            hauteur_m         : hauteur totale (metres)
            source            : 'murs+planchers', 'murs', 'planchers' ou 'fallback(0,0)'
        None si aucun element trouve
    """
    xs, ys = [], []
    source_parts = []

    # Murs
    try:
        walls = list(FilteredElementCollector(doc).OfClass(Wall))
        for w in walls:
            try:
                bb = w.get_BoundingBox(None)
                if bb:
                    xs.extend([feet_to_m(float(bb.Min.X)), feet_to_m(float(bb.Max.X))])
                    ys.extend([feet_to_m(float(bb.Min.Y)), feet_to_m(float(bb.Max.Y))])
            except:
                pass
        if xs:
            source_parts.append("murs")
    except:
        pass

    # Planchers
    try:
        floors = list(FilteredElementCollector(doc).OfClass(Floor))
        for f in floors:
            try:
                bb = f.get_BoundingBox(None)
                if bb:
                    xs.extend([feet_to_m(float(bb.Min.X)), feet_to_m(float(bb.Max.X))])
                    ys.extend([feet_to_m(float(bb.Min.Y)), feet_to_m(float(bb.Max.Y))])
            except:
                pass
        if floors:
            source_parts.append("planchers")
    except:
        pass

    # Fallback
    if not xs or not ys:
        print("AVERTISSEMENT get_project_origin_from_elements : "
              "aucun mur ni plancher trouve, origine = (0, 0)")
        return {
            'x_min_m': 0.0, 'y_min_m': 0.0,
            'x_max_m': 0.0, 'y_max_m': 0.0,
            'cx_m': 0.0,    'cy_m': 0.0,
            'largeur_m': 0.0, 'hauteur_m': 0.0,
            'source': 'fallback(0,0)'
        }

    x_min = min(xs); x_max = max(xs)
    y_min = min(ys); y_max = max(ys)

    return {
        'x_min_m':   x_min,
        'y_min_m':   y_min,
        'x_max_m':   x_max,
        'y_max_m':   y_max,
        'cx_m':      (x_min + x_max) / 2.0,
        'cy_m':      (y_min + y_max) / 2.0,
        'largeur_m': x_max - x_min,
        'hauteur_m': y_max - y_min,
        'source':    '+'.join(source_parts) if source_parts else 'fallback(0,0)'
    }


def make_grid_position(origin, offset_x_m=0.0, offset_y_m=0.0):
    """
    Calcule la position absolue d'une grille a partir de l'origine reelle.

    Args:
        origin     : dict retourne par get_project_origin_from_elements()
        offset_x_m : decalage en X depuis le bord gauche du batiment (metres)
        offset_y_m : decalage en Y depuis le bord bas du batiment (metres)

    Returns:
        dict avec x_m, y_m (metres) et x_ft, y_ft (pieds pour l'API Revit)
    """
    x_m = origin['x_min_m'] + offset_x_m
    y_m = origin['y_min_m'] + offset_y_m
    return {
        'x_m':  x_m,
        'y_m':  y_m,
        'x_ft': m_to_feet(x_m),
        'y_ft': m_to_feet(y_m)
    }


# ---------------------------------------------------------------------
# 1. CALCULS DE DISTANCES ET POSITIONS
# ---------------------------------------------------------------------

def calculate_distance(point1, point2):
    return point1.DistanceTo(point2)

def calculate_distance_mm(point1, point2):
    return feet_to_mm(point1.DistanceTo(point2))

def calculate_distance_m(point1, point2):
    return feet_to_m(point1.DistanceTo(point2))

def calculate_centroid(points):
    if not points:
        return XYZ.Zero
    count = len(points)
    sum_x = sum(p.X for p in points)
    sum_y = sum(p.Y for p in points)
    sum_z = sum(p.Z for p in points)
    return XYZ(sum_x / count, sum_y / count, sum_z / count)

def is_point_on_line(point, line, tolerance_mm=None):
    if tolerance_mm is None:
        tolerance_mm = Tolerances.POINT_ON_LINE_MM
    tolerance_feet = mm_to_feet(tolerance_mm)
    result = line.Project(point)
    if result:
        return result.Distance <= tolerance_feet
    return False

def project_point_on_curve(point, curve):
    result = curve.Project(point)
    if result:
        return (result.XYZPoint, result.Parameter)
    return (None, None)

def offset_point(point, direction, distance_mm):
    distance_feet = mm_to_feet(distance_mm)
    offset_vector = direction.Normalize().Multiply(distance_feet)
    return point.Add(offset_vector)

def get_midpoint(point1, point2):
    return XYZ(
        (point1.X + point2.X) / 2.0,
        (point1.Y + point2.Y) / 2.0,
        (point1.Z + point2.Z) / 2.0
    )


# ---------------------------------------------------------------------
# 2. CLASSIFICATION DES GRILLES
# ---------------------------------------------------------------------

def classify_grid_by_angle(grid):
    """
    Classifie une grille selon l'angle de sa courbe.
    Retourne 'X' (vertical), 'Y' (horizontal) ou '?'
    """
    try:
        curve = grid.Curve
        start = curve.GetEndPoint(0)
        end   = curve.GetEndPoint(1)

        dx = abs(float(end.X) - float(start.X))
        dy = abs(float(end.Y) - float(start.Y))
        length_m = math.sqrt(dx*dx + dy*dy) * 0.3048
        angle_deg = abs(math.degrees(math.atan2(dy, dx)))

        if angle_deg >= (90.0 - Tolerances.DIAG_MIN_DEG):
            gtype    = "X"
            position = (float(start.X) + float(end.X)) / 2.0
        elif angle_deg <= Tolerances.DIAG_MIN_DEG:
            gtype    = "Y"
            position = (float(start.Y) + float(end.Y)) / 2.0
        else:
            gtype    = "?"
            position = 0.0

        return gtype, float(angle_deg), float(position), float(length_m)

    except Exception:
        return "?", 0.0, 0.0, 0.0


def is_grid_duplicate(grid1, grid2, tolerance_mm=None):
    if tolerance_mm is None:
        tolerance_mm = Tolerances.DUPLICATE_GRID_MM
    type1, _, pos1, _ = classify_grid_by_angle(grid1)
    type2, _, pos2, _ = classify_grid_by_angle(grid2)
    if type1 != type2 or type1 == "?":
        return False
    tol_ft = mm_to_feet(tolerance_mm)
    return abs(float(pos1) - float(pos2)) < tol_ft


def get_grid_network(grids):
    """
    Organise les grilles en reseau structure.
    Returns dict avec 'X', 'Y', 'diagonal', 'all'
    """
    network = {'X': [], 'Y': [], 'diagonal': [], 'all': grids}

    for grid in grids:
        gtype, angle_deg, position, length_m = classify_grid_by_angle(grid)
        info = {
            'grid':        grid,
            'name':        str(grid.Name),
            'id':          grid.Id,
            'type':        gtype,
            'angle_deg':   float(angle_deg),
            'position_ft': float(position),
            'position_m':  float(feet_to_m(float(position))),
            'length_m':    float(length_m)
        }
        if gtype == "X":
            network['X'].append(info)
        elif gtype == "Y":
            network['Y'].append(info)
        else:
            network['diagonal'].append(info)

    network['X'].sort(key=lambda g: g['position_m'])
    network['Y'].sort(key=lambda g: g['position_m'])
    return network


# ---------------------------------------------------------------------
# 3. INTERSECTIONS ET CALCULS DE TRAVEES
# ---------------------------------------------------------------------

def calculate_grid_intersections(grids_x, grids_y):
    intersections = []
    for gx in grids_x:
        curve_x = gx['grid'].Curve if isinstance(gx, dict) else gx.Curve
        for gy in grids_y:
            curve_y = gy['grid'].Curve if isinstance(gy, dict) else gy.Curve
            result_array = IntersectionResultArray()
            result = curve_x.Intersect(curve_y, result_array)
            if result == SetComparisonResult.Overlap:
                if result_array and result_array.Size > 0:
                    pt = result_array.get_Item(0).XYZPoint
                    intersections.append({
                        'point':     pt,
                        'grid_x':   gx['name'] if isinstance(gx, dict) else gx.Name,
                        'grid_y':   gy['name'] if isinstance(gy, dict) else gy.Name,
                        'grid_x_id': gx['id'] if isinstance(gx, dict) else gx.Id,
                        'grid_y_id': gy['id'] if isinstance(gy, dict) else gy.Id,
                        'x': float(pt.X),
                        'y': float(pt.Y),
                        'z': float(pt.Z)
                    })
    intersections.sort(key=lambda p: (p['x'], p['y']))
    return intersections


def detect_rectangular_bays(grid_network):
    bays = []
    x_grids = grid_network.get('X', []) or grid_network.get('vertical', [])
    y_grids = grid_network.get('Y', []) or grid_network.get('horizontal', [])
    if len(x_grids) < 2 or len(y_grids) < 2:
        return bays
    for i in range(len(x_grids) - 1):
        x1 = float(x_grids[i]['position_ft'])
        x2 = float(x_grids[i + 1]['position_ft'])
        for j in range(len(y_grids) - 1):
            y1 = float(y_grids[j]['position_ft'])
            y2 = float(y_grids[j + 1]['position_ft'])
            corners  = [XYZ(x1,y1,0), XYZ(x2,y1,0), XYZ(x2,y2,0), XYZ(x1,y2,0)]
            w_mm = abs(feet_to_mm(x2 - x1))
            l_mm = abs(feet_to_mm(y2 - y1))
            bays.append({
                'min_x': min(x1,x2), 'max_x': max(x1,x2),
                'min_y': min(y1,y2), 'max_y': max(y1,y2),
                'corners':  corners,
                'center':   calculate_centroid(corners),
                'width_mm':  float(w_mm),
                'length_mm': float(l_mm),
                'area_m2':   float((w_mm/1000.0) * (l_mm/1000.0)),
                'grid_x1': x_grids[i]['name'],
                'grid_x2': x_grids[i+1]['name'],
                'grid_y1': y_grids[j]['name'],
                'grid_y2': y_grids[j+1]['name']
            })
    return bays


# ---------------------------------------------------------------------
# 4. BOITES ENGLOBANTES
# ---------------------------------------------------------------------

def get_project_bbox_from_grids(grids):
    """
    Calcule la boite englobante a partir des grilles existantes.
    NOTE : Pour l'origine du projet, utiliser get_project_origin_from_elements()
    """
    xs, ys = [], []
    for grid in grids:
        try:
            curve = grid.Curve
            s = curve.GetEndPoint(0)
            e = curve.GetEndPoint(1)
            xs.extend([feet_to_m(float(s.X)), feet_to_m(float(e.X))])
            ys.extend([feet_to_m(float(s.Y)), feet_to_m(float(e.Y))])
        except:
            pass
    if not xs or not ys:
        return None
    return {
        'min_x': min(xs), 'max_x': max(xs),
        'min_y': min(ys), 'max_y': max(ys)
    }


def is_point_in_bbox(point_m, bbox, margin_percent=20):
    margin_x = (bbox['max_x'] - bbox['min_x']) * (margin_percent / 100.0)
    margin_y = (bbox['max_y'] - bbox['min_y']) * (margin_percent / 100.0)
    return (bbox['min_x'] - margin_x <= point_m <= bbox['max_x'] + margin_x)


def calculate_level_gaps(levels):
    gaps = []
    for i in range(len(levels) - 1):
        current  = levels[i]
        next_lvl = levels[i + 1]
        gap      = float(next_lvl['elevation_m']) - float(current['elevation_m'])
        status   = 'normal'
        if gap < Tolerances.GAP_MIN_M:   status = 'trop_petit'
        elif gap > Tolerances.GAP_MAX_M: status = 'trop_grand'
        gaps.append({
            'from_level': current['name'],
            'to_level':   next_lvl['name'],
            'gap_m':      round(gap, 2),
            'status':     status
        })
    return gaps


def get_bounding_rectangle(points):
    if not points:
        return None
    min_x = min(p.X for p in points)
    min_y = min(p.Y for p in points)
    min_z = min(p.Z for p in points)
    max_x = max(p.X for p in points)
    max_y = max(p.Y for p in points)
    max_z = max(p.Z for p in points)
    return {
        'min_point':    XYZ(min_x, min_y, min_z),
        'max_point':    XYZ(max_x, max_y, max_z),
        'center':       calculate_centroid([XYZ(min_x,min_y,min_z), XYZ(max_x,max_y,max_z)]),
        'diagonal_ft':  calculate_distance(XYZ(min_x,min_y,min_z), XYZ(max_x,max_y,max_z)),
        'width_m':      feet_to_m(max_x - min_x),
        'length_m':     feet_to_m(max_y - min_y),
        'height_m':     feet_to_m(max_z - min_z)
    }


# ---------------------------------------------------------------------
# 5. TRANSFORMATIONS ET ORDONNANCEMENT
# ---------------------------------------------------------------------

def sort_points_clockwise(points):
    if len(points) <= 1:
        return points
    center = calculate_centroid(points)
    def get_angle(point):
        return math.atan2(point.Y - center.Y, point.X - center.X)
    return sorted(points, key=get_angle, reverse=True)

def sort_points_by_distance(ref_point, points):
    return sorted(points, key=lambda p: calculate_distance(ref_point, p))


# ---------------------------------------------------------------------
# 6. CREATION D'ENTITES GEOMETRIQUES
# ---------------------------------------------------------------------

def create_line_between_points(point1, point2):
    return Line.CreateBound(point1, point2)

def create_curve_loop_from_rectangle(points):
    if len(points) != 4:
        raise ValueError("4 points requis pour un rectangle")
    curve_loop = CurveLoop()
    for i in range(4):
        curve_loop.Append(Line.CreateBound(points[i], points[(i+1) % 4]))
    return curve_loop


# ---------------------------------------------------------------------
# 7. SERIALISATION ET UTILITAIRES
# ---------------------------------------------------------------------

def xyz_to_dict_mm(point):
    return {
        'x': round(feet_to_mm(float(point.X)), 2),
        'y': round(feet_to_mm(float(point.Y)), 2),
        'z': round(feet_to_mm(float(point.Z)), 2)
    }

def xyz_to_dict_m(point):
    return {
        'x': round(feet_to_m(float(point.X)), 3),
        'y': round(feet_to_m(float(point.Y)), 3),
        'z': round(feet_to_m(float(point.Z)), 3)
    }

def is_parallel(line1, line2, tolerance=0.001):
    if hasattr(line1, 'Direction') and hasattr(line2, 'Direction'):
        dir1  = line1.Direction.Normalize()
        dir2  = line2.Direction.Normalize()
        cross = dir1.CrossProduct(dir2)
        return cross.GetLength() < tolerance
    return False

def get_angle_between_vectors(v1, v2):
    dot = v1.Normalize().DotProduct(v2.Normalize())
    dot = max(-1.0, min(1.0, dot))
    return math.acos(dot)

def detect_wall_axes(doc, tolerance_mm=300.0):
    """
    Retourne UN AXE PAR MUR (groupes par position proche) dans les deux sens.

    Un mur quasi-vertical  (angle >= 80 deg) -> axe X (grille verticale)
    Un mur quasi-horizontal (angle <= 10 deg) -> axe Y (grille horizontale)

    Args:
        doc           : Document Revit actif
        tolerance_mm  : distance max entre deux murs pour les considerer
                        sur le meme axe (defaut 300 mm = 30 cm)

    Returns:
        dict:
            'axes_x_m'  : liste triee des positions X en metres
            'axes_y_m'  : liste triee des positions Y en metres
            'axes_x_ft' : idem en pieds
            'axes_y_ft' : idem en pieds
            'count_x'   : nombre d'axes X
            'count_y'   : nombre d'axes Y
            'details_x' : liste de dicts par axe X
            'details_y' : liste de dicts par axe Y
    """
    tol_ft = tolerance_mm / 304.8

    axes_raw_x = []
    axes_raw_y = []

    try:
        walls = list(FilteredElementCollector(doc).OfClass(Wall))
    except Exception as e:
        print("detect_wall_axes : impossible de collecter les murs (%s)" % e)
        walls = []

    for wall in walls:
        try:
            curve  = wall.Location.Curve
            start  = curve.GetEndPoint(0)
            end    = curve.GetEndPoint(1)

            dx = float(end.X) - float(start.X)
            dy = float(end.Y) - float(start.Y)
            length_ft  = math.sqrt(dx*dx + dy*dy)
            length_m   = length_ft * 0.3048

            if length_m < 0.05:
                continue

            angle_deg = abs(math.degrees(math.atan2(abs(dy), abs(dx))))

            if angle_deg >= 80.0:
                pos_ft   = (float(start.X) + float(end.X)) / 2.0
                start_m  = min(float(start.Y), float(end.Y)) * 0.3048
                end_m    = max(float(start.Y), float(end.Y)) * 0.3048
                axes_raw_x.append((pos_ft, length_m, start_m, end_m, wall.Id))

            elif angle_deg <= 10.0:
                pos_ft   = (float(start.Y) + float(end.Y)) / 2.0
                start_m  = min(float(start.X), float(end.X)) * 0.3048
                end_m    = max(float(start.X), float(end.X)) * 0.3048
                axes_raw_y.append((pos_ft, length_m, start_m, end_m, wall.Id))

        except Exception as e:
            print("detect_wall_axes : erreur lecture mur (%s)" % e)
            continue

    def grouper(axes_raw):
        if not axes_raw:
            return []
        tries = sorted(axes_raw, key=lambda a: a[0])
        groupes = []
        groupe_courant = [tries[0]]
        for entree in tries[1:]:
            pos_ft_prev = groupe_courant[-1][0]
            if abs(entree[0] - pos_ft_prev) <= tol_ft:
                groupe_courant.append(entree)
            else:
                groupes.append(groupe_courant)
                groupe_courant = [entree]
        groupes.append(groupe_courant)
        result = []
        for g in groupes:
            pos_ft_moy   = sum(e[0] for e in g) / len(g)
            pos_m_moy    = pos_ft_moy * 0.3048
            long_totale  = sum(e[1] for e in g)
            murs_detail  = [
                {
                    'longueur_m': round(e[1], 3),
                    'start_m':    round(e[2], 3),
                    'end_m':      round(e[3], 3),
                    'wall_id':    e[4]
                }
                for e in g
            ]
            result.append({
                'position_m':        round(pos_m_moy, 4),
                'position_ft':       round(pos_ft_moy, 6),
                'murs':              murs_detail,
                'longueur_totale_m': round(long_totale, 3),
                'nb_murs':           len(g)
            })
        return sorted(result, key=lambda r: r['position_m'])

    details_x = grouper(axes_raw_x)
    details_y = grouper(axes_raw_y)

    axes_x_m  = [d['position_m']  for d in details_x]
    axes_y_m  = [d['position_m']  for d in details_y]
    axes_x_ft = [d['position_ft'] for d in details_x]
    axes_y_ft = [d['position_ft'] for d in details_y]

    print("detect_wall_axes -> %d axes X, %d axes Y" % (len(axes_x_m), len(axes_y_m)))
    print("  Axes X (m) : %s" % [round(x, 2) for x in axes_x_m])
    print("  Axes Y (m) : %s" % [round(y, 2) for y in axes_y_m])

    return {
        'axes_x_m':   axes_x_m,
        'axes_y_m':   axes_y_m,
        'axes_x_ft':  axes_x_ft,
        'axes_y_ft':  axes_y_ft,
        'count_x':    len(axes_x_m),
        'count_y':    len(axes_y_m),
        'details_x':  details_x,
        'details_y':  details_y,
    }


# =====================================================================
# AJOUTS v3.2 - FONCTIONS POUR WallPlacementEngine
# =====================================================================

def get_rectangle_from_points(points):
    """
    Calcule le rectangle englobant minimal depuis une liste de points XYZ.

    Utilise par WallPlacementEngine pour encadrer les segments de voiles.

    Args:
        points : liste de XYZ

    Returns:
        dict avec :
            min_point  : XYZ coin bas-gauche
            max_point  : XYZ coin haut-droite
            width_mm   : largeur en mm
            height_mm  : hauteur en mm (axe Y)
            depth_mm   : profondeur en mm (axe Z)
            center     : XYZ centre
            corners    : liste des 4 coins (plan XY)
        None si liste vide
    """
    if not points:
        return None

    min_x = min(p.X for p in points)
    min_y = min(p.Y for p in points)
    min_z = min(p.Z for p in points)
    max_x = max(p.X for p in points)
    max_y = max(p.Y for p in points)
    max_z = max(p.Z for p in points)

    min_pt = XYZ(min_x, min_y, min_z)
    max_pt = XYZ(max_x, max_y, max_z)

    corners = [
        XYZ(min_x, min_y, min_z),
        XYZ(max_x, min_y, min_z),
        XYZ(max_x, max_y, min_z),
        XYZ(min_x, max_y, min_z),
    ]

    return {
        'min_point': min_pt,
        'max_point': max_pt,
        'width_mm':  feet_to_mm(max_x - min_x),
        'height_mm': feet_to_mm(max_y - min_y),
        'depth_mm':  feet_to_mm(max_z - min_z),
        'center':    XYZ(
                        (min_x + max_x) / 2.0,
                        (min_y + max_y) / 2.0,
                        (min_z + max_z) / 2.0
                     ),
        'corners':   corners,
    }


def find_intermediate_points(curve, num_points=5):
    """
    Trouve des points intermediaires regulierement espaces sur une courbe.

    Utilise par WallPlacementEngine pour subdiviser les murs longs
    et detecter les ouvertures intermediaires.

    Args:
        curve      : Courbe Revit (Line ou Curve)
        num_points : Nombre de points intermediaires (sans les extremites)

    Returns:
        liste de XYZ (points intermediaires uniquement, sans start/end)
        liste vide si num_points <= 0 ou courbe invalide
    """
    if num_points <= 0:
        return []

    try:
        points = []
        # On divise en (num_points + 1) intervalles
        # les parametres normalises vont de 0.0 a 1.0
        for i in range(1, num_points + 1):
            param = float(i) / float(num_points + 1)
            pt = curve.Evaluate(param, True)   # True = parametre normalise
            if pt:
                points.append(pt)
        return points
    except Exception as e:
        print("find_intermediate_points erreur : %s" % str(e))
        return []


def get_wall_orientation(wall):
    """
    Retourne l'orientation d'un mur : 'H' (horizontal), 'V' (vertical) ou '?' (diagonal).

    Utilise par WallPlacementEngine pour classer les voiles.

    Args:
        wall : Element Wall Revit

    Returns:
        str : 'H', 'V' ou '?'
    """
    try:
        loc = wall.Location
        if not hasattr(loc, 'Curve'):
            return '?'
        curve = loc.Curve
        start = curve.GetEndPoint(0)
        end   = curve.GetEndPoint(1)
        dx = abs(float(end.X) - float(start.X))
        dy = abs(float(end.Y) - float(start.Y))
        angle_deg = abs(math.degrees(math.atan2(dy, dx)))
        if angle_deg <= 10.0:
            return 'H'
        elif angle_deg >= 80.0:
            return 'V'
        else:
            return '?'
    except:
        return '?'


def segment_length_mm(point1, point2):
    """
    Calcule la longueur entre deux points XYZ en millimetres.

    Args:
        point1, point2 : XYZ

    Returns:
        float : longueur en mm
    """
    try:
        return feet_to_mm(point1.DistanceTo(point2))
    except:
        return 0.0


def points_are_collinear(points, tolerance_mm=10.0):
    """
    Teste si une liste de points XYZ sont alignes (colineaires).

    Utilise par WallPlacementEngine pour valider les segments de voile.

    Args:
        points       : liste de XYZ (minimum 3)
        tolerance_mm : tolerance d'alignement en mm

    Returns:
        bool : True si tous les points sont alignes
    """
    if len(points) < 3:
        return True

    try:
        tol_ft = mm_to_feet(tolerance_mm)
        p0 = points[0]
        p1 = points[-1]

        # Vecteur directeur de la droite de reference
        ref_line = Line.CreateBound(p0, p1)

        for pt in points[1:-1]:
            result = ref_line.Project(pt)
            if result and result.Distance > tol_ft:
                return False
        return True
    except Exception as e:
        print("points_are_collinear erreur : %s" % str(e))
        return True


def get_wall_axis_direction(wall):
    """
    Retourne le vecteur directeur normalise d'un mur.

    Utilise par WallPlacementEngine pour orienter les voiles correctement.

    Args:
        wall : Element Wall Revit

    Returns:
        XYZ vecteur normalise, ou XYZ(1, 0, 0) par defaut
    """
    try:
        loc = wall.Location
        if not hasattr(loc, 'Curve'):
            return XYZ(1, 0, 0)
        curve = loc.Curve
        start = curve.GetEndPoint(0)
        end   = curve.GetEndPoint(1)
        dx = end.X - start.X
        dy = end.Y - start.Y
        dz = end.Z - start.Z
        length = math.sqrt(dx*dx + dy*dy + dz*dz)
        if length < 1e-9:
            return XYZ(1, 0, 0)
        return XYZ(dx / length, dy / length, dz / length)
    except:
        return XYZ(1, 0, 0)


def clamp_param(value, min_val=0.0, max_val=1.0):
    """
    Limite une valeur entre min_val et max_val.
    Utilitaire simple pour les parametres de courbes (0.0 - 1.0).

    Args:
        value   : valeur a limiter
        min_val : borne inferieure (defaut 0.0)
        max_val : borne superieure (defaut 1.0)

    Returns:
        float
    """
    return max(min_val, min(max_val, value))


def is_rectangle(points, tolerance_mm=50.0):
    """
    Teste si 4 points XYZ forment un rectangle.

    Verifie que les angles sont droits en testant
    l'orthogonalite des vecteurs adjacents.

    Args:
        points       : liste de 4 XYZ
        tolerance_mm : tolerance angulaire en mm (produit scalaire)

    Returns:
        bool : True si les 4 points forment un rectangle
    """
    if not points or len(points) != 4:
        return False

    try:
        tol = mm_to_feet(tolerance_mm)

        def vec(a, b):
            return XYZ(b.X - a.X, b.Y - a.Y, b.Z - a.Z)

        v0 = vec(points[0], points[1])
        v1 = vec(points[1], points[2])
        v2 = vec(points[2], points[3])
        v3 = vec(points[3], points[0])

        # Chaque paire de vecteurs adjacents doit etre perpendiculaire
        def dot(a, b):
            return a.X * b.X + a.Y * b.Y + a.Z * b.Z

        return (
            abs(dot(v0, v1)) < tol and
            abs(dot(v1, v2)) < tol and
            abs(dot(v2, v3)) < tol and
            abs(dot(v3, v0)) < tol
        )
    except Exception as e:
        print("is_rectangle erreur : %s" % str(e))
        return False