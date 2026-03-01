# -*- coding: utf-8 -*-
"""
DocumentationEngine - Moteur de documentation et d'export
===========================================================
Responsabilités :
- Création automatique de vues (plans, coupes, 3D)
- Génération de nomenclatures et métrés
- Création de feuilles et mise en page
- Export PDF/DWG/IFC
- Gestion des cartouches et révisions
- Impression batch

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
from services.transaction_service import TransactionService
from services.logging_service import LoggingService
from algorithms.geometry_utils import get_bounding_rectangle

logger = get_logger(__name__)

try:
    from Autodesk.Revit.DB import (
        Document,
        ViewPlan,
        ViewSection,
        View3D,
        ViewSheet,
        ViewFamilyType,
        ViewFamily,
        FilteredElementCollector,
        BuiltInCategory,
        BuiltInParameter,
        ElementId,
        Level,
        BoundingBoxXYZ,
        Line,
        XYZ,
        Transaction,
        ScheduleSheetInstance,
        ViewSchedule,
        ScheduleField,
        ScheduleFieldType,
        FilteredWorksetCollector,
        Workset,
        PDFExportOptions,
        DWGExportOptions,
        IFCExportOptions,
        ImageExportOptions,
        ImageFileType,
        ExportDestination,
        ParameterFilterElement,
        ParameterFilterRuleFactory,
        ElementFilter,
        LogicalOrFilter,
        LogicalAndFilter
    )
    REVIT_AVAILABLE = True
except ImportError:
    REVIT_AVAILABLE = False
     
    
    class XYZ:
        def __init__(self, x=0, y=0, z=0):
            self.X = x
            self.Y = y
            self.Z = z


class DocumentationEngine:
    """
    Moteur de documentation et d'export.
    
    Exemple d'utilisation :
    ----------------------
    >>> from pyrevit import revit
    >>> from core import DocumentationEngine
    >>>
    >>> doc = revit.doc
    >>> engine = DocumentationEngine(doc)
    >>>
    >>> # Créer des vues de plan pour tous les niveaux
    >>> views = engine.create_floor_plans()
    >>>
    >>> # Générer des nomenclatures
    >>> schedules = engine.create_column_schedule()
    >>>
    >>> # Créer des feuilles
    >>> sheets = engine.create_sheets_from_views(views)
    >>>
    >>> # Exporter en PDF
    >>> engine.export_views_to_pdf(views, "C:/Exports/")
    """

    # Types de vues prédéfinis
    VIEW_TEMPLATES = {
        'structural_plan': {
            'view_family': ViewFamily.FloorPlan,
            'view_name_prefix': 'STR - Plan',
            'scale': 100,
            'detail_level': 'Medium',
            'discipline': 'Structural',
            'phase': 'Construction'
        },
        'structural_section': {
            'view_family': ViewFamily.Section,
            'view_name_prefix': 'STR - Coupe',
            'scale': 50,
            'detail_level': 'Fine',
            'discipline': 'Structural',
            'phase': 'Construction'
        },
        'structural_3d': {
            'view_family': ViewFamily.ThreeDimensional,
            'view_name_prefix': 'STR - 3D',
            'scale': 100,
            'detail_level': 'Fine',
            'discipline': 'Structural',
            'phase': 'Construction'
        },
        'reinforcement_3d': {
            'view_family': ViewFamily.ThreeDimensional,
            'view_name_prefix': 'STR - Ferraillage 3D',
            'scale': 50,
            'detail_level': 'Fine',
            'discipline': 'Structural',
            'phase': 'Construction'
        },
        'formwork_plan': {
            'view_family': ViewFamily.FloorPlan,
            'view_name_prefix': 'STR - Coffrage',
            'scale': 100,
            'detail_level': 'Medium',
            'discipline': 'Structural',
            'phase': 'Construction'
        }
    }

    # Formats de feuilles standards (largeur x hauteur en mm)
    SHEET_SIZES = {
        'A0': (841, 1189),
        'A1': (594, 841),
        'A2': (420, 594),
        'A3': (297, 420),
        'A4': (210, 297),
        'ARCH_E1': (762, 1067),
        'ARCH_D': (559, 864),
        'ARCH_C': (432, 559),
        'ARCH_B': (305, 457),
        'ARCH_A': (216, 279)
    }

    def __init__(self, document):
        """
        Initialise le moteur de documentation.
        
        Args:
            document: Document Revit actif
        """
        if not REVIT_AVAILABLE and document is not None:
            logger.warning("Revit API non disponible - documentation limitée")
        
        self.doc = document
        
        # Services
        self.revit_service = RevitService(document)
        self.geometry_service = GeometryService(document)
        self.transaction_service = TransactionService(document)
        self.logger = LoggingService()
        
        # Cache des types de vues et feuilles
        self._view_family_types_cache = {}
        self._sheet_family_types_cache = {}
        self._titleblock_types_cache = {}
        
        # Statistiques
        self.stats = {
            'views_created': 0,
            'schedules_created': 0,
            'sheets_created': 0,
            'exports_performed': 0
        }
        
        logger.info("DocumentationEngine initialisé")

    # ========================================================================
    # CRÉATION DE VUES
    # ========================================================================

    def create_floor_plans(self, levels=None, template='structural_plan'):
        """
        Crée des vues en plan pour les niveaux spécifiés.
        
        Args:
            levels (list): Liste des niveaux (None = tous les niveaux)
            template (str): Nom du template à utiliser
        
        Returns:
            list: Vues créées
        """
        logger.info("Création de vues en plan - Template: " + template)
        
        created_views = []
        
        try:
            # Récupérer les niveaux
            if levels is None:
                levels = self.revit_service.get_all_levels()
            
            # Récupérer le type de vue
            view_family_type = self._get_view_family_type(
                ViewFamily.FloorPlan,
                template
            )
            
            if not view_family_type:
                raise ValidationError("Type de vue plan non trouvé")
            
            # Créer une vue pour chaque niveau
            for level in levels:
                # Éviter les doublons
                existing_views = self._find_existing_views(
                    ViewFamily.FloorPlan,
                    level.Name
                )
                
                if existing_views:
                    logger.debug("Vue existante pour " + level.Name + " - " + existing_views[0].Name)
                    created_views.extend(existing_views)
                    continue
                
                # Créer la vue
                view = ViewPlan.Create(
                    self.doc,
                    view_family_type.Id,
                    level.Id
                )
                
                # Renommer
                view_name = self.VIEW_TEMPLATES[template]['view_name_prefix'] + " - " + level.Name
                view.Name = self._get_unique_view_name(view_name)
                
                # Appliquer les paramètres
                self._apply_view_template(view, template)
                
                created_views.append(view)
                self.stats['views_created'] += 1
                
                logger.info("Vue créée: " + view.Name)
            
        except Exception as e:
            logger.error("Erreur création vues en plan: " + str(e))
            raise RevitAPIError("Échec création vues: " + str(e))
        
        return created_views

    def create_structural_sections(self, section_lines, template='structural_section'):
        """
        Crée des vues en coupe.
        
        Args:
            section_lines (list): Liste de dict avec start, end, bounding_box
            template (str): Nom du template
        
        Returns:
            list: Vues créées
        """
        logger.info("Création de coupes structurelles")
        
        created_views = []
        
        try:
            # Récupérer le type de vue
            view_family_type = self._get_view_family_type(
                ViewFamily.Section,
                template
            )
            
            if not view_family_type:
                raise ValidationError("Type de vue coupe non trouvé")
            
            for i, section_data in enumerate(section_lines):
                start = section_data['start']
                end = section_data['end']
                bbox = section_data.get('bounding_box')
                
                # Créer la ligne de coupe
                line = Line.CreateBound(start, end)
                
                # Créer la vue
                section = ViewSection.CreateSection(
                    self.doc,
                    view_family_type.Id,
                    line,
                    bbox
                )
                
                # Renommer
                section_name = self.VIEW_TEMPLATES[template]['view_name_prefix'] + " " + str(i + 1)
                section.Name = self._get_unique_view_name(section_name)
                
                # Appliquer les paramètres
                self._apply_view_template(section, template)
                
                created_views.append(section)
                self.stats['views_created'] += 1
                
                logger.info("Coupe créée: " + section.Name)
            
        except Exception as e:
            logger.error("Erreur création coupes: " + str(e))
            raise RevitAPIError("Échec création coupes: " + str(e))
        
        return created_views

    def create_3d_view(self, name="3D Structure", template='structural_3d'):
        """
        Crée une vue 3D structurelle.
        
        Args:
            name (str): Nom de la vue
            template (str): Nom du template
        
        Returns:
            View3D: Vue créée
        """
        logger.info("Création vue 3D: " + name)
        
        try:
            # Chercher une vue existante
            existing_views = self._find_existing_views(ViewFamily.ThreeDimensional, name)
            if existing_views:
                logger.debug("Vue 3D existante: " + name)
                return existing_views[0]
            
            # Récupérer le type de vue
            view_family_type = self._get_view_family_type(
                ViewFamily.ThreeDimensional,
                template
            )
            
            if not view_family_type:
                raise ValidationError("Type de vue 3D non trouvé")
            
            # Créer la vue
            view_3d = View3D.CreateIsometric(self.doc, view_family_type.Id)
            
            # Renommer
            view_3d.Name = self._get_unique_view_name(name)
            
            # Appliquer les paramètres
            self._apply_view_template(view_3d, template)
            
            # Appliquer le filtre de catégories structurelles
            self._apply_structural_filter(view_3d)
            
            self.stats['views_created'] += 1
            logger.info("Vue 3D créée: " + view_3d.Name)
            
            return view_3d
            
        except Exception as e:
            logger.error("Erreur création vue 3D: " + str(e))
            raise RevitAPIError("Échec création vue 3D: " + str(e))

    def create_reinforcement_3d_view(self):
        """
        Crée une vue 3D spécifique au ferraillage.
        
        Returns:
            View3D: Vue créée
        """
        view = self.create_3d_view("STR - Ferraillage 3D", "reinforcement_3d")
        
        # TODO: Configurer la visibilité des armatures
        return view

    def _get_view_family_type(self, view_family, template_key):
        """Récupère le type de famille de vue."""
        cache_key = str(view_family) + "_" + template_key
        
        if cache_key in self._view_family_types_cache:
            return self._view_family_types_cache[cache_key]
        
        collector = FilteredElementCollector(self.doc)\
            .OfClass(ViewFamilyType)
        
        for vft in collector:
            if vft.ViewFamily == view_family:
                self._view_family_types_cache[cache_key] = vft
                return vft
        
        return None

    def _apply_view_template(self, view, template_key):
        """Applique les paramètres de template à une vue."""
        template = self.VIEW_TEMPLATES.get(template_key, {})
        
        try:
            # Échelle
            scale_param = view.get_Parameter(BuiltInParameter.VIEW_SCALE)
            if scale_param and 'scale' in template:
                scale_param.Set(template['scale'])
            
            # Niveau de détail
            detail_param = view.get_Parameter(BuiltInParameter.VIEW_DETAIL_LEVEL)
            if detail_param and 'detail_level' in template:
                detail_level = {
                    'Coarse': 0,
                    'Medium': 1,
                    'Fine': 2
                }.get(template['detail_level'], 1)
                detail_param.Set(detail_level)
            
            # Discipline
            discipline_param = view.get_Parameter(BuiltInParameter.VIEW_DISCIPLINE)
            if discipline_param and 'discipline' in template:
                discipline = {
                    'Architectural': 1,
                    'Structural': 2,
                    'Mechanical': 3,
                    'Electrical': 4,
                    'Plumbing': 5
                }.get(template['discipline'], 2)
                discipline_param.Set(discipline)
            
            # Phase
            phase_param = view.get_Parameter(BuiltInParameter.PHASE_CREATED)
            if phase_param and 'phase' in template:
                # TODO: Trouver l'ID de phase correspondante
                pass
            
        except Exception as e:
            logger.warning("Erreur application template vue: " + str(e))

    def _apply_structural_filter(self, view):
        """Applique un filtre pour n'afficher que les éléments structurels."""
        try:
            # Catégories structurelles à afficher
            structural_cats = [
                BuiltInCategory.OST_StructuralColumns,
                BuiltInCategory.OST_StructuralFraming,
                BuiltInCategory.OST_StructuralFoundation,
                BuiltInCategory.OST_Walls,
                BuiltInCategory.OST_Floors,
                BuiltInCategory.OST_Stairs,
                BuiltInCategory.OST_Ramps
            ]
            
            # Masquer les catégories non-structurelles
            for cat in structural_cats:
                try:
                    view.SetCategoryHidden(cat, False)
                except:
                    pass
            
        except Exception as e:
            logger.warning("Erreur application filtre structurel: " + str(e))

    def _find_existing_views(self, view_family, name_pattern):
        """Trouve les vues existantes correspondant à un pattern."""
        existing = []
        
        collector = FilteredElementCollector(self.doc)\
            .OfClass(ViewPlan)\
            .WhereElementIsNotElementType()
        
        for view in collector:
            if view.ViewFamily == view_family:
                if name_pattern in view.Name:
                    existing.append(view)
        
        return existing

    def _get_unique_view_name(self, base_name):
        """Génère un nom de vue unique."""
        collector = FilteredElementCollector(self.doc)\
            .OfClass(ViewPlan)\
            .WhereElementIsNotElementType()
        
        existing_names = set()
        for view in collector:
            existing_names.add(view.Name)
        
        if base_name not in existing_names:
            return base_name
        
        counter = 1
        while base_name + " (" + str(counter) + ")" in existing_names:
            counter += 1
        
        return base_name + " (" + str(counter) + ")"

    # ========================================================================
    # CRÉATION DE NOMENCLATURES
    # ========================================================================

    def create_column_schedule(self):
        """
        Crée une nomenclature de poteaux.
        
        Returns:
            ViewSchedule: Nomenclature créée
        """
        logger.info("Création nomenclature poteaux")
        
        try:
            # Vérifier si la nomenclature existe déjà
            existing = self._find_schedule("Nomenclature Poteaux")
            if existing:
                logger.debug("Nomenclature existante: Nomenclature Poteaux")
                return existing[0]
            
            # Créer la nomenclature
            schedule = ViewSchedule.CreateSchedule(
                self.doc,
                ElementId(BuiltInCategory.OST_StructuralColumns)
            )
            
            schedule.Name = "Nomenclature Poteaux"
            
            # Ajouter les champs
            fields = [
                ("Famille", ScheduleFieldType.Text),
                ("Type", ScheduleFieldType.Text),
                ("Largeur", ScheduleFieldType.Integer),
                ("Hauteur", ScheduleFieldType.Integer),
                ("Longueur", ScheduleFieldType.Length),
                ("Volume", ScheduleFieldType.Volume),
                ("Niveau", ScheduleFieldType.Text),
                ("Commentaires", ScheduleFieldType.Text)
            ]
            
            for field_name, field_type in fields:
                self._add_schedule_field(schedule, field_name, field_type)
            
            # Trier par niveau
            self._add_schedule_sort(schedule, "Niveau", True)
            
            self.stats['schedules_created'] += 1
            logger.info("Nomenclature créée: " + schedule.Name)
            
            return schedule
            
        except Exception as e:
            logger.error("Erreur création nomenclature poteaux: " + str(e))
            raise RevitAPIError("Échec création nomenclature: " + str(e))

    def create_beam_schedule(self):
        """
        Crée une nomenclature de poutres.
        
        Returns:
            ViewSchedule: Nomenclature créée
        """
        logger.info("Création nomenclature poutres")
        
        try:
            existing = self._find_schedule("Nomenclature Poutres")
            if existing:
                return existing[0]
            
            schedule = ViewSchedule.CreateSchedule(
                self.doc,
                ElementId(BuiltInCategory.OST_StructuralFraming)
            )
            
            schedule.Name = "Nomenclature Poutres"
            
            fields = [
                ("Famille", ScheduleFieldType.Text),
                ("Type", ScheduleFieldType.Text),
                ("Largeur", ScheduleFieldType.Integer),
                ("Hauteur", ScheduleFieldType.Integer),
                ("Longueur", ScheduleFieldType.Length),
                ("Volume", ScheduleFieldType.Volume),
                ("Niveau", ScheduleFieldType.Text),
                ("Commentaires", ScheduleFieldType.Text)
            ]
            
            for field_name, field_type in fields:
                self._add_schedule_field(schedule, field_name, field_type)
            
            self._add_schedule_sort(schedule, "Niveau", True)
            
            self.stats['schedules_created'] += 1
            logger.info("Nomenclature créée: " + schedule.Name)
            
            return schedule
            
        except Exception as e:
            logger.error("Erreur création nomenclature poutres: " + str(e))
            raise

    def create_slab_schedule(self):
        """
        Crée une nomenclature de dalles.
        
        Returns:
            ViewSchedule: Nomenclature créée
        """
        logger.info("Création nomenclature dalles")
        
        try:
            existing = self._find_schedule("Nomenclature Dalles")
            if existing:
                return existing[0]
            
            schedule = ViewSchedule.CreateSchedule(
                self.doc,
                ElementId(BuiltInCategory.OST_Floors)
            )
            
            schedule.Name = "Nomenclature Dalles"
            
            fields = [
                ("Famille", ScheduleFieldType.Text),
                ("Type", ScheduleFieldType.Text),
                ("Épaisseur", ScheduleFieldType.Length),
                ("Surface", ScheduleFieldType.Area),
                ("Volume", ScheduleFieldType.Volume),
                ("Niveau", ScheduleFieldType.Text),
                ("Commentaires", ScheduleFieldType.Text)
            ]
            
            for field_name, field_type in fields:
                self._add_schedule_field(schedule, field_name, field_type)
            
            self._add_schedule_sort(schedule, "Niveau", True)
            
            self.stats['schedules_created'] += 1
            logger.info("Nomenclature créée: " + schedule.Name)
            
            return schedule
            
        except Exception as e:
            logger.error("Erreur création nomenclature dalles: " + str(e))
            raise

    def create_rebar_schedule(self):
        """
        Crée une nomenclature d'armatures.
        
        Returns:
            ViewSchedule: Nomenclature créée
        """
        logger.info("Création nomenclature armatures")
        
        try:
            existing = self._find_schedule("Nomenclature Armatures")
            if existing:
                return existing[0]
            
            schedule = ViewSchedule.CreateSchedule(
                self.doc,
                ElementId(BuiltInCategory.OST_Rebar)
            )
            
            schedule.Name = "Nomenclature Armatures"
            
            fields = [
                ("Famille", ScheduleFieldType.Text),
                ("Type", ScheduleFieldType.Text),
                ("Diamètre", ScheduleFieldType.Integer),
                ("Longueur", ScheduleFieldType.Length),
                ("Quantité", ScheduleFieldType.Integer),
                ("Poids total", ScheduleFieldType.Text),
                ("Commentaires", ScheduleFieldType.Text)
            ]
            
            for field_name, field_type in fields:
                self._add_schedule_field(schedule, field_name, field_type)
            
            self.stats['schedules_created'] += 1
            logger.info("Nomenclature créée: " + schedule.Name)
            
            return schedule
            
        except Exception as e:
            logger.error("Erreur création nomenclature armatures: " + str(e))
            raise

    def _add_schedule_field(self, schedule, field_name, field_type):
        """Ajoute un champ à une nomenclature."""
        try:
            field = schedule.Definition.AddField(field_type)
            field.ColumnHeading = field_name
            return field
        except Exception as e:
            logger.warning("Erreur ajout champ " + field_name + ": " + str(e))
            return None

    def _add_schedule_sort(self, schedule, field_name, ascending=True):
        """Ajoute un tri à une nomenclature."""
        try:
            # Trouver le champ par son nom
            for i in range(schedule.Definition.GetFieldCount()):
                field = schedule.Definition.GetField(i)
                if field.ColumnHeading == field_name:
                    schedule.Definition.AddSortGroupField(field, ascending)
                    break
        except Exception as e:
            logger.warning("Erreur ajout tri: " + str(e))

    def _find_schedule(self, name):
        """Trouve une nomenclature par son nom."""
        collector = FilteredElementCollector(self.doc)\
            .OfClass(ViewSchedule)\
            .WhereElementIsNotElementType()
        
        schedules = []
        for schedule in collector:
            if schedule.Name == name:
                schedules.append(schedule)
        
        return schedules

    # ========================================================================
    # CRÉATION DE FEUILLES
    # ========================================================================

    def create_sheets_from_views(self, views, sheet_size='A1', titleblock=None):
        """
        Crée des feuilles et y place des vues.
        
        Args:
            views (list): Liste des vues à placer
            sheet_size (str): Format de feuille ('A1', 'A0', etc.)
            titleblock (str): Nom du cartouche
        
        Returns:
            list: Feuilles créées
        """
        logger.info("Création de feuilles - Format: " + sheet_size)
        
        created_sheets = []
        
        try:
            # Récupérer le cartouche
            titleblock_type = self._get_titleblock_type(titleblock)
            if not titleblock_type:
                raise ValidationError("Cartouche non trouvé")
            
            # Récupérer les dimensions de la feuille
            width_mm, height_mm = self.SHEET_SIZES.get(sheet_size, (594, 841))
            width_feet = width_mm / 304.8
            height_feet = height_mm / 304.8
            
            # Grouper les vues par type/niveau
            view_groups = {}
            for view in views:
                key = view.ViewFamily
                if key not in view_groups:
                    view_groups[key] = []
                view_groups[key].append(view)
            
            # Créer une feuille par groupe
            sheet_number = 1
            
            for family, family_views in view_groups.items():
                # Créer la feuille
                sheet = ViewSheet.Create(self.doc, titleblock_type.Id)
                
                sheet.Name = "STR - " + str(family) + " - " + str(sheet_number)
                sheet.SheetNumber = "S-" + str(sheet_number).zfill(2)
                
                # Placer les vues
                x_offset = 0.1  # 100mm en feet
                y_offset = 0.1
                
                for i, view in enumerate(family_views[:4]):  # Max 4 vues par feuille
                    try:
                        col = i % 2
                        row = i // 2
                        
                        x = x_offset + col * (width_feet * 0.45)
                        y = y_offset + row * (height_feet * 0.45)
                        
                        viewport = sheet.AddView(view, XYZ(x, y, 0))
                        
                    except Exception as e:
                        logger.warning("Erreur placement vue: " + str(e))
                
                created_sheets.append(sheet)
                self.stats['sheets_created'] += 1
                sheet_number += 1
                
                logger.info("Feuille créée: " + sheet.SheetNumber + " - " + sheet.Name)
            
        except Exception as e:
            logger.error("Erreur création feuilles: " + str(e))
            raise RevitAPIError("Échec création feuilles: " + str(e))
        
        return created_sheets

    def _get_titleblock_type(self, titleblock_name=None):
        """Récupère le type de cartouche."""
        cache_key = titleblock_name or "default"
        
        if cache_key in self._titleblock_types_cache:
            return self._titleblock_types_cache[cache_key]
        
        collector = FilteredElementCollector(self.doc)\
            .OfCategory(BuiltInCategory.OST_TitleBlocks)\
            .WhereElementIsElementType()
        
        for tb in collector:
            if titleblock_name is None or titleblock_name.lower() in tb.Name.lower():
                self._titleblock_types_cache[cache_key] = tb
                return tb
        
        # Retourner le premier disponible
        first = collector.FirstElement()
        if first:
            self._titleblock_types_cache[cache_key] = first
            return first
        
        return None

    # ========================================================================
    # EXPORT
    # ========================================================================

    def export_views_to_pdf(self, views, output_dir, combine=False):
        """
        Exporte des vues au format PDF.
        
        Args:
            views (list): Liste des vues à exporter
            output_dir (str): Répertoire de sortie
            combine (bool): Combiner en un seul fichier
        
        Returns:
            list: Chemins des fichiers générés
        """
        logger.info("Export PDF - " + str(len(views)) + " vues")
        
        exported_files = []
        
        try:
            # Créer le répertoire si nécessaire
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Configurer les options PDF
            pdf_options = PDFExportOptions()
            pdf_options.ExportQuality = PDFExportOptions.PDFQuality.High
            pdf_options.CombineViews = combine
            pdf_options.ExportLinks = False
            pdf_options.ExportMarks = True
            pdf_options.ExportTextAsText = True
            
            if combine:
                # Exporter toutes les vues en un seul fichier
                output_file = os.path.join(output_dir, "AutoRevit_Export.pdf")
                views_ids = [v.Id for v in views]
                
                pdf_options.SetViewsAndSheets(views_ids)
                self.doc.Export(output_dir, output_file, pdf_options)
                exported_files.append(output_file)
                
            else:
                # Exporter chaque vue séparément
                for view in views:
                    view_name = self._sanitize_filename(view.Name)
                    output_file = os.path.join(output_dir, view_name + ".pdf")
                    
                    pdf_options.SetViewsAndSheets([view.Id])
                    self.doc.Export(output_dir, view_name, pdf_options)
                    exported_files.append(output_file)
            
            self.stats['exports_performed'] += 1
            logger.info(str(len(exported_files)) + " fichier(s) PDF généré(s)")
            
        except Exception as e:
            logger.error("Erreur export PDF: " + str(e))
            raise RevitAPIError("Échec export PDF: " + str(e))
        
        return exported_files

    def export_views_to_dwg(self, views, output_dir):
        """
        Exporte des vues au format DWG.
        
        Args:
            views (list): Liste des vues à exporter
            output_dir (str): Répertoire de sortie
        
        Returns:
            list: Chemins des fichiers générés
        """
        logger.info("Export DWG - " + str(len(views)) + " vues")
        
        exported_files = []
        
        try:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            dwg_options = DWGExportOptions()
            
            for view in views:
                view_name = self._sanitize_filename(view.Name)
                
                dwg_options.SetViewsAndSheets([view.Id])
                self.doc.Export(output_dir, view_name, dwg_options)
                
                exported_files.append(os.path.join(output_dir, view_name + ".dwg"))
            
            self.stats['exports_performed'] += 1
            logger.info(str(len(exported_files)) + " fichier(s) DWG généré(s)")
            
        except Exception as e:
            logger.error("Erreur export DWG: " + str(e))
            raise RevitAPIError("Échec export DWG: " + str(e))
        
        return exported_files

    def export_to_ifc(self, output_dir, filename="AutoRevit.ifc"):
        """
        Exporte le modèle au format IFC.
        
        Args:
            output_dir (str): Répertoire de sortie
            filename (str): Nom du fichier
        
        Returns:
            str: Chemin du fichier généré
        """
        logger.info("Export IFC")
        
        try:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            output_path = os.path.join(output_dir, filename)
            
            ifc_options = IFCExportOptions()
            
            # Configuration IFC de base
            ifc_options.WallAndColumnSplitting = False
            ifc_options.ExportBaseQuantities = True
            ifc_options.ExportPartsAsBuildingElements = True
            
            self.doc.Export(output_dir, filename, ifc_options)
            
            self.stats['exports_performed'] += 1
            logger.info("Export IFC: " + output_path)
            
            return output_path
            
        except Exception as e:
            logger.error("Erreur export IFC: " + str(e))
            raise RevitAPIError("Échec export IFC: " + str(e))

    def _sanitize_filename(self, filename):
        """Nettoie un nom de fichier."""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename

    # ========================================================================
    # GESTION DES CARTUCHES
    # ========================================================================

    def update_titleblocks(self, project_info):
        """
        Met à jour les informations des cartouches.
        
        Args:
            project_info (dict): Informations projet
        
        Returns:
            int: Nombre de cartouches mis à jour
        """
        logger.info("Mise à jour des cartouches")
        
        updated = 0
        
        try:
            collector = FilteredElementCollector(self.doc)\
                .OfCategory(BuiltInCategory.OST_TitleBlocks)\
                .WhereElementIsNotElementType()
            
            for titleblock in collector:
                # Nom du projet
                param = titleblock.LookupParameter("Project Name")
                if param and 'name' in project_info:
                    param.Set(project_info['name'])
                    updated += 1
                
                # Numéro du projet
                param = titleblock.LookupParameter("Project Number")
                if param and 'number' in project_info:
                    param.Set(project_info['number'])
                    updated += 1
                
                # Adresse
                param = titleblock.LookupParameter("Project Address")
                if param and 'address' in project_info:
                    param.Set(project_info['address'])
                    updated += 1
                
                # Date
                param = titleblock.LookupParameter("Date")
                if param:
                    today = datetime.now().strftime("%d/%m/%Y")
                    param.Set(today)
                    updated += 1
                
                # Auteur
                param = titleblock.LookupParameter("Author")
                if param:
                    from helpers.revit_helpers import get_username
                    username = get_username()
                    param.Set(username)
                    updated += 1
            
            logger.info(str(updated) + " cartouche(s) mis à jour")
            
        except Exception as e:
            logger.error("Erreur mise à jour cartouches: " + str(e))
        
        return updated

    # ========================================================================
    # STATISTIQUES
    # ========================================================================

    def get_stats(self):
        """
        Récupère les statistiques du moteur.
        
        Returns:
            dict: Statistiques
        """
        return {
            'views_created': self.stats['views_created'],
            'schedules_created': self.stats['schedules_created'],
            'sheets_created': self.stats['sheets_created'],
            'exports_performed': self.stats['exports_performed'],
            'total_documents': sum(self.stats.values())
        }

    def reset_stats(self):
        """Réinitialise les statistiques."""
        self.stats = {
            'views_created': 0,
            'schedules_created': 0,
            'sheets_created': 0,
            'exports_performed': 0
        }
        logger.info("Statistiques réinitialisées")


# ============================================================================
# FONCTION DE TEST
# ============================================================================

def test_documentation_engine():
    """
    Test du moteur de documentation.
    """
    print("\n" + "="*60)
    print("TEST DOCUMENTATION ENGINE")
    print("="*60)
    
    if not REVIT_AVAILABLE:
        print("\n❌ Revit non disponible - test en mode développement")
    else:
        print("\n✅ Revit disponible")
    
    try:
        from pyrevit import revit
        
        print("\n1. Initialisation...")
        doc = revit.doc if REVIT_AVAILABLE else None
        engine = DocumentationEngine(doc)
        print("   ✅ DocumentationEngine créé")
        
        print("\n2. Test création vues...")
        if REVIT_AVAILABLE:
            views = engine.create_floor_plans()
            print("   " + str(len(views)) + " vues en plan créées")
        
        print("\n3. Test nomenclatures...")
        if REVIT_AVAILABLE:
            schedule = engine.create_column_schedule()
            if schedule:
                print("   ✅ Nomenclature poteaux créée")
        
        print("\n4. Test stats...")
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
    test_documentation_engine()