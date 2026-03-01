# -*- coding: utf-8 -*-
"""
AutoRevit Extension - Startup Script v4.2
==========================================
Construit automatiquement les panels selon la session.

LOGIQUE v4.2 :
1. Si session active → Télécharge config UI + construit panels (mise en cache)
2. Si session expirée mais cache existe → Affiche panels depuis cache
3. Si jamais connecté (pas de cache) → Supprime panels dynamiques

CORRECTIF ICÔNES :
- _ensure_all_icons() crée des placeholders PNG valides au démarrage
  pour éviter les erreurs pyRevit [Errno 2] sur les icon.png manquants.
  Ces placeholders sont ensuite écrasés par les vraies icônes du serveur.
"""
import os
import sys
import json
import struct
import zlib

from pyrevit import HOST_APP

# Ajouter lib au path
LIB_PATH = os.path.join(os.path.dirname(__file__), 'lib')
if LIB_PATH not in sys.path:
    sys.path.insert(0, LIB_PATH)


# ══════════════════════════════════════════════════════════════════
#  ✅ FIX ICÔNES - EXÉCUTÉ EN PREMIER AVANT TOUT IMPORT MÉTIER
#  Génère des placeholders PNG valides pour tous les bundles
#  qui n'ont pas encore d'icône, pour éviter les erreurs pyRevit.
#  Les vraies icônes du serveur viendront écraser ces placeholders.
# ══════════════════════════════════════════════════════════════════

def _make_png_chunk(chunk_type, data):
    chunk_len  = struct.pack(b'>I', len(data))
    chunk_data = chunk_type + data
    chunk_crc  = struct.pack(b'>I', zlib.crc32(chunk_data) & 0xffffffff)
    return chunk_len + chunk_data + chunk_crc


def _make_placeholder_png(size=32, gray=180):
    """PNG RGB valide size x size, sans dépendance externe. Compatible IronPython 2.7."""
    sig  = b'\x89PNG\r\n\x1a\n'
    ihdr = _make_png_chunk(b'IHDR', struct.pack(b'>IIBBBBB', size, size, 8, 2, 0, 0, 0))
    row  = b'\x00' + bytes(bytearray([gray, gray, gray] * size))
    idat = _make_png_chunk(b'IDAT', zlib.compress(row * size, 9))
    iend = _make_png_chunk(b'IEND', b'')
    return sig + ihdr + idat + iend


def _ensure_all_icons():
    """
    Parcourt tous les bundles dans AutoRevit.tab et crée un icon.png
    placeholder pour chaque bundle qui n'en a pas ou dont l'icône est invalide.
    Appelé AVANT le scan pyRevit pour éviter les erreurs [Errno 2].
    """
    _ext_dir = os.path.dirname(os.path.abspath(__file__))
    tab_dir  = os.path.join(_ext_dir, 'AutoRevit.tab')

    if not os.path.exists(tab_dir):
        return

    BUNDLE_EXTS   = ('.pushbutton', '.pulldown', '.splitbutton', '.stack', '.panel')
    MIN_ICON_SIZE = 100  # bytes minimum pour un PNG valide

    placeholder_32 = _make_placeholder_png(size=32, gray=180)
    placeholder_64 = _make_placeholder_png(size=64, gray=160)

    count = 0

    for root, dirs, files in os.walk(tab_dir):
        folder = os.path.basename(root)

        if not any(folder.endswith(ext) for ext in BUNDLE_EXTS):
            continue

        icon_path    = os.path.join(root, 'icon.png')
        needs_create = (
            not os.path.exists(icon_path) or
            os.path.getsize(icon_path) < MIN_ICON_SIZE
        )

        if not needs_create:
            continue

        try:
            png_data = placeholder_64 if folder.endswith('.panel') else placeholder_32
            with open(icon_path, 'wb') as f:
                f.write(png_data)
            count += 1
        except Exception as e:
            print("[AutoRevit] Impossible de créer placeholder {}: {}".format(icon_path, e))

    if count > 0:
        print("[AutoRevit] {} placeholder(s) icon.png créé(s) au démarrage".format(count))


# ✅ Appel immédiat — avant tous les imports métier
_ensure_all_icons()


# ══════════════════════════════════════════════════════════════════
#  IMPORTS MÉTIER
# ══════════════════════════════════════════════════════════════════

from config.settings import Settings
from config.api_client import APIClient, APIAuthenticationError, APIConnectionError
from ui.ribbon_builder import RibbonBuilder
from utils.logger import get_logger

logger = get_logger('Startup')


def has_cached_session():
    """
    Vérifie si un fichier de session existe.

    Returns:
        bool: True si session_token.json existe
    """
    try:
        settings = Settings()
        session_file = os.path.join(settings.cache_dir, 'session_token.json')
        return os.path.exists(session_file)
    except Exception as e:
        logger.warning("Erreur vérification session cache: {}".format(e))
        return False


def has_cached_ui_config():
    """
    Vérifie si une config UI en cache existe.

    Returns:
        bool: True si ui_config.json existe
    """
    try:
        settings = Settings()
        cache_file = os.path.join(settings.cache_dir, 'ui_config.json')
        return os.path.exists(cache_file)
    except:
        return False


def load_cached_ui_config():
    """
    Charge la config UI depuis le cache.

    Returns:
        dict: Config UI ou None
    """
    try:
        settings = Settings()
        cache_file = os.path.join(settings.cache_dir, 'ui_config.json')

        if not os.path.exists(cache_file):
            return None

        # Compatible IronPython 2.7
        try:
            from io import open as io_open
            with io_open(cache_file, 'r', encoding='utf-8') as f:
                ui_config = json.load(f)
        except ImportError:
            import codecs
            with codecs.open(cache_file, 'r', encoding='utf-8') as f:
                ui_config = json.load(f)

        logger.info("Config UI chargée depuis cache")
        return ui_config

    except Exception as e:
        logger.error("Erreur chargement cache UI: {}".format(e))
        return None


def save_cached_ui_config(ui_config):
    """
    Sauvegarde la config UI dans le cache.

    Args:
        ui_config (dict): Config UI à sauvegarder
    """
    try:
        settings = Settings()
        cache_file = os.path.join(settings.cache_dir, 'ui_config.json')

        try:
            from io import open as io_open
            with io_open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(ui_config, f, ensure_ascii=False, indent=2)
        except ImportError:
            import codecs
            with codecs.open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(ui_config, f, ensure_ascii=False, indent=2)

        logger.debug("Config UI sauvegardée en cache")

    except Exception as e:
        logger.warning("Impossible de sauvegarder cache UI: {}".format(e))


def clear_dynamic_panels():
    """
    Supprime tous les panels dynamiques (garde seulement les panels fixes).

    Les panels fixes sont :
    - 00_Connexion.panel
    - Session.panel
    """
    try:
        settings = Settings()
        extension_dir = os.path.dirname(__file__)
        tab_dir = os.path.join(extension_dir, 'AutoRevit.tab')

        if not os.path.exists(tab_dir):
            return

        import shutil

        for item in os.listdir(tab_dir):
            if not item.endswith('.panel'):
                continue

            # Garder les panels fixes
            if item.startswith('00_') or item == 'Session.panel':
                logger.debug("Panel fixe conservé: {}".format(item))
                continue

            # Supprimer les panels dynamiques
            panel_path = os.path.join(tab_dir, item)
            if os.path.isdir(panel_path):
                try:
                    shutil.rmtree(panel_path)
                    logger.info("Panel dynamique supprimé: {}".format(item))
                except Exception as e:
                    logger.warning("Impossible de supprimer {}: {}".format(item, e))

        logger.info("Panels dynamiques nettoyés")

    except Exception as e:
        logger.error("Erreur nettoyage panels: {}".format(e))


def main():
    """
    Point d'entrée du startup.

    LOGIQUE SIMPLIFIÉE :
    - Si session_token.json existe → Afficher panels (depuis cache ou API)
    - Si session_token.json n'existe pas → Supprimer panels dynamiques
    - La session disparaît uniquement lors de la déconnexion manuelle
    """
    try:
        logger.info("=" * 60)
        logger.info("🚀 DÉMARRAGE AUTOREVIT EXTENSION v4.2")
        logger.info("=" * 60)

        # Initialiser
        settings = Settings()

        logger.info("[1/4] Configuration chargée")
        logger.info("  • Revit version: {}".format(HOST_APP.version))
        logger.info("  • API URL: {}".format(settings.api_url))
        logger.info("  • Cache dir: {}".format(settings.cache_dir))

        # Vérifier session
        logger.info("[2/4] Vérification session...")

        has_session  = has_cached_session()
        has_ui_cache = has_cached_ui_config()

        logger.info("  • Session trouvée: {}".format("Oui" if has_session else "Non"))
        logger.info("  • Config UI en cache: {}".format("Oui" if has_ui_cache else "Non"))

        # CAS 1: Pas de session → Jamais connecté OU déconnecté
        if not has_session:
            logger.info("[3/4] Aucune session active")
            logger.info("  → Suppression des panels dynamiques...")
            clear_dynamic_panels()
            logger.info("=" * 60)
            logger.info("✅ AUTOREVIT INITIALISÉ (mode déconnecté)")
            logger.info("  → Cliquez sur 'Se connecter' pour charger vos panels")
            logger.info("=" * 60)
            return

        # CAS 2: Session existe → Utilisateur connecté
        logger.info("[3/4] Session active détectée")
        ui_config = None

        # Essayer de télécharger la config UI fraîche
        logger.info("  → Tentative de téléchargement config UI...")

        try:
            api_client = APIClient(settings)
            ui_config  = api_client.get_ui_config_authenticated()

            if ui_config and ui_config.get('panels'):
                logger.info("  ✅ Config UI téléchargée ({} panels)".format(
                    len(ui_config.get('panels', []))
                ))
                # Sauvegarder en cache pour prochaine utilisation
                save_cached_ui_config(ui_config)
            else:
                logger.warning("  ⚠️  Config UI vide reçue")
                ui_config = None

        except Exception as e:
            logger.warning("  ⚠️  Téléchargement échoué: {}".format(str(e)))
            logger.info("  → Utilisation du cache...")
            ui_config = None

        # Fallback sur le cache si téléchargement échoué
        if ui_config is None and has_ui_cache:
            logger.info("  → Chargement depuis cache...")
            ui_config = load_cached_ui_config()

            if ui_config:
                logger.info("  ✅ Config UI chargée depuis cache ({} panels)".format(
                    len(ui_config.get('panels', []))
                ))

        # Vérifier qu'on a une config UI
        if not ui_config or not ui_config.get('panels'):
            logger.warning("  ⚠️  Aucune config UI disponible")
            logger.info("  → Panels ne peuvent pas être chargés")
            logger.info("=" * 60)
            logger.info("⚠️  AUTOREVIT INITIALISÉ (config UI manquante)")
            logger.info("  → Reconnectez-vous pour télécharger vos panels")
            logger.info("=" * 60)
            return

        # Construire les panels
        logger.info("[4/4] Construction panels...")

        try:
            user_data      = ui_config.get('user', {})
            ribbon_builder = RibbonBuilder(
                ui_config=ui_config,
                user_data=user_data,
                settings=settings
            )
            report = ribbon_builder.build()

            logger.info("  ✅ Panels construits :")
            logger.info("    • {} panels créés".format(report['panels_created']))
            logger.info("    • {} scripts écrits".format(report['scripts_written']))
            logger.info("    • {} scripts en cache".format(report['scripts_cached']))
            logger.info("    • {} icônes copiées".format(report['icons_copied']))

            if report.get('warnings'):
                logger.warning("  ⚠️  {} avertissement(s)".format(len(report['warnings'])))
                for w in report['warnings'][:3]:
                    logger.warning("    - {}".format(w))

        except Exception as e:
            logger.error("  ❌ Erreur construction panels: {}".format(str(e)), exc_info=True)
            logger.info("=" * 60)
            logger.info("⚠️  AUTOREVIT INITIALISÉ (panels non construits)")
            logger.info("=" * 60)
            return

        logger.info("=" * 60)
        logger.info("✅ AUTOREVIT INITIALISÉ")
        logger.info("=" * 60)

    except Exception as e:
        logger.error("❌ ERREUR STARTUP: {}".format(str(e)), exc_info=True)
        logger.info("=" * 60)
        logger.info("❌ AUTOREVIT - ERREUR INITIALISATION")
        logger.info("=" * 60)


if __name__ == '__main__':
    main()