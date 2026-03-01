# -*- coding: utf-8 -*-
"""
utils/decorators.py

Decorateurs reutilisables pour l'extension AutoRevit.
Utilisation :
    from utils.decorators import transaction, log_execution, handle_exceptions

    @transaction("Nom de la transaction")
    def creer_poteaux(doc):
        ...

    @log_execution
    def calculer_section(force):
        ...
"""

import time
import functools

# Imports Revit (seulement quand necessaire)
try:
    from pyrevit import revit, forms
    from Autodesk.Revit.DB import Transaction
    REVIT_AVAILABLE = True
except ImportError:
    revit = None
    forms = None
    Transaction = None
    REVIT_AVAILABLE = False

# Imports internes
from utils.logger import get_logger

logger = get_logger(__name__)

# Exceptions personnalisees
class AutoRevitError(Exception):
    """Exception de base pour AutoRevit"""
    def __init__(self, message, details=None):
        super(AutoRevitError, self).__init__(message)
        self.details = details or {}

class RevitTransactionError(AutoRevitError):
    """Exception levee lors d'erreurs de transaction"""
    pass

class RevitDocumentError(AutoRevitError):
    """Exception levee lors d'erreurs de document"""
    pass

class UserCancelledError(AutoRevitError):
    """Exception levee quand l'utilisateur annule"""
    pass


def format_error_for_user(error):
    """Formate une erreur pour l'affichage utilisateur."""
    return str(error)


def transaction(name):
    """
    Decorateur pour encapsuler une fonction dans une Transaction Revit.
    - Cree une transaction avec le nom fourni
    - Commit si succes
    - Rollback + raise si erreur
    - Necessite que la fonction prenne 'doc' en premier argument ou utilise revit.doc
    
    Args:
        name: Nom de la transaction
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not REVIT_AVAILABLE or Transaction is None or revit is None:
                raise AutoRevitError("Transaction impossible : API Revit non disponible")

            # Recuperer le document Revit (premier arg ou revit.doc)
            doc = args[0] if args and hasattr(args[0], 'Create') else revit.doc
            if doc is None or doc.IsFamilyDocument:
                raise RevitDocumentError("Aucun document projet Revit actif")

            t_name = name if name else func.__name__.replace('_', ' ').title()
            t = Transaction(doc, "AutoRevit - " + t_name)

            try:
                t.Start()
                result = func(*args, **kwargs)
                t.Commit()
                logger.info("Transaction '" + t_name + "' commitee avec succes")
                return result
            except UserCancelledError as e:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                logger.info("Transaction annulee par utilisateur : " + str(e))
                raise
            except Exception as e:
                if t.HasStarted() and not t.HasEnded():
                    t.RollBack()
                logger.error("Transaction '" + t_name + "' rollback : " + str(e))
                raise RevitTransactionError("Echec transaction '" + t_name + "' : " + str(e))

        return wrapper
    return decorator


def log_execution(func):
    """
    Decorateur qui loggue l'execution d'une fonction :
    - Entree avec arguments
    - Temps d'execution
    - Resultat ou exception
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__

        # Log entree (evite de logger les gros objets)
        safe_args = [type(a).__name__ for a in args] if args else []
        safe_kwargs = list(kwargs.keys())
        logger.debug("-> " + func_name + " | args=" + str(safe_args) + " | kwargs=" + str(safe_kwargs))

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info("OK " + func_name + " terminee en " + "{:.3f}".format(duration) + "s | retour=" + type(result).__name__)
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error("ERREUR " + func_name + " echouee apres " + "{:.3f}".format(duration) + "s : " + str(e))
            raise

    return wrapper


def handle_exceptions(alert_user=True):
    """
    Decorateur pour catcher les exceptions et les traiter uniformement :
    - Loggue l'erreur
    - Affiche une alert pyRevit si demande
    - Releve une AutoRevitError si besoin
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AutoRevitError as e:
                logger.error(str(e))
                if alert_user and forms:
                    forms.alert(format_error_for_user(e), title="Erreur AutoRevit")
                raise
            except Exception as e:
                logger.error("Erreur non geree dans " + func.__name__ + " : " + str(e))
                if alert_user and forms:
                    forms.alert("Erreur inattendue :\n" + str(e), title="Erreur Critique")
                raise AutoRevitError("Erreur inattendue dans " + func.__name__, details={"original": str(e)})

        return wrapper

    return decorator


# Alias pour handle_exceptions avec message personnalise
def handle_errors(message="Erreur"):
    """
    Alias pour handle_exceptions avec un message personnalise.
    
    Usage:
        @handle_errors("Erreur lors de la creation")
        def ma_fonction():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(message + " : " + str(e))
                if forms:
                    forms.alert(message + " :\n" + str(e), title="Erreur AutoRevit")
                raise
        return wrapper
    return decorator


def revit_only(func):
    """
    Decorateur qui verifie qu'un document Revit projet est ouvert.
    Utile pour les fonctions qui interagissent avec l'API Revit.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not REVIT_AVAILABLE or revit is None or revit.doc is None:
            raise RevitDocumentError("Aucun document Revit actif")
        if revit.doc.IsFamilyDocument:
            raise RevitDocumentError("Operation interdite dans un document de famille (projet requis)")
        return func(*args, **kwargs)

    return wrapper


# Alias pratiques / variantes
transactional = transaction          # synonyme courant
logged = log_execution
safe_execution = handle_exceptions   # par defaut avec alert