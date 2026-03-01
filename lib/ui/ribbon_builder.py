# -*- coding: utf-8 -*-
"""
RibbonBuilder - Construction dynamique du ruban pyRevit
========================================================
Version 4.8 - CORRECTION icônes placeholder 32x32 valides
- ✅ FIX #1 : Encodage Unicode (Python 2/3, Windows/IronPython)
- ✅ FIX #2 : Division automatique des stacks > 3 items (robuste)
- ✅ FIX #3 : Generation automatique YAML pour panels et boutons
- ✅ FIX #4 : Accents + caracteres speciaux -> ASCII dans les scripts
- ✅ FIX #6 : Icônes placeholder 32x32 valides pour pyRevit
- ✅ FIX #7 : Optimisation sanitize_script avec str.translate
- ✅ FIX #9 : SCRIPT_HEADER sans import auth.session (évite erreurs)
- ✅ FIX #10: Placeholder PNG 32x32 gris généré via struct+zlib (sans PIL)
- ✅ FIX #11: urllib corrigé Python 2/3, placeholder auto si pas d'icône API
- ⚠️  REMOVED : Largeur adaptative (pyRevit gère automatiquement)
"""

import os
import json
import shutil
import struct
import zlib

# ══════════════════════════════════════════════════════════════════
#  COMPAT PYTHON 2 / 3
# ══════════════════════════════════════════════════════════════════
import sys
PY2 = sys.version_info[0] == 2

if PY2:
    text_type = unicode  # noqa: F821
    string_types = (str, unicode)  # noqa: F821
else:
    text_type = str
    string_types = (str,)


def _safe_str(value):
    """✅ FIX #1 - UNICODE"""
    if value is None:
        return u''
    if isinstance(value, text_type):
        return value
    if isinstance(value, bytes):
        for enc in ('utf-8', 'latin-1', 'cp1252'):
            try:
                return value.decode(enc)
            except (UnicodeDecodeError, AttributeError):
                continue
        return value.decode('utf-8', errors='replace')
    try:
        return text_type(value)
    except Exception:
        return repr(value)


def _open_utf8(path, mode='r'):
    """✅ FIX #1 - UNICODE"""
    try:
        from io import open as io_open
        return io_open(path, mode, encoding='utf-8')
    except ImportError:
        import codecs
        return codecs.open(path, mode, encoding='utf-8')


_ACCENT_MAP = {
    u'à': u'a', u'â': u'a', u'ä': u'a', u'á': u'a', u'ã': u'a', u'å': u'a',
    u'è': u'e', u'é': u'e', u'ê': u'e', u'ë': u'e',
    u'î': u'i', u'ï': u'i', u'í': u'i', u'ì': u'i',
    u'ô': u'o', u'ö': u'o', u'ó': u'o', u'ò': u'o', u'õ': u'o', u'ø': u'o',
    u'ù': u'u', u'û': u'u', u'ü': u'u', u'ú': u'u',
    u'ç': u'c', u'ñ': u'n', u'ý': u'y', u'ÿ': u'y',
    u'À': u'A', u'Â': u'A', u'Ä': u'A', u'Á': u'A', u'Ã': u'A', u'Å': u'A',
    u'È': u'E', u'É': u'E', u'Ê': u'E', u'Ë': u'E',
    u'Î': u'I', u'Ï': u'I', u'Í': u'I', u'Ì': u'I',
    u'Ô': u'O', u'Ö': u'O', u'Ó': u'O', u'Ò': u'O', u'Õ': u'O', u'Ø': u'O',
    u'Ù': u'U', u'Û': u'U', u'Ü': u'U', u'Ú': u'U',
    u'Ç': u'C', u'Ñ': u'N', u'Ý': u'Y',
    u'\u2019': u"'", u'\u201c': u'"', u'\u201d': u'"',
    u'\u2013': u'-', u'\u2014': u'-', u'\u2026': u'...',
}


def _sanitize_script_text(text):
    """✅ FIX #4 + FIX #7 - ACCENTS (optimisé)"""
    if not text:
        return text
    text = _safe_str(text)

    if PY2:
        for char, replacement in _ACCENT_MAP.items():
            text = text.replace(char, replacement)
    else:
        try:
            trans_table = str.maketrans(_ACCENT_MAP)
            text = text.translate(trans_table)
        except Exception:
            for char, replacement in _ACCENT_MAP.items():
                text = text.replace(char, replacement)

    result = []
    for char in text:
        if ord(char) > 127:
            result.append(u'?')
        else:
            result.append(char)
    return u''.join(result)


try:
    from utils.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    class FallbackLogger:
        def _print(self, level, msg):
            try:
                line = u"[{}] {}".format(level, _safe_str(msg))
                if PY2:
                    print(line.encode('utf-8', errors='replace'))
                else:
                    print(line)
            except Exception:
                print("[{}] <message>".format(level))
        def info(self, msg): self._print("INFO", msg)
        def warning(self, msg): self._print("WARN", msg)
        def error(self, msg): self._print("ERROR", msg)
        def debug(self, msg): pass
    logger = FallbackLogger()


# ✅ FIX #9: Header sans import auth.session
_SCRIPT_HEADER = u'''# -*- coding: utf-8 -*-
# AUTO-GENERE PAR AUTOREVIT - NE PAS MODIFIER MANUELLEMENT
import os
import sys

_script_dir = os.path.dirname(__file__)
_button_dir = os.path.dirname(_script_dir)
_panel_dir = os.path.dirname(_button_dir)
_tab_dir = os.path.dirname(_panel_dir)
_ext_dir = os.path.dirname(_tab_dir)
_lib_path = os.path.join(_ext_dir, 'lib')

if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

from config.settings import Settings
from config.api_client import APIClient
from utils.logger import get_logger

# Note: auth.session ne peut pas etre importe directement
# Utiliser la lecture directe de session_token.json si besoin

_settings = Settings()
_client = APIClient(_settings)
logger = get_logger(__name__)

'''


# ══════════════════════════════════════════════════════════════════
#  ✅ FIX #10 - GÉNÉRATION PNG PLACEHOLDER 32x32 VALIDE
# ══════════════════════════════════════════════════════════════════

def _make_png_chunk(chunk_type, data):
    """Crée un chunk PNG valide avec CRC."""
    chunk_len = struct.pack(b'>I', len(data))
    chunk_data = chunk_type + data
    chunk_crc = struct.pack(b'>I', zlib.crc32(chunk_data) & 0xffffffff)
    return chunk_len + chunk_data + chunk_crc


def _generate_placeholder_png(width=32, height=32, r=180, g=180, b=180):
    """
    ✅ FIX #10 - Génère un PNG RGB valide de taille width x height
    en couleur gris (r,g,b) sans aucune dépendance externe.
    Compatible Python 2 et 3, IronPython.
    """
    # Signature PNG
    png_sig = b'\x89PNG\r\n\x1a\n'

    # IHDR: width, height, bit_depth=8, color_type=2 (RGB), compression=0, filter=0, interlace=0
    ihdr_data = struct.pack(b'>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr_chunk = _make_png_chunk(b'IHDR', ihdr_data)

    # IDAT: image data
    # Chaque ligne commence par un byte de filtre (0 = None)
    raw_rows = b''
    row_pixel = bytes(bytearray([r, g, b] * width))
    for _ in range(height):
        raw_rows += b'\x00' + row_pixel  # filtre 0 + pixels RGB

    compressed = zlib.compress(raw_rows, 9)
    idat_chunk = _make_png_chunk(b'IDAT', compressed)

    # IEND
    iend_chunk = _make_png_chunk(b'IEND', b'')

    return png_sig + ihdr_chunk + idat_chunk + iend_chunk


def _generate_placeholder_png_large(width=64, height=64, r=160, g=160, b=160):
    """Génère un PNG 64x64 pour icônes larges."""
    return _generate_placeholder_png(width=width, height=height, r=r, g=g, b=b)


# ══════════════════════════════════════════════════════════════════
#  YAML GENERATORS
# ══════════════════════════════════════════════════════════════════

def _generate_panel_yaml(panel_data):
    """✅ FIX #3 - YAML auto panel (sans largeur)"""
    name = _safe_str(panel_data.get('name', 'Panel'))
    description = _safe_str(panel_data.get('description', ''))
    code = _safe_str(panel_data.get('code', ''))
    author = _safe_str(panel_data.get('author', 'AutoRevit'))
    version = _safe_str(panel_data.get('version', '1.0'))

    lines = [
        u"# bundle.yaml - AUTO-GENERE PAR AUTOREVIT v4.8",
        u"# Panel : {}".format(name),
        u"",
        u'title: "{}"'.format(name),
        u'tooltip: "{}"'.format(description if description else u"Panel {}".format(name)),
    ]

    if code:
        lines.append(u"# code: {}".format(code))

    lines += [
        u"",
        u"# Metadonnees",
        u'author: "{}"'.format(author),
        u'version: "{}"'.format(version),
        u"",
    ]

    return u"\n".join(lines)


def _generate_button_yaml(btn_data):
    """✅ FIX #3 - YAML auto bouton"""
    name = _safe_str(btn_data.get('name', 'Button'))
    description = _safe_str(btn_data.get('description', ''))
    code = _safe_str(btn_data.get('code', ''))
    author = _safe_str(btn_data.get('author', 'AutoRevit'))
    version = _safe_str(btn_data.get('script_version', 1))
    icon_name = _safe_str(btn_data.get('icon', 'icon.png'))
    shortcut = _safe_str(btn_data.get('shortcut', ''))

    tooltip = description if description else u"Executer : {}".format(name)

    lines = [
        u"# bundle.yaml - AUTO-GENERE PAR AUTOREVIT v4.8",
        u"# Bouton : {}".format(name),
        u"",
        u"title: \"{}\"".format(name),
        u"tooltip: \"{}\"".format(tooltip),
    ]

    if icon_name:
        lines.append(u"icon: \"{}\"".format(icon_name))

    lines.append(u"script: \"script.py\"")

    if shortcut:
        lines.append(u"highlight_syntax: true")
        lines.append(u"shortcut: \"{}\"".format(shortcut))

    lines += [
        u"",
        u"# Metadonnees",
        u"author: \"{}\"".format(author),
        u"version: \"{}\"".format(version),
    ]

    if code:
        lines.append(u"# code_id: {}".format(code))

    lines.append(u"")
    return u"\n".join(lines)


def _generate_submenu_yaml(submenu_data):
    """✅ FIX #3 - YAML auto sous-menu"""
    name = _safe_str(submenu_data.get('name', 'Menu'))
    menu_type = _safe_str(submenu_data.get('menu_type', 'pulldown'))
    desc = _safe_str(submenu_data.get('description', ''))
    author = _safe_str(submenu_data.get('author', 'AutoRevit'))
    version = _safe_str(submenu_data.get('version', '1.0'))

    tooltip = desc if desc else u"Menu : {}".format(name)

    lines = [
        u"# bundle.yaml - AUTO-GENERE PAR AUTOREVIT v4.8",
        u"# Sous-menu : {} ({})".format(name, menu_type),
        u"",
        u"title: \"{}\"".format(name),
        u"tooltip: \"{}\"".format(tooltip),
        u"",
        u"# Metadonnees",
        u"author: \"{}\"".format(author),
        u"version: \"{}\"".format(version),
        u"",
    ]

    return u"\n".join(lines)


def _write_yaml(yaml_path, content):
    """✅ FIX #1 + FIX #3 - Écrit YAML en UTF-8"""
    try:
        with _open_utf8(yaml_path, 'w') as f:
            f.write(_safe_str(content))
        return True
    except IOError as e:
        logger.warning(u"Impossible d'ecrire YAML {} : {}".format(yaml_path, e))
        return False


# ══════════════════════════════════════════════════════════════════
#  CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════

class RibbonBuilder:
    """Construit le ruban Revit dynamiquement depuis la configuration API"""

    # Taille minimale en bytes pour considérer une icône valide
    # Un PNG 32x32 RGB valide fait ~100-300 bytes minimum après compression
    _ICON_MIN_SIZE = 500

    def __init__(self, ui_config, user_data, settings):
        self.ui_config = ui_config
        self.user_data = user_data
        self.settings  = settings

        self.extension_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.tab_dir = os.path.join(self.extension_dir, 'AutoRevit.tab')

        self.cache_dir   = os.path.join(self.extension_dir, 'cache')
        self.icons_cache = os.path.join(self.cache_dir, 'icons_source')

        for d in [self.cache_dir, self.icons_cache]:
            if not os.path.exists(d):
                os.makedirs(d)

        self._registry_file = os.path.join(self.cache_dir, '_registry.json')
        self._registry      = self._load_registry()

        logger.info(u"RibbonBuilder v4.8 initialise - user: {} role: {}".format(
            _safe_str(user_data.get('username', '?')),
            _safe_str(user_data.get('role', '?'))
        ))

    def build(self):
        """Construit la structure physique complète du ruban"""
        report = {
            'panels_created': 0,
            'scripts_written': 0,
            'scripts_cached':  0,
            'icons_copied':    0,
            'icons_placeholder': 0,
            'yamls_written':   0,
            'warnings':        []
        }

        panels = self.ui_config.get('panels', [])

        user_roles = self.user_data.get('roles', [])
        if not user_roles:
            single_role = self.user_data.get('role')
            if single_role:
                user_roles = [single_role]

        logger.info(u"Construction ruban : {} panels pour roles {}".format(
            len(panels), user_roles
        ))

        filtered_panels = [
            p for p in panels
            if self._has_permission(p.get('allowed_roles', []), user_roles)
        ]

        logger.info(u"  -> {} panels accessibles".format(len(filtered_panels)))

        for panel_data in sorted(filtered_panels, key=lambda p: p.get('order', 99)):
            try:
                self._create_panel(panel_data, user_roles, report)
            except Exception as e:
                msg = u"Erreur panel {} : {}".format(
                    _safe_str(panel_data.get('code', '?')), _safe_str(e)
                )
                logger.error(msg)
                report['warnings'].append(msg)

        self._save_registry()

        logger.info(
            u"Ruban construit : {} panels, {} scripts ecrits, "
            u"{} en cache, {} icones reelles, {} placeholders, {} YAML".format(
                report['panels_created'],
                report['scripts_written'],
                report['scripts_cached'],
                report['icons_copied'],
                report['icons_placeholder'],
                report['yamls_written'],
            )
        )

        return report

    def _create_panel(self, panel_data, user_roles, report):
        """Crée un panel et son contenu"""
        order = panel_data.get('order', 99)
        name  = _safe_str(panel_data.get('name', 'Panel'))

        panel_dirname = u"{:02d}_{}.panel".format(order, name)
        panel_path    = os.path.join(self.tab_dir, panel_dirname)

        if not os.path.exists(panel_path):
            os.makedirs(panel_path)
            logger.info(u"  Panel cree : {}".format(panel_dirname))
            report['panels_created'] += 1
        else:
            logger.info(u"  Panel existant : {}".format(panel_dirname))

        self._write_panel_yaml(panel_data, panel_path, report)

        # Icône panel (64x64 large)
        if panel_data.get('icon_large'):
            icon_dest = os.path.join(panel_path, 'icon.png')
            self._copy_icon(panel_data['icon_large'], 'icons_large', icon_dest, report, large=True)

        buttons = panel_data.get('buttons', [])
        filtered_buttons = [
            b for b in buttons
            if self._has_permission(b.get('allowed_roles', []), user_roles)
        ]
        for btn in sorted(filtered_buttons, key=lambda b: b.get('order', 99)):
            self._create_button(btn, panel_path, report)

        submenus = panel_data.get('submenus', [])
        filtered_submenus = [
            s for s in submenus
            if self._has_permission(s.get('allowed_roles', []), user_roles)
        ]
        for submenu in sorted(filtered_submenus, key=lambda s: s.get('order', 99)):
            self._create_submenu(submenu, panel_path, user_roles, report)

    def _create_submenu(self, submenu_data, parent_path, user_roles, report):
        """Crée un sous-menu (stack, pulldown ou splitbutton)"""
        menu_type = _safe_str(submenu_data.get('menu_type', 'pulldown'))
        name      = _safe_str(submenu_data.get('name', 'Menu'))

        if menu_type == 'stack':
            buttons  = submenu_data.get('buttons', [])
            children = submenu_data.get('children', [])

            filtered_buttons = [
                b for b in buttons
                if self._has_permission(b.get('allowed_roles', []), user_roles)
            ]
            total_items = len(children) + len(filtered_buttons)

            if total_items > 3:
                logger.warning(
                    u"    Stack '{}' a {} items -> division automatique en stacks de 3"
                    .format(name, total_items)
                )
                self._create_divided_stack(submenu_data, parent_path, user_roles, report)
                return

        ext_map = {
            'stack':       '.stack',
            'pulldown':    '.pulldown',
            'splitbutton': '.splitbutton',
        }
        ext = ext_map.get(menu_type, '.pulldown')

        submenu_dirname = u"{}{}".format(name, ext)
        submenu_path    = os.path.join(parent_path, submenu_dirname)

        if not os.path.exists(submenu_path):
            os.makedirs(submenu_path)
            logger.info(u"    {} cree : {}".format(menu_type.upper(), name))

        self._write_submenu_yaml(submenu_data, submenu_path, report)

        # ✅ FIX #11: Toujours créer une icône (réelle ou placeholder 32x32)
        icon_dest = os.path.join(submenu_path, 'icon.png')
        icon_name = submenu_data.get('icon', '')
        if icon_name:
            self._copy_icon(icon_name, 'icons', icon_dest, report, large=False)
        else:
            self._ensure_placeholder_icon(icon_dest, report, large=False)

        buttons = submenu_data.get('buttons', [])
        filtered_buttons = [
            b for b in buttons
            if self._has_permission(b.get('allowed_roles', []), user_roles)
        ]
        for btn in sorted(filtered_buttons, key=lambda b: b.get('order', 99)):
            self._create_button(btn, submenu_path, report)

        children = submenu_data.get('children', [])
        for child in sorted(children, key=lambda c: c.get('order', 99)):
            self._create_submenu(child, submenu_path, user_roles, report)

    def _create_divided_stack(self, submenu_data, parent_path, user_roles, report):
        """✅ FIX #2 - Divise un stack > 3 items"""
        name     = _safe_str(submenu_data.get('name', 'Menu'))
        buttons  = submenu_data.get('buttons', [])
        children = submenu_data.get('children', [])

        filtered_buttons = [
            b for b in buttons
            if self._has_permission(b.get('allowed_roles', []), user_roles)
        ]

        all_items = []
        for child in sorted(children, key=lambda c: c.get('order', 99)):
            all_items.append(('child', child))
        for btn in sorted(filtered_buttons, key=lambda b: b.get('order', 99)):
            all_items.append(('button', btn))

        total    = len(all_items)
        n_stacks = (total + 2) // 3

        for stack_idx, i in enumerate(range(0, total, 3), start=1):
            chunk = all_items[i:i + 3]

            stack_name = name if n_stacks == 1 else u"{} {}".format(name, stack_idx)
            stack_dirname = u"{}.stack".format(stack_name)
            stack_path    = os.path.join(parent_path, stack_dirname)

            if not os.path.exists(stack_path):
                os.makedirs(stack_path)

            logger.info(u"    STACK cree : {} ({}/{} items)".format(
                stack_name, len(chunk), total
            ))

            sub_data_chunk = dict(submenu_data)
            sub_data_chunk['name'] = stack_name
            self._write_submenu_yaml(sub_data_chunk, stack_path, report)

            icon_dest = os.path.join(stack_path, 'icon.png')
            icon_name = submenu_data.get('icon', '')
            if icon_name:
                self._copy_icon(icon_name, 'icons', icon_dest, report, large=False)
            else:
                self._ensure_placeholder_icon(icon_dest, report, large=False)

            for item_type, item_data in chunk:
                if item_type == 'child':
                    self._create_submenu(item_data, stack_path, user_roles, report)
                else:
                    self._create_button(item_data, stack_path, report)

    def _create_button(self, btn_data, parent_path, report):
        """Crée un bouton"""
        code        = _safe_str(btn_data.get('code', ''))
        name        = _safe_str(btn_data.get('name', 'Button'))
        script_code = _sanitize_script_text(_safe_str(btn_data.get('script_code', '')))
        version     = btn_data.get('script_version', 1)

        button_dirname = u"{}.pushbutton".format(name)
        button_path    = os.path.join(parent_path, button_dirname)

        if not os.path.exists(button_path):
            os.makedirs(button_path)

        script_path    = os.path.join(button_path, 'script.py')
        cached_version = self._registry.get(code, 0)

        if cached_version == version and os.path.exists(script_path):
            logger.debug(u"      {} : cache OK (v{})".format(code, version))
            report['scripts_cached'] += 1
        else:
            if not script_code or not script_code.strip():
                full_script = _SCRIPT_HEADER
                full_script += u'# Bouton: {} | Version: {}\n'.format(name, version)
                full_script += u'# Script vide - A completer dans Django Admin\n\n'
                full_script += u'from pyrevit import forms\n'
                full_script += u'forms.alert("Bouton \'{}\' : script non configure", title="AutoRevit")\n'.format(name)
            else:
                full_script = _SCRIPT_HEADER
                full_script += u'# Bouton: {} | Version: {}\n\n'.format(name, version)
                # PATCH AUTO - Corriger imports incorrects du serveur
                script_code = script_code.replace(
                    'from algorithms.column_placement import ColumnPlacementEngine, ColumnType',
                    'from algorithms.column_placement import ColumnPlacementEngine'
                )
                script_code = script_code.replace(
                    'from algorithms.beam_placement import BeamPlacementEngine, BeamType',
                    'from algorithms.beam_placement import BeamPlacementEngine'
                )
                script_code = script_code.replace(
                    'from algorithms.slab_placement import SlabPlacementEngine, SlabType',
                    'from algorithms.slab_placement import SlabPlacementEngine'
                )
                full_script += script_code

            try:
                with _open_utf8(script_path, 'w') as f:
                    f.write(full_script)

                self._registry[code] = version
                report['scripts_written'] += 1
                logger.info(u"      {} : script ecrit (v{})".format(name, version))

            except IOError as e:
                msg = u"Impossible d'ecrire script {} : {}".format(code, _safe_str(e))
                logger.error(msg)
                report['warnings'].append(msg)

        self._write_button_yaml(btn_data, button_path, report)

        # ✅ FIX #11: Toujours créer une icône (réelle ou placeholder 32x32)
        icon_dest = os.path.join(button_path, 'icon.png')
        icon_name = btn_data.get('icon', '')
        if icon_name:
            self._copy_icon(icon_name, 'icons', icon_dest, report, large=False)
        else:
            self._ensure_placeholder_icon(icon_dest, report, large=False)

    def _write_panel_yaml(self, panel_data, panel_path, report):
        """Écrit bundle.yaml panel"""
        yaml_path = os.path.join(panel_path, 'bundle.yaml')

        yaml_content = _safe_str(panel_data.get('yaml_content', ''))
        if not yaml_content or not yaml_content.strip():
            yaml_content = _generate_panel_yaml(panel_data)

        if _write_yaml(yaml_path, yaml_content):
            report['yamls_written'] += 1
            logger.debug(u"      bundle.yaml panel ecrit")

    def _write_button_yaml(self, btn_data, button_path, report):
        """Écrit bundle.yaml bouton"""
        yaml_path = os.path.join(button_path, 'bundle.yaml')

        if os.path.exists(yaml_path):
            return

        yaml_content = _safe_str(btn_data.get('yaml_content', ''))
        if not yaml_content or not yaml_content.strip():
            yaml_content = _generate_button_yaml(btn_data)

        if _write_yaml(yaml_path, yaml_content):
            report['yamls_written'] += 1
            logger.debug(u"      bundle.yaml bouton ecrit : {}".format(
                _safe_str(btn_data.get('name', '?'))
            ))

    def _write_submenu_yaml(self, submenu_data, submenu_path, report):
        """Écrit bundle.yaml sous-menu"""
        yaml_path = os.path.join(submenu_path, 'bundle.yaml')

        if os.path.exists(yaml_path):
            return

        yaml_content = _safe_str(submenu_data.get('yaml_content', ''))
        if not yaml_content or not yaml_content.strip():
            yaml_content = _generate_submenu_yaml(submenu_data)

        if _write_yaml(yaml_path, yaml_content):
            report['yamls_written'] += 1
            logger.debug(u"      bundle.yaml sous-menu ecrit : {}".format(
                _safe_str(submenu_data.get('name', '?'))
            ))

    def _get_urlopen(self):
        """✅ FIX #11 - urllib compatible Python 2 et 3"""
        if PY2:
            try:
                import urllib2
                return urllib2.urlopen
            except ImportError:
                pass
        # Python 3
        try:
            import urllib.request
            return urllib.request.urlopen
        except ImportError:
            pass
        # Fallback urllib2 style dans certains IronPython
        try:
            import urllib2
            return urllib2.urlopen
        except ImportError:
            return None

    def _copy_icon(self, icon_name, subfolder, dest_path, report, large=False):
        """
        ✅ FIX #6 + FIX #11 - Télécharge icône depuis API.
        Si échec, crée un placeholder PNG valide 32x32 (ou 64x64 si large=True).
        """
        icon_name = _safe_str(icon_name)

        # Vérifier si l'icône existante est valide
        if os.path.exists(dest_path):
            if os.path.getsize(dest_path) >= self._ICON_MIN_SIZE:
                logger.debug(u"      Icone deja valide : {}".format(icon_name))
                return
            else:
                logger.warning(u"      Icone invalide (trop petite), remplacement: {}".format(icon_name))
                os.remove(dest_path)

        base_url = self.settings.api_url.replace('/api/v1', '')

        urls_to_try = [
            u"{}/static/images/{}/{}".format(base_url, subfolder, icon_name),
            u"https://raw.githubusercontent.com/autorevit/Autorevit/main/static/images/{}/{}".format(
                subfolder, icon_name
            ),
        ]

        urlopen = self._get_urlopen()

        if urlopen is not None:
            for attempt, icon_url in enumerate(urls_to_try, 1):
                try:
                    logger.debug(u"      Telechargement icone ({}): {}".format(attempt, icon_url))
                    response  = urlopen(icon_url, timeout=10)
                    icon_data = response.read()

                    if len(icon_data) < self._ICON_MIN_SIZE:
                        raise ValueError(u"Icone trop petite: {} bytes".format(len(icon_data)))

                    with open(dest_path, 'wb') as f:
                        f.write(icon_data)

                    report['icons_copied'] += 1
                    logger.info(u"      Icone telechargee : {} ({} bytes)".format(
                        icon_name, len(icon_data)
                    ))
                    return

                except Exception as e:
                    logger.debug(u"      Echec {} : {}".format(icon_url, _safe_str(e)))
                    continue
        else:
            logger.warning(u"      urllib non disponible, placeholder cree pour : {}".format(icon_name))

        # Échec téléchargement → placeholder valide
        self._create_placeholder_icon(dest_path, large=large)
        report['icons_placeholder'] += 1
        logger.warning(u"      Icone introuvable, placeholder cree : {}".format(icon_name))

    def _ensure_placeholder_icon(self, dest_path, report, large=False):
        """
        ✅ FIX #11 - Crée un placeholder si l'icône n'existe pas ou est invalide.
        Appelé quand aucune icône n'est définie dans l'API.
        """
        if os.path.exists(dest_path):
            if os.path.getsize(dest_path) >= self._ICON_MIN_SIZE:
                return  # Déjà valide
            else:
                os.remove(dest_path)

        self._create_placeholder_icon(dest_path, large=large)
        report['icons_placeholder'] += 1
        logger.debug(u"      Placeholder cree : {}".format(dest_path))

    def _create_placeholder_icon(self, dest_path, large=False):
        """
        ✅ FIX #10 - Crée un PNG placeholder valide via struct+zlib.
        - Boutons normaux : 32x32 gris clair (180,180,180)
        - Icônes larges   : 64x64 gris moyen (160,160,160)
        Aucune dépendance externe requise.
        """
        try:
            if large:
                png_data = _generate_placeholder_png(width=64, height=64, r=160, g=160, b=160)
            else:
                png_data = _generate_placeholder_png(width=32, height=32, r=180, g=180, b=180)

            with open(dest_path, 'wb') as f:
                f.write(png_data)

            logger.debug(u"      Placeholder PNG {}x{} cree : {}".format(
                64 if large else 32,
                64 if large else 32,
                os.path.basename(dest_path)
            ))
        except Exception as e:
            logger.error(u"Impossible creer placeholder : {}".format(_safe_str(e)))

    def _has_permission(self, allowed_roles, user_roles):
        """Vérifie permissions"""
        if not allowed_roles:
            return True
        if 'admin' in user_roles:
            return True
        return any(role in allowed_roles for role in user_roles)

    def _load_registry(self):
        """Charge registry versions"""
        if os.path.exists(self._registry_file):
            try:
                with _open_utf8(self._registry_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(u"Impossible charger registry : {}".format(_safe_str(e)))
        return {}

    def _save_registry(self):
        """Sauvegarde registry"""
        try:
            with _open_utf8(self._registry_file, 'w') as f:
                json.dump(self._registry, f, indent=2, ensure_ascii=False)
            logger.debug(u"Registry sauvegarde ({} scripts)".format(len(self._registry)))
        except IOError as e:
            logger.error(u"Impossible sauvegarder registry : {}".format(_safe_str(e)))

    def clear_cache(self):
        """Vide cache (préserve panels fixes)"""
        logger.info(u"Vidage cache...")

        if os.path.exists(self.tab_dir):
            for item in os.listdir(self.tab_dir):
                if item.endswith('.panel'):
                    if item.startswith('00_') or item == 'Session.panel':
                        logger.debug(u"  Conserve (fixe) : {}".format(item))
                        continue

                item_path = os.path.join(self.tab_dir, item)
                if os.path.isdir(item_path):
                    try:
                        shutil.rmtree(item_path)
                        logger.info(u"  Supprime : {}".format(item))
                    except Exception as e:
                        logger.warning(u"  Impossible supprimer {} : {}".format(
                            item, _safe_str(e)
                        ))

        self._registry = {}
        self._save_registry()
        logger.info(u"Cache vide")

    def print_report(self, report=None):
        """Affiche rapport construction"""
        if report is None:
            report = self.build()

        print(u"\n" + u"=" * 60)
        print(u"RAPPORT RIBBON BUILDER v4.8")
        print(u"=" * 60)
        print(u"Panels crees       : {}".format(report['panels_created']))
        print(u"Scripts ecrits     : {}".format(report['scripts_written']))
        print(u"Scripts en cache   : {}".format(report['scripts_cached']))
        print(u"Icones reelles     : {}".format(report['icons_copied']))
        print(u"Icones placeholder : {}".format(report['icons_placeholder']))
        print(u"YAMLs generes      : {}".format(report['yamls_written']))

        if report['warnings']:
            print(u"\nAVERTISSEMENTS :")
            for w in report['warnings']:
                print(u"  . {}".format(_safe_str(w)))
        else:
            print(u"\nAucun avertissement")

        print(u"=" * 60 + u"\n")
        return report

    def get_script_path(self, button_code):
        """Retourne chemin script pour un bouton (debug)"""
        for panel_name in os.listdir(self.tab_dir):
            if not panel_name.endswith('.panel'):
                continue
            panel_path = os.path.join(self.tab_dir, panel_name)
            for item in os.listdir(panel_path):
                if item.endswith('.pushbutton'):
                    script = os.path.join(panel_path, item, 'script.py')
                    if os.path.exists(script):
                        pass  # TODO: filtrage par button_code
        return None

    # ── Compatibilité v2.0 / v3.0 / v4.0 ─────────────────────────

    def verify_structure(self):
        """Compatibilité v2.0/v3.0 - appelle build()"""
        report = self.build()
        return {
            'panels_found':    report['panels_created'],
            'buttons_found':   report['scripts_written'] + report['scripts_cached'],
            'missing_panels':  [],
            'missing_buttons': [],
            'extra_panels':    [],
            'warnings':        report['warnings'],
        }

    def generate_structure(self):
        """Compatibilité v2.0/v3.0 - DEPRECATED"""
        logger.warning(u"generate_structure() est deprecated -> utiliser build()")
        report = self.build()
        return len(report['warnings']) == 0


# ══════════════════════════════════════════════════════════════════
#  POINT D'ENTRÉE POUR TESTS
# ══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print(u"RibbonBuilder v4.8 - Test module")
    print(u"Ce module doit etre importe, pas execute directement")

    # Test génération placeholder
    test_path = '/tmp/test_placeholder.png'
    png_data = _generate_placeholder_png(32, 32)
    with open(test_path, 'wb') as f:
        f.write(png_data)
    print(u"Placeholder 32x32 genere : {} bytes -> {}".format(len(png_data), test_path))

    png_data_large = _generate_placeholder_png(64, 64)
    print(u"Placeholder 64x64 genere : {} bytes".format(len(png_data_large)))