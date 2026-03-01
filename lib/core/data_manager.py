# -*- coding: utf-8 -*-
"""
DataManager - Gestionnaire de donnees avec cache intelligent
=============================================================
Responsabilites :
- Chargement donnees depuis API avec cache multi-niveaux
- Gestion mode offline
- Synchronisation periodique
- Invalidation cache intelligente

Architecture cache :
- L1 (Memoire) : Instant, volatile
- L2 (Fichier) : Rapide, persistant
- L3 (API) : Lent, source de verite

Auteur : AutoRevit Team
Date : 2025
"""

import os
import json
import time
from datetime import datetime, timedelta

from config import settings
from utils.logger import get_logger
from utils.exceptions import AutoRevitError

logger = get_logger(__name__)

# Constantes depuis settings
CACHE_DIR = getattr(settings, 'cache_dir', 
                    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache'))
CACHE_TIMEOUT = getattr(settings, 'cache_timeout', 3600)


class CacheError(AutoRevitError):
    """Exception levee en cas d'erreur de cache."""
    pass


class DataManager:
    """
    Gestionnaire centralise des donnees avec cache intelligent.
    
    Exemple d'utilisation :
    ----------------------
    >>> from config import api_client
    >>> from core import DataManager
    >>>
    >>> data_mgr = DataManager(api_client)
    >>>
    >>> # Charge normes (cache automatique)
    >>> norms = data_mgr.get_norms()
    >>>
    >>> # Force refresh
    >>> norms = data_mgr.get_norms(force_refresh=True)
    >>>
    >>> # Vide cache
    >>> data_mgr.clear_cache()
    """
    
    # Strategie de cache par type de donnees
    CACHE_STRATEGIES = {
        'norms': {'ttl': 86400, 'offline_required': True},
        'materials': {'ttl': 86400, 'offline_required': True},
        'sections': {'ttl': 86400, 'offline_required': True},
        'exposure': {'ttl': 86400, 'offline_required': True},
        'rules': {'ttl': 3600, 'offline_required': True},
        'parameters': {'ttl': 3600, 'offline_required': True},
        'ui_config': {'ttl': 3600, 'offline_required': True},
        'projects': {'ttl': 300, 'offline_required': False},
        'user_profile': {'ttl': 1800, 'offline_required': False}
    }
    
    def __init__(self, api_client=None, cache_dir=None):
        """
        Initialise le gestionnaire de donnees.
        
        Args:
            api_client: Client API optionnel
            cache_dir: Repertoire cache (depasse settings.cache_dir)
        """
        self.api = api_client
        
        if cache_dir:
            self.cache_dir = cache_dir
        else:
            self.cache_dir = CACHE_DIR
        
        # Cache memoire (L1 - le plus rapide)
        self._memory_cache = {}
        
        # Creer dossier cache si inexistant
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            logger.info("Dossier cache cree: " + self.cache_dir)
        
        # Mode offline (active si API indisponible)
        self.offline_mode = getattr(settings, 'offline_mode', False)
        
        logger.info("DataManager initialise - Cache: " + self.cache_dir)
        logger.debug("Mode offline: " + str(self.offline_mode))
    
    def get_norms(self, country='FR', active_only=True, force_refresh=False):
        """
        Charge les normes avec cache.
        
        Args:
            country (str): Code pays (FR, BE, CH, etc.)
            active_only (bool): Normes actives uniquement
            force_refresh (bool): Ignorer le cache
        
        Returns:
            list: Liste des normes
        """
        cache_key = 'norms_' + country + '_' + str(active_only)
        
        def api_call():
            if self.api:
                return self.api.get_norms(country=country, active=active_only)
            return []
        
        return self._get_with_cache(
            cache_key=cache_key,
            api_method=api_call,
            data_type='norms',
            force_refresh=force_refresh
        )
    
    def get_materials(self, force_refresh=False):
        """
        Charge les materiaux (beton, acier, barres) avec cache.
        
        Args:
            force_refresh (bool): Ignorer le cache
        
        Returns:
            dict: Materiaux organises par type
        """
        cache_key = 'materials_all'
        
        def fetch_materials():
            if self.api:
                return {
                    'concrete': self.api.get_concrete_classes(),
                    'steel': self.api.get_steel_classes(),
                    'bars': self.api.get_rebar_diameters()
                }
            return {'concrete': [], 'steel': [], 'bars': []}
        
        return self._get_with_cache(
            cache_key=cache_key,
            api_method=fetch_materials,
            data_type='materials',
            force_refresh=force_refresh
        )
    
    def get_sections(self, family=None, force_refresh=False):
        """
        Charge les sections standards avec cache.
        
        Args:
            family (str): Famille de sections (COLUMN, BEAM, etc.)
            force_refresh (bool): Ignorer le cache
        
        Returns:
            list: Sections standards
        """
        cache_key = 'sections_' + (family or 'all')
        
        def api_call():
            if self.api:
                return self.api.get_sections(family=family)
            return []
        
        return self._get_with_cache(
            cache_key=cache_key,
            api_method=api_call,
            data_type='sections',
            force_refresh=force_refresh
        )
    
    def get_exposure_classes(self, force_refresh=False):
        """
        Charge les classes d'exposition avec cache.
        
        Args:
            force_refresh (bool): Ignorer le cache
        
        Returns:
            list: Classes d'exposition
        """
        cache_key = 'exposure_classes'
        
        def api_call():
            if self.api:
                return self.api.get_exposure_classes()
            return []
        
        return self._get_with_cache(
            cache_key=cache_key,
            api_method=api_call,
            data_type='exposure',
            force_refresh=force_refresh
        )
    
    def get_rules(self, element_type=None, category=None, force_refresh=False):
        """
        Charge les regles metier avec cache.
        
        Args:
            element_type (str): Type d'element
            category (str): Categorie de regle
            force_refresh (bool): Ignorer le cache
        
        Returns:
            list: Regles
        """
        cache_key = 'rules_' + (element_type or 'all') + '_' + (category or 'all')
        
        def api_call():
            if self.api:
                return self.api.get_rules(element_type=element_type, category=category)
            return []
        
        return self._get_with_cache(
            cache_key=cache_key,
            api_method=api_call,
            data_type='rules',
            force_refresh=force_refresh
        )
    
    def get_parameters(self, category=None, force_refresh=False):
        """
        Charge les parametres avec cache.
        
        Args:
            category (str): Categorie de parametre
            force_refresh (bool): Ignorer le cache
        
        Returns:
            list: Parametres
        """
        cache_key = 'parameters_' + (category or 'all')
        
        def api_call():
            if self.api:
                return self.api.get_parameters(category=category)
            return []
        
        return self._get_with_cache(
            cache_key=cache_key,
            api_method=api_call,
            data_type='parameters',
            force_refresh=force_refresh
        )
    
    def get_ui_config(self, force_refresh=False):
        """
        Charge la configuration UI avec cache.
        
        Args:
            force_refresh (bool): Ignorer le cache
        
        Returns:
            dict: Configuration UI
        """
        cache_key = 'ui_config'
        
        def api_call():
            if self.api:
                return self.api.get_ui_config()
            return {}
        
        return self._get_with_cache(
            cache_key=cache_key,
            api_method=api_call,
            data_type='ui_config',
            force_refresh=force_refresh
        )
    
    def get_projects(self, active_only=True, force_refresh=False):
        """
        Charge les projets avec cache.
        
        Args:
            active_only (bool): Projets actifs uniquement
            force_refresh (bool): Ignorer le cache
        
        Returns:
            list: Projets
        """
        cache_key = 'projects_' + str(active_only)
        
        def api_call():
            if self.api:
                return self.api.get_projects(active_only=active_only)
            return []
        
        return self._get_with_cache(
            cache_key=cache_key,
            api_method=api_call,
            data_type='projects',
            force_refresh=force_refresh
        )
    
    def get_user_profile(self, force_refresh=False):
        """
        Charge le profil utilisateur avec cache.
        
        Args:
            force_refresh (bool): Ignorer le cache
        
        Returns:
            dict: Profil utilisateur
        """
        cache_key = 'user_profile'
        
        def api_call():
            if self.api:
                return self.api.get_user_profile()
            return {}
        
        return self._get_with_cache(
            cache_key=cache_key,
            api_method=api_call,
            data_type='user_profile',
            force_refresh=force_refresh
        )
    
    def _get_with_cache(self, cache_key, api_method, data_type, force_refresh=False):
        """
        Recupere des donnees avec strategie de cache multi-niveaux.
        """
        strategy = self.CACHE_STRATEGIES.get(
            data_type, 
            {'ttl': 3600, 'offline_required': False}
        )
        
        if force_refresh:
            logger.info("Force refresh: " + cache_key)
            return self._fetch_and_cache(cache_key, api_method, strategy)
        
        if cache_key in self._memory_cache:
            logger.debug("Cache L1 (memoire): " + cache_key)
            return self._memory_cache[cache_key]
        
        cache_file = self._get_cache_filepath(cache_key)
        if self._is_cache_valid(cache_file, strategy['ttl']):
            logger.debug("Cache L2 (fichier): " + cache_key)
            data = self._load_from_file(cache_file)
            self._memory_cache[cache_key] = data
            return data
        
        logger.info("Appel API: " + cache_key)
        return self._fetch_and_cache(cache_key, api_method, strategy)
    
    def _fetch_and_cache(self, cache_key, api_method, strategy):
        """
        Recupere les donnees depuis l'API et les met en cache.
        """
        try:
            data = api_method()
            
            self._save_to_cache(cache_key, data)
            self._memory_cache[cache_key] = data
            
            if self.offline_mode:
                logger.info("Reconnecte - Mode online")
                self.offline_mode = False
            
            return data
        
        except Exception as e:
            logger.warning("Erreur API: " + str(e))
            
            if not self.offline_mode:
                logger.warning("Passage en mode offline")
                self.offline_mode = True
            
            cache_file = self._get_cache_filepath(cache_key)
            if os.path.exists(cache_file):
                logger.warning("Utilisation cache expire: " + cache_key)
                data = self._load_from_file(cache_file)
                self._memory_cache[cache_key] = data
                return data
            
            if strategy['offline_required']:
                raise CacheError(
                    "Donnees '" + cache_key + "' requises mais indisponibles"
                )
            else:
                raise
    
    def _get_cache_filepath(self, cache_key):
        """Genere le chemin du fichier cache."""
        safe_key = cache_key.replace('/', '_').replace('\\', '_').replace(' ', '_')
        return os.path.join(self.cache_dir, safe_key + '.json')
    
    def _is_cache_valid(self, cache_file, ttl):
        """Verifie si un fichier cache est encore valide."""
        if not os.path.exists(cache_file):
            return False
        
        file_age = time.time() - os.path.getmtime(cache_file)
        is_valid = file_age < ttl
        
        if not is_valid:
            logger.debug("Cache expire (" + str(int(file_age)) + "s > " + str(ttl) + "s): " + 
                        os.path.basename(cache_file))
        
        return is_valid
    
    def _load_from_file(self, cache_file):
        """Charge des donnees depuis un fichier cache."""
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error("Erreur lecture cache " + cache_file + ": " + str(e))
            raise CacheError("Impossible de lire cache: " + str(e))
    
    def _save_to_cache(self, cache_key, data):
        """Sauvegarde des donnees dans le cache fichier."""
        cache_file = self._get_cache_filepath(cache_key)
        
        try:
            with open(cache_file, 'w') as f:
                json_str = json.dumps(data, ensure_ascii=False, indent=2)
                f.write(json_str)
            logger.debug("Cache sauvegarde: " + cache_key)
        except Exception as e:
            logger.warning("Impossible de sauvegarder cache " + cache_key + ": " + str(e))
    
    def clear_cache(self, cache_key=None):
        """Vide le cache (tout ou partie)."""
        if cache_key:
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
            
            cache_file = self._get_cache_filepath(cache_key)
            if os.path.exists(cache_file):
                os.remove(cache_file)
                logger.info("Cache vide: " + cache_key)
        else:
            self._memory_cache.clear()
            
            for file in os.listdir(self.cache_dir):
                if file.endswith('.json'):
                    try:
                        os.remove(os.path.join(self.cache_dir, file))
                    except:
                        pass
            
            logger.info("Tout le cache vide")
    
    def invalidate_cache(self, data_type):
        """Invalide le cache pour un type de donnees."""
        keys_to_remove = [k for k in self._memory_cache if k.startswith(data_type)]
        for key in keys_to_remove:
            del self._memory_cache[key]
        
        for file in os.listdir(self.cache_dir):
            if file.startswith(data_type) and file.endswith('.json'):
                try:
                    os.remove(os.path.join(self.cache_dir, file))
                except:
                    pass
        
        logger.info("Cache invalide: " + data_type)
    
    def get_cache_stats(self):
        """Recupere les statistiques du cache."""
        file_cache = [f for f in os.listdir(self.cache_dir) if f.endswith('.json')]
        
        total_size = 0
        for f in file_cache:
            try:
                total_size += os.path.getsize(os.path.join(self.cache_dir, f))
            except:
                pass
        
        return {
            'memory_count': len(self._memory_cache),
            'file_count': len(file_cache),
            'total_size_mb': round(total_size / (1024.0 * 1024), 2),
            'cache_dir': self.cache_dir,
            'offline_mode': self.offline_mode
        }


def test_data_manager():
    """Test du gestionnaire de donnees."""
    print("\n" + "="*60)
    print("TEST DATA MANAGER")
    print("="*60)
    
    try:
        from config import api_client
        
        print("\n1. Initialisation...")
        
        if api_client is None:
            print("   ⚠️  API client non configure - test en mode simulation")
            data_mgr = DataManager(api_client=None)
            print("   ✅ DataManager créé (mode simulation)")
        else:
            print("   Authentification API...")
            try:
                api_client.login('dessinateur', 'password123')
                print("   ✅ Authentification réussie")
            except Exception as e:
                print("   ⚠️  Authentification échouée: " + str(e))
            
            data_mgr = DataManager(api_client)
            print("   ✅ DataManager créé")
        
        print("\n2. Statistiques cache...")
        stats = data_mgr.get_cache_stats()
        print("   Cache dir: " + stats['cache_dir'])
        print("   Entrees memoire: " + str(stats['memory_count']))
        print("   Fichiers cache: " + str(stats['file_count']))
        print("   Taille cache: " + str(stats['total_size_mb']) + " MB")
        print("   Mode offline: " + str(stats['offline_mode']))
        
        print("\n3. Nettoyage...")
        data_mgr.clear_cache()
        print("   ✅ Cache vidé")
        
        print("\n" + "="*60)
        print("✅ TEST TERMINÉ")
        print("="*60 + "\n")
        
    except Exception as e:
        print("\n❌ ERREUR: " + str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_data_manager()