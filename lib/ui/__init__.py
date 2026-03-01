# lib/ui/__init__.py
# -*- coding: utf-8 -*-
"""
UI - Interface utilisateur pour AutoRevit
==========================================
Gestion du ruban Revit et des commandes.
"""

# ✅ CORRIGÉ : Imports relatifs ou sans 
from ui.ribbon_builder  import RibbonBuilder


__all__ = [
    'RibbonBuilder',
    
]
__version__ = "3.0.0"