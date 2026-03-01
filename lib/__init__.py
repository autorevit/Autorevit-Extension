# -*- coding: utf-8 -*-
"""
AutoRevit - Extension d'automatisation BIM pour Revit
=======================================================
Solution complete d'automatisation des processus structurels
pour Revit, avec backend Django et extension pyRevit.

Architecture :
    - config      : Configuration et client API
    - core        : Moteurs metier principaux
    - models      : Modeles de donnees locaux
    - algorithms  : Algorithmes de placement et dimensionnement
    - services    : Services d'interaction avec Revit
    - helpers     : Fonctions utilitaires
    - utils       : Utilitaires generaux (logger, exceptions, decorators)

Auteur : AutoRevit Team
Date : 2025
Version : 1.0.0
"""

__version__ = "1.0.0"
__author__ = "AutoRevit Team"
__license__ = "Proprietaire - Tous droits reserves"

# ========================================================================
# Imports depuis config (singletons essentiels)
# ========================================================================
from config import settings, api_client, get_settings, get_api_client

# ========================================================================
# Imports depuis core (moteurs principaux)
# ========================================================================
from core import (
    # Gestion des donnees
    DataManager,
    
    # Moteurs d'execution
    RulesEngine,
    CreationEngine,
    VerificationEngine,
    DocumentationEngine,
    CalculationEngine
)

# Import conditionnel de ExecutionEngine
try:
    from core import ExecutionEngine
    EXECUTION_ENGINE_AVAILABLE = True
except ImportError:
    ExecutionEngine = None
    EXECUTION_ENGINE_AVAILABLE = False

# ========================================================================
# Imports depuis models (representations locales)
# ========================================================================
from models import (
    Action,
    Workflow,
    WorkflowStep,
    Parameter,
    ParameterValue,
    Rule,
    RuleSet,
    RuleCondition
)

# ========================================================================
# Imports depuis algorithms (intelligence metier)
# ========================================================================
from algorithms import (
    # Engines de placement
    ColumnPlacementEngine,
    BeamPlacementEngine,
    SlabPlacementEngine,
    WallPlacementEngine,
    FoundationPlacementEngine,
    SecondaryElementsEngine,
    StairPlacementEngine,
    ShaftPlacementEngine,
    
    # Utilitaires geometriques
    calculate_grid_intersections,
    find_intermediate_points,
    detect_rectangular_bays,
    calculate_distance,
    is_point_on_line,
    offset_point,
    get_rectangle_from_points,
    sort_points_clockwise,
    calculate_centroid,
    
    # Calculateurs dimensionnels
    calculate_beam_height,
    calculate_slab_thickness,
    calculate_column_section,
    calculate_foundation_dimensions,
    calculate_reinforcement_ratio,
    
    # Analyse geometrique
    GeometryAnalyzer,
    
    # Validateurs
    validate_positive_number,
    validate_range,
    validate_in_list,
    validate_required_params
)

# ========================================================================
# Imports depuis services (interactions Revit)
# ========================================================================
from services import (
    RevitService,
    GeometryService,
    ParametersService,
    SelectionService,
    TransactionService,
    LoggingService
)

# ========================================================================
# Imports depuis helpers (utilitaires rapides)
# ========================================================================
from helpers import (
    # Revit helpers
    get_active_document,
    get_revit_version,
    get_all_levels,
    get_all_grids,
    get_all_columns,
    get_all_beams,
    get_all_walls,
    get_all_floors,
    
    # Conversion unites
    mm_to_feet,
    feet_to_mm,
    m_to_feet,
    feet_to_m,
    
    # Geometrie
    distance_between_points,
    midpoint,
    centroid,
    create_line,
    
    # UI
    alert,
    confirm,
    select_from_list,
    ProgressBar,
    show_message_box,
    show_error_dialog,
    show_warning_dialog,
    
    # Validation
    validate_concrete_class,
    validate_steel_class,
    validate_exposure_class,
    validate_dimension,
    validate_load
)

# ========================================================================
# Imports depuis utils (si disponibles - optionnel)
# ========================================================================
try:
    from utils import setup_logger, AutoRevitException
    __all_utils_available = True
except ImportError:
    __all_utils_available = False

# ========================================================================
# Interface publique - Ce qui est accessible directement depuis lib
# ========================================================================
__all__ = [
    # Configuration
    'settings',
    'api_client',
    'get_settings',
    'get_api_client',
    
    # Core - Moteurs
    'DataManager',
    'RulesEngine',
    'CreationEngine',
    'VerificationEngine',
    'DocumentationEngine',
    'CalculationEngine',
    
    # Models
    'Action',
    'Workflow',
    'WorkflowStep',
    'Parameter',
    'ParameterValue',
    'Rule',
    'RuleSet',
    'RuleCondition',
    
    # Algorithms - Placement
    'ColumnPlacementEngine',
    'BeamPlacementEngine',
    'SlabPlacementEngine',
    'WallPlacementEngine',
    'FoundationPlacementEngine',
    'SecondaryElementsEngine',
    'StairPlacementEngine',
    'ShaftPlacementEngine',
    
    # Algorithms - Utilitaires geometriques
    'calculate_grid_intersections',
    'find_intermediate_points',
    'detect_rectangular_bays',
    'calculate_distance',
    'is_point_on_line',
    'offset_point',
    'get_rectangle_from_points',
    'sort_points_clockwise',
    'calculate_centroid',
    
    # Algorithms - Calculateurs
    'calculate_beam_height',
    'calculate_slab_thickness',
    'calculate_column_section',
    'calculate_foundation_dimensions',
    'calculate_reinforcement_ratio',
    
    # Algorithms - Analyse
    'GeometryAnalyzer',
    
    # Algorithms - Validateurs
    'validate_positive_number',
    'validate_range',
    'validate_in_list',
    'validate_required_params',
    
    # Services
    'RevitService',
    'GeometryService',
    'ParametersService',
    'SelectionService',
    'TransactionService',
    'LoggingService',
    
    # Helpers - Revit
    'get_active_document',
    'get_revit_version',
    'get_all_levels',
    'get_all_grids',
    'get_all_columns',
    'get_all_beams',
    'get_all_walls',
    'get_all_floors',
    
    # Helpers - Conversion
    'mm_to_feet',
    'feet_to_mm',
    'm_to_feet',
    'feet_to_m',
    
    # Helpers - Geometrie
    'distance_between_points',
    'midpoint',
    'centroid',
    'create_line',
    
    # Helpers - UI
    'alert',
    'confirm',
    'select_from_list',
    'ProgressBar',
    'show_message_box',
    'show_error_dialog',
    'show_warning_dialog',
    
    # Helpers - Validation metier
    'validate_concrete_class',
    'validate_steel_class',
    'validate_exposure_class',
    'validate_dimension',
    'validate_load',
]

# Ajouter ExecutionEngine si disponible
if EXECUTION_ENGINE_AVAILABLE:
    __all__.append('ExecutionEngine')

# ========================================================================
# Informations sur l'extension
# ========================================================================

def get_version():
    """Retourne la version de l'extension."""
    return __version__

def get_info():
    """Retourne les informations completes sur l'extension."""
    return {
        'name': 'AutoRevit',
        'version': __version__,
        'author': __author__,
        'license': __license__,
        'description': 'Extension d\'automatisation BIM pour Revit',
        'modules': [m for m in __all__ if not m.startswith('_')][:10] + ['...']
    }

# ========================================================================
# Initialisation rapide - Fonctions de commodite
# ========================================================================

def quick_start():
    """
    Initialisation rapide de l'extension.
    
    Returns:
        dict: Elements essentiels prets a l'emploi
    """
    return {
        'settings': settings,
        'api': api_client,
        'revit': get_active_document() if 'get_active_document' in dir() else None
    }

def is_revit_available():
    """
    Verifie si Revit est disponible.
    
    Returns:
        bool: True si Revit API accessible
    """
    try:
        from pyrevit import revit
        return revit.doc is not None
    except:
        return False

# ========================================================================
# Docstring d'exemple - Utilisation typique
# ========================================================================

"""
Exemple d'utilisation typique :
------------------------------

>>> import lib
>>> 
>>> # 1. Verifier la version
>>> print(__version__)
'1.0.0'
>>> 
>>> # 2. Acceder a la configuration
>>> from lib import settings, api_client
>>> print(settings.api_url)
'http://localhost:8000/api/v1'
>>> 
>>> # 3. Utiliser un moteur
>>> from lib import DataManager
>>> data_mgr = DataManager(api_client)
>>> norms = data_mgr.get_norms()
>>> 
>>> # 4. Utiliser un helper
>>> from lib import mm_to_feet, alert
>>> alert("Projet charge avec succes !")
"""