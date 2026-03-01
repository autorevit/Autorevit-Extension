# -*- coding: utf-8 -*-
"""
CreationEngine - Moteur de création d'éléments Revit
=====================================================
Responsabilités :
- Création de poteaux aux intersections de grilles
- Création de poutres entre appuis
- Création de dalles sur panneaux
- Création de fondations sous poteaux/murs
- Création de voiles avec détection d'ouvertures
- Gestion des familles et types

Auteur : AutoRevit Team
Date : 2025
"""

import math
import traceback
from utils.logger import get_logger
from services.revit_service import RevitService
from services.geometry_service import GeometryService
from services.transaction_service import TransactionService
from services.logging_service import LoggingService
from algorithms.geometry_utils import (
    calculate_grid_intersections,
    find_intermediate_points,
    get_midpoint,
    calculate_distance_mm
)

logger = get_logger(__name__)

# Exceptions personnalisees
class RevitAPIError(Exception):
    """Exception levee quand Revit API n'est pas disponible"""
    pass

class ValidationError(Exception):
    """Exception levee lors d'erreurs de validation"""
    pass


try:
    from Autodesk.Revit.DB import (
        Document,
        FamilyInstance,
        FamilySymbol,
        Level,
        Grid,
        Wall,
        Floor,
        BuiltInCategory,
        BuiltInParameter,
        XYZ,
        Line,
        CurveLoop,
        Transaction,
        FilteredElementCollector,
        ElementId
    )
    from Autodesk.Revit.DB.Structure import StructuralType
    REVIT_AVAILABLE = True
except Exception as _revit_import_err:
    REVIT_AVAILABLE = False
    import sys
    sys.stderr.write("Import error in creation_engine.py: " + str(_revit_import_err) + "\n")
     
    
    # Classes factices pour mode développement
    class XYZ:
        def __init__(self, x=0, y=0, z=0):
            self.X = x
            self.Y = y
            self.Z = z


class CreationEngine:
    """
    Moteur de création d'éléments structurels Revit.
    
    Exemple d'utilisation :
    ----------------------
    >>> from pyrevit import revit
    >>> from core import CreationEngine
    >>>
    >>> doc = revit.doc
    >>> engine = CreationEngine(doc)
    >>>
    >>> # Créer des poteaux
    >>> columns = engine.create_columns_at_grids(
    ...     level_base, level_top,
    ...     section=(400, 400)
    ... )
    >>>
    >>> # Créer des poutres
    >>> beams = engine.create_beams_between_columns(level)
    """

    def __init__(self, document):
        """
        Initialise le moteur de création.
        
        Args:
            document: Document Revit actif
        """
        if not REVIT_AVAILABLE and document is not None:
            logger.warning("Revit API non disponible - création limitée")
        
        self.doc = document
        
        # Services
        self.revit_service = RevitService(document)
        self.geometry_service = GeometryService(document)
        self.transaction_service = TransactionService(document)
        self.logger = LoggingService()
        
        # Cache des familles
        self._column_families_cache = {}
        self._beam_families_cache = {}
        self._wall_families_cache = {}
        self._floor_families_cache = {}
        self._foundation_families_cache = {}
        
        # Statistiques
        self.stats = {
            'columns_created': 0,
            'beams_created': 0,
            'slabs_created': 0,
            'walls_created': 0,
            'foundations_created': 0
        }
        
        logger.info("CreationEngine initialisé")

    # ========================================================================
    # CRÉATION DE POTEAUX
    # ========================================================================

    def create_columns_at_grids(self, base_level, top_level, section=(300, 300)):
        """
        Crée des poteaux à toutes les intersections de grilles.
        
        Args:
            base_level (Level): Niveau de base
            top_level (Level): Niveau supérieur
            section (tuple): (largeur, hauteur) en mm
        
        Returns:
            list: Poteaux créés
        """
        logger.info("Création poteaux aux intersections de grilles")
        
        try:
            # Récupérer les grilles
            grids = self.revit_service.get_all_grids()
            if len(grids) < 2:
                raise ValidationError("Au moins 2 grilles requises")
            
            # Séparer grilles horizontales/verticales
            h_grids = []
            v_grids = []
            
            for grid in grids:
                curve = grid.Curve
                direction = curve.Direction
                if abs(direction.X) > abs(direction.Y):
                    h_grids.append(grid)
                else:
                    v_grids.append(grid)
            
            # Calculer les intersections
            points = []
            for v_grid in v_grids:
                v_curve = v_grid.Curve
                for h_grid in h_grids:
                    h_curve = h_grid.Curve
                    intersection = self.geometry_service.get_intersection(v_curve, h_curve)
                    if intersection:
                        points.append({
                            'point': intersection,
                            'grid_x': h_grid.Name,
                            'grid_y': v_grid.Name
                        })
            
            # Créer les poteaux
            return self.create_columns(
                points,
                section,
                base_level,
                top_level
            )
            
        except Exception as e:
            logger.error("Erreur création poteaux aux grilles: " + str(e))
            raise RevitAPIError("Échec création poteaux: " + str(e))

    def create_columns(self, locations, section, base_level, top_level):
        """
        Crée des poteaux à des positions données.
        
        Args:
            locations (list): Liste de points ou dict avec 'point'
            section (tuple): (largeur, hauteur) en mm
            base_level (Level): Niveau de base
            top_level (Level): Niveau supérieur
        
        Returns:
            list: Poteaux créés
        """
        width_mm, height_mm = section
        created = []
        
        try:
            # Récupérer le type de poteau
            column_type = self._get_column_family(width_mm, height_mm)
            if not column_type:
                raise ValidationError(
                    "Type poteau non trouvé: " + str(width_mm) + "x" + str(height_mm)
                )
            
            # Activer le type
            if not column_type.IsActive:
                column_type.Activate()
            
            # Créer chaque poteau
            for loc in locations:
                point = loc['point'] if isinstance(loc, dict) else loc
                
                column = self.doc.Create.NewFamilyInstance(
                    point,
                    column_type,
                    base_level,
                    StructuralType.Column
                )
                
                # Définir le niveau supérieur
                column.get_Parameter(
                    BuiltInParameter.FAMILY_TOP_LEVEL_PARAM
                ).Set(top_level.Id)
                
                # Ajouter commentaire
                comment_param = column.LookupParameter("Comments")
                if comment_param:
                    grid_ref = ""
                    if isinstance(loc, dict) and 'grid_x' in loc and 'grid_y' in loc:
                        grid_ref = " - " + loc['grid_x'] + "/" + loc['grid_y']
                    
                    comment_param.Set(
                        "AutoRevit - " + str(width_mm) + "x" + str(height_mm) + "mm" + grid_ref
                    )
                
                created.append(column)
                self.stats['columns_created'] += 1
            
            logger.info(str(len(created)) + " poteaux créés (" + str(width_mm) + "x" + str(height_mm) + "mm)")
            return created
            
        except Exception as e:
            logger.error("Erreur création poteaux: " + str(e))
            raise RevitAPIError("Échec création poteaux: " + str(e))

    def _get_column_family(self, width_mm, height_mm):
        """
        Récupère ou crée la famille de poteau.
        
        Args:
            width_mm (int): Largeur en mm
            height_mm (int): Hauteur en mm
        
        Returns:
            FamilySymbol: Type de poteau
        """
        cache_key = str(width_mm) + "x" + str(height_mm)
        
        if cache_key in self._column_families_cache:
            return self._column_families_cache[cache_key]
        
        # Chercher dans les types existants
        collector = FilteredElementCollector(self.doc)\
            .OfCategory(BuiltInCategory.OST_StructuralColumns)\
            .WhereElementIsElementType()
        
        width_feet = width_mm / 304.8
        height_feet = height_mm / 304.8
        
        for symbol in collector:
            # Vérifier les dimensions
            w_param = symbol.LookupParameter("Largeur") or symbol.LookupParameter("Width")
            h_param = symbol.LookupParameter("Hauteur") or symbol.LookupParameter("Height")
            
            if w_param and h_param:
                try:
                    w_val = w_param.AsDouble()
                    h_val = h_param.AsDouble()
                    
                    if abs(w_val - width_feet) < 0.01 and abs(h_val - height_feet) < 0.01:
                        self._column_families_cache[cache_key] = symbol
                        return symbol
                except:
                    pass
        
        # Utiliser le premier type disponible
        first = collector.FirstElement()
        if first:
            self._column_families_cache[cache_key] = first
            return first
        
        return None

    # ========================================================================
    # CRÉATION DE POUTRES
    # ========================================================================

    def create_beams_between_columns(self, level):
        """
        Crée des poutres entre les poteaux d'un niveau.
        
        Args:
            level (Level): Niveau
        
        Returns:
            list: Poutres créées
        """
        logger.info("Création poutres entre poteaux - Niveau: " + level.Name)
        
        try:
            # Récupérer les poteaux du niveau
            columns = self.revit_service.get_structural_columns(level)
            if len(columns) < 2:
                raise ValidationError("Au moins 2 poteaux requis")
            
            # Extraire les points
            column_points = []
            for col in columns:
                point = self.revit_service.get_element_location_point(col)
                if point:
                    column_points.append({
                        'point': point,
                        'id': col.Id,
                        'element': col
                    })
            
            # Trier par X et Y
            column_points.sort(key=lambda p: (p['point'].X, p['point'].Y))
            
            beam_data = []
            
            # Poutres horizontales (même Y)
            y_groups = {}
            for col in column_points:
                y = round(col['point'].Y, 3)
                if y not in y_groups:
                    y_groups[y] = []
                y_groups[y].append(col)
            
            for y, group in y_groups.items():
                group.sort(key=lambda p: p['point'].X)
                for i in range(len(group) - 1):
                    col1 = group[i]
                    col2 = group[i + 1]
                    
                    span_mm = calculate_distance_mm(col1['point'], col2['point'])
                    
                    beam_data.append({
                        'start': col1['point'],
                        'end': col2['point'],
                        'level': level,
                        'span_mm': span_mm,
                        'type': 'PRINCIPALE' if span_mm < 6000 else 'SECONDAIRE'
                    })
            
            # Poutres verticales (même X)
            x_groups = {}
            for col in column_points:
                x = round(col['point'].X, 3)
                if x not in x_groups:
                    x_groups[x] = []
                x_groups[x].append(col)
            
            for x, group in x_groups.items():
                group.sort(key=lambda p: p['point'].Y)
                for i in range(len(group) - 1):
                    col1 = group[i]
                    col2 = group[i + 1]
                    
                    beam_data.append({
                        'start': col1['point'],
                        'end': col2['point'],
                        'level': level,
                        'span_mm': calculate_distance_mm(col1['point'], col2['point']),
                        'type': 'SECONDAIRE'
                    })
            
            # Créer les poutres
            return self.create_beams(beam_data)
            
        except Exception as e:
            logger.error("Erreur création poutres entre poteaux: " + str(e))
            raise RevitAPIError("Échec création poutres: " + str(e))

    def create_beams(self, beam_data):
        """
        Crée des poutres selon les données fournies.
        
        Args:
            beam_data (list): Liste de dict avec start, end, level, type, span_mm
        
        Returns:
            list: Poutres créées
        """
        created = []
        
        try:
            for data in beam_data:
                # Calculer dimensions selon portée
                span_m = data['span_mm'] / 1000.0
                
                if data['type'] == 'PRINCIPALE':
                    height_mm = (span_m / 9) * 1000  # L/9
                    height_mm = int(round(height_mm / 50)) * 50
                    width_mm = int(height_mm * 0.4)
                    width_mm = int(round(width_mm / 50)) * 50
                else:
                    height_mm = 300  # Poutre secondaire
                    width_mm = 200
                
                # Récupérer le type de poutre
                beam_type = self._get_beam_family(width_mm, height_mm)
                if not beam_type:
                    logger.warning("Type poutre non trouvé: " + str(width_mm) + "x" + str(height_mm))
                    continue
                
                if not beam_type.IsActive:
                    beam_type.Activate()
                
                # Créer la ligne
                line = Line.CreateBound(data['start'], data['end'])
                
                # Créer la poutre
                beam = self.doc.Create.NewFamilyInstance(
                    line,
                    beam_type,
                    data['level'],
                    StructuralType.Beam
                )
                
                # Ajouter commentaire
                comment_param = beam.LookupParameter("Comments")
                if comment_param:
                    comment_param.Set(
                        "AutoRevit - " + data['type'] + " - " +
                        str(width_mm) + "x" + str(height_mm) + "mm - L=" + str(int(data['span_mm'])) + "mm"
                    )
                
                created.append(beam)
                self.stats['beams_created'] += 1
            
            logger.info(str(len(created)) + " poutres créées")
            return created
            
        except Exception as e:
            logger.error("Erreur création poutres: " + str(e))
            raise RevitAPIError("Échec création poutres: " + str(e))

    def _get_beam_family(self, width_mm, height_mm):
        """
        Récupère la famille de poutre.
        
        Args:
            width_mm (int): Largeur en mm
            height_mm (int): Hauteur en mm
        
        Returns:
            FamilySymbol: Type de poutre
        """
        cache_key = str(width_mm) + "x" + str(height_mm)
        
        if cache_key in self._beam_families_cache:
            return self._beam_families_cache[cache_key]
        
        collector = FilteredElementCollector(self.doc)\
            .OfCategory(BuiltInCategory.OST_StructuralFraming)\
            .WhereElementIsElementType()
        
        width_feet = width_mm / 304.8
        height_feet = height_mm / 304.8
        
        for symbol in collector:
            w_param = symbol.LookupParameter("Largeur") or symbol.LookupParameter("Width")
            h_param = symbol.LookupParameter("Hauteur") or symbol.LookupParameter("Height")
            
            if w_param and h_param:
                try:
                    w_val = w_param.AsDouble()
                    h_val = h_param.AsDouble()
                    
                    if abs(w_val - width_feet) < 0.01 and abs(h_val - height_feet) < 0.01:
                        self._beam_families_cache[cache_key] = symbol
                        return symbol
                except:
                    pass
        
        first = collector.FirstElement()
        if first:
            self._beam_families_cache[cache_key] = first
            return first
        
        return None

    # ========================================================================
    # CRÉATION DE DALLES
    # ========================================================================

    def create_slab_on_beam_panels(self, level, thickness_mm=160):
        """
        Crée des dalles sur les panneaux délimités par des poutres.
        
        Args:
            level (Level): Niveau
            thickness_mm (int): Épaisseur dalle en mm
        
        Returns:
            list: Dalles créées
        """
        logger.info("Création dalles - Niveau: " + level.Name + " épaisseur: " + str(thickness_mm) + "mm")
        
        try:
            # Récupérer les poutres du niveau
            beams = self.revit_service.get_structural_framing(level)
            if len(beams) < 4:
                raise ValidationError("Au moins 4 poutres requises pour former des panneaux")
            
            # Récupérer les lignes des poutres
            beam_lines = []
            for beam in beams:
                curve = self.revit_service.get_element_location_curve(beam)
                if curve:
                    beam_lines.append(curve)
            
            # Grouper par orientation
            h_lines = []
            v_lines = []
            
            for line in beam_lines:
                start = line.GetEndPoint(0)
                end = line.GetEndPoint(1)
                
                if abs(start.Y - end.Y) < 0.001:
                    h_lines.append(line)
                else:
                    v_lines.append(line)
            
            # Trier par position
            h_lines.sort(key=lambda l: l.GetEndPoint(0).Y)
            v_lines.sort(key=lambda l: l.GetEndPoint(0).X)
            
            # Créer les dalles
            slabs = []
            
            for i in range(len(h_lines) - 1):
                for j in range(len(v_lines) - 1):
                    y1 = h_lines[i].GetEndPoint(0).Y
                    y2 = h_lines[i + 1].GetEndPoint(0).Y
                    x1 = v_lines[j].GetEndPoint(0).X
                    x2 = v_lines[j + 1].GetEndPoint(0).X
                    
                    # Points du rectangle
                    p1 = XYZ(x1, y1, level.Elevation)
                    p2 = XYZ(x2, y1, level.Elevation)
                    p3 = XYZ(x2, y2, level.Elevation)
                    p4 = XYZ(x1, y2, level.Elevation)
                    
                    slab = self.create_slab([p1, p2, p3, p4], level, thickness_mm)
                    if slab:
                        slabs.append(slab)
            
            logger.info(str(len(slabs)) + " dalles créées")
            return slabs
            
        except Exception as e:
            logger.error("Erreur création dalles: " + str(e))
            raise RevitAPIError("Échec création dalles: " + str(e))

    def create_slab(self, boundary_points, level, thickness_mm=160):
        """
        Crée une dalle à partir d'un contour.
        
        Args:
            boundary_points (list): Liste de 4 points XYZ
            level (Level): Niveau
            thickness_mm (int): Épaisseur en mm
        
        Returns:
            Floor: Dalle créée
        """
        try:
            # Récupérer le type de dalle
            floor_type = self._get_floor_type(thickness_mm)
            if not floor_type:
                logger.warning("Type dalle non trouvé pour épaisseur " + str(thickness_mm) + "mm")
                return None
            
            # Créer le contour
            curve_loop = CurveLoop()
            
            for i in range(len(boundary_points)):
                start = boundary_points[i]
                end = boundary_points[(i + 1) % len(boundary_points)]
                curve_loop.Append(Line.CreateBound(start, end))
            
            # Créer la dalle
            floor = Floor.Create(self.doc, [curve_loop], floor_type.Id, level.Id)
            
            # Définir l'épaisseur
            thickness_param = floor.get_Parameter(
                BuiltInParameter.FLOOR_ATTR_DEFAULT_THICKNESS_PARAM
            )
            if thickness_param:
                thickness_param.Set(thickness_mm / 304.8)
            
            # Ajouter commentaire
            comment_param = floor.LookupParameter("Comments")
            if comment_param:
                width_m = abs(boundary_points[1].X - boundary_points[0].X) * 304.8 / 1000
                length_m = abs(boundary_points[2].Y - boundary_points[1].Y) * 304.8 / 1000
                comment_param.Set(
                    "AutoRevit - Dalle e=" + str(thickness_mm) + "mm - " +
                    str(int(width_m)) + "x" + str(int(length_m)) + "m"
                )
            
            self.stats['slabs_created'] += 1
            return floor
            
        except Exception as e:
            logger.error("Erreur création dalle: " + str(e))
            return None

    def _get_floor_type(self, thickness_mm):
        """
        Récupère le type de dalle.
        
        Args:
            thickness_mm (int): Épaisseur en mm
        
        Returns:
            FloorType: Type de dalle
        """
        cache_key = "floor_" + str(thickness_mm)
        
        if cache_key in self._floor_families_cache:
            return self._floor_families_cache[cache_key]
        
        collector = FilteredElementCollector(self.doc)\
            .OfClass(Floor)\
            .WhereElementIsElementType()
        
        thickness_feet = thickness_mm / 304.8
        
        for floor_type in collector:
            # Chercher par nom
            if str(thickness_mm) + "mm" in floor_type.Name:
                self._floor_families_cache[cache_key] = floor_type
                return floor_type
        
        first = collector.FirstElement()
        if first:
            self._floor_families_cache[cache_key] = first
            return first
        
        return None

    # ========================================================================
    # CRÉATION DE FONDATIONS
    # ========================================================================

    def create_foundations_under_columns(self, base_level, footing_size=(800, 800, 300)):
        """
        Crée des semelles sous tous les poteaux.
        
        Args:
            base_level (Level): Niveau de fondation
            footing_size (tuple): (largeur, longueur, épaisseur) en mm
        
        Returns:
            list: Semelles créées
        """
        logger.info("Création fondations sous poteaux")
        
        try:
            # Récupérer tous les poteaux
            columns = self.revit_service.get_structural_columns()
            
            created = []
            for column in columns:
                point = self.revit_service.get_element_location_point(column)
                if point:
                    footing = self.create_foundation(
                        point,
                        base_level,
                        footing_size
                    )
                    if footing:
                        created.append(footing)
            
            logger.info(str(len(created)) + " fondations créées")
            return created
            
        except Exception as e:
            logger.error("Erreur création fondations: " + str(e))
            raise RevitAPIError("Échec création fondations: " + str(e))

    def create_foundation(self, point, level, dimensions=(800, 800, 300)):
        """
        Crée une semelle isolée.
        
        Args:
            point (XYZ): Point d'insertion
            level (Level): Niveau
            dimensions (tuple): (largeur, longueur, épaisseur) en mm
        
        Returns:
            FamilyInstance: Semelle créée
        """
        try:
            width_mm, length_mm, thickness_mm = dimensions
            
            # Récupérer la famille de semelle
            footing_type = self._get_foundation_family()
            if not footing_type:
                logger.warning("Type semelle non trouvé")
                return None
            
            if not footing_type.IsActive:
                footing_type.Activate()
            
            # Point d'insertion
            footing_point = XYZ(point.X, point.Y, level.Elevation)
            
            # Créer la semelle
            footing = self.doc.Create.NewFamilyInstance(
                footing_point,
                footing_type,
                level,
                StructuralType.Footing
            )
            
            # Définir les dimensions
            w_param = footing.LookupParameter("Largeur") or footing.LookupParameter("Width")
            l_param = footing.LookupParameter("Longueur") or footing.LookupParameter("Length")
            t_param = footing.LookupParameter("Épaisseur") or footing.LookupParameter("Thickness")
            
            if w_param:
                w_param.Set(width_mm / 304.8)
            if l_param:
                l_param.Set(length_mm / 304.8)
            if t_param:
                t_param.Set(thickness_mm / 304.8)
            
            # Ajouter commentaire
            comment_param = footing.LookupParameter("Comments")
            if comment_param:
                comment_param.Set(
                    "AutoRevit - Semelle isolée - " +
                    str(width_mm) + "x" + str(length_mm) + "x" + str(thickness_mm) + "mm"
                )
            
            self.stats['foundations_created'] += 1
            return footing
            
        except Exception as e:
            logger.error("Erreur création fondation: " + str(e))
            return None

    def _get_foundation_family(self):
        """
        Récupère la famille de semelle.
        
        Returns:
            FamilySymbol: Type de semelle
        """
        cache_key = "foundation_default"
        
        if cache_key in self._foundation_families_cache:
            return self._foundation_families_cache[cache_key]
        
        collector = FilteredElementCollector(self.doc)\
            .OfCategory(BuiltInCategory.OST_StructuralFoundation)\
            .OfClass(FamilySymbol)
        
        for symbol in collector:
            if "isolée" in symbol.Name.lower() or "isolated" in symbol.Name.lower():
                self._foundation_families_cache[cache_key] = symbol
                return symbol
        
        first = collector.FirstElement()
        if first:
            self._foundation_families_cache[cache_key] = first
            return first
        
        return None

    # ========================================================================
    # STATISTIQUES
    # ========================================================================

    def get_stats(self):
        """
        Récupère les statistiques de création.
        
        Returns:
            dict: Statistiques
        """
        return {
            'columns_created': self.stats['columns_created'],
            'beams_created': self.stats['beams_created'],
            'slabs_created': self.stats['slabs_created'],
            'walls_created': self.stats['walls_created'],
            'foundations_created': self.stats['foundations_created'],
            'total_elements': sum(self.stats.values())
        }

    def reset_stats(self):
        """Réinitialise les statistiques."""
        self.stats = {
            'columns_created': 0,
            'beams_created': 0,
            'slabs_created': 0,
            'walls_created': 0,
            'foundations_created': 0
        }
        logger.info("Statistiques réinitialisées")


# ============================================================================
# FONCTION DE TEST
# ============================================================================

def test_creation_engine():
    """
    Test du moteur de création.
    """
    print("\n" + "="*60)
    print("TEST CREATION ENGINE")
    print("="*60)
    
    if not REVIT_AVAILABLE:
        print("\n❌ Revit non disponible - test en mode développement")
    else:
        print("\n✅ Revit disponible")
    
    try:
        from pyrevit import revit
        
        print("\n1. Initialisation...")
        doc = revit.doc if REVIT_AVAILABLE else None
        engine = CreationEngine(doc)
        print("   ✅ CreationEngine créé")
        
        print("\n2. Test stats...")
        stats = engine.get_stats()
        print("   Stats: " + str(stats))
        
        print("\n" + "="*60)
        print("✅ TEST TERMINÉ")
        print("="*60 + "\n")
        
    except Exception as e:
        print("\n❌ ERREUR: " + str(e))
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_creation_engine()