try:
    from .data_manager import DataManager
    DATA_MANAGER_AVAILABLE = True
except ImportError as e:
    DataManager = None
    DATA_MANAGER_AVAILABLE = False
    print("Warning: DataManager non disponible - " + str(e))

try:
    from .rules_engine import RulesEngine
    RULES_ENGINE_AVAILABLE = True
except ImportError as e:
    RulesEngine = None
    RULES_ENGINE_AVAILABLE = False
    print("Warning: RulesEngine non disponible - " + str(e))

try:
    from .creation_engine import CreationEngine
    CREATION_ENGINE_AVAILABLE = True
except ImportError as e:
    CreationEngine = None
    CREATION_ENGINE_AVAILABLE = False
    print("Warning: CreationEngine non disponible - " + str(e))

try:
    from .verification_engine import VerificationEngine
    VERIFICATION_ENGINE_AVAILABLE = True
except ImportError as e:
    VerificationEngine = None
    VERIFICATION_ENGINE_AVAILABLE = False
    print("Warning: VerificationEngine non disponible - " + str(e))

try:
    from .documentation_engine import DocumentationEngine
    DOCUMENTATION_ENGINE_AVAILABLE = True
except ImportError as e:
    DocumentationEngine = None
    DOCUMENTATION_ENGINE_AVAILABLE = False
    print("Warning: DocumentationEngine non disponible - " + str(e))


try:
    from .execution_engine import ExecutionEngine
    EXECUTION_ENGINE_AVAILABLE = True
except ImportError as e:
    ExecutionEngine = None
    EXECUTION_ENGINE_AVAILABLE = False
    print("Warning: ExecutionEngine non disponible - " + str(e))

__all__ = []
if DATA_MANAGER_AVAILABLE:      __all__.append('DataManager')
if RULES_ENGINE_AVAILABLE:      __all__.append('RulesEngine')
if CREATION_ENGINE_AVAILABLE:   __all__.append('CreationEngine')
if VERIFICATION_ENGINE_AVAILABLE: __all__.append('VerificationEngine')
if DOCUMENTATION_ENGINE_AVAILABLE: __all__.append('DocumentationEngine')

if EXECUTION_ENGINE_AVAILABLE:  __all__.append('ExecutionEngine')
__version__ = "1.0.0"