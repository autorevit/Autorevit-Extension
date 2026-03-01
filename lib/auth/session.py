# -*- coding: utf-8 -*-
"""
Gestionnaire de sessions utilisateur - VERSION CORRIGÉE
✅ CORRECTION: Utilise session_token.json (même fichier que api_client.py)
"""
import os
import json
import time

# Compatible IronPython 2.7
try:
    from io import open as io_open
except ImportError:
    io_open = open


class SessionManager(object):
    """Gestionnaire de session utilisateur avec persistence"""
    
    def __init__(self, cache_dir):
        """
        Initialise le gestionnaire de session.
        
        Args:
            cache_dir (str): Chemin vers le dossier cache
        """
        self.cache_dir = cache_dir
        # ✅ CORRECTION: Utiliser session_token.json (même fichier que api_client.py)
        self.session_file = os.path.join(cache_dir, 'session_token.json')
        self._session_data = None
        self._load_session()
    
    def _load_session(self):
        """Charge la session depuis le fichier cache"""
        if not os.path.exists(self.session_file):
            self._session_data = None
            return
        
        try:
            with io_open(self.session_file, 'r', encoding='utf-8') as f:
                self._session_data = json.load(f)
            print("Debug: Session chargee depuis cache")
        except Exception as e:
            print("Warning: Erreur chargement session : " + str(e))
            self._session_data = None
    
    def _save_session(self):
        """Sauvegarde la session dans le fichier cache"""
        try:
            with io_open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self._session_data, f, ensure_ascii=False, indent=2)
            print("Debug: Session sauvegardee")
        except Exception as e:
            print("Error: Impossible de sauvegarder session : " + str(e))
    
    def create_session(self, user_data):
        """
        Crée une nouvelle session utilisateur.
        
        Args:
            user_data (dict): Données utilisateur
                {
                    'access_token': 'JWT...',      # ✅ JWT access token
                    'refresh_token': 'JWT...',     # ✅ JWT refresh token
                    'username': 'benjamin',
                    'role': 'admin',
                    'user_id': 1,
                    'ui_config_version': 1
                }
        """
        # ✅ CORRECTION: Stocker access_token comme session_token
        access_token = user_data.get('access_token') or user_data.get('session_token')
        
        self._session_data = {
            'session_token': access_token,  # JWT access token
            'refresh_token': user_data.get('refresh_token', ''),
            'username': user_data.get('username'),
            'role': user_data.get('role'),
            'user_id': user_data.get('user_id'),
            'ui_config_version': user_data.get('ui_config_version', 1),
            'created_at': time.time(),
            'last_activity': time.time()
        }
        self._save_session()
        print("Info: Session creee pour : " + str(self._session_data.get('username')))
    
    def is_authenticated(self):
        """Vérifie si une session valide existe"""
        if not self._session_data:
            return False
        
        # Vérifier présence du session_token (JWT)
        if not self._session_data.get('session_token'):
            return False
        
        return True
    
    def get_session_data(self):
        """
        Retourne les données de session.
        
        Returns:
            dict: Données de session ou None
        """
        if self.is_authenticated():
            return self._session_data
        return None
    
    def get_session_token(self):
        """
        Retourne le JWT access token.
        
        Returns:
            str: Token ou None
        """
        if self._session_data:
            return self._session_data.get('session_token')
        return None
    
    def get_refresh_token(self):
        """
        Retourne le JWT refresh token.
        
        Returns:
            str: Refresh token ou None
        """
        if self._session_data:
            return self._session_data.get('refresh_token')
        return None
    
    def get_username(self):
        """Retourne le nom d'utilisateur de la session active"""
        if self._session_data:
            return self._session_data.get('username')
        return None
    
    def get_role(self):
        """Retourne le rôle de l'utilisateur"""
        if self._session_data:
            return self._session_data.get('role')
        return None
    
    def get_user_id(self):
        """Retourne l'ID utilisateur"""
        if self._session_data:
            return self._session_data.get('user_id')
        return None
    
    def get_ui_config_version(self):
        """Retourne la version de config UI"""
        if self._session_data:
            return self._session_data.get('ui_config_version', 1)
        return 1
    
    def update_activity(self):
        """Met à jour le timestamp de dernière activité"""
        if not self._session_data:
            print("Warning: Tentative de mise a jour activite sans session active")
            return
        
        self._session_data['last_activity'] = time.time()
        self._save_session()
    
    def update_ui_config_version(self, version):
        """
        Met à jour la version de config UI.
        
        Args:
            version (int): Nouvelle version
        """
        if not self._session_data:
            print("Warning: Tentative de mise a jour version sans session active")
            return
        
        self._session_data['ui_config_version'] = version
        self._save_session()
        print("Debug: Version UI config mise a jour : {}".format(version))
    
    def clear_session(self):
        """Supprime la session (déconnexion)"""
        self._session_data = None
        
        if os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
                print("Info: Session supprimee")
            except Exception as e:
                print("Warning: Impossible de supprimer session : " + str(e))
    
    def get_last_activity(self):
        """
        Retourne le timestamp de dernière activité.
        
        Returns:
            float: Timestamp ou 0 si pas de session
        """
        if not self._session_data:
            return 0
        
        return self._session_data.get('last_activity', 0)
    
    def get_session_age(self):
        """
        Retourne l'âge de la session en secondes.
        
        Returns:
            float: Secondes depuis la création ou 0
        """
        if not self._session_data:
            return 0
        
        created_at = self._session_data.get('created_at', time.time())
        return time.time() - created_at
    
    def __str__(self):
        if self._session_data:
            return "<SessionManager user={} role={} authenticated={}>".format(
                self._session_data.get('username', '?'),
                self._session_data.get('role', '?'),
                self.is_authenticated()
            )
        return "<SessionManager authenticated=False>"