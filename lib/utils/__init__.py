# -*- coding: utf-8 -*-
"""
Utils - Utilitaires generaux pour l'extension AutoRevit
Auteur : AutoRevit Team - Date : 2025
"""

__version__ = "1.0.0"

# ── logger (import direct, pas conditionnel — c'est la base) ──────────
from .logger import get_logger, AutoRevitLogger

# ── exceptions ────────────────────────────────────────────────────────
try:
    from .exceptions import (
        AutoRevitError,
        ConfigurationError,
        CacheError,
        OfflineModeRestrictedError,
        APIConnectionError,
        APIAuthenticationError,
        APIPermissionError,
        APIResponseError,
        APITimeoutError,
        RevitTransactionError,
        RevitDocumentError,
        RevitElementNotFoundError,
        RevitParameterError,
        ValidationError,
        NormNotFoundError,
        WorkflowStepError,
        UserCancelledError,
        InputValidationError,
        format_error_for_user,
        is_critical
    )
    EXCEPTIONS_AVAILABLE = True
except ImportError:
    EXCEPTIONS_AVAILABLE = False
    class AutoRevitError(Exception):
        pass

# ── decorators ────────────────────────────────────────────────────────
try:
    from .decorators import (
        transaction, transactional, log_execution, logged,
        handle_exceptions, safe_execution, revit_only, handle_errors
    )
    DECORATORS_AVAILABLE = True
except ImportError:
    DECORATORS_AVAILABLE = False
    def transaction(func):      return func
    def transactional(func):    return func
    def log_execution(func):    return func
    def logged(func):           return func
    def handle_exceptions(alert_user=True):
        def decorator(func): return func
        return decorator
    def safe_execution(alert_user=True):
        def decorator(func): return func
        return decorator
    def revit_only(func):       return func
    def handle_errors(message="Erreur"):
        def decorator(func): return func
        return decorator

# ── constants ─────────────────────────────────────────────────────────
try:
    from .constants import (
        EXTENSION_NAME, EXTENSION_VERSION, EXTENSION_AUTHOR,
        EXTENSION_DESCRIPTION, PYREVIT_MIN_VERSION, REVIT_SUPPORTED_VERSIONS,
        APIEndpoints, Messages, ErrorCodes, Defaults, Paths,
        UIConfig, Roles, WorkflowSteps, Formats, CacheConfig,
        get_endpoint, get_message
    )
    CONSTANTS_AVAILABLE = True
except ImportError:
    CONSTANTS_AVAILABLE = False

# ── __all__ ───────────────────────────────────────────────────────────
__all__ = [
    'get_logger', 'AutoRevitLogger',
    'transaction', 'transactional', 'log_execution', 'logged',
    'handle_exceptions', 'safe_execution', 'revit_only', 'handle_errors',
]

if EXCEPTIONS_AVAILABLE:
    __all__ += [
        'AutoRevitError', 'ConfigurationError', 'CacheError',
        'OfflineModeRestrictedError', 'APIConnectionError', 'APIAuthenticationError',
        'APIPermissionError', 'APIResponseError', 'APITimeoutError',
        'RevitTransactionError', 'RevitDocumentError', 'RevitElementNotFoundError',
        'RevitParameterError', 'ValidationError', 'NormNotFoundError',
        'WorkflowStepError', 'UserCancelledError', 'InputValidationError',
        'format_error_for_user', 'is_critical',
    ]
else:
    __all__.append('AutoRevitError')

if CONSTANTS_AVAILABLE:
    __all__ += [
        'EXTENSION_NAME', 'EXTENSION_VERSION', 'EXTENSION_AUTHOR',
        'EXTENSION_DESCRIPTION', 'PYREVIT_MIN_VERSION', 'REVIT_SUPPORTED_VERSIONS',
        'APIEndpoints', 'Messages', 'ErrorCodes', 'Defaults', 'Paths',
        'UIConfig', 'Roles', 'WorkflowSteps', 'Formats', 'CacheConfig',
        'get_endpoint', 'get_message',
    ]

# ── fonctions utilitaires ─────────────────────────────────────────────
def get_version():
    return __version__

def test_logger():
    logger = get_logger("utils.test")
    logger.debug("Test debug")
    logger.info("Test info")
    logger.warning("Test warning")
    logger.error("Test error")
    return "Logger OK"

def test_exceptions():
    try:
        raise ValidationError("Test") if EXCEPTIONS_AVAILABLE else AutoRevitError("Test")
    except AutoRevitError as e:
        return str(e)
    except Exception as e:
        return "Erreur inattendue: " + str(e)

_initialized = False
def _init():
    global _initialized
    if not _initialized:
        _initialized = True
_init()