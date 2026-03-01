# -*- coding: utf-8 -*-
"""
Models - Modèles de données locaux pour AutoRevit
==================================================
Représentations Python des données manipulées dans l'extension.
Ces modèles sont des classes simples (pas de base de données)
qui facilitent la manipulation des données provenant de l'API.
Auteur : AutoRevit Team
Date : 2025
"""
try:
    from .action import Action
    ACTION_AVAILABLE = True
except ImportError as e:
    ACTION_AVAILABLE = False
    Action = None
    print("Warning: action non disponible - " + str(e))

try:
    from .workflow import Workflow, WorkflowStep
    WORKFLOW_AVAILABLE = True
except ImportError as e:
    WORKFLOW_AVAILABLE = False
    Workflow     = None
    WorkflowStep = None
    print("Warning: workflow non disponible - " + str(e))

try:
    from .parameter import Parameter, ParameterValue
    PARAMETER_AVAILABLE = True
except ImportError as e:
    PARAMETER_AVAILABLE = False
    Parameter      = None
    ParameterValue = None
    print("Warning: parameter non disponible - " + str(e))

try:
    from .rule import Rule, RuleSet, RuleCondition
    RULE_AVAILABLE = True
except ImportError as e:
    RULE_AVAILABLE = False
    Rule          = None
    RuleSet       = None
    RuleCondition = None
    print("Warning: rule non disponible - " + str(e))

__all__ = [
    'Action',
    'Workflow',
    'WorkflowStep',
    'Parameter',
    'ParameterValue',
    'Rule',
    'RuleSet',
    'RuleCondition',
]