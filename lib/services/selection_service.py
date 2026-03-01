# -*- coding: utf-8 -*-
"""
SelectionService - Service de selection utilisateur
====================================================
Responsabilites :
- Recuperer la selection courante
- Interaction utilisateur (pick elements, points)
- Filtrage de selection
- Gestion des sets de selection

Auteur : AutoRevit Team
Date : 2025
"""

from utils.logger import get_logger

logger = get_logger(__name__)

# Imports Revit API (avec gestion si hors Revit)
try:
    from Autodesk.Revit.DB import (
        FilteredElementCollector,
        BuiltInCategory,
        BuiltInParameter,
        ElementId,
        Element,
        Reference,
        XYZ,
        SelectionFilterElement,
        ISelectionFilter,
        Document,
        UIDocument
    )
    from Autodesk.Revit.UI import Selection
    REVIT_AVAILABLE = True
except ImportError:
    
    REVIT_AVAILABLE = False
    
    # Classes factices pour mode developpement
    class Reference:
        pass
    
    class XYZ:
        def __init__(self, x=0, y=0, z=0):
            self.x = x
            self.y = y
            self.z = z


# Exception personnalisee
class RevitAPIError(Exception):
    """Exception levee quand Revit API n'est pas disponible"""
    pass


class ElementCategoryFilter:
    """
    Filtre de selection par categorie.
    """
    def __init__(self, allowed_categories):
        self.allowed_categories = allowed_categories
    
    def AllowElement(self, element):
        if element.Category:
            return element.Category.Id.IntegerValue in self.allowed_categories
        return False
    
    def AllowReference(self, ref, point):
        return False


class StructuralElementFilter:
    """
    Filtre pour elements structurels (poteaux, poutres, etc.).
    """
    STRUCTURAL_CATEGORIES = [
        BuiltInCategory.OST_StructuralColumns,
        BuiltInCategory.OST_StructuralFraming,
        BuiltInCategory.OST_StructuralFoundation,
        BuiltInCategory.OST_Walls
    ]
    
    def AllowElement(self, element):
        if element.Category:
            cat_id = element.Category.Id.IntegerValue
            return cat_id in [int(cat) for cat in self.STRUCTURAL_CATEGORIES]
        return False
    
    def AllowReference(self, ref, point):
        return False


class SelectionService:
    """
    Service de selection utilisateur.
    
    Exemple d'utilisation :
    ----------------------
    >>> from pyrevit import revit
    >>> from services import SelectionService
    >>>
    >>> uidoc = revit.uidoc
    >>> sel_svc = SelectionService(uidoc)
    >>>
    >>> # Recuperer elements selectionnes
    >>> elements = sel_svc.get_selected_elements()
    >>>
    >>> # Demander selection utilisateur
    >>> beams = sel_svc.pick_elements("Selectionnez poutres", StructuralElementFilter())
    """

    def __init__(self, uidocument):
        if not REVIT_AVAILABLE:
            raise RevitAPIError("Revit API non disponible")
        
        self.uidoc = uidocument
        self.doc = uidocument.Document
        self.selection = uidocument.Selection
        
        logger.info("SelectionService initialise")
    
    # ========================================================================
    # RECUPERER SELECTION COURANTE
    # ========================================================================
    
    def get_selected_element_ids(self):
        """
        Recupere les IDs des elements selectionnes.
        
        Returns:
            list: Liste des ElementId
        """
        try:
            return list(self.selection.GetElementIds())
        except Exception as e:
            logger.error("Erreur get_selected_element_ids: " + str(e))
            return []
    
    def get_selected_elements(self):
        """
        Recupere les elements selectionnes.
        
        Returns:
            list: Liste des elements
        """
        try:
            element_ids = self.get_selected_element_ids()
            elements = []
            
            for elem_id in element_ids:
                element = self.doc.GetElement(elem_id)
                if element:
                    elements.append(element)
            
            logger.info(str(len(elements)) + " elements selectionnes")
            return elements
        
        except Exception as e:
            logger.error("Erreur get_selected_elements: " + str(e))
            return []
    
    def get_selected_elements_by_category(self, category):
        """
        Recupere les elements selectionnes d'une categorie.
        
        Args:
            category (BuiltInCategory): Categorie
        
        Returns:
            list: Elements de la categorie
        """
        elements = self.get_selected_elements()
        filtered = []
        
        for elem in elements:
            if elem.Category and elem.Category.Id.IntegerValue == int(category):
                filtered.append(elem)
        
        return filtered
    
    def get_selected_element_ids_by_category(self, category):
        """
        Recupere les IDs des elements selectionnes d'une categorie.
        
        Args:
            category (BuiltInCategory): Categorie
        
        Returns:
            list: IDs des elements
        """
        elements = self.get_selected_elements_by_category(category)
        return [elem.Id for elem in elements]
    
    # ========================================================================
    # ACTIONS SUR SELECTION
    # ========================================================================
    
    def set_selection(self, elements_or_ids):
        """
        Definit la selection courante.
        
        Args:
            elements_or_ids (list): Liste d'elements ou ElementId
        
        Returns:
            bool: True si reussi
        """
        try:
            element_ids = []
            
            for item in elements_or_ids:
                if isinstance(item, Element):
                    element_ids.append(item.Id)
                elif isinstance(item, ElementId):
                    element_ids.append(item)
                elif hasattr(item, 'Id'):
                    element_ids.append(item.Id)
            
            self.selection.SetElementIds(element_ids)
            logger.info("Selection mise a jour: " + str(len(element_ids)) + " elements")
            return True
        
        except Exception as e:
            logger.error("Erreur set_selection: " + str(e))
            return False
    
    def add_to_selection(self, elements_or_ids):
        """
        Ajoute des elements a la selection courante.
        
        Args:
            elements_or_ids (list): Elements a ajouter
        
        Returns:
            bool: True si reussi
        """
        try:
            current_ids = set(self.get_selected_element_ids())
            
            for item in elements_or_ids:
                if isinstance(item, Element):
                    current_ids.add(item.Id)
                elif isinstance(item, ElementId):
                    current_ids.add(item)
                elif hasattr(item, 'Id'):
                    current_ids.add(item.Id)
            
            self.selection.SetElementIds(list(current_ids))
            return True
        
        except Exception as e:
            logger.error("Erreur add_to_selection: " + str(e))
            return False
    
    def remove_from_selection(self, elements_or_ids):
        """
        Retire des elements de la selection courante.
        
        Args:
            elements_or_ids (list): Elements a retirer
        
        Returns:
            bool: True si reussi
        """
        try:
            current_ids = set(self.get_selected_element_ids())
            
            for item in elements_or_ids:
                if isinstance(item, Element):
                    current_ids.discard(item.Id)
                elif isinstance(item, ElementId):
                    current_ids.discard(item)
                elif hasattr(item, 'Id'):
                    current_ids.discard(item.Id)
            
            self.selection.SetElementIds(list(current_ids))
            return True
        
        except Exception as e:
            logger.error("Erreur remove_from_selection: " + str(e))
            return False
    
    def clear_selection(self):
        """
        Vide la selection courante.
        
        Returns:
            bool: True si reussi
        """
        try:
            self.selection.SetElementIds([])
            logger.info("Selection videe")
            return True
        except Exception as e:
            logger.error("Erreur clear_selection: " + str(e))
            return False
    
    # ========================================================================
    # INTERACTION UTILISATEUR - PICK ELEMENTS
    # ========================================================================
    
    def pick_elements(self, prompt="Selectionnez des elements", 
                     filter=None, multiselect=True):
        """
        Demande a l'utilisateur de selectionner des elements.
        
        Args:
            prompt (str): Message guide
            filter (ISelectionFilter): Filtre de selection
            multiselect (bool): Selection multiple
        
        Returns:
            list: Elements selectionnes
        """
        try:
            if multiselect:
                refs = self.selection.PickObjects(
                    Selection.ObjectType.Element,
                    filter,
                    prompt
                )
                elements = [self.doc.GetElement(ref.ElementId) for ref in refs]
            else:
                ref = self.selection.PickObject(
                    Selection.ObjectType.Element,
                    filter,
                    prompt
                )
                elements = [self.doc.GetElement(ref.ElementId)]
            
            logger.info(str(len(elements)) + " elements selectionnes par utilisateur")
            return elements
        
        except Exception as e:
            # Annulation utilisateur
            logger.info("Selection annulee par utilisateur")
            return []
    
    def pick_elements_by_category(self, category, prompt=None, multiselect=True):
        """
        Demande selection d'elements d'une categorie specifique.
        
        Args:
            category (BuiltInCategory): Categorie
            prompt (str): Message guide
            multiselect (bool): Selection multiple
        
        Returns:
            list: Elements selectionnes
        """
        if not prompt:
            prompt = "Selectionnez des elements de categorie " + str(category)
        
        filter = ElementCategoryFilter([int(category)])
        return self.pick_elements(prompt, filter, multiselect)
    
    def pick_structural_elements(self, prompt=None, multiselect=True):
        """
        Demande selection d'elements structurels.
        
        Args:
            prompt (str): Message guide
            multiselect (bool): Selection multiple
        
        Returns:
            list: Elements structurels selectionnes
        """
        if not prompt:
            prompt = "Selectionnez des elements structurels"
        
        return self.pick_elements(prompt, StructuralElementFilter(), multiselect)
    
    def pick_columns(self, multiselect=True):
        """
        Demande selection de poteaux.
        
        Args:
            multiselect (bool): Selection multiple
        
        Returns:
            list: Poteaux selectionnes
        """
        return self.pick_elements_by_category(
            BuiltInCategory.OST_StructuralColumns,
            "Selectionnez des poteaux",
            multiselect
        )
    
    def pick_beams(self, multiselect=True):
        """
        Demande selection de poutres.
        
        Args:
            multiselect (bool): Selection multiple
        
        Returns:
            list: Poutres selectionnes
        """
        return self.pick_elements_by_category(
            BuiltInCategory.OST_StructuralFraming,
            "Selectionnez des poutres",
            multiselect
        )
    
    def pick_walls(self, structural_only=True, multiselect=True):
        """
        Demande selection de murs.
        
        Args:
            structural_only (bool): Murs porteurs uniquement
            multiselect (bool): Selection multiple
        
        Returns:
            list: Murs selectionnes
        """
        walls = self.pick_elements_by_category(
            BuiltInCategory.OST_Walls,
            "Selectionnez des murs",
            multiselect
        )
        
        if structural_only:
            # Filtrer murs porteurs
            walls = [w for w in walls 
                    if w.get_Parameter(BuiltInParameter.WALL_STRUCTURAL_SIGNIFICANT)
                    and w.get_Parameter(BuiltInParameter.WALL_STRUCTURAL_SIGNIFICANT).AsInteger() == 1]
        
        return walls
    
    # ========================================================================
    # INTERACTION UTILISATEUR - PICK POINTS
    # ========================================================================
    
    def pick_point(self, prompt="Selectionnez un point"):
        """
        Demande a l'utilisateur de selectionner un point.
        
        Args:
            prompt (str): Message guide
        
        Returns:
            XYZ: Point selectionne ou None
        """
        try:
            ref = self.selection.PickObject(
                Selection.ObjectType.PointOnElement,
                prompt
            )
            return ref.GlobalPoint
        except Exception as e:
            logger.info("Selection point annulee")
            return None
    
    def pick_point_on_face(self, prompt="Selectionnez une face"):
        """
        Demande a l'utilisateur de selectionner un point sur une face.
        
        Args:
            prompt (str): Message guide
        
        Returns:
            tuple: (point, face_reference) ou None
        """
        try:
            ref = self.selection.PickObject(
                Selection.ObjectType.Face,
                prompt
            )
            return ref.GlobalPoint, ref
        except Exception as e:
            logger.info("Selection face annulee")
            return None, None
    
    def pick_points(self, prompt="Selectionnez des points", max_points=None):
        """
        Demande a l'utilisateur de selectionner plusieurs points.
        
        Args:
            prompt (str): Message guide
            max_points (int): Nombre maximum de points
        
        Returns:
            list: Points selectionnes
        """
        points = []
        
        try:
            while True:
                if max_points and len(points) >= max_points:
                    break
                
                ref = self.selection.PickObject(
                    Selection.ObjectType.PointOnElement,
                    prompt + " (ESC pour terminer)"
                )
                points.append(ref.GlobalPoint)
        
        except Exception as e:
            logger.info("Selection terminee: " + str(len(points)) + " points")
        
        return points
    
    def pick_rectangle(self, prompt="Selectionnez deux coins"):
        """
        Demande a l'utilisateur de definir un rectangle.
        
        Args:
            prompt (str): Message guide
        
        Returns:
            tuple: (point1, point2) ou None
        """
        try:
            print(prompt + " - Premier coin")
            p1 = self.pick_point()
            if not p1:
                return None
            
            print(prompt + " - Deuxieme coin")
            p2 = self.pick_point()
            if not p2:
                return None
            
            return p1, p2
        
        except Exception as e:
            logger.error("Erreur pick_rectangle: " + str(e))
            return None
    
    # ========================================================================
    # FILTRES PERSONNALISES
    # ========================================================================
    
    def get_filter_by_category(self, categories):
        """
        Cree un filtre par categories.
        
        Args:
            categories (list): Liste de BuiltInCategory
        
        Returns:
            ElementCategoryFilter: Filtre
        """
        cat_ids = [int(cat) for cat in categories]
        return ElementCategoryFilter(cat_ids)
    
    def get_filter_by_class(self, class_type):
        """
        Cree un filtre par classe.
        
        Args:
            class_type (type): Classe Revit (Wall, Floor, etc.)
        
        Returns:
            ISelectionFilter: Filtre
        """
        class ClassFilter(ISelectionFilter):
            def AllowElement(self, element):
                return isinstance(element, class_type)
            def AllowReference(self, ref, point):
                return False
        
        return ClassFilter()
    
    def get_filter_by_parameter(self, param_name, param_value):
        """
        Cree un filtre par valeur de parametre.
        
        Args:
            param_name (str): Nom du parametre
            param_value: Valeur attendue
        
        Returns:
            ISelectionFilter: Filtre
        """
        class ParameterFilter(ISelectionFilter):
            def __init__(self, svc, param_name, param_value):
                self.svc = svc
                self.param_name = param_name
                self.param_value = param_value
            
            def AllowElement(self, element):
                from services import ParametersService
                param_svc = ParametersService(self.svc.doc)
                value = param_svc.get_parameter_value(element, self.param_name, as_string=False)
                return value == self.param_value
            
            def AllowReference(self, ref, point):
                return False
        
        return ParameterFilter(self, param_name, param_value)
    
    # ========================================================================
    # UTILITAIRES
    # ========================================================================
    
    def get_element_count_in_selection(self):
        """
        Retourne le nombre d'elements selectionnes.
        
        Returns:
            int: Nombre d'elements
        """
        return len(self.get_selected_element_ids())
    
    def has_selection(self):
        """
        Verifie si des elements sont selectionnes.
        
        Returns:
            bool: True si selection non vide
        """
        return self.get_element_count_in_selection() > 0
    
    def get_selection_summary(self):
        """
        Resume de la selection courante.
        
        Returns:
            dict: Resume par categorie
        """
        elements = self.get_selected_elements()
        summary = {}
        
        for elem in elements:
            if elem.Category:
                cat_name = elem.Category.Name
                if cat_name not in summary:
                    summary[cat_name] = 0
                summary[cat_name] += 1
        
        return summary


# ============================================================================
# FONCTION DE TEST
# ============================================================================

def test_selection_service():
    print("\n" + "="*60)
    print("TEST SELECTION SERVICE")
    print("="*60)
    
    try:
        from pyrevit import revit
        uidoc = revit.uidoc
        
        if not uidoc:
            print("Aucun document Revit ouvert")
            return
        
        print("\n1 Creation SelectionService...")
        sel_svc = SelectionService(uidoc)
        
        # Test recuperation selection courante
        print("\n2 Test selection courante...")
        selected = sel_svc.get_selected_elements()
        print("   " + str(len(selected)) + " elements selectionnes")
        
        if selected:
            summary = sel_svc.get_selection_summary()
            print("   Resume:")
            for cat, count in summary.items():
                print("     - " + cat + ": " + str(count))
        
        # Test actions sur selection
        print("\n3 Test actions selection...")
        if not selected:
            # Selectionner premier poteau
            collector = FilteredElementCollector(sel_svc.doc)\
                .OfCategory(BuiltInCategory.OST_StructuralColumns)\
                .WhereElementIsNotElementType()\
                .FirstElement()
            
            if collector:
                sel_svc.set_selection([collector])
                print("   Selection definie: 1 element")
        
        print("\n" + "="*60)
        print("TOUS LES TESTS PASSES")
        print("="*60 + "\n")
    
    except Exception as e:
        print("\nERREUR: " + str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_selection_service()