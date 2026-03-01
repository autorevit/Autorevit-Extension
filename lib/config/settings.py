# -*- coding: utf-8 -*-
"""
lib/config/settings.py
Classe Settings centralisee qui lit et gere la configuration de l'extension.
- Charge config.json
- Fournit des valeurs par defaut
- Permet de sauvegarder des modifications
- Utilisee par APIClient, ribbon, etc.
"""
import os
import json

# Compatible IronPython 2.7 - io.open pour encoding
try:
    from io import open as io_open
except ImportError:
    io_open = open

DEFAULT_CONFIG = {
    "api_url": "http://localhost:8000/api/v1",
    "api_timeout": 30,
    "debug_mode": True,
    "auto_sync_interval": 300,
    "cache_dir": None,
    "logs_dir": None,
    "offline_mode": False,
    "language": "fr",
    "units": {"length": "mm", "force": "kN", "stress": "MPa", "area": "m2"},
    "show_welcome_message": True,
    "max_retries": 3,
    "retry_delay": 3,
    "log_level": "INFO",
    "max_log_size_mb": 50,
    "ui_config_cache_duration": 86400,
    
    # ✅ NOUVELLES CLÉS AJOUTÉES
    "download_chunk_size": 8192,  # Taille des chunks pour téléchargement (bytes)
    "upload_chunk_size": 8192,    # Taille des chunks pour upload (bytes)
    "token_refresh_interval": 3600,  # Intervalle rafraîchissement token JWT (secondes)
    "experimental_features": False,  # Activer features expérimentales
    "backup_interval": 86400,     # Intervalle backup auto (secondes, 24h par défaut)
    "default_country": "FR",      # Pays par défaut pour normes
    "version": "1.0.0",           # Version de l'extension
    "retry_failed_requests": True,  # Réessayer requêtes échouées
    "last_project": None,         # Dernier projet ouvert (ID)
    "telemetry_enabled": False,   # Télémétrie (analytics) - RGPD compliant
    "auto_update": False,         # Mise à jour automatique
    "enable_debug_tools": False,  # Outils de debug avancés
    "notifications_enabled": True,  # Notifications système
    "last_user": None,            # Dernier utilisateur connecté
    "developer_mode": False,      # Mode développeur (logs verbeux)
    "session_timeout": 7200,      # Timeout session (secondes, 2h)
    "performance_monitoring": False,  # Monitoring performance
    "clear_cache_on_startup": False,  # Vider cache au démarrage
    "default_norm": "EC2",        # Norme par défaut
    "theme": "light",             # Thème UI (light/dark/auto)
    "remember_me": True,          # Se souvenir de moi
    "supported_revit_versions": [2021, 2022, 2023, 2024, 2025],  # Versions Revit supportées
    "compression_enabled": False,  # Compression des requêtes API
    "check_updates_on_startup": True,  # Vérifier MAJ au démarrage
    "auto_backup": False,         # Backup automatique projets
    "cors_allowed_origins": ["*"],  # CORS (si besoin côté client)
}

class Settings(object):
    """Gestionnaire de configuration global pour AutoRevit."""
    
    def __init__(self):
        self.extension_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.config_path = os.path.join(self.extension_dir, "config.json")
        
        # Initialisation avec defaults
        for key, value in DEFAULT_CONFIG.items():
            setattr(self, key, value)
        
        # Definition dynamique des chemins si pas dans config
        if self.cache_dir is None:
            self.cache_dir = os.path.join(self.extension_dir, "cache")
        if self.logs_dir is None:
            self.logs_dir = os.path.join(self.extension_dir, "logs")
        
        # Compatible IronPython / Python 2
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
        
        self._load_from_file()
    
    def _load_from_file(self):
        """Charge et applique le config.json si present."""
        if not os.path.exists(self.config_path):
            print("Warning: config.json introuvable - utilisation des valeurs par defaut")
            return
        
        try:
            with io_open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            for key, value in config_data.items():
                if hasattr(self, key):
                    setattr(self, key, value)
                else:
                    print("Debug: Cle inconnue dans config.json ignoree : " + str(key))
            
            print("Info: Configuration chargee depuis : " + str(self.config_path))
            print("Debug: API URL chargee : " + str(self.api_url))
            print("Debug: Mode offline : " + str(self.offline_mode))
        
        except ValueError as e:
            print("Error: config.json invalide (JSON mal forme) : " + str(e))
        except Exception as e:
            print("Error: Erreur lors de la lecture de config.json : " + str(e))
    
    def save(self):
        """Sauvegarde la configuration actuelle dans config.json."""
        try:
            data = {}
            for key in DEFAULT_CONFIG:
                if hasattr(self, key):
                    data[key] = getattr(self, key)
            
            with io_open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print("Info: Configuration sauvegardee avec succes")
        except Exception as e:
            print("Error: Echec sauvegarde config : " + str(e))
    
    # Methodes pratiques
    @property
    def is_offline(self):
        return self.offline_mode
    
    def set_offline(self, value):
        self.offline_mode = value
        print("Info: Mode offline modifie : " + str(value))
    
    def __str__(self):
        return "<Settings api_url=" + str(self.api_url) + " offline=" + str(self.offline_mode) + " lang=" + str(self.language) + ">"