# -*- coding: utf-8 -*-
"""Algorithme de creation et dimensionnement des escaliers - Revit 2024

PATTERN CORRECT REVIT 2024 :
    with StairsEditScope(doc, "nom") as scope:
        stair_id = scope.Start(base_level.Id, top_level.Id)
        with Transaction(doc, "run") as t:
            t.Start()
            stair_elem.ChangeTypeId(stair_type.Id)
            StairsRun.CreateStraightRun(doc, stair_id, line, StairsRunJustification.Center)
            run.get_Parameter(BuiltInParameter.STAIRS_RUN_ACTUAL_RUN_WIDTH).Set(width_ft)
            t.Commit()
        scope.Commit(IgnoreAllWarnings())
    # Commentaire dans Transaction SEPAREE apres fermeture du scope
"""

import math

try:
    from typing import List, Dict, Tuple, Optional
except Exception:
    pass

try:
    from enum import Enum as _BaseEnum
    class StairType(_BaseEnum):
        STRAIGHT = "DROIT"
        L_SHAPED = "QUART_TOURNANT"
        U_SHAPED = "DOUBLE_QUART"
        WINDING  = "BALANCE"
        SPIRAL   = "HELICOIDAL"
except Exception:
    class StairType(object):
        STRAIGHT = "DROIT"
        L_SHAPED = "QUART_TOURNANT"
        U_SHAPED = "DOUBLE_QUART"
        WINDING  = "BALANCE"
        SPIRAL   = "HELICOIDAL"

from Autodesk.Revit.DB import (
    XYZ, Line, Level, FilteredElementCollector,
    BuiltInParameter, CurveLoop, ElementId, Transaction,
    StairsEditScope, IFailuresPreprocessor, FailureProcessingResult
)
from Autodesk.Revit.DB.Architecture import (
    Stairs, StairsType, StairsRun, StairsLanding, StairsRunJustification
)

from services.revit_service import RevitService
from services.geometry_service import GeometryService
from services.logging_service import LoggingService
from helpers.revit_helpers import get_all_levels, mm_to_feet, feet_to_mm


# ---------------------------------------------------------------------------
# IFailuresPreprocessor minimal - accepte tous les avertissements
# ---------------------------------------------------------------------------
class IgnoreAllWarnings(IFailuresPreprocessor):
    def PreprocessFailures(self, failuresAccessor):
        return FailureProcessingResult.Continue


class StairPlacementEngine(object):
    """
    Moteur de creation et dimensionnement des escaliers.

    PATTERN REVIT 2024 :
    - StairsEditScope.Start(baseLevelId, topLevelId) pour creer
    - StairsEditScope.Start(stairsId) pour editer
    - Transaction interne pour toutes les modifications
    - scope.Commit(IgnoreAllWarnings()) pour finaliser
    - Commentaires dans Transaction SEPAREE apres le scope
    """

    BLONDEL_MIN   = 600
    BLONDEL_MAX   = 640
    BLONDEL_IDEAL = 630

    RISER_MIN   = 160
    RISER_MAX   = 180
    RISER_IDEAL = 170

    TREAD_MIN   = 280
    TREAD_MAX   = 320
    TREAD_IDEAL = 290

    MIN_HEADROOM      = 1900
    MIN_WIDTH_PRIVATE = 800
    MIN_WIDTH_PUBLIC  = 1200

    def __init__(self, doc, api_client=None):
        self.doc              = doc
        self.api              = api_client
        self.revit_service    = RevitService(doc)
        self.geometry_service = GeometryService(doc)
        self.logger           = LoggingService(api_client)
        self._stair_types_cache   = {}
        self._railing_types_cache = {}

    # -----------------------------------------------------------------------
    # 1. CALCUL DES MARCHES (LOI DE BLONDEL)
    # -----------------------------------------------------------------------

    def calculate_steps(self, height_diff_mm,
                        riser_override_mm=None,
                        tread_override_mm=None):
        if riser_override_mm and riser_override_mm > 0:
            riser     = float(riser_override_mm)
            num_steps = int(round(height_diff_mm / riser))
            if num_steps < 1:
                num_steps = 1
            riser = height_diff_mm / float(num_steps)
            tread = tread_override_mm if tread_override_mm else (
                self.BLONDEL_IDEAL - 2 * riser)
            tread = max(self.TREAD_MIN, min(self.TREAD_MAX, tread))
            return {
                'riser_count':     num_steps,
                'riser_height_mm': round(riser, 1),
                'tread_depth_mm':  round(tread, 1),
                'blondel_value':   round(2 * riser + tread, 1),
                'total_height_mm': height_diff_mm,
                'total_run_mm':    round(tread * num_steps, 1),
            }

        min_steps         = int(math.ceil(height_diff_mm / self.RISER_MAX))
        max_steps         = int(math.floor(height_diff_mm / self.RISER_MIN))
        best_solution     = None
        best_blondel_diff = float('inf')

        for num_steps in range(min_steps, max_steps + 1):
            riser = height_diff_mm / float(num_steps)
            tread = self.BLONDEL_IDEAL - 2 * riser
            if self.TREAD_MIN <= tread <= self.TREAD_MAX:
                blondel      = 2 * riser + tread
                blondel_diff = abs(blondel - self.BLONDEL_IDEAL)
                if blondel_diff < best_blondel_diff:
                    best_blondel_diff = blondel_diff
                    best_solution = {
                        'riser_count':     num_steps,
                        'riser_height_mm': round(riser, 1),
                        'tread_depth_mm':  round(tread, 1),
                        'blondel_value':   round(blondel, 1),
                        'total_height_mm': height_diff_mm,
                        'total_run_mm':    round(tread * num_steps, 1),
                    }

        if not best_solution:
            riser     = float(self.RISER_IDEAL)
            num_steps = int(round(height_diff_mm / riser))
            if num_steps < 1:
                num_steps = 1
            riser = height_diff_mm / float(num_steps)
            tread = self.BLONDEL_IDEAL - 2 * riser
            tread = max(self.TREAD_MIN, min(self.TREAD_MAX, tread))
            best_solution = {
                'riser_count':     num_steps,
                'riser_height_mm': round(riser, 1),
                'tread_depth_mm':  round(tread, 1),
                'blondel_value':   round(2 * riser + tread, 1),
                'total_height_mm': height_diff_mm,
                'total_run_mm':    round(tread * num_steps, 1),
            }

        return best_solution

    # -----------------------------------------------------------------------
    # 2. SELECTION DU TYPE D ESCALIER
    # -----------------------------------------------------------------------

    def recommend_stair_type(self, available_space_mm, height_diff_mm):
        width, length = available_space_mm
        steps        = self.calculate_steps(height_diff_mm)
        required_run = steps['total_run_mm']
        if length >= required_run and width >= self.MIN_WIDTH_PRIVATE:
            return StairType.STRAIGHT
        if length >= required_run * 0.6 and width >= required_run * 0.4:
            return StairType.L_SHAPED
        if length >= required_run * 0.4 and width >= required_run * 0.4:
            return StairType.U_SHAPED
        return StairType.SPIRAL

    # -----------------------------------------------------------------------
    # UTILITAIRE : lire le nom d'un element de facon robuste
    # -----------------------------------------------------------------------

    def _get_name(self, elem):
        try:
            p = elem.get_Parameter(BuiltInParameter.ALL_MODEL_TYPE_NAME)
            if p and p.HasValue:
                return p.AsString()
        except: pass
        try:
            return elem.Name
        except: pass
        return "(sans nom)"

    # -----------------------------------------------------------------------
    # UTILITAIRE : ajouter un commentaire apres creation
    # -----------------------------------------------------------------------

    def _set_comment(self, stair_elem_id, comment_text):
        try:
            with Transaction(self.doc, "AutoRevit - Commentaire") as t_cmt:
                t_cmt.Start()
                stair_elem = self.doc.GetElement(stair_elem_id)
                if stair_elem:
                    cmt = stair_elem.LookupParameter("Comments")
                    if cmt and not cmt.IsReadOnly:
                        cmt.Set(comment_text)
                t_cmt.Commit()
        except Exception as e:
            try:
                self.logger.log_error(e, {'action': 'set_comment'})
            except:
                pass

    # -----------------------------------------------------------------------
    # 3. CREATION ESCALIER DROIT
    # -----------------------------------------------------------------------

    def create_straight_stair(self, start_point, end_point,
                               base_level, top_level, width_mm=900,
                               riser_height_mm=None, tread_depth_mm=None):
        """
        Cree un escalier droit entre deux niveaux.
        Pattern Revit 2024 : scope.Start(base, top) + Transaction interne.
        """
        try:
            height_mm = feet_to_mm(top_level.Elevation - base_level.Elevation)
            steps     = self.calculate_steps(height_mm, riser_height_mm, tread_depth_mm)

            stair_type = self._get_stair_type()
            if not stair_type:
                self.logger.log_error(
                    Exception("Aucun type d escalier disponible"), {})
                return None

            tread_ft      = mm_to_feet(steps['tread_depth_mm'])
            width_ft      = mm_to_feet(width_mm)
            run_length_ft = tread_ft * steps['riser_count']

            dx   = end_point.X - start_point.X
            dy   = end_point.Y - start_point.Y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < 0.01:
                adjusted_end = XYZ(
                    start_point.X + run_length_ft,
                    start_point.Y,
                    start_point.Z)
            else:
                adjusted_end = XYZ(
                    start_point.X + (dx / dist) * run_length_ft,
                    start_point.Y + (dy / dist) * run_length_ft,
                    start_point.Z)

            new_stair_id  = None
            preprocessor  = IgnoreAllWarnings()

            with StairsEditScope(self.doc, "AutoRevit Escalier droit") as scope:
                try:
                    stair_elem_id = scope.Start(base_level.Id, top_level.Id)

                    with Transaction(self.doc, "AutoRevit - Run droit") as t:
                        t.Start()

                        # Appliquer le type
                        stair_elem = self.doc.GetElement(stair_elem_id)
                        stair_elem.ChangeTypeId(stair_type.Id)

                        # Creer la volee
                        run = StairsRun.CreateStraightRun(
                            self.doc,
                            stair_elem_id,
                            Line.CreateBound(start_point, adjusted_end),
                            StairsRunJustification.Center)

                        # Largeur
                        w = run.get_Parameter(
                            BuiltInParameter.STAIRS_RUN_ACTUAL_RUN_WIDTH)
                        if w and not w.IsReadOnly:
                            w.Set(width_ft)

                        t.Commit()

                    scope.Commit(preprocessor)
                    new_stair_id = stair_elem_id

                except Exception as e_inner:
                    try:
                        scope.Cancel()
                    except:
                        pass
                    self.logger.log_error(e_inner, {
                        'start': str(start_point),
                        'end':   str(adjusted_end),
                        'base':  base_level.Name,
                        'top':   top_level.Name,
                    })
                    return None

            # Commentaire dans Transaction SEPAREE
            if new_stair_id:
                self._set_comment(
                    new_stair_id,
                    "AutoRevit DROIT {0}m h={1:.0f}mm g={2:.0f}mm".format(
                        steps['riser_count'],
                        steps['riser_height_mm'],
                        steps['tread_depth_mm']))

            return new_stair_id

        except Exception as e:
            self.logger.log_error(e, {
                'start': str(start_point),
                'end':   str(end_point),
                'base':  base_level.Name,
                'top':   top_level.Name,
            })
            return None

    # -----------------------------------------------------------------------
    # 4. CREATION ESCALIER QUART TOURNANT
    # -----------------------------------------------------------------------

    def create_l_shaped_stair(self, location, base_level, top_level,
                               width_mm=900, left_turn=True,
                               riser_height_mm=None, tread_depth_mm=None):
        try:
            height_mm = feet_to_mm(top_level.Elevation - base_level.Elevation)
            steps     = self.calculate_steps(height_mm, riser_height_mm, tread_depth_mm)

            steps_first  = steps['riser_count'] // 2
            steps_second = steps['riser_count'] - steps_first

            stair_type = self._get_stair_type()
            if not stair_type:
                return None

            tread_ft     = mm_to_feet(steps['tread_depth_mm'])
            width_ft     = mm_to_feet(width_mm)
            new_stair_id = None
            preprocessor = IgnoreAllWarnings()

            with StairsEditScope(self.doc, "AutoRevit Quart tournant") as scope:
                try:
                    stair_elem_id = scope.Start(base_level.Id, top_level.Id)

                    with Transaction(self.doc, "AutoRevit - Runs quart tournant") as t:
                        t.Start()

                        # Appliquer le type
                        stair_elem = self.doc.GetElement(stair_elem_id)
                        stair_elem.ChangeTypeId(stair_type.Id)

                        p1 = XYZ(location.X, location.Y, base_level.Elevation)
                        p2 = XYZ(location.X + tread_ft * steps_first,
                                 location.Y,
                                 base_level.Elevation)

                        run1 = StairsRun.CreateStraightRun(
                            self.doc, stair_elem_id,
                            Line.CreateBound(p1, p2),
                            StairsRunJustification.Center)
                        w1 = run1.get_Parameter(
                            BuiltInParameter.STAIRS_RUN_ACTUAL_RUN_WIDTH)
                        if w1 and not w1.IsReadOnly:
                            w1.Set(width_ft)

                        # Palier intermediaire
                        hw  = width_ft / 2.0
                        ld  = tread_ft * 2.0
                        lp1 = XYZ(p2.X - hw, p2.Y - ld / 2.0, p2.Z)
                        lp2 = XYZ(p2.X + hw, p2.Y - ld / 2.0, p2.Z)
                        lp3 = XYZ(p2.X + hw, p2.Y + ld / 2.0, p2.Z)
                        lp4 = XYZ(p2.X - hw, p2.Y + ld / 2.0, p2.Z)
                        loop = CurveLoop()
                        loop.Append(Line.CreateBound(lp1, lp2))
                        loop.Append(Line.CreateBound(lp2, lp3))
                        loop.Append(Line.CreateBound(lp3, lp4))
                        loop.Append(Line.CreateBound(lp4, lp1))
                        StairsLanding.CreateSketchedLanding(
                            self.doc, stair_elem_id, base_level.Id, loop)

                        # Deuxieme volee
                        dy  = tread_ft * steps_second
                        p3  = XYZ(p2.X,
                                  p2.Y + dy if left_turn else p2.Y - dy,
                                  p2.Z)
                        run2 = StairsRun.CreateStraightRun(
                            self.doc, stair_elem_id,
                            Line.CreateBound(p2, p3),
                            StairsRunJustification.Center)
                        w2 = run2.get_Parameter(
                            BuiltInParameter.STAIRS_RUN_ACTUAL_RUN_WIDTH)
                        if w2 and not w2.IsReadOnly:
                            w2.Set(width_ft)

                        t.Commit()

                    scope.Commit(preprocessor)
                    new_stair_id = stair_elem_id

                except Exception as e_inner:
                    try:
                        scope.Cancel()
                    except:
                        pass
                    self.logger.log_error(e_inner, {
                        'location': str(location),
                        'base':     base_level.Name,
                        'top':      top_level.Name,
                    })
                    return None

            if new_stair_id:
                self._set_comment(
                    new_stair_id,
                    "AutoRevit QUART_TOURNANT {0}m".format(steps['riser_count']))

            return new_stair_id

        except Exception as e:
            self.logger.log_error(e, {
                'location': str(location),
                'base':     base_level.Name,
                'top':      top_level.Name,
            })
            return None

    # -----------------------------------------------------------------------
    # 5. CREATION ESCALIER HELICOIDAL
    # -----------------------------------------------------------------------

    def create_spiral_stair(self, center, base_level, top_level,
                             radius_mm=900, rotation_angle=360,
                             riser_height_mm=None, tread_depth_mm=None):
        try:
            height_mm = feet_to_mm(top_level.Elevation - base_level.Elevation)
            steps     = self.calculate_steps(height_mm, riser_height_mm, tread_depth_mm)

            stair_type = self._get_stair_type()
            if not stair_type:
                return None

            radius_ft = mm_to_feet(radius_mm)
            tread_ft  = mm_to_feet(steps['tread_depth_mm'])
            num_pts   = steps['riser_count'] + 1

            pts = []
            for i in range(num_pts):
                angle = (rotation_angle * i / float(num_pts - 1)) * math.pi / 180.0
                pts.append(XYZ(
                    center.X + radius_ft * math.cos(angle),
                    center.Y + radius_ft * math.sin(angle),
                    base_level.Elevation))

            new_stair_id = None
            preprocessor = IgnoreAllWarnings()

            with StairsEditScope(self.doc, "AutoRevit Helicoidal") as scope:
                try:
                    stair_elem_id = scope.Start(base_level.Id, top_level.Id)

                    with Transaction(self.doc, "AutoRevit - Runs helicoidal") as t:
                        t.Start()

                        stair_elem = self.doc.GetElement(stair_elem_id)
                        stair_elem.ChangeTypeId(stair_type.Id)

                        for i in range(len(pts) - 1):
                            seg = Line.CreateBound(pts[i], pts[i + 1])
                            run = StairsRun.CreateStraightRun(
                                self.doc, stair_elem_id, seg,
                                StairsRunJustification.Center)
                            w = run.get_Parameter(
                                BuiltInParameter.STAIRS_RUN_ACTUAL_RUN_WIDTH)
                            if w and not w.IsReadOnly:
                                w.Set(radius_ft / 2.0)

                        t.Commit()

                    scope.Commit(preprocessor)
                    new_stair_id = stair_elem_id

                except Exception as e_inner:
                    try:
                        scope.Cancel()
                    except:
                        pass
                    self.logger.log_error(e_inner, {
                        'center': str(center),
                        'base':   base_level.Name,
                        'top':    top_level.Name,
                    })
                    return None

            if new_stair_id:
                self._set_comment(
                    new_stair_id,
                    "AutoRevit HELICOIDAL R={0}mm {1}m".format(
                        radius_mm, steps['riser_count']))

            return new_stair_id

        except Exception as e:
            self.logger.log_error(e, {
                'center': str(center),
                'base':   base_level.Name,
                'top':    top_level.Name,
            })
            return None

    # -----------------------------------------------------------------------
    # 6. UTILITAIRES
    # -----------------------------------------------------------------------

    def _get_stair_type(self):
        collector = (FilteredElementCollector(self.doc)
                     .OfClass(StairsType)
                     .WhereElementIsElementType())
        # Preference : beton monolithique
        for st in collector:
            n = self._get_name(st).lower()
            if "monolith" in n or "beton" in n or "concrete" in n:
                return st
        # Sinon premier disponible
        return (FilteredElementCollector(self.doc)
                .OfClass(StairsType)
                .WhereElementIsElementType()
                .FirstElement())

    def _add_railings(self, stair, width_mm):
        return []

    # -----------------------------------------------------------------------
    # 7. EXECUTION GLOBALE
    # -----------------------------------------------------------------------

    def create_all_stairs(self):
        levels = get_all_levels(self.doc)
        levels = sorted(levels, key=lambda l: l.Elevation)

        if len(levels) < 2:
            return {'success': False, 'message': 'Niveaux insuffisants'}

        results = []

        for i in range(len(levels) - 1):
            base = levels[i]
            top  = levels[i + 1]

            height_mm     = feet_to_mm(top.Elevation - base.Elevation)
            steps         = self.calculate_steps(height_mm)
            run_length_ft = mm_to_feet(steps['total_run_mm'])

            start_point = XYZ(0,             0, base.Elevation)
            end_point   = XYZ(run_length_ft, 0, base.Elevation)

            stair_id = self.create_straight_stair(
                start_point, end_point, base, top, width_mm=900)

            if stair_id:
                results.append({
                    'id':   stair_id.IntegerValue,
                    'base': base.Name,
                    'top':  top.Name,
                    'type': 'DROIT',
                })

        self.logger.log_info("{0} escaliers crees".format(len(results)))

        return {
            'success': True,
            'total':   len(results),
            'stairs':  results,
        }


# ---------------------------------------------------------------------------
# Point d entree
# ---------------------------------------------------------------------------

def main():
    from pyrevit import revit, forms

    doc    = revit.doc
    levels = get_all_levels(doc)

    if len(levels) < 2:
        forms.alert(
            "Au moins 2 niveaux sont necessaires.",
            title="AutoRevit - Escaliers")
        return

    options = [
        "Creer escaliers entre tous les niveaux",
        "Calculer dimensions seulement",
    ]

    selected = forms.SelectFromList.show(
        options,
        title="AutoRevit - Creation escaliers",
        button_name='Continuer',
        multiselect=False)

    if not selected:
        return

    engine = StairPlacementEngine(doc)

    if selected[0] == options[1]:
        from pyrevit import script
        out    = script.get_output()
        height = forms.ask_for_string(
            prompt="Hauteur a franchir (mm):",
            title="AutoRevit - Calcul escalier",
            default="3000")
        if height:
            try:
                height_mm = float(height)
                steps     = engine.calculate_steps(height_mm)
                out.print_md("## Dimensions - Hauteur: {0}mm".format(height_mm))
                out.print_md("**Nombre de marches:** {0}".format(steps['riser_count']))
                out.print_md("**Hauteur marche:** {0:.0f} mm".format(steps['riser_height_mm']))
                out.print_md("**Giron:** {0:.0f} mm".format(steps['tread_depth_mm']))
                out.print_md("**Blondel:** {0:.0f} mm".format(steps['blondel_value']))
                out.print_md("**Longueur volee:** {0:.0f} mm".format(steps['total_run_mm']))
            except ValueError:
                forms.alert("Valeur invalide", title="Erreur")
    else:
        if forms.alert(
            "Creer des escaliers entre les {0} niveaux ?".format(len(levels)),
            title="AutoRevit - Escaliers",
            yes=True, no=True):
            result = engine.create_all_stairs()
            if result['success']:
                forms.alert(
                    "{0} escaliers crees !".format(result['total']),
                    title="Succes")


if __name__ == '__main__':
    main()