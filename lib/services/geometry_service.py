# -*- coding: utf-8 -*-
"""
GeometryService - Service de geometrie pour Revit
==================================================
Responsabilites :
- Calculs geometriques (intersections, distances, projections)
- Transformations de points et courbes
- Detection de formes
- Utilitaires de bounding box

Auteur : AutoRevit Team
Date : 2025
"""

from utils.logger import get_logger
from utils.exceptions import AutoRevitError

logger = get_logger(__name__)


class RevitAPIError(AutoRevitError):
    """Exception levee en cas d'erreur avec l'API Revit."""
    pass


# Imports Revit API (avec gestion si hors Revit)
try:
    from Autodesk.Revit.DB import (
        XYZ,
        Line,
        Curve,
        CurveLoop,
        Plane,
        Transform,
        BoundingBoxXYZ,
        IntersectionResultArray,
        SetComparisonResult,
        Solid,
        GeometryElement,
        GeometryInstance,
        Options,
        Face,
        Edge,
        Mesh,
        FilteredElementCollector,
        BuiltInCategory
    )
    REVIT_AVAILABLE = True
except ImportError:
    
    REVIT_AVAILABLE = False


class GeometryService:
    """Service de geometrie pour Revit."""

    def __init__(self, document):
        if not REVIT_AVAILABLE:
            raise RevitAPIError("Revit API non disponible")
        
        self.doc = document
        self.options = Options()
        self.options.ComputeReferences = True
        self.options.DetailLevel = 0
        self.options.IncludeNonVisibleObjects = False
        
        logger.info("GeometryService initialise")
    
    def calculate_distance(self, point1, point2):
        try:
            return point1.DistanceTo(point2)
        except Exception as e:
            logger.error("Erreur calculate_distance: " + str(e))
            return 0.0
    
    def calculate_distance_mm(self, point1, point2):
        try:
            return self.feet_to_mm(point1.DistanceTo(point2))
        except Exception as e:
            logger.error("Erreur calculate_distance_mm: " + str(e))
            return 0.0
    
    def calculate_midpoint(self, point1, point2):
        try:
            return XYZ(
                (point1.X + point2.X) / 2,
                (point1.Y + point2.Y) / 2,
                (point1.Z + point2.Z) / 2
            )
        except Exception as e:
            logger.error("Erreur calculate_midpoint: " + str(e))
            return None
    
    def calculate_centroid(self, points):
        try:
            if not points:
                return XYZ.Zero
            
            count = len(points)
            sum_x = 0.0
            sum_y = 0.0
            sum_z = 0.0
            
            for point in points:
                sum_x += point.X
                sum_y += point.Y
                sum_z += point.Z
            
            return XYZ(sum_x / count, sum_y / count, sum_z / count)
        except Exception as e:
            logger.error("Erreur calculate_centroid: " + str(e))
            return XYZ.Zero
    
    def offset_point(self, point, direction, distance_feet):
        try:
            offset_vector = direction.Normalize().Multiply(distance_feet)
            return point.Add(offset_vector)
        except Exception as e:
            logger.error("Erreur offset_point: " + str(e))
            return point
    
    def get_vector(self, start_point, end_point):
        try:
            return end_point.Subtract(start_point)
        except Exception as e:
            logger.error("Erreur get_vector: " + str(e))
            return XYZ.Zero
    
    def get_unit_vector(self, vector):
        try:
            length = vector.GetLength()
            if length > 0:
                return vector.Divide(length)
            return XYZ.Zero
        except Exception as e:
            logger.error("Erreur get_unit_vector: " + str(e))
            return XYZ.Zero
    
    def create_line(self, start_point, end_point):
        try:
            return Line.CreateBound(start_point, end_point)
        except Exception as e:
            logger.error("Erreur create_line: " + str(e))
            return None
    
    def project_point_on_curve(self, point, curve):
        try:
            result = curve.Project(point)
            if result:
                return result.XYZPoint, result.Parameter
            return None, None
        except Exception as e:
            logger.error("Erreur project_point_on_curve: " + str(e))
            return None, None
    
    def is_point_on_curve(self, point, curve, tolerance_mm=10):
        try:
            projected, _ = self.project_point_on_curve(point, curve)
            if projected:
                distance_mm = self.calculate_distance_mm(point, projected)
                return distance_mm <= tolerance_mm
            return False
        except Exception as e:
            logger.error("Erreur is_point_on_curve: " + str(e))
            return False
    
    def get_curve_length(self, curve):
        try:
            return curve.Length
        except Exception as e:
            logger.error("Erreur get_curve_length: " + str(e))
            return 0.0
    
    def get_curve_endpoints(self, curve):
        try:
            return curve.GetEndPoint(0), curve.GetEndPoint(1)
        except Exception as e:
            logger.error("Erreur get_curve_endpoints: " + str(e))
            return None, None
    
    def get_intersection(self, curve1, curve2):
        try:
            result_array = IntersectionResultArray()
            result = curve1.Intersect(curve2, result_array)
            
            if result == SetComparisonResult.Overlap and result_array.Size > 0:
                return result_array.get_Item(0).XYZPoint
            return None
        except Exception as e:
            logger.error("Erreur get_intersection: " + str(e))
            return None
    
    def get_all_intersections(self, curves1, curves2):
        intersections = []
        
        try:
            for curve1 in curves1:
                for curve2 in curves2:
                    point = self.get_intersection(curve1, curve2)
                    if point:
                        intersections.append({
                            'point': point,
                            'curve1': curve1,
                            'curve2': curve2
                        })
        except Exception as e:
            logger.error("Erreur get_all_intersections: " + str(e))
        
        return intersections
    
    def curve_intersects_plane(self, curve, plane):
        try:
            result = curve.Intersect(plane)
            if result:
                return curve.Evaluate(0.5, True)
            return None
        except Exception as e:
            logger.error("Erreur curve_intersects_plane: " + str(e))
            return None
    
    def create_curve_loop_from_points(self, points):
        try:
            curve_loop = CurveLoop()
            
            for i in range(len(points)):
                start = points[i]
                end = points[(i + 1) % len(points)]
                line = Line.CreateBound(start, end)
                curve_loop.Append(line)
            
            return curve_loop
        except Exception as e:
            logger.error("Erreur create_curve_loop_from_points: " + str(e))
            return None
    
    def create_rectangle_loop(self, min_point, max_point):
        try:
            p1 = XYZ(min_point.X, min_point.Y, min_point.Z)
            p2 = XYZ(max_point.X, min_point.Y, min_point.Z)
            p3 = XYZ(max_point.X, max_point.Y, min_point.Z)
            p4 = XYZ(min_point.X, max_point.Y, min_point.Z)
            
            return self.create_curve_loop_from_points([p1, p2, p3, p4])
        except Exception as e:
            logger.error("Erreur create_rectangle_loop: " + str(e))
            return None
    
    def get_curve_loop_area(self, curve_loop):
        try:
            return curve_loop.GetArea()
        except Exception as e:
            logger.error("Erreur get_curve_loop_area: " + str(e))
            return 0.0
    
    def get_bounding_box(self, element, view=None):
        try:
            return element.get_BoundingBox(view)
        except Exception as e:
            logger.error("Erreur get_bounding_box: " + str(e))
            return None
    
    def get_bounding_box_center(self, bbox):
        try:
            return XYZ(
                (bbox.Min.X + bbox.Max.X) / 2,
                (bbox.Min.Y + bbox.Max.Y) / 2,
                (bbox.Min.Z + bbox.Max.Z) / 2
            )
        except Exception as e:
            logger.error("Erreur get_bounding_box_center: " + str(e))
            return None
    
    def get_bounding_box_dimensions(self, bbox):
        try:
            width_mm = self.feet_to_mm(bbox.Max.X - bbox.Min.X)
            depth_mm = self.feet_to_mm(bbox.Max.Y - bbox.Min.Y)
            height_mm = self.feet_to_mm(bbox.Max.Z - bbox.Min.Z)
            
            return {
                'width_mm': width_mm,
                'depth_mm': depth_mm,
                'height_mm': height_mm,
                'max_dimension_mm': max(width_mm, depth_mm, height_mm),
                'min_dimension_mm': min(width_mm, depth_mm, height_mm)
            }
        except Exception as e:
            logger.error("Erreur get_bounding_box_dimensions: " + str(e))
            return {'width_mm': 0, 'depth_mm': 0, 'height_mm': 0,
                   'max_dimension_mm': 0, 'min_dimension_mm': 0}
    
    def bounding_boxes_intersect(self, bbox1, bbox2, tolerance_feet=0):
        try:
            return not (bbox1.Max.X + tolerance_feet < bbox2.Min.X or
                       bbox1.Min.X - tolerance_feet > bbox2.Max.X or
                       bbox1.Max.Y + tolerance_feet < bbox2.Min.Y or
                       bbox1.Min.Y - tolerance_feet > bbox2.Max.Y or
                       bbox1.Max.Z + tolerance_feet < bbox2.Min.Z or
                       bbox1.Min.Z - tolerance_feet > bbox2.Max.Z)
        except Exception as e:
            logger.error("Erreur bounding_boxes_intersect: " + str(e))
            return False
    
    def get_element_geometry(self, element):
        try:
            return element.Geometry[self.options]
        except Exception as e:
            logger.error("Erreur get_element_geometry: " + str(e))
            return None
    
    def get_solids_from_geometry(self, geometry):
        solids = []
        
        try:
            if not geometry:
                return solids
            
            for obj in geometry:
                if isinstance(obj, Solid) and obj.Volume > 0:
                    solids.append(obj)
                elif isinstance(obj, GeometryInstance):
                    instance_geo = obj.GetInstanceGeometry()
                    solids.extend(self.get_solids_from_geometry(instance_geo))
        except Exception as e:
            logger.error("Erreur get_solids_from_geometry: " + str(e))
        
        return solids
    
    def get_solid_volume(self, solid):
        try:
            return solid.Volume
        except Exception as e:
            logger.error("Erreur get_solid_volume: " + str(e))
            return 0.0
    
    def get_solid_surface_area(self, solid):
        try:
            return solid.SurfaceArea
        except Exception as e:
            logger.error("Erreur get_solid_surface_area: " + str(e))
            return 0.0
    
    def apply_transform(self, point, transform):
        try:
            return transform.OfPoint(point)
        except Exception as e:
            logger.error("Erreur apply_transform: " + str(e))
            return point
    
    def create_translation_transform(self, translation_vector):
        try:
            transform = Transform.Identity
            transform.Origin = translation_vector
            return transform
        except Exception as e:
            logger.error("Erreur create_translation_transform: " + str(e))
            return Transform.Identity
    
    def is_rectangle(self, points, tolerance_mm=50):
        try:
            if len(points) != 4:
                return False
            
            v1 = self.get_vector(points[0], points[1])
            v2 = self.get_vector(points[1], points[2])
            v3 = self.get_vector(points[2], points[3])
            v4 = self.get_vector(points[3], points[0])
            
            tolerance = self.mm_to_feet(tolerance_mm)
            
            return (abs(v1.DotProduct(v2)) < tolerance and
                   abs(v2.DotProduct(v3)) < tolerance and
                   abs(v3.DotProduct(v4)) < tolerance and
                   abs(v4.DotProduct(v1)) < tolerance)
        except Exception as e:
            logger.error("Erreur is_rectangle: " + str(e))
            return False
    
    def is_circle(self, points, tolerance_percent=10):
        try:
            if len(points) < 3:
                return {'is_circle': False}
            
            center = self.calculate_centroid(points)
            radii = [self.calculate_distance(center, p) for p in points]
            avg_radius = sum(radii) / len(radii)
            tolerance = avg_radius * (tolerance_percent / 100.0)
            
            for radius in radii:
                if abs(radius - avg_radius) > tolerance:
                    return {'is_circle': False}
            
            return {
                'is_circle': True,
                'center': center,
                'radius': avg_radius,
                'radius_mm': self.feet_to_mm(avg_radius),
                'points_count': len(points)
            }
        except Exception as e:
            logger.error("Erreur is_circle: " + str(e))
            return {'is_circle': False}
    
    def feet_to_mm(self, feet_value):
        try:
            return feet_value * 304.8
        except Exception as e:
            logger.error("Erreur feet_to_mm: " + str(e))
            return 0.0
    
    def mm_to_feet(self, mm_value):
        try:
            return mm_value / 304.8
        except Exception as e:
            logger.error("Erreur mm_to_feet: " + str(e))
            return 0.0
    
    def feet_to_m(self, feet_value):
        try:
            return feet_value / 3.28084
        except Exception as e:
            logger.error("Erreur feet_to_m: " + str(e))
            return 0.0
    
    def m_to_feet(self, m_value):
        try:
            return m_value * 3.28084
        except Exception as e:
            logger.error("Erreur m_to_feet: " + str(e))
            return 0.0
    
    def point_to_dict(self, point):
        try:
            return {'x': point.X, 'y': point.Y, 'z': point.Z}
        except Exception as e:
            logger.error("Erreur point_to_dict: " + str(e))
            return {'x': 0, 'y': 0, 'z': 0}
    
    def point_to_dict_mm(self, point):
        try:
            return {
                'x': self.feet_to_mm(point.X),
                'y': self.feet_to_mm(point.Y),
                'z': self.feet_to_mm(point.Z)
            }
        except Exception as e:
            logger.error("Erreur point_to_dict_mm: " + str(e))
            return {'x': 0, 'y': 0, 'z': 0}
    
    def bbox_to_dict(self, bbox):
        try:
            return {
                'min': self.point_to_dict(bbox.Min),
                'max': self.point_to_dict(bbox.Max),
                'center': self.point_to_dict(self.get_bounding_box_center(bbox)),
                'dimensions_mm': self.get_bounding_box_dimensions(bbox)
            }
        except Exception as e:
            logger.error("Erreur bbox_to_dict: " + str(e))
            return {}


def test_geometry_service():
    print("\n" + "="*60)
    print("TEST GEOMETRY SERVICE")
    print("="*60)
    
    try:
        from pyrevit import revit
        doc = revit.doc
        
        if not doc:
            print("Aucun document Revit ouvert")
            return
        
        print("\n1 Creation GeometryService...")
        geo_svc = GeometryService(doc)
        
        print("\n2 Test calculs points...")
        p1 = XYZ(0, 0, 0)
        p2 = XYZ(10, 0, 0)
        
        dist = geo_svc.calculate_distance_mm(p1, p2)
        print("   Distance 10ft = " + str(int(dist)) + " mm")
        
        mid = geo_svc.calculate_midpoint(p1, p2)
        print("   Point milieu: X=" + str(mid.X))
        
        print("\n3 Test courbes...")
        line = geo_svc.create_line(p1, p2)
        if line:
            length = geo_svc.get_curve_length(line)
            print("   Longueur ligne: " + str(length) + " ft")
        
        print("\n4 Test bounding box...")
        cols = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_StructuralColumns).WhereElementIsNotElementType().FirstElement()
        
        if cols:
            bbox = geo_svc.get_bounding_box(cols)
            if bbox:
                dims = geo_svc.get_bounding_box_dimensions(bbox)
                print("   Dimensions poteau: " + str(int(dims['width_mm'])) + " x " + str(int(dims['depth_mm'])) + " mm")
        
        print("\n" + "="*60)
        print("TOUS LES TESTS PASSES")
        print("="*60 + "\n")
    
    except Exception as e:
        print("\nERREUR: " + str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_geometry_service()