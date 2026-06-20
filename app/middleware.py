"""
Middleware para manejar sesiones y logout automático
"""
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.contrib.auth import logout
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class SessionTimeoutMiddleware(MiddlewareMixin):
    """
    Middleware para cerrar sesión automáticamente después de inactividad.
    
    Si el usuario no realiza ninguna acción durante SESSION_TIMEOUT_SECONDS,
    la sesión expirará automáticamente.
    """
    
    def process_request(self, request):
        """Procesa cada solicitud para verificar timeout de sesión"""
        
        # Si el usuario no está autenticado, no hacer nada
        if not request.user.is_authenticated:
            return None
        
        # Obtener tiempo actual
        now = timezone.now()
        
        # Definir tiempo de inactividad (30 minutos por defecto)
        session_timeout = 1800  # segundos
        
        # Verificar última actividad guardada en sesión
        last_activity_str = request.session.get('last_activity')
        
        if last_activity_str:
            try:
                last_activity = timezone.datetime.fromisoformat(last_activity_str)
                
                # Calcular tiempo desde última actividad
                time_elapsed = (now - last_activity).total_seconds()
                
                if time_elapsed > session_timeout:
                    # Tiempo de inactividad excedido - logout
                    logger.warning(
                        f"Session timeout para usuario {request.user.username} "
                        f"tras {time_elapsed} segundos de inactividad"
                    )
                    logout(request)
                    request.session.flush()
                    return None
                
            except (ValueError, TypeError) as e:
                logger.error(f"Error procesando last_activity: {e}")
        
        # Actualizar última actividad
        request.session['last_activity'] = now.isoformat()
        
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware para agregar headers de seguridad adicionales.
    """
    
    def process_response(self, request, response):
        """Agrega headers de seguridad a cada respuesta"""
        
        # Prevenir clickjacking
        response['X-Frame-Options'] = 'DENY'
        
        # Prevenir MIME sniffing
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Habilitar XSS protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Content Security Policy básica
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' cdnjs.cloudflare.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        
        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy (Feature Policy)
        response['Permissions-Policy'] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )
        
        return response
