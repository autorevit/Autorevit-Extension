# -*- coding: utf-8 -*-
"""
utils/constants.py

Constantes globales pour l'extension AutoRevit.
Centralise les valeurs fixes utilisees partout dans le code pour eviter la duplication
et faciliter la maintenance.

Categories :
- API ENDPOINTS : Routes backend Django
- MESSAGES UTILISATEUR : Textes alerts/toasts
- CODES ERREUR : Status HTTP, codes metier
- VALEURS PAR DEFAUT : Dimensions, tolerances, normes
- CHEMINS FICHIERS : Extensions, templates
- UI CONFIGURATION : Labels, icones, ordre panels
"""

# ==============================================================================
# VERSION & METADATA
# ==============================================================================

EXTENSION_NAME = "AutoRevit"
EXTENSION_VERSION = "1.0.0"
EXTENSION_AUTHOR = "Benjamin"
EXTENSION_DESCRIPTION = "Automatisation BIM pour Revit avec backend Django"

PYREVIT_MIN_VERSION = "4.8"
REVIT_SUPPORTED_VERSIONS = [2021, 2022, 2023, 2024, 2025]


# ==============================================================================
# API ENDPOINTS (relatifs a base_url)
# ==============================================================================

class APIEndpoints:
    """Routes API backend Django"""
    
    # Authentification
    LOGIN = "auth/login/"
    LOGOUT = "auth/logout/"
    REFRESH_TOKEN = "auth/refresh/"
    USER_PROFILE = "auth/profile/"
    
    # Configuration UI
    UI_CONFIG = "ui/user-config/"
    UI_PANELS = "ui/panels/"
    UI_BUTTONS = "ui/buttons/"
    
    # Normes & Regles
    NORMS = "norms/"
    NORM_SECTIONS = "norms/{norm_id}/sections/"
    DTU = "dtu/"
    BUILDING_CODES = "building-codes/"
    
    # Parametres
    PARAMETERS = "parameters/"
    PARAMETER_CATEGORIES = "parameters/categories/"
    PARAMETER_VALUES = "parameters/values/"
    SAFETY_FACTORS = "parameters/safety-factors/"
    
    # Materiaux
    CONCRETE_CLASSES = "materials/concrete/"
    STEEL_CLASSES = "materials/steel/"
    REINFORCEMENT_CLASSES = "materials/reinforcement/"
    
    # Sections
    SECTIONS = "sections/"
    SECTION_PROPERTIES = "sections/{section_id}/properties/"
    
    # Exposition
    EXPOSURE_CLASSES = "exposure/"
    
    # Actions Revit
    ACTIONS = "actions/"
    ACTION_EXECUTE = "actions/{action_id}/execute/"
    
    # Workflows
    WORKFLOWS = "workflows/"
    WORKFLOW_STEPS = "workflows/{workflow_id}/steps/"
    
    # Projets
    PROJECTS = "projects/"
    PROJECT_CONFIG = "projects/{project_id}/config/"
    PROJECT_ELEMENTS = "projects/{project_id}/elements/"
    
    # Formules
    FORMULAS = "formulas/"
    FORMULA_EVALUATE = "formulas/{formula_id}/evaluate/"
    
    # Templates
    TEMPLATES = "templates/"
    TEMPLATE_GENERATE = "templates/{template_id}/generate/"
    
    # Charges
    LOAD_CASES = "loads/cases/"
    LOAD_COMBINATIONS = "loads/combinations/"
    
    # Logs & Historique
    LOGS = "logs/"
    AUDIT_TRAIL = "audit/"
    
    # Sante systeme
    HEALTH = "health/"
    VERSION = "version/"


# ==============================================================================
# MESSAGES UTILISATEUR (francais par defaut)
# ==============================================================================

class Messages:
    """Messages standardises pour l'utilisateur"""
    
    # Bienvenue & Demarrage
    WELCOME = "Bienvenue dans {name} v{version} !"
    STARTUP_SUCCESS = "Extension chargee avec succes"
    STARTUP_FAILED = "Erreur lors du chargement de l'extension"
    
    # Authentification
    LOGIN_SUCCESS = "Connexion reussie - Bienvenue {username} !"
    LOGIN_FAILED = "Echec de connexion - Verifiez vos identifiants"
    LOGOUT_SUCCESS = "Deconnexion reussie"
    TOKEN_EXPIRED = "Session expiree - Veuillez vous reconnecter"
    NO_PERMISSION = "Vous n'avez pas les droits pour cette action"
    
    # Operations generales
    OPERATION_SUCCESS = "Operation terminee avec succes"
    OPERATION_CANCELLED = "Operation annulee par l'utilisateur"
    OPERATION_FAILED = "Echec de l'operation : {error}"
    
    # Connexion API
    API_CONNECTED = "Connexion au serveur etablie"
    API_DISCONNECTED = "Serveur inaccessible - Mode hors ligne active"
    API_TIMEOUT = "Le serveur met trop de temps a repondre"
    
    # Document Revit
    NO_DOCUMENT = "Aucun document Revit ouvert"
    DOCUMENT_IS_FAMILY = "Cette operation necessite un projet (pas une famille)"
    DOCUMENT_READONLY = "Document en lecture seule"
    
    # Elements Revit
    ELEMENT_CREATED = "{count} element(s) cree(s) avec succes"
    ELEMENT_MODIFIED = "{count} element(s) modifie(s)"
    ELEMENT_DELETED = "{count} element(s) supprime(s)"
    ELEMENT_NOT_FOUND = "Element introuvable : {name}"
    
    # Validation
    VALIDATION_ERROR = "Donnees invalides : {details}"
    PARAMETER_MISSING = "Parametre requis manquant : {param}"
    VALUE_OUT_OF_RANGE = "{param} doit etre entre {min} et {max}"
    
    # Workflow
    WORKFLOW_STEP_REQUIRED = "Completez d'abord l'etape {step_number} : {step_name}"
    WORKFLOW_COMPLETED = "Workflow termine avec succes !"
    
    # Fichiers
    FILE_NOT_FOUND = "Fichier introuvable : {path}"
    FILE_SAVE_SUCCESS = "Fichier sauvegarde : {path}"
    FILE_LOAD_FAILED = "Echec de chargement : {path}"


# ==============================================================================
# CODES ERREUR & STATUS
# ==============================================================================

class ErrorCodes:
    """Codes d'erreur metier"""
    
    # Codes HTTP standards
    HTTP_OK = 200
    HTTP_CREATED = 201
    HTTP_BAD_REQUEST = 400
    HTTP_UNAUTHORIZED = 401
    HTTP_FORBIDDEN = 403
    HTTP_NOT_FOUND = 404
    HTTP_TIMEOUT = 408
    HTTP_SERVER_ERROR = 500
    
    # Codes metier AutoRevit (1000-1999 : config/auth)
    INVALID_CONFIG = 1001
    MISSING_CONFIG_KEY = 1002
    CACHE_CORRUPTED = 1003
    
    AUTH_FAILED = 1100
    TOKEN_INVALID = 1101
    TOKEN_EXPIRED = 1102
    INSUFFICIENT_PERMISSIONS = 1103
    
    # Codes Revit (2000-2999)
    NO_DOCUMENT = 2001
    DOCUMENT_LOCKED = 2002
    TRANSACTION_FAILED = 2003
    ELEMENT_NOT_FOUND = 2004
    PARAMETER_READONLY = 2005
    
    # Codes metier (3000-3999)
    NORM_NOT_FOUND = 3001
    VALIDATION_FAILED = 3002
    CALCULATION_ERROR = 3003
    WORKFLOW_STEP_BLOCKED = 3004


# ==============================================================================
# VALEURS PAR DEFAUT METIER
# ==============================================================================

class Defaults:
    """Valeurs par defaut pour calculs et validations"""
    
    # Normes
    DEFAULT_NORM = "EC2"
    DEFAULT_COUNTRY = "FR"
    DEFAULT_LANGUAGE = "fr"
    
    # Unites (coherent avec config.json)
    LENGTH_UNIT = "mm"
    FORCE_UNIT = "kN"
    STRESS_UNIT = "MPa"
    AREA_UNIT = "m2"
    VOLUME_UNIT = "m3"
    
    # Materiaux par defaut
    DEFAULT_CONCRETE_CLASS = "C30/37"
    DEFAULT_STEEL_CLASS = "S500"
    DEFAULT_REINFORCEMENT = "HA"
    
    # Exposition
    DEFAULT_EXPOSURE_CLASS = "XC1"
    
    # Geometrie (mm)
    MIN_COLUMN_DIM = 200
    MAX_COLUMN_DIM = 1200
    MIN_BEAM_WIDTH = 150
    MIN_BEAM_HEIGHT = 250
    MIN_SLAB_THICKNESS = 120
    MIN_WALL_THICKNESS = 150
    
    # Enrobage (mm)
    DEFAULT_COVER = 30
    MIN_COVER = 20
    MAX_COVER = 80
    
    # Coefficients de securite (si non definis par norme)
    GAMMA_C = 1.5   # Beton
    GAMMA_S = 1.15  # Acier
    GAMMA_G = 1.35  # Charges permanentes
    GAMMA_Q = 1.50  # Charges variables
    
    # Tolerances calculs
    TOLERANCE_LENGTH = 1.0    # mm
    TOLERANCE_FORCE = 0.01    # kN
    TOLERANCE_STRESS = 0.1    # MPa


# ==============================================================================
# CHEMINS FICHIERS & EXTENSIONS
# ==============================================================================

class Paths:
    """Chemins relatifs a l'extension"""
    
    # Dossiers principaux
    LIB = "lib"
    UTILS = "utils"
    RESOURCES = "resources"
    ICONS = "resources/icons"
    TEMPLATES = "resources/templates"
    CACHE = "cache"
    LOGS = "logs"
    
    # Extensions fichiers
    REVIT_PROJECT = ".rvt"
    REVIT_FAMILY = ".rfa"
    REVIT_TEMPLATE = ".rte"
    DWG = ".dwg"
    IFC = ".ifc"
    
    # Fichiers config
    CONFIG_FILE = "config.json"
    TOKEN_CACHE = "cache/token.json"
    UI_CONFIG_CACHE = "cache/ui_config.json"
    
    # Templates de calcul
    CALC_TEMPLATE_COLUMN = "templates/column_calc.json"
    CALC_TEMPLATE_BEAM = "templates/beam_calc.json"
    CALC_TEMPLATE_SLAB = "templates/slab_calc.json"
    CALC_TEMPLATE_FOUNDATION = "templates/foundation_calc.json"


# ==============================================================================
# CONFIGURATION UI (RUBAN REVIT)
# ==============================================================================

class UIConfig:
    """Configuration interface utilisateur pyRevit"""
    
    # Nom du tab principal
    TAB_NAME = "AutoRevit"
    
    # Noms des 8 panels (selon workflow)
    PANEL_PROJECT = "01 - Projet"
    PANEL_ANALYSIS = "02 - Analyse"
    PANEL_LOADS = "03 - Charges"
    PANEL_STRUCTURE = "04 - Structure"
    PANEL_SECONDARY = "05 - Secondaire"
    PANEL_VERIFICATION = "06 - Verification"
    PANEL_REINFORCEMENT = "07 - Ferraillage"
    PANEL_DOCUMENTATION = "08 - Documentation"
    
    # Tailles icones (pixels)
    ICON_SIZE_LARGE = 32
    ICON_SIZE_MEDIUM = 16
    ICON_SIZE_SMALL = 16
    
    # Types de boutons
    BUTTON_TYPE_PUSH = "push"
    BUTTON_TYPE_SPLIT = "split"
    BUTTON_TYPE_PULLDOWN = "pulldown"
    BUTTON_TYPE_STACK = "stack"


# ==============================================================================
# ROLES & PERMISSIONS
# ==============================================================================

class Roles:
    """Codes roles utilisateurs (coherent avec backend)"""
    
    ADMIN = "ADMIN"
    ENGINEER = "ING"
    DRAFTER = "DESS"
    READER = "LECTEUR"
    
    # Mapping permissions (exemple)
    PERMISSIONS = {
        ADMIN: ["all"],
        ENGINEER: ["calculate", "verify", "design", "export"],
        DRAFTER: ["model", "document", "view"],
        READER: ["view"]
    }


# ==============================================================================
# WORKFLOW STEPS
# ==============================================================================

class WorkflowSteps:
    """Etapes du workflow projet (coherent avec backend)"""
    
    STEP_1_PROJECT = 1       # Projet & Initialisation
    STEP_2_ANALYSIS = 2      # Analyse & Diagnostic
    STEP_3_LOADS = 3         # Charges & Combinaisons
    STEP_4_STRUCTURE = 4     # Structure Principale
    STEP_5_SECONDARY = 5     # Elements Secondaires
    STEP_6_VERIFICATION = 6  # Verification & Qualite
    STEP_7_REINFORCEMENT = 7 # Ferraillage & Coffrage
    STEP_8_DOCUMENTATION = 8 # Documentation & Export
    
    STEP_NAMES = {
        STEP_1_PROJECT: "Projet & Initialisation",
        STEP_2_ANALYSIS: "Analyse & Diagnostic",
        STEP_3_LOADS: "Charges & Combinaisons",
        STEP_4_STRUCTURE: "Structure Principale",
        STEP_5_SECONDARY: "Elements Secondaires",
        STEP_6_VERIFICATION: "Verification & Qualite",
        STEP_7_REINFORCEMENT: "Ferraillage & Coffrage",
        STEP_8_DOCUMENTATION: "Documentation & Export"
    }


# ==============================================================================
# FORMATS & PATTERNS
# ==============================================================================

class Formats:
    """Formats de donnees standards"""
    
    # Dates
    DATE_FORMAT = "%Y-%m-%d"
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    LOG_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
    
    # Numeriques
    DECIMAL_SEPARATOR = "."
    THOUSANDS_SEPARATOR = " "
    PRECISION_LENGTH = 2    # decimales pour longueurs
    PRECISION_FORCE = 3     # decimales pour forces
    PRECISION_STRESS = 2    # decimales pour contraintes
    
    # Nomenclature
    LEVEL_PREFIX = "N"          # N+0.00, N+3.50
    GRID_PREFIX = "AXE"         # AXE-A, AXE-1
    COLUMN_PREFIX = "P"         # P1, P2
    BEAM_PREFIX = "PO"          # PO1, PO2
    WALL_PREFIX = "V"           # V1, V2
    SLAB_PREFIX = "D"           # D1, D2
    FOUNDATION_PREFIX = "F"     # F1, F2


# ==============================================================================
# CACHE & PERFORMANCE
# ==============================================================================

class CacheConfig:
    """Configuration du cache local"""
    
    # Durees de validite (secondes)
    TOKEN_VALIDITY = 3600           # 1 heure
    UI_CONFIG_VALIDITY = 86400      # 24 heures
    NORM_DATA_VALIDITY = 604800     # 7 jours
    MATERIAL_VALIDITY = 604800      # 7 jours
    
    # Tailles limites (octets)
    MAX_CACHE_SIZE = 100 * 1024 * 1024   # 100 MB
    MAX_SINGLE_FILE = 10 * 1024 * 1024   # 10 MB
    
    # Cleanup
    AUTO_CLEANUP_ENABLED = True
    CLEANUP_INTERVAL = 86400        # 1 jour


# ==============================================================================
# HELPERS (fonctions utilitaires pour acces rapide)
# ==============================================================================

def get_endpoint(endpoint_name, **kwargs):
    """
    Recupere une URL d'endpoint avec remplacement de parametres.
    Exemple : get_endpoint('NORM_SECTIONS', norm_id=42)
    """
    endpoint = getattr(APIEndpoints, endpoint_name, None)
    if endpoint and kwargs:
        return endpoint.format(**kwargs)
    return endpoint


def get_message(message_name, **kwargs):
    """
    Recupere un message avec remplacement de variables.
    Exemple : get_message('WELCOME', name='AutoRevit', version='1.0.0')
    """
    message = getattr(Messages, message_name, "")
    if message and kwargs:
        return message.format(**kwargs)
    return message


# ==============================================================================
# TESTS (si execute directement)
# ==============================================================================

if __name__ == "__main__":
    print("=== AutoRevit Constants ===")
    print("Version : " + str(EXTENSION_VERSION))
    print("API Login endpoint : " + str(APIEndpoints.LOGIN))
    print("Message bienvenue : " + get_message('WELCOME', name=EXTENSION_NAME, version=EXTENSION_VERSION))
    print("Endpoint norme sections (norme 5) : " + get_endpoint('NORM_SECTIONS', norm_id=5))