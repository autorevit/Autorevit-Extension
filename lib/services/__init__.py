try:
    from .revit_service import RevitService
    REVIT_SERVICE_AVAILABLE = True
except ImportError as e:
    RevitService = None
    REVIT_SERVICE_AVAILABLE = False
    print("Warning: RevitService non disponible - " + str(e))

try:
    from .geometry_service import GeometryService
    GEOMETRY_SERVICE_AVAILABLE = True
except ImportError as e:
    GeometryService = None
    GEOMETRY_SERVICE_AVAILABLE = False
    print("Warning: GeometryService non disponible - " + str(e))

try:
    from .parameters_service import ParametersService
    PARAMETERS_SERVICE_AVAILABLE = True
except ImportError as e:
    ParametersService = None
    PARAMETERS_SERVICE_AVAILABLE = False
    print("Warning: ParametersService non disponible - " + str(e))

try:
    from .selection_service import SelectionService
    SELECTION_SERVICE_AVAILABLE = True
except ImportError as e:
    SelectionService = None
    SELECTION_SERVICE_AVAILABLE = False
    print("Warning: SelectionService non disponible - " + str(e))

try:
    from .transaction_service import TransactionService, TransactionContext
    TRANSACTION_SERVICE_AVAILABLE = True
except ImportError as e:
    TransactionService = None
    TransactionContext = None
    TRANSACTION_SERVICE_AVAILABLE = False
    print("Warning: TransactionService non disponible - " + str(e))

try:
    from .logging_service import LoggingService
    LOGGING_SERVICE_AVAILABLE = True
except ImportError as e:
    LoggingService = None
    LOGGING_SERVICE_AVAILABLE = False
    print("Warning: LoggingService non disponible - " + str(e))

__all__ = []
if REVIT_SERVICE_AVAILABLE:      __all__.append('RevitService')
if GEOMETRY_SERVICE_AVAILABLE:   __all__.append('GeometryService')
if PARAMETERS_SERVICE_AVAILABLE: __all__.append('ParametersService')
if SELECTION_SERVICE_AVAILABLE:  __all__.append('SelectionService')
if TRANSACTION_SERVICE_AVAILABLE: __all__ += ['TransactionService', 'TransactionContext']
if LOGGING_SERVICE_AVAILABLE:    __all__.append('LoggingService')
__version__ = "1.0.0"