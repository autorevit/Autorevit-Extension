# -*- coding: utf-8 -*-
"""
Bouton: Se Deconnecter
[OK] Efface la session locale et recharge pyRevit
[OK] FIX UNICODE : Encodage robuste Python 2/3 / IronPython / Windows
"""

import os
import sys
import traceback

# ==================================================================
#  [OK] FIX UNICODE : Fonctions utilitaires (avant tout import)
# ==================================================================
PY2 = sys.version_info[0] == 2

if PY2:
    text_type = unicode    # noqa: F821
else:
    text_type = str


def _safe_str(value):
    """
    Convertit n'importe quelle valeur en str unicode propre.
    Compatible Python 2/3, IronPython, Windows (cp1252/utf-8/latin-1).
    Ne leve jamais d'exception.
    """
    if value is None:
        return u''
    if isinstance(value, text_type):
        return value
    if isinstance(value, bytes):
        for enc in ('utf-8', 'latin-1', 'cp1252'):
            try:
                return value.decode(enc)
            except (UnicodeDecodeError, AttributeError):
                continue
        return value.decode('utf-8', errors='replace')
    try:
        return text_type(value)
    except Exception:
        return repr(value)


def _safe_format(template, *args, **kwargs):
    """
    Format de chaine securise : convertit tous les args en _safe_str
    avant de formater. Evite les UnicodeDecodeError sur les valeurs Revit.
    """
    safe_args   = [_safe_str(a) for a in args]
    safe_kwargs = {k: _safe_str(v) for k, v in kwargs.items()}
    try:
        return template.format(*safe_args, **safe_kwargs)
    except Exception as e:
        return u"[format_error: {}]".format(repr(e))


def _safe_print(msg):
    """
    Print securise : encode proprement pour la console Windows
    (evite UnicodeEncodeError sur cp850/cp1252).
    """
    try:
        line = _safe_str(msg)
        if PY2:
            print(line.encode('utf-8', errors='replace'))
        else:
            print(line)
    except Exception:
        print("[message non affichable]")


def _safe_traceback():
    """Retourne le traceback courant sous forme de str unicode propre."""
    try:
        return _safe_str(traceback.format_exc())
    except Exception:
        return u"traceback non disponible"


# ==================================================================
#  AJOUT LIB AU PATH
# ==================================================================

script_dir = os.path.dirname(__file__)
panel_dir  = os.path.dirname(script_dir)
tab_dir    = os.path.dirname(panel_dir)
ext_dir    = os.path.dirname(tab_dir)
lib_path   = os.path.join(ext_dir, 'lib')

if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

_safe_print(_safe_format(u"Debug: lib_path = {}", lib_path))

# ==================================================================
#  IMPORTS
# ==================================================================

from pyrevit import forms


def _import_or_alert(module_path, symbol, label):
    """
    Importe un symbole depuis un module.
    Affiche une alerte et leve l'exception en cas d'echec.
    """
    try:
        mod = __import__(module_path, fromlist=[symbol])
        obj = getattr(mod, symbol)
        _safe_print(_safe_format(u"OK  {} importe", label))
        return obj
    except Exception as e:
        msg = _safe_format(u"ERREUR import {} : {}", label, e)
        _safe_print(msg)
        forms.alert(
            _safe_format(u"Erreur: impossible de charger {}\n\n{}", label, e)
        )
        raise


Settings       = _import_or_alert('config.settings', 'Settings',       'Settings')
SessionManager = _import_or_alert('auth.session',     'SessionManager', 'SessionManager')

# logger optionnel
logger = None
try:
    from utils.logger import get_logger
    logger = get_logger('Logout')
    _safe_print(u"OK  get_logger importe")
except Exception as e:
    _safe_print(_safe_format(u"WARN logger non disponible : {}", e))


# ==================================================================
#  FONCTIONS UTILITAIRES
# ==================================================================

def _log(msg):
    """Log via logger si disponible, sinon print securise."""
    if logger:
        logger.info(_safe_str(msg))
    else:
        _safe_print(msg)


def _log_error(msg):
    """Log erreur via logger si disponible, sinon print securise."""
    if logger:
        logger.error(_safe_str(msg))
    else:
        _safe_print(_safe_format(u"ERREUR {}", msg))


def _clear_dynamic_panels(tab_dir):
    """
    Supprime les panels dynamiques (tous sauf 00_* et Session.panel)
    pour nettoyer le ruban avant le rechargement.

    Args:
        tab_dir (str): Chemin du dossier AutoRevit.tab/

    Returns:
        int: Nombre de panels supprimes
    """
    import shutil
    count = 0

    if not os.path.exists(tab_dir):
        return 0

    for item in os.listdir(tab_dir):
        # Garder les panels fixes
        if item.startswith('00_'):
            continue
        if item == 'Session.panel':
            continue
        if not item.endswith('.panel'):
            continue

        item_path = os.path.join(tab_dir, item)
        if not os.path.isdir(item_path):
            continue

        try:
            shutil.rmtree(item_path)
            _log(_safe_format(u"Panel supprime : {}", item))
            count += 1
        except Exception as e:
            _log_error(_safe_format(u"Impossible de supprimer {} : {}", item, e))

    return count


# ==================================================================
#  POINT D'ENTREE PRINCIPAL
# ==================================================================

def main():
    """Point d'entree du script de deconnexion"""
    try:
        _safe_print(u"=" * 60)
        _safe_print(u"DEMARRAGE SCRIPT DE DECONNEXION")
        _safe_print(u"=" * 60)

        settings        = Settings()
        session_manager = SessionManager(settings.cache_dir)

        # -- Cas 1 : Pas de session active -------------------------
        if not session_manager.is_authenticated():
            forms.alert(
                u"Vous n'etes pas connecte.",
                title = u"AutoRevit"
            )
            return

        # -- Recuperer infos session avant suppression --------------
        try:
            session_data = session_manager.get_session()
            username     = _safe_str(session_data.get('username', u'Utilisateur'))
            role         = _safe_str(session_data.get('role', u''))
        except Exception:
            username = u'Utilisateur'
            role     = u''

        # -- Confirmation -------------------------------------------
        msg = _safe_format(
            u"Etes-vous sur de vouloir vous deconnecter ?\n\n"
            u"Utilisateur : {}\n"
            u"Role        : {}",
            username,
            role
        )

        result = forms.alert(
            msg,
            title = u"AutoRevit - Deconnexion",
            yes   = True,
            no    = True
        )

        if not result:
            _safe_print(u"Deconnexion annulee par l'utilisateur")
            return

        # -- Effacer la session -------------------------------------
        _log(_safe_format(u"Deconnexion de : {}", username))
        session_manager.clear_session()
        _log(u"Session effacee")

        # -- Supprimer les panels dynamiques -----------------------
        tab_dir   = os.path.dirname(os.path.dirname(script_dir))
        n_removed = _clear_dynamic_panels(tab_dir)
        _log(_safe_format(u"{} panels dynamiques supprimes", n_removed))

        # -- Supprimer le cache UI ----------------------------------
        cache_ui = os.path.join(settings.cache_dir, 'ui_config.json')
        if os.path.exists(cache_ui):
            try:
                os.remove(cache_ui)
                _log(u"Cache UI supprime")
            except Exception as e:
                _log_error(_safe_format(u"Impossible de supprimer cache UI : {}", e))

        # -- Message et rechargement --------------------------------
        forms.alert(
            _safe_format(
                u"Deconnexion reussie.\n\n"
                u"Au revoir {} !\n\n"
                u"pyRevit va se recharger...",
                username
            ),
            title = u"AutoRevit"
        )

        from pyrevit.loader import sessionmgr
        sessionmgr.reload_pyrevit()

    except Exception as e:
        _safe_print(_safe_format(u"ERREUR CRITIQUE : {}", e))
        _safe_print(_safe_traceback())

        forms.alert(
            _safe_format(
                u"Erreur lors de la deconnexion:\n\n{}",
                e
            ),
            title = u"AutoRevit - Erreur"
        )


if __name__ == '__main__':
    main()