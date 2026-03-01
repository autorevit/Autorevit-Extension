# -*- coding: utf-8 -*-
"""Config - Configuration centralisee"""

try:
    from .settings import Settings
    SETTINGS_AVAILABLE = True
except ImportError as e:
    print("Warning: Settings non disponible - " + str(e))
    SETTINGS_AVAILABLE = False
    Settings = None

try:
    from .api_client import (
        APIClient,
        APIError,
        APIConnectionError,
        APIAuthenticationError,
        APIPermissionError,
        APINotFoundError,
        APIResponseError,
        APITimeoutError,
        OfflineModeRestrictedError,
    )
    API_CLIENT_AVAILABLE = True
except ImportError as e:
    print("Warning: APIClient non disponible - " + str(e))
    API_CLIENT_AVAILABLE = False
    APIClient                  = None
    APIError                   = None
    APIConnectionError         = None
    APIAuthenticationError     = None
    APIPermissionError         = None
    APINotFoundError           = None
    APIResponseError           = None
    APITimeoutError            = None
    OfflineModeRestrictedError = None

# Singletons
_settings   = None
_api_client = None

def get_settings():
    global _settings
    if _settings is None and SETTINGS_AVAILABLE:
        try:
            _settings = Settings()
        except Exception as e:
            print("Erreur creation Settings: " + str(e))
    return _settings

def get_api_client():
    global _api_client
    if _api_client is None and API_CLIENT_AVAILABLE:
        try:
            s = get_settings()
            if s:
                _api_client = APIClient(s)
        except Exception as e:
            print("Erreur creation APIClient: " + str(e))
    return _api_client

# Auto-init
settings   = get_settings()
api_client = get_api_client()

__all__ = [
    # Classes principales
    'Settings',
    'APIClient',
    # Exceptions
    'APIError',
    'APIConnectionError',
    'APIAuthenticationError',
    'APIPermissionError',
    'APINotFoundError',
    'APIResponseError',
    'APITimeoutError',
    'OfflineModeRestrictedError',
    # Helpers
    'get_settings',
    'get_api_client',
    'settings',
    'api_client',
]