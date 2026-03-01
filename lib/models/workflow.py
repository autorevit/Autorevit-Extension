# -*- coding: utf-8 -*-
"""
Workflow - Modèles représentant un workflow d'actions
======================================================
Un workflow est une séquence ordonnée d'actions à exécuter
dans un ordre défini, avec conditions et gestion d'erreurs.

Classes:
    - WorkflowStep: Étape individuelle d'un workflow
    - Workflow: Collection d'étapes formant un processus complet

Auteur : AutoRevit Team
Date : 2025
"""

from utils.logger import get_logger
from models.action import Action

logger = get_logger(__name__)


class WorkflowStep:
    """
    Étape d'un workflow.
    
    Une étape associe une action à exécuter avec ses paramètres,
    des conditions d'exécution, et des règles de gestion d'erreurs.
    """
    
    def __init__(self, data):
        """
        Initialise une étape de workflow.
        
        Args:
            data (dict): Données de l'étape
                {
                    'step_number': int,
                    'action_code': str,
                    'action': Action (optionnel),
                    'parameters': dict,
                    'condition': dict (optionnel),
                    'is_optional': bool,
                    'can_skip': bool,
                    'on_error': str,
                    'description': str
                }
        """
        self.step_number = data.get('step_number', 1)
        self.action_code = data.get('action_code', '')
        self._action = data.get('action')  # Instance d'Action (peut être None)
        
        self.parameters = data.get('parameters', {})
        self.condition = data.get('condition', {})
        
        self.is_optional = data.get('is_optional', False)
        self.can_skip = data.get('can_skip', False)
        self.on_error = data.get('on_error', 'stop')  # stop, continue, ignore
        
        self.description = data.get('description', '')
        
        # État d'exécution
        self.status = None  # pending, running, success, error, skipped
        self.result = None
        self.error = None
        self.execution_time = 0
        self.start_time = None
        self.end_time = None
        
        logger.debug("WorkflowStep creee: " + str(self.step_number) + " - " + self.action_code)
    
    @property
    def action(self):
        """Retourne l'action associée."""
        return self._action
    
    @action.setter
    def action(self, action_instance):
        """Définit l'action associée."""
        self._action = action_instance
    
    def has_action(self):
        """Vérifie si l'action est chargée."""
        return self._action is not None
    
    def validate(self):
        """
        Valide que l'étape est prête à être exécutée.
        
        Returns:
            tuple: (is_valid, message)
        """
        if not self.action_code:
            return False, "Code d'action manquant"
        
        if not self._action:
            return False, "Action non chargee: " + self.action_code
        
        # Valider paramètres
        valid, errors = self._action.validate_parameters(self.parameters)
        if not valid:
            error_msg = "; ".join([k + ": " + v for k, v in errors.items()])
            return False, "Parametres invalides: " + error_msg
        
        return True, "OK"
    
    def to_dict(self):
        """
        Convertit l'étape en dictionnaire.
        
        Returns:
            dict: Représentation dictionnaire
        """
        return {
            'step_number': self.step_number,
            'action_code': self.action_code,
            'parameters': self.parameters,
            'condition': self.condition,
            'is_optional': self.is_optional,
            'can_skip': self.can_skip,
            'on_error': self.on_error,
            'description': self.description,
            'status': self.status
        }
    
    def __str__(self):
        """Représentation string de l'étape."""
        status_str = " [" + self.status + "]" if self.status else ""
        return "[Step " + str(self.step_number) + "] " + self.action_code + status_str


class Workflow:
    """
    Workflow complet composé d'étapes séquentielles.
    
    Un workflow représente un processus métier complet
    (ex: "Création structure complète", "Ferraillage poteaux", etc.)
    """
    
    def __init__(self, data):
        """
        Initialise un workflow.
        
        Args:
            data (dict): Données du workflow
                {
                    'code': str,
                    'name': str,
                    'description': str,
                    'category': str,
                    'steps': list,
                    'is_active': bool,
                    'version': int,
                    'created_by': str,
                    'created_at': str
                }
        """
        self.code = data.get('code', '')
        self.name = data.get('name', self.code)
        self.description = data.get('description', '')
        self.category = data.get('category', 'GENERAL')
        
        # Étapes
        steps_data = data.get('steps', [])
        self.steps = []
        self.steps_by_number = {}
        
        for step_data in steps_data:
            step = WorkflowStep(step_data)
            self.steps.append(step)
            self.steps_by_number[step.step_number] = step
        
        # Trier par numéro
        self.steps.sort(key=lambda s: s.step_number)
        
        # Métadonnées
        self.is_active = data.get('is_active', True)
        self.version = data.get('version', 1)
        self.created_by = data.get('created_by', '')
        self.created_at = data.get('created_at', '')
        self.updated_at = data.get('updated_at', '')
        
        # État d'exécution
        self.current_step_index = -1
        self.status = None  # pending, running, completed, failed, cancelled
        self.start_time = None
        self.end_time = None
        self.context = {}  # Contexte partagé entre les étapes
        
        logger.debug("Workflow cree: " + self.code + " v" + str(self.version))
    
    def load_actions(self, action_map):
        """
        Charge les actions associées aux étapes.
        
        Args:
            action_map (dict): Dictionnaire {code_action: instance Action}
        
        Returns:
            int: Nombre d'actions chargées
        """
        loaded = 0
        
        for step in self.steps:
            if step.action_code in action_map:
                step.action = action_map[step.action_code]
                loaded += 1
            else:
                logger.warning("Action non trouvee: " + step.action_code)
        
        return loaded
    
    def get_step(self, step_number):
        """
        Récupère une étape par son numéro.
        
        Args:
            step_number (int): Numéro de l'étape
        
        Returns:
            WorkflowStep: Étape ou None
        """
        return self.steps_by_number.get(step_number)
    
    def get_next_step(self):
        """
        Récupère la prochaine étape à exécuter.
        
        Returns:
            WorkflowStep: Prochaine étape ou None
        """
        next_index = self.current_step_index + 1
        
        if next_index < len(self.steps):
            return self.steps[next_index]
        
        return None
    
    def get_pending_steps(self):
        """
        Récupère les étapes non encore exécutées.
        
        Returns:
            list: Étapes en attente
        """
        return [s for s in self.steps if s.status is None]
    
    def get_completed_steps(self):
        """
        Récupère les étapes exécutées avec succès.
        
        Returns:
            list: Étapes réussies
        """
        return [s for s in self.steps if s.status == 'success']
    
    def get_failed_steps(self):
        """
        Récupère les étapes en échec.
        
        Returns:
            list: Étapes échouées
        """
        return [s for s in self.steps if s.status == 'error']
    
    def get_progress(self):
        """
        Calcule la progression du workflow.
        
        Returns:
            dict: Progression (pourcentage, étapes)
        """
        total = len(self.steps)
        if total == 0:
            return {'percent': 0, 'completed': 0, 'total': 0}
        
        completed = len(self.get_completed_steps())
        percent = (completed / float(total)) * 100
        
        return {
            'percent': round(percent, 1),
            'completed': completed,
            'total': total,
            'current': self.current_step_index + 1 if self.current_step_index >= 0 else 0,
            'status': self.status
        }
    
    def reset(self):
        """Réinitialise l'état d'exécution du workflow."""
        self.current_step_index = -1
        self.status = None
        self.start_time = None
        self.end_time = None
        self.context = {}
        
        for step in self.steps:
            step.status = None
            step.result = None
            step.error = None
            step.execution_time = 0
        
        logger.debug("Workflow reinitialise: " + self.code)
    
    def to_dict(self):
        """
        Convertit le workflow en dictionnaire.
        
        Returns:
            dict: Représentation dictionnaire
        """
        return {
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'steps': [s.to_dict() for s in self.steps],
            'is_active': self.is_active,
            'version': self.version,
            'created_by': self.created_by,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __str__(self):
        """Représentation string du workflow."""
        steps_count = len(self.steps)
        return "[Workflow] " + self.code + " - " + self.name + " (" + str(steps_count) + " etapes)"
    
    def __len__(self):
        """Nombre d'étapes."""
        return len(self.steps)