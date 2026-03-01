# -*- coding: utf-8 -*-
"""
utils/exceptions.py

Exceptions personnalisees pour l'extension AutoRevit.
Toutes les erreurs specifiques au projet doivent heriter de AutoRevitError
pour un traitement uniforme (logs, alerts, messages utilisateur clairs).
"""


class AutoRevitError(Exception):
    """
    Classe de base pour toutes les exceptions specifiques a AutoRevit.
    Permet de catcher les erreurs metier de maniere ciblee.
    """
    def __init__(self, message="Une erreur inattendue s'est produite dans AutoRevit", details=None):
        self.message = message
        self.details = details or {}
        Exception.__init__(self, self.message)

    def __str__(self):
        if self.details:
            return str(self.message) + " | Details : " + str(self.details)
        return str(self.message)


# ------------------------------------------------------------------------------
# Erreurs de configuration et environnement
# ------------------------------------------------------------------------------

class ConfigurationError(AutoRevitError):
    """Erreur de configuration (config.json invalide, dossier manquant, parametre obligatoire absent)"""
    pass


class CacheError(AutoRevitError):
    """Probleme avec le cache local (lecture/ecriture/expiration/corruption)"""
    pass


class OfflineModeRestrictedError(AutoRevitError):
    """Fonctionnalite non disponible en mode offline"""
    def __init__(self, feature_name="cette fonctionnalite"):
        AutoRevitError.__init__(
            self,
            str(feature_name) + " n'est pas disponible en mode hors-ligne. Veuillez vous connecter a l'API."
        )


# ------------------------------------------------------------------------------
# Erreurs liees a l'API backend / reseau
# ------------------------------------------------------------------------------

class APIConnectionError(AutoRevitError):
    """Impossible de contacter le serveur API (reseau, timeout, serveur down)"""
    def __init__(self, url=None, original_exc=None):
        msg = "Impossible de se connecter a l'API AutoRevit"
        if url:
            msg += " (" + str(url) + ")"
        if original_exc:
            msg += " - " + str(original_exc)
        AutoRevitError.__init__(self, msg)


class APIAuthenticationError(AutoRevitError):
    """Echec d'authentification (token invalide/expire, mauvais credentials, 401)"""
    def __init__(self, message="Echec d'authentification - Veuillez vous reconnecter"):
        AutoRevitError.__init__(self, message)


class APIPermissionError(AutoRevitError):
    """L'utilisateur n'a pas les droits necessaires pour cette action (403)"""
    pass


class APIResponseError(AutoRevitError):
    """Reponse API invalide ou erreur serveur (JSON mal forme, 500, etc.)"""
    def __init__(self, status_code=None, message="Reponse invalide du serveur"):
        msg = str(message)
        if status_code:
            msg += " (HTTP " + str(status_code) + ")"
        AutoRevitError.__init__(self, msg)


class APITimeoutError(APIConnectionError):
    """Timeout specifique lors d'une requete longue"""
    pass


# ------------------------------------------------------------------------------
# Erreurs liees a l'API Revit / document actif
# ------------------------------------------------------------------------------

class RevitAPIError(AutoRevitError):
    """Erreur generale lors de l'utilisation de l'API Revit"""
    pass


class RevitTransactionError(AutoRevitError):
    """Erreur pendant une Transaction Revit (rollback force, document verrouille, etc.)"""
    pass


class RevitDocumentError(AutoRevitError):
    """Probleme avec le document Revit actif (pas de projet ouvert, famille ouverte, etc.)"""
    pass


class RevitElementNotFoundError(AutoRevitError):
    """Element Revit attendu introuvable (niveau, grille, famille, parametre partage, etc.)"""
    pass


class RevitParameterError(AutoRevitError):
    """Probleme avec un parametre Revit (inexistant, type incorrect, lecture seule)"""
    pass


# ------------------------------------------------------------------------------
# Erreurs metier / validation donnees
# ------------------------------------------------------------------------------

class ValidationError(AutoRevitError):
    """Donnees invalides selon regles metier (ex. : section poteau trop petite, charge negative)"""
    pass


class NormNotFoundError(AutoRevitError):
    """Norme, DTU ou reglement demande non trouve ou non actif"""
    pass


class WorkflowStepError(AutoRevitError):
    """Action interdite a l'etape actuelle du workflow projet"""
    pass


# ------------------------------------------------------------------------------
# Erreurs liees a l'utilisateur / interaction
# ------------------------------------------------------------------------------

class UserCancelledError(AutoRevitError):
    """L'utilisateur a annule l'operation (bouton Annuler, fermeture dialog)"""
    def __init__(self, message="Operation annulee par l'utilisateur"):
        AutoRevitError.__init__(self, message)


class InputValidationError(AutoRevitError):
    """Valeur saisie par l'utilisateur invalide (dans un formulaire)"""
    pass


# ------------------------------------------------------------------------------
# Helpers utiles pour gerer les exceptions uniformement
# ------------------------------------------------------------------------------

def format_error_for_user(exc):
    """Formate un message propre pour forms.alert() ou toast"""
    if isinstance(exc, AutoRevitError):
        return str(exc)
    return "Erreur inattendue : " + str(exc)


def is_critical(exc):
    """Determine si l'erreur merite une alerte bloquante (et non juste un log)"""
    return isinstance(exc, (
        APIAuthenticationError,
        RevitTransactionError,
        RevitDocumentError,
        ConfigurationError,
    ))