# -*- coding: utf-8 -*-
"""
Bouton: Se Connecter - VERSION FINALE
✅ Supprime les panels dynamiques lors de la déconnexion
"""

import os
import sys
import shutil

# ✅ CORRECTION: Ajouter lib au path CORRECTEMENT
script_dir = os.path.dirname(__file__)
panel_dir = os.path.dirname(script_dir)
tab_dir = os.path.dirname(panel_dir)
ext_dir = os.path.dirname(tab_dir)
lib_path = os.path.join(ext_dir, 'lib')

if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

print("Debug: lib_path = " + lib_path)

# Imports
from pyrevit import forms

try:
    from config.settings import Settings
    print("✅ Settings importé")
except Exception as e:
    print("❌ Erreur import Settings: " + str(e))
    forms.alert("Erreur: impossible de charger Settings\n\n" + str(e))
    raise

try:
    from config.api_client import APIClient
    print("✅ APIClient importé")
except Exception as e:
    print("❌ Erreur import APIClient: " + str(e))
    forms.alert("Erreur: impossible de charger APIClient\n\n" + str(e))
    raise

try:
    from auth.session import SessionManager
    print("✅ SessionManager importé")
except Exception as e:
    print("❌ Erreur import SessionManager: " + str(e))
    forms.alert("Erreur: impossible de charger SessionManager\n\n" + str(e))
    raise

try:
    from ui.ribbon_builder import RibbonBuilder
    print("✅ RibbonBuilder importé")
except Exception as e:
    print("❌ Erreur import RibbonBuilder: " + str(e))
    forms.alert("Erreur: impossible de charger RibbonBuilder\n\n" + str(e))
    raise

try:
    from auth.login_window import show_login_window
    print("✅ show_login_window importé")
except Exception as e:
    print("❌ Erreur import login_window: " + str(e))
    show_login_window = None

try:
    from utils.logger import get_logger
    print("✅ get_logger importé")
    logger = get_logger('Login')
except Exception as e:
    print("❌ Erreur import logger: " + str(e))
    logger = None


def delete_dynamic_panels(ext_dir):
    """
    Supprime tous les panels dynamiques (sauf 00_Connexion qui est statique).
    
    Args:
        ext_dir: Chemin vers AutoRevit.extension
    """
    try:
        tab_dir = os.path.join(ext_dir, 'AutoRevit.tab')
        
        if not os.path.exists(tab_dir):
            if logger:
                logger.warning("Tab dir introuvable: {}".format(tab_dir))
            return
        
        deleted_count = 0
        
        # Lister tous les dossiers dans AutoRevit.tab
        for item in os.listdir(tab_dir):
            item_path = os.path.join(tab_dir, item)
            
            # Ignorer si ce n'est pas un dossier
            if not os.path.isdir(item_path):
                continue
            
            # ✅ GARDER seulement le panel de connexion
            if item == '00_Connexion.panel':
                continue
            
            # ✅ SUPPRIMER tous les autres panels (dynamiques)
            if item.endswith('.panel'):
                try:
                    shutil.rmtree(item_path)
                    deleted_count += 1
                    
                    if logger:
                        logger.info("🗑️ Panel supprimé: {}".format(item))
                    else:
                        print("🗑️ Panel supprimé: {}".format(item))
                
                except Exception as e:
                    if logger:
                        logger.error("Erreur suppression {}: {}".format(item, str(e)))
                    else:
                        print("❌ Erreur suppression {}: {}".format(item, str(e)))
        
        if logger:
            logger.info("✅ {} panels dynamiques supprimés".format(deleted_count))
        else:
            print("✅ {} panels dynamiques supprimés".format(deleted_count))
        
    except Exception as e:
        if logger:
            logger.error("Erreur suppression panels: {}".format(str(e)))
        else:
            print("❌ Erreur suppression panels: {}".format(str(e)))


def build_dynamic_panels(settings, api_client):
    """Télécharge la config UI et crée les scripts dynamiques."""
    try:
        if logger:
            logger.info("📥 Téléchargement configuration UI...")
        else:
            print("📥 Téléchargement configuration UI...")
        
        ui_config = api_client.get_ui_config_authenticated()
        
        if not ui_config:
            if logger:
                logger.error("Config UI vide")
            return False
        
        if logger:
            logger.info("✅ Config UI récupérée ({} panels)".format(
                len(ui_config.get('panels', []))
            ))
        else:
            print("✅ Config UI récupérée ({} panels)".format(
                len(ui_config.get('panels', []))
            ))
        
        user_data = ui_config.get('user', {})
        
        ribbon_builder = RibbonBuilder(
            ui_config=ui_config,
            user_data=user_data,
            settings=settings
        )
        
        if logger:
            logger.info("🔨 Construction des scripts...")
        else:
            print("🔨 Construction des scripts...")
        
        report = ribbon_builder.build()
        
        if logger:
            logger.info("✅ Scripts: {} écrits, {} en cache | Icônes: {}".format(
                report['scripts_written'],
                report['scripts_cached'],
                report['icons_copied']
            ))
        else:
            print("✅ Scripts: {} écrits, {} en cache | Icônes: {}".format(
                report['scripts_written'],
                report['scripts_cached'],
                report['icons_copied']
            ))
        
        import json
        try:
            from io import open as io_open
        except ImportError:
            io_open = open
        
        cache_file = os.path.join(settings.cache_dir, 'ui_config.json')
        with io_open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(ui_config, f, ensure_ascii=False, indent=2)
        
        # ✅ Sauvegarder aussi le marqueur pour le startup
        marker_file = os.path.join(settings.cache_dir, 'panels_built.json')
        marker_data = {
            'version': ui_config.get('version', 1),
            'panels_count': len(ui_config.get('panels', [])),
            'timestamp': 'manual_build'
        }
        with io_open(marker_file, 'w', encoding='utf-8') as f:
            json.dump(marker_data, f, ensure_ascii=False, indent=2)
        
        if logger:
            logger.info("💾 Config sauvegardée en cache")
        else:
            print("💾 Config sauvegardée en cache")
        
        return True
        
    except Exception as e:
        if logger:
            logger.error("Erreur construction panels: {}".format(str(e)), exc_info=True)
        else:
            print("❌ Erreur construction panels: {}".format(str(e)))
        return False


def main():
    """Point d'entrée du script de connexion"""
    try:
        print("=" * 60)
        print("DÉMARRAGE SCRIPT DE CONNEXION")
        print("=" * 60)
        
        settings = Settings()
        session_manager = SessionManager(settings.cache_dir)
        
        # Vérifier si déjà connecté
        if session_manager.is_authenticated():
            result = forms.alert(
                "Vous êtes déjà connecté.\n\n"
                "Voulez-vous vous déconnecter ?",
                title="AutoRevit",
                yes=True,
                no=True
            )
            
            if result:
                # ✅ DÉCONNEXION : Supprimer session + cache + panels
                print("🔓 Déconnexion en cours...")
                
                session_manager.clear_session()
                print("✅ Session supprimée")
                
                # Supprimer cache UI
                cache_file = os.path.join(settings.cache_dir, 'ui_config.json')
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    print("🗑️ Cache UI supprimé")
                
                # Supprimer marqueur panels
                marker_file = os.path.join(settings.cache_dir, 'panels_built.json')
                if os.path.exists(marker_file):
                    os.remove(marker_file)
                    print("🗑️ Marqueur panels supprimé")
                
                # ✅ SUPPRIMER PHYSIQUEMENT LES PANELS DYNAMIQUES
                delete_dynamic_panels(ext_dir)
                
                forms.alert(
                    "✅ Déconnecté avec succès !\n\n"
                    "pyRevit va se recharger...",
                    title="AutoRevit"
                )
                
                from pyrevit.loader import sessionmgr
                sessionmgr.reload_pyrevit()
                return
            
            # ✅ RESTER CONNECTÉ : Juste reconstruire
            else:
                print("🔄 Reconstruction des panels...")
                api_client = APIClient(settings)
                
                try:
                    panels_ok = build_dynamic_panels(settings, api_client)
                    
                    if panels_ok:
                        forms.alert(
                            "✅ Panels mis à jour !",
                            title="AutoRevit"
                        )
                    else:
                        forms.alert(
                            "❌ Erreur lors de la mise à jour des panels.",
                            title="AutoRevit"
                        )
                except Exception as e:
                    forms.alert(
                        "Erreur: {}\n\nRedémarrez Revit si le problème persiste.".format(str(e)),
                        title="AutoRevit"
                    )
                
                return
        
        # ✅ CONNEXION : Afficher dialogue
        if show_login_window:
            login_response = show_login_window()
        else:
            forms.alert("Erreur: fenêtre de connexion non disponible", title="AutoRevit")
            return
        
        if not login_response:
            print("Connexion annulée")
            return
        
        user_data = login_response.get('user', {})
        username = user_data.get('username', 'Utilisateur')
        
        print("🔐 Login réussi pour: {}".format(username))
        
        # Créer APIClient (va charger automatiquement le JWT du cache)
        api_client = APIClient(settings)
        
        # Récupérer profil utilisateur pour avoir toutes les infos
        try:
            profile = api_client.get_current_user()
        except Exception as e:
            print("Warning: Impossible de récupérer le profil : {}".format(str(e)))
            profile = user_data
        
        # Créer session dans SessionManager
        session_manager.create_session({
            'access_token': login_response.get('access'),
            'refresh_token': login_response.get('refresh'),
            'username': profile.get('username'),
            'role': profile.get('role') if isinstance(profile.get('role'), str) else profile.get('role', {}).get('code'),
            'user_id': profile.get('id') or profile.get('user_id'),
            'ui_config_version': profile.get('ui_config_version', 1)
        })
        
        print("✅ Session créée pour: {}".format(username))
        
        # Construire panels dynamiques
        panels_ok = build_dynamic_panels(settings, api_client)
        
        if not panels_ok:
            forms.alert(
                "Connexion réussie mais impossible de charger les panels.\n\n"
                "Vérifiez votre connexion réseau.",
                title="AutoRevit - Avertissement"
            )
            return
        
        # Message succès
        role_name = profile.get('role', {}).get('name') if isinstance(profile.get('role'), dict) else profile.get('role', 'Inconnu')
        
        forms.alert(
            "✅ Connexion réussie !\n\n"
            "Utilisateur: {}\n"
            "Rôle: {}\n\n"
            "pyRevit va se recharger pour afficher vos panels...".format(
                username,
                role_name
            ),
            title="AutoRevit"
        )
        
        # Recharger pyRevit
        from pyrevit.loader import sessionmgr
        sessionmgr.reload_pyrevit()
    
    except Exception as e:
        err_msg = "Erreur: {}".format(str(e))
        print("❌ " + err_msg)
        
        import traceback
        traceback.print_exc()
        
        forms.alert(
            "Erreur lors de la connexion:\n\n{}".format(str(e)),
            title="AutoRevit - Erreur"
        )


if __name__ == '__main__':
    main()