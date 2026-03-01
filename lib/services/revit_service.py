# -*- coding: utf-8 -*-
"""
RevitService - Service d'interaction avec l'API Revit
======================================================
Responsabilites :
- Collecte d'elements par categorie/type/niveau
- Extraction parametres (built-in et partages)
- Conversion unites (feet <-> mm)
- Helpers geometrie
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
        FilteredElementCollector,
        BuiltInCategory,
        BuiltInParameter,
        Level,
        Grid,
        Wall,
        Floor,
        FamilyInstance,
        ElementId,
        XYZ,
        Line,
        Transaction,
        UnitUtils,
        UnitTypeId
    )
    from Autodesk.Revit.DB.Structure import StructuralType
    REVIT_AVAILABLE = True
except Exception as e:
    REVIT_AVAILABLE = False
    import sys
    sys.stderr.write("revit_service import error: %s\n" % str(e))
    import sys
    sys.stderr.write("revit_service import error: %s\n" % str(e))

class RevitService:
    """
    Service d'interaction avec l'API Revit.
    
    Exemple d'utilisation :
    ----------------------
    >>> from pyrevit import revit
    >>> from services import RevitService
    >>>
    >>> doc = revit.doc
    >>> revit_svc = RevitService(doc)
    >>>
    >>> # Recuperer tous les niveaux
    >>> levels = revit_svc.get_all_levels()
    """

    def __init__(self, document):
        if not REVIT_AVAILABLE:
            raise RevitAPIError("Revit API non disponible")
        
        self.doc = document
        logger.info("RevitService initialise - Doc: " + self.doc.Title)
    
    def get_all_levels(self, sorted_by_elevation=True):
        try:
            collector = FilteredElementCollector(self.doc)
            levels = collector.OfClass(Level).ToElements()
            
            if sorted_by_elevation:
                levels = sorted(levels, key=lambda l: l.Elevation)
            
            logger.info(str(len(levels)) + " niveaux trouves")
            return list(levels)
        
        except Exception as e:
            logger.error("Erreur get_all_levels: " + str(e))
            raise RevitAPIError("Impossible de recuperer niveaux: " + str(e))
    
    def get_level_by_name(self, level_name):
        levels = self.get_all_levels(sorted_by_elevation=False)
        for level in levels:
            if level.Name == level_name:
                return level
        
        logger.warning("Niveau '" + level_name + "' introuvable")
        return None
    
    def get_all_grids(self):
        try:
            collector = FilteredElementCollector(self.doc)
            grids = collector.OfClass(Grid).ToElements()
            
            logger.info(str(len(grids)) + " grilles trouvees")
            return list(grids)
        
        except Exception as e:
            logger.error("Erreur get_all_grids: " + str(e))
            raise RevitAPIError("Impossible de recuperer grilles: " + str(e))
    
    def get_structural_columns(self, level=None):
        try:
            collector = FilteredElementCollector(self.doc)
            
            if level:
                collector = collector.OfCategory(BuiltInCategory.OST_StructuralColumns).WhereElementIsNotElementType()
                
                columns = [elem for elem in collector
                           if isinstance(elem, FamilyInstance)
                           and self._get_element_level(elem) == level]
            else:
                columns = collector.OfCategory(BuiltInCategory.OST_StructuralColumns).WhereElementIsNotElementType().ToElements()
            
            logger.info(str(len(columns)) + " poteaux trouves")
            return list(columns)
        
        except Exception as e:
            logger.error("Erreur get_structural_columns: " + str(e))
            raise RevitAPIError("Impossible de recuperer poteaux: " + str(e))
    
    def get_structural_framing(self, level=None):
        try:
            collector = FilteredElementCollector(self.doc)
            
            if level:
                collector = collector.OfCategory(BuiltInCategory.OST_StructuralFraming).WhereElementIsNotElementType()
                
                beams = [elem for elem in collector
                         if isinstance(elem, FamilyInstance)
                         and self._get_element_level(elem) == level]
            else:
                beams = collector.OfCategory(BuiltInCategory.OST_StructuralFraming).WhereElementIsNotElementType().ToElements()
            
            logger.info(str(len(beams)) + " poutres trouvees")
            return list(beams)
        
        except Exception as e:
            logger.error("Erreur get_structural_framing: " + str(e))
            raise RevitAPIError("Impossible de recuperer poutres: " + str(e))
    
    def get_floors(self, level=None, structural_only=False):
        try:
            collector = FilteredElementCollector(self.doc)
            
            floors = collector.OfCategory(BuiltInCategory.OST_Floors).WhereElementIsNotElementType().ToElements()
            
            if structural_only:
                floors = [f for f in floors if f.get_Parameter(BuiltInParameter.FLOOR_PARAM_IS_STRUCTURAL).AsInteger() == 1]
            
            if level:
                floors = [f for f in floors if self._get_element_level(f) == level]
            
            logger.info(str(len(floors)) + " dalles trouvees")
            return list(floors)
        
        except Exception as e:
            logger.error("Erreur get_floors: " + str(e))
            raise RevitAPIError("Impossible de recuperer dalles: " + str(e))
    
    def get_walls(self, level=None, structural_only=False):
        try:
            collector = FilteredElementCollector(self.doc)
            
            walls = collector.OfCategory(BuiltInCategory.OST_Walls).WhereElementIsNotElementType().ToElements()
            
            if structural_only:
                walls = [w for w in walls if w.get_Parameter(BuiltInParameter.WALL_STRUCTURAL_SIGNIFICANT).AsInteger() == 1]
            
            if level:
                walls = [w for w in walls if self._get_element_level(w) == level]
            
            logger.info(str(len(walls)) + " murs trouves")
            return list(walls)
        
        except Exception as e:
            logger.error("Erreur get_walls: " + str(e))
            raise RevitAPIError("Impossible de recuperer murs: " + str(e))
    
    def get_structural_foundations(self):
        try:
            collector = FilteredElementCollector(self.doc)
            foundations = collector.OfCategory(BuiltInCategory.OST_StructuralFoundation).WhereElementIsNotElementType().ToElements()
            
            logger.info(str(len(foundations)) + " fondations trouvees")
            return list(foundations)
        
        except Exception as e:
            logger.error("Erreur get_structural_foundations: " + str(e))
            raise RevitAPIError("Impossible de recuperer fondations: " + str(e))
    
    def get_parameter_value(self, element, parameter_name, as_string=True):
        try:
            param = element.LookupParameter(parameter_name)
            
            if param is None:
                logger.warning("Parametre '" + parameter_name + "' introuvable")
                return None
            
            if as_string:
                return param.AsValueString()
            else:
                storage_type = param.StorageType
                
                if storage_type == 0:
                    return param.AsString()
                elif storage_type == 1:
                    return param.AsInteger()
                elif storage_type == 2:
                    return param.AsDouble()
                elif storage_type == 3:
                    return param.AsElementId()
                
        except Exception as e:
            logger.error("Erreur get_parameter_value: " + str(e))
            return None
    
    def set_parameter_value(self, element, parameter_name, value):
        try:
            param = element.LookupParameter(parameter_name)
            
            if param is None:
                logger.warning("Parametre '" + parameter_name + "' introuvable")
                return False
            
            if param.IsReadOnly:
                logger.warning("Parametre '" + parameter_name + "' en lecture seule")
                return False
            
            if isinstance(value, str):
                param.Set(value)
            elif isinstance(value, int):
                param.Set(value)
            elif isinstance(value, float):
                param.Set(value)
            elif isinstance(value, ElementId):
                param.Set(value)
            else:
                logger.warning("Type valeur non supporte: " + str(type(value)))
                return False
            
            return True
        
        except Exception as e:
            logger.error("Erreur set_parameter_value: " + str(e))
            return False
    
    def get_builtin_parameter_value(self, element, builtin_param, as_string=True):
        try:
            param = element.get_Parameter(builtin_param)
            
            if param is None:
                return None
            
            if as_string:
                return param.AsValueString()
            else:
                storage_type = param.StorageType
                
                if storage_type == 0:
                    return param.AsString()
                elif storage_type == 1:
                    return param.AsInteger()
                elif storage_type == 2:
                    return param.AsDouble()
                elif storage_type == 3:
                    return param.AsElementId()
        
        except Exception as e:
            logger.error("Erreur get_builtin_parameter_value: " + str(e))
            return None
    
    def feet_to_mm(self, feet_value):
        return feet_value * 304.8
    
    def mm_to_feet(self, mm_value):
        return mm_value / 304.8
    
    def m_to_feet(self, m_value):
        return m_value * 3.28084
    
    def feet_to_m(self, feet_value):
        return feet_value / 3.28084
    
    def get_element_location(self, element):
        try:
            from Autodesk.Revit.DB import LocationPoint, LocationCurve
            
            location = element.Location
            
            if isinstance(location, LocationPoint):
                return location.Point
            elif isinstance(location, LocationCurve):
                return location.Curve
            else:
                logger.warning("Type location non supporte: " + str(type(location)))
                return None
                
        except Exception as e:
            logger.error("Erreur get_element_location: " + str(e))
            return None
    
    def get_bounding_box(self, element, view=None):
        try:
            return element.get_BoundingBox(view)
        except Exception as e:
            logger.error("Erreur get_bounding_box: " + str(e))
            return None
    
    def distance_between_points(self, point1, point2):
        try:
            return point1.DistanceTo(point2)
        except Exception as e:
            logger.error("Erreur distance_between_points: " + str(e))
            return 0
    
    def _get_element_level(self, element):
        try:
            level_id = element.get_Parameter(BuiltInParameter.FAMILY_LEVEL_PARAM)
            if level_id and level_id.AsElementId():
                return self.doc.GetElement(level_id.AsElementId())
            
            level_id = element.get_Parameter(BuiltInParameter.SCHEDULE_LEVEL_PARAM)
            if level_id and level_id.AsElementId():
                return self.doc.GetElement(level_id.AsElementId())
            
            level_id = element.get_Parameter(BuiltInParameter.INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM)
            if level_id and level_id.AsElementId():
                return self.doc.GetElement(level_id.AsElementId())
            
            return None
            
        except Exception as e:
            logger.debug("Impossible de recuperer niveau: " + str(e))
            return None
    
    def get_document_info(self):
        try:
            proj_info = self.doc.ProjectInformation
            return {
                'title': self.doc.Title,
                'path': self.doc.PathName if self.doc.IsWorkshared else None,
                'is_workshared': self.doc.IsWorkshared,
                'is_modified': self.doc.IsModified,
                'revit_version': self.doc.Application.VersionNumber,
                'project_info': {
                    'name': proj_info.Name if proj_info else None,
                    'number': proj_info.Number if proj_info else None,
                    'address': proj_info.Address if proj_info else None,
                }
            }
        except Exception as e:
            logger.error("Erreur get_document_info: " + str(e))
            return {}


def test_revit_service():
    print("\n" + "="*60)
    print("TEST REVIT SERVICE")
    print("="*60)
    
    try:
        from pyrevit import revit
        doc = revit.doc
        
        if not doc:
            print("Aucun document Revit ouvert")
            return
        
        print("\n1 Creation RevitService...")
        revit_svc = RevitService(doc)
        
        print("\n2 Informations document...")
        info = revit_svc.get_document_info()
        print(" Projet: " + info['title'])
        print(" Version Revit: " + info['revit_version'])
        
        print("\n3 Recuperation niveaux...")
        levels = revit_svc.get_all_levels()
        print(" " + str(len(levels)) + " niveaux")
        for level in levels:
            elevation_mm = revit_svc.feet_to_mm(level.Elevation)
            print(" - " + level.Name + ": " + str(int(elevation_mm)) + " mm")
        
        print("\n4 Recuperation grilles...")
        grids = revit_svc.get_all_grids()
        print(" " + str(len(grids)) + " grilles")
        
        print("\n5 Recuperation poteaux...")
        columns = revit_svc.get_structural_columns()
        print(" " + str(len(columns)) + " poteaux")
        
        if columns:
            col = columns[0]
            print(" Exemple poteau:")
            print(" - ID: " + str(col.Id))
            family_name = revit_svc.get_parameter_value(col, 'Family')
            type_name = revit_svc.get_parameter_value(col, 'Type')
            print(" - Famille: " + str(family_name))
            print(" - Type: " + str(type_name))
        
        print("\n6 Recuperation poutres...")
        beams = revit_svc.get_structural_framing()
        print(" " + str(len(beams)) + " poutres")
        
        print("\n7 Recuperation dalles...")
        floors = revit_svc.get_floors(structural_only=True)
        print(" " + str(len(floors)) + " dalles structurelles")
        
        print("\n8 Recuperation murs...")
        walls = revit_svc.get_walls(structural_only=True)
        print(" " + str(len(walls)) + " murs porteurs")
        
        print("\n" + "="*60)
        print("TOUS LES TESTS PASSES")
        print("="*60 + "\n")
    
    except Exception as e:
        print("\nERREUR: " + str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_revit_service()