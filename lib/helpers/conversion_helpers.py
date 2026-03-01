# -*- coding: utf-8 -*-
"""
ConversionHelpers - Fonctions de conversion d'unites
=====================================================
Conversions pour longueurs, forces, pressions, surfaces, volumes, etc.

Auteur : AutoRevit Team
Date : 2025
"""

import math
from utils.logger import get_logger

logger = get_logger(__name__)


# ========================================================================
# LONGUEURS
# ========================================================================

def mm_to_cm(mm):
    """Millimetres -> Centimetres."""
    return mm / 10.0


def cm_to_mm(cm):
    """Centimetres -> Millimetres."""
    return cm * 10.0


def m_to_mm(m):
    """Metres -> Millimetres."""
    return m * 1000.0


def mm_to_m(mm):
    """Millimetres -> Metres."""
    return mm / 1000.0


def m_to_cm(m):
    """Metres -> Centimetres."""
    return m * 100.0


def cm_to_m(cm):
    """Centimetres -> Metres."""
    return cm / 100.0


def km_to_m(km):
    """Kilometres -> Metres."""
    return km * 1000.0


def m_to_km(m):
    """Metres -> Kilometres."""
    return m / 1000.0


def inches_to_mm(inches):
    """Pouces -> Millimetres."""
    return inches * 25.4


def mm_to_inches(mm):
    """Millimetres -> Pouces."""
    return mm / 25.4


def feet_to_inches(feet):
    """Feet -> Pouces."""
    return feet * 12.0


def inches_to_feet(inches):
    """Pouces -> Feet."""
    return inches / 12.0


# ========================================================================
# FORCES
# ========================================================================

def kn_to_n(kn):
    """Kilonewtons -> Newtons."""
    return kn * 1000.0


def n_to_kn(n):
    """Newtons -> Kilonewtons."""
    return n / 1000.0


def kn_to_lbs(kn):
    """Kilonewtons -> Livres-force."""
    return kn * 224.808943


def lbs_to_kn(lbs):
    """Livres-force -> Kilonewtons."""
    return lbs / 224.808943


def kn_to_kgf(kn):
    """Kilonewtons -> Kilogrammes-force."""
    return kn * 101.971621


def kgf_to_kn(kgf):
    """Kilogrammes-force -> Kilonewtons."""
    return kgf / 101.971621


def t_to_kn(t):
    """Tonnes -> Kilonewtons."""
    return t * 9.80665


def kn_to_t(kn):
    """Kilonewtons -> Tonnes."""
    return kn / 9.80665


# ========================================================================
# PRESSIONS
# ========================================================================

def mpa_to_kpa(mpa):
    """Megapascals -> Kilopascals."""
    return mpa * 1000.0


def kpa_to_mpa(kpa):
    """Kilopascals -> Megapascals."""
    return kpa / 1000.0


def mpa_to_pa(mpa):
    """Megapascals -> Pascals."""
    return mpa * 1000000.0


def pa_to_mpa(pa):
    """Pascals -> Megapascals."""
    return pa / 1000000.0


def mpa_to_psi(mpa):
    """Megapascals -> PSI (livres par pouce carre)."""
    return mpa * 145.037738


def psi_to_mpa(psi):
    """PSI -> Megapascals."""
    return psi / 145.037738


def mpa_to_bar(mpa):
    """Megapascals -> Bars."""
    return mpa * 10.0


def bar_to_mpa(bar):
    """Bars -> Megapascals."""
    return bar / 10.0


def mpa_to_kgf_cm2(mpa):
    """Megapascals -> kgf/cm²."""
    return mpa * 10.197162


def kgf_cm2_to_mpa(kgf_cm2):
    """kgf/cm² -> Megapascals."""
    return kgf_cm2 / 10.197162


def kpa_to_kgf_m2(kpa):
    """Kilopascals -> kgf/m²."""
    return kpa * 101.971621


def kgf_m2_to_kpa(kgf_m2):
    """kgf/m² -> Kilopascals."""
    return kgf_m2 / 101.971621


# ========================================================================
# SURFACES
# ========================================================================

def m2_to_cm2(m2):
    """Metres carres -> Centimetres carres."""
    return m2 * 10000.0


def cm2_to_m2(cm2):
    """Centimetres carres -> Metres carres."""
    return cm2 / 10000.0


def m2_to_mm2(m2):
    """Metres carres -> Millimetres carres."""
    return m2 * 1000000.0


def mm2_to_m2(mm2):
    """Millimetres carres -> Metres carres."""
    return mm2 / 1000000.0


def ha_to_m2(ha):
    """Hectares -> Metres carres."""
    return ha * 10000.0


def m2_to_ha(m2):
    """Metres carres -> Hectares."""
    return m2 / 10000.0


def km2_to_m2(km2):
    """Kilometres carres -> Metres carres."""
    return km2 * 1000000.0


def m2_to_km2(m2):
    """Metres carres -> Kilometres carres."""
    return m2 / 1000000.0


def sqft_to_m2(sqft):
    """Pieds carres -> Metres carres."""
    return sqft * 0.092903


def m2_to_sqft(m2):
    """Metres carres -> Pieds carres."""
    return m2 / 0.092903


# ========================================================================
# VOLUMES
# ========================================================================

def m3_to_l(m3):
    """Metres cubes -> Litres."""
    return m3 * 1000.0


def l_to_m3(l):
    """Litres -> Metres cubes."""
    return l / 1000.0


def m3_to_cm3(m3):
    """Metres cubes -> Centimetres cubes."""
    return m3 * 1000000.0


def cm3_to_m3(cm3):
    """Centimetres cubes -> Metres cubes."""
    return cm3 / 1000000.0


def m3_to_mm3(m3):
    """Metres cubes -> Millimetres cubes."""
    return m3 * 1000000000.0


def mm3_to_m3(mm3):
    """Millimetres cubes -> Metres cubes."""
    return mm3 / 1000000000.0


def l_to_gal(l):
    """Litres -> Gallons US."""
    return l * 0.264172


def gal_to_l(gal):
    """Gallons US -> Litres."""
    return gal / 0.264172


def cuft_to_m3(cuft):
    """Pieds cubes -> Metres cubes."""
    return cuft * 0.028317


def m3_to_cuft(m3):
    """Metres cubes -> Pieds cubes."""
    return m3 / 0.028317


# ========================================================================
# MASSES
# ========================================================================

def kg_to_t(kg):
    """Kilogrammes -> Tonnes."""
    return kg / 1000.0


def t_to_kg(t):
    """Tonnes -> Kilogrammes."""
    return t * 1000.0


def kg_to_lbs(kg):
    """Kilogrammes -> Livres."""
    return kg * 2.20462


def lbs_to_kg(lbs):
    """Livres -> Kilogrammes."""
    return lbs / 2.20462


def g_to_kg(g):
    """Grammes -> Kilogrammes."""
    return g / 1000.0


def kg_to_g(kg):
    """Kilogrammes -> Grammes."""
    return kg * 1000.0


# ========================================================================
# TEMPERATURES
# ========================================================================

def celsius_to_fahrenheit(c):
    """Celsius -> Fahrenheit."""
    return (c * 9/5) + 32


def fahrenheit_to_celsius(f):
    """Fahrenheit -> Celsius."""
    return (f - 32) * 5/9


def celsius_to_kelvin(c):
    """Celsius -> Kelvin."""
    return c + 273.15


def kelvin_to_celsius(k):
    """Kelvin -> Celsius."""
    return k - 273.15


# ========================================================================
# ANGLES
# ========================================================================

def deg_to_rad(deg):
    """Degres -> Radians."""
    return deg * math.pi / 180.0


def rad_to_deg(rad):
    """Radians -> Degres."""
    return rad * 180.0 / math.pi


def grad_to_deg(grad):
    """Grades -> Degres."""
    return grad * 0.9


def deg_to_grad(deg):
    """Degres -> Grades."""
    return deg / 0.9


# ========================================================================
# FORMATAGE
# ========================================================================

def format_mm_to_m(mm, decimals=2):
    """
    Formate des millimetres en metres.
    
    Args:
        mm (float): Millimetres
        decimals (int): Nombre de decimales
    
    Returns:
        str: "{value} m"
    """
    m = mm_to_m(mm)
    return "{:,.{dec}f} m".format(m, dec=decimals).replace(',', ' ')


def format_mm_to_cm(mm, decimals=1):
    """
    Formate des millimetres en centimetres.
    
    Args:
        mm (float): Millimetres
        decimals (int): Nombre de decimales
    
    Returns:
        str: "{value} cm"
    """
    cm = mm_to_cm(mm)
    return "{:,.{dec}f} cm".format(cm, dec=decimals).replace(',', ' ')


def format_area_m2(m2, decimals=2):
    """
    Formate une surface en m².
    
    Args:
        m2 (float): Metres carres
        decimals (int): Nombre de decimales
    
    Returns:
        str: "{value} m²"
    """
    return "{:,.{dec}f} m²".format(m2, dec=decimals).replace(',', ' ')


def format_volume_m3(m3, decimals=2):
    """
    Formate un volume en m³.
    
    Args:
        m3 (float): Metres cubes
        decimals (int): Nombre de decimales
    
    Returns:
        str: "{value} m³"
    """
    return "{:,.{dec}f} m³".format(m3, dec=decimals).replace(',', ' ')


def format_load_kN(kn, decimals=1):
    """
    Formate une charge en kN.
    
    Args:
        kn (float): Kilonewtons
        decimals (int): Nombre de decimales
    
    Returns:
        str: "{value} kN"
    """
    return "{:,.{dec}f} kN".format(kn, dec=decimals).replace(',', ' ')


def format_pressure_MPa(mpa, decimals=2):
    """
    Formate une pression en MPa.
    
    Args:
        mpa (float): Megapascals
        decimals (int): Nombre de decimales
    
    Returns:
        str: "{value} MPa"
    """
    return "{:,.{dec}f} MPa".format(mpa, dec=decimals).replace(',', ' ')


def format_percentage(value, decimals=1):
    """
    Formate un pourcentage.
    
    Args:
        value (float): Valeur (0-100)
        decimals (int): Nombre de decimales
    
    Returns:
        str: "{value}%"
    """
    return "{:,.{dec}f}%".format(value, dec=decimals).replace(',', ' ')


# ========================================================================
# FONCTION DE TEST
# ========================================================================

def test_conversion_helpers():
    print("\n" + "="*60)
    print("TEST CONVERSION HELPERS")
    print("="*60)
    
    print("\n1 Longueurs:")
    print("   1000 mm = " + format_mm_to_m(1000))
    print("   2.5 m = " + str(int(m_to_mm(2.5))) + " mm")
    
    print("\n2 Forces:")
    print("   100 kN = " + str(int(kn_to_n(100))) + " N")
    print("   50 kN = " + str(round(kn_to_lbs(50), 1)) + " lbs")
    
    print("\n3 Pressions:")
    print("   25 MPa = " + str(round(mpa_to_psi(25), 1)) + " psi")
    print("   0.2 MPa = " + str(round(mpa_to_kgf_cm2(0.2), 2)) + " kgf/cm²")
    
    print("\n4 Surfaces:")
    print("   100 m² = " + format_area_m2(100))
    print("   50 m² = " + str(int(m2_to_sqft(50))) + " sqft")
    
    print("\n5 Volumes:")
    print("   2.5 m³ = " + format_volume_m3(2.5))
    print("   1000 L = " + str(round(l_to_m3(1000), 2)) + " m³")
    
    print("\n" + "="*60)
    print("TEST TERMINE")
    print("="*60 + "\n")


if __name__ == '__main__':
    test_conversion_helpers()