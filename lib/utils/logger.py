# -*- coding: utf-8 -*-
"""
utils/logger.py
Module de logging centralise pour l'extension AutoRevit

Fonctionnalites principales :
- Logger unique par nom (singleton-like)
- Niveaux : DEBUG, INFO, WARNING, ERROR, CRITICAL
- Sortie console (pyRevit output / stdout)
- Sortie fichier : un fichier par jour (autorevit_YYYYMMDD.log)
- Rotation manuelle simple (pas de taille pour l'instant, un fichier/jour)
- Format lisible avec timestamp, niveau, nom du logger, message
- Compatible avec config.json (log_level, logs_dir, max_log_size_mb)
- Methodes pratiques : success, fail, etc.
"""

import os
import sys
import json
import datetime
from io import open as io_open  # pour compatibilite encodage

# Pour eviter les imports circulaires, on ne depend pas encore de settings ici
# On lira config.json directement si besoin (fallback valeurs par defaut)

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
DEFAULT_MAX_SIZE_MB = 50


class AutoRevitLogger:
    """
    Logger principal de l'extension AutoRevit.
    Utilisation recommandee :
        from utils.logger import get_logger
        logger = get_logger("MonModule")
        logger.info("Message normal")
        logger.debug("Detail technique")
        logger.error("Probleme detecte", exc_info=True)
    """

    _loggers = {}  # Cache des instances pour eviter doublons

    def __init__(self, name="AutoRevit"):
        self.name = name
        self.level = self._get_level_from_config()
        self.logs_dir = self._get_logs_dir_from_config()
        self.max_size_mb = self._get_max_size_from_config()

        # Creation dossier logs si inexistant (compatible IronPython / Python 2)
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)

        # Fichier du jour
        today = datetime.date.today().strftime("%Y%m%d")
        self.log_file = os.path.join(self.logs_dir, "autorevit_" + today + ".log")

        # Verification taille (rotation tres basique)
        self._check_and_rotate_if_needed()

    def _get_level_from_config(self):
        """Lit log_level depuis config.json ou fallback"""
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
            if os.path.exists(config_path):
                with io_open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                level_str = config.get("log_level", DEFAULT_LOG_LEVEL).upper()
                levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
                return levels.get(level_str, 20)
        except:
            pass
        return 20  # INFO par defaut

    def _get_logs_dir_from_config(self):
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
            if os.path.exists(config_path):
                with io_open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config.get("logs_dir", DEFAULT_LOGS_DIR)
        except:
            pass
        return DEFAULT_LOGS_DIR

    def _get_max_size_from_config(self):
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
            if os.path.exists(config_path):
                with io_open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return config.get("max_log_size_mb", DEFAULT_MAX_SIZE_MB) * 1024 * 1024  # en bytes
        except:
            pass
        return DEFAULT_MAX_SIZE_MB * 1024 * 1024

    def _check_and_rotate_if_needed(self):
        """Rotation tres simple : si fichier trop gros -> renomme avec timestamp"""
        if not os.path.exists(self.log_file):
            return

        size = os.path.getsize(self.log_file)
        if size > self.max_size_mb:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = self.log_file.replace(".log", "_" + timestamp + ".log")
            try:
                os.rename(self.log_file, new_name)
            except:
                pass  # silencieux, on continue avec l'ancien

    def _format_message(self, level, message):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return "[" + ts + "] [" + "{0:8}".format(level) + "] [" + "{0:20}".format(self.name) + "] " + str(message)

    def _log(self, level_num, level_name, message, exc_info=False):
        if level_num < self.level:
            return

        formatted = self._format_message(level_name, message)

        # Console (pyRevit output)
        print(formatted)

        # Fichier
        try:
            with io_open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(formatted + "\n")
                if exc_info:
                    import traceback
                    tb = traceback.format_exc()
                    if tb:
                        f.write(tb + "\n")
        except Exception as e:
            print("[LOGGER ERROR] Impossible d'ecrire dans le log: " + str(e))

    def debug(self, message, exc_info=False):
        self._log(10, "DEBUG", message, exc_info)

    def info(self, message, exc_info=False):
        self._log(20, "INFO ", message, exc_info)

    def warning(self, message, exc_info=False):
        self._log(30, "WARN ", message, exc_info)

    def error(self, message, exc_info=False):
        self._log(40, "ERROR", message, exc_info)

    def critical(self, message, exc_info=False):
        self._log(50, "CRIT ", message, exc_info)

    # Alias pratiques
    def success(self, message):
        self.info("[OK] " + str(message))

    def fail(self, message):
        self.error("[FAIL] " + str(message))


# ----------------------------------------------------------------------------
# Fonction d'acces globale (recommandee)
# ----------------------------------------------------------------------------
def get_logger(name="AutoRevit"):
    """
    Recupere ou cree un logger avec le nom donne.
    Usage : logger = get_logger(__name__)  # ou "MonModule.SousModule"
    """
    if name not in AutoRevitLogger._loggers:
        AutoRevitLogger._loggers[name] = AutoRevitLogger(name)
    return AutoRevitLogger._loggers[name]


# Pour tests directs (python utils/logger.py)
if __name__ == "__main__":
    logger = get_logger("TestLogger")
    logger.debug("Ceci est un debug")
    logger.info("Information normale")
    logger.warning("Attention quelque chose")
    logger.error("Erreur exemple", exc_info=True)
    logger.critical("Probleme critique !")
    logger.success("Operation reussie")
    logger.fail("Echec de l'operation")