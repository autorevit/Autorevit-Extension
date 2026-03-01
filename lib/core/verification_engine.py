# -*- coding: utf-8 -*-
"""
VerificationEngine - Moteur de vérification qualité et conformité
==================================================================
Responsabilités :
- Vérification géométrique (dimensions, proportions, élancement)
- Vérification des dégagements et encombrements
- Vérification de l'intégrité structurelle
- Détection de collisions
- Génération de rapports de vérification
- Export des résultats (PDF, Excel, HTML)

Auteur : AutoRevit Team
Date : 2025
"""

import os
import time
import math
import traceback
from datetime import datetime
from utils.logger import get_logger
from utils.exceptions import RevitDocumentError, ValidationError
from services.revit_service import RevitService
from services.geometry_service import GeometryService
from services.logging_service import LoggingService
from algorithms.geometry_utils import (
    calculate_distance_mm,
    get_bounding_rectangle,
    is_point_on_line
)

logger = get_logger(__name__)

try:
    from Autodesk.Revit.DB import (
        Document,
        Element,
        FamilyInstance,
        Level,
        BuiltInCategory,
        BuiltInParameter,
        XYZ,
        FilteredElementCollector,
        Solid,
        GeometryElement,
        GeometryInstance,
        Options,
        IntersectionResultArray,
        SetComparisonResult,
        Transaction,
        ViewPlan,
        ViewSection,
        View3D,
        ViewFamilyType
    )
    REVIT_AVAILABLE = True
except ImportError:
    REVIT_AVAILABLE = False
    logger.warning("Revit API non disponible (mode développement)")
    
    class XYZ:
        def __init__(self, x=0, y=0, z=0):
            self.X = x
            self.Y = y
            self.Z = z


class VerificationEngine:
    """
    Moteur de vérification qualité et conformité.
    
    Exemple d'utilisation :
    ----------------------
    >>> from pyrevit import revit
    >>> from core import VerificationEngine
    >>>
    >>> doc = revit.doc
    >>> engine = VerificationEngine(doc)
    >>>
    >>> # Vérifier la géométrie des poteaux
    >>> columns = engine.get_structural_columns()
    >>> results = engine.verify_geometry(columns)
    >>>
    >>> # Vérifier les collisions
    >>> clashes = engine.detect_clashes()
    >>>
    >>> # Générer rapport
    >>> report = engine.generate_report(results, format='html')
    """

    # Seuils de vérification
    THRESHOLDS = {
        'column_slenderness_max': 15,      # Élancement max poteau
        'beam_span_ratio_min': 1/20,       # Ratio h/L minimum
        'beam_span_ratio_max': 1/8,        # Ratio h/L maximum
        'slab_span_ratio_min': 1/30,       # Ratio e/L minimum
        'slab_span_ratio_max': 1/25,       # Ratio e/L maximum
        'clearance_min_mm': 50,            # Dégagement minimum
        'cover_min_mm': 30,                # Enrobage minimum
        'column_vertical_alignment_tolerance_mm': 100  # Tolérance alignement vertical
    }

    # Niveaux de sévérité
    SEVERITY = {
        'CRITICAL': 4,
        'ERROR': 3,
        'WARNING': 2,
        'INFO': 1,
        'PASS': 0
    }

    def __init__(self, document):
        """
        Initialise le moteur de vérification.
        
        Args:
            document: Document Revit actif
        """
        if not REVIT_AVAILABLE and document is not None:
            logger.warning("Revit API non disponible - vérification limitée")
        
        self.doc = document
        
        # Services
        self.revit_service = RevitService(document)
        self.geometry_service = GeometryService(document)
        self.logger = LoggingService()
        
        # Options de géométrie
        if REVIT_AVAILABLE:
            self.geom_options = Options()
            self.geom_options.ComputeReferences = True
            self.geom_options.DetailLevel = 0  # Coarse
            self.geom_options.IncludeNonVisibleObjects = False
        else:
            self.geom_options = None
        
        # Statistiques
        self.stats = {
            'verifications_performed': 0,
            'critical_issues': 0,
            'errors': 0,
            'warnings': 0,
            'passed': 0
        }
        
        logger.info("VerificationEngine initialisé")

    # ========================================================================
    # COLLECTE DES ÉLÉMENTS
    # ========================================================================

    def get_structural_columns(self, level=None):
        """Récupère les poteaux structurels."""
        return self.revit_service.get_structural_columns(level)

    def get_structural_framing(self, level=None):
        """Récupère les poutres structurelles."""
        return self.revit_service.get_structural_framing(level)

    def get_floors(self, level=None, structural_only=True):
        """Récupère les dalles."""
        return self.revit_service.get_floors(level, structural_only)

    def get_walls(self, level=None, structural_only=True):
        """Récupère les murs."""
        return self.revit_service.get_walls(level, structural_only)

    def get_structural_foundations(self):
        """Récupère les fondations."""
        return self.revit_service.get_structural_foundations()

    # ========================================================================
    # VÉRIFICATION GÉOMÉTRIQUE
    # ========================================================================

    def verify_geometry(self, elements):
        """
        Vérifie la géométrie des éléments.
        
        Args:
            elements (list): Liste d'éléments Revit
        
        Returns:
            list: Résultats de vérification par élément
        """
        results = []
        
        for element in elements:
            element_results = {
                'element_id': self._get_element_id(element),
                'element_name': self._get_element_name(element),
                'element_category': self._get_element_category(element),
                'checks': [],
                'passed': True,
                'severity': 'PASS'
            }
            
            # Vérifier selon le type
            category = element_results['element_category'].lower()
            
            if 'column' in category or 'poteau' in category:
                check = self._verify_column_geometry(element)
            elif 'framing' in category or 'poutre' in category:
                check = self._verify_beam_geometry(element)
            elif 'floor' in category or 'dalle' in category:
                check = self._verify_slab_geometry(element)
            elif 'wall' in category or 'mur' in category:
                check = self._verify_wall_geometry(element)
            elif 'foundation' in category or 'semelle' in category:
                check = self._verify_foundation_geometry(element)
            else:
                check = self._verify_generic_geometry(element)
            
            element_results['checks'] = check.get('checks', [])
            element_results['passed'] = check.get('passed', True)
            element_results['severity'] = self._get_max_severity(check.get('checks', []))
            
            results.append(element_results)
            
            # Mettre à jour les stats
            self.stats['verifications_performed'] += 1
            if element_results['severity'] == 'CRITICAL':
                self.stats['critical_issues'] += 1
            elif element_results['severity'] == 'ERROR':
                self.stats['errors'] += 1
            elif element_results['severity'] == 'WARNING':
                self.stats['warnings'] += 1
            else:
                self.stats['passed'] += 1
        
        return results

    def _verify_column_geometry(self, column):
        """
        Vérifie la géométrie d'un poteau.
        
        Args:
            column (FamilyInstance): Poteau
        
        Returns:
            dict: Résultats des vérifications
        """
        checks = []
        passed = True
        
        try:
            # Récupérer les dimensions
            width_param = column.LookupParameter("Largeur") or column.LookupParameter("Width")
            height_param = column.LookupParameter("Hauteur") or column.LookupParameter("Height")
            
            if width_param and height_param:
                width_mm = self._feet_to_mm(width_param.AsDouble())
                height_mm = self._feet_to_mm(height_param.AsDouble())
                min_dim = min(width_mm, height_mm)
                
                # Vérifier dimensions minimales
                if min_dim < 200:
                    checks.append({
                        'check': 'dimensions_minimales',
                        'status': 'ERROR',
                        'message': 'Section trop petite: ' + str(int(min_dim)) + 'mm (min 200mm)',
                        'value': int(min_dim),
                        'threshold': 200,
                        'unit': 'mm'
                    })
                    passed = False
                else:
                    checks.append({
                        'check': 'dimensions_minimales',
                        'status': 'PASS',
                        'message': 'Section OK: ' + str(int(min_dim)) + 'mm',
                        'value': int(min_dim),
                        'threshold': 200,
                        'unit': 'mm'
                    })
                
                # Vérifier élancement
                location = column.Location
                if hasattr(location, 'Point'):
                    height_feet = column.get_Parameter(BuiltInParameter.FAMILY_TOP_LEVEL_PARAM)
                    base_level = column.get_Parameter(BuiltInParameter.FAMILY_LEVEL_PARAM)
                    
                    if height_feet and base_level:
                        top_level = self.doc.GetElement(height_feet.AsElementId())
                        base_level_elem = self.doc.GetElement(base_level.AsElementId())
                        
                        if top_level and base_level_elem:
                            column_height_mm = self._feet_to_mm(
                                top_level.Elevation - base_level_elem.Elevation
                            )
                            slenderness = column_height_mm / min_dim
                            
                            if slenderness > self.THRESHOLDS['column_slenderness_max']:
                                checks.append({
                                    'check': 'élancement',
                                    'status': 'WARNING',
                                    'message': 'Élancement élevé: ' + str(round(slenderness, 1)) +
                                              ' (max ' + str(self.THRESHOLDS['column_slenderness_max']) + ')',
                                    'value': round(slenderness, 1),
                                    'threshold': self.THRESHOLDS['column_slenderness_max'],
                                    'unit': ''
                                })
                                passed = False
                            else:
                                checks.append({
                                    'check': 'élancement',
                                    'status': 'PASS',
                                    'message': 'Élancement OK: ' + str(round(slenderness, 1)),
                                    'value': round(slenderness, 1),
                                    'threshold': self.THRESHOLDS['column_slenderness_max'],
                                    'unit': ''
                                })
            
        except Exception as e:
            logger.error("Erreur vérification poteau: " + str(e))
            checks.append({
                'check': 'erreur',
                'status': 'ERROR',
                'message': 'Erreur de vérification: ' + str(e),
                'value': None,
                'threshold': None,
                'unit': ''
            })
            passed = False
        
        return {'checks': checks, 'passed': passed}

    def _verify_beam_geometry(self, beam):
        """
        Vérifie la géométrie d'une poutre.
        
        Args:
            beam (FamilyInstance): Poutre
        
        Returns:
            dict: Résultats des vérifications
        """
        checks = []
        passed = True
        
        try:
            # Récupérer les dimensions
            height_param = beam.LookupParameter("Hauteur") or beam.LookupParameter("Height")
            location = beam.Location
            
            if height_param and hasattr(location, 'Curve'):
                height_mm = self._feet_to_mm(height_param.AsDouble())
                span_mm = self._feet_to_mm(location.Curve.Length)
                span_m = span_mm / 1000.0
                
                # Vérifier ratio hauteur/portée
                ratio = height_mm / span_mm
                
                if ratio < self.THRESHOLDS['beam_span_ratio_min']:
                    checks.append({
                        'check': 'ratio_h/L',
                        'status': 'ERROR',
                        'message': 'Hauteur insuffisante: h/L = ' + str(round(ratio, 3)) +
                                  ' (min ' + str(self.THRESHOLDS['beam_span_ratio_min']) + ')',
                        'value': round(ratio, 3),
                        'threshold': self.THRESHOLDS['beam_span_ratio_min'],
                        'unit': ''
                    })
                    passed = False
                elif ratio > self.THRESHOLDS['beam_span_ratio_max']:
                    checks.append({
                        'check': 'ratio_h/L',
                        'status': 'WARNING',
                        'message': 'Hauteur surdimensionnée: h/L = ' + str(round(ratio, 3)) +
                                  ' (max ' + str(self.THRESHOLDS['beam_span_ratio_max']) + ')',
                        'value': round(ratio, 3),
                        'threshold': self.THRESHOLDS['beam_span_ratio_max'],
                        'unit': ''
                    })
                    passed = False
                else:
                    checks.append({
                        'check': 'ratio_h/L',
                        'status': 'PASS',
                        'message': 'Ratio h/L OK: ' + str(round(ratio, 3)),
                        'value': round(ratio, 3),
                        'threshold': None,
                        'unit': ''
                    })
                
                # Vérifier portée maximale
                if span_m > 12:
                    checks.append({
                        'check': 'portee_max',
                        'status': 'WARNING',
                        'message': 'Grande portée: ' + str(round(span_m, 1)) + 'm (>12m)',
                        'value': round(span_m, 1),
                        'threshold': 12,
                        'unit': 'm'
                    })
                    passed = False
                
        except Exception as e:
            logger.error("Erreur vérification poutre: " + str(e))
            checks.append({
                'check': 'erreur',
                'status': 'ERROR',
                'message': 'Erreur de vérification: ' + str(e),
                'value': None,
                'threshold': None,
                'unit': ''
            })
            passed = False
        
        return {'checks': checks, 'passed': passed}

    def _verify_slab_geometry(self, slab):
        """
        Vérifie la géométrie d'une dalle.
        
        Args:
            slab (Floor): Dalle
        
        Returns:
            dict: Résultats des vérifications
        """
        checks = []
        passed = True
        
        try:
            # Récupérer l'épaisseur
            thickness_param = slab.get_Parameter(
                BuiltInParameter.FLOOR_ATTR_DEFAULT_THICKNESS_PARAM
            )
            
            if thickness_param:
                thickness_mm = self._feet_to_mm(thickness_param.AsDouble())
                
                # Vérifier épaisseur minimale
                if thickness_mm < 150:
                    checks.append({
                        'check': 'epaisseur_min',
                        'status': 'ERROR',
                        'message': 'Épaisseur insuffisante: ' + str(int(thickness_mm)) + 'mm (min 150mm)',
                        'value': int(thickness_mm),
                        'threshold': 150,
                        'unit': 'mm'
                    })
                    passed = False
                else:
                    checks.append({
                        'check': 'epaisseur_min',
                        'status': 'PASS',
                        'message': 'Épaisseur OK: ' + str(int(thickness_mm)) + 'mm',
                        'value': int(thickness_mm),
                        'threshold': 150,
                        'unit': 'mm'
                    })
                
                # Calculer la portée approximative
                bbox = slab.get_BoundingBox(None)
                if bbox:
                    width_mm = self._feet_to_mm(bbox.Max.X - bbox.Min.X)
                    length_mm = self._feet_to_mm(bbox.Max.Y - bbox.Min.Y)
                    span_mm = min(width_mm, length_mm)
                    span_m = span_mm / 1000.0
                    
                    ratio = thickness_mm / span_mm
                    
                    if ratio < self.THRESHOLDS['slab_span_ratio_min']:
                        checks.append({
                            'check': 'ratio_e/L',
                            'status': 'WARNING',
                            'message': 'Épaisseur faible pour la portée: e/L = ' + str(round(ratio, 3)),
                            'value': round(ratio, 3),
                            'threshold': self.THRESHOLDS['slab_span_ratio_min'],
                            'unit': ''
                        })
                        passed = False
        
        except Exception as e:
            logger.error("Erreur vérification dalle: " + str(e))
            checks.append({
                'check': 'erreur',
                'status': 'ERROR',
                'message': 'Erreur de vérification: ' + str(e),
                'value': None,
                'threshold': None,
                'unit': ''
            })
            passed = False
        
        return {'checks': checks, 'passed': passed}

    def _verify_wall_geometry(self, wall):
        """Vérifie la géométrie d'un mur."""
        # TODO: Implémenter vérification murs
        return {'checks': [], 'passed': True}

    def _verify_foundation_geometry(self, foundation):
        """Vérifie la géométrie d'une fondation."""
        # TODO: Implémenter vérification fondations
        return {'checks': [], 'passed': True}

    def _verify_generic_geometry(self, element):
        """Vérification générique pour tout élément."""
        return {'checks': [], 'passed': True}

    # ========================================================================
    # VÉRIFICATION DES DÉGAGEMENTS
    # ========================================================================

    def verify_clearance(self, elements, clearance_mm=50):
        """
        Vérifie les dégagements entre éléments.
        
        Args:
            elements (list): Liste d'éléments à vérifier
            clearance_mm (int): Dégagement minimum requis
        
        Returns:
            list: Problèmes de dégagement détectés
        """
        issues = []
        
        try:
            for i in range(len(elements)):
                for j in range(i + 1, len(elements)):
                    elem1 = elements[i]
                    elem2 = elements[j]
                    
                    bbox1 = elem1.get_BoundingBox(None)
                    bbox2 = elem2.get_BoundingBox(None)
                    
                    if bbox1 and bbox2:
                        # Vérifier si les bounding boxes sont proches
                        distance = self._bbox_distance(bbox1, bbox2)
                        distance_mm = self._feet_to_mm(distance)
                        
                        if 0 < distance_mm < clearance_mm:
                            issues.append({
                                'type': 'clearance',
                                'severity': 'WARNING',
                                'element1_id': self._get_element_id(elem1),
                                'element1_name': self._get_element_name(elem1),
                                'element2_id': self._get_element_id(elem2),
                                'element2_name': self._get_element_name(elem2),
                                'distance_mm': round(distance_mm, 1),
                                'required_mm': clearance_mm,
                                'message': 'Dégagement insuffisant: ' +
                                         str(round(distance_mm, 1)) + 'mm (requis ' + str(clearance_mm) + 'mm)'
                            })
        
        except Exception as e:
            logger.error("Erreur vérification dégagements: " + str(e))
        
        return issues

    def _bbox_distance(self, bbox1, bbox2):
        """Calcule la distance minimale entre deux bounding boxes."""
        dx = max(bbox1.Min.X, bbox2.Min.X) - min(bbox1.Max.X, bbox2.Max.X)
        dy = max(bbox1.Min.Y, bbox2.Min.Y) - min(bbox1.Max.Y, bbox2.Max.Y)
        dz = max(bbox1.Min.Z, bbox2.Min.Z) - min(bbox1.Max.Z, bbox2.Max.Z)
        
        if dx < 0 and dy < 0 and dz < 0:
            return 0  # Intersection
        
        return math.sqrt(max(0, dx)**2 + max(0, dy)**2 + max(0, dz)**2)

    # ========================================================================
    # DÉTECTION DE COLLISIONS
    # ========================================================================

    def detect_clashes(self, 
                      categories1=None, 
                      categories2=None, 
                      tolerance_mm=50):
        """
        Détecte les collisions entre éléments.
        
        Args:
            categories1 (list): Première liste de catégories
            categories2 (list): Deuxième liste de catégories
            tolerance_mm (int): Tolérance de détection
        
        Returns:
            list: Collisions détectées
        """
        logger.info("Détection des collisions...")
        
        if not REVIT_AVAILABLE:
            logger.warning("Revit API non disponible - détection impossible")
            return []
        
        if not categories1:
            categories1 = [BuiltInCategory.OST_StructuralColumns,
                          BuiltInCategory.OST_StructuralFraming,
                          BuiltInCategory.OST_Walls,
                          BuiltInCategory.OST_Floors]
        
        if not categories2:
            categories2 = [BuiltInCategory.OST_Doors,
                          BuiltInCategory.OST_Windows,
                          BuiltInCategory.OST_MechanicalEquipment,
                          BuiltInCategory.OST_Ducts,
                          BuiltInCategory.OST_Pipes]
        
        clashes = []
        
        try:
            # Récupérer les éléments
            elements1 = self._get_elements_by_categories(categories1)
            elements2 = self._get_elements_by_categories(categories2)
            
            tolerance_feet = tolerance_mm / 304.8
            
            for elem1 in elements1:
                bbox1 = elem1.get_BoundingBox(None)
                if not bbox1:
                    continue
                
                for elem2 in elements2:
                    if elem1.Id == elem2.Id:
                        continue
                    
                    bbox2 = elem2.get_BoundingBox(None)
                    if not bbox2:
                        continue
                    
                    # Test rapide des bounding boxes
                    if self._bounding_boxes_intersect(bbox1, bbox2, tolerance_feet):
                        # Test géométrique précis
                        if self._elements_intersect(elem1, elem2):
                            clash = {
                                'type': 'clash',
                                'severity': self._evaluate_clash_severity(elem1, elem2),
                                'element1_id': self._get_element_id(elem1),
                                'element1_name': self._get_element_name(elem1),
                                'element1_category': self._get_element_category(elem1),
                                'element2_id': self._get_element_id(elem2),
                                'element2_name': self._get_element_name(elem2),
                                'element2_category': self._get_element_category(elem2),
                                'message': 'Collision entre ' +
                                         self._get_element_category(elem1) + ' et ' +
                                         self._get_element_category(elem2)
                            }
                            clashes.append(clash)
                            
                            if clash['severity'] == 'CRITICAL':
                                self.stats['critical_issues'] += 1
                            elif clash['severity'] == 'ERROR':
                                self.stats['errors'] += 1
                            else:
                                self.stats['warnings'] += 1
        
        except Exception as e:
            logger.error("Erreur détection collisions: " + str(e))
        
        logger.info(str(len(clashes)) + " collisions détectées")
        return clashes

    def _get_elements_by_categories(self, categories):
        """Récupère les éléments de plusieurs catégories."""
        elements = []
        
        for cat in categories:
            collector = FilteredElementCollector(self.doc)\
                .OfCategory(cat)\
                .WhereElementIsNotElementType()
            
            elements.extend(list(collector))
        
        return elements

    def _bounding_boxes_intersect(self, bbox1, bbox2, tolerance=0):
        """Vérifie si deux bounding boxes s'intersectent."""
        return not (bbox1.Max.X + tolerance < bbox2.Min.X or
                   bbox1.Min.X - tolerance > bbox2.Max.X or
                   bbox1.Max.Y + tolerance < bbox2.Min.Y or
                   bbox1.Min.Y - tolerance > bbox2.Max.Y or
                   bbox1.Max.Z + tolerance < bbox2.Min.Z or
                   bbox1.Min.Z - tolerance > bbox2.Max.Z)

    def _elements_intersect(self, elem1, elem2):
        """Vérifie si deux éléments s'intersectent géométriquement."""
        try:
            geo1 = elem1.get_Geometry(self.geom_options)
            geo2 = elem2.get_Geometry(self.geom_options)
            
            if not geo1 or not geo2:
                return False
            
            solids1 = self._get_solids_from_geometry(geo1)
            solids2 = self._get_solids_from_geometry(geo2)
            
            for solid1 in solids1:
                for solid2 in solids2:
                    try:
                        result = solid1.Intersect(solid2)
                        if hasattr(Solid, 'SolidIntersectionResult'):
                            if result != Solid.SolidIntersectionResult.NonIntersecting:
                                return True
                        else:
                            # Méthode alternative pour versions plus anciennes
                            if result != SetComparisonResult.Disjoint:
                                return True
                    except:
                        pass
            
            return False
        except Exception as e:
            logger.debug("Erreur test intersection: " + str(e))
            return False

    def _get_solids_from_geometry(self, geometry):
        """Extrait les solides d'un objet Geometry."""
        solids = []
        
        try:
            for obj in geometry:
                if isinstance(obj, Solid) and obj.Volume > 0:
                    solids.append(obj)
                elif isinstance(obj, GeometryInstance):
                    instance_geo = obj.GetInstanceGeometry()
                    if instance_geo:
                        solids.extend(self._get_solids_from_geometry(instance_geo))
        except Exception as e:
            logger.debug("Erreur extraction solides: " + str(e))
        
        return solids

    def _evaluate_clash_severity(self, elem1, elem2):
        """Évalue la sévérité d'une collision."""
        cat1 = self._get_element_category(elem1).lower()
        cat2 = self._get_element_category(elem2).lower()
        
        # Collisions critiques
        if ('column' in cat1 or 'poteau' in cat1) and ('beam' in cat2 or 'poutre' in cat2):
            return 'CRITICAL'
        if ('beam' in cat1 or 'poutre' in cat1) and ('column' in cat2 or 'poteau' in cat2):
            return 'CRITICAL'
        
        # Collisions structure/équipement
        if ('structural' in cat1 or 'structure' in cat1) and ('mechanical' in cat2 or 'duct' in cat2):
            return 'ERROR'
        if ('structural' in cat2 or 'structure' in cat2) and ('mechanical' in cat1 or 'duct' in cat1):
            return 'ERROR'
        
        # Collisions mineures
        return 'WARNING'

    # ========================================================================
    # VÉRIFICATION DE L'INTÉGRITÉ STRUCTURELLE
    # ========================================================================

    def verify_structural_integrity(self):
        """
        Vérifie l'intégrité structurelle du projet.
        
        Returns:
            dict: Rapport d'intégrité structurelle
        """
        logger.info("Vérification de l'intégrité structurelle...")
        
        report = {
            'vertical_alignment': [],
            'missing_supports': [],
            'discontinuous_load_path': [],
            'issues': []
        }
        
        try:
            # Vérifier l'alignement vertical des poteaux
            levels = self.revit_service.get_all_levels()
            
            for i in range(len(levels) - 1):
                level_current = levels[i]
                level_next = levels[i + 1]
                
                columns_current = self.get_structural_columns(level_current)
                columns_next = self.get_structural_columns(level_next)
                
                # Vérifier la continuité
                for col_current in columns_current:
                    loc_current = col_current.Location
                    if not hasattr(loc_current, 'Point'):
                        continue
                    
                    found_match = False
                    for col_next in columns_next:
                        loc_next = col_next.Location
                        if hasattr(loc_next, 'Point'):
                            dist = self.geometry_service.calculate_distance_mm(
                                loc_current.Point,
                                loc_next.Point
                            )
                            if dist < self.THRESHOLDS['column_vertical_alignment_tolerance_mm']:
                                found_match = True
                                break
                    
                    if not found_match:
                        issue = {
                            'type': 'vertical_alignment',
                            'severity': 'WARNING',
                            'column_id': self._get_element_id(col_current),
                            'level': level_current.Name,
                            'message': 'Poteau non prolongé au niveau ' + level_next.Name
                        }
                        report['vertical_alignment'].append(issue)
                        report['issues'].append(issue)
            
            # Vérifier les appuis manquants
            beams = self.get_structural_framing()
            
            for beam in beams:
                location = beam.Location
                if not hasattr(location, 'Curve'):
                    continue
                
                curve = location.Curve
                start = curve.GetEndPoint(0)
                end = curve.GetEndPoint(1)
                
                if not self._has_support_at_point(start):
                    issue = {
                        'type': 'missing_support',
                        'severity': 'ERROR',
                        'beam_id': self._get_element_id(beam),
                        'end': 'start',
                        'message': 'Appui manquant au départ de la poutre'
                    }
                    report['missing_supports'].append(issue)
                    report['issues'].append(issue)
                
                if not self._has_support_at_point(end):
                    issue = {
                        'type': 'missing_support',
                        'severity': 'ERROR',
                        'beam_id': self._get_element_id(beam),
                        'end': 'end',
                        'message': 'Appui manquant à l\'arrivée de la poutre'
                    }
                    report['missing_supports'].append(issue)
                    report['issues'].append(issue)
        
        except Exception as e:
            logger.error("Erreur vérification intégrité: " + str(e))
        
        return report

    def _has_support_at_point(self, point, tolerance_mm=200):
        """Vérifie si un point a un support (poteau ou mur)."""
        tolerance_feet = tolerance_mm / 304.8
        
        # Vérifier les poteaux
        columns = self.get_structural_columns()
        for col in columns:
            loc = col.Location
            if hasattr(loc, 'Point'):
                dist = self.geometry_service.calculate_distance(point, loc.Point)
                if dist < tolerance_feet:
                    return True
        
        # Vérifier les murs porteurs
        walls = self.get_walls(structural_only=True)
        for wall in walls:
            loc = wall.Location
            if hasattr(loc, 'Curve'):
                if is_point_on_line(point, loc.Curve, tolerance_mm):
                    return True
        
        return False

    # ========================================================================
    # GÉNÉRATION DE RAPPORTS
    # ========================================================================

    def generate_report(self, verification_results, format='html'):
        """
        Génère un rapport de vérification.
        
        Args:
            verification_results (list/dict): Résultats des vérifications
            format (str): Format du rapport ('html', 'txt', 'json')
        
        Returns:
            str: Rapport généré
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if format == 'json':
            import json
            report = {
                'timestamp': timestamp,
                'stats': self.stats,
                'results': verification_results
            }
            return json.dumps(report, indent=2, ensure_ascii=False)
        
        elif format == 'html':
            html = []
            html.append('<!DOCTYPE html>')
            html.append('<html>')
            html.append('<head>')
            html.append('<meta charset="UTF-8">')
            html.append('<title>Rapport de vérification - AutoRevit</title>')
            html.append('<style>')
            html.append('body { font-family: Arial, sans-serif; margin: 20px; }')
            html.append('h1 { color: #2c3e50; }')
            html.append('.critical { color: #c0392b; font-weight: bold; }')
            html.append('.error { color: #e67e22; font-weight: bold; }')
            html.append('.warning { color: #f39c12; }')
            html.append('.pass { color: #27ae60; }')
            html.append('table { border-collapse: collapse; width: 100%; }')
            html.append('th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }')
            html.append('th { background-color: #f2f2f2; }')
            html.append('</style>')
            html.append('</head>')
            html.append('<body>')
            html.append('<h1>Rapport de vérification structurelle</h1>')
            html.append('<p>Généré le: ' + timestamp + '</p>')
            
            # Statistiques
            html.append('<h2>Statistiques</h2>')
            html.append('<ul>')
            html.append('<li>Vérifications effectuées: ' + str(self.stats['verifications_performed']) + '</li>')
            html.append('<li class="critical">Problèmes critiques: ' + str(self.stats['critical_issues']) + '</li>')
            html.append('<li class="error">Erreurs: ' + str(self.stats['errors']) + '</li>')
            html.append('<li class="warning">Avertissements: ' + str(self.stats['warnings']) + '</li>')
            html.append('<li class="pass">Conformes: ' + str(self.stats['passed']) + '</li>')
            html.append('</ul>')
            
            # Résultats détaillés
            if isinstance(verification_results, list):
                html.append('<h2>Résultats détaillés</h2>')
                html.append('<table>')
                html.append('<tr><th>Élément</th><th>Catégorie</th><th>Vérification</th><th>Statut</th><th>Message</th></tr>')
                
                for result in verification_results:
                    for check in result.get('checks', []):
                        status_class = check['status'].lower()
                        html.append('<tr>')
                        html.append('<td>' + result.get('element_name', '') + '</td>')
                        html.append('<td>' + result.get('element_category', '') + '</td>')
                        html.append('<td>' + check.get('check', '') + '</td>')
                        html.append('<td class="' + status_class + '">' + check.get('status', '') + '</td>')
                        html.append('<td>' + check.get('message', '') + '</td>')
                        html.append('</tr>')
                
                html.append('</table>')
            
            html.append('</body>')
            html.append('</html>')
            
            return '\n'.join(html)
        
        else:
            # Format texte simple
            lines = []
            lines.append('=' * 60)
            lines.append('RAPPORT DE VÉRIFICATION - AutoRevit')
            lines.append('=' * 60)
            lines.append('Généré le: ' + timestamp)
            lines.append('')
            lines.append('STATISTIQUES:')
            lines.append('  Vérifications: ' + str(self.stats["verifications_performed"]))
            lines.append('  Critiques: ' + str(self.stats["critical_issues"]))
            lines.append('  Erreurs: ' + str(self.stats["errors"]))
            lines.append('  Avertissements: ' + str(self.stats["warnings"]))
            lines.append('  Conformes: ' + str(self.stats["passed"]))
            
            return '\n'.join(lines)

    # ========================================================================
    # UTILITAIRES
    # ========================================================================

    def _get_element_id(self, element):
        """Récupère l'ID de l'élément."""
        try:
            return element.Id.IntegerValue
        except:
            return 0

    def _get_element_name(self, element):
        """Récupère le nom de l'élément."""
        try:
            return element.Name
        except:
            return ""

    def _get_element_category(self, element):
        """Récupère la catégorie de l'élément."""
        try:
            if element.Category:
                return element.Category.Name
        except:
            pass
        return ""

    def _feet_to_mm(self, feet):
        """Convertit feet en mm."""
        return feet * 304.8

    def _get_max_severity(self, checks):
        """Récupère la sévérité maximale des vérifications."""
        severity_order = {'CRITICAL': 4, 'ERROR': 3, 'WARNING': 2, 'INFO': 1, 'PASS': 0}
        max_severity = 'PASS'
        max_level = 0
        
        for check in checks:
            status = check.get('status', 'PASS')
            level = severity_order.get(status, 0)
            if level > max_level:
                max_level = level
                max_severity = status
        
        return max_severity

    def get_stats(self):
        """Récupère les statistiques du moteur."""
        return self.stats

    def reset_stats(self):
        """Réinitialise les statistiques."""
        self.stats = {
            'verifications_performed': 0,
            'critical_issues': 0,
            'errors': 0,
            'warnings': 0,
            'passed': 0
        }
        logger.info("Statistiques réinitialisées")


# ============================================================================
# FONCTION DE TEST
# ============================================================================

def test_verification_engine():
    """
    Test du moteur de vérification.
    """
    print("\n" + "="*60)
    print("TEST VERIFICATION ENGINE")
    print("="*60)
    
    if not REVIT_AVAILABLE:
        print("\n❌ Revit non disponible - test en mode développement")
    else:
        print("\n✅ Revit disponible")
    
    try:
        from pyrevit import revit
        
        print("\n1. Initialisation...")
        doc = revit.doc if REVIT_AVAILABLE else None
        engine = VerificationEngine(doc)
        print("   ✅ VerificationEngine créé")
        
        print("\n2. Test stats...")
        stats = engine.get_stats()
        print("   Stats: " + str(stats))
        
        print("\n3. Test vérification poteau...")
        if REVIT_AVAILABLE:
            columns = engine.get_structural_columns()
            if columns:
                results = engine.verify_geometry([columns[0]])
                print("   ✅ Vérification effectuée")
        
        print("\n" + "="*60)
        print("✅ TEST TERMINÉ")
        print("="*60 + "\n")
        
    except Exception as e:
        print("\n❌ ERREUR: " + str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_verification_engine()