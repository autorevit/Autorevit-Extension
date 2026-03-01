# -*- coding: utf-8 -*-
"""Algorithme de création des éléments structurels secondaires

ÉLÉMENTS SECONDAIRES IMPLÉMENTÉS :

1. ACROTÈRES
   - Détection périmètre toiture
   - Hauteur minimale : 500mm
   - Épaisseur : 150-200mm
   - Chaînage horizontal en tête

2. LINTEAUX
   - Au-dessus portes et fenêtres
   - Appui minimal : 200mm de chaque côté
   - Hauteur : 200mm minimum
   - Armatures minimales

3. POUTRES VOILES (raidisseurs verticaux)
   - Renforts ponctuels dans grands voiles
   - Espacement max : 4m
   - Section carrée (200x200mm min)

4. CHAINAGES HORIZONTAUX
   - Ceinturage des bâtiments
   - Niveau plancher haut
   - Section minimale : 200x200mm
"""

# Compatibilité IronPython 2.7 / Python 3
try:
    from typing import List, Dict, Tuple, Optional
except Exception as _revit_import_err:
    pass

try:
    from enum import Enum as _BaseEnum

    class SecondaryElementType(_BaseEnum):
        """Types d'éléments secondaires"""
        ACROTERE  = "ACROTERE"
        LINTEL    = "LINTEAU"
        WALL_BEAM = "POUTRE_VOILE"
        TIE_BEAM  = "CHAINAGE"
        PARAPET   = "GARDE_CORPS"

except Exception as _revit_import_err:
    class SecondaryElementType(object):
        ACROTERE  = "ACROTERE"
        LINTEL    = "LINTEAU"
        WALL_BEAM = "POUTRE_VOILE"
        TIE_BEAM  = "CHAINAGE"
        PARAPET   = "GARDE_CORPS"

from Autodesk.Revit.DB import (
    XYZ, Line, Wall, Level, FamilyInstance,
    FilteredElementCollector, BuiltInCategory,
    BuiltInParameter,
    Curve, LocationCurve, LocationPoint,
    ElementId, Transaction, FamilySymbol
)

from services.revit_service import RevitService
from services.geometry_service import GeometryService
from services.logging_service import LoggingService
from utils.decorators import log_execution, transaction, handle_errors
from helpers.revit_helpers import (
    get_all_levels, mm_to_feet, feet_to_mm,
    get_all_walls, get_all_roofs,
    get_all_doors, get_all_windows
)
from algorithms.geometry_utils import (
    calculate_distance,
    is_point_on_line,
    offset_point,
    sort_points_clockwise,
    get_rectangle_from_points
)
from algorithms.wall_placement import WallPlacementEngine


class SecondaryElementsEngine(object):
    """
    Moteur de création des éléments structurels secondaires.

    Complète la structure principale avec tous les éléments
    secondaires nécessaires à la stabilité et à l'étanchéité.
    """

    # Dimensions standards (mm)
    ACROTERE_MIN_HEIGHT = 500
    ACROTERE_THICKNESS  = 200

    LINTEL_MIN_HEIGHT = 200
    LINTEL_BEARING    = 200

    WALL_BEAM_MIN_SIZE = 200
    WALL_BEAM_SPACING  = 4000

    TIE_BEAM_SIZE = 200

    def __init__(self, doc, api_client=None):
        """
        Initialise le moteur d'éléments secondaires.

        Args:
            doc:        Document Revit actif
            api_client: Client API optionnel
        """
        self.doc              = doc
        self.api              = api_client
        self.revit_service    = RevitService(doc)
        self.geometry_service = GeometryService(doc)
        self.logger           = LoggingService(api_client)

        self.wall_engine = WallPlacementEngine(doc, api_client)

        self._beam_types_cache = {}
        self._wall_types_cache = {}

    # -------------------------------------------------------------------------
    # 1. ACROTÈRES
    # -------------------------------------------------------------------------

    def detect_roof_perimeter(self, level):
        """
        Détecte le périmètre de la toiture.

        Args:
            level: Niveau de toiture

        Returns:
            Liste des courbes du périmètre
        """
        perimeters = []
        walls      = get_all_walls(self.doc)

        roof_walls = []
        for wall in walls:
            if wall.LevelId == level.Id:
                location = wall.Location
                if isinstance(location, LocationCurve):
                    roof_walls.append(location.Curve)

        if roof_walls:
            # TODO: Algorithme de chaînage des courbes
            perimeters = roof_walls

        return perimeters

    @log_execution
    @transaction("Création des acrotères")
    @handle_errors("Erreur lors de la création des acrotères")
    def create_acrotere(self, roof_level):
        """
        Crée des acrotères sur le périmètre de la toiture.

        Args:
            roof_level: Niveau de toiture

        Returns:
            Liste des acrotères créés
        """
        created = []

        perimeter_curves = self.detect_roof_perimeter(roof_level)

        if not perimeter_curves:
            self.logger.log_warning("Aucun périmètre de toiture détecté")
            return created

        wall_type = self.wall_engine.get_wall_type(
            self.ACROTERE_THICKNESS,
            is_structural=False
        )

        if not wall_type:
            return created

        for curve in perimeter_curves:
            try:
                acrotere = Wall.Create(
                    self.doc,
                    curve,
                    wall_type.Id,
                    roof_level.Id,
                    mm_to_feet(self.ACROTERE_MIN_HEIGHT),
                    0,
                    False,
                    False
                )

                c_param = acrotere.LookupParameter("Comments")
                if c_param:
                    c_param.Set(
                        "AutoRevit - Acrotère - H={0}mm".format(
                            self.ACROTERE_MIN_HEIGHT
                        )
                    )

                created.append(acrotere)

            except Exception as e:
                self.logger.log_error(e, {'curve': str(curve)})

        self.logger.log_info("{0} acrotères créés".format(len(created)))
        return created

    # -------------------------------------------------------------------------
    # 2. LINTEAUX
    # -------------------------------------------------------------------------

    @log_execution
    @transaction("Création des linteaux")
    @handle_errors("Erreur lors de la création des linteaux")
    def create_lintels(self, level):
        """
        Crée des linteaux au-dessus de toutes les ouvertures.

        Args:
            level: Niveau concerné

        Returns:
            Liste des linteaux créés
        """
        created = []

        doors   = get_all_doors(self.doc)
        windows = get_all_windows(self.doc)

        openings = []
        for door in doors:
            if door.LevelId == level.Id:
                openings.append(('door', door))

        for window in windows:
            if window.LevelId == level.Id:
                openings.append(('window', window))

        beam_type = self._get_lintel_beam_type()

        if not beam_type:
            return created

        for opening_type, opening in openings:
            try:
                location = opening.Location
                if not isinstance(location, LocationPoint):
                    continue

                point = location.Point

                width_param = opening.get_Parameter(BuiltInParameter.DOOR_WIDTH)
                if not width_param:
                    width_param = opening.get_Parameter(BuiltInParameter.WINDOW_WIDTH)

                if not width_param:
                    continue

                width_mm = feet_to_mm(width_param.AsDouble())

                height_param = opening.get_Parameter(BuiltInParameter.DOOR_HEIGHT)
                if not height_param:
                    height_param = opening.get_Parameter(BuiltInParameter.WINDOW_HEIGHT)

                height_mm = feet_to_mm(height_param.AsDouble()) if height_param else 2100

                sill_param = opening.get_Parameter(BuiltInParameter.INSTANCE_SILL_HEIGHT_PARAM)
                sill_mm    = feet_to_mm(sill_param.AsDouble()) if sill_param else 0

                lintel_bottom = level.Elevation + mm_to_feet(sill_mm + height_mm)
                lintel_top    = lintel_bottom + mm_to_feet(self.LINTEL_MIN_HEIGHT)

                lintel_width = width_mm + 2 * self.LINTEL_BEARING

                start = XYZ(
                    point.X - mm_to_feet(lintel_width / 2.0),
                    point.Y,
                    lintel_bottom
                )
                end = XYZ(
                    point.X + mm_to_feet(lintel_width / 2.0),
                    point.Y,
                    lintel_bottom
                )

                line = Line.CreateBound(start, end)

                lintel = self.doc.Create.NewFamilyInstance(
                    line,
                    beam_type,
                    level
.Beam
                )

                c_param = lintel.LookupParameter("Comments")
                if c_param:
                    c_param.Set(
                        "AutoRevit - Linteau - L={0}mm".format(int(lintel_width))
                    )

                created.append(lintel)

            except Exception as e:
                self.logger.log_error(e, {
                    'opening': opening.Id.IntegerValue
                })

        self.logger.log_info(
            "{0} linteaux créés au niveau {1}".format(len(created), level.Name)
        )
        return created

    def _get_lintel_beam_type(self):
        """Récupère le type de poutre pour linteaux."""
        collector = (FilteredElementCollector(self.doc)
                     .OfCategory(BuiltInCategory.OST_StructuralFraming)
                     .OfClass(FamilySymbol))

        for symbol in collector:
            name_lower = symbol.Name.lower()
            if "linteau" in name_lower or "lintel" in name_lower:
                return symbol

        return collector.FirstElement()

    # -------------------------------------------------------------------------
    # 3. POUTRES VOILES (RAIDISSEURS VERTICAUX)
    # -------------------------------------------------------------------------

    @log_execution
    @transaction("Création des poutres voiles")
    @handle_errors("Erreur lors de la création des poutres voiles")
    def create_wall_beams(self, level, next_level):
        """
        Crée des raidisseurs verticaux dans les grands voiles.

        Args:
            level:      Niveau de base
            next_level: Niveau supérieur

        Returns:
            Liste des poutres voiles créées
        """
        created = []

        walls = get_all_walls(self.doc)

        structural_walls = []
        for wall in walls:
            if wall.LevelId == level.Id:
                structural_param = wall.get_Parameter(
                    BuiltInParameter.WALL_STRUCTURAL_USAGE_PARAM
                )
                if structural_param and structural_param.AsInteger() != 0:
                    structural_walls.append(wall)

        beam_type = self._get_wall_beam_type()

        if not beam_type:
            return created

        for wall in structural_walls:
            try:
                location = wall.Location
                if not isinstance(location, LocationCurve):
                    continue

                wall_line   = location.Curve
                wall_length_mm = feet_to_mm(wall_line.Length)

                num_beams = max(0, int(wall_length_mm / self.WALL_BEAM_SPACING) - 1)

                if num_beams <= 0:
                    continue

                for i in range(1, num_beams + 1):
                    param = i / float(num_beams + 1)
                    point = wall_line.Evaluate(param, True)

                    beam = self.doc.Create.NewFamilyInstance(
                        point,
                        beam_type,
                        level
.Beam
                    )

                    top_level_param = beam.get_Parameter(
                        BuiltInParameter.FAMILY_TOP_LEVEL_PARAM
                    )
                    if top_level_param:
                        top_level_param.Set(next_level.Id)

                    w_param = beam.get_Parameter(BuiltInParameter.FAMILY_WIDTH_PARAM)
                    h_param = beam.get_Parameter(BuiltInParameter.FAMILY_HEIGHT_PARAM)

                    if w_param:
                        w_param.Set(mm_to_feet(self.WALL_BEAM_MIN_SIZE))
                    if h_param:
                        h_param.Set(mm_to_feet(self.WALL_BEAM_MIN_SIZE))

                    c_param = beam.LookupParameter("Comments")
                    if c_param:
                        c_param.Set(
                            "AutoRevit - Raidisseur voile - {0}x{0}mm".format(
                                self.WALL_BEAM_MIN_SIZE
                            )
                        )

                    created.append(beam)

            except Exception as e:
                self.logger.log_error(e, {'wall': wall.Id.IntegerValue})

        self.logger.log_info("{0} raidisseurs créés".format(len(created)))
        return created

    def _get_wall_beam_type(self):
        """Récupère le type de poutre pour raidisseurs verticaux."""
        collector = (FilteredElementCollector(self.doc)
                     .OfCategory(BuiltInCategory.OST_StructuralFraming)
                     .OfClass(FamilySymbol))

        for symbol in collector:
            if "poteau" in symbol.Name.lower():
                return symbol

        return collector.FirstElement()

    # -------------------------------------------------------------------------
    # 4. CHAINAGES HORIZONTAUX
    # -------------------------------------------------------------------------

    @log_execution
    @transaction("Création des chaînages")
    @handle_errors("Erreur lors de la création des chaînages")
    def create_tie_beams(self, level):
        """
        Crée des chaînages horizontaux au niveau des planchers.

        Args:
            level: Niveau de plancher

        Returns:
            Liste des chaînages créés
        """
        created   = []
        perimeter = self.detect_building_perimeter(level)

        if not perimeter:
            return created

        beam_type = self._get_tie_beam_type()

        if not beam_type:
            return created

        for i in range(len(perimeter)):
            start = perimeter[i]
            end   = perimeter[(i + 1) % len(perimeter)]

            try:
                line = Line.CreateBound(
                    XYZ(start.X, start.Y, level.Elevation),
                    XYZ(end.X,   end.Y,   level.Elevation)
                )

                tie_beam = self.doc.Create.NewFamilyInstance(
                    line,
                    beam_type,
                    level
.Beam
                )

                w_param = tie_beam.get_Parameter(BuiltInParameter.FAMILY_WIDTH_PARAM)
                h_param = tie_beam.get_Parameter(BuiltInParameter.FAMILY_HEIGHT_PARAM)

                if w_param:
                    w_param.Set(mm_to_feet(self.TIE_BEAM_SIZE))
                if h_param:
                    h_param.Set(mm_to_feet(self.TIE_BEAM_SIZE))

                c_param = tie_beam.LookupParameter("Comments")
                if c_param:
                    c_param.Set(
                        "AutoRevit - Chaînage horizontal - {0}x{0}mm".format(
                            self.TIE_BEAM_SIZE
                        )
                    )

                created.append(tie_beam)

            except Exception as e:
                self.logger.log_error(e, {'level': level.Name})

        return created

    def detect_building_perimeter(self, level):
        """
        Détecte le périmètre du bâtiment à un niveau donné.

        Args:
            level: Niveau concerné

        Returns:
            Liste ordonnée des points du périmètre
        """
        walls  = get_all_walls(self.doc)
        points = []

        for wall in walls:
            if wall.LevelId == level.Id:
                location = wall.Location
                if isinstance(location, LocationCurve):
                    curve = location.Curve
                    points.append(curve.GetEndPoint(0))
                    points.append(curve.GetEndPoint(1))

        if len(points) < 3:
            return []

        return sort_points_clockwise(points)

    def _get_tie_beam_type(self):
        """Récupère le type de poutre pour chaînages."""
        collector = (FilteredElementCollector(self.doc)
                     .OfCategory(BuiltInCategory.OST_StructuralFraming)
                     .OfClass(FamilySymbol))

        return collector.FirstElement()

    # -------------------------------------------------------------------------
    # 5. EXÉCUTION GLOBALE
    # -------------------------------------------------------------------------

    @log_execution
    @transaction("Création des éléments secondaires")
    @handle_errors("Erreur lors de la création des éléments secondaires")
    def create_all_secondary_elements(self):
        """
        Crée tous les éléments secondaires du projet.

        Returns:
            Dictionnaire des résultats
        """
        levels = get_all_levels(self.doc)
        levels = sorted(levels, key=lambda l: l.Elevation)

        results = {
            'acroteres': [],
            'lintels':   [],
            'wall_beams': [],
            'tie_beams':  [],
        }

        # Acrotères (dernier niveau = toit)
        roof_level = levels[-1] if levels else None
        if roof_level:
            acroteres = self.create_acrotere(roof_level)
            results['acroteres'] = [a.Id.IntegerValue for a in acroteres]

        # Linteaux (tous niveaux)
        for level in levels:
            lintels = self.create_lintels(level)
            results['lintels'].extend([l.Id.IntegerValue for l in lintels])

        # Poutres voiles (entre niveaux)
        for i in range(len(levels) - 1):
            wall_beams = self.create_wall_beams(levels[i], levels[i + 1])
            results['wall_beams'].extend([wb.Id.IntegerValue for wb in wall_beams])

        # Chaînages (tous niveaux)
        for level in levels:
            tie_beams = self.create_tie_beams(level)
            results['tie_beams'].extend([tb.Id.IntegerValue for tb in tie_beams])

        total = (
            len(results['acroteres']) +
            len(results['lintels'])   +
            len(results['wall_beams']) +
            len(results['tie_beams'])
        )

        self.logger.log_info(
            "Création terminée : {0} éléments secondaires".format(total)
        )

        return {
            'success': True,
            'total':   total,
            'details': results,
        }


# -----------------------------------------------------------------------------
# Fonction d'entrée pour les boutons pyRevit
# -----------------------------------------------------------------------------

def main():
    """Point d'entrée principal pour l'exécution depuis l'interface Revit."""
    from pyrevit import revit, forms

    doc = revit.doc

    options = [
        "Créer tous les éléments secondaires",
        "Acrotères uniquement",
        "Linteaux uniquement",
        "Raidisseurs de voiles",
        "Chaînages horizontaux",
    ]

    selected = forms.SelectFromList.show(
        options,
        title="AutoRevit - Éléments secondaires",
        button_name='Continuer',
        multiselect=False
    )

    if not selected:
        return

    engine = SecondaryElementsEngine(doc)
    mode   = selected[0]

    if mode == options[0]:
        if forms.alert(
            "Créer tous les éléments secondaires ?",
            title="AutoRevit",
            yes=True, no=True
        ):
            result = engine.create_all_secondary_elements()

            if result['success']:
                forms.alert(
                    "{0} éléments secondaires créés !\n\n"
                    "Acrotères: {1}\n"
                    "Linteaux: {2}\n"
                    "Raidisseurs: {3}\n"
                    "Chaînages: {4}".format(
                        result['total'],
                        len(result['details']['acroteres']),
                        len(result['details']['lintels']),
                        len(result['details']['wall_beams']),
                        len(result['details']['tie_beams'])
                    ),
                    title="Succès"
                )

    elif mode == options[1]:
        levels     = get_all_levels(doc)
        roof_level = levels[-1] if levels else None

        if roof_level:
            result = engine.create_acrotere(roof_level)
            forms.alert(
                "{0} acrotères créés".format(len(result)),
                title="Succès"
            )

    elif mode == options[2]:
        total  = 0
        levels = get_all_levels(doc)

        for level in levels:
            result = engine.create_lintels(level)
            total += len(result)

        forms.alert("{0} linteaux créés".format(total), title="Succès")

    elif mode == options[3]:
        levels = get_all_levels(doc)
        levels = sorted(levels, key=lambda l: l.Elevation)
        total  = 0

        for i in range(len(levels) - 1):
            result = engine.create_wall_beams(levels[i], levels[i + 1])
            total += len(result)

        forms.alert("{0} raidisseurs créés".format(total), title="Succès")

    elif mode == options[4]:
        total  = 0
        levels = get_all_levels(doc)

        for level in levels:
            result = engine.create_tie_beams(level)
            total += len(result)

        forms.alert("{0} chaînages créés".format(total), title="Succès")


if __name__ == '__main__':
    main()