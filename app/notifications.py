"""
🔔 Utilitaire de notifications desktop avec plyer
Support: Linux, macOS, Windows
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Import conditionnel de plyer (peut ne pas être disponible sur tous les systèmes)
try:
    from plyer import notification as plyer_notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    logger.warning("⚠️ plyer not installed. Desktop notifications disabled.")


def show_notification(
    title: str,
    message: str,
    timeout: int = 5,
    notification_type: str = 'info'
) -> bool:
    """
    Affiche une notification desktop.
    
    Args:
        title: Titre de la notification
        message: Message de la notification
        timeout: Durée d'affichage en secondes (défaut: 5)
        notification_type: Type ('info', 'success', 'error', 'warning')
    
    Returns:
        True si succès, False sinon
    
    Exemple:
        show_notification(
            title="Connexion réussie",
            message="Bienvenue sur UniMarket!",
            notification_type='success'
        )
    """
    if not PLYER_AVAILABLE:
        logger.debug(f"[NOTIFICATION] {title}: {message}")
        return False
    
    try:
        # Mapper les types aux icônes (pour certains OS)
        icon_map = {
            'info': 'dialog-information',
            'success': 'dialog-ok',
            'error': 'dialog-error',
            'warning': 'dialog-warning',
        }
        
        # Ajouter un préfixe au titre selon le type
        type_prefix = {
            'info': 'ℹ️',
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
        }
        
        full_title = f"{type_prefix.get(notification_type, '')} {title}".strip()
        
        plyer_notification.notify(
            title=full_title,
            message=message,
            timeout=timeout,
            app_name='UniMarket',
        )
        
        logger.info(f"✓ Notification affichée: {full_title}")
        return True
    
    except Exception as e:
        logger.error(f"❌ Erreur notification: {str(e)}")
        return False


def notify_login_success(user_email: str, user_name: str = "") -> None:
    """Notification de connexion réussie"""
    name = user_name or user_email.split('@')[0]
    show_notification(
        title="Connexion réussie",
        message=f"Bienvenue {name}! 👋",
        notification_type='success'
    )


def notify_login_failed(reason: str = "Email ou mot de passe incorrect") -> None:
    """Notification d'échec de connexion"""
    show_notification(
        title="Connexion échouée",
        message=reason,
        notification_type='error'
    )


def notify_signup_success(user_name: str) -> None:
    """Notification d'inscription réussie"""
    show_notification(
        title="Inscription réussie",
        message=f"Compte créé pour {user_name}! 🎉",
        notification_type='success'
    )


def notify_upload_success(filename: str) -> None:
    """Notification d'upload réussi"""
    show_notification(
        title="Upload réussi",
        message=f"Document '{filename}' uploadé! 📄",
        notification_type='success'
    )


def notify_upload_failed(reason: str) -> None:
    """Notification d'échec d'upload"""
    show_notification(
        title="Upload échoué",
        message=reason,
        notification_type='error'
    )


def notify_profile_updated(field_name: str) -> None:
    """Notification de profil mis à jour"""
    show_notification(
        title="Profil mis à jour",
        message=f"{field_name} a été enregistré! ✓",
        notification_type='success'
    )


def notify_rate_limit_exceeded(action: str) -> None:
    """Notification de limite atteinte"""
    show_notification(
        title="Trop de tentatives",
        message=f"Limite d'{action} dépassée. Réessayez plus tard.",
        notification_type='warning',
        timeout=10
    )


def notify_error(title: str, message: str) -> None:
    """Notification d'erreur générique"""
    show_notification(
        title=title,
        message=message,
        notification_type='error',
        timeout=8
    )


def notify_info(title: str, message: str) -> None:
    """Notification d'info générique"""
    show_notification(
        title=title,
        message=message,
        notification_type='info',
        timeout=5
    )
