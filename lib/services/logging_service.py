# -*- coding: utf-8 -*-
"""
LoggingService - Service de logging pour Revit
===============================================
Responsabilites :
- Logging local (fichier, console)
- Envoi logs vers API backend
- Gestion cache logs hors ligne
- Formatage et rotation logs

Auteur : AutoRevit Team
Date : 2025
"""

import os
import json
import time
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)

# Exception personnalisee
class APIError(Exception):
    """Exception levee lors d'erreurs API"""
    pass


# Imports optionnels
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("Requests non disponible (logs API desactives)")

try:
    from config.api_client import APIClient
    API_CLIENT_AVAILABLE = True
except ImportError:
    API_CLIENT_AVAILABLE = False


class LoggingService:
    """
    Service de logging pour AutoRevit.
    
    Exemple d'utilisation :
    ----------------------
    >>> from services import LoggingService
    >>>
    >>> logger = LoggingService(api_client)
    >>>
    >>> # Log action
    >>> logger.log_action("CREATE_COLUMN", "success", "10 poteaux crees", 2.5)
    >>>
    >>> # Log erreur
    >>> logger.log_error(e, {"context": "creation"})
    >>>
    >>> # Envoyer logs au backend
    >>> logger.send_logs_to_api()
    """

    # Niveaux de log
    LEVELS = {
        'DEBUG': 10,
        'INFO': 20,
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50
    }

    def __init__(self, api_client=None, cache_dir=None, log_level='INFO'):
        """
        Initialise le service de logging.
        
        Args:
            api_client: Client API optionnel
            cache_dir: Repertoire cache pour logs hors ligne
            log_level: Niveau de log ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        """
        self.api = api_client
        self.log_level = self.LEVELS.get(log_level.upper(), 20)
        
        # Cache pour logs hors ligne
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            from config import settings
            self.cache_dir = getattr(settings, 'CACHE_DIR', None)
        
        if self.cache_dir:
            self.logs_file = os.path.join(self.cache_dir, 'autorevit_logs.json')
            self._ensure_cache_dir()
        else:
            self.logs_file = None
        
        # Logs en memoire
        self.session_logs = []
        self.pending_api_logs = []
        self.session_id = self._generate_session_id()
        
        logger.info("LoggingService initialise - Session: " + self.session_id)
    
    # ========================================================================
    # LOGGING ACTIONS
    # ========================================================================
    
    def log_action(self, action_code, status, message, duration=None, user=None, project=None):
        """
        Log une action executee.
        
        Args:
            action_code (str): Code de l'action
            status (str): 'success', 'warning', 'error'
            message (str): Message descriptif
            duration (float): Duree d'execution (secondes)
            user (str): Utilisateur (optionnel)
            project (str): Projet (optionnel)
        
        Returns:
            dict: Entree de log creee
        """
        log_entry = {
            'type': 'action',
            'session_id': self.session_id,
            'action': action_code,
            'status': status,
            'message': message,
            'duration': duration,
            'user': user,
            'project': project,
            'timestamp': datetime.now().isoformat(),
            'timestamp_epoch': time.time()
        }
        
        self._add_log_entry(log_entry)
        
        # Afficher dans console
        if status == 'success':
            logger.info("[ACTION] " + action_code + " - " + message)
        elif status == 'warning':
            logger.warning("[ACTION] " + action_code + " - " + message)
        else:
            logger.error("[ACTION] " + action_code + " - " + message)
        
        return log_entry
    
    def log_error(self, error, context=None, user=None, project=None):
        """
        Log une erreur.
        
        Args:
            error (Exception): Exception
            context (dict): Contexte au moment erreur
            user (str): Utilisateur
            project (str): Projet
        
        Returns:
            dict: Entree de log creee
        """
        import traceback
        
        log_entry = {
            'type': 'error',
            'session_id': self.session_id,
            'error_type': error.__class__.__name__,
            'error_message': str(error),
            'stack_trace': traceback.format_exc(),
            'context': context or {},
            'user': user,
            'project': project,
            'timestamp': datetime.now().isoformat(),
            'timestamp_epoch': time.time()
        }
        
        self._add_log_entry(log_entry)
        logger.error("[ERROR] " + str(error))
        
        return log_entry
    
    def log_info(self, message, category=None, user=None, project=None):
        """
        Log un message informatif.
        
        Args:
            message (str): Message
            category (str): Categorie
            user (str): Utilisateur
            project (str): Projet
        
        Returns:
            dict: Entree de log
        """
        if self.LEVELS['INFO'] < self.log_level:
            return None
        
        log_entry = {
            'type': 'info',
            'session_id': self.session_id,
            'category': category,
            'message': message,
            'user': user,
            'project': project,
            'timestamp': datetime.now().isoformat(),
            'timestamp_epoch': time.time()
        }
        
        self._add_log_entry(log_entry)
        logger.info("[INFO] " + message)
        
        return log_entry
    
    def log_warning(self, message, category=None, user=None, project=None):
        """
        Log un avertissement.
        
        Args:
            message (str): Message
            category (str): Categorie
            user (str): Utilisateur
            project (str): Projet
        
        Returns:
            dict: Entree de log
        """
        if self.LEVELS['WARNING'] < self.log_level:
            return None
        
        log_entry = {
            'type': 'warning',
            'session_id': self.session_id,
            'category': category,
            'message': message,
            'user': user,
            'project': project,
            'timestamp': datetime.now().isoformat(),
            'timestamp_epoch': time.time()
        }
        
        self._add_log_entry(log_entry)
        logger.warning("[WARNING] " + message)
        
        return log_entry
    
    def log_debug(self, message, category=None, data=None):
        """
        Log un message de debug.
        
        Args:
            message (str): Message
            category (str): Categorie
            data (dict): Donnees additionnelles
        
        Returns:
            dict: Entree de log
        """
        if self.LEVELS['DEBUG'] < self.log_level:
            return None
        
        log_entry = {
            'type': 'debug',
            'session_id': self.session_id,
            'category': category,
            'message': message,
            'data': data,
            'timestamp': datetime.now().isoformat(),
            'timestamp_epoch': time.time()
        }
        
        self._add_log_entry(log_entry)
        logger.debug("[DEBUG] " + message)
        
        return log_entry
    
    # ========================================================================
    # GESTION LOGS
    # ========================================================================
    
    def _add_log_entry(self, entry):
        """Ajoute une entree aux logs."""
        # Memoire session
        self.session_logs.append(entry)
        
        # Cache pour API
        self.pending_api_logs.append(entry)
        
        # Fichier local
        if self.logs_file:
            self._append_to_file(entry)
        
        # Limiter taille memoire
        if len(self.session_logs) > 1000:
            self.session_logs = self.session_logs[-1000:]
    
    def _append_to_file(self, entry):
        """Ajoute une entree au fichier de logs."""
        try:
            logs = []
            
            # Lire logs existants
            if os.path.exists(self.logs_file):
                with open(self.logs_file, 'r') as f:
                    try:
                        logs = json.load(f)
                    except:
                        logs = []
            
            # Ajouter nouvelle entree
            logs.append(entry)
            
            # Garder dernieres 1000 entrees
            if len(logs) > 1000:
                logs = logs[-1000:]
            
            # Ecrire fichier
            with open(self.logs_file, 'w') as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            logger.error("Impossible d'ecrire log fichier: " + str(e))
    
    def get_session_logs(self, log_type=None):
        """
        Recupere les logs de la session courante.
        
        Args:
            log_type (str): Filtrer par type ('action', 'error', etc.)
        
        Returns:
            list: Logs de session
        """
        if log_type:
            return [log for log in self.session_logs if log.get('type') == log_type]
        return self.session_logs
    
    def get_pending_logs(self):
        """
        Recupere les logs en attente d'envoi API.
        
        Returns:
            list: Logs en attente
        """
        return self.pending_api_logs
    
    def clear_session_logs(self):
        """Vide les logs de session."""
        self.session_logs = []
        logger.debug("Logs session vides")
    
    # ========================================================================
    # ENVOI API
    # ========================================================================
    
    def send_logs_to_api(self, max_logs=50):
        """
        Envoie les logs en attente au backend.
        
        Args:
            max_logs (int): Nombre maximum de logs a envoyer
        
        Returns:
            bool: True si succes
        """
        if not self.api:
            logger.warning("Aucun client API configure")
            return False
        
        if not self.pending_api_logs:
            logger.debug("Aucun log en attente")
            return True
        
        # Prendre premiers logs
        logs_to_send = self.pending_api_logs[:max_logs]
        
        try:
            # Appel API
            result = self.api.send_logs(logs_to_send)
            
            if result:
                # Retirer logs envoyes
                self.pending_api_logs = self.pending_api_logs[len(logs_to_send):]
                logger.info(str(len(logs_to_send)) + " logs envoyes au backend")
                return True
            else:
                logger.warning("Echec envoi logs API")
                return False
        
        except APIError as e:
            logger.error("Erreur API envoi logs: " + str(e))
            return False
        except Exception as e:
            logger.error("Erreur envoi logs: " + str(e))
            return False
    
    def send_error_report(self, error, context=None):
        """
        Envoie un rapport d'erreur immediatement.
        
        Args:
            error (Exception): Exception
            context (dict): Contexte
        
        Returns:
            bool: True si succes
        """
        log_entry = self.log_error(error, context)
        
        # Tentative envoi immediat
        if self.api:
            try:
                result = self.api.send_error_report(log_entry)
                if result:
                    # Retirer des logs en attente
                    if log_entry in self.pending_api_logs:
                        self.pending_api_logs.remove(log_entry)
                    return True
            except:
                pass
        
        return False
    
    # ========================================================================
    # RAPPORTS ET STATISTIQUES
    # ========================================================================
    
    def generate_session_report(self):
        """
        Genere un rapport de la session courante.
        
        Returns:
            dict: Rapport de session
        """
        report = {
            'session_id': self.session_id,
            'start_time': self.session_logs[0]['timestamp'] if self.session_logs else None,
            'end_time': datetime.now().isoformat(),
            'total_logs': len(self.session_logs),
            'actions': len([l for l in self.session_logs if l.get('type') == 'action']),
            'errors': len([l for l in self.session_logs if l.get('type') == 'error']),
            'warnings': len([l for l in self.session_logs if l.get('type') == 'warning']),
            'success_rate': 0
        }
        
        # Calcul taux reussite
        actions = [l for l in self.session_logs if l.get('type') == 'action']
        if actions:
            success = len([a for a in actions if a.get('status') == 'success'])
            report['success_rate'] = (success / float(len(actions))) * 100
        
        return report
    
    def get_statistics(self):
        """
        Recupere les statistiques de logging.
        
        Returns:
            dict: Statistiques
        """
        return {
            'session_logs_count': len(self.session_logs),
            'pending_api_logs': len(self.pending_api_logs),
            'session_id': self.session_id,
            'log_level': self._get_level_name(self.log_level)
        }
    
    # ========================================================================
    # UTILITAIRES
    # ========================================================================
    
    def _ensure_cache_dir(self):
        """Cree le repertoire cache si necessaire."""
        if self.cache_dir and not os.path.exists(self.cache_dir):
            try:
                os.makedirs(self.cache_dir)
            except Exception as e:
                logger.error("Impossible de creer cache dir: " + str(e))
                self.cache_dir = None
                self.logs_file = None
    
    def _generate_session_id(self):
        """Genere un ID unique pour la session."""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def _get_level_name(self, level):
        """Retourne le nom du niveau de log."""
        for name, value in self.LEVELS.items():
            if value == level:
                return name
        return 'UNKNOWN'
    
    def set_log_level(self, level_name):
        """
        Definit le niveau de log.
        
        Args:
            level_name (str): 'DEBUG', 'INFO', 'WARNING', 'ERROR'
        """
        level = self.LEVELS.get(level_name.upper())
        if level:
            self.log_level = level
            logger.info("Niveau log: " + level_name)


# ============================================================================
# FONCTION DE TEST
# ============================================================================

def test_logging_service():
    print("\n" + "="*60)
    print("TEST LOGGING SERVICE")
    print("="*60)
    
    try:
        print("\n1 Creation LoggingService...")
        log_svc = LoggingService(api_client=None, cache_dir=None)
        
        # Test differents logs
        print("\n2 Test logs...")
        log_svc.log_action("TEST_ACTION", "success", "Test reussi", 1.5)
        log_svc.log_info("Message information")
        log_svc.log_warning("Avertissement test")
        
        try:
            raise ValueError("Erreur test")
        except Exception as e:
            log_svc.log_error(e, {"test": True})
        
        # Test rapport
        print("\n3 Test rapport...")
        report = log_svc.generate_session_report()
        print("   Session: " + report['session_id'])
        print("   Logs: " + str(report['total_logs']))
        print("   Taux reussite: " + str(round(report['success_rate'], 1)) + "%")
        
        print("\n" + "="*60)
        print("TOUS LES TESTS PASSES")
        print("="*60 + "\n")
    
    except Exception as e:
        print("\nERREUR: " + str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_logging_service()