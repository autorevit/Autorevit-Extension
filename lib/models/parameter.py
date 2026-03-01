# -*- coding: utf-8 -*-
"""
Parameter - Modèles représentant des paramètres et leurs valeurs
=================================================================
Gestion des paramètres techniques (dimensions, charges, etc.)
et de leurs valeurs associées à des contextes (projet, élément).

Classes:
    - Parameter: Définition d'un paramètre
    - ParameterValue: Valeur d'un paramètre dans un contexte

Auteur : AutoRevit Team
Date : 2025
"""

import json
from utils.logger import get_logger

logger = get_logger(__name__)


class Parameter:
    """
    Définition d'un paramètre technique.
    
    Un paramètre est défini par son code, son nom, son type,
    son unité, et éventuellement des valeurs par défaut/contraintes.
    """
    
    # Types de données supportés
    DATA_TYPES = ['float', 'int', 'string', 'boolean', 'choice', 'json']
    
    def __init__(self, data):
        """
        Initialise un paramètre.
        
        Args:
            data (dict): Données du paramètre
                {
                    'code': str,
                    'name': str,
                    'category': str,
                    'data_type': str,
                    'unit': str (optionnel),
                    'default_value': any (optionnel),
                    'min_value': float (optionnel),
                    'max_value': float (optionnel),
                    'choices': list (optionnel),
                    'is_system': bool,
                    'is_calculated': bool,
                    'description': str (optionnel)
                }
        """
        self.code = data.get('code', '')
        self.name = data.get('name', self.code)
        self.category = data.get('category', 'GENERAL')
        
        # Type et validation
        self.data_type = data.get('data_type', 'string')
        if self.data_type not in self.DATA_TYPES:
            logger.warning("Type de donnees inconnu: " + self.data_type)
            self.data_type = 'string'
        
        self.unit = data.get('unit', '')
        self.description = data.get('description', '')
        
        # Contraintes
        self.default_value = data.get('default_value')
        self.min_value = data.get('min_value')
        self.max_value = data.get('max_value')
        self.choices = data.get('choices', [])
        
        # Comportement
        self.is_system = data.get('is_system', False)
        self.is_calculated = data.get('is_calculated', False)
        self.formula = data.get('formula', '')
        
        # Métadonnées
        self.order = data.get('order', 0)
        self.is_active = data.get('is_active', True)
        
        logger.debug("Parameter cree: " + self.code)
    
    def validate_value(self, value):
        """
        Valide une valeur par rapport aux contraintes du paramètre.
        
        Args:
            value: Valeur à valider
        
        Returns:
            tuple: (is_valid, message)
        """
        if value is None:
            return False, "Valeur nulle non autorisee"
        
        # Validation selon le type
        try:
            if self.data_type == 'float':
                val = float(value)
                
                if self.min_value is not None and val < self.min_value:
                    return False, "Valeur minimale: " + str(self.min_value)
                
                if self.max_value is not None and val > self.max_value:
                    return False, "Valeur maximale: " + str(self.max_value)
            
            elif self.data_type == 'int':
                val = int(value)
                
                if self.min_value is not None and val < self.min_value:
                    return False, "Valeur minimale: " + str(int(self.min_value))
                
                if self.max_value is not None and val > self.max_value:
                    return False, "Valeur maximale: " + str(int(self.max_value))
            
            elif self.data_type == 'boolean':
                if value not in (True, False, 0, 1, 'true', 'false'):
                    return False, "Valeur booleenne attendue"
            
            elif self.data_type == 'choice':
                if value not in self.choices:
                    return False, "Valeur doit etre parmi: " + str(self.choices)
            
            elif self.data_type == 'json':
                # Vérifier que c'est du JSON valide
                if isinstance(value, basestring):
                    json.loads(value)
            
        except ValueError as e:
            return False, "Erreur de conversion: " + str(e)
        except Exception as e:
            return False, "Erreur de validation: " + str(e)
        
        return True, "OK"
    
    def convert_value(self, value, target_unit=None):
        """
        Convertit une valeur vers l'unité cible.
        
        Args:
            value: Valeur à convertir
            target_unit (str): Unité cible (None = unité par défaut)
        
        Returns:
            float: Valeur convertie
        """
        # TODO: Implémenter conversions d'unités
        # Pour l'instant, retourne la valeur inchangée
        return value
    
    def format_value(self, value, include_unit=True):
        """
        Formate une valeur pour affichage.
        
        Args:
            value: Valeur à formater
            include_unit (bool): Inclure l'unité
        
        Returns:
            str: Valeur formatée
        """
        if value is None:
            return ""
        
        if self.data_type == 'float':
            try:
                val = float(value)
                formatted = "{:.2f}".format(val).replace('.', ',')
            except:
                formatted = str(value)
        
        elif self.data_type == 'int':
            try:
                val = int(value)
                formatted = str(val)
            except:
                formatted = str(value)
        
        elif self.data_type == 'boolean':
            if value in (True, 1, 'true', 'yes'):
                formatted = "Oui"
            else:
                formatted = "Non"
        
        else:
            formatted = str(value)
        
        if include_unit and self.unit:
            return formatted + " " + self.unit
        
        return formatted
    
    def get_default_value(self):
        """
        Récupère la valeur par défaut.
        
        Returns:
            Valeur par défaut ou None
        """
        return self.default_value
    
    def to_dict(self):
        """
        Convertit le paramètre en dictionnaire.
        
        Returns:
            dict: Représentation dictionnaire
        """
        return {
            'code': self.code,
            'name': self.name,
            'category': self.category,
            'data_type': self.data_type,
            'unit': self.unit,
            'description': self.description,
            'default_value': self.default_value,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'choices': self.choices,
            'is_system': self.is_system,
            'is_calculated': self.is_calculated,
            'is_active': self.is_active
        }
    
    def __str__(self):
        """Représentation string du paramètre."""
        unit_str = " [" + self.unit + "]" if self.unit else ""
        return "[Parameter] " + self.code + " - " + self.name + unit_str


class ParameterValue:
    """
    Valeur d'un paramètre dans un contexte spécifique.
    
    Un contexte peut être un projet, un élément Revit,
    une famille, une vue, etc.
    """
    
    # Types de contextes supportés
    CONTEXT_TYPES = ['project', 'element', 'family', 'view', 'global']
    
    def __init__(self, data, parameter=None):
        """
        Initialise une valeur de paramètre.
        
        Args:
            data (dict): Données de la valeur
                {
                    'parameter_code': str,
                    'parameter': Parameter (optionnel),
                    'context_type': str,
                    'context_id': int,
                    'value': any,
                    'updated_at': str,
                    'updated_by': str
                }
            parameter (Parameter): Instance du paramètre (optionnel)
        """
        self.parameter_code = data.get('parameter_code', '')
        self._parameter = parameter or data.get('parameter')
        
        self.context_type = data.get('context_type', 'global')
        if self.context_type not in self.CONTEXT_TYPES:
            logger.warning("Type de contexte inconnu: " + self.context_type)
            self.context_type = 'global'
        
        self.context_id = data.get('context_id', 0)
        self.value = data.get('value')
        
        self.updated_at = data.get('updated_at', '')
        self.updated_by = data.get('updated_by', '')
        
        logger.debug("ParameterValue creee: " + self.parameter_code)
    
    @property
    def parameter(self):
        """Retourne le paramètre associé."""
        return self._parameter
    
    @parameter.setter
    def parameter(self, param_instance):
        """Définit le paramètre associé."""
        self._parameter = param_instance
    
    def has_parameter(self):
        """Vérifie si le paramètre est chargé."""
        return self._parameter is not None
    
    def get_formatted_value(self, include_unit=True):
        """
        Récupère la valeur formatée.
        
        Args:
            include_unit (bool): Inclure l'unité
        
        Returns:
            str: Valeur formatée
        """
        if self._parameter:
            return self._parameter.format_value(self.value, include_unit)
        
        return str(self.value)
    
    def validate(self):
        """
        Valide la valeur par rapport au paramètre.
        
        Returns:
            tuple: (is_valid, message)
        """
        if not self._parameter:
            return False, "Parametre non charge: " + self.parameter_code
        
        return self._parameter.validate_value(self.value)
    
    def to_dict(self):
        """
        Convertit la valeur en dictionnaire.
        
        Returns:
            dict: Représentation dictionnaire
        """
        return {
            'parameter_code': self.parameter_code,
            'context_type': self.context_type,
            'context_id': self.context_id,
            'value': self.value,
            'updated_at': self.updated_at,
            'updated_by': self.updated_by
        }
    
    def __str__(self):
        """Représentation string de la valeur."""
        param_str = self.parameter_code
        if self._parameter:
            param_str = self._parameter.name
        
        value_str = self.get_formatted_value()
        return "[ParamValue] " + param_str + " = " + value_str