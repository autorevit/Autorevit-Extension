# -*- coding: utf-8 -*-
"""Algorithme de placement et dimensionnement des dalles

RÈGLES MÉTIER IMPLÉMENTÉES :

TYPE 1 : DALLE PLEINE
- Sous-sol : OBLIGATOIRE
- Étages : Choix utilisateur
- Épaisseur : lx/25 à lx/30 (min 15cm)
- Encadrement : 4 côtés obligatoires

TYPE 2 : DALLE NERVURÉE
- Étages : Par défaut
- Table : 5cm
- Nervures : lx/20 (min 20cm)
- Entraxe : 60cm

ENCADREMENT (4 CÔTÉS OBLIGATOIRES) :
- Cas 1 : 2 principales + 2 raidisseurs
- Cas 2 : 2 principales + 2 secondaires
- Cas 3 : 2 principales + 2 plates
- Cas 4 : 1 principale + 1 plate + 2 raidisseurs
→ RÈGLE : 2 poutres principales MINIMUM
"""

from __future__ import division, print_function

try:
    from Autodesk.Revit.DB import (
        XYZ, Line, Level, Floor, FloorType,
        FilteredElementCollector, BuiltInCategory,
        CurveArray, CurveLoop, Transform,
        BuiltInParameter
    )
    REVIT_AVAILABLE = True
except ImportError:
    REVIT_AVAILABLE = False
    XYZ = None
    Line = None
    Level = None
    Floor = None
    FloorType = None
    FilteredElementCollector = None
    BuiltInCategory = None
    CurveArray = None
    CurveLoop = None
    Transform = None
    BuiltInParameter = None

from services.revit_service import RevitService
from services.geometry_service import GeometryService
from services.logging_service import LoggingService
from utils.decorators import log_execution, transaction, handle_errors
from helpers.revit_helpers import (
    get_all_levels, mm_to_feet, feet_to_mm
)
from algorithms.beam_placement import BeamPlacementEngine, BeamType
from algorithms.geometry_utils import (
    detect_rectangular_bays,
    sort_points_clockwise,
    calculate_centroid,
    get_rectangle_from_points
)


# Classe pour simuler Enum (compatible IronPython 2.7)
class SlabType:
    """Types de dalles selon construction"""
    SOLID = "PLEINE"
    RIBBED = "NERVURÉE"
    HOLLOW_CORE = "PRÉDALLE"
    COMPOSITE = "COMPOSITE"


class SlabPlacementEngine:
    """
    Moteur de placement et dimensionnement des dalles.
    
    Implémente les règles métier pour :
    - Choix du type de dalle selon contexte (sous-sol vs étage)
    - Calcul d'épaisseur selon portée
    - Validation de l'encadrement par poutres
    - Création des dalles pleines et nervurées
    """
    
    # Ratios d'épaisseur pour dalles pleines
    SOLID_SPAN_RATIO_MIN = 1.0/30  # lx/30
    SOLID_SPAN_RATIO_MAX = 1.0/25  # lx/25
    
    # Épaisseur minimale (mm)
    MIN_SOLID_THICKNESS = 150  # 15cm
    MIN_RIBBED_THICKNESS = 200  # 20cm (nervure)
    
    # Table de compression (mm)
    TOPPING_THICKNESS = 50  # 5cm
    
    # Entraxe nervures (mm)
    RIB_SPACING = 600  # 60cm
    
    # Nombre minimal de poutres principales pour encadrement
    MIN_PRIMARY_BEAMS = 2
    
    def __init__(self, doc, api_client=None):
        """
        Initialise le moteur de placement des dalles.
        
        Args:
            doc: Document Revit actif
            api_client: Client API optionnel
        """
        self.doc = doc
        self.api = api_client
        self.revit_service = RevitService(doc)
        self.geometry_service = GeometryService(doc)
        self.logger = LoggingService(api_client)
        
        # Dépendances
        self.beam_engine = BeamPlacementEngine(doc, api_client)
        
        # Cache
        self._floor_types_cache = {}
        self._levels_cache = None
        
    # ---------------------------------------------------------------------
    # 1. DÉTERMINATION DU TYPE DE DALLE
    # ---------------------------------------------------------------------
    
    def is_basement(self, level):
        """
        Détermine si un niveau est un sous-sol.
        
        Args:
            level: Niveau à tester
            
        Returns:
            True si c'est un sous-sol
        """
        name_lower = level.Name.lower()
        return (
            "sous-sol" in name_lower or 
            "basement" in name_lower or
            "ss" in name_lower
        )
    
    def prompt_slab_type_choice(self, level):
        """
        Demande à l'utilisateur le type de dalle pour un niveau.
        
        Règle : 
        - Sous-sol : Dalle pleine OBLIGATOIRE
        - Étages : Choix entre pleine et nervurée
        
        Args:
            level: Niveau concerné
            
        Returns:
            Type de dalle choisi
        """
        # Sous-sol : dalle pleine obligatoire
        if self.is_basement(level):
            self.logger.log_info("Sous-sol détecté - Dalle pleine obligatoire")
            return SlabType.SOLID
        
        # TODO: Interface utilisateur réelle
        # Pour le développement, on utilise une config ou défaut
        from pyrevit import forms
        
        options = {
            'Dalle pleine (béton coulé en place)': SlabType.SOLID,
            'Dalle nervurée (avec table de compression)': SlabType.RIBBED,
            'Prédalle (préfabrication)': SlabType.HOLLOW_CORE
        }
        
        selected = forms.SelectFromList.show(
            list(options.keys()),
            title="Type de dalle pour %s" % level.Name,
            button_name='Valider',
            multiselect=False
        )
        
        if selected:
            return options[selected[0]]
        
        # Défaut : dalle nervurée pour étages
        return SlabType.RIBBED
    
    # ---------------------------------------------------------------------
    # 2. DÉTECTION DES PANNEAUX DE DALLE
    # ---------------------------------------------------------------------
    
    def find_slab_panels(self, level):
        """
        Détecte les panneaux de dalle à créer à partir du réseau de poutres.
        
        Args:
            level: Niveau concerné
            
        Returns:
            Liste des panneaux détectés
        """
        # Récupérer toutes les poutres du niveau
        beams = self.beam_engine.get_all_beams_for_level(level)
        
        if len(beams) < 4:  # Minimum pour fermer un panneau
            self.logger.log_warning("Pas assez de poutres au niveau %s" % level.Name)
            return []
        
        # Construire le réseau de poutres
        network = self.build_beam_network(beams)
        
        # Détecter les panneaux rectangulaires
        panels = self.detect_rectangular_panels(network)
        
        self.logger.log_info("%d panneaux détectés au niveau %s" % (len(panels), level.Name))
        return panels
    
    def build_beam_network(self, beams):
        """
        Construit un réseau de poutres pour analyse spatiale.
        
        Args:
            beams: Liste des poutres du niveau
            
        Returns:
            Réseau avec lignes et colonnes
        """
        network = {
            'horizontal': [],  # Poutres en X
            'vertical': [],    # Poutres en Y
            'points': set(),   # Points d'intersection
            'beams_by_id': {}
        }
        
        for beam in beams:
            orientation = beam.get('orientation')
            if orientation == 'X':
                network['horizontal'].append(beam)
            elif orientation == 'Y':
                network['vertical'].append(beam)
            
            # Points d'extrémité
            network['points'].add((beam['start'].X, beam['start'].Y))
            network['points'].add((beam['end'].X, beam['end'].Y))
            
            network['beams_by_id'][beam['id'].IntegerValue] = beam
        
        return network
    
    def detect_rectangular_panels(self, network):
        """
        Détecte les panneaux rectangulaires dans le réseau de poutres.
        
        Args:
            network: Réseau de poutres structuré
            
        Returns:
            Liste des panneaux (avec points de contour et poutres adjacentes)
        """
        panels = []
        
        # Trier les points
        points = sorted(list(network['points']))
        
        if len(points) < 4:
            return panels
        
        # Grouper par X et Y
        x_coords = sorted(set(p[0] for p in points))
        y_coords = sorted(set(p[1] for p in points))
        
        # Pour chaque rectangle potentiel
        for i in range(len(x_coords) - 1):
            for j in range(len(y_coords) - 1):
                x1 = x_coords[i]
                x2 = x_coords[i + 1]
                y1 = y_coords[j]
                y2 = y_coords[j + 1]
                
                # Vérifier que les 4 coins existent
                corners = [
                    (x1, y1),
                    (x2, y1),
                    (x2, y2),
                    (x1, y2)
                ]
                
                if all(c in network['points'] for c in corners):
                    # Trouver les poutres qui bordent ce panneau
                    border_beams = self._find_border_beams(network, x1, x2, y1, y2)
                    
                    # Valider la configuration d'encadrement
                    if self.validate_panel_configuration(border_beams):
                        if REVIT_AVAILABLE and XYZ:
                            corners_xyz = [XYZ(p[0], p[1], 0) for p in corners]
                        else:
                            corners_xyz = corners
                        
                        panels.append({
                            'min_x': x1,
                            'max_x': x2,
                            'min_y': y1,
                            'max_y': y2,
                            'corners': corners_xyz,
                            'border_beams': border_beams,
                            'width_mm': (x2 - x1) * 304.8,
                            'length_mm': (y2 - y1) * 304.8
                        })
        
        return panels
    
    def _find_border_beams(self, network, 
                          x1, x2, 
                          y1, y2):
        """
        Trouve les poutres qui bordent un panneau.
        
        Args:
            network: Réseau de poutres
            x1, x2, y1, y2: Coordonnées du rectangle
            
        Returns:
            Liste des poutres de bordure
        """
        border_beams = []
        
        # Poutres horizontales (côtés haut/bas)
        for beam in network['horizontal']:
            y = beam['start'].Y
            x_start = min(beam['start'].X, beam['end'].X)
            x_end = max(beam['start'].X, beam['end'].X)
            
            if abs(y - y1) < 0.001 or abs(y - y2) < 0.001:
                if x_start <= x1 and x_end >= x2:
                    border_beams.append(beam)
        
        # Poutres verticales (côtés gauche/droite)
        for beam in network['vertical']:
            x = beam['start'].X
            y_start = min(beam['start'].Y, beam['end'].Y)
            y_end = max(beam['start'].Y, beam['end'].Y)
            
            if abs(x - x1) < 0.001 or abs(x - x2) < 0.001:
                if y_start <= y1 and y_end >= y2:
                    border_beams.append(beam)
        
        return border_beams
    
    # ---------------------------------------------------------------------
    # 3. VALIDATION DE LA CONFIGURATION
    # ---------------------------------------------------------------------
    
    def validate_panel_configuration(self, border_beams):
        """
        Valide qu'un panneau est correctement encadré.
        
        Règle : 4 côtés obligatoires avec MINIMUM 2 poutres principales.
        
        Args:
            border_beams: Liste des poutres de bordure
            
        Returns:
            True si la configuration est valide
        """
        if len(border_beams) < 4:
            self.logger.log_debug("Panneau invalide : seulement %d côtés" % len(border_beams))
            return False
        
        # Compter les poutres principales
        primary_count = 0
        for beam in border_beams:
            beam_type = beam.get('type')
            if beam_type and beam_type == BeamType.PRIMARY:
                primary_count += 1
        
        if primary_count < self.MIN_PRIMARY_BEAMS:
            self.logger.log_debug(
                "Panneau invalide : %d poutres principales (minimum %d)" % 
                (primary_count, self.MIN_PRIMARY_BEAMS)
            )
            return False
        
        return True
    
    # ---------------------------------------------------------------------
    # 4. CALCUL DE L'ÉPAISSEUR
    # ---------------------------------------------------------------------
    
    def calculate_slab_thickness(self, 
                                panel, 
                                slab_type):
        """
        Calcule l'épaisseur de dalle appropriée.
        
        Règles :
        - Dalle pleine : lx/25 à lx/30 (min 15cm)
        - Dalle nervurée : nervure = lx/20 (min 20cm), table = 5cm
        
        Args:
            panel: Panneau de dalle
            slab_type: Type de dalle
            
        Returns:
            Épaisseur totale (mm)
        """
        # Portée du petit côté (lx)
        span_mm = min(panel['width_mm'], panel['length_mm'])
        span_m = span_mm / 1000.0
        
        if slab_type == SlabType.SOLID:
            # Dalle pleine : lx/25 à lx/30
            thickness = (span_m / 27.5) * 1000  # L/27.5 par défaut
            
            # Arrondir au multiple de 10 mm
            thickness = int(round(thickness / 10)) * 10
            
            # Épaisseur minimale
            thickness = max(self.MIN_SOLID_THICKNESS, thickness)
            
        elif slab_type == SlabType.RIBBED:
            # Dalle nervurée : hauteur nervure = lx/20
            rib_height = (span_m / 20.0) * 1000
            rib_height = int(round(rib_height / 10)) * 10
            rib_height = max(self.MIN_RIBBED_THICKNESS, rib_height)
            
            # Épaisseur totale = nervure + table
            thickness = rib_height + self.TOPPING_THICKNESS
            
        else:
            # Autres types : prédalle, etc.
            thickness = self.MIN_SOLID_THICKNESS
        
        return thickness
    
    # ---------------------------------------------------------------------
    # 5. CRÉATION DES DALLES
    # ---------------------------------------------------------------------
    
    def get_floor_type(self, 
                      thickness_mm, 
                      slab_type):
        """
        Récupère ou crée le type de dalle approprié.
        
        Args:
            thickness_mm: Épaisseur en mm
            slab_type: Type de dalle
            
        Returns:
            FloorType pour la dalle
        """
        cache_key = "%s_%d" % (slab_type, thickness_mm)
        
        if cache_key in self._floor_types_cache:
            return self._floor_types_cache[cache_key]
        
        if not REVIT_AVAILABLE or not FilteredElementCollector:
            return None
        
        # Chercher dans les types existants
        collector = FilteredElementCollector(self.doc)\
            .OfClass(FloorType)\
            .WhereElementIsElementType()
        
        thickness_feet = mm_to_feet(thickness_mm)
        
        for floor_type in collector:
            # Vérifier le nom et les paramètres
            if "%dmm" % thickness_mm in floor_type.Name:
                if slab_type == SlabType.SOLID and "pleine" in floor_type.Name.lower():
                    self._floor_types_cache[cache_key] = floor_type
                    return floor_type
                elif slab_type == SlabType.RIBBED and "nervurée" in floor_type.Name.lower():
                    self._floor_types_cache[cache_key] = floor_type
                    return floor_type
        
        # TODO: Créer le type si nécessaire
        # Utiliser le type par défaut
        default_type = collector.FirstElement()
        self._floor_types_cache[cache_key] = default_type
        return default_type
    
    @log_execution
    @transaction("Création des dalles")
    @handle_errors("Erreur lors de la création des dalles")
    def create_slabs_for_level(self, level):
        """
        Crée toutes les dalles pour un niveau donné.
        
        Args:
            level: Niveau concerné
            
        Returns:
            Liste des dalles créées
        """
        # 1. Déterminer le type de dalle
        slab_type = self.prompt_slab_type_choice(level)
        
        # 2. Détecter les panneaux
        panels = self.find_slab_panels(level)
        
        if not panels:
            self.logger.log_warning("Aucun panneau valide au niveau %s" % level.Name)
            return []
        
        # 3. Créer les dalles
        created_slabs = []
        
        for panel in panels:
            try:
                # Calculer épaisseur
                thickness = self.calculate_slab_thickness(panel, slab_type)
                
                # Récupérer le type
                floor_type = self.get_floor_type(thickness, slab_type)
                if not floor_type:
                    continue
                
                if not REVIT_AVAILABLE or not CurveLoop or not Line or not Floor:
                    continue
                
                # Créer le contour
                curve_loop = CurveLoop()
                
                # Trier les points dans le sens horaire
                points = sort_points_clockwise(panel['corners'])
                
                for i in range(len(points)):
                    start = points[i]
                    end = points[(i + 1) % len(points)]
                    line = Line.CreateBound(start, end)
                    curve_loop.Append(line)
                
                # Créer la dalle
                floor = Floor.Create(self.doc, [curve_loop], floor_type.Id, level.Id)
                
                # Définir l'épaisseur
                floor.get_Parameter(BuiltInParameter.FLOOR_ATTR_DEFAULT_THICKNESS_PARAM)\
                    .Set(mm_to_feet(thickness))
                
                # Ajouter commentaires
                floor.LookupParameter("Comments").Set(
                    "AutoRevit - %s - e=%dmm - %dx%dm" % (
                        slab_type,
                        thickness,
                        int(panel['width_mm']/1000),
                        int(panel['length_mm']/1000)
                    )
                )
                
                created_slabs.append({
                    'element': floor,
                    'id': floor.Id,
                    'type': slab_type,
                    'thickness': thickness,
                    'dimensions': (panel['width_mm'], panel['length_mm'])
                })
                
            except Exception as e:
                self.logger.log_error(e, {
                    'level': level.Name,
                    'panel': panel
                })
        
        self.logger.log_info(
            "%d dalles créées au niveau %s (type: %s)" % 
            (len(created_slabs), level.Name, slab_type)
        )
        
        # Si dalle nervurée, créer les nervures
        if slab_type == SlabType.RIBBED and created_slabs:
            self.create_ribs_for_slabs(created_slabs, panels, level)
        
        return created_slabs
    
    def create_ribs_for_slabs(self, 
                            slabs, 
                            panels, 
                            level):
        """
        Crée les nervures pour les dalles nervurées.
        
        Args:
            slabs: Dalles créées
            panels: Panneaux correspondants
            level: Niveau concerné
            
        Returns:
            Liste des nervures créées
        """
        ribs_created = []
        
        # TODO: Implémenter la création des nervures
        # Ceci nécessite des familles de poutres spécifiques pour nervures
        
        return ribs_created
    
    @log_execution
    @transaction("Création de toutes les dalles")
    @handle_errors("Erreur lors de la création de toutes les dalles")
    def create_all_slabs(self):
        """
        Crée les dalles pour tous les niveaux du projet.
        
        Returns:
            Dictionnaire des résultats par niveau
        """
        levels = get_all_levels(self.doc)
        
        # Trier par altitude
        levels = sorted(levels, key=lambda l: l.Elevation)
        
        results = {}
        total_slabs = 0
        
        for level in levels:
            # Ne pas créer de dalles au niveau toit?
            if "toit" in level.Name.lower():
                # Demander confirmation pour le toit
                from pyrevit import forms
                if not forms.alert(
                    "Créer une dalle au niveau %s ?" % level.Name,
                    title="AutoRevit - Dalle toit",
                    yes=True, no=True
                ):
                    continue
            
            slabs = self.create_slabs_for_level(level)
            
            results[level.Name] = {
                'count': len(slabs),
                'slabs': slabs,
                'type': slabs[0]['type'] if slabs else None
            }
            total_slabs += len(slabs)
        
        self.logger.log_info("Création terminée : %d dalles au total" % total_slabs)
        
        return {
            'success': True,
            'total_slabs': total_slabs,
            'by_level': results
        }


# Fonction d'entrée pour les boutons pyRevit
def main():
    """
    Point d'entrée principal pour l'exécution depuis l'interface Revit.
    """
    from pyrevit import revit, forms
    
    doc = revit.doc
    
    # Vérifier qu'il y a des poutres
    collector = FilteredElementCollector(doc)\
        .OfCategory(BuiltInCategory.OST_StructuralFraming)\
        .WhereElementIsNotElementType()
    
    if collector.GetElementCount() == 0:
        forms.alert(
            "❌ Aucune poutre trouvée. Créez d'abord les poutres.",
            title="AutoRevit - Création dalles"
        )
        return
    
    # Créer le moteur
    engine = SlabPlacementEngine(doc)
    
    # Demander confirmation
    if forms.alert(
        "Créer les dalles pour tous les niveaux ?",
        title="AutoRevit - Création dalles",
        ok=False,
        yes=True,
        no=True
    ):
        result = engine.create_all_slabs()
        
        if result['success']:
            forms.alert(
                "✅ %d dalles créées avec succès !" % result['total_slabs'],
                title="Succès"
            )
        else:
            forms.alert(
                "❌ Erreur : %s" % result.get('message', 'Inconnue'),
                title="Erreur"
            )


if __name__ == '__main__':
    main()