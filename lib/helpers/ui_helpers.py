# -*- coding: utf-8 -*-
"""
UIHelpers - Fonctions utilitaires pour l'interface utilisateur
===============================================================
Boites de dialogue, progress bars, WPF, feedback utilisateur.

Auteur : AutoRevit Team
Date : 2025
"""

import os
import sys
import webbrowser
import subprocess
from utils.logger import get_logger

logger = get_logger(__name__)

# Imports pyRevit
try:
    from pyrevit import forms
    from pyrevit import script
    PYREVIT_AVAILABLE = True
except ImportError:
    PYREVIT_AVAILABLE = False
    logger.warning("pyRevit non disponible (mode developpement)")

# Imports Revit API
try:
    from Autodesk.Revit.UI import TaskDialog, TaskDialogCommonButtons, TaskDialogResult
    from Autodesk.Revit.UI import RibbonPanel, PushButton, SplitButton, PulldownButton
    REVIT_AVAILABLE = True
except ImportError:
    REVIT_AVAILABLE = False

# Imports WPF
try:
    import clr
    clr.AddReference('PresentationFramework')
    clr.AddReference('PresentationCore')
    clr.AddReference('WindowsBase')
    clr.AddReference('System.Xaml')
    
    from System.Windows import Window, Application
    from System.Windows.Markup import XamlReader
    from System.IO import FileStream, StreamReader, MemoryStream
    from System.Text import Encoding
    WPF_AVAILABLE = True
except:
    WPF_AVAILABLE = False


# ========================================================================
# BOITES DE DIALOGUE SIMPLES
# ========================================================================

def show_message_box(message, title="AutoRevit", icon="Information"):
    """
    Affiche une boite de message simple.
    
    Args:
        message (str): Message
        title (str): Titre
        icon (str): Icone (Information, Warning, Error, Question)
    
    Returns:
        bool: True si OK
    """
    return alert(message, title=title, icon=icon)


def show_task_dialog(message, title="AutoRevit", icon="Information"):
    """
    Affiche un TaskDialog Revit ou une alerte de fallback.
    
    Args:
        message (str): Message
        title (str): Titre
        icon (str): Icone
    
    Returns:
        bool: True si OK
    """
    if REVIT_AVAILABLE:
        try:
            td = TaskDialog(title)
            td.MainContent = message
            td.CommonButtons = TaskDialogCommonButtons.Ok
            result = td.Show()
            return result == TaskDialogResult.Ok
        except:
            pass
    return alert(message, title=title, icon=icon)


def show_error_dialog(message, title="Erreur"):
    """Affiche une boite d'erreur."""
    return alert(message, title=title, icon="Error", warn_icon=True)


def show_warning_dialog(message, title="Attention"):
    """Affiche un avertissement."""
    return alert(message, title=title, icon="Warning", warn_icon=True)


def show_info_dialog(message, title="Information"):
    """Affiche une information."""
    return alert(message, title=title, icon="Information", warn_icon=False)


def show_question_dialog(message, title="Confirmation"):
    """Affiche une question Yes/No."""
    return confirm(message, title=title)


# ========================================================================
# FONCTIONS PYREVIT
# ========================================================================

def alert(message, title="AutoRevit", icon="Information", warn_icon=False, cancel=False):
    """
    Affiche une alerte.
    
    Args:
        message (str): Message
        title (str): Titre
        icon (str): Icone
        warn_icon (bool): Utiliser icone warning
        cancel (bool): Ajouter bouton Cancel
    
    Returns:
        bool: True si OK/Yes
    """
    if PYREVIT_AVAILABLE:
        try:
            return forms.alert(
                message,
                title=title,
                warn_icon=warn_icon or icon in ['Warning', 'Error'],
                cancel=cancel
            )
        except:
            pass
    
    # Fallback
    print(title + ": " + message)
    return True


def confirm(message, title="Confirmation", cancel=False):
    """
    Affiche une confirmation Yes/No.
    
    Args:
        message (str): Message
        title (str): Titre
        cancel (bool): Ajouter bouton Cancel
    
    Returns:
        bool: True si Yes
    """
    if PYREVIT_AVAILABLE:
        try:
            return forms.alert(
                message,
                title=title,
                yes=True,
                no=True,
                cancel=cancel
            )
        except:
            pass
    
    # Fallback
    print(title + ": " + message + " (y/n)")
    response = raw_input().lower()
    return response.startswith('y')


def prompt_for_string(prompt, title="AutoRevit", default=""):
    """
    Demande une saisie texte.
    
    Args:
        prompt (str): Message
        title (str): Titre
        default (str): Valeur par defaut
    
    Returns:
        str: Valeur saisie ou None
    """
    if PYREVIT_AVAILABLE:
        try:
            return forms.ask_for_string(
                prompt=prompt,
                title=title,
                default=default
            )
        except:
            pass
    
    # Fallback
    print(title + ": " + prompt)
    print("Defaut: " + default)
    value = raw_input()
    return value if value else default


def prompt_for_integer(prompt, title="AutoRevit", default=None, min=None, max=None):
    """
    Demande un entier.
    
    Args:
        prompt (str): Message
        title (str): Titre
        default (int): Valeur par defaut
        min (int): Valeur minimale
        max (int): Valeur maximale
    
    Returns:
        int: Valeur saisie ou None
    """
    if PYREVIT_AVAILABLE:
        try:
            return forms.ask_for_integer(
                prompt=prompt,
                title=title,
                default=default,
                min=min,
                max=max
            )
        except:
            pass
    
    # Fallback
    print(title + ": " + prompt)
    if default is not None:
        print("Defaut: " + str(default))
    
    try:
        value = int(raw_input())
        return value
    except:
        return default


def prompt_for_float(prompt, title="AutoRevit", default=None, min=None, max=None):
    """
    Demande un flottant.
    
    Args:
        prompt (str): Message
        title (str): Titre
        default (float): Valeur par defaut
        min (float): Valeur minimale
        max (float): Valeur maximale
    
    Returns:
        float: Valeur saisie ou None
    """
    if PYREVIT_AVAILABLE:
        try:
            return forms.ask_for_real(
                prompt=prompt,
                title=title,
                default=default,
                min=min,
                max=max
            )
        except:
            pass
    
    # Fallback
    print(title + ": " + prompt)
    if default is not None:
        print("Defaut: " + str(default))
    
    try:
        value = float(raw_input())
        return value
    except:
        return default


def select_from_list(options, title="Selection", button_name="OK", multiselect=False, width=400, height=300):
    """
    Selection dans une liste.
    
    Args:
        options (list): Options
        title (str): Titre
        button_name (str): Texte bouton
        multiselect (bool): Selection multiple
        width (int): Largeur
        height (int): Hauteur
    
    Returns:
        list/str: Selection(s)
    """
    if PYREVIT_AVAILABLE and options:
        try:
            return forms.SelectFromList.show(
                options,
                title=title,
                button_name=button_name,
                multiselect=multiselect,
                width=width,
                height=height
            )
        except:
            pass
    
    # Fallback
    print(title)
    for i, opt in enumerate(options):
        print("  " + str(i+1) + ". " + str(opt))
    
    if multiselect:
        print("Entrez les numeros separes par des virgules:")
        try:
            indices = raw_input().split(',')
            selected = []
            for idx in indices:
                i = int(idx.strip()) - 1
                if 0 <= i < len(options):
                    selected.append(options[i])
            return selected
        except:
            return []
    else:
        print("Entrez le numero:")
        try:
            i = int(raw_input()) - 1
            if 0 <= i < len(options):
                return [options[i]]
        except:
            pass
        return None


def select_from_dict(options_dict, title="Selection", button_name="OK"):
    """
    Selection dans un dictionnaire.
    
    Args:
        options_dict (dict): {cle: valeur}
        title (str): Titre
        button_name (str): Texte bouton
    
    Returns:
        tuple: (cle, valeur) selectionne
    """
    if PYREVIT_AVAILABLE and options_dict:
        try:
            return forms.SelectFromList.show(
                options_dict,
                title=title,
                button_name=button_name
            )
        except:
            pass
    
    # Fallback
    keys = list(options_dict.keys())
    selected = select_from_list(keys, title, button_name, multiselect=False)
    if selected and selected[0] in options_dict:
        return (selected[0], options_dict[selected[0]])
    return None


# ========================================================================
# PROGRESS BAR
# ========================================================================

class ProgressBar:
    """
    Barre de progression.
    
    Exemple:
    >>> with ProgressBar("Traitement...", 100) as pb:
    >>>     for i in range(100):
    >>>         pb.update(i + 1)
    >>>         pb.message("Etape " + str(i + 1))
    """
    
    def __init__(self, title="Progression", max_value=100, cancellable=True):
        """
        Initialise la barre de progression.
        
        Args:
            title (str): Titre
            max_value (int): Valeur maximale
            cancellable (bool): Annulable
        """
        self.title = title
        self.max_value = max_value
        self.cancellable = cancellable
        self.current_value = 0
        self.cancelled = False
        self.progress_bar = None
        
        if PYREVIT_AVAILABLE:
            try:
                from pyrevit.forms import ProgressBar as PyRevitProgressBar
                self.progress_bar = PyRevitProgressBar(
                    title=title,
                    cancellable=cancellable
                )
            except:
                pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.progress_bar:
            self.progress_bar.Close()
        return False
    
    def update(self, value, msg=None):
        """
        Met a jour la progression.
        
        Args:
            value (int): Nouvelle valeur
            msg (str): Message
        """
        self.current_value = value
        
        if self.progress_bar:
            try:
                if msg:
                    self.progress_bar.update_progress(value, self.max_value, msg)
                else:
                    self.progress_bar.update_progress(value, self.max_value)
            except:
                pass
        else:
            # Fallback console
            percent = int((value / float(self.max_value)) * 100)
            bar = '#' * (percent // 5) + '-' * (20 - percent // 5)
            sys.stdout.write('\r[{}] {}% - {}'.format(bar, percent, msg or ''))
            sys.stdout.flush()
    
    def message(self, msg):
        """Affiche un message."""
        self.update(self.current_value, msg)
    
    def increment(self, step=1, msg=None):
        """Incremente la progression."""
        self.update(self.current_value + step, msg)
    
    def is_cancelled(self):
        """Verifie si annulation demandee."""
        if self.progress_bar and self.cancellable:
            try:
                return self.progress_bar.cancelled
            except:
                pass
        return False


def with_progress(title=None, cancellable=True):
    """
    Decorateur pour afficher une barre de progression.
    
    Args:
        title (str): Titre
        cancellable (bool): Annulable
    
    Exemple:
    >>> @with_progress("Creation poteaux")
    >>> def create_columns(progress):
    >>>     for i in range(100):
    >>>         if progress.is_cancelled():
    >>>             break
    >>>         progress.update(i + 1, "Poteau " + str(i + 1))
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            progress_title = title or func.__name__.replace('_', ' ').title()
            with ProgressBar(progress_title, 100, cancellable) as pb:
                kwargs['progress'] = pb
                return func(*args, **kwargs)
        return wrapper
    return decorator


# ========================================================================
# WPF WINDOWS
# ========================================================================

def create_wpf_window(xaml_string):
    """
    Cree une fenetre WPF a partir de XAML.
    
    Args:
        xaml_string (str): XAML string
    
    Returns:
        Window: Fenetre WPF
    """
    if not WPF_AVAILABLE:
        logger.error("WPF non disponible")
        return None
    
    try:
        stream = MemoryStream(Encoding.UTF8.GetBytes(xaml_string))
        return XamlReader.Load(stream)
    except Exception as e:
        logger.error("Erreur create_wpf_window: " + str(e))
        return None


def load_wpf_window(xaml_file):
    """
    Charge une fenetre WPF depuis un fichier XAML.
    
    Args:
        xaml_file (str): Chemin fichier XAML
    
    Returns:
        Window: Fenetre WPF
    """
    if not WPF_AVAILABLE:
        logger.error("WPF non disponible")
        return None
    
    try:
        with open(xaml_file, 'r') as f:
            xaml = f.read()
        return create_wpf_window(xaml)
    except Exception as e:
        logger.error("Erreur load_wpf_window: " + str(e))
        return None


class WPFWindow:
    """
    Wrapper pour fenetre WPF pyRevit.
    
    Exemple:
    >>> wpf = WPFWindow('Interface.xaml')
    >>> wpf.show()
    """
    
    def __init__(self, xaml_file_or_string):
        """
        Initialise la fenetre WPF.
        
        Args:
            xaml_file_or_string: Chemin fichier ou XAML string
        """
        self.window = None
        
        if PYREVIT_AVAILABLE:
            try:
                from pyrevit.forms import WPFWindow as PyRevitWPFWindow
                self.window = PyRevitWPFWindow(xaml_file_or_string)
            except:
                pass
        
        if not self.window and WPF_AVAILABLE:
            if os.path.isfile(xaml_file_or_string):
                self.window = load_wpf_window(xaml_file_or_string)
            else:
                self.window = create_wpf_window(xaml_file_or_string)
    
    def show(self):
        """Affiche la fenetre."""
        if self.window:
            if PYREVIT_AVAILABLE and hasattr(self.window, 'show_dialog'):
                self.window.show_dialog()
            else:
                self.window.ShowDialog()
    
    def close(self):
        """Ferme la fenetre."""
        if self.window:
            self.window.Close()
    
    def find_element(self, name):
        """
        Trouve un element par nom.
        
        Args:
            name (str): Nom de l'element
        
        Returns:
            FrameworkElement: Element trouve
        """
        if self.window:
            return self.window.FindName(name)
        return None
    
    def __getattr__(self, name):
        """Acces direct aux elements."""
        if self.window:
            element = self.find_element(name)
            if element:
                return element
        raise AttributeError(name)


# ========================================================================
# FEEDBACK UTILISATEUR
# ========================================================================

def show_toast(message, title="AutoRevit", duration=3):
    """
    Affiche une notification toast (Windows 10+).
    
    Args:
        message (str): Message
        title (str): Titre
        duration (int): Duree en secondes
    """
    try:
        from pyrevit import userutil
        userutil.show_toast(title, message, duration=duration)
    except:
        # Fallback
        print(title + ": " + message)


def show_balloon_tip(message, title="AutoRevit", icon=0):
    """
    Affiche une bulle d'information (Revit).
    
    Args:
        message (str): Message
        title (str): Titre
        icon (int): 0=Info, 1=Warning, 2=Error
    """
    try:
        from pyrevit import revit
        uidoc = revit.uidoc
        if uidoc:
            uidoc.Application.ShowBalloonTip(title, message, icon)
    except:
        pass


def open_url(url):
    """
    Ouvre une URL dans le navigateur par defaut.
    
    Args:
        url (str): URL
    """
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.error("Erreur open_url: " + str(e))


def copy_to_clipboard(text):
    """
    Copie du texte dans le presse-papiers.
    
    Args:
        text (str): Texte a copier
    """
    try:
        from pyrevit import userutil
        userutil.set_clipboard(text)
    except:
        try:
            import subprocess
            cmd = 'echo ' + text.strip() + '| clip'
            subprocess.check_call(cmd, shell=True)
        except:
            pass


def show_in_explorer(path):
    """
    Ouvre le dossier dans l'explorateur Windows.
    
    Args:
        path (str): Chemin du dossier/fichier
    """
    try:
        if os.path.exists(path):
            subprocess.Popen(r'explorer /select,"' + path + '"')
    except Exception as e:
        logger.error("Erreur show_in_explorer: " + str(e))


def get_output_window():
    """
    Recupere la fenetre de sortie pyRevit.
    
    Returns:
        OutputWindow: Fenetre de sortie
    """
    if PYREVIT_AVAILABLE:
        try:
            return script.get_output()
        except:
            pass
    
    # Fallback - "print" est un mot-cle en IronPython 2,
    # on utilise print_text a la place
    class DummyOutput:
        def print_text(self, text):
            print(text)
        
        def print_md(self, text):
            print(text)
    
    return DummyOutput()


# ========================================================================
# FONCTION DE TEST
# ========================================================================

def test_ui_helpers():
    print("\n" + "="*60)
    print("TEST UI HELPERS")
    print("="*60)
    
    print("\n1 Alertes:")
    show_info_dialog("Test information", "Test")
    print("   Info dialog OK")
    
    print("\n2 Selection:")
    options = ["Option 1", "Option 2", "Option 3"]
    selected = select_from_list(options, "Test selection", "Choisir")
    print("   Selection: " + str(selected))
    
    print("\n3 Saisie:")
    value = prompt_for_string("Test saisie", "Test", "defaut")
    print("   Saisie: " + str(value))
    
    print("\n4 Progress bar:")
    with ProgressBar("Test", 10) as pb:
        for i in range(10):
            pb.update(i + 1, "Etape " + str(i + 1))
    print("   Progress OK")
    
    print("\n" + "="*60)
    print("TEST TERMINE")
    print("="*60 + "\n")


if __name__ == '__main__':
    test_ui_helpers()