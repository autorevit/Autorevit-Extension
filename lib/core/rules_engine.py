# -*- coding: utf-8 -*-
"""
RulesEngine - Moteur d'évaluation des règles métier (IF/THEN/ELSE)
==================================================================
Responsabilités :
- Évaluation de conditions complexes (and, or, not, comparaisons)
- Application de règles sur des éléments Revit
- Agrégation de résultats par règleset
- Support des opérateurs : ==, !=, >, <, >=, <=, in, not in, is_null, is_not_null
- Construction de contexte à partir d'éléments Revit

Auteur : AutoRevit Team
Date : 2025
"""

import time
import traceback
from utils.logger import get_logger
from utils.exceptions import AutoRevitError
from models.rule import Rule, RuleSet, RuleCondition
from services.logging_service import LoggingService

logger = get_logger(__name__)


class ValidationError(AutoRevitError):
    """Exception levée en cas d'erreur de validation."""
    pass


try:
    from Autodesk.Revit.DB import (
        Document, Element, FamilyInstance,
        Parameter, BuiltInParameter, ElementId
    )
    REVIT_AVAILABLE = True
except ImportError:
    REVIT_AVAILABLE = False
    logger.warning("Revit API non disponible (mode développement)")


class RulesEngine:
    """
    Moteur d'évaluation des règles métier.
    
    Exemple d'utilisation :
    ----------------------
    >>> from core import RulesEngine
    >>> from config import api_client
    >>>
    >>> engine = RulesEngine(api_client)
    >>>
    >>> # Évaluer une règle unique
    >>> result = engine.evaluate_rule(rule, element_context)
    >>>
    >>> # Appliquer un règleset à des éléments
    >>> violations = engine.apply_ruleset("STRUCTURAL_CHECKS", elements)
    >>>
    >>> # Vérifier conformité normes
    >>> compliance = engine.check_compliance(elements, "EC2")
    """

    # Opérateurs supportés et leur signification
    OPERATORS = {
        'eq': '==',
        'ne': '!=',
        'gt': '>',
        'lt': '<',
        'ge': '>=',
        'le': '<=',
        'in': 'dans',
        'not_in': 'pas dans',
        'is_null': 'est nul',
        'is_not_null': "n'est pas nul"
    }

    def __init__(self, api_client=None):
        """
        Initialise le moteur de règles.
        
        Args:
            api_client: Client API optionnel pour charger règles
        """
        self.api = api_client
        self.logger = LoggingService(api_client) if api_client else None
        
        # Cache des règles
        self._rules_cache = {}
        self._rulesets_cache = {}
        
        # Statistiques
        self.stats = {
            'rules_evaluated': 0,
            'rules_passed': 0,
            'rules_failed': 0,
            'rulesets_applied': 0
        }
        
        logger.info("RulesEngine initialise")

    def evaluate_rule(self, rule, context):
        """
        Évalue une règle dans un contexte donné.
        
        Args:
            rule (Rule/dict): Règle à évaluer
            context (dict): Contexte d'évaluation
        
        Returns:
            dict: Résultat de l'évaluation
        """
        start_time = time.time()
        
        try:
            if isinstance(rule, dict):
                rule_obj = Rule(rule)
            else:
                rule_obj = rule
            
            result = rule_obj.evaluate(context)
            
            self.stats['rules_evaluated'] += 1
            if result['condition_result']:
                self.stats['rules_passed'] += 1
            else:
                self.stats['rules_failed'] += 1
            
            logger.debug("Regle evaluee: " + rule_obj.code + " = " + str(result['condition_result']))
            
            return result
            
        except Exception as e:
            logger.error("Erreur evaluation regle: " + str(e))
            raise ValidationError("Echec evaluation regle: " + str(e))

    def evaluate_condition(self, condition, context):
        """
        Évalue une condition seule.
        
        Args:
            condition (dict): Définition de la condition
            context (dict): Contexte d'évaluation
        
        Returns:
            bool: Résultat de l'évaluation
        """
        try:
            cond = RuleCondition(condition)
            return cond.evaluate(context)
        except Exception as e:
            logger.error("Erreur evaluation condition: " + str(e))
            return False

    def apply_rule_to_element(self, rule, element):
        """
        Applique une règle à un élément Revit.
        
        Args:
            rule (Rule/dict): Règle à appliquer
            element (Element): Élément Revit
        
        Returns:
            dict: Résultat de l'évaluation
        """
        context = self._build_element_context(element)
        return self.evaluate_rule(rule, context)

    def apply_ruleset(self, ruleset_code, elements, filter_active=True):
        """
        Applique un ensemble de règles à des éléments.
        
        Args:
            ruleset_code (str): Code du règleset
            elements (list): Liste d'éléments Revit
            filter_active (bool): N'appliquer que les règles actives
        
        Returns:
            list: Résultats pour chaque élément/rule
        """
        start_time = time.time()
        logger.info("Application ruleset: " + ruleset_code + " sur " + str(len(elements)) + " elements")
        
        try:
            ruleset = self._get_ruleset(ruleset_code)
            if not ruleset:
                raise ValidationError("Ruleset non trouve: " + ruleset_code)
            
            results = []
            violations = []
            warnings = []
            infos = []
            
            for element in elements:
                context = self._build_element_context(element)
                
                for rule in ruleset.rules:
                    if filter_active and not rule.is_active:
                        continue
                    
                    result = rule.evaluate(context)
                    
                    result['element_id'] = self._get_element_id(element)
                    result['element_name'] = self._get_element_name(element)
                    
                    results.append(result)
                    
                    if not result['condition_result']:
                        if result['severity'] == 'error' or result['severity'] == 'critical':
                            violations.append(result)
                        elif result['severity'] == 'warning':
                            warnings.append(result)
                        else:
                            infos.append(result)
            
            self.stats['rulesets_applied'] += 1
            
            duration = time.time() - start_time
            logger.info("Ruleset applique: " + ruleset_code + 
                       " (" + str(len(violations)) + " violations, " +
                       str(len(warnings)) + " avertissements) - " + str(round(duration, 2)) + "s")
            
            return {
                'ruleset': ruleset_code,
                'ruleset_name': ruleset.name,
                'elements_checked': len(elements),
                'rules_evaluated': len(results),
                'violations': violations,
                'warnings': warnings,
                'infos': infos,
                'total_issues': len(violations) + len(warnings) + len(infos),
                'duration': duration,
                'results': results
            }
            
        except Exception as e:
            logger.error("Erreur application ruleset: " + str(e))
            raise

    def check_compliance(self, elements, norm_code):
        """
        Vérifie la conformité d'éléments à une norme.
        
        Args:
            elements (list): Liste d'éléments Revit
            norm_code (str): Code de la norme (EC2, BAEL91, etc.)
        
        Returns:
            dict: Rapport de conformité
        """
        ruleset_code = "NORM_" + norm_code
        return self.apply_ruleset(ruleset_code, elements)

    def _build_element_context(self, element):
        """
        Construit un contexte d'évaluation à partir d'un élément Revit.
        
        Args:
            element (Element): Élément Revit
        
        Returns:
            dict: Contexte avec paramètres et propriétés
        """
        context = {
            'element': {
                'id': self._get_element_id(element),
                'name': self._get_element_name(element),
                'category': self._get_element_category(element),
                'family': self._get_element_family(element),
                'type': self._get_element_type(element),
                'level': self._get_element_level(element)
            },
            'parameters': self._get_element_parameters(element),
            'geometry': self._get_element_geometry_context(element),
            'location': self._get_element_location(element)
        }
        
        return context

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

    def _get_element_family(self, element):
        """Récupère la famille de l'élément."""
        try:
            if hasattr(element, 'Symbol'):
                return element.Symbol.Family.Name
        except:
            pass
        return ""

    def _get_element_type(self, element):
        """Récupère le type de l'élément."""
        try:
            if hasattr(element, 'Symbol'):
                return element.Symbol.Name
        except:
            pass
        return ""

    def _get_element_level(self, element):
        """Récupère le niveau de l'élément."""
        try:
            if REVIT_AVAILABLE:
                param = element.get_Parameter(BuiltInParameter.FAMILY_LEVEL_PARAM)
                if param and param.HasValue:
                    level_id = param.AsElementId()
                    if level_id and level_id.IntegerValue > 0:
                        doc = element.Document
                        level = doc.GetElement(level_id)
                        return level.Name
        except:
            pass
        return ""

    def _get_element_parameters(self, element):
        """
        Récupère tous les paramètres importants de l'élément.
        
        Returns:
            dict: Paramètres {nom: valeur}
        """
        params = {}
        
        if not REVIT_AVAILABLE:
            return params
        
        try:
            for builtin in [
                BuiltInParameter.FAMILY_WIDTH_PARAM,
                BuiltInParameter.FAMILY_HEIGHT_PARAM,
                BuiltInParameter.FAMILY_LENGTH_PARAM,
                BuiltInParameter.FLOOR_ATTR_THICKNESS_PARAM,
                BuiltInParameter.WALL_ATTR_WIDTH_PARAM
            ]:
                param = element.get_Parameter(builtin)
                if param and param.HasValue:
                    name = param.Definition.Name
                    params[name] = param.AsDouble()
                    params[name + '_mm'] = self._feet_to_mm(param.AsDouble())
            
            for builtin in [
                BuiltInParameter.STRUCTURAL_LOADS_APPLIED_FORCE1,
                BuiltInParameter.STRUCTURAL_LOADS_APPLIED_FORCE2,
                BuiltInParameter.STRUCTURAL_LOADS_APPLIED_FORCE3
            ]:
                param = element.get_Parameter(builtin)
                if param and param.HasValue:
                    name = param.Definition.Name
                    params[name] = param.AsDouble()
                    params[name + '_kN'] = self._feet_to_mm(param.AsDouble()) / 1000
            
            mat_param = element.get_Parameter(BuiltInParameter.STRUCTURAL_MATERIAL_PARAM)
            if mat_param and mat_param.HasValue:
                mat_id = mat_param.AsElementId()
                if mat_id.IntegerValue > 0:
                    doc = element.Document
                    material = doc.GetElement(mat_id)
                    params['material'] = material.Name
            
        except Exception as e:
            logger.debug("Erreur extraction parametres: " + str(e))
        
        return params

    def _get_element_geometry_context(self, element):
        """Récupère les informations géométriques de l'élément."""
        geo = {}
        
        try:
            bbox = element.get_BoundingBox(None)
            if bbox:
                width = bbox.Max.X - bbox.Min.X
                depth = bbox.Max.Y - bbox.Min.Y
                height = bbox.Max.Z - bbox.Min.Z
                
                geo['width'] = width
                geo['depth'] = depth
                geo['height'] = height
                geo['width_mm'] = self._feet_to_mm(width)
                geo['depth_mm'] = self._feet_to_mm(depth)
                geo['height_mm'] = self._feet_to_mm(height)
                geo['volume'] = width * depth * height
                geo['volume_m3'] = self._feet_to_mm(width) * self._feet_to_mm(depth) * self._feet_to_mm(height) / 1e9
                
        except Exception as e:
            logger.debug("Erreur extraction geometrie: " + str(e))
        
        return geo

    def _get_element_location(self, element):
        """Récupère la localisation de l'élément."""
        loc = {}
        
        try:
            location = element.Location
            if hasattr(location, 'Point'):
                point = location.Point
                loc['x'] = point.X
                loc['y'] = point.Y
                loc['z'] = point.Z
                loc['x_mm'] = self._feet_to_mm(point.X)
                loc['y_mm'] = self._feet_to_mm(point.Y)
                loc['z_mm'] = self._feet_to_mm(point.Z)
            elif hasattr(location, 'Curve'):
                curve = location.Curve
                start = curve.GetEndPoint(0)
                end = curve.GetEndPoint(1)
                loc['start'] = {'x': start.X, 'y': start.Y, 'z': start.Z}
                loc['end'] = {'x': end.X, 'y': end.Y, 'z': end.Z}
                loc['length'] = curve.Length
                loc['length_mm'] = self._feet_to_mm(curve.Length)
        except Exception as e:
            logger.debug("Erreur extraction localisation: " + str(e))
        
        return loc

    def _feet_to_mm(self, feet):
        """Convertit feet en mm."""
        return feet * 304.8

    def _get_ruleset(self, ruleset_code):
        """
        Récupère un règleset depuis le cache ou l'API.
        
        Args:
            ruleset_code (str): Code du règleset
        
        Returns:
            RuleSet: Instance du règleset ou None
        """
        if ruleset_code in self._rulesets_cache:
            logger.debug("Ruleset trouve dans cache: " + ruleset_code)
            return self._rulesets_cache[ruleset_code]
        
        if self.api:
            try:
                data = self.api.get_ruleset(ruleset_code)
                if data:
                    ruleset = RuleSet(data)
                    self._rulesets_cache[ruleset_code] = ruleset
                    logger.debug("Ruleset charge depuis API: " + ruleset_code)
                    return ruleset
            except Exception as e:
                logger.warning("Impossible de charger ruleset " + ruleset_code + ": " + str(e))
        
        return None

    def get_rule(self, rule_code):
        """
        Récupère une règle depuis le cache ou l'API.
        
        Args:
            rule_code (str): Code de la règle
        
        Returns:
            Rule: Instance de la règle ou None
        """
        if rule_code in self._rules_cache:
            return self._rules_cache[rule_code]
        
        if self.api:
            try:
                data = self.api.get_rule(rule_code)
                if data:
                    rule = Rule(data)
                    self._rules_cache[rule_code] = rule
                    return rule
            except Exception as e:
                logger.warning("Impossible de charger regle " + rule_code + ": " + str(e))
        
        return None

    def clear_cache(self):
        """Vide le cache des règles et règlesets."""
        self._rules_cache.clear()
        self._rulesets_cache.clear()
        logger.info("Cache des regles vide")

    def get_stats(self):
        """
        Récupère les statistiques du moteur.
        
        Returns:
            dict: Statistiques
        """
        return {
            'rules_evaluated': self.stats['rules_evaluated'],
            'rules_passed': self.stats['rules_passed'],
            'rules_failed': self.stats['rules_failed'],
            'rulesets_applied': self.stats['rulesets_applied'],
            'success_rate': round(
                (self.stats['rules_passed'] / max(self.stats['rules_evaluated'], 1)) * 100, 
                1
            ),
            'cache_rules': len(self._rules_cache),
            'cache_rulesets': len(self._rulesets_cache)
        }

    def reset_stats(self):
        """Réinitialise les statistiques."""
        self.stats = {
            'rules_evaluated': 0,
            'rules_passed': 0,
            'rules_failed': 0,
            'rulesets_applied': 0
        }
        logger.info("Statistiques reinitialisees")


def test_rules_engine():
    """Test du moteur de règles."""
    print("\n" + "="*60)
    print("TEST RULES ENGINE")
    print("="*60)
    
    try:
        print("\n1. Initialisation...")
        engine = RulesEngine(api_client=None)
        print("   ✅ RulesEngine cree")
        
        print("\n2. Test condition simple...")
        condition = {
            'operator': 'eq',
            'field': 'test',
            'value': 42
        }
        context = {'test': 42}
        result = engine.evaluate_condition(condition, context)
        print("   Condition eq: " + str(result) + " (attendu: True)")
        
        print("\n3. Test condition composee...")
        condition_and = {
            'operator': 'and',
            'conditions': [
                {'operator': 'gt', 'field': 'a', 'value': 10},
                {'operator': 'lt', 'field': 'b', 'value': 20}
            ]
        }
        context = {'a': 15, 'b': 18}
        result = engine.evaluate_condition(condition_and, context)
        print("   Condition and: " + str(result) + " (attendu: True)")
        
        print("\n4. Test condition in...")
        condition_in = {
            'operator': 'in',
            'field': 'value',
            'value': [1, 2, 3, 4, 5]
        }
        context = {'value': 3}
        result = engine.evaluate_condition(condition_in, context)
        print("   Condition in: " + str(result) + " (attendu: True)")
        
        print("\n5. Test stats...")
        stats = engine.get_stats()
        print("   Stats: " + str(stats))
        
        print("\n" + "="*60)
        print("✅ TEST TERMINE")
        print("="*60 + "\n")
        
    except Exception as e:
        print("\n❌ ERREUR: " + str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_rules_engine()