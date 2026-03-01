# -*- coding: utf-8 -*-
"""
RevitHelpers - Fonctions utilitaires pour l'API Revit
======================================================
Fonctions rapides pour operations courantes Revit.

Auteur : AutoRevit Team
Date : 2025
"""

from utils.logger import get_logger

logger = get_logger(__name__)

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
        UnitTypeId,
        LocationPoint,
        LocationCurve,
        BoundingBoxXYZ,
        Document,
        Element,
        View,
        Parameter,
        Family,
        FamilySymbol,
        Options
    )
    from Autodesk.Revit.DB.Structure import StructuralType
    from Autodesk.Revit.UI import TaskDialog, TaskDialogCommonButtons, TaskDialogResult
    REVIT_AVAILABLE = True
except Exception as e:
    REVIT_AVAILABLE = False
    import sys
    sys.stderr.write("revit_helpers import error: %s\n" % str(e))
# ========================================================================
# DOCUMENTS ET APPLICATIONS
# ========================================================================

def get_active_document():
    """
    Recupere le document Revit actif.
    
    Returns:
        Document: Document actif ou None
    """
    if not REVIT_AVAILABLE:
        return None
    
    try:
        from pyrevit import revit
        return revit.doc
    except Exception as e:
        logger.error("Erreur get_active_document: " + str(e))
        return None


def get_revit_version():
    """
    Recupere la version de Revit.
    
    Returns:
        str: Version Revit
    """
    if not REVIT_AVAILABLE:
        return "0.0"
    
    try:
        from pyrevit import HOST_APP
        return HOST_APP.version
    except Exception as e:
        logger.error("Erreur get_revit_version: " + str(e))
        return "0.0"


def get_revit_year():
    """
    Recupere l'annee de version Revit.
    
    Returns:
        int: Annee (2021, 2022, etc.)
    """
    version = get_revit_version()
    try:
        return int(version.split('.')[0])
    except:
        return 0


def is_revit_available():
    """
    Verifie si Revit API est disponible.
    
    Returns:
        bool: True si disponible
    """
    return REVIT_AVAILABLE and get_active_document() is not None


# ========================================================================
# COLLECTE ELEMENTS
# ========================================================================

def get_all_levels(doc=None, sorted_by_elevation=True):
    """
    Recupere tous les niveaux du document.
    
    Args:
        doc: Document Revit (None = document actif)
        sorted_by_elevation: Trier par elevation
    
    Returns:
        list: Niveaux
    """
    if not REVIT_AVAILABLE:
        return []
    
    try:
        if doc is None:
            doc = get_active_document()
            if doc is None:
                return []
        
        collector = FilteredElementCollector(doc)
        levels = collector.OfClass(Level).ToElements()
        
        if sorted_by_elevation:
            levels = sorted(levels, key=lambda l: l.Elevation)
        
        return list(levels)
    except Exception as e:
        logger.error("Erreur get_all_levels: " + str(e))
        return []


def get_level_by_name(level_name, doc=None):
    """
    Recupere un niveau par son nom.
    
    Args:
        level_name (str): Nom du niveau
        doc: Document Revit
    
    Returns:
        Level: Niveau ou None
    """
    levels = get_all_levels(doc, sorted_by_elevation=False)
    for level in levels:
        if level.Name == level_name:
            return level
    return None


def get_all_grids(doc):
    import clr
    from Autodesk.Revit.DB import (
        FilteredElementCollector, Grid,
        RevitLinkInstance, Transform
    )

    grids = []

    # 1. Grilles du document courant
    for g in FilteredElementCollector(doc).OfClass(Grid).ToElements():
        grids.append({'grid': g, 'transform': None})

    # 2. Grilles dans les modeles lies
    links = FilteredElementCollector(doc)\
        .OfClass(RevitLinkInstance).ToElements()

    for link in links:
        try:
            link_doc = link.GetLinkDocument()
            if not link_doc:
                continue
            transform = link.GetTotalTransform()
            for g in FilteredElementCollector(link_doc)\
                    .OfClass(Grid).ToElements():
                grids.append({'grid': g, 'transform': transform})
        except:
            pass

    return grids


def get_all_structural_columns(doc=None, level=None):
    """
    Recupere tous les poteaux structurels.
    
    Args:
        doc: Document Revit
        level: Filtrer par niveau
    
    Returns:
        list: Poteaux
    """
    if not REVIT_AVAILABLE:
        return []
    
    try:
        if doc is None:
            doc = get_active_document()
            if doc is None:
                return []
        
        collector = FilteredElementCollector(doc)
        columns = collector.OfCategory(BuiltInCategory.OST_StructuralColumns) \
                          .WhereElementIsNotElementType() \
                          .ToElements()
        
        if level:
            columns = [c for c in columns if get_element_level(c) == level]
        
        return list(columns)
    except Exception as e:
        logger.error("Erreur get_all_structural_columns: " + str(e))
        return []


get_all_columns = get_all_structural_columns


def get_all_structural_framing(doc=None, level=None):
    """
    Recupere toutes les poutres structurelles.
    
    Args:
        doc: Document Revit
        level: Filtrer par niveau
    
    Returns:
        list: Poutres
    """
    if not REVIT_AVAILABLE:
        return []
    
    try:
        if doc is None:
            doc = get_active_document()
            if doc is None:
                return []
        
        collector = FilteredElementCollector(doc)
        beams = collector.OfCategory(BuiltInCategory.OST_StructuralFraming) \
                        .WhereElementIsNotElementType() \
                        .ToElements()
        
        if level:
            beams = [b for b in beams if get_element_level(b) == level]
        
        return list(beams)
    except Exception as e:
        logger.error("Erreur get_all_structural_framing: " + str(e))
        return []


get_all_beams = get_all_structural_framing


def get_all_walls(doc=None, structural_only=False, level=None):
    """
    Recupere tous les murs.
    
    Args:
        doc: Document Revit
        structural_only: Murs porteurs uniquement
        level: Filtrer par niveau
    
    Returns:
        list: Murs
    """
    if not REVIT_AVAILABLE:
        return []
    
    try:
        if doc is None:
            doc = get_active_document()
            if doc is None:
                return []
        
        collector = FilteredElementCollector(doc)
        walls = collector.OfCategory(BuiltInCategory.OST_Walls) \
                        .WhereElementIsNotElementType() \
                        .ToElements()
        
        if structural_only:
            walls = [w for w in walls 
                    if w.get_Parameter(BuiltInParameter.WALL_STRUCTURAL_SIGNIFICANT)
                    and w.get_Parameter(BuiltInParameter.WALL_STRUCTURAL_SIGNIFICANT).AsInteger() == 1]
        
        if level:
            walls = [w for w in walls if get_element_level(w) == level]
        
        return list(walls)
    except Exception as e:
        logger.error("Erreur get_all_walls: " + str(e))
        return []


def get_all_floors(doc=None, structural_only=False, level=None):
    """
    Recupere toutes les dalles.
    
    Args:
        doc: Document Revit
        structural_only: Dalles structurelles uniquement
        level: Filtrer par niveau
    
    Returns:
        list: Dalles
    """
    if not REVIT_AVAILABLE:
        return []
    
    try:
        if doc is None:
            doc = get_active_document()
            if doc is None:
                return []
        
        collector = FilteredElementCollector(doc)
        floors = collector.OfCategory(BuiltInCategory.OST_Floors) \
                         .WhereElementIsNotElementType() \
                         .ToElements()
        
        if structural_only:
            floors = [f for f in floors 
                     if f.get_Parameter(BuiltInParameter.FLOOR_PARAM_IS_STRUCTURAL)
                     and f.get_Parameter(BuiltInParameter.FLOOR_PARAM_IS_STRUCTURAL).AsInteger() == 1]
        
        if level:
            floors = [f for f in floors if get_element_level(f) == level]
        
        return list(floors)
    except Exception as e:
        logger.error("Erreur get_all_floors: " + str(e))
        return []


def get_all_doors(doc=None, level=None):
    """
    Recupere toutes les portes.
    
    Args:
        doc: Document Revit
        level: Filtrer par niveau
    
    Returns:
        list: Portes
    """
    if not REVIT_AVAILABLE:
        return []
    
    try:
        if doc is None:
            doc = get_active_document()
            if doc is None:
                return []
        
        collector = FilteredElementCollector(doc)
        doors = collector.OfCategory(BuiltInCategory.OST_Doors) \
                        .WhereElementIsNotElementType() \
                        .ToElements()
        
        if level:
            doors = [d for d in doors if get_element_level(d) == level]
        
        return list(doors)
    except Exception as e:
        logger.error("Erreur get_all_doors: " + str(e))
        return []


def get_all_windows(doc=None, level=None):
    """
    Recupere toutes les fenetres.
    
    Args:
        doc: Document Revit
        level: Filtrer par niveau
    
    Returns:
        list: Fenetres
    """
    if not REVIT_AVAILABLE:
        return []
    
    try:
        if doc is None:
            doc = get_active_document()
            if doc is None:
                return []
        
        collector = FilteredElementCollector(doc)
        windows = collector.OfCategory(BuiltInCategory.OST_Windows) \
                          .WhereElementIsNotElementType() \
                          .ToElements()
        
        if level:
            windows = [w for w in windows if get_element_level(w) == level]
        
        return list(windows)
    except Exception as e:
        logger.error("Erreur get_all_windows: " + str(e))
        return []


def get_all_foundations(doc=None):
    """
    Recupere toutes les fondations.
    
    Args:
        doc: Document Revit
    
    Returns:
        list: Fondations
    """
    if not REVIT_AVAILABLE:
        return []
    
    try:
        if doc is None:
            doc = get_active_document()
            if doc is None:
                return []
        
        collector = FilteredElementCollector(doc)
        foundations = collector.OfCategory(BuiltInCategory.OST_StructuralFoundation) \
                              .WhereElementIsNotElementType() \
                              .ToElements()
        
        return list(foundations)
    except Exception as e:
        logger.error("Erreur get_all_foundations: " + str(e))
        return []


# ========================================================================
# FILTRES PAR NIVEAU
# ========================================================================

def get_elements_by_level(elements, level):
    """
    Filtre les elements par niveau.
    
    Args:
        elements (list): Liste d'elements
        level (Level): Niveau
    
    Returns:
        list: Elements du niveau
    """
    return [e for e in elements if get_element_level(e) == level]


def get_columns_by_level(level, doc=None):
    """
    Recupere les poteaux d'un niveau.
    
    Args:
        level (Level): Niveau
        doc: Document Revit
    
    Returns:
        list: Poteaux du niveau
    """
    return get_all_structural_columns(doc, level)


def get_beams_by_level(level, doc=None):
    """
    Recupere les poutres d'un niveau.
    
    Args:
        level (Level): Niveau
        doc: Document Revit
    
    Returns:
        list: Poutres du niveau
    """
    return get_all_structural_framing(doc, level)


def get_walls_by_level(level, structural_only=True, doc=None):
    """
    Recupere les murs d'un niveau.
    
    Args:
        level (Level): Niveau
        structural_only: Murs porteurs uniquement
        doc: Document Revit
    
    Returns:
        list: Murs du niveau
    """
    return get_all_walls(doc, structural_only, level)


# ========================================================================
# PARAMETRES
# ========================================================================

def get_parameter_value(element, param_name, as_string=True):
    """
    Recupere la valeur d'un parametre.
    
    Args:
        element (Element): Element Revit
        param_name (str): Nom du parametre
        as_string (bool): Retourner en string
    
    Returns:
        Valeur du parametre
    """
    if not REVIT_AVAILABLE or not element:
        return None
    
    try:
        param = element.LookupParameter(param_name)
        
        if param is None:
            return None
        
        if as_string:
            return param.AsValueString()
        else:
            storage_type = param.StorageType
            
            if storage_type == 0:  # String
                return param.AsString()
            elif storage_type == 1:  # Integer
                return param.AsInteger()
            elif storage_type == 2:  # Double
                return param.AsDouble()
            elif storage_type == 3:  # ElementId
                elem_id = param.AsElementId()
                if elem_id and elem_id.IntegerValue > 0:
                    elem = element.Document.GetElement(elem_id)
                    return elem.Name if elem else None
            return None
    except Exception as e:
        logger.error("Erreur get_parameter_value: " + str(e))
        return None


def set_parameter_value(element, param_name, value):
    """
    Definit la valeur d'un parametre.
    
    Args:
        element (Element): Element Revit
        param_name (str): Nom du parametre
        value: Valeur a definir
    
    Returns:
        bool: True si reussi
    """
    if not REVIT_AVAILABLE or not element:
        return False
    
    try:
        param = element.LookupParameter(param_name)
        
        if param is None:
            logger.warning("Parametre '" + param_name + "' introuvable")
            return False
        
        if param.IsReadOnly:
            logger.warning("Parametre '" + param_name + "' lecture seule")
            return False
        
        if isinstance(value, basestring):
            return param.Set(value)
        elif isinstance(value, (int, long)):
            return param.Set(value)
        elif isinstance(value, float):
            return param.Set(value)
        elif isinstance(value, bool):
            return param.Set(int(value))
        elif hasattr(value, 'Id'):
            return param.Set(value.Id)
        else:
            logger.warning("Type valeur non supporte: " + str(type(value)))
            return False
    except Exception as e:
        logger.error("Erreur set_parameter_value: " + str(e))
        return False


def has_parameter(element, param_name):
    """
    Verifie si un parametre existe.
    
    Args:
        element (Element): Element Revit
        param_name (str): Nom du parametre
    
    Returns:
        bool: True si parametre existe
    """
    if not REVIT_AVAILABLE or not element:
        return False
    
    try:
        return element.LookupParameter(param_name) is not None
    except:
        return False


# ========================================================================
# UNITES
# ========================================================================

def mm_to_feet(mm_value):
    """Convertit millimetres en feet."""
    try:
        return mm_value / 304.8
    except:
        return 0.0


def feet_to_mm(feet_value):
    """Convertit feet en millimetres."""
    try:
        return feet_value * 304.8
    except:
        return 0.0


def m_to_feet(m_value):
    """Convertit metres en feet."""
    try:
        return m_value * 3.28084
    except:
        return 0.0


def feet_to_m(feet_value):
    """Convertit feet en metres."""
    try:
        return feet_value / 3.28084
    except:
        return 0.0


def cm_to_feet(cm_value):
    """Convertit centimetres en feet."""
    try:
        return cm_value / 30.48
    except:
        return 0.0


def feet_to_cm(feet_value):
    """Convertit feet en centimetres."""
    try:
        return feet_value * 30.48
    except:
        return 0.0


# ========================================================================
# GEOMETRIE
# ========================================================================

def get_element_location_point(element):
    """
    Recupere la localisation d'un element (point).
    
    Args:
        element (Element): Element Revit
    
    Returns:
        XYZ: Point de localisation ou None
    """
    if not REVIT_AVAILABLE or not element:
        return None
    
    try:
        location = element.Location
        if isinstance(location, LocationPoint):
            return location.Point
        return None
    except Exception as e:
        logger.error("Erreur get_element_location_point: " + str(e))
        return None


def get_element_location_curve(element):
    """
    Recupere la localisation d'un element (courbe).
    
    Args:
        element (Element): Element Revit
    
    Returns:
        Curve: Courbe de localisation ou None
    """
    if not REVIT_AVAILABLE or not element:
        return None
    
    try:
        location = element.Location
        if isinstance(location, LocationCurve):
            return location.Curve
        return None
    except Exception as e:
        logger.error("Erreur get_element_location_curve: " + str(e))
        return None


def get_element_location(element):
    """
    Recupere la localisation d'un element (point ou courbe).
    
    Args:
        element (Element): Element Revit
    
    Returns:
        XYZ/Curve: Localisation ou None
    """
    point = get_element_location_point(element)
    if point:
        return point
    
    return get_element_location_curve(element)


def get_bounding_box(element, view=None):
    """
    Recupere la bounding box d'un element.
    
    Args:
        element (Element): Element Revit
        view (View): Vue optionnelle
    
    Returns:
        BoundingBoxXYZ: Bounding box
    """
    if not REVIT_AVAILABLE or not element:
        return None
    
    try:
        return element.get_BoundingBox(view)
    except Exception as e:
        logger.error("Erreur get_bounding_box: " + str(e))
        return None


def get_bounding_box_center(bbox):
    """
    Calcule le centre d'une bounding box.
    
    Args:
        bbox (BoundingBoxXYZ): Bounding box
    
    Returns:
        XYZ: Centre
    """
    if not bbox:
        return None
    
    try:
        return XYZ(
            (bbox.Min.X + bbox.Max.X) / 2,
            (bbox.Min.Y + bbox.Max.Y) / 2,
            (bbox.Min.Z + bbox.Max.Z) / 2
        )
    except Exception as e:
        logger.error("Erreur get_bounding_box_center: " + str(e))
        return None


def get_bounding_box_dimensions(bbox):
    """
    Calcule les dimensions d'une bounding box.
    
    Args:
        bbox (BoundingBoxXYZ): Bounding box
    
    Returns:
        dict: Dimensions en mm
    """
    if not bbox:
        return {'width_mm': 0, 'depth_mm': 0, 'height_mm': 0}
    
    try:
        width_mm = feet_to_mm(bbox.Max.X - bbox.Min.X)
        depth_mm = feet_to_mm(bbox.Max.Y - bbox.Min.Y)
        height_mm = feet_to_mm(bbox.Max.Z - bbox.Min.Z)
        
        return {
            'width_mm': width_mm,
            'depth_mm': depth_mm,
            'height_mm': height_mm
        }
    except Exception as e:
        logger.error("Erreur get_bounding_box_dimensions: " + str(e))
        return {'width_mm': 0, 'depth_mm': 0, 'height_mm': 0}


# ========================================================================
# TRANSACTIONS
# ========================================================================

class TransactionContext:
    """Context manager pour transactions Revit."""
    
    def __init__(self, doc, name="AutoRevit Operation"):
        self.doc = doc
        self.name = name
        self.transaction = None
    
    def __enter__(self):
        if REVIT_AVAILABLE and self.doc:
            self.transaction = Transaction(self.doc, self.name)
            self.transaction.Start()
        return self.transaction
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.transaction and self.transaction.HasStarted():
            if exc_type is None:
                self.transaction.Commit()
            else:
                self.transaction.RollBack()
        return False


def with_transaction(name=None):
    """
    Decorateur pour executer une fonction dans une transaction.
    
    Args:
        name (str): Nom de la transaction
    
    Returns:
        function: Fonction decoree
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            doc = None
            
            # Chercher document dans arguments
            for arg in args:
                if hasattr(arg, 'Document'):
                    doc = arg.Document
                    break
                elif hasattr(arg, 'doc'):
                    doc = arg.doc
                    break
            
            if not doc:
                doc = get_active_document()
            
            if not doc:
                return func(*args, **kwargs)
            
            tx_name = name or func.__name__
            
            with TransactionContext(doc, tx_name):
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# ========================================================================
# UI
# ========================================================================

def show_message_box(message, title="AutoRevit", icon="Information"):
    """
    Affiche une boite de message simple.
    
    Args:
        message (str): Message
        title (str): Titre
        icon (str): Icone (Information, Warning, Error)
    
    Returns:
        int: Resultat
    """
    if not REVIT_AVAILABLE:
        print(title + ": " + message)
        return 1
    
    try:
        from pyrevit import forms
        if icon == "Error":
            forms.alert(message, title=title, warn_icon=True)
        elif icon == "Warning":
            forms.alert(message, title=title, warn_icon=True)
        else:
            forms.alert(message, title=title, warn_icon=False)
        return 1
    except:
        try:
            from Autodesk.Revit.UI import TaskDialog
            
            td = TaskDialog(title)
            td.MainContent = message
            td.MainInstruction = title
            
            if icon == "Error":
                td.MainIcon = TaskDialog.TaskDialogIcon.TD_ICON_ERROR
            elif icon == "Warning":
                td.MainIcon = TaskDialog.TaskDialogIcon.TD_ICON_WARNING
            else:
                td.MainIcon = TaskDialog.TaskDialogIcon.TD_ICON_INFORMATION
            
            return td.Show()
        except:
            print(title + ": " + message)
            return 1


def show_task_dialog(title, message, buttons=None):
    """
    Affiche une boite de dialogue avec choix.
    
    Args:
        title (str): Titre
        message (str): Message
        buttons (list): Boutons ['Yes', 'No', 'Cancel', 'Retry', etc.]
    
    Returns:
        str: Bouton clique
    """
    if not REVIT_AVAILABLE:
        print(title + ": " + message)
        return "Yes"
    
    try:
        from pyrevit import forms
        
        if buttons:
            return forms.alert(message, title=title, yes=True, no=True)
        else:
            forms.alert(message, title=title)
            return "OK"
    except:
        try:
            from Autodesk.Revit.UI import TaskDialog, TaskDialogCommonButtons
            
            td = TaskDialog(title)
            td.MainInstruction = title
            td.MainContent = message
            
            if buttons:
                btn_flags = 0
                for btn in buttons:
                    if btn == 'Yes':
                        btn_flags |= TaskDialogCommonButtons.Yes
                    elif btn == 'No':
                        btn_flags |= TaskDialogCommonButtons.No
                    elif btn == 'Cancel':
                        btn_flags |= TaskDialogCommonButtons.Cancel
                    elif btn == 'Retry':
                        btn_flags |= TaskDialogCommonButtons.Retry
                    elif btn == 'Close':
                        btn_flags |= TaskDialogCommonButtons.Close
                
                td.CommonButtons = btn_flags
                result = td.Show()
                
                if result == TaskDialogResult.Yes:
                    return 'Yes'
                elif result == TaskDialogResult.No:
                    return 'No'
                elif result == TaskDialogResult.Cancel:
                    return 'Cancel'
                elif result == TaskDialogResult.Retry:
                    return 'Retry'
                else:
                    return 'Close'
            else:
                td.Show()
                return 'OK'
        except:
            print(title + ": " + message)
            return 'Yes'


def get_selected_elements(doc=None):
    """
    Recupere les elements selectionnes.
    
    Args:
        doc: Document Revit
    
    Returns:
        list: Elements selectionnes
    """
    if not REVIT_AVAILABLE:
        return []
    
    try:
        from pyrevit import revit
        uidoc = revit.uidoc
        
        if not uidoc:
            return []
        
        selection = uidoc.Selection
        element_ids = selection.GetElementIds()
        
        if doc is None:
            doc = uidoc.Document
        
        elements = [doc.GetElement(eid) for eid in element_ids]
        return [e for e in elements if e is not None]
    except Exception as e:
        logger.error("Erreur get_selected_elements: " + str(e))
        return []


# ========================================================================
# DIVERS
# ========================================================================

def get_element_level(element):
    """
    Recupere le niveau d'un element.
    
    Args:
        element (Element): Element Revit
    
    Returns:
        Level: Niveau ou None
    """
    if not REVIT_AVAILABLE or not element:
        return None
    
    try:
        # Parametre FAMILY_LEVEL_PARAM
        level_id = element.get_Parameter(BuiltInParameter.FAMILY_LEVEL_PARAM)
        if level_id and level_id.AsElementId():
            return element.Document.GetElement(level_id.AsElementId())
        
        # Parametre SCHEDULE_LEVEL_PARAM
        level_id = element.get_Parameter(BuiltInParameter.SCHEDULE_LEVEL_PARAM)
        if level_id and level_id.AsElementId():
            return element.Document.GetElement(level_id.AsElementId())
        
        # Parametre INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM
        level_id = element.get_Parameter(BuiltInParameter.INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM)
        if level_id and level_id.AsElementId():
            return element.Document.GetElement(level_id.AsElementId())
        
        return None
    except Exception as e:
        logger.debug("Impossible de recuperer niveau: " + str(e))
        return None


def get_document_info(doc=None):
    """
    Recupere les informations du document.
    
    Args:
        doc: Document Revit
    
    Returns:
        dict: Informations
    """
    if not REVIT_AVAILABLE:
        return {}
    
    try:
        if doc is None:
            doc = get_active_document()
            if doc is None:
                return {}
        
        proj_info = doc.ProjectInformation
        
        return {
            'title': doc.Title,
            'path': doc.PathName,
            'is_workshared': doc.IsWorkshared,
            'is_modified': doc.IsModified,
            'project_name': proj_info.Name if proj_info else None,
            'project_number': proj_info.Number if proj_info else None,
            'project_address': proj_info.Address if proj_info else None
        }
    except Exception as e:
        logger.error("Erreur get_document_info: " + str(e))
        return {}


def get_project_info(doc=None):
    """
    Recupere les informations du projet.
    
    Args:
        doc: Document Revit
    
    Returns:
        dict: Informations projet
    """
    info = get_document_info(doc)
    return {
        'name': info.get('project_name', ''),
        'number': info.get('project_number', ''),
        'address': info.get('project_address', '')
    }


def get_username():
    """
    Recupere le nom d'utilisateur Revit.
    
    Returns:
        str: Nom utilisateur
    """
    if not REVIT_AVAILABLE:
        return ''
    
    try:
        from pyrevit import revit
        app = revit.app
        return app.Username
    except:
        try:
            import os
            return os.environ.get('USERNAME', '')
        except:
            return ''


# ========================================================================
# FONCTION DE TEST
# ========================================================================

def test_revit_helpers():
    print("\n" + "="*60)
    print("TEST REVIT HELPERS")
    print("="*60)
    
    if not is_revit_available():
        print("\n❌ Revit non disponible")
        return
    
    print("\n✅ Revit disponible")
    print("   Version: " + get_revit_version())
    print("   Annee: " + str(get_revit_year()))
    
    print("\n1 Niveaux:")
    levels = get_all_levels()
    print("   " + str(len(levels)) + " niveaux")
    
    print("\n2 Grilles:")
    grids = get_all_grids()
    print("   " + str(len(grids)) + " grilles")
    
    print("\n3 Poteaux:")
    columns = get_all_columns()
    print("   " + str(len(columns)) + " poteaux")
    
    print("\n4 Poutres:")
    beams = get_all_beams()
    print("   " + str(len(beams)) + " poutres")
    
    print("\n5 Murs porteurs:")
    walls = get_all_walls(structural_only=True)
    print("   " + str(len(walls)) + " murs")
    
    print("\n6 Dalles structurelles:")
    floors = get_all_floors(structural_only=True)
    print("   " + str(len(floors)) + " dalles")
    
    print("\n" + "="*60)
    print("TEST TERMINE")
    print("="*60 + "\n")


if __name__ == '__main__':
    test_revit_helpers()