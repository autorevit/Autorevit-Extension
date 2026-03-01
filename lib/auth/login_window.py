# -*- coding: utf-8 -*-
"""
Fenêtre WPF de connexion AutoRevit - VERSION CORRIGÉE
✅ CORRECTION: Vérifie 'access' (JWT) au lieu de 'session_token'
"""
import os
import sys
import socket

from config.settings  import Settings
from config.api_client import APIClient
from utils.logger      import get_logger

logger = get_logger('autorevit.login')


# ── XAML de la fenêtre de login ───────────────────────────────────
LOGIN_XAML = """
<Window
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
    Title="AutoRevit - Connexion"
    Width="400" Height="300"
    WindowStartupLocation="CenterScreen"
    ResizeMode="NoResize"
    Background="#1E2A3A">

    <Window.Resources>
        <Style x:Key="InputStyle" TargetType="TextBox">
            <Setter Property="Background" Value="#2D3E50"/>
            <Setter Property="Foreground" Value="White"/>
            <Setter Property="BorderBrush" Value="#4A90D9"/>
            <Setter Property="BorderThickness" Value="1"/>
            <Setter Property="Padding" Value="8,6"/>
            <Setter Property="FontSize" Value="13"/>
            <Setter Property="Height" Value="36"/>
        </Style>
        <Style x:Key="PassStyle" TargetType="PasswordBox">
            <Setter Property="Background" Value="#2D3E50"/>
            <Setter Property="Foreground" Value="White"/>
            <Setter Property="BorderBrush" Value="#4A90D9"/>
            <Setter Property="BorderThickness" Value="1"/>
            <Setter Property="Padding" Value="8,6"/>
            <Setter Property="FontSize" Value="13"/>
            <Setter Property="Height" Value="36"/>
        </Style>
        <Style x:Key="BtnStyle" TargetType="Button">
            <Setter Property="Background" Value="#4A90D9"/>
            <Setter Property="Foreground" Value="White"/>
            <Setter Property="FontSize" Value="14"/>
            <Setter Property="FontWeight" Value="Bold"/>
            <Setter Property="Height" Value="40"/>
            <Setter Property="BorderThickness" Value="0"/>
            <Setter Property="Cursor" Value="Hand"/>
        </Style>
    </Window.Resources>

    <Grid Margin="30">
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="20"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="10"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="10"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="10"/>
            <RowDefinition Height="Auto"/>
            <RowDefinition Height="Auto"/>
        </Grid.RowDefinitions>

        <!-- Logo / Titre -->
        <TextBlock Grid.Row="0" Text="AutoRevit" FontSize="26" FontWeight="Bold"
                   Foreground="#4A90D9" HorizontalAlignment="Center"/>

        <!-- Champ Utilisateur -->
        <TextBlock Grid.Row="2" Text="Nom d'utilisateur" Foreground="#AAB8C2" FontSize="11" Margin="0,0,0,4"/>
        <TextBox   Grid.Row="2" Name="UsernameInput" Style="{StaticResource InputStyle}"
                   VerticalAlignment="Bottom"/>

        <!-- Champ Mot de passe -->
        <TextBlock Grid.Row="4" Text="Mot de passe" Foreground="#AAB8C2" FontSize="11" Margin="0,0,0,4"/>
        <PasswordBox Grid.Row="4" Name="PasswordInput" Style="{StaticResource PassStyle}"
                     VerticalAlignment="Bottom"/>

        <!-- Message d'erreur -->
        <TextBlock Grid.Row="6" Name="ErrorMsg" Foreground="#E74C3C"
                   FontSize="11" TextWrapping="Wrap" Visibility="Collapsed"/>

        <!-- Bouton Connexion -->
        <Button Grid.Row="8" Name="LoginBtn" Content="Se connecter"
                Style="{StaticResource BtnStyle}"/>

        <!-- Version -->
        <TextBlock Grid.Row="9" Text="v1.0 - AutoRevit BIM" Foreground="#4A6070"
                   FontSize="10" HorizontalAlignment="Center" Margin="0,8,0,0"/>
    </Grid>
</Window>
"""


def show_login_window():
    """
    Affiche la fenêtre de login et retourne les données de session si succès.
    Retourne None si l'utilisateur annule.
    
    Returns:
        dict | None : Réponse complète du login (access, refresh, user, ...)
    """
    try:
        import clr
        clr.AddReference('PresentationFramework')
        clr.AddReference('PresentationCore')
        from System.Windows       import Window, Visibility
        from System.Windows.Markup import XamlReader

        # Charger le XAML
        win = XamlReader.Parse(LOGIN_XAML)

        login_result = [None]  # Liste pour contourner la closure Python

        def on_login_click(sender, e):
            username = win.FindName('UsernameInput').Text.strip()
            password = win.FindName('PasswordInput').Password.strip()
            error_block = win.FindName('ErrorMsg')

            if not username or not password:
                error_block.Text       = "Veuillez renseigner tous les champs."
                error_block.Visibility = Visibility.Visible
                return

            # Créer APIClient (sans JWT token)
            settings = Settings()
            client = APIClient(settings)
            
            # Appel API login
            try:
                result = client.login(
                    username, 
                    password,
                    revit_version=_get_revit_version(),
                    machine_name=socket.gethostname()
                )

                # ✅ CORRECTION: Vérifier 'access' (JWT) au lieu de 'session_token'
                if result and result.get('access'):
                    login_result[0] = result
                    win.Close()
                else:
                    error_block.Text       = "Identifiants incorrects. Réessayez."
                    error_block.Visibility = Visibility.Visible
                    logger.warning("Tentative login echouee pour : {}".format(username))
                    
            except Exception as e:
                error_block.Text       = "Erreur : {}".format(str(e))
                error_block.Visibility = Visibility.Visible
                logger.error("Erreur login : {}".format(e))

        # Relier le bouton
        btn = win.FindName('LoginBtn')
        btn.Click += on_login_click

        # Afficher en modal
        win.ShowDialog()

        return login_result[0]

    except Exception as e:
        logger.error("Erreur fenetre login : {}".format(e))
        # Fallback : login via formulaire pyRevit simple
        return _fallback_login()


def _fallback_login():
    """
    Fallback si WPF ne fonctionne pas.
    Utilise les formulaires natifs pyRevit.
    """
    try:
        from pyrevit import forms

        username = forms.ask_for_string(
            default='',
            prompt='Nom d\'utilisateur AutoRevit :',
            title='AutoRevit - Connexion'
        )
        if not username:
            return None

        password = forms.ask_for_string(
            default='',
            prompt='Mot de passe :',
            title='AutoRevit - Connexion'
        )
        if not password:
            return None

        # Créer APIClient (sans JWT token)
        settings = Settings()
        client = APIClient(settings)
        
        result = client.login(
            username, 
            password,
            revit_version=_get_revit_version(),
            machine_name=socket.gethostname()
        )

        # ✅ CORRECTION: Vérifier 'access' (JWT) au lieu de 'session_token'
        if result and result.get('access'):
            return result
        else:
            forms.alert("Identifiants incorrects.", title="AutoRevit")
            return None

    except Exception as e:
        logger.error("Erreur fallback login : {}".format(e))
        return None


def _get_revit_version():
    """Récupère la version de Revit"""
    try:
        from pyrevit import HOST_APP
        return str(HOST_APP.version)
    except Exception:
        return 'unknown'