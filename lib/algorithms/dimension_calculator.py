# -*- coding: utf-8 -*-
"""Calculateur de dimensions pour éléments structurels

Formules de calcul pour :
- Poutres : hauteur selon portée, largeur selon hauteur
- Poteaux : section selon charge et hauteur
- Dalles : épaisseur selon portée
- Fondations : dimensions selon charge et sol
- Ferraillage : sections d'acier minimales
"""

from __future__ import division, print_function
import math


# Classe pour simuler Enum (compatible IronPython 2.7)
class StructuralElementType:
    """Types d'éléments structurels"""
    BEAM = "poutre"
    COLUMN = "poteau"
    SLAB = "dalle"
    WALL = "voile"
    FOOTING = "semelle"
    STRIP_FOOTING = "semelle_filante"
    RAFT = "radier"


class MaterialType:
    """Types de matériaux"""
    CONCRETE = "beton"
    STEEL = "acier"
    REINFORCEMENT = "armature"


# ---------------------------------------------------------------------
# 1. POUTRES
# ---------------------------------------------------------------------

def calculate_beam_height(span_m, 
                         beam_type="PRINCIPALE",
                         slab_thickness_mm=0):
    """
    Calcule la hauteur d'une poutre selon sa portée.
    
    Règles :
    - Principale : L/8 à L/12 (défaut L/9)
    - Secondaire : = hauteur dalle
    - Raidisseur : = hauteur dalle (carré)
    - Plate : L/15 à L/20 (défaut L/17)
    
    Args:
        span_m: Portée en mètres
        beam_type: Type de poutre (PRINCIPALE, SECONDAIRE, RAIDISSEUR, PLATE)
        slab_thickness_mm: Épaisseur dalle pour poutres secondaires
        
    Returns:
        Hauteur en mm
    """
    beam_type_upper = beam_type.upper()
    
    if beam_type_upper == "PRINCIPALE" or beam_type_upper == "PRIMARY":
        # L/8 à L/12, défaut L/9
        height_mm = (span_m / 9.0) * 1000
        
    elif beam_type_upper == "SECONDAIRE" or beam_type_upper == "SECONDARY":
        # Égale à hauteur dalle
        return max(200, slab_thickness_mm)
        
    elif beam_type_upper == "RAIDISSEUR" or beam_type_upper == "STIFFENER":
        # Carré = hauteur dalle
        return max(200, slab_thickness_mm)
        
    elif beam_type_upper == "PLATE" or beam_type_upper == "FLAT":
        # L/15 à L/20, défaut L/17
        height_mm = (span_m / 17.0) * 1000
        
    else:
        # Par défaut: poutre courante L/12
        height_mm = (span_m / 12.0) * 1000
    
    # Arrondir au multiple de 50 mm
    height_mm = int(round(height_mm / 50)) * 50
    
    # Hauteur minimale
    height_mm = max(200, height_mm)
    
    return height_mm


def calculate_beam_width(height_mm, 
                        beam_type="PRINCIPALE"):
    """
    Calcule la largeur d'une poutre selon sa hauteur.
    
    Règles :
    - Largeur = 0.3 à 0.5 × hauteur
    - Largeur minimale : 150 mm
    - Raidisseur : carré (largeur = hauteur)
    - Plate : largeur > hauteur
    
    Args:
        height_mm: Hauteur de la poutre
        beam_type: Type de poutre
        
    Returns:
        Largeur en mm
    """
    beam_type_upper = beam_type.upper()
    
    if beam_type_upper == "RAIDISSEUR" or beam_type_upper == "STIFFENER":
        # Section carrée
        width_mm = height_mm
        
    elif beam_type_upper == "PLATE" or beam_type_upper == "FLAT":
        # Largeur > hauteur
        width_mm = int(height_mm * 1.5)
        
    else:
        # Largeur = 40% de hauteur
        width_mm = int(height_mm * 0.4)
    
    # Arrondir au multiple de 50 mm
    width_mm = int(round(width_mm / 50)) * 50
    
    # Largeur minimale
    width_mm = max(150, width_mm)
    
    return width_mm


def calculate_beam_reinforcement(width_mm, 
                               height_mm,
                               concrete_class="C25/30",
                               steel_class="B500B"):
    """
    Calcule le ferraillage minimal d'une poutre.
    
    Args:
        width_mm: Largeur de la poutre
        height_mm: Hauteur de la poutre
        concrete_class: Classe de béton
        steel_class: Classe d'acier
        
    Returns:
        Dictionnaire avec sections d'acier
    """
    # Section de béton
    concrete_area_mm2 = width_mm * height_mm
    
    # Coefficient selon classe d'acier
    if "B500" in steel_class:
        fyk = 500  # MPa
    elif "B400" in steel_class:
        fyk = 400  # MPa
    else:
        fyk = 500
    
    # Résistance béton
    if "C25" in concrete_class:
        fck = 25
    elif "C30" in concrete_class:
        fck = 30
    elif "C35" in concrete_class:
        fck = 35
    elif "C40" in concrete_class:
        fck = 40
    else:
        fck = 25
    
    # Section minimale d'armatures (EC2)
    # As,min = 0.26 * (fctm/fyk) * bt * d ≥ 0.0013 * bt * d
    fctm = 0.3 * fck ** (2.0/3.0)  # Approximation
    d = 0.9 * height_mm  # Hauteur utile
    
    as_min_1 = 0.26 * (fctm / fyk) * width_mm * d
    as_min_2 = 0.0013 * width_mm * d
    
    as_min = max(as_min_1, as_min_2)
    
    # Section maximale (hors zones de recouvrement)
    as_max = 0.04 * concrete_area_mm2
    
    # Armatures longitudinales
    # 2 à 4 barres en travée
    if width_mm <= 200:
        main_bars_count = 2
        main_bar_diameter = 12
    elif width_mm <= 300:
        main_bars_count = 3
        main_bar_diameter = 14
    else:
        main_bars_count = 4
        main_bar_diameter = 16
    
    main_bars_area = main_bars_count * (math.pi * (main_bar_diameter/2.0) ** 2)
    
    # Armatures transversales (cadres)
    if height_mm <= 300:
        stirrup_diameter = 6
        stirrup_spacing = 200
    elif height_mm <= 500:
        stirrup_diameter = 8
        stirrup_spacing = 200
    else:
        stirrup_diameter = 10
        stirrup_spacing = 150
    
    stirrup_area = 2 * (math.pi * (stirrup_diameter/2.0) ** 2)  # 2 brins
    
    return {
        'concrete_section_mm2': concrete_area_mm2,
        'reinforcement_min_mm2': round(as_min, 0),
        'reinforcement_max_mm2': round(as_max, 0),
        'main_bars': {
            'count': main_bars_count,
            'diameter': main_bar_diameter,
            'area_mm2': round(main_bars_area, 0),
            'steel_class': steel_class
        },
        'stirrups': {
            'diameter': stirrup_diameter,
            'spacing_mm': stirrup_spacing,
            'area_mm2': round(stirrup_area, 0),
            'steel_class': steel_class
        }
    }


# ---------------------------------------------------------------------
# 2. POTEAUX
# ---------------------------------------------------------------------

def calculate_column_section(load_kN,
                           height_mm,
                           concrete_class="C25/30"):
    """
    Calcule la section minimale d'un poteau.
    
    Args:
        load_kN: Charge axiale en kN
        height_mm: Hauteur du poteau en mm
        concrete_class: Classe de béton
        
    Returns:
        (largeur, hauteur) en mm
    """
    # Résistance béton
    if "C25" in concrete_class:
        fck = 25
        fcd = 25 / 1.5  # 16.7 MPa
    elif "C30" in concrete_class:
        fck = 30
        fcd = 30 / 1.5  # 20 MPa
    elif "C35" in concrete_class:
        fck = 35
        fcd = 35 / 1.5  # 23.3 MPa
    elif "C40" in concrete_class:
        fck = 40
        fcd = 40 / 1.5  # 26.7 MPa
    else:
        fcd = 25 / 1.5
    
    # Section nécessaire (N / fcd)
    # Charge en kN -> N, fcd en MPa = N/mm²
    area_needed_mm2 = (load_kN * 1000) / fcd
    
    # Ajouter 1% pour armatures (approximation)
    area_needed_mm2 *= 1.01
    
    # Section carrée par défaut
    side_mm = math.sqrt(area_needed_mm2)
    
    # Vérifier conditions d'élancement
    slenderness = height_mm / side_mm if side_mm > 0 else 999
    
    if slenderness > 15:
        # Poteau élancé, augmenter section
        side_mm = height_mm / 12.0  # λ = 12
    elif slenderness < 8:
        # Poteau trapu, peut réduire
        side_mm = max(side_mm, height_mm / 15.0)
    
    # Dimensions minimales
    if height_mm <= 3000:
        side_mm = max(side_mm, 200)
    elif height_mm <= 5000:
        side_mm = max(side_mm, 250)
    else:
        side_mm = max(side_mm, 300)
    
    # Arrondir au multiple de 50 mm
    side_mm = int(round(side_mm / 50)) * 50
    
    # Optimisation: préférer rectangulaire si avantageux
    if side_mm == 300:
        return (250, 350)  # 25x35 plutôt que 30x30
    elif side_mm == 350:
        return (300, 400)  # 30x40 plutôt que 35x35
    elif side_mm == 500:
        return (400, 600)  # 40x60 plutôt que 50x50
    
    return (side_mm, side_mm)


def calculate_column_reinforcement(width_mm,
                                 height_mm,
                                 load_kN,
                                 concrete_class="C25/30",
                                 steel_class="B500B"):
    """
    Calcule le ferraillage minimal d'un poteau.
    
    Args:
        width_mm: Largeur du poteau
        height_mm: Hauteur du poteau
        load_kN: Charge axiale
        concrete_class: Classe de béton
        steel_class: Classe d'acier
        
    Returns:
        Dictionnaire avec armatures
    """
    section_mm2 = width_mm * height_mm
    
    # Section minimale d'armatures (EC2)
    # As,min = max(0.1 * N/fyd, 0.002 * Ac)
    if "B500" in steel_class:
        fyk = 500
        fyd = 500 / 1.15  # 435 MPa
    else:
        fyk = 400
        fyd = 400 / 1.15  # 348 MPa
    
    as_min_1 = 0.1 * (load_kN * 1000) / fyd
    as_min_2 = 0.002 * section_mm2
    
    as_min = max(as_min_1, as_min_2)
    
    # Section maximale (hors recouvrement)
    as_max = 0.04 * section_mm2
    
    # Nombre et diamètre des barres
    # Minimum 4 barres (1 par angle)
    if width_mm <= 200:
        bar_diameter = 12
        bar_count = 4
    elif width_mm <= 300:
        bar_diameter = 14
        bar_count = 4
    elif width_mm <= 400:
        bar_diameter = 16
        bar_count = 4
    else:
        bar_diameter = 20
        bar_count = 4 + (2 if width_mm > 500 else 0)  # Barres intermédiaires
    
    bar_area = math.pi * (bar_diameter/2.0) ** 2
    total_area = bar_count * bar_area
    
    # Cadres
    if width_mm <= 300:
        stirrup_diameter = 6
        stirrup_spacing = 200
    else:
        stirrup_diameter = 8
        stirrup_spacing = 150
    
    return {
        'concrete_section_mm2': section_mm2,
        'reinforcement_min_mm2': round(as_min, 0),
        'reinforcement_max_mm2': round(as_max, 0),
        'main_bars': {
            'count': bar_count,
            'diameter': bar_diameter,
            'area_mm2': round(total_area, 0),
            'steel_class': steel_class
        },
        'stirrups': {
            'diameter': stirrup_diameter,
            'spacing_mm': stirrup_spacing
        }
    }


# ---------------------------------------------------------------------
# 3. DALLES
# ---------------------------------------------------------------------

def calculate_slab_thickness(span_m,
                           slab_type="RIBBED",
                           is_basement=False):
    """
    Calcule l'épaisseur d'une dalle.
    
    Règles :
    - Dalle pleine : L/25 à L/30 (min 150mm)
    - Dalle nervurée : L/20 (min 200mm) + table 50mm
    - Sous-sol : majoration 20%
    
    Args:
        span_m: Petite portée en mètres
        slab_type: Type de dalle (SOLID, RIBBED)
        is_basement: True si sous-sol
        
    Returns:
        Épaisseur totale en mm
    """
    slab_type_upper = slab_type.upper()
    
    if slab_type_upper == "SOLID" or slab_type_upper == "PLEINE":
        # Dalle pleine : L/25 à L/30
        thickness = (span_m / 27.5) * 1000  # L/27.5 par défaut
        min_thickness = 150
        
    elif slab_type_upper == "RIBBED" or slab_type_upper == "NERVUREE":
        # Dalle nervurée : hauteur nervure = L/20
        rib_height = (span_m / 20.0) * 1000
        rib_height = max(200, rib_height)
        thickness = rib_height + 50  # Table compression 50mm
        min_thickness = 200
        
    else:
        # Dalle pleine par défaut
        thickness = (span_m / 27.5) * 1000
        min_thickness = 150
    
    # Majoration sous-sol
    if is_basement:
        thickness *= 1.2
    
    thickness = max(min_thickness, int(round(thickness / 10)) * 10)
    
    return thickness


def calculate_slab_reinforcement(thickness_mm,
                               span_m,
                               concrete_class="C25/30"):
    """
    Calcule le ferraillage minimal d'une dalle.
    
    Args:
        thickness_mm: Épaisseur dalle
        span_m: Portée
        concrete_class: Classe béton
        
    Returns:
        Dictionnaire avec armatures
    """
    # Section pour 1m de largeur
    width_mm = 1000
    d = thickness_mm - 30  # Enrobage
    
    # Résistance béton
    if "C25" in concrete_class:
        fck = 25
    elif "C30" in concrete_class:
        fck = 30
    else:
        fck = 25
    
    fctm = 0.3 * fck ** (2.0/3.0)
    
    # Section minimale (fissuration)
    as_min = 0.26 * (fctm / 500) * width_mm * d
    as_min = max(as_min, 0.0013 * width_mm * d)
    
    # Treillis soudé standard
    if thickness_mm <= 150:
        mesh = "ST25"  # 7x7 - 150x150
        wire_diameter = 7
        spacing = 150
        area_per_m = 257  # mm²/m
    elif thickness_mm <= 200:
        mesh = "ST35"  # 8x8 - 150x150
        wire_diameter = 8
        spacing = 150
        area_per_m = 335
    else:
        mesh = "ST50"  # 10x10 - 150x150
        wire_diameter = 10
        spacing = 150
        area_per_m = 523
    
    return {
        'thickness_mm': thickness_mm,
        'reinforcement_min_mm2_per_m': round(as_min, 0),
        'recommended_mesh': mesh,
        'wire_diameter': wire_diameter,
        'spacing_mm': spacing,
        'area_mm2_per_m': area_per_m,
        'span_m': span_m
    }


# ---------------------------------------------------------------------
# 4. FONDATIONS
# ---------------------------------------------------------------------

def calculate_foundation_dimensions(load_kN,
                                  soil_capacity_mpa=0.2,
                                  foundation_type="ISOLATED"):
    """
    Calcule les dimensions d'une fondation.
    
    Args:
        load_kN: Charge en kN
        soil_capacity_mpa: Capacité portante du sol en MPa
        foundation_type: Type de fondation
        
    Returns:
        Dictionnaire avec dimensions
    """
    # Conversion: charge kN -> N, sol MPa -> N/mm²
    area_needed_mm2 = (load_kN * 1000) / soil_capacity_mpa
    
    foundation_type_upper = foundation_type.upper()
    
    if foundation_type_upper == "STRIP" or foundation_type_upper == "FILANTE":
        # Semelle filante - dimensions pour 1m linéaire
        width_mm = math.sqrt(area_needed_mm2 * 1000)  # Approximation
        width_mm = max(400, int(round(width_mm / 50)) * 50)
        
        thickness_mm = max(250, int(width_mm * 0.35))
        thickness_mm = int(round(thickness_mm / 50)) * 50
        
        return {
            'width_mm': width_mm,
            'thickness_mm': thickness_mm,
            'length_mm': None,  # Dépend du mur
            'type': 'strip',
            'area_needed_mm2_per_m': round(area_needed_mm2 / 1000, 0)
        }
        
    else:
        # Semelle isolée ou engrênée
        side_mm = math.sqrt(area_needed_mm2)
        side_mm = max(600, int(round(side_mm / 50)) * 50)
        
        thickness_mm = max(250, int(side_mm * 0.3))
        thickness_mm = int(round(thickness_mm / 50)) * 50
        
        return {
            'width_mm': side_mm,
            'length_mm': side_mm,
            'thickness_mm': thickness_mm,
            'type': 'isolated',
            'area_needed_mm2': round(area_needed_mm2, 0)
        }


# ---------------------------------------------------------------------
# 5. RATIOS DE FERRAILLAGE
# ---------------------------------------------------------------------

def calculate_reinforcement_ratio(concrete_area_mm2,
                                steel_area_mm2):
    """
    Calcule le pourcentage d'armatures.
    
    Args:
        concrete_area_mm2: Section béton
        steel_area_mm2: Section acier
        
    Returns:
        Ratio en %
    """
    if concrete_area_mm2 <= 0:
        return 0
    
    return (steel_area_mm2 / concrete_area_mm2) * 100


def check_reinforcement_limits(ratio,
                             element_type):
    """
    Vérifie si le ratio de ferraillage est dans les limites.
    
    Args:
        ratio: Ratio de ferraillage en %
        element_type: Type d'élément
        
    Returns:
        (is_valid, message)
    """
    element_type_lower = element_type.lower()
    
    if "poutre" in element_type_lower or "beam" in element_type_lower:
        min_ratio = 0.13
        max_ratio = 4.0
    elif "poteau" in element_type_lower or "column" in element_type_lower:
        min_ratio = 0.2
        max_ratio = 4.0
    elif "dalle" in element_type_lower or "slab" in element_type_lower:
        min_ratio = 0.13
        max_ratio = 1.0
    else:
        min_ratio = 0.15
        max_ratio = 4.0
    
    if ratio < min_ratio:
        return False, "Ratio trop faible: %.2f%% < %.2f%%" % (ratio, min_ratio)
    elif ratio > max_ratio:
        return False, "Ratio trop élevé: %.2f%% > %.2f%%" % (ratio, max_ratio)
    else:
        return True, "Ratio OK: %.2f%%" % ratio