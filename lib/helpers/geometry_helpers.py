# -*- coding: utf-8 -*-
"""
GeometryHelpers - Fonctions utilitaires pour la geometrie
==========================================================
Operations geometriques courantes sans dependance Revit directe.

Auteur : AutoRevit Team
Date : 2025
"""

import math
from utils.logger import get_logger

logger = get_logger(__name__)

# Imports Revit API optionnels
try:
    from Autodesk.Revit.DB import XYZ, Line, Curve, CurveLoop, Plane, Transform
    REVIT_AVAILABLE = True
except ImportError:
    REVIT_AVAILABLE = False
    
    # Classe XYZ factice pour mode developpement
    class XYZ:
        def __init__(self, x=0, y=0, z=0):
            self.X = x
            self.Y = y
            self.Z = z
            self.x = x
            self.y = y
            self.z = z
        
        def DistanceTo(self, other):
            dx = self.X - other.X
            dy = self.Y - other.Y
            dz = self.Z - other.Z
            return math.sqrt(dx*dx + dy*dy + dz*dz)
        
        def Add(self, other):
            return XYZ(self.X + other.X, self.Y + other.Y, self.Z + other.Z)
        
        def Subtract(self, other):
            return XYZ(self.X - other.X, self.Y - other.Y, self.Z - other.Z)
        
        def Multiply(self, scalar):
            return XYZ(self.X * scalar, self.Y * scalar, self.Z * scalar)
        
        def Divide(self, scalar):
            return XYZ(self.X / scalar, self.Y / scalar, self.Z / scalar)
        
        def Normalize(self):
            length = self.GetLength()
            if length > 0:
                return self.Divide(length)
            return self
        
        def DotProduct(self, other):
            return self.X * other.X + self.Y * other.Y + self.Z * other.Z
        
        def CrossProduct(self, other):
            return XYZ(
                self.Y * other.Z - self.Z * other.Y,
                self.Z * other.X - self.X * other.Z,
                self.X * other.Y - self.Y * other.X
            )
        
        def GetLength(self):
            return math.sqrt(self.X*self.X + self.Y*self.Y + self.Z*self.Z)
        
        @staticmethod
        def zero():
            return XYZ(0, 0, 0)
        
        @staticmethod
        def basisX():
            return XYZ(1, 0, 0)
        
        @staticmethod
        def basisY():
            return XYZ(0, 1, 0)
        
        @staticmethod
        def basisZ():
            return XYZ(0, 0, 1)
    
    class Line:
        @staticmethod
        def CreateBound(p1, p2):
            return None
    
    class CurveLoop:
        pass
    
    class Plane:
        pass
    
    class Transform:
        pass


# ========================================================================
# CONVERSIONS UNITES (sans Revit)
# ========================================================================

def mm_to_feet(mm_value):
    """Convertit millimetres en feet."""
    return mm_value / 304.8


def feet_to_mm(feet_value):
    """Convertit feet en millimetres."""
    return feet_value * 304.8


def m_to_feet(m_value):
    """Convertit metres en feet."""
    return m_value * 3.28084


def feet_to_m(feet_value):
    """Convertit feet en metres."""
    return feet_value / 3.28084


# ========================================================================
# CALCULS DE POINTS ET DISTANCES
# ========================================================================

def distance_between_points(p1, p2):
    """
    Calcule la distance entre deux points.
    
    Args:
        p1 (XYZ): Premier point
        p2 (XYZ): Deuxieme point
    
    Returns:
        float: Distance en feet
    """
    try:
        return p1.DistanceTo(p2)
    except Exception as e:
        logger.error("Erreur distance_between_points: " + str(e))
        return 0.0


def distance_between_points_mm(p1, p2):
    """
    Calcule la distance entre deux points en mm.
    
    Args:
        p1 (XYZ): Premier point
        p2 (XYZ): Deuxieme point
    
    Returns:
        float: Distance en mm
    """
    return feet_to_mm(distance_between_points(p1, p2))


def midpoint(p1, p2):
    """
    Calcule le point milieu entre deux points.
    
    Args:
        p1 (XYZ): Premier point
        p2 (XYZ): Deuxieme point
    
    Returns:
        XYZ: Point milieu
    """
    try:
        return XYZ(
            (p1.X + p2.X) / 2,
            (p1.Y + p2.Y) / 2,
            (p1.Z + p2.Z) / 2
        )
    except Exception as e:
        logger.error("Erreur midpoint: " + str(e))
        return XYZ.zero() if REVIT_AVAILABLE else XYZ(0, 0, 0)


def centroid(points):
    """
    Calcule le centroide d'une liste de points.
    
    Args:
        points (list): Liste de points XYZ
    
    Returns:
        XYZ: Centroide
    """
    if not points:
        return XYZ.zero() if REVIT_AVAILABLE else XYZ(0, 0, 0)
    
    try:
        count = len(points)
        sum_x = 0.0
        sum_y = 0.0
        sum_z = 0.0
        
        for p in points:
            sum_x += p.X
            sum_y += p.Y
            sum_z += p.Z
        
        return XYZ(
            sum_x / count,
            sum_y / count,
            sum_z / count
        )
    except Exception as e:
        logger.error("Erreur centroid: " + str(e))
        return XYZ.zero() if REVIT_AVAILABLE else XYZ(0, 0, 0)


def is_point_on_line(point, line_start, line_end, tolerance_mm=10):
    """
    Verifie si un point est sur un segment.
    
    Args:
        point (XYZ): Point a tester
        line_start (XYZ): Debut du segment
        line_end (XYZ): Fin du segment
        tolerance_mm (float): Tolerance en mm
    
    Returns:
        bool: True si point sur segment
    """
    try:
        # Distance au segment
        d = distance_point_to_segment(point, line_start, line_end)
        d_mm = feet_to_mm(d)
        
        if d_mm > tolerance_mm:
            return False
        
        # Verifier si le point est entre les extremites
        dot_product = (point.X - line_start.X) * (line_end.X - line_start.X) + \
                     (point.Y - line_start.Y) * (line_end.Y - line_start.Y) + \
                     (point.Z - line_start.Z) * (line_end.Z - line_start.Z)
        
        if dot_product < 0:
            return False
        
        squared_length = (line_end.X - line_start.X)**2 + \
                        (line_end.Y - line_start.Y)**2 + \
                        (line_end.Z - line_start.Z)**2
        
        if dot_product > squared_length:
            return False
        
        return True
    except Exception as e:
        logger.error("Erreur is_point_on_line: " + str(e))
        return False


def distance_point_to_segment(point, segment_start, segment_end):
    """
    Calcule la distance d'un point a un segment.
    
    Args:
        point (XYZ): Point
        segment_start (XYZ): Debut segment
        segment_end (XYZ): Fin segment
    
    Returns:
        float: Distance en feet
    """
    try:
        # Vecteur du segment
        segment_vec = segment_end.Subtract(segment_start)
        segment_length = segment_vec.GetLength()
        
        if segment_length == 0:
            return point.DistanceTo(segment_start)
        
        # Projection du point sur la ligne
        point_vec = point.Subtract(segment_start)
        t = point_vec.DotProduct(segment_vec) / (segment_length * segment_length)
        
        if t < 0:
            return point.DistanceTo(segment_start)
        elif t > 1:
            return point.DistanceTo(segment_end)
        else:
            projection = segment_start.Add(segment_vec.Multiply(t))
            return point.DistanceTo(projection)
    except Exception as e:
        logger.error("Erreur distance_point_to_segment: " + str(e))
        return float('inf')


def project_point_on_line(point, line_start, line_end):
    """
    Projette un point sur une ligne.
    
    Args:
        point (XYZ): Point a projeter
        line_start (XYZ): Debut ligne
        line_end (XYZ): Fin ligne
    
    Returns:
        XYZ: Point projete
    """
    try:
        line_vec = line_end.Subtract(line_start)
        line_length = line_vec.GetLength()
        
        if line_length == 0:
            return line_start
        
        point_vec = point.Subtract(line_start)
        t = point_vec.DotProduct(line_vec) / (line_length * line_length)
        
        return line_start.Add(line_vec.Multiply(t))
    except Exception as e:
        logger.error("Erreur project_point_on_line: " + str(e))
        return line_start


def offset_point(point, direction, distance_feet):
    """
    Decale un point dans une direction.
    
    Args:
        point (XYZ): Point d'origine
        direction (XYZ): Vecteur direction
        distance_feet (float): Distance en feet
    
    Returns:
        XYZ: Point decale
    """
    try:
        norm_dir = direction.Normalize()
        offset = norm_dir.Multiply(distance_feet)
        return point.Add(offset)
    except Exception as e:
        logger.error("Erreur offset_point: " + str(e))
        return point


# ========================================================================
# VECTEURS
# ========================================================================

def vector_from_points(p1, p2):
    """
    Cree un vecteur entre deux points.
    
    Args:
        p1 (XYZ): Point de depart
        p2 (XYZ): Point d'arrivee
    
    Returns:
        XYZ: Vecteur
    """
    try:
        return p2.Subtract(p1)
    except Exception as e:
        logger.error("Erreur vector_from_points: " + str(e))
        return XYZ.zero() if REVIT_AVAILABLE else XYZ(0, 0, 0)


def normalize_vector(vector):
    """
    Normalise un vecteur.
    
    Args:
        vector (XYZ): Vecteur
    
    Returns:
        XYZ: Vecteur normalise
    """
    try:
        return vector.Normalize()
    except Exception as e:
        logger.error("Erreur normalize_vector: " + str(e))
        return vector


def vector_length(vector):
    """
    Calcule la longueur d'un vecteur.
    
    Args:
        vector (XYZ): Vecteur
    
    Returns:
        float: Longueur
    """
    try:
        return vector.GetLength()
    except Exception as e:
        logger.error("Erreur vector_length: " + str(e))
        return 0.0


def dot_product(v1, v2):
    """
    Calcule le produit scalaire.
    
    Args:
        v1 (XYZ): Premier vecteur
        v2 (XYZ): Deuxieme vecteur
    
    Returns:
        float: Produit scalaire
    """
    try:
        return v1.DotProduct(v2)
    except Exception as e:
        logger.error("Erreur dot_product: " + str(e))
        return 0.0


def cross_product(v1, v2):
    """
    Calcule le produit vectoriel.
    
    Args:
        v1 (XYZ): Premier vecteur
        v2 (XYZ): Deuxieme vecteur
    
    Returns:
        XYZ: Produit vectoriel
    """
    try:
        return v1.CrossProduct(v2)
    except Exception as e:
        logger.error("Erreur cross_product: " + str(e))
        return XYZ.zero() if REVIT_AVAILABLE else XYZ(0, 0, 0)


def angle_between_vectors(v1, v2):
    """
    Calcule l'angle entre deux vecteurs.
    
    Args:
        v1 (XYZ): Premier vecteur
        v2 (XYZ): Deuxieme vecteur
    
    Returns:
        float: Angle en radians
    """
    try:
        dot = v1.Normalize().DotProduct(v2.Normalize())
        dot = max(-1.0, min(1.0, dot))
        return math.acos(dot)
    except Exception as e:
        logger.error("Erreur angle_between_vectors: " + str(e))
        return 0.0


# ========================================================================
# COURBES
# ========================================================================

def create_line(p1, p2):
    """
    Cree une ligne entre deux points.
    
    Args:
        p1 (XYZ): Point de depart
        p2 (XYZ): Point d'arrivee
    
    Returns:
        Line: Ligne creee
    """
    if not REVIT_AVAILABLE:
        return None
    
    try:
        return Line.CreateBound(p1, p2)
    except Exception as e:
        logger.error("Erreur create_line: " + str(e))
        return None


def get_curve_length(curve):
    """
    Calcule la longueur d'une courbe.
    
    Args:
        curve (Curve): Courbe
    
    Returns:
        float: Longueur en feet
    """
    if not REVIT_AVAILABLE or not curve:
        return 0.0
    
    try:
        return curve.Length
    except Exception as e:
        logger.error("Erreur get_curve_length: " + str(e))
        return 0.0


def get_curve_midpoint(curve):
    """
    Calcule le point milieu d'une courbe.
    
    Args:
        curve (Curve): Courbe
    
    Returns:
        XYZ: Point milieu
    """
    if not REVIT_AVAILABLE or not curve:
        return None
    
    try:
        return curve.Evaluate(0.5, True)
    except Exception as e:
        logger.error("Erreur get_curve_midpoint: " + str(e))
        return None


def get_curve_endpoints(curve):
    """
    Recupere les extremites d'une courbe.
    
    Args:
        curve (Curve): Courbe
    
    Returns:
        tuple: (point_depart, point_arrivee)
    """
    if not REVIT_AVAILABLE or not curve:
        return (None, None)
    
    try:
        return (curve.GetEndPoint(0), curve.GetEndPoint(1))
    except Exception as e:
        logger.error("Erreur get_curve_endpoints: " + str(e))
        return (None, None)


# ========================================================================
# INTERSECTIONS
# ========================================================================

def intersect_lines(line1_start, line1_end, line2_start, line2_end):
    """
    Calcule l'intersection de deux segments.
    
    Args:
        line1_start (XYZ): Debut ligne 1
        line1_end (XYZ): Fin ligne 1
        line2_start (XYZ): Debut ligne 2
        line2_end (XYZ): Fin ligne 2
    
    Returns:
        XYZ: Point d'intersection ou None
    """
    try:
        # Vecteurs des lignes
        v1 = vector_from_points(line1_start, line1_end)
        v2 = vector_from_points(line2_start, line2_end)
        v3 = vector_from_points(line1_start, line2_start)
        
        # Produit vectoriel
        cross1 = cross_product(v1, v2)
        cross2 = cross_product(v3, v2)
        
        if vector_length(cross1) == 0:
            return None
        
        t = vector_length(cross2) / vector_length(cross1)
        
        # Verifier signe
        if dot_product(cross1, cross2) < 0:
            t = -t
        
        # Point d'intersection
        intersection = line1_start.Add(v1.Multiply(t))
        
        # Verifier si intersection est sur les segments
        if t < 0 or t > 1:
            return None
        
        # Verifier deuxieme segment
        v4 = vector_from_points(line2_start, intersection)
        s = vector_length(v4) / vector_length(v2)
        
        if s < 0 or s > 1:
            return None
        
        return intersection
    except Exception as e:
        logger.error("Erreur intersect_lines: " + str(e))
        return None


def intersect_line_and_plane(line_point, line_direction, plane_point, plane_normal):
    """
    Calcule l'intersection d'une ligne et d'un plan.
    
    Args:
        line_point (XYZ): Point sur la ligne
        line_direction (XYZ): Direction de la ligne
        plane_point (XYZ): Point sur le plan
        plane_normal (XYZ): Normale du plan
    
    Returns:
        XYZ: Point d'intersection ou None
    """
    try:
        d = dot_product(plane_normal, line_direction)
        
        if abs(d) < 0.000001:
            return None
        
        v = vector_from_points(plane_point, line_point)
        t = dot_product(plane_normal, v) / d
        
        return line_point.Add(line_direction.Multiply(t))
    except Exception as e:
        logger.error("Erreur intersect_line_and_plane: " + str(e))
        return None


# ========================================================================
# FORMES
# ========================================================================

def create_rectangle_loop(p1, p2, p3, p4):
    """
    Cree une boucle de courbes rectangulaire.
    
    Args:
        p1, p2, p3, p4 (XYZ): Points du rectangle
    
    Returns:
        CurveLoop: Boucle de courbes
    """
    if not REVIT_AVAILABLE:
        return None
    
    try:
        curve_loop = CurveLoop()
        curve_loop.Append(Line.CreateBound(p1, p2))
        curve_loop.Append(Line.CreateBound(p2, p3))
        curve_loop.Append(Line.CreateBound(p3, p4))
        curve_loop.Append(Line.CreateBound(p4, p1))
        return curve_loop
    except Exception as e:
        logger.error("Erreur create_rectangle_loop: " + str(e))
        return None


def create_circle_loop(center, radius_feet, segments=32):
    """
    Cree une boucle de courbes circulaire.
    
    Args:
        center (XYZ): Centre du cercle
        radius_feet (float): Rayon en feet
        segments (int): Nombre de segments
    
    Returns:
        CurveLoop: Boucle de courbes
    """
    if not REVIT_AVAILABLE:
        return None
    
    try:
        curve_loop = CurveLoop()
        
        for i in range(segments):
            angle1 = 2 * math.pi * i / segments
            angle2 = 2 * math.pi * (i + 1) / segments
            
            p1 = XYZ(
                center.X + radius_feet * math.cos(angle1),
                center.Y + radius_feet * math.sin(angle1),
                center.Z
            )
            
            p2 = XYZ(
                center.X + radius_feet * math.cos(angle2),
                center.Y + radius_feet * math.sin(angle2),
                center.Z
            )
            
            curve_loop.Append(Line.CreateBound(p1, p2))
        
        return curve_loop
    except Exception as e:
        logger.error("Erreur create_circle_loop: " + str(e))
        return None


def points_to_curve_loop(points):
    """
    Cree une boucle de courbes a partir de points.
    
    Args:
        points (list): Liste de points XYZ
    
    Returns:
        CurveLoop: Boucle de courbes
    """
    if not REVIT_AVAILABLE or len(points) < 3:
        return None
    
    try:
        curve_loop = CurveLoop()
        
        for i in range(len(points)):
            start = points[i]
            end = points[(i + 1) % len(points)]
            curve_loop.Append(Line.CreateBound(start, end))
        
        return curve_loop
    except Exception as e:
        logger.error("Erreur points_to_curve_loop: " + str(e))
        return None


def is_rectangle(points, tolerance_mm=50):
    """
    Verifie si 4 points forment un rectangle.
    
    Args:
        points (list): 4 points
        tolerance_mm (float): Tolerance
    
    Returns:
        bool: True si rectangle
    """
    if len(points) != 4:
        return False
    
    try:
        # Vecteurs des cotes
        v1 = vector_from_points(points[0], points[1])
        v2 = vector_from_points(points[1], points[2])
        v3 = vector_from_points(points[2], points[3])
        v4 = vector_from_points(points[3], points[0])
        
        # Produits scalaires doivent etre ~0 (angles droits)
        tolerance = mm_to_feet(tolerance_mm)
        
        return (abs(dot_product(v1, v2)) < tolerance and
                abs(dot_product(v2, v3)) < tolerance and
                abs(dot_product(v3, v4)) < tolerance and
                abs(dot_product(v4, v1)) < tolerance)
    except Exception as e:
        logger.error("Erreur is_rectangle: " + str(e))
        return False


# ========================================================================
# POINTS - CONVERSIONS
# ========================================================================

def point_to_dict(point):
    """
    Convertit un point en dictionnaire.
    
    Args:
        point (XYZ): Point
    
    Returns:
        dict: {'x': x, 'y': y, 'z': z}
    """
    if not point:
        return {'x': 0, 'y': 0, 'z': 0}
    
    try:
        return {
            'x': point.X,
            'y': point.Y,
            'z': point.Z
        }
    except Exception as e:
        logger.error("Erreur point_to_dict: " + str(e))
        return {'x': 0, 'y': 0, 'z': 0}


def point_to_dict_mm(point):
    """
    Convertit un point en dictionnaire (mm).
    
    Args:
        point (XYZ): Point
    
    Returns:
        dict: {'x': x_mm, 'y': y_mm, 'z': z_mm}
    """
    d = point_to_dict(point)
    return {
        'x': feet_to_mm(d['x']),
        'y': feet_to_mm(d['y']),
        'z': feet_to_mm(d['z'])
    }


def dict_to_point(d):
    """
    Convertit un dictionnaire en point.
    
    Args:
        d (dict): {'x': x, 'y': y, 'z': z}
    
    Returns:
        XYZ: Point
    """
    try:
        return XYZ(
            d.get('x', 0),
            d.get('y', 0),
            d.get('z', 0)
        )
    except Exception as e:
        logger.error("Erreur dict_to_point: " + str(e))
        return XYZ.zero() if REVIT_AVAILABLE else XYZ(0, 0, 0)


def points_to_list(points):
    """
    Convertit une liste de points en liste de dictionnaires.
    
    Args:
        points (list): Liste de points XYZ
    
    Returns:
        list: Liste de dict {'x': x, 'y': y, 'z': z}
    """
    return [point_to_dict(p) for p in points]


def points_to_list_mm(points):
    """
    Convertit une liste de points en liste de dictionnaires (mm).
    
    Args:
        points (list): Liste de points XYZ
    
    Returns:
        list: Liste de dict {'x': x_mm, 'y': y_mm, 'z': z_mm}
    """
    return [point_to_dict_mm(p) for p in points]


# ========================================================================
# VALIDATION
# ========================================================================

def is_valid_point(point):
    """
    Verifie si un point est valide.
    
    Args:
        point: Point a verifier
    
    Returns:
        bool: True si valide
    """
    if point is None:
        return False
    
    try:
        hasattr(point, 'X') and hasattr(point, 'Y') and hasattr(point, 'Z')
        return True
    except:
        return False


def is_valid_curve(curve):
    """
    Verifie si une courbe est valide.
    
    Args:
        curve: Courbe a verifier
    
    Returns:
        bool: True si valide
    """
    if curve is None:
        return False
    
    try:
        return curve.Length > 0
    except:
        return False


# ========================================================================
# FONCTION DE TEST
# ========================================================================

def test_geometry_helpers():
    print("\n" + "="*60)
    print("TEST GEOMETRY HELPERS")
    print("="*60)
    
    # Test points
    print("\n1 Test points:")
    p1 = XYZ(0, 0, 0)
    p2 = XYZ(10, 0, 0)
    
    dist = distance_between_points_mm(p1, p2)
    print("   Distance 10ft = " + str(int(dist)) + " mm")
    
    mid = midpoint(p1, p2)
    print("   Point milieu: X=" + str(mid.X))
    
    # Test vecteurs
    print("\n2 Test vecteurs:")
    v = vector_from_points(p1, p2)
    print("   Vecteur: (" + str(v.X) + ", " + str(v.Y) + ", " + str(v.Z) + ")")
    print("   Longueur: " + str(vector_length(v)))
    
    # Test conversions
    print("\n3 Test conversions:")
    print("   1000 mm = " + str(mm_to_feet(1000)) + " ft")
    print("   10 ft = " + str(int(feet_to_mm(10))) + " mm")
    
    print("\n" + "="*60)
    print("TEST TERMINE")
    print("="*60 + "\n")


if __name__ == '__main__':
    test_geometry_helpers()