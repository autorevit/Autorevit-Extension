# -*- coding: utf-8 -*-
"""
ExecutionEngine - Moteur d'exécution des actions et workflows
==============================================================
Responsabilités :
- Exécution atomique des actions Revit
- Gestion des transactions
- Validation des paramètres
- Exécution séquentielle des workflows
- Gestion des conditions et erreurs
- Logging des performances

Auteur : AutoRevit Team
Date : 2025
"""

import time
import traceback
from utils.logger import get_logger
from utils.exceptions import (
    AutoRevitError,
    ValidationError,
    RevitDocumentError,
    RevitTransactionError,
    RevitAPIError
)
from services.transaction_service import TransactionService
from services.logging_service import LoggingService
from models.action import Action
from models.workflow import Workflow, WorkflowStep

logger = get_logger(__name__)

try:
    from Autodesk.Revit.DB import Document
    REVIT_AVAILABLE = True
except ImportError:
    REVIT_AVAILABLE = False
    logger.warning("Revit API non disponible (mode développement)")


class ExecutionEngine:
    """
    Moteur d'exécution des actions et workflows Revit.
    
    Exemple d'utilisation :
    ----------------------
    >>> from pyrevit import revit
    >>> from core import ExecutionEngine
    >>> from config import api_client
    >>>
    >>> doc = revit.doc
    >>> engine = ExecutionEngine(doc, api_client)
    >>>
    >>> # Exécuter une action simple
    >>> result = engine.execute_action("COLUMN_CREATE", {
    ...     "width": 400,
    ...     "height": 400,
    ...     "level": "Niveau 1"
    ... })
    >>>
    >>> # Exécuter un workflow complet
    >>> workflow_result = engine.execute_workflow("STRUCTURE_COMPLETE", {
    ...     "building_type": "R+3",
    ...     "norm": "EC2"
    ... })
    """

    def __init__(self, document, api_client=None):
        """
        Initialise le moteur d'exécution.
        
        Args:
            document: Document Revit actif
            api_client: Client API optionnel pour récupérer actions/workflows
        """
        if not REVIT_AVAILABLE and document is not None:
            logger.warning("Revit API non disponible - exécution limitée")
        
        self.document = document
        self.api_client = api_client
        
        # Services
        self.transaction_manager = TransactionService(document)
        self.logger = LoggingService(api_client)
        
        # Cache des actions et workflows
        self._actions_cache = {}
        self._workflows_cache = {}
        
        # Statistiques d'exécution
        self.stats = {
            'actions_executed': 0,
            'workflows_executed': 0,
            'success_count': 0,
            'error_count': 0,
            'total_duration': 0
        }
        
        logger.info("ExecutionEngine initialisé")

    # ========================================================================
    # EXÉCUTION D'ACTIONS ATOMIQUES
    # ========================================================================

    def execute_action(self, action_code, parameters=None):
        """
        Exécute une action atomique.
        
        Args:
            action_code (str): Code de l'action (ex: "COLUMN_CREATE")
            parameters (dict): Paramètres de l'action
        
        Returns:
            dict: Résultat de l'exécution
        
        Raises:
            ValidationError: Paramètres invalides
            RevitAPIError: Erreur lors de l'exécution Revit
            RevitTransactionError: Erreur de transaction
        """
        start_time = time.time()
        logger.info("Exécution action: " + action_code)
        
        try:
            # 1. Récupérer la définition de l'action
            action = self._get_action(action_code)
            if not action:
                raise ValidationError("Action non trouvée: " + action_code)
            
            # 2. Valider les paramètres
            parameters = parameters or {}
            is_valid, errors = action.validate_parameters(parameters)
            if not is_valid:
                error_msg = "; ".join([k + ": " + v for k, v in errors.items()])
                raise ValidationError("Paramètres invalides: " + error_msg)
            
            # 3. Fusionner avec les paramètres par défaut
            exec_params = action.get_default_parameters()
            exec_params.update(parameters)
            
            # 4. Exécuter l'action avec ou sans transaction
            if action.requires_transaction:
                with self.transaction_manager.start(action.name):
                    result = self._execute_action_template(action, exec_params)
            else:
                result = self._execute_action_template(action, exec_params)
            
            # 5. Logger le succès
            duration = time.time() - start_time
            self.logger.log_action(
                action_code,
                'success',
                str(result)[:200],
                duration
            )
            
            # 6. Mettre à jour les statistiques
            self.stats['actions_executed'] += 1
            self.stats['success_count'] += 1
            self.stats['total_duration'] += duration
            
            logger.info("Action terminée: " + action_code + " (" + str(round(duration, 2)) + "s)")
            
            return {
                'success': True,
                'action': action_code,
                'result': result,
                'duration': duration
            }
            
        except ValidationError as e:
            duration = time.time() - start_time
            self.logger.log_error(e, {'action': action_code, 'parameters': parameters})
            self.stats['error_count'] += 1
            logger.error("Validation échouée: " + str(e))
            raise
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.log_error(e, {'action': action_code, 'parameters': parameters})
            self.stats['error_count'] += 1
            logger.error("Erreur exécution action " + action_code + ": " + str(e))
            raise RevitAPIError("Échec exécution: " + str(e))

    def _get_action(self, action_code):
        """
        Récupère une action depuis le cache ou l'API.
        
        Args:
            action_code (str): Code de l'action
        
        Returns:
            Action: Instance de l'action ou None
        """
        # Cache mémoire
        if action_code in self._actions_cache:
            logger.debug("Action trouvée dans cache: " + action_code)
            return self._actions_cache[action_code]
        
        # Charger depuis l'API
        if self.api_client:
            try:
                data = self.api_client.get_action_detail(action_code)
                if data:
                    action = Action(data)
                    self._actions_cache[action_code] = action
                    logger.debug("Action chargée depuis API: " + action_code)
                    return action
            except Exception as e:
                logger.warning("Impossible de charger l'action " + action_code + ": " + str(e))
        
        return None

    def _execute_action_template(self, action, parameters):
        """
        Exécute le template Python de l'action.
        
        Args:
            action (Action): Action à exécuter
            parameters (dict): Paramètres validés
        
        Returns:
            Résultat de l'exécution
        """
        if not action.template:
            logger.warning("Action sans template: " + action.code)
            return {'status': 'no_template', 'parameters': parameters}
        
        try:
            # Créer un environnement d'exécution sécurisé
            exec_globals = {
                '__builtins__': __builtins__,
                'doc': self.document,
                'logger': self.logger,
                'parameters': parameters,
                'Action': Action,
                'result': None
            }
            
            # Exécuter le template
            exec(action.template, exec_globals)
            
            return exec_globals.get('result', {'status': 'executed'})
            
        except Exception as e:
            logger.error("Erreur dans le template: " + str(e))
            logger.debug(traceback.format_exc())
            raise RevitAPIError("Erreur d'exécution du template: " + str(e))

    # ========================================================================
    # EXÉCUTION DE WORKFLOWS
    # ========================================================================

    def execute_workflow(self, workflow_code, context=None):
        """
        Exécute un workflow complet (séquence d'actions).
        
        Args:
            workflow_code (str): Code du workflow
            context (dict): Contexte d'exécution (partagé entre les étapes)
        
        Returns:
            dict: Résultats du workflow
        """
        start_time = time.time()
        logger.info("Exécution workflow: " + workflow_code)
        
        try:
            # 1. Récupérer le workflow
            workflow = self._get_workflow(workflow_code)
            if not workflow:
                raise ValidationError("Workflow non trouvé: " + workflow_code)
            
            # 2. Charger les actions associées
            self._load_workflow_actions(workflow)
            
            # 3. Initialiser le contexte
            workflow_context = context or {}
            workflow.reset()
            workflow.status = 'running'
            workflow.start_time = time.time()
            
            results = []
            failed = False
            
            # 4. Exécuter chaque étape
            for step in workflow.steps:
                # Vérifier si annulation demandée
                if workflow_context.get('cancelled', False):
                    logger.info("Workflow annulé par l'utilisateur")
                    workflow.status = 'cancelled'
                    break
                
                # Vérifier la condition d'exécution
                if step.condition:
                    if not self._evaluate_condition(step.condition, workflow_context):
                        logger.debug("Condition non remplie pour étape " + str(step.step_number))
                        step.status = 'skipped'
                        continue
                
                # Exécuter l'étape
                try:
                    step.status = 'running'
                    step.start_time = time.time()
                    
                    # Fusionner paramètres étape + contexte
                    step_params = step.parameters.copy()
                    step_params.update({
                        'workflow_context': workflow_context,
                        'workflow_code': workflow_code,
                        'step_number': step.step_number
                    })
                    
                    # Exécuter l'action
                    action_result = self.execute_action(
                        step.action_code,
                        step_params
                    )
                    
                    step.status = 'success'
                    step.result = action_result.get('result')
                    step.execution_time = time.time() - step.start_time
                    
                    # Mettre à jour le contexte
                    workflow_context['step_' + str(step.step_number) + '_result'] = step.result
                    workflow_context['step_' + str(step.step_number) + '_success'] = True
                    
                    results.append({
                        'step': step.step_number,
                        'action': step.action_code,
                        'status': 'success',
                        'result': step.result,
                        'duration': step.execution_time
                    })
                    
                    logger.info("Étape " + str(step.step_number) + " réussie")
                    
                except Exception as e:
                    step.status = 'error'
                    step.error = str(e)
                    step.execution_time = time.time() - step.start_time
                    
                    results.append({
                        'step': step.step_number,
                        'action': step.action_code,
                        'status': 'error',
                        'error': str(e),
                        'duration': step.execution_time
                    })
                    
                    logger.error("Étape " + str(step.step_number) + " échouée: " + str(e))
                    
                    # Gérer l'erreur selon la configuration
                    if step.on_error == 'stop':
                        logger.warning("Arrêt du workflow sur erreur")
                        failed = True
                        break
                    elif step.on_error == 'ignore':
                        logger.warning("Erreur ignorée, continuation")
                        continue
                    elif step.on_error == 'retry':
                        # TODO: Implémenter retry
                        pass
            
            # 5. Finaliser le workflow
            workflow.end_time = time.time()
            workflow.status = 'failed' if failed else 'completed'
            
            total_duration = time.time() - start_time
            
            # 6. Logger le résultat
            self.logger.log_action(
                'workflow_' + workflow_code,
                'success' if not failed else 'error',
                'Workflow terminé avec ' + str(len(results)) + ' étapes',
                total_duration
            )
            
            self.stats['workflows_executed'] += 1
            self.stats['total_duration'] += total_duration
            
            logger.info("Workflow terminé: " + workflow_code + " (" + str(round(total_duration, 2)) + "s)")
            
            return {
                'success': not failed,
                'workflow': workflow_code,
                'workflow_name': workflow.name,
                'steps_total': len(workflow.steps),
                'steps_completed': len([r for r in results if r['status'] == 'success']),
                'steps_failed': len([r for r in results if r['status'] == 'error']),
                'steps_skipped': len([r for r in results if r['status'] == 'skipped']),
                'results': results,
                'context': workflow_context,
                'duration': total_duration
            }
            
        except Exception as e:
            logger.error("Erreur workflow " + workflow_code + ": " + str(e))
            logger.debug(traceback.format_exc())
            raise

    def _get_workflow(self, workflow_code):
        """
        Récupère un workflow depuis le cache ou l'API.
        
        Args:
            workflow_code (str): Code du workflow
        
        Returns:
            Workflow: Instance du workflow ou None
        """
        if workflow_code in self._workflows_cache:
            logger.debug("Workflow trouvé dans cache: " + workflow_code)
            return self._workflows_cache[workflow_code]
        
        if self.api_client:
            try:
                data = self.api_client.get_workflow_detail(workflow_code)
                if data:
                    workflow = Workflow(data)
                    self._workflows_cache[workflow_code] = workflow
                    logger.debug("Workflow chargé depuis API: " + workflow_code)
                    return workflow
            except Exception as e:
                logger.warning("Impossible de charger workflow " + workflow_code + ": " + str(e))
        
        return None

    def _load_workflow_actions(self, workflow):
        """
        Charge toutes les actions nécessaires à un workflow.
        
        Args:
            workflow (Workflow): Workflow à préparer
        """
        action_codes = set()
        for step in workflow.steps:
            action_codes.add(step.action_code)
        
        for action_code in action_codes:
            action = self._get_action(action_code)
            if action:
                workflow.load_actions({action_code: action})
            else:
                logger.warning("Action non disponible pour workflow: " + action_code)

    def _evaluate_condition(self, condition, context):
        """
        Évalue une condition dans le contexte donné.
        
        Args:
            condition (dict): Définition de la condition
            context (dict): Contexte d'évaluation
        
        Returns:
            bool: Résultat de l'évaluation
        """
        from models.rule import RuleCondition
        
        try:
            cond = RuleCondition(condition)
            return cond.evaluate(context)
        except Exception as e:
            logger.warning("Erreur évaluation condition: " + str(e))
            return False

    # ========================================================================
    # GESTION DU CACHE
    # ========================================================================

    def clear_cache(self, action_code=None, workflow_code=None):
        """
        Vide le cache des actions et workflows.
        
        Args:
            action_code (str): Action spécifique à vider
            workflow_code (str): Workflow spécifique à vider
        """
        if action_code:
            if action_code in self._actions_cache:
                del self._actions_cache[action_code]
                logger.info("Cache action vidé: " + action_code)
        elif workflow_code:
            if workflow_code in self._workflows_cache:
                del self._workflows_cache[workflow_code]
                logger.info("Cache workflow vidé: " + workflow_code)
        else:
            self._actions_cache.clear()
            self._workflows_cache.clear()
            logger.info("Tout le cache d'exécution vidé")

    # ========================================================================
    # STATISTIQUES
    # ========================================================================

    def get_stats(self):
        """
        Récupère les statistiques d'exécution.
        
        Returns:
            dict: Statistiques du moteur
        """
        return {
            'actions_executed': self.stats['actions_executed'],
            'workflows_executed': self.stats['workflows_executed'],
            'success_count': self.stats['success_count'],
            'error_count': self.stats['error_count'],
            'total_duration_seconds': round(self.stats['total_duration'], 2),
            'average_action_duration': round(
                self.stats['total_duration'] / max(self.stats['actions_executed'], 1), 
                2
            ),
            'cache_actions': len(self._actions_cache),
            'cache_workflows': len(self._workflows_cache)
        }

    def reset_stats(self):
        """Réinitialise les statistiques d'exécution."""
        self.stats = {
            'actions_executed': 0,
            'workflows_executed': 0,
            'success_count': 0,
            'error_count': 0,
            'total_duration': 0
        }
        logger.info("Statistiques réinitialisées")


# ============================================================================
# FONCTION DE TEST
# ============================================================================

def test_execution_engine():
    """
    Test du moteur d'exécution.
    """
    print("\n" + "="*60)
    print("TEST EXECUTION ENGINE")
    print("="*60)
    
    if not REVIT_AVAILABLE:
        print("\n❌ Revit non disponible - test en mode développement")
    else:
        print("\n✅ Revit disponible")
    
    try:
        from pyrevit import revit
        from config import api_client
        
        print("\n1. Initialisation...")
        doc = revit.doc if REVIT_AVAILABLE else None
        engine = ExecutionEngine(doc, api_client)
        print("   ✅ ExecutionEngine créé")
        
        print("\n2. Test stats...")
        stats = engine.get_stats()
        print("   Stats: " + str(stats))
        
        print("\n3. Test cache...")
        engine.clear_cache()
        print("   ✅ Cache vidé")
        
        print("\n" + "="*60)
        print("✅ TEST TERMINÉ")
        print("="*60 + "\n")
        
    except Exception as e:
        print("\n❌ ERREUR: " + str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_execution_engine()