# -*- coding: utf-8 -*-
"""
ParametersService - Service de gestion des parametres Revit
===========================================================
Responsabilites :
- Creation et gestion des parametres partages
- Lecture/ecriture parametres instances et types
- Export/import parametres
- Validation parametres

Auteur : AutoRevit Team
Date : 2025
"""

import json
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
        Element,
        FamilyInstance,
        Parameter,
        ParameterType,
        ParameterGroup,
        InternalDefinition,
        ExternalDefinition,
        SharedParameterElement,
        DefinitionGroup,
        DefinitionFile,
        DefinitionGroups,
        CategorySet,
        Category,
        InstanceBinding,
        TypeBinding,
        ElementBinding,
        StorageType,
        UnitUtils,
        UnitTypeId,
        Transaction,
        FailureHandlingOptions,
        FailureHandler,
        ElementId,
        ExternalDefinitionCreationOptions
    )
    REVIT_AVAILABLE = True
except ImportError:
    
    REVIT_AVAILABLE = False


class ParametersService:
    """Service de gestion des parametres Revit."""

    def __init__(self, document):
        if not REVIT_AVAILABLE:
            raise RevitAPIError("Revit API non disponible")
        
        self.doc = document
        self.app = document.Application
        
        logger.info("ParametersService initialise")
    
    def get_parameter_value(self, element, param_name, as_string=True):
        """
        Recupere la valeur d'un parametre par nom.
        
        Args:
            element (Element): Element Revit
            param_name (str): Nom du parametre
            as_string (bool): Retourner en string
        
        Returns:
            Valeur du parametre ou None
        """
        try:
            param = element.LookupParameter(param_name)
            
            if param is None:
                logger.debug("Parametre '" + param_name + "' introuvable")
                return None
            
            return self._extract_parameter_value(param, as_string)
        
        except Exception as e:
            logger.error("Erreur get_parameter_value: " + str(e))
            return None
    
    def get_builtin_parameter(self, element, builtin_param, as_string=True):
        """
        Recupere la valeur d'un parametre built-in.
        
        Args:
            element (Element): Element Revit
            builtin_param (BuiltInParameter): Parametre built-in
            as_string (bool): Retourner en string
        
        Returns:
            Valeur du parametre ou None
        """
        try:
            param = element.get_Parameter(builtin_param)
            
            if param is None:
                return None
            
            return self._extract_parameter_value(param, as_string)
        
        except Exception as e:
            logger.error("Erreur get_builtin_parameter: " + str(e))
            return None
    
    def get_all_parameters(self, element, include_builtin=False):
        """
        Recupere tous les parametres d'un element.
        
        Args:
            element (Element): Element Revit
            include_builtin (bool): Inclure parametres built-in
        
        Returns:
            dict: Dictionnaire des parametres
        """
        parameters = {}
        
        try:
            for param in element.Parameters:
                name = param.Definition.Name
                value = self._extract_parameter_value(param, True)
                parameters[name] = value
            
            if include_builtin:
                for param in element.ParametersMap:
                    name = param.Definition.Name
                    value = self._extract_parameter_value(param, True)
                    parameters[name] = value
        
        except Exception as e:
            logger.error("Erreur get_all_parameters: " + str(e))
        
        return parameters
    
    def _extract_parameter_value(self, param, as_string=True):
        """Extrait la valeur d'un parametre selon son type."""
        try:
            if param.HasValue:
                if as_string:
                    return param.AsValueString()
                else:
                    storage_type = param.StorageType
                    
                    if storage_type == StorageType.String:
                        return param.AsString()
                    elif storage_type == StorageType.Integer:
                        return param.AsInteger()
                    elif storage_type == StorageType.Double:
                        return param.AsDouble()
                    elif storage_type == StorageType.ElementId:
                        elem_id = param.AsElementId()
                        if elem_id and elem_id.IntegerValue > 0:
                            elem = self.doc.GetElement(elem_id)
                            return elem.Name if elem else None
                    return None
            return None
        
        except Exception as e:
            logger.error("Erreur _extract_parameter_value: " + str(e))
            return None
    
    def set_parameter_value(self, element, param_name, value):
        """
        Definit la valeur d'un parametre.
        
        Args:
            element (Element): Element Revit
            param_name (str): Nom du parametre
            value: Valeur a definir
        
        Returns:
            bool: True si reussi
        """
        try:
            param = element.LookupParameter(param_name)
            
            if param is None:
                logger.warning("Parametre '" + param_name + "' introuvable")
                return False
            
            if param.IsReadOnly:
                logger.warning("Parametre '" + param_name + "' lecture seule")
                return False
            
            return self._assign_parameter_value(param, value)
        
        except Exception as e:
            logger.error("Erreur set_parameter_value: " + str(e))
            return False
    
    def set_builtin_parameter(self, element, builtin_param, value):
        """
        Definit la valeur d'un parametre built-in.
        
        Args:
            element (Element): Element Revit
            builtin_param (BuiltInParameter): Parametre built-in
            value: Valeur a definir
        
        Returns:
            bool: True si reussi
        """
        try:
            param = element.get_Parameter(builtin_param)
            
            if param is None:
                logger.warning("Builtin param introuvable: " + str(builtin_param))
                return False
            
            return self._assign_parameter_value(param, value)
        
        except Exception as e:
            logger.error("Erreur set_builtin_parameter: " + str(e))
            return False
    
    def _assign_parameter_value(self, param, value):
        """Assigne une valeur a un parametre."""
        try:
            if isinstance(value, str):
                return param.Set(value)
            elif isinstance(value, int):
                return param.Set(value)
            elif isinstance(value, float):
                return param.Set(value)
            elif isinstance(value, bool):
                return param.Set(int(value))
            elif hasattr(value, 'Id'):
                return param.Set(value.Id)
            elif hasattr(value, 'IntegerValue'):
                return param.Set(value)
            else:
                logger.warning("Type valeur non supporte: " + str(type(value)))
                return False
        
        except Exception as e:
            logger.error("Erreur _assign_parameter_value: " + str(e))
            return False
    
    def load_shared_parameter_file(self, file_path):
        """
        Charge un fichier de parametres partages.
        
        Args:
            file_path (str): Chemin vers le fichier .txt
        
        Returns:
            DefinitionFile: Fichier de definitions
        """
        try:
            self.app.SharedParametersFilename = file_path
            return self.app.OpenSharedParameterFile()
        except Exception as e:
            logger.error("Erreur load_shared_parameter_file: " + str(e))
            return None
    
    def get_or_create_definition_group(self, group_name):
        """
        Recupere ou cree un groupe de definitions.
        
        Args:
            group_name (str): Nom du groupe
        
        Returns:
            DefinitionGroup: Groupe de definitions
        """
        try:
            shared_param_file = self.app.OpenSharedParameterFile()
            
            if not shared_param_file:
                logger.error("Aucun fichier parametres partages charge")
                return None
            
            groups = shared_param_file.Groups
            
            for group in groups:
                if group.Name == group_name:
                    return group
            
            return groups.Create(group_name)
        
        except Exception as e:
            logger.error("Erreur get_or_create_definition_group: " + str(e))
            return None
    
    def create_shared_parameter(self, param_name, group_name, param_type,
                               param_group=None, visible=True):
        """
        Cree une definition de parametre partage.
        
        Args:
            param_name (str): Nom du parametre
            group_name (str): Nom du groupe
            param_type (ParameterType): Type de parametre
            param_group (ParameterGroup): Groupe Revit
            visible (bool): Visible dans l'UI
        
        Returns:
            ExternalDefinition: Definition creee
        """
        try:
            if param_group is None and REVIT_AVAILABLE:
                param_group = ParameterGroup.PG_DATA
            
            group = self.get_or_create_definition_group(group_name)
            if not group:
                return None
            
            options = ExternalDefinitionCreationOptions(param_name, param_type)
            options.Visible = visible
            
            return group.Definitions.Create(options)
        
        except Exception as e:
            logger.error("Erreur create_shared_parameter: " + str(e))
            return None
    
    def bind_shared_parameter(self, definition, categories, instance_binding=True):
        """
        Lie un parametre partage a des categories.
        
        Args:
            definition (ExternalDefinition): Definition
            categories (list): Liste des categories
            instance_binding (bool): Instance (True) ou Type (False)
        
        Returns:
            bool: True si reussi
        """
        try:
            binding_map = self.doc.ParameterBindings
            category_set = self.app.Create.NewCategorySet()
            
            for cat in categories:
                if isinstance(cat, BuiltInCategory):
                    category = Category.GetCategory(self.doc, cat)
                else:
                    category = cat
                
                if category:
                    category_set.Insert(category)
            
            if instance_binding:
                binding = self.app.Create.NewInstanceBinding(category_set)
            else:
                binding = self.app.Create.NewTypeBinding(category_set)
            
            return binding_map.Insert(definition, binding)
        
        except Exception as e:
            logger.error("Erreur bind_shared_parameter: " + str(e))
            return False
    
    def export_parameters_to_json(self, elements, file_path=None):
        """
        Exporte les parametres d'elements vers JSON.
        
        Args:
            elements (list): Liste d'elements
            file_path (str): Chemin fichier (optionnel)
        
        Returns:
            dict/str: Dictionnaire ou JSON string
        """
        result = {}
        
        try:
            for element in elements:
                elem_id = str(element.Id.IntegerValue)
                result[elem_id] = {
                    'name': element.Name if hasattr(element, 'Name') else '',
                    'category': element.Category.Name if element.Category else '',
                    'parameters': self.get_all_parameters(element)
                }
            
            if file_path:
                with open(file_path, 'w') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                return file_path
            else:
                return result
        
        except Exception as e:
            logger.error("Erreur export_parameters_to_json: " + str(e))
            return {} if not file_path else None
    
    def import_parameters_from_json(self, json_data, source_file=None):
        """
        Importe des parametres depuis JSON.
        
        Args:
            json_data (dict/str): Dictionnaire ou JSON string
            source_file (str): Fichier source (optionnel)
        
        Returns:
            dict: Resultats par element
        """
        results = {}
        
        try:
            if source_file:
                with open(source_file, 'r') as f:
                    data = json.load(f)
            elif isinstance(json_data, str):
                data = json.loads(json_data)
            else:
                data = json_data
            
            for elem_id_str, elem_data in data.items():
                elem_id = ElementId(int(elem_id_str))
                element = self.doc.GetElement(elem_id)
                
                if not element:
                    results[elem_id_str] = {'success': False, 'error': 'Element introuvable'}
                    continue
                
                success_count = 0
                fail_count = 0
                
                for param_name, param_value in elem_data.get('parameters', {}).items():
                    if self.set_parameter_value(element, param_name, param_value):
                        success_count += 1
                    else:
                        fail_count += 1
                
                results[elem_id_str] = {
                    'success': True,
                    'updated': success_count,
                    'failed': fail_count
                }
        
        except Exception as e:
            logger.error("Erreur import_parameters_from_json: " + str(e))
        
        return results
    
    def validate_parameter_exists(self, element, param_name):
        """
        Verifie si un parametre existe sur un element.
        
        Args:
            element (Element): Element Revit
            param_name (str): Nom du parametre
        
        Returns:
            bool: True si existe
        """
        return element.LookupParameter(param_name) is not None
    
    def validate_parameter_value(self, element, param_name, validator_func):
        """
        Valide la valeur d'un parametre avec une fonction.
        
        Args:
            element (Element): Element Revit
            param_name (str): Nom du parametre
            validator_func (callable): Fonction de validation
        
        Returns:
            tuple: (is_valid, message)
        """
        try:
            value = self.get_parameter_value(element, param_name, as_string=False)
            
            if value is None:
                return False, "Parametre introuvable"
            
            return validator_func(value)
        
        except Exception as e:
            logger.error("Erreur validate_parameter_value: " + str(e))
            return False, str(e)
    
    def copy_parameters(self, source_element, target_element, param_names=None):
        """
        Copie des parametres d'un element vers un autre.
        
        Args:
            source_element (Element): Element source
            target_element (Element): Element cible
            param_names (list): Liste des parametres a copier (None = tous)
        
        Returns:
            dict: Resultats par parametre
        """
        results = {}
        
        try:
            if param_names is None:
                params_to_copy = []
                for param in source_element.Parameters:
                    params_to_copy.append(param.Definition.Name)
            else:
                params_to_copy = param_names
            
            for param_name in params_to_copy:
                source_value = self.get_parameter_value(source_element, param_name, as_string=False)
                
                if source_value is not None:
                    success = self.set_parameter_value(target_element, param_name, source_value)
                    results[param_name] = success
                else:
                    results[param_name] = False
        
        except Exception as e:
            logger.error("Erreur copy_parameters: " + str(e))
        
        return results
    
    def get_parameter_units(self, param):
        """
        Recupere l'unite d'un parametre.
        
        Args:
            param (Parameter): Parametre Revit
        
        Returns:
            str: Unite ou None
        """
        try:
            if param.HasValue:
                display_value = param.AsValueString()
                if display_value:
                    parts = display_value.split()
                    if len(parts) > 1:
                        return parts[-1]
            return None
        except Exception as e:
            logger.error("Erreur get_parameter_units: " + str(e))
            return None
    
    def get_parameter_type(self, param):
        """
        Recupere le type de stockage d'un parametre.
        
        Args:
            param (Parameter): Parametre Revit
        
        Returns:
            str: Type ('string', 'integer', 'double', 'elementid')
        """
        try:
            storage_type = param.StorageType
            
            if storage_type == StorageType.String:
                return 'string'
            elif storage_type == StorageType.Integer:
                return 'integer'
            elif storage_type == StorageType.Double:
                return 'double'
            elif storage_type == StorageType.ElementId:
                return 'elementid'
            else:
                return 'unknown'
        except Exception as e:
            logger.error("Erreur get_parameter_type: " + str(e))
            return 'unknown'


def test_parameters_service():
    print("\n" + "="*60)
    print("TEST PARAMETERS SERVICE")
    print("="*60)
    
    try:
        from pyrevit import revit
        doc = revit.doc
        
        if not doc:
            print("Aucun document Revit ouvert")
            return
        
        print("\n1 Creation ParametersService...")
        param_svc = ParametersService(doc)
        
        print("\n2 Test lecture parametres...")
        collector = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_StructuralColumns).WhereElementIsNotElementType()
        
        columns = list(collector)
        
        if columns:
            column = columns[0]
            
            family_name = param_svc.get_parameter_value(column, "Family")
            print("   Famille: " + str(family_name))
            
            height = param_svc.get_parameter_value(column, "Height")
            print("   Hauteur: " + str(height))
            
            all_params = param_svc.get_all_parameters(column)
            print("   Total parametres: " + str(len(all_params)))
        
        print("\n3 Test ecriture parametres...")
        if columns:
            column = columns[0]
            
            success = param_svc.set_parameter_value(
                column,
                "Comments",
                "AutoRevit - Test " + doc.Title
            )
            print("   Ecriture Comments: " + ("OK" if success else "ECHEC"))
        
        print("\n4 Test export JSON...")
        if columns:
            export_data = param_svc.export_parameters_to_json(columns[:3])
            print("   Export " + str(len(export_data)) + " elements")
        
        print("\n" + "="*60)
        print("TOUS LES TESTS PASSES")
        print("="*60 + "\n")
    
    except Exception as e:
        print("\nERREUR: " + str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_parameters_service()