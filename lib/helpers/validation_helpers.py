# -*- coding: utf-8 -*-
"""
GenericValidators - Validateurs generiques pour donnees
========================================================
Fonctions de validation pour types, plages, formats, etc.

Auteur : AutoRevit Team
Date : 2025
"""

import re
import math
from typing import Any, Dict, List, Tuple, Optional, Union

from utils.logger import get_logger

logger = get_logger(__name__)


# ========================================================================
# VALIDATEURS DE TYPE
# ========================================================================

def validate_positive_number(value, allow_zero=False, allow_float=True):
    """Valide un nombre positif."""
    try:
        if allow_float:
            num = float(value)
        else:
            num = int(value)
        
        if num < 0:
            return False, "La valeur doit être positive (reçu: " + str(num) + ")"
        
        if not allow_zero and num == 0:
            return False, "La valeur doit être non nulle"
        
        return True, "OK"
    except (ValueError, TypeError):
        return False, "Valeur non numérique: " + str(value)


def validate_integer(value, min_value=None, max_value=None):
    """Valide un entier dans une plage."""
    try:
        num = int(value)
        
        if min_value is not None and num < min_value:
            return False, "Valeur minimale: " + str(min_value) + " (reçu: " + str(num) + ")"
        
        if max_value is not None and num > max_value:
            return False, "Valeur maximale: " + str(max_value) + " (reçu: " + str(num) + ")"
        
        return True, "OK"
    except (ValueError, TypeError):
        return False, "Valeur non entière: " + str(value)


def validate_float(value, min_value=None, max_value=None, precision=None):
    """Valide un flottant dans une plage."""
    try:
        num = float(value)
        
        if min_value is not None and num < min_value:
            return False, "Valeur minimale: " + str(min_value) + " (reçu: " + str(num) + ")"
        
        if max_value is not None and num > max_value:
            return False, "Valeur maximale: " + str(max_value) + " (reçu: " + str(num) + ")"
        
        if precision is not None:
            str_num = str(num)
            if '.' in str_num:
                decimals = len(str_num.split('.')[1])
                if decimals > precision:
                    return False, "Maximum " + str(precision) + " décimales (reçu: " + str(decimals) + ")"
        
        return True, "OK"
    except (ValueError, TypeError):
        return False, "Valeur non numérique: " + str(value)


def validate_string(value, min_length=None, max_length=None, not_empty=True):
    """Valide une chaine de caracteres."""
    if not isinstance(value, basestring):
        try:
            value = str(value)
        except:
            return False, "Valeur non convertible en chaîne: " + str(type(value))
    
    if not_empty and not value.strip():
        return False, "Chaîne vide non autorisée"
    
    length = len(value.strip())
    
    if min_length is not None and length < min_length:
        return False, "Longueur minimale: " + str(min_length) + " (reçu: " + str(length) + ")"
    
    if max_length is not None and length > max_length:
        return False, "Longueur maximale: " + str(max_length) + " (reçu: " + str(length) + ")"
    
    return True, "OK"


def validate_boolean(value):
    """Valide un booleen."""
    if isinstance(value, bool):
        return True, "OK"
    
    if isinstance(value, (int, float)):
        return value in (0, 1), "Booléen attendu (0/1), reçu: " + str(value)
    
    if isinstance(value, basestring):
        return value.lower() in ('true', 'false', '1', '0', 'yes', 'no'), \
               "Booléen attendu, reçu: " + value
    
    return False, "Type booléen attendu, reçu: " + str(type(value).__name__)


def validate_list(value, min_length=None, max_length=None, item_type=None):
    """Valide une liste."""
    if not isinstance(value, (list, tuple)):
        return False, "Liste attendue, reçu: " + str(type(value).__name__)
    
    length = len(value)
    
    if min_length is not None and length < min_length:
        return False, "Longueur minimale: " + str(min_length) + " (reçu: " + str(length) + ")"
    
    if max_length is not None and length > max_length:
        return False, "Longueur maximale: " + str(max_length) + " (reçu: " + str(length) + ")"
    
    if item_type is not None:
        for i, item in enumerate(value):
            if not isinstance(item, item_type):
                return False, "Élément " + str(i) + ": type " + item_type.__name__ + " attendu, reçu: " + str(type(item).__name__)
    
    return True, "OK"


def validate_dict(value, required_keys=None, optional_keys=None):
    """Valide un dictionnaire."""
    if not isinstance(value, dict):
        return False, "Dictionnaire attendu, reçu: " + str(type(value).__name__)
    
    if required_keys:
        for key in required_keys:
            if key not in value:
                return False, "Clé obligatoire manquante: " + key
    
    if optional_keys:
        all_keys = set(required_keys or []) | set(optional_keys)
        extra_keys = set(value.keys()) - all_keys
        if extra_keys:
            return False, "Clés non autorisées: " + str(list(extra_keys))
    
    return True, "OK"


# ========================================================================
# VALIDATEURS DE PLAGE
# ========================================================================

def validate_range(value, min_val, max_val, inclusive=True):
    """Valide qu'une valeur est dans une plage."""
    valid, msg = validate_float(value)
    if not valid:
        return valid, msg
    
    if inclusive:
        if value < min_val or value > max_val:
            return False, "Valeur hors plage [" + str(min_val) + ", " + str(max_val) + "] (reçu: " + str(value) + ")"
    else:
        if value <= min_val or value >= max_val:
            return False, "Valeur hors plage ]" + str(min_val) + ", " + str(max_val) + "[ (reçu: " + str(value) + ")"
    
    return True, "OK"


def validate_step(value, base, step):
    """Valide qu'une valeur est un multiple d'un pas."""
    valid, msg = validate_float(value)
    if not valid:
        return valid, msg
    
    diff = value - base
    remainder = diff % step
    
    if abs(remainder) > 0.0001:
        return False, "Valeur doit être multiple de " + str(step) + " (base " + str(base) + ")"
    
    return True, "OK"


def validate_percentage(value, allow_zero=True):
    """Valide un pourcentage (0-100)."""
    valid, msg = validate_float(value, 0, 100)
    if not valid:
        return valid, msg
    
    if not allow_zero and value == 0:
        return False, "Pourcentage nul non autorisé"
    
    return True, "OK"


# ========================================================================
# VALIDATEURS DE FORMAT
# ========================================================================

def validate_code(code, pattern=r'^[A-Z0-9_\-]+$'):
    """Valide un code (majuscules, chiffres, _, -)."""
    valid, msg = validate_string(code, min_length=1)
    if not valid:
        return valid, msg
    
    if not re.match(pattern, code):
        return False, "Format de code invalide: " + code
    
    return True, "OK"


def validate_email(email):
    """Valide une adresse email."""
    valid, msg = validate_string(email, min_length=5)
    if not valid:
        return valid, msg
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(pattern, email):
        return False, "Format d'email invalide: " + email
    
    return True, "OK"


def validate_phone(phone):
    """Valide un numero de telephone."""
    valid, msg = validate_string(phone, min_length=10)
    if not valid:
        return valid, msg
    
    # Enlever les separateurs
    cleaned = re.sub(r'[\s\-\.\(\)]', '', phone)
    
    if not cleaned.isdigit():
        return False, "Caractères non numériques: " + phone
    
    if len(cleaned) < 10 or len(cleaned) > 12:
        return False, "Longueur téléphone invalide: " + str(len(cleaned)) + " chiffres"
    
    return True, "OK"


def validate_url(url):
    """Valide une URL."""
    valid, msg = validate_string(url, min_length=5)
    if not valid:
        return valid, msg
    
    pattern = r'^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$'
    
    if not re.match(pattern, url, re.IGNORECASE):
        return False, "Format d'URL invalide: " + url
    
    return True, "OK"


def validate_filename(filename):
    """Valide un nom de fichier."""
    valid, msg = validate_string(filename, min_length=1)
    if not valid:
        return valid, msg
    
    # Caracteres interdits dans les noms de fichiers
    forbidden = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    
    for char in forbidden:
        if char in filename:
            return False, "Caractère interdit '" + char + "' dans le nom de fichier"
    
    return True, "OK"


# ========================================================================
# VALIDATEURS DE COHERENCE
# ========================================================================

def validate_required_params(params, required):
    """Verifie que tous les parametres requis sont presents."""
    missing = [key for key in required if key not in params]
    
    if missing:
        return False, "Paramètres requis manquants: " + str(missing), missing
    
    return True, "OK", []


def validate_dependency(value1, value2, condition="eq"):
    """Verifie une dependance entre deux valeurs."""
    try:
        if condition == "eq":
            valid = value1 == value2
            msg = "Doit être égal à " + str(value2)
        elif condition == "ne":
            valid = value1 != value2
            msg = "Doit être différent de " + str(value2)
        elif condition == "gt":
            valid = float(value1) > float(value2)
            msg = "Doit être > " + str(value2)
        elif condition == "lt":
            valid = float(value1) < float(value2)
            msg = "Doit être < " + str(value2)
        elif condition == "ge":
            valid = float(value1) >= float(value2)
            msg = "Doit être ≥ " + str(value2)
        elif condition == "le":
            valid = float(value1) <= float(value2)
            msg = "Doit être ≤ " + str(value2)
        else:
            return False, "Condition inconnue: " + condition
        
        if not valid:
            return False, msg + " (reçu: " + str(value1) + ")"
        
        return True, "OK"
    except (ValueError, TypeError) as e:
        return False, "Erreur de comparaison: " + str(e)


def validate_consistency(validation_results):
    """Agrege plusieurs validations."""
    errors = []
    
    for valid, msg in validation_results:
        if not valid:
            errors.append(msg)
    
    return len(errors) == 0, errors


# ========================================================================
# VALIDATEURS METIER
# ========================================================================

def validate_dimension(value, unit="mm", min_val=None, max_val=None, step=None):
    """Valide une dimension structurelle."""
    # Convertir en mm
    if unit == "cm":
        value_mm = value * 10
    elif unit == "m":
        value_mm = value * 1000
    else:
        value_mm = value
    
    if min_val is None:
        min_val = 100
    
    if max_val is None:
        max_val = 2000
    
    valid, msg = validate_range(value_mm, min_val, max_val)
    if not valid:
        return valid, msg
    
    if step is not None:
        valid, msg = validate_step(value_mm, 0, step)
        if not valid:
            return valid, msg
    
    return True, "OK"


def validate_load(value, unit="kN", min_val=None, max_val=None):
    """Valide une charge structurelle."""
    if min_val is None:
        min_val = 0
    
    if max_val is None:
        if u"m²" in unit:
            max_val = 50
        elif u"m" in unit:
            max_val = 100
        else:
            max_val = 10000
    
    return validate_range(value, min_val, max_val)


def validate_concrete_class(concrete_class):
    """Valide une classe de beton (C25/30, etc.)."""
    valid, msg = validate_string(concrete_class)
    if not valid:
        return valid, msg
    
    pattern = r'^C\d{2}/\d{2,3}$'
    
    if not re.match(pattern, concrete_class):
        return False, "Format classe béton invalide: " + concrete_class
    
    match = re.match(r'^C(\d+)/(\d+)$', concrete_class)
    if match:
        fck = int(match.group(1))
        fck_cube = int(match.group(2))
        
        if fck_cube < fck:
            return False, "Résistance sur cube (" + str(fck_cube) + ") < résistance cylindre (" + str(fck) + ")"
        
        if fck not in [12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 70, 80, 90]:
            return False, "Classe de béton non standard: C" + str(fck)
    
    return True, "OK"


def validate_steel_class(steel_class):
    """Valide une classe d'acier (B500B, etc.)."""
    valid, msg = validate_string(steel_class)
    if not valid:
        return valid, msg
    
    pattern = r'^B\d{3}[A-C]$'
    
    if not re.match(pattern, steel_class):
        return False, "Format classe acier invalide: " + steel_class
    
    return True, "OK"


def validate_exposure_class(exposure_class):
    """Valide une classe d'exposition (XC1, XF1, etc.)."""
    valid, msg = validate_string(exposure_class)
    if not valid:
        return valid, msg
    
    pattern = r'^(XC|XD|XS|XF|XA)[1-4]$'
    
    if not re.match(pattern, exposure_class):
        return False, "Format classe exposition invalide: " + exposure_class
    
    return True, "OK"


# ========================================================================
# VALIDATION DE FORMULAIRE
# ========================================================================

def validate_form_input(data, schema):
    """
    Valide les donnees d'un formulaire selon un schema.
    
    Args:
        data (dict): Donnees du formulaire
        schema (dict): Schema de validation
    
    Returns:
        tuple: (is_valid, errors_dict)
    """
    errors = {}
    
    for field, rules in schema.items():
        value = data.get(field)
        field_name = rules.get('label', field)
        
        # Champ requis
        if rules.get('required', False):
            if value is None or (isinstance(value, basestring) and not value.strip()):
                errors[field] = field_name + " est requis"
                continue
        
        if value is not None and value != '':
            field_type = rules.get('type', 'string')
            
            if field_type == 'number':
                valid, msg = validate_positive_number(value, 
                                                     allow_zero=rules.get('allow_zero', False))
                if not valid:
                    errors[field] = msg
            
            elif field_type == 'integer':
                min_val = rules.get('min')
                max_val = rules.get('max')
                valid, msg = validate_integer(value, min_val, max_val)
                if not valid:
                    errors[field] = msg
            
            elif field_type == 'float':
                min_val = rules.get('min')
                max_val = rules.get('max')
                valid, msg = validate_float(value, min_val, max_val)
                if not valid:
                    errors[field] = msg
            
            elif field_type == 'string':
                min_len = rules.get('min_length')
                max_len = rules.get('max_length')
                valid, msg = validate_string(value, min_len, max_len)
                if not valid:
                    errors[field] = msg
            
            elif field_type == 'email':
                valid, msg = validate_email(value)
                if not valid:
                    errors[field] = msg
            
            elif field_type == 'phone':
                valid, msg = validate_phone(value)
                if not valid:
                    errors[field] = msg
            
            elif field_type == 'code':
                pattern = rules.get('pattern', r'^[A-Z0-9_\-]+$')
                valid, msg = validate_code(value, pattern)
                if not valid:
                    errors[field] = msg
            
            choices = rules.get('choices')
            if choices and value not in choices:
                errors[field] = field_name + " doit être parmi " + str(choices)
    
    return len(errors) == 0, errors


# Schema de validation pour projet
PROJECT_SCHEMA = {
    'code': {
        'label': 'Code projet',
        'type': 'code',
        'required': True,
        'min_length': 3,
        'max_length': 20,
        'pattern': r'^[A-Z0-9_\-]+$'
    },
    'name': {
        'label': 'Nom du projet',
        'type': 'string',
        'required': True,
        'min_length': 3,
        'max_length': 100
    },
    'client': {
        'label': 'Client',
        'type': 'string',
        'required': True,
        'min_length': 2
    },
    'norm': {
        'label': 'Norme',
        'type': 'string',
        'required': True,
        'choices': ['EC2', 'BAEL91', 'EC8', 'ACI318']
    },
    'floor_count': {
        'label': 'Nombre de niveaux',
        'type': 'integer',
        'required': True,
        'min': 1,
        'max': 50
    }
}


def format_validation_errors(errors):
    """Formate les erreurs de validation pour affichage."""
    if not errors:
        return "Validation réussie"
    
    lines = ["❌ Erreurs de validation:"]
    for field, error in errors.items():
        lines.append("  • " + field + ": " + error)
    
    return "\n".join(lines)


# ========================================================================
# FONCTION DE TEST
# ========================================================================

def test_generic_validators():
    print("\n" + "="*60)
    print("TEST GENERIC VALIDATORS")
    print("="*60)
    
    print("\n1 Validation type:")
    valid, msg = validate_positive_number(10)
    print("   Nombre positif 10: " + ("OK" if valid else msg))
    
    valid, msg = validate_integer(5, 1, 10)
    print("   Entier 5 [1-10]: " + ("OK" if valid else msg))
    
    valid, msg = validate_string("Test", 3, 10)
    print("   Chaine 'Test': " + ("OK" if valid else msg))
    
    print("\n2 Validation format:")
    valid, msg = validate_code("EC2_2004")
    print("   Code 'EC2_2004': " + ("OK" if valid else msg))
    
    valid, msg = validate_email("test@autorevit.com")
    print("   Email 'test@autorevit.com': " + ("OK" if valid else msg))
    
    print("\n3 Validation metier:")
    valid, msg = validate_concrete_class("C25/30")
    print("   Beton C25/30: " + ("OK" if valid else msg))
    
    valid, msg = validate_steel_class("B500B")
    print("   Acier B500B: " + ("OK" if valid else msg))
    
    print("\n" + "="*60)
    print("TEST TERMINE")
    print("="*60 + "\n")


if __name__ == '__main__':
    test_generic_validators()