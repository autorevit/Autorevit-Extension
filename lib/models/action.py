# -*- coding: utf-8 -*-
"""
Action - Modèle représentant une action Revit
==============================================
Une action est une opération élémentaire exécutable dans Revit
(création d'élément, modification, suppression, etc.).

Propriétés :
    - code: Identifiant unique (ex: "COLUMN_CREATE")
    - name: Nom affichable (ex: "Créer poteau")
    - category: Catégorie (CREATE, MODIFY, DELETE, EXPORT)
    - parameters: Schéma des paramètres attendus
    - template: Code Python à exécuter
    - requires_transaction: Nécessite une transaction
    - estimated_time: Temps d'exécution estimé (secondes)

Auteur : AutoRevit Team
Date : 2025
"""

from utils.logger import get_logger

logger = get_logger(__name__)


class Action:
    """
    Représentation locale d'une action Revit API.
    
    Exemple:
    >>> data = {
    >>>     'code': 'COLUMN_CREATE',
    >>>     'name': 'Créer poteau',
    >>>     'category': 'CREATE',
    >>>     'parameters': [
    >>>         {'name': 'width', 'type': 'int', 'required': True},
    >>>         {'name': 'height', 'type': 'int', 'required': True}
    >>>     ],
    >>>     'template_code': '...',
    >>>     'requires_transaction': True
    >>> }
    >>> action = Action(data)
    >>> print(action.name)
    """
    
    def __init__(self, data):
        """
        Initialise une action à partir des données API.
        
        Args:
            data (dict): Données de l'action provenant de l'API
                {
                    'code': str,
                    'name': str,
                    'category': str,
                    'description': str (optionnel),
                    'parameters': list (optionnel),
                    'template_code': str (optionnel),
                    'requires_transaction': bool (optionnel),
                    'estimated_time': int (optionnel),
                    'is_active': bool (optionnel),
                    'icon': str (optionnel)
                }
        """
        # Identifiants
        self.code = data.get('code', '')
        self.name = data.get('name', self.code)
        self.category = data.get('category', 'GENERAL')
        self.description = data.get('description', '')
        
        # Paramètres
        self.parameters = data.get('parameters', [])
        self.parameter_schema = self._build_schema(self.parameters)
        
        # Exécution
        self.template = data.get('template_code', '')
        self.requires_transaction = data.get('requires_transaction', True)
        self.estimated_time = data.get('estimated_time', 0)  # secondes
        
        # Métadonnées
        self.is_active = data.get('is_active', True)
        self.icon = data.get('icon', '')
        self.created_at = data.get('created_at', '')
        self.updated_at = data.get('updated_at', '')
        
        # Attributs calculés
        self.parameter_names = [p.get('name') for p in self.parameters if p.get('name')]
        self.required_parameters = [p for p in self.parameters if p.get('required', False)]
        
        logger.debug("Action creee: " + self.code)
    
    def _build_schema(self, parameters):
        """
        Construit un schéma de validation pour les paramètres.
        
        Args:
            parameters (list): Liste des paramètres
        
        Returns:
            dict: Schéma {nom_param: {type, required, default, ...}}
        """
        schema = {}
        
        for param in parameters:
            name = param.get('name')
            if name:
                schema[name] = {
                    'type': param.get('type', 'string'),
                    'required': param.get('required', False),
                    'default': param.get('default'),
                    'min': param.get('min'),
                    'max': param.get('max'),
                    'choices': param.get('choices', []),
                    'description': param.get('description', '')
                }
        
        return schema
    
    def validate_parameters(self, params):
        """
        Valide les paramètres fournis contre le schéma.
        
        Args:
            params (dict): Paramètres à valider
        
        Returns:
            tuple: (is_valid, errors_dict)
        """
        errors = {}
        
        # Vérifier paramètres requis
        for param_name, schema in self.parameter_schema.items():
            if schema['required'] and param_name not in params:
                errors[param_name] = "Parametre requis manquant"
        
        # Valider types et valeurs
        for param_name, value in params.items():
            if param_name in self.parameter_schema:
                schema = self.parameter_schema[param_name]
                
                # Validation du type (simplifiée)
                if schema['type'] == 'int':
                    try:
                        int(value)
                    except (ValueError, TypeError):
                        errors[param_name] = "Doit etre un entier"
                
                elif schema['type'] == 'float':
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errors[param_name] = "Doit etre un nombre"
                
                elif schema['type'] == 'boolean':
                    if value not in (True, False, 0, 1, 'true', 'false'):
                        errors[param_name] = "Doit etre un booleen"
                
                # Validation des bornes
                if 'min' in schema and schema['min'] is not None:
                    try:
                        if float(value) < schema['min']:
                            errors[param_name] = "Valeur minimale: " + str(schema['min'])
                    except:
                        pass
                
                if 'max' in schema and schema['max'] is not None:
                    try:
                        if float(value) > schema['max']:
                            errors[param_name] = "Valeur maximale: " + str(schema['max'])
                    except:
                        pass
                
                # Validation des choix
                if schema['choices'] and value not in schema['choices']:
                    errors[param_name] = "Doit etre parmi: " + str(schema['choices'])
        
        return len(errors) == 0, errors
    
    def get_default_parameters(self):
        """
        Récupère les paramètres par défaut.
        
        Returns:
            dict: Paramètres avec valeurs par défaut
        """
        defaults = {}
        
        for param_name, schema in self.parameter_schema.items():
            if schema['default'] is not None:
                defaults[param_name] = schema['default']
        
        return defaults
    
    def to_dict(self):
        """
        Convertit l'action en dictionnaire.
        
        Returns:
            dict: Représentation dictionnaire
        """
        return {
            'code': self.code,
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'parameters': self.parameters,
            'requires_transaction': self.requires_transaction,
            'estimated_time': self.estimated_time,
            'is_active': self.is_active,
            'icon': self.icon
        }
    
    def __str__(self):
        """Représentation string de l'action."""
        return "[Action] " + self.code + " - " + self.name
    
    def __repr__(self):
        """Représentation détaillée."""
        return "<Action code=" + self.code + " category=" + self.category + ">"