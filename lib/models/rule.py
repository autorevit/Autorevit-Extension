# -*- coding: utf-8 -*-
"""
Rule - Modèles représentant des règles métier
==============================================
Moteur de règles conditionnelles (IF/THEN/ELSE) pour
automatiser les vérifications et décisions.

Classes:
    - RuleCondition: Condition logique
    - Rule: Règle avec condition et actions
    - RuleSet: Ensemble de règles groupées

Auteur : AutoRevit Team
Date : 2025
"""

import copy
import json
from utils.logger import get_logger

logger = get_logger(__name__)


class RuleCondition:
    """
    Condition logique pour une règle.
    
    Supporte les opérateurs:
        - Comparaison: eq, ne, gt, lt, ge, le
        - Logiques: and, or, not
        - Appartenance: in, not_in
        - Null: is_null, is_not_null
    """
    
    # Opérateurs supportés
    OPERATORS = [
        'eq', 'ne', 'gt', 'lt', 'ge', 'le',
        'and', 'or', 'not',
        'in', 'not_in',
        'is_null', 'is_not_null'
    ]
    
    def __init__(self, data=None):
        """
        Initialise une condition.
        
        Args:
            data (dict): Définition de la condition
                {
                    'operator': str,
                    'field': str (optionnel),
                    'value': any (optionnel),
                    'conditions': list (pour and/or/not)
                }
        """
        self.operator = data.get('operator', 'eq') if data else 'eq'
        
        if self.operator not in self.OPERATORS:
            logger.warning("Operateur inconnu: " + self.operator)
            self.operator = 'eq'
        
        self.field = data.get('field') if data else None
        self.value = data.get('value') if data else None
        
        # Pour les opérateurs logiques
        self.conditions = []
        if data and 'conditions' in data:
            for cond_data in data['conditions']:
                self.conditions.append(RuleCondition(cond_data))
        
        self.raw_data = copy.deepcopy(data) if data else {}
    
    def evaluate(self, context):
        """
        Évalue la condition dans un contexte donné.
        
        Args:
            context (dict): Contexte d'évaluation (valeurs des champs)
        
        Returns:
            bool: Résultat de l'évaluation
        """
        try:
            # Opérateurs logiques
            if self.operator == 'and':
                return all(c.evaluate(context) for c in self.conditions)
            
            elif self.operator == 'or':
                return any(c.evaluate(context) for c in self.conditions)
            
            elif self.operator == 'not':
                return not self.conditions[0].evaluate(context) if self.conditions else False
            
            # Opérateurs de comparaison
            if self.field is None:
                return False
            
            # Récupérer la valeur du champ dans le contexte
            field_value = self._get_field_value(context, self.field)
            
            if self.operator == 'eq':
                return field_value == self.value
            
            elif self.operator == 'ne':
                return field_value != self.value
            
            elif self.operator == 'gt':
                return float(field_value) > float(self.value)
            
            elif self.operator == 'lt':
                return float(field_value) < float(self.value)
            
            elif self.operator == 'ge':
                return float(field_value) >= float(self.value)
            
            elif self.operator == 'le':
                return float(field_value) <= float(self.value)
            
            elif self.operator == 'in':
                return field_value in self.value
            
            elif self.operator == 'not_in':
                return field_value not in self.value
            
            elif self.operator == 'is_null':
                return field_value is None
            
            elif self.operator == 'is_not_null':
                return field_value is not None
            
        except Exception as e:
            logger.error("Erreur evaluation condition: " + str(e))
        
        return False
    
    def _get_field_value(self, context, field_path):
        """
        Récupère la valeur d'un champ dans le contexte.
        
        Args:
            context (dict): Contexte
            field_path (str): Chemin du champ (ex: "element.width")
        
        Returns:
            Valeur du champ ou None
        """
        parts = field_path.split('.')
        value = context
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
        
        return value
    
    def to_dict(self):
        """
        Convertit la condition en dictionnaire.
        
        Returns:
            dict: Représentation dictionnaire
        """
        if self.conditions:
            return {
                'operator': self.operator,
                'conditions': [c.to_dict() for c in self.conditions]
            }
        else:
            return {
                'operator': self.operator,
                'field': self.field,
                'value': self.value
            }
    
    def __str__(self):
        """Représentation string de la condition."""
        if self.conditions:
            op_str = self.operator.upper()
            conds_str = ", ".join(str(c) for c in self.conditions)
            return "(" + op_str + " " + conds_str + ")"
        else:
            return self.field + " " + self.operator + " " + str(self.value)


class Rule:
    """
    Règle métier conditionnelle.
    
    Structure: SI condition ALORS actions_si_vrai SINON actions_si_faux
    """
    
    # Niveaux de sévérité
    SEVERITY_LEVELS = ['info', 'warning', 'error', 'critical']
    
    def __init__(self, data):
        """
        Initialise une règle.
        
        Args:
            data (dict): Données de la règle
                {
                    'code': str,
                    'name': str,
                    'category': str,
                    'condition': dict,
                    'actions_if_true': list,
                    'actions_if_false': list,
                    'is_active': bool,
                    'severity': str,
                    'message': str,
                    'order': int
                }
        """
        self.code = data.get('code', '')
        self.name = data.get('name', self.code)
        self.category = data.get('category', 'GENERAL')
        self.description = data.get('description', '')
        
        # Condition
        condition_data = data.get('condition', {})
        self.condition = RuleCondition(condition_data) if condition_data else None
        
        # Actions
        self.actions_if_true = data.get('actions_if_true', [])
        self.actions_if_false = data.get('actions_if_false', [])
        
        # Métadonnées
        self.is_active = data.get('is_active', True)
        self.severity = data.get('severity', 'info')
        if self.severity not in self.SEVERITY_LEVELS:
            self.severity = 'info'
        
        self.message = data.get('message', '')
        self.order = data.get('order', 0)
        
        # Statistiques
        self.evaluation_count = 0
        self.true_count = 0
        self.false_count = 0
        
        logger.debug("Rule creee: " + self.code)
    
    def evaluate(self, context):
        """
        Évalue la règle dans un contexte.
        
        Args:
            context (dict): Contexte d'évaluation
        
        Returns:
            dict: Résultat de l'évaluation
                {
                    'rule_code': str,
                    'rule_name': str,
                    'condition_result': bool,
                    'actions': list,
                    'message': str,
                    'severity': str
                }
        """
        self.evaluation_count += 1
        
        if not self.condition:
            result = True
        else:
            result = self.condition.evaluate(context)
        
        if result:
            self.true_count += 1
            actions = self.actions_if_true
            message = self.message or "Regle validee: " + self.name
        else:
            self.false_count += 1
            actions = self.actions_if_false
            message = self.message or "Regle non validee: " + self.name
        
        return {
            'rule_code': self.code,
            'rule_name': self.name,
            'condition_result': result,
            'actions': actions,
            'message': message,
            'severity': self.severity,
            'category': self.category
        }
    
    def get_statistics(self):
        """
        Récupère les statistiques d'évaluation.
        
        Returns:
            dict: Statistiques
        """
        return {
            'evaluation_count': self.evaluation_count,
            'true_count': self.true_count,
            'false_count': self.false_count,
            'true_ratio': (self.true_count / float(max(self.evaluation_count, 1))) * 100
        }
    
    def reset_statistics(self):
        """Réinitialise les statistiques."""
        self.evaluation_count = 0
        self.true_count = 0
        self.false_count = 0
    
    def to_dict(self):
        """
        Convertit la règle en dictionnaire.
        
        Returns:
            dict: Représentation dictionnaire
        """
        return {
            'code': self.code,
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'condition': self.condition.to_dict() if self.condition else {},
            'actions_if_true': self.actions_if_true,
            'actions_if_false': self.actions_if_false,
            'is_active': self.is_active,
            'severity': self.severity,
            'message': self.message,
            'order': self.order
        }
    
    def __str__(self):
        """Représentation string de la règle."""
        severity_icon = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'error': '❌',
            'critical': '🚨'
        }.get(self.severity, '📋')
        
        return "[Rule] " + severity_icon + " " + self.code + " - " + self.name


class RuleSet:
    """
    Ensemble de règles groupées.
    
    Un RuleSet permet d'appliquer un groupe de règles
    dans un ordre défini, typiquement par catégorie ou norme.
    """
    
    def __init__(self, data):
        """
        Initialise un ensemble de règles.
        
        Args:
            data (dict): Données du RuleSet
                {
                    'code': str,
                    'name': str,
                    'description': str,
                    'rules': list,
                    'norm': str,
                    'is_active': bool
                }
        """
        self.code = data.get('code', '')
        self.name = data.get('name', self.code)
        self.description = data.get('description', '')
        
        # Règles
        self.rules = []
        self.rules_by_code = {}
        self._load_rules(data.get('rules', []))
        
        # Métadonnées
        self.norm = data.get('norm', '')
        self.is_active = data.get('is_active', True)
        
        logger.debug("RuleSet cree: " + self.code + " (" + str(len(self.rules)) + " regles)")
    
    def _load_rules(self, rules_data):
        """Charge les règles depuis les données."""
        for rule_data in rules_data:
            rule = Rule(rule_data)
            self.rules.append(rule)
            self.rules_by_code[rule.code] = rule
        
        # Trier par ordre
        self.rules.sort(key=lambda r: r.order)
    
    def get_rule(self, rule_code):
        """
        Récupère une règle par son code.
        
        Args:
            rule_code (str): Code de la règle
        
        Returns:
            Rule: Règle ou None
        """
        return self.rules_by_code.get(rule_code)
    
    def evaluate_all(self, context):
        """
        Évalue toutes les règles actives.
        
        Args:
            context (dict): Contexte d'évaluation
        
        Returns:
            list: Résultats de chaque règle
        """
        results = []
        
        for rule in self.rules:
            if rule.is_active:
                result = rule.evaluate(context)
                results.append(result)
        
        return results
    
    def evaluate_filtered(self, context, severities=None, categories=None):
        """
        Évalue les règles filtrées.
        
        Args:
            context (dict): Contexte d'évaluation
            severities (list): Niveaux de sévérité à inclure
            categories (list): Catégories à inclure
        
        Returns:
            list: Résultats filtrés
        """
        results = []
        
        for rule in self.rules:
            if not rule.is_active:
                continue
            
            if severities and rule.severity not in severities:
                continue
            
            if categories and rule.category not in categories:
                continue
            
            results.append(rule.evaluate(context))
        
        return results
    
    def get_active_rules(self):
        """
        Récupère les règles actives.
        
        Returns:
            list: Règles actives
        """
        return [r for r in self.rules if r.is_active]
    
    def get_rules_by_severity(self, severity):
        """
        Récupère les règles d'un niveau de sévérité.
        
        Args:
            severity (str): Niveau de sévérité
        
        Returns:
            list: Règles correspondantes
        """
        return [r for r in self.rules if r.severity == severity]
    
    def get_rules_by_category(self, category):
        """
        Récupère les règles d'une catégorie.
        
        Args:
            category (str): Catégorie
        
        Returns:
            list: Règles correspondantes
        """
        return [r for r in self.rules if r.category == category]
    
    def to_dict(self):
        """
        Convertit le RuleSet en dictionnaire.
        
        Returns:
            dict: Représentation dictionnaire
        """
        return {
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'rules': [r.to_dict() for r in self.rules],
            'norm': self.norm,
            'is_active': self.is_active
        }
    
    def __str__(self):
        """Représentation string du RuleSet."""
        active = sum(1 for r in self.rules if r.is_active)
        return "[RuleSet] " + self.code + " - " + self.name + " (" + str(active) + "/" + str(len(self.rules)) + " regles actives)"
    
    def __len__(self):
        """Nombre de règles."""
        return len(self.rules)