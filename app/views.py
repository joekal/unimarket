from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, authenticate, login as auth_login
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Count, Avg, Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.utils.html import escape
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.core.cache import cache
from app.models import StudentProfile, Listing, ListingImage, UploadedFile, Review, Category, NewsletterSubscription
from app.notifications import (
    notify_login_success, notify_login_failed,
    notify_signup_success, notify_upload_success, notify_upload_failed,
    notify_profile_updated, notify_rate_limit_exceeded, notify_error
)
import json
import logging
import uuid
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from django.core.files.base import ContentFile
import os

logger = logging.getLogger(__name__)

# Configuration de sécurité
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
ALLOWED_DOCUMENT_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain'
}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50MB

# ======================================================================
# HELPER FUNCTIONS - SÉCURITÉ ET VALIDATION
# ======================================================================

def sanitize_input(value, max_length=None):
    """Sanitize user input to prevent XSS"""
    if not value:
        return ""
    value = escape(str(value).strip())
    if max_length:
        value = value[:max_length]
    return value


def validate_email(email):
    """Valider format d'email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password):
    """Valider force du mot de passe"""
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères"
    if not any(char.isdigit() for char in password):
        return False, "Le mot de passe doit contenir au moins un chiffre"
    if not any(char.isupper() for char in password):
        return False, "Le mot de passe doit contenir au moins une majuscule"
    return True, "OK"


def rate_limit_check(request, action, limit=10, window=3600):
    """Simple rate limiting (dans un projet réel, utiliser redis)"""
    key = f"ratelimit:{request.META.get('REMOTE_ADDR')}:{action}"
    count = cache.get(key, 0)
    if count >= limit:
        return False
    cache.set(key, count + 1, window)
    return True


def is_safe_redirect_url(url, request):
    """Valide que l'URL de redirection est sûre (prévient open redirect)"""
    if not url or not isinstance(url, str):
        return False
    
    # Rejeter les URL absolues
    if url.startswith(('http://', 'https://', '//')):
        return False
    
    # Vérifier que l'URL commence par /
    if not url.startswith('/'):
        return False
    
    # Vérifier que l'URL n'est pas trop longue (prévient les attaques buffer overflow)
    if len(url) > 200:
        return False
    
    # Liste blanche des redirections autorisées
    allowed_paths = ['/', '/profile', '/posts', '/search', '/services', '/about', '/contact', '/dashboard']
    
    # Vérifier que le chemin commence par un chemin autorisé ou est un chemin autorisé
    return any(url.startswith(path) for path in allowed_paths)


def validate_file_type(uploaded_file, allowed_types):
    """Valide le type MIME du fichier"""
    if not hasattr(uploaded_file, 'content_type'):
        return False, "Type de fichier non détecté"
    
    file_type = uploaded_file.content_type.lower()
    
    # Vérifier l'extension aussi (ne pas faire confiance au content-type seul)
    filename_lower = uploaded_file.name.lower()
    
    # Extensions autorisées selon le type
    extension_map = {
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/webp': ['.webp'],
        'application/pdf': ['.pdf'],
        'application/msword': ['.doc'],
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
        'application/vnd.ms-excel': ['.xls'],
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
        'text/plain': ['.txt'],
    }
    
    if file_type not in allowed_types:
        return False, f"Type de fichier non autorisé: {file_type}"
    
    # Vérifier l'extension
    valid_extensions = extension_map.get(file_type, [])
    has_valid_extension = any(filename_lower.endswith(ext) for ext in valid_extensions)
    
    if not has_valid_extension:
        return False, "Extension de fichier invalide"
    
    return True, "OK"


def sanitize_filename(filename):
    """Nettoie le nom de fichier (prévient directory traversal)"""
    import os
    # Garder seulement le nom de fichier, pas le chemin
    filename = os.path.basename(filename)
    # Supprimer les caractères dangereux
    filename = re.sub(r'[^\w\s.-]', '', filename)
    # Remplacer les espaces multiples
    filename = re.sub(r'\s+', '_', filename)
    return filename


def generate_unique_slug(model, value):
    """Génère un slug unique pour un modèle Django."""
    base_slug = slugify(value)
    slug = base_slug
    counter = 1
    while model.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def log_security_event(request, event_type, details=""):
    """Log les événements de sécurité"""
    ip = request.META.get('REMOTE_ADDR', 'UNKNOWN')
    user = request.user.email if request.user.is_authenticated else 'ANONYMOUS'
    logger.warning(f"[SECURITY] {event_type} | User: {user} | IP: {ip} | {details}")


def generate_avatar_with_initials(first_name, last_name):
    """Génère une image avatar avec les initiales du nom et prénom"""
    try:
        # Obtenir les initiales
        initials = f"{first_name[0]}{last_name[0]}".upper() if first_name and last_name else "???"
        
        # Convertir les couleurs hex en RGB
        # #fec89a = or VaultEdge, #3d3d3d = dark VaultEdge
        bg_color = (254, 200, 154)  # OR (#fec89a)
        text_color = (61, 61, 61)   # DARK (#3d3d3d)
        
        # Créer une image 200x200 avec le thème VaultEdge
        img = Image.new('RGB', (200, 200), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        # Essayer de charger une police, sinon utiliser la police par défaut
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
        except:
            font = ImageFont.load_default()
        
        # Dessiner les initiales au centre
        bbox = draw.textbbox((0, 0), initials, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        position = (
            (200 - text_width) // 2,
            (200 - text_height) // 2
        )
        
        draw.text(position, initials, fill=text_color, font=font)
        
        # Convertir en bytes
        img_io = BytesIO()
        img.save(img_io, format='JPEG', quality=90)
        img_io.seek(0)
        
        return ContentFile(img_io.read(), name=f'avatar_{first_name}_{last_name}.jpg')
    
    except Exception as e:
        logger.error(f"Erreur lors de la génération d'avatar: {str(e)}")
        return None


def create_user_profile_automatically(user):
    """Crée automatiquement un profil StudentProfile pour un nouvel utilisateur"""
    try:
        # Vérifier si le profil existe déjà
        profile, created = StudentProfile.objects.get_or_create(user=user)
        
        if created:
            # Générer l'avatar avec les initiales
            avatar = generate_avatar_with_initials(user.first_name, user.last_name)
            if avatar:
                profile.profile_picture = avatar
            
            # Autres infos par défaut
            profile.university = 'UPC'
            profile.specialty = 'INFORMATIQUE'
            profile.promotion = ''
            profile.phone = ''
            profile.bio = ''
            profile.rating = 5.0
            profile.is_active = True
            profile.save()
            
            logger.info(f"✓ Profil créé automatiquement pour: {user.email}")
            return profile, True
        
        return profile, False
    
    except Exception as e:
        logger.error(f"Erreur lors de la création du profil automatique: {str(e)}")
        return None, False


# ======================================================================
# VUE PAGES PUBLIQUES
# ======================================================================

def index(request):
    """Vue pour la page d'accueil avec données dynamiques"""
    try:
        # Stats générales
        total_listings = Listing.objects.filter(status='ACTIVE').count()
        total_users = User.objects.filter(is_active=True).count()
        avg_rating = StudentProfile.objects.aggregate(avg=Avg('rating'))['avg'] or 5.0
        total_reviews = Review.objects.count()
        
        # Catégories de services
        categories = Category.objects.filter(is_active=True).order_by('order')[:7]
        
        # Facultés/Spécialités avec comptage
        specialties = [
            ('THEOLOGIE', 'Théologie'),
            ('MEDECINE', 'Médecine'),
            ('DROIT', 'Droit'),
            ('ECONOMIE', 'Économie'),
            ('INFORMATIQUE', 'Sciences Informatiques'),
        ]
        specialty_stats = []
        for code, name in specialties:
            count = StudentProfile.objects.filter(specialty=code).count()
            specialty_stats.append({
                'name': name,
                'code': code,
                'count': count
            })
        
        # Témoignages (Reviews)
        testimonials = Review.objects.select_related(
            'reviewer', 'reviewer__user'
        ).filter(
            is_verified_buyer=True
        ).order_by('-created_at')[:6]
        
        # Derniers documents publics
        recent_posts = UploadedFile.objects.filter(
            category='EXAM',
            is_public=True
        ).select_related('uploader', 'uploader__user').order_by('-created_at')[:3]

        # Derniers listings (services/annonces) à afficher sur la page d'accueil
        recent_listings = Listing.objects.filter(
            status='ACTIVE',
            is_active=True
        ).select_related('seller', 'seller__user', 'category').only(
            'id', 'title', 'slug', 'image', 'seller_id', 'category_id', 'created_at', 'description'
        ).order_by('-created_at')[:3]
        
        context = {
            'page_title': 'Accueil - UniMarket',
            'total_listings': total_listings,
            'total_users': total_users,
            'avg_rating': round(avg_rating, 1),
            'total_reviews': total_reviews,
            'faculty_count': len(specialty_stats),
            'categories': categories,
            'specialties': specialty_stats,
            'testimonials': testimonials,
            'recent_posts': recent_posts,
            'recent_listings': recent_listings,
        }
        return render(request, 'app/index.html', context)
    
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Erreur dans index: {str(e)}")
        logger.error(tb)
        context = {
            'page_title': 'Accueil - UniMarket',
            'error': 'Erreur lors du chargement de la page'
        }
        return render(request, 'app/index.html', context, status=500)


def about(request):
    """Vue pour la page À propos"""
    categories = Category.objects.filter(is_active=True).order_by('order')
    context = {
        'page_title': 'À propos - UniMarket',
        'total_users': User.objects.filter(is_active=True).count(),
        'total_listings': Listing.objects.filter(status='ACTIVE').count(),
        'categories': categories,
    }
    return render(request, 'app/about.html', context)


def services(request):
    """Vue pour la page Services"""
    categories = Category.objects.filter(is_active=True).order_by('order')
    selected_category = request.GET.get('category', None)
    
    context = {
        'page_title': 'Services - UniMarket',
        'categories': categories,
        'selected_category': selected_category,
    }
    return render(request, 'app/services.html', context)


@require_http_methods(["GET", "POST"])
@csrf_protect
def contact(request):
    """Vue pour la page Contact avec formulaire"""
    if request.method == 'POST':
        # Récupérer les données du formulaire
        name = sanitize_input(request.POST.get('name', ''), 200)
        email = sanitize_input(request.POST.get('email', ''), 200)
        message = sanitize_input(request.POST.get('message', ''), 2000)
        
        # Validation basique
        errors = []
        if not name or len(name) < 3:
            errors.append('Le nom est requis (minimum 3 caractères)')
        if not email or not validate_email(email):
            errors.append('Email valide requis')
        if not message or len(message) < 10:
            errors.append('Le message doit contenir au moins 10 caractères')
        
        if not errors:
            try:
                # Log du message de contact
                logger.info(f"Message de contact reçu: {email} - {name}")
                
                context = {
                    'page_title': 'Contact - UniMarket',
                    'success': True,
                    'success_message': 'Votre message a été reçu. Nous vous répondrons bientôt!',
                }
                return render(request, 'app/contact.html', context)
            except Exception as e:
                logger.error(f"Erreur lors de la soumission du contact: {str(e)}")
                errors.append('Erreur serveur. Veuillez réessayer.')
        
        # Si erreurs, retourner avec les données et erreurs
        context = {
            'page_title': 'Contact - UniMarket',
            'errors': errors,
            'form_data': {
                'name': name,
                'email': email,
                'message': message,
            }
        }
        return render(request, 'app/contact.html', context)
    
    # GET request - afficher le formulaire
    context = {
        'page_title': 'Contact - UniMarket',
    }
    return render(request, 'app/contact.html', context)


def posts(request):
    """Vue pour les services/annonces avec pagination et filtres"""
    try:
        # Récupérer les annonces actives avec optimisation des requêtes
        posts_list = Listing.objects.filter(
            status='ACTIVE',
            is_active=True
        ).select_related(
            'seller', 
            'seller__user', 
            'category'
        ).only(
            'id', 'title', 'slug', 'description', 'price', 'image',
            'condition', 'location', 'views_count', 'contacts_count',
            'is_featured', 'created_at',
            'seller_id', 'category_id'
        ).order_by('-is_featured', '-created_at')
        
        # Filtrage par catégorie
        category_filter = request.GET.get('category', '')
        if category_filter:
            category_filter = sanitize_input(category_filter, 50)
            posts_list = posts_list.filter(category__slug=category_filter)
        
        # Filtrage par condition (type de service)
        condition_filter = request.GET.get('condition', '')
        if condition_filter:
            condition_filter = sanitize_input(condition_filter, 50)
            posts_list = posts_list.filter(condition=condition_filter)
        
        # Recherche par titre/description
        search_query = request.GET.get('search', '')
        if search_query:
            search_query = sanitize_input(search_query, 200)
            posts_list = posts_list.filter(
                models.Q(title__icontains=search_query) | 
                models.Q(description__icontains=search_query)
            )
        
        # Tri
        sort_by = request.GET.get('sort', '-created_at')
        valid_sorts = ['-created_at', 'views_count', '-views_count', 'price', '-price']
        if sort_by in valid_sorts:
            posts_list = posts_list.order_by(sort_by) if sort_by != '-created_at' else posts_list.order_by('-is_featured', sort_by)
        
        # Pagination
        paginator = Paginator(posts_list, 12)
        page_number = request.GET.get('page', 1)
        try:
            posts_page = paginator.page(page_number)
        except PageNotAnInteger:
            posts_page = paginator.page(1)
        except EmptyPage:
            posts_page = paginator.page(paginator.num_pages)
        
        # Récupérer toutes les catégories pour le filtre
        categories = Category.objects.filter(is_active=True).annotate(
            active_listings=Count(
                'listings',
                filter=Q(listings__status='ACTIVE', listings__is_active=True)
            )
        ).order_by('order')

        recent_posts = Listing.objects.filter(
            status='ACTIVE',
            is_active=True
        ).select_related('seller', 'seller__user', 'category').only(
            'id', 'title', 'slug', 'image', 'seller_id', 'category_id'
        ).order_by('-created_at')[:3]
        
        context = {
            'page_title': 'Services & Annonces - UniMarket',
            'posts': posts_page,
            'categories': categories,
            'recent_posts': recent_posts,
            'total_posts': paginator.count,
            'current_page': posts_page.number,
            'category_filter': category_filter,
            'condition_filter': condition_filter,
            'search_query': search_query,
            'sort_by': sort_by,
            'conditions': Listing.CONDITION_CHOICES,
        }
        return render(request, 'app/posts.html', context)
    
    except Exception as e:
        logger.error(f"Erreur dans posts: {str(e)}")
        return render(request, 'app/posts.html', {
            'page_title': 'Services - UniMarket',
            'error': 'Erreur lors du chargement des services'
        }, status=500)


def search(request):
    """Vue pour la recherche globale"""
    query = request.GET.get('q', '').strip()
    results = []
    
    if query:
        query = sanitize_input(query, 100)
        
        # Rechercher dans les documents
        files = UploadedFile.objects.filter(
            is_public=True,
            title__icontains=query
        ) | UploadedFile.objects.filter(
            is_public=True,
            description__icontains=query
        )
        
        # Rechercher dans les annonces
        listings = Listing.objects.filter(
            status='ACTIVE',
            title__icontains=query
        ) | Listing.objects.filter(
            status='ACTIVE',
            description__icontains=query
        )
        
        results = {
            'files': files[:10],
            'listings': listings[:10],
            'total': files.count() + listings.count()
        }
    
    context = {
        'page_title': f'Recherche: {query}' if query else 'Recherche - UniMarket',
        'search_query': query,
        'results': results,
    }
    return render(request, 'app/search.html', context)


# ======================================================================
# AUTHENTIFICATION - SIGNUP / LOGIN / LOGOUT
# ======================================================================

@csrf_protect
@require_http_methods(["GET", "POST"])
def signup(request):
    """
    Inscription utilisateur avec sécurité complète:
    - Création de nouvel utilisateur OU complétude de profil
    - Validation stricte des données
    - Transactions atomiques
    - Protection contre les attaques
    """
    if request.user.is_authenticated:
        # L'utilisateur est déjà connecté
        try:
            # Créer le profil s'il n'existe pas
            profile, _ = create_user_profile_automatically(request.user)
            
            # Vérifier si le profil est complet
            if profile.promotion and profile.specialty and profile.university:
                # Profil complet, rediriger au dashboard
                return redirect('profile')
            # Sinon, laisser compléter le profil via ce formulaire
        except Exception as e:
            logger.error(f"Erreur lors de la création du profil: {str(e)}")
            # Pas de profil, créer un
            pass
    
    if request.method == 'POST':
        # Rate limiting: 5 tentatives par heure
        if not rate_limit_check(request, 'signup', limit=5, window=3600):
            log_security_event(request, 'SIGNUP_RATE_LIMIT', 'Trop de tentatives')
            return render(request, 'app/signup.html', {
                'page_title': 'S\'inscrire - UniMarket',
                'error': 'Trop de tentatives. Essayez dans 1 heure.'
            }, status=429)
        
        # === CAS 1: Utilisateur authentifié qui complète son profil ===
        if request.user.is_authenticated:
            return _complete_profile(request)
        
        # === CAS 2: Nouvel utilisateur ===
        return _create_new_user(request)
    
    # GET request - afficher le formulaire
    context = {
        'page_title': 'S\'inscrire - UniMarket',
        'is_authenticated': request.user.is_authenticated,
    }
    return render(request, 'app/signup.html', context)


def _create_new_user(request):
    """Créer un nouvel utilisateur (cas non authentifié)"""
    email = sanitize_input(request.POST.get('email', ''), 100).lower().strip()
    password = request.POST.get('password', '')
    password_confirm = request.POST.get('password_confirm', '')
    first_name = sanitize_input(request.POST.get('first_name', ''), 100)
    last_name = sanitize_input(request.POST.get('last_name', ''), 100)
    university = sanitize_input(request.POST.get('university', 'UPC'), 100)
    specialty = sanitize_input(request.POST.get('specialty', 'INFORMATIQUE'), 50)
    promotion = sanitize_input(request.POST.get('promotion', ''), 50)
    phone = sanitize_input(request.POST.get('phone', ''), 20)
    
    # === VALIDATION ===
    errors = []
    
    # Email
    if not email or not validate_email(email):
        errors.append('Email valide requis')
    elif User.objects.filter(email=email).exists():
        log_security_event(request, 'SIGNUP_DUPLICATE_EMAIL', f'Email: {email}')
        # Ne pas révéler que l'email existe (sécurité)
        errors.append('Cet email ne peut pas être utilisé')
    
    # Noms
    if not first_name or len(first_name) < 2:
        errors.append('Prénom valide requis (minimum 2 caractères)')
    if not last_name or len(last_name) < 2:
        errors.append('Nom valide requis (minimum 2 caractères)')
    
    # Mot de passe
    if password != password_confirm:
        errors.append('Les mots de passe ne correspondent pas')
    else:
        valid_pwd, pwd_msg = validate_password(password)
        if not valid_pwd:
            errors.append(pwd_msg)
    
    # Promotion
    if not promotion:
        errors.append('Année de promotion requise')
    
    if errors:
        return render(request, 'app/signup.html', {
            'page_title': 'S\'inscrire - UniMarket',
            'errors': errors,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'university': university,
            'specialty': specialty,
            'promotion': promotion,
            'phone': phone,
            'accept_terms': True if request.POST.get('accept_terms') else False,
        })
    
    # === CRÉATION ===
    try:
        with transaction.atomic():
            # Générer un username unique basé sur l'email
            base_username = email.split('@')[0]
            username = base_username
            counter = 1
            
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            # Créer l'utilisateur Django
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
            
            # Créer le profil étudiant
            StudentProfile.objects.create(
                user=user,
                university=university,
                specialty=specialty,
                promotion=promotion,
                phone=phone,
                verification_token=str(uuid.uuid4()),
            )
            
            # Authentifier et connecter l'utilisateur
            user = authenticate(username=username, password=password)
            if user:
                auth_login(request, user)
                logger.info(f"✓ Nouvel utilisateur inscrit: {user.email}")
                # 🔔 Notification d'inscription réussie
                notify_signup_success(user.get_full_name() or user.username)
                return redirect('profile')
            else:
                # Fallback improbable
                logger.error(f"Erreur authentification après création: {email}")
                return redirect('login')
    
    except Exception as e:
        logger.error(f"Erreur critique lors de l'inscription: {str(e)}")
        log_security_event(request, 'SIGNUP_ERROR', str(e))
        return render(request, 'app/signup.html', {
            'page_title': 'S\'inscrire - UniMarket',
            'error': 'Erreur lors de l\'inscription. Veuillez réessayer.'
        }, status=500)


def _complete_profile(request):
    """Compléter le profil d'un utilisateur authentifié"""
    try:
        user = request.user
        profile = user.profile
        
        specialty = sanitize_input(request.POST.get('specialty', 'INFORMATIQUE'), 50)
        promotion = sanitize_input(request.POST.get('promotion', ''), 50)
        university = sanitize_input(request.POST.get('university', 'UPC'), 100)
        phone = sanitize_input(request.POST.get('phone', ''), 20)
        
        # Validation
        errors = []
        if not promotion:
            errors.append('Année de promotion requise')
        
        if errors:
            return render(request, 'app/signup.html', {
                'page_title': 'Compléter votre profil - UniMarket',
                'errors': errors,
            })
        
        # Mise à jour
        with transaction.atomic():
            profile.specialty = specialty
            profile.promotion = promotion
            profile.university = university
            profile.phone = phone
            profile.save()
            
            logger.info(f"✓ Profil complété: {user.email}")
            return redirect('profile')
    
    except StudentProfile.DoesNotExist:
        logger.error(f"Profil introuvable pour {request.user.email}")
        return render(request, 'app/signup.html', {
            'page_title': 'S\'inscrire - UniMarket',
            'error': 'Erreur lors de la mise à jour du profil'
        }, status=500)
    except Exception as e:
        logger.error(f"Erreur lors de la complétude du profil: {str(e)}")
        return render(request, 'app/signup.html', {
            'page_title': 'S\'inscrire - UniMarket',
            'error': 'Erreur lors de la mise à jour du profil'
        }, status=500)


@csrf_protect
@require_http_methods(["GET", "POST"])
def login(request):
    """
    Connexion utilisateur avec protection complète:
    - Rate limiting sur les tentatives
    - Protection contre open redirect
    - Pas d'énumération d'utilisateurs
    - Logs de sécurité
    """
    # Rediriger si déjà connecté
    if request.user.is_authenticated:
        return redirect('profile')
    
    if request.method == 'POST':
        # Rate limiting: 10 tentatives par 5 minutes
        if not rate_limit_check(request, 'login', limit=10, window=300):
            log_security_event(request, 'LOGIN_RATE_LIMIT', 'Trop de tentatives')
            return render(request, 'app/login.html', {
                'page_title': 'Connexion - UniMarket',
                'error': 'Trop de tentatives. Essayez dans 5 minutes.'
            }, status=429)
        
        # Récupérer et nettoyer les données
        email = sanitize_input(request.POST.get('email', ''), 100).lower().strip()
        password = request.POST.get('password', '')
        
        # Validations basiques
        if not email or not password:
            return render(request, 'app/login.html', {
                'page_title': 'Connexion - UniMarket',
                'error': 'Email et mot de passe requis'
            })
        
        if not validate_email(email):
            log_security_event(request, 'LOGIN_INVALID_EMAIL', f'Email: {email}')
            return render(request, 'app/login.html', {
                'page_title': 'Connexion - UniMarket',
                'error': 'Email ou mot de passe incorrect'
            })
        
        try:
            # Chercher l'utilisateur par email
            user_obj = User.objects.filter(email=email).first()
            
            if user_obj is None:
                # Ne pas révéler si l'email existe ou non (protection contre énumération)
                log_security_event(request, 'LOGIN_UNKNOWN_EMAIL', f'Email: {email}')
                return render(request, 'app/login.html', {
                    'page_title': 'Connexion - UniMarket',
                    'error': 'Email ou mot de passe incorrect'
                })
            
            # Vérifier que l'utilisateur est actif
            if not user_obj.is_active:
                log_security_event(request, 'LOGIN_INACTIVE_USER', f'User: {user_obj.email}')
                return render(request, 'app/login.html', {
                    'page_title': 'Connexion - UniMarket',
                    'error': 'Email ou mot de passe incorrect'
                })
            
            # Authentifier avec le username
            user = authenticate(username=user_obj.username, password=password)
            
            if user is not None:
                auth_login(request, user)
                logger.info(f"✓ Connexion réussie: {user.email}")
                
                # Créer automatiquement le profil s'il n'existe pas
                profile, created = create_user_profile_automatically(user)
                if created:
                    # Notifier l'utilisateur de mettre à jour son profil
                    notify_profile_updated("Profil créé automatiquement - Veuillez compléter vos informations")
                
                # 🔔 Notification de succès
                notify_login_success(user.email, user.get_full_name() or user.username)
                
                # Valider et rediriger vers 'next' en toute sécurité
                next_url = request.GET.get('next')
                if next_url and is_safe_redirect_url(next_url, request):
                    return redirect(next_url)
                
                # Après connexion réussie, rediriger vers profile pour compléter/afficher
                return redirect('profile')
            
            else:
                # Mot de passe incorrect
                log_security_event(request, 'LOGIN_INVALID_PASSWORD', f'User: {user_obj.email}')
                # 🔔 Notification d'erreur
                notify_login_failed("Email ou mot de passe incorrect")
                return render(request, 'app/login.html', {
                    'page_title': 'Connexion - UniMarket',
                    'error': 'Email ou mot de passe incorrect'
                })
        
        except Exception as e:
            logger.error(f"Erreur critique lors de la connexion: {str(e)}")
            log_security_event(request, 'LOGIN_ERROR', str(e))
            return render(request, 'app/login.html', {
                'page_title': 'Connexion - UniMarket',
                'error': 'Erreur serveur. Veuillez réessayer.'
            }, status=500)
    
    # GET request - afficher le formulaire
    context = {
        'page_title': 'Connexion - UniMarket'
    }
    return render(request, 'app/login.html', context)


@login_required(login_url='login')
@require_http_methods(["POST"])
def user_logout(request):
    """Déconnexion sécurisée"""
    logger.info(f"Déconnexion: {request.user.email}")
    logout(request)
    return redirect('home')


# ======================================================================
# PROFIL UTILISATEUR
# ======================================================================

@login_required(login_url='login')
def profile(request):
    """Afficher le profil utilisateur"""
    try:
        # Créer le profil s'il n'existe pas (ou récupérer)
        profile, created = create_user_profile_automatically(request.user)

        # Si le profil vient d'être créé, notifier et s'assurer des valeurs par défaut
        if created:
            notify_profile_updated("Profil créé automatiquement - Veuillez compléter vos informations")

        # S'assurer que les champs essentiels ont des valeurs par défaut pour l'affichage
        updated = False
        if not profile.university:
            profile.university = 'UPC'
            updated = True
        if not profile.specialty:
            profile.specialty = 'INFORMATIQUE'
            updated = True
        if profile.promotion is None:
            profile.promotion = ''
            updated = True
        if profile.phone is None:
            profile.phone = ''
            updated = True
        if profile.bio is None:
            profile.bio = ''
            updated = True

        if updated:
            try:
                profile.save()
            except Exception:
                # Ne pas bloquer l'affichage si la sauvegarde échoue
                logger.warning('Impossible d\'enregistrer les valeurs par défaut du profil')

        # Calculer les initiales (utiles si pas d'image de profil)
        first = (request.user.first_name or '').strip()
        last = (request.user.last_name or '').strip()
        if first or last:
            initials = (first[:1] + (last[:1] if last else '')).upper()
        else:
            # fallback sur le username
            uname = (request.user.username or '')
            initials = (uname[:2]).upper() if uname else 'U'

        # Si pas d'image de profil, générer et sauvegarder un avatar image automatiquement
        try:
            if not profile.profile_picture:
                avatar = generate_avatar_with_initials(request.user.first_name or uname, request.user.last_name or '')
                if avatar:
                    profile.profile_picture = avatar
                    profile.save()
        except Exception as e:
            logger.warning(f"Impossible de générer l'avatar automatique: {str(e)}")

        # Récupérer les listings et avis (limités pour la page profil)
        listings = Listing.objects.filter(seller=profile).order_by('-created_at')
        reviews = Review.objects.filter(seller=profile).select_related('reviewer', 'reviewer__user').order_by('-created_at')

        context = {
            'page_title': 'Mon Profil - UniMarket',
            'user': request.user,
            'profile': profile,
            'initials': initials,
            'listings': listings[:5],
            'reviews': reviews[:5],
            'listings_count': listings.count(),
            'reviews_count': reviews.count(),
            'profile_needs_update': created,
        }
        return render(request, 'app/profile.html', context)

    except Exception as e:
        logger.error(f"Erreur dans profile: {str(e)}")
        return render(request, 'app/profile.html', {
            'page_title': 'Mon Profil - UniMarket',
            'error': 'Erreur lors du chargement du profil'
        }, status=500)


@login_required(login_url='login')
@require_http_methods(["POST"])
@csrf_protect
def profile_update(request):
    """
    Mettre à jour le profil utilisateur avec validation complète:
    - Validation MIME stricte
    - Validation de taille
    - Protection contre les uploads malveillants
    - Audit logging
    """
    try:
        # Créer le profil s'il n'existe pas
        profile, _ = create_user_profile_automatically(request.user)
        user = request.user
        
        # === IMAGE DE PROFIL ===
        if 'profile_picture' in request.FILES:
            profile_picture = request.FILES['profile_picture']
            
            # Valider la taille
            if profile_picture.size > MAX_IMAGE_SIZE:
                return JsonResponse({
                    'success': False,
                    'error': f'L\'image doit faire moins de {MAX_IMAGE_SIZE // (1024*1024)}MB'
                }, status=400)
            
            # Valider le type MIME et l'extension
            is_valid, error_msg = validate_file_type(profile_picture, ALLOWED_IMAGE_TYPES)
            if not is_valid:
                log_security_event(request, 'PROFILE_INVALID_IMAGE', f'Type: {profile_picture.content_type}')
                return JsonResponse({
                    'success': False,
                    'error': error_msg
                }, status=400)
            
            try:
                with transaction.atomic():
                    # Supprimer l'ancienne image si elle existe
                    if profile.profile_picture:
                        profile.profile_picture.delete(save=False)
                    
                    # Sanitizer le nom du fichier
                    new_filename = f"profile_{user.id}_{uuid.uuid4().hex[:8]}.jpg"
                    profile_picture.name = new_filename
                    
                    profile.profile_picture = profile_picture
                    profile.save()
                    
                    logger.info(f"✓ Image de profil mise à jour: {user.email}")
                    
                    # 🔔 Notification
                    notify_profile_updated("Photo de profil")
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Photo mise à jour avec succès',
                        'image_url': profile.profile_picture.url if profile.profile_picture else ''
                    })
            except Exception as e:
                logger.error(f"Erreur lors de l'upload d'image: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'Erreur lors de l\'enregistrement'
                }, status=500)
        
        # === DONNÉES JSON ===
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Format JSON invalide'
            }, status=400)
        
        field = sanitize_input(data.get('field', ''), 50)
        
        # Liste blanche des champs modifiables
        allowed_fields = ['full_name', 'bio', 'phone']
        if field not in allowed_fields:
            log_security_event(request, 'PROFILE_UNAUTHORIZED_FIELD', f'Field: {field}')
            return JsonResponse({
                'success': False,
                'error': 'Champ non autorisé'
            }, status=403)
        
        try:
            with transaction.atomic():
                if field == 'full_name':
                    first_name = sanitize_input(data.get('first_name', ''), 100)
                    last_name = sanitize_input(data.get('last_name', ''), 100)
                    
                    if not first_name or not last_name:
                        return JsonResponse({
                            'success': False,
                            'error': 'Prénom et nom requis'
                        }, status=400)
                    
                    user.first_name = first_name
                    user.last_name = last_name
                    user.save()
                    new_value = user.get_full_name()
                    logger.info(f"✓ Nom mis à jour: {user.email}")
                    notify_profile_updated("Nom complet")
                    # Régénérer un avatar automatique si l'utilisateur n'a pas uploadé d'image
                    try:
                        if not profile.profile_picture:
                            avatar = generate_avatar_with_initials(first_name or user.username, last_name)
                            if avatar:
                                profile.profile_picture = avatar
                                profile.save()
                                # inclure l'URL de la nouvelle image dans la réponse
                                image_url = profile.profile_picture.url
                            else:
                                image_url = ''
                        else:
                            image_url = profile.profile_picture.url if profile.profile_picture else ''
                    except Exception as e:
                        logger.warning(f"Impossible de régénérer l'avatar: {str(e)}")
                        image_url = ''
                
                elif field == 'bio':
                    bio = sanitize_input(data.get('bio', ''), 500)
                    profile.bio = bio
                    profile.save()
                    new_value = bio
                    logger.info(f"✓ Bio mise à jour: {user.email}")
                    notify_profile_updated("Bio")
                
                elif field == 'phone':
                    phone = sanitize_input(data.get('phone', ''), 20)
                    
                    # Valider le format du téléphone (optionnel mais recommandé)
                    if phone and not re.match(r'^[\d\s\-\+\(\)]{6,20}$', phone):
                        return JsonResponse({
                            'success': False,
                            'error': 'Numéro de téléphone invalide'
                        }, status=400)
                    
                    profile.phone = phone
                    profile.save()
                    new_value = phone
                    logger.info(f"✓ Téléphone mis à jour: {user.email}")
                    notify_profile_updated("Numéro de téléphone")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Profil mis à jour',
                    'new_value': new_value,
                    'image_url': getattr(profile.profile_picture, 'url', '')
                })
        
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du profil: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Erreur lors de la mise à jour'
            }, status=500)
    
    except StudentProfile.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Profil non trouvé'
        }, status=404)
    except Exception as e:
        logger.error(f"Erreur critique profile_update: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur serveur'
        }, status=500)


# ======================================================================
# UPLOAD DE DOCUMENTS
# ======================================================================

@login_required(login_url='login')
@require_http_methods(["GET", "POST"])
@csrf_protect
def upload(request):
    """
    Upload de documents académiques avec sécurité complète:
    - Validation stricte du type MIME et extension
    - Limite de taille par document et par utilisateur
    - Validation du nom de fichier (protection directory traversal)
    - Rate limiting
    - Audit logging complet
    """
    try:
        # Créer le profil s'il n'existe pas
        profile, _ = create_user_profile_automatically(request.user)
    except Exception as e:
        logger.error(f"Erreur lors de la création du profil: {str(e)}")
        return render(request, 'app/upload.html', {
            'page_title': 'Upload - UniMarket',
            'error': 'Erreur lors de l\'accès au profil'
        }, status=403)
    
    # === GET: Afficher le formulaire ===
    if request.method == 'GET':
        context = {
            'page_title': 'Upload Document - UniMarket',
            'categories': UploadedFile.CATEGORY_CHOICES,
            'max_file_size_mb': MAX_DOCUMENT_SIZE // (1024 * 1024),
        }
        return render(request, 'app/upload.html', context)
    
    # === POST: Traiter l'upload ===
    # Rate limiting: 10 uploads par jour
    if not rate_limit_check(request, 'upload', limit=10, window=86400):
        log_security_event(request, 'UPLOAD_RATE_LIMIT', f'User: {request.user.email}')
        return render(request, 'app/upload.html', {
            'page_title': 'Upload - UniMarket',
            'error': 'Limite d\'uploads atteinte. Réessayez demain.'
        }, status=429)
    
    # Récupérer les données
    uploaded_file = request.FILES.get('file')
    title = sanitize_input(request.POST.get('title', 'Sans titre'), 200)
    category = sanitize_input(request.POST.get('category', 'RESOURCE'), 20)
    description = sanitize_input(request.POST.get('description', ''), 1000)
    subject = sanitize_input(request.POST.get('subject', ''), 100)
    course_code = sanitize_input(request.POST.get('course_code', ''), 50)
    
    # === VALIDATION INITIALE ===
    errors = []
    
    if not uploaded_file:
        errors.append('Fichier requis')
    
    if not title or len(title.strip()) < 3:
        errors.append('Titre requis (minimum 3 caractères)')
    
    if errors:
        return render(request, 'app/upload.html', {
            'page_title': 'Upload - UniMarket',
            'errors': errors,
            'categories': UploadedFile.CATEGORY_CHOICES,
        })
    
    # === VALIDATION DU FICHIER ===
    try:
        # Taille maximale
        if uploaded_file.size > MAX_DOCUMENT_SIZE:
            log_security_event(request, 'UPLOAD_SIZE_EXCEEDED', 
                             f'User: {request.user.email}, Size: {uploaded_file.size}')
            return render(request, 'app/upload.html', {
                'page_title': 'Upload - UniMarket',
                'error': f'Le fichier ne doit pas dépasser {MAX_DOCUMENT_SIZE // (1024*1024)}MB',
                'categories': UploadedFile.CATEGORY_CHOICES,
            })
        
        # Taille minimale (protection contre les fichiers vides)
        if uploaded_file.size < 100:
            return render(request, 'app/upload.html', {
                'page_title': 'Upload - UniMarket',
                'error': 'Le fichier doit faire au moins 100 bytes',
                'categories': UploadedFile.CATEGORY_CHOICES,
            })
        
        # Validation MIME et extension
        is_valid, error_msg = validate_file_type(uploaded_file, ALLOWED_DOCUMENT_TYPES)
        if not is_valid:
            log_security_event(request, 'UPLOAD_INVALID_FILE_TYPE', 
                             f'User: {request.user.email}, Type: {uploaded_file.content_type}')
            return render(request, 'app/upload.html', {
                'page_title': 'Upload - UniMarket',
                'error': error_msg,
                'categories': UploadedFile.CATEGORY_CHOICES,
            })
        
        # Valider le nom du fichier (prévention directory traversal)
        original_filename = sanitize_filename(uploaded_file.name)
        if not original_filename or len(original_filename) < 3:
            log_security_event(request, 'UPLOAD_INVALID_FILENAME', 
                             f'User: {request.user.email}, Filename: {uploaded_file.name}')
            return render(request, 'app/upload.html', {
                'page_title': 'Upload - UniMarket',
                'error': 'Nom de fichier invalide',
                'categories': UploadedFile.CATEGORY_CHOICES,
            })
        
        # === VÉRIFICATION DES QUOTAS ===
        user_uploads_today = UploadedFile.objects.filter(
            uploader=profile,
            created_at__date=timezone.now().date()
        ).count()
        
        if user_uploads_today >= 10:
            log_security_event(request, 'UPLOAD_DAILY_QUOTA_EXCEEDED', 
                             f'User: {request.user.email}')
            return render(request, 'app/upload.html', {
                'page_title': 'Upload - UniMarket',
                'error': 'Limite d\'uploads quotidienne atteinte (10 par jour)',
                'categories': UploadedFile.CATEGORY_CHOICES,
            })
        
        # === CRÉATION DU DOCUMENT ===
        try:
            with transaction.atomic():
                # Générer un nom de fichier unique et sécurisé
                file_hash = uuid.uuid4().hex[:16]
                file_ext = original_filename.split('.')[-1].lower()
                new_filename = f"uploads/{request.user.id}/{file_hash}.{file_ext}"
                
                # Créer l'objet UploadedFile
                file_obj = UploadedFile.objects.create(
                    uploader=profile,
                    file=uploaded_file,
                    title=title,
                    category=category,
                    description=description,
                    subject=subject,
                    course_code=course_code,
                    file_size=uploaded_file.size,
                    is_public=True,
                )
                
                logger.info(f"✓ Document uploadé par {request.user.email}: {title} ({uploaded_file.size} bytes)")
                
                # 🔔 Notification d'upload réussi
                notify_upload_success(title)
                
                return render(request, 'app/upload.html', {
                    'page_title': 'Upload - UniMarket',
                    'success': True,
                    'message': f'Document "{title}" uploadé avec succès!',
                    'categories': UploadedFile.CATEGORY_CHOICES,
                })
        
        except Exception as e:
            logger.error(f"Erreur lors de la création du document: {str(e)}")
            log_security_event(request, 'UPLOAD_CREATION_ERROR', str(e))
            return render(request, 'app/upload.html', {
                'page_title': 'Upload - UniMarket',
                'error': 'Erreur lors de l\'upload. Veuillez réessayer.',
                'categories': UploadedFile.CATEGORY_CHOICES,
            }, status=500)
    
    except Exception as e:
        logger.error(f"Erreur critique lors de l'upload: {str(e)}")
        log_security_event(request, 'UPLOAD_CRITICAL_ERROR', str(e))
        return render(request, 'app/upload.html', {
            'page_title': 'Upload - UniMarket',
            'error': 'Erreur serveur',
            'categories': UploadedFile.CATEGORY_CHOICES,
        }, status=500)


# ======================================================================
# NEWSLETTER
# ======================================================================

@require_http_methods(["POST"])
@csrf_protect
def newsletter_subscribe(request):
    """S'inscrire à la newsletter"""
    if not rate_limit_check(request, 'newsletter', limit=5, window=3600):
        return JsonResponse({
            'success': False,
            'error': 'Trop de tentatives. Réessayez plus tard.'
        }, status=429)
    
    email = sanitize_input(request.POST.get('email', ''), 100).lower()
    name = sanitize_input(request.POST.get('name', ''), 100)
    
    if not email or not validate_email(email):
        return JsonResponse({
            'success': False,
            'error': 'Email invalide'
        }, status=400)
    
    try:
        subscription, created = NewsletterSubscription.objects.get_or_create(
            email=email,
            defaults={
                'name': name,
                'token': str(uuid.uuid4()),
                'is_active': True,
                'frequency': 'WEEKLY'
            }
        )
        
        if created:
            logger.info(f"Nouvel inscrit newsletter: {email}")
            message = 'Bienvenue! Vous êtes inscrit à la newsletter.'
        else:
            if not subscription.is_active:
                subscription.is_active = True
                subscription.save()
                logger.info(f"Réactivation newsletter: {email}")
            message = 'Cet email est déjà inscrit à la newsletter.'
        
        return JsonResponse({
            'success': True,
            'message': message
        })
    
    except Exception as e:
        logger.error(f"Erreur newsletter: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur serveur'
        }, status=500)


# ======================================================================
# AVIS / REVIEWS
# ======================================================================

@login_required(login_url='login')
@require_http_methods(["POST"])
@csrf_protect
def add_review(request):
    """Ajouter un avis/témoignage (AJAX JSON)"""
    try:
        data = json.loads(request.body)
        listing_id = data.get('listing_id')
        rating = data.get('rating', 5)
        comment = sanitize_input(data.get('comment', ''), 500)
        
        if not listing_id:
            return JsonResponse({
                'success': False,
                'error': 'Listing ID manquant'
            }, status=400)
        
        # Valider le rating
        try:
            rating = int(rating)
            rating = max(1, min(rating, 5))
        except:
            rating = 5
        
        if len(comment) < 10:
            return JsonResponse({
                'success': False,
                'error': 'Le commentaire doit faire au moins 10 caractères'
            }, status=400)
        
        try:
            # Créer le profil s'il n'existe pas
            reviewer_profile, _ = create_user_profile_automatically(request.user)
        except Exception as e:
            logger.error(f"Erreur lors de la création du profil: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Erreur lors de l\'accès au profil'
            }, status=400)
        
        try:
            listing = Listing.objects.get(id=listing_id)
        except Listing.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Annonce non trouvée'
            }, status=404)
        
        # Empêcher l'auto-évaluation
        if listing.seller == reviewer_profile:
            return JsonResponse({
                'success': False,
                'error': 'Vous ne pouvez pas évaluer votre propre annonce'
            }, status=403)
        
        try:
            with transaction.atomic():
                review = Review.objects.create(
                    reviewer=reviewer_profile,
                    reviewer_name=request.user.get_full_name() or request.user.username,
                    listing=listing,
                    seller=listing.seller,
                    rating=rating,
                    title=f"Avis - {rating}★",
                    comment=comment,
                    is_verified_buyer=True
                )
                
                # Mettre à jour la note moyenne du vendeur
                seller_reviews = Review.objects.filter(seller=listing.seller)
                avg_rating = seller_reviews.aggregate(avg=models.Avg('rating'))['avg'] or 5.0
                listing.seller.rating = round(avg_rating, 1)
                listing.seller.total_reviews = seller_reviews.count()
                listing.seller.save()
                
                logger.info(f"Avis ajouté par {request.user.email} pour {listing.title}")
                
                return JsonResponse({
                    'success': True,
                    'message': 'Avis enregistré avec succès',
                    'review_id': review.id
                })
        
        except Exception as e:
            logger.error(f"Erreur add_review: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Erreur lors de l\'enregistrement'
            }, status=500)
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'JSON invalide'
        }, status=400)
    except Exception as e:
        logger.error(f"Erreur générale add_review: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur serveur'
        }, status=500)


# ============================================================
# NOUVELLES VUES - DÉTAILS POST ET DASHBOARD
# ============================================================

def post_detail(request, slug):
    """Affiche les détails d'un post/service avec formulaire de contact"""
    try:
        post = get_object_or_404(Listing, slug=slug, is_active=True, status='ACTIVE')
        
        # Incrémenter les vues
        post.views_count += 1
        post.save(update_fields=['views_count'])
        
        # Récupérer les demandes de contact pour ce post
        contacts = post.contacts.all().order_by('-created_at')
        contact_count = contacts.count()
        
        # Déterminer le lien WhatsApp
        whatsapp_url = None
        if post.whatsapp_number:
            message = f"Bonjour, je suis intéressé par: {post.title}"
            whatsapp_url = f"https://wa.me/{post.whatsapp_number.replace('+', '')}?text={message}"
        
        context = {
            'page_title': f'{post.title} - UniMarket',
            'post': post,
            'seller': post.seller,
            'whatsapp_url': whatsapp_url,
            'contact_count': contact_count,
            'user_has_contacted': False,
        }
        
        # Vérifier si l'utilisateur actuel a déjà contacté
        if request.user.is_authenticated:
            try:
                # Créer le profil s'il n'existe pas
                profile, _ = create_user_profile_automatically(request.user)
                context['user_has_contacted'] = post.contacts.filter(buyer=profile).exists()
            except Exception as e:
                logger.error(f"Erreur lors de la création du profil: {str(e)}")
                context['user_has_contacted'] = False
        
        return render(request, 'app/post_detail.html', context)
    
    except Exception as e:
        logger.error(f"Erreur post_detail: {str(e)}")
        return render(request, 'app/posts.html', {
            'error': 'Post non trouvé'
        }, status=404)


@login_required(login_url='login')
def post_contact(request, slug):
    """AJAX: Enregistrer une demande de contact pour un post"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    try:
        post = get_object_or_404(Listing, slug=slug, is_active=True, status='ACTIVE')
        
        # Créer le profil s'il n'existe pas
        profile, _ = create_user_profile_automatically(request.user)
        
        # Vérifier si déjà contacté (prevent duplicates)
        contact, created = post.contacts.get_or_create(
            listing=post,
            buyer=profile,
            defaults={
                'buyer_email': request.user.email,
                'buyer_phone': profile.phone,
                'buyer_name': request.user.get_full_name() or request.user.username,
                'message': request.POST.get('message', ''),
                'contacted_via': 'PLATFORM',
            }
        )
        
        if created:
            post.contacts_count += 1
            post.save(update_fields=['contacts_count'])
            
            logger.info(f"✓ Contact enregistré: {request.user.email} → {post.title}")
            return JsonResponse({
                'success': True,
                'message': 'Demande de contact enregistrée ✓'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Vous avez déjà contacté ce service'
            })
    
    except Exception as e:
        logger.error(f"Erreur post_contact: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required(login_url='login')
def seller_dashboard(request):
    """Tableau de bord du vendeur/propriétaire de service"""
    try:
        # Créer le profil s'il n'existe pas
        profile, _ = create_user_profile_automatically(request.user)
        
        # Récupérer tous les posts du vendeur
        user_listings = profile.listings.filter(is_active=True).order_by('-created_at')
        
        # Statistiques globales
        total_listings = user_listings.count()
        total_views = sum(listing.views_count for listing in user_listings)
        total_contacts = sum(listing.contacts_count for listing in user_listings)
        
        # Récupérer tous les contacts pour les posts du vendeur
        all_contacts = []
        for listing in user_listings:
            for contact in listing.contacts.all():
                all_contacts.append({
                    'listing': listing,
                    'contact': contact,
                })
        
        all_contacts = sorted(all_contacts, key=lambda x: x['contact'].created_at, reverse=True)
        
        # Pagination pour les contacts
        paginator = Paginator(all_contacts, 10)
        page_number = request.GET.get('page', 1)
        try:
            contacts_page = paginator.page(page_number)
        except PageNotAnInteger:
            contacts_page = paginator.page(1)
        except EmptyPage:
            contacts_page = paginator.page(paginator.num_pages)
        
        # Statistiques par listing
        listing_stats = []
        for listing in user_listings:
            listing_stats.append({
                'listing': listing,
                'views': listing.views_count,
                'contacts': listing.contacts_count,
                'status': 'Actif' if listing.status == 'ACTIVE' else listing.get_status_display(),
            })
        
        context = {
            'page_title': 'Tableau de Bord - Mes Services',
            'profile': profile,
            'total_listings': total_listings,
            'total_views': total_views,
            'total_contacts': total_contacts,
            'contacts': contacts_page,
            'listing_stats': listing_stats,
            'total_contacts_page': paginator.count,
        }
        
        return render(request, 'app/seller_dashboard.html', context)
    
    except Exception as e:
        logger.error(f"Erreur seller_dashboard: {str(e)}")
        return render(request, 'app/posts.html', {
            'error': 'Erreur lors du chargement du tableau de bord'
        }, status=500)


@login_required(login_url='login')
def create_listing(request):
    """Créer un nouveau service/listing pour le vendeur."""
    try:
        # Créer le profil s'il n'existe pas
        profile, _ = create_user_profile_automatically(request.user)
        
    except Exception as e:
        logger.error(f"Erreur lors de la création du profil: {str(e)}")
        return redirect('profile')

    if request.method == 'GET':
        context = {
            'page_title': 'Publier un Service - UniMarket',
            'categories': Category.objects.filter(is_active=True),
            'conditions': Listing.CONDITION_CHOICES,
            'max_image_size_mb': MAX_IMAGE_SIZE // (1024 * 1024),
            'form_data': {
                'price_status': 'free',
            },
        }
        return render(request, 'app/seller_listing_create.html', context)

    title = sanitize_input(request.POST.get('title', ''), 200)
    description = sanitize_input(request.POST.get('description', ''), 5000)
    location = sanitize_input(request.POST.get('location', ''), 200)
    whatsapp_number = sanitize_input(request.POST.get('whatsapp_number', ''), 20)
    condition = sanitize_input(request.POST.get('condition', ''), 20)
    category_id = request.POST.get('category', '')
    price_status = request.POST.get('price_status', 'free')
    price_raw = request.POST.get('price', '').strip()
    images = request.FILES.getlist('images')
    # fallback for older form (single 'image')
    if not images and request.FILES.get('image'):
        images = [request.FILES.get('image')]

    errors = []
    if not title or len(title) < 5:
        errors.append('Le titre doit contenir au moins 5 caractères.')
    if not description or len(description) < 20:
        errors.append('La description doit contenir au moins 20 caractères.')
    if not location:
        errors.append('La localisation est requise.')
    if not category_id:
        errors.append('La catégorie est requise.')
    if condition not in dict(Listing.CONDITION_CHOICES):
        errors.append('Le type de service est invalide.')
    if not images:
        errors.append('Au moins une image est requise.')
    else:
        # validate each image
        for idx, img in enumerate(images):
            if img.size > MAX_IMAGE_SIZE:
                errors.append(f"L'image '{sanitize_filename(img.name)}' dépasse la taille maximale de {MAX_IMAGE_SIZE // (1024 * 1024)}MB.")
            else:
                valid_image, image_error = validate_file_type(img, ALLOWED_IMAGE_TYPES)
                if not valid_image:
                    errors.append(f"{sanitize_filename(img.name)}: {image_error}")

    price = None
    if price_status == 'paid':
        if not price_raw:
            errors.append('Le prix est requis pour un service payant.')
        else:
            try:
                price = Decimal(price_raw)
                if price < 0:
                    errors.append('Le prix ne peut pas être négatif.')
            except InvalidOperation:
                errors.append('Le prix doit être un nombre valide.')
    else:
        price = None

    category = None
    if category_id:
        try:
            category = Category.objects.get(id=int(category_id), is_active=True)
        except (Category.DoesNotExist, ValueError):
            errors.append('La catégorie sélectionnée est invalide.')

    if errors:
        context = {
            'page_title': 'Publier un Service - UniMarket',
            'categories': Category.objects.filter(is_active=True),
            'conditions': Listing.CONDITION_CHOICES,
            'errors': errors,
            'form_data': {
                'title': title,
                'description': description,
                'location': location,
                'whatsapp_number': whatsapp_number,
                'condition': condition,
                'category_id': category_id,
                'price_status': price_status,
                'price': price_raw,
            },
            'max_image_size_mb': MAX_IMAGE_SIZE // (1024 * 1024),
        }
        return render(request, 'app/seller_listing_create.html', context)

    slug = generate_unique_slug(Listing, title)
    # create listing with first image as main
    first_image = images[0] if images else None
    listing = Listing.objects.create(
        seller=profile,
        title=title,
        description=description,
        category=category,
        price=price,
        image=first_image,
        condition=condition,
        location=location,
        whatsapp_number=whatsapp_number,
        slug=slug,
        status='ACTIVE',
        contact_method='EMAIL',
    )

    # Save gallery images (remaining images)
    try:
        for order_idx, img in enumerate(images[1:], start=1):
            ListingImage.objects.create(listing=listing, image=img, order=order_idx)
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde des images de la galerie: {str(e)}")

    logger.info(f"✓ Nouveau service créé: {listing.title} ({listing.slug})")
    messages.success(request, 'Votre service a été publié avec succès !')
    return redirect('post_detail', slug=listing.slug)


@login_required(login_url='login')
def seller_listing_edit(request, slug):
    """Éditer un post/service du vendeur"""
    try:
        # Créer le profil s'il n'existe pas
        profile, _ = create_user_profile_automatically(request.user)
        listing = get_object_or_404(Listing, slug=slug, seller=profile)
        
        if request.method == 'POST':
            # Mettre à jour les champs
            listing.title = sanitize_input(request.POST.get('title', listing.title), 200)
            listing.description = sanitize_input(request.POST.get('description', listing.description), 5000)
            listing.price = request.POST.get('price', listing.price) or None
            listing.location = sanitize_input(request.POST.get('location', listing.location), 200)
            listing.whatsapp_number = sanitize_input(request.POST.get('whatsapp_number', listing.whatsapp_number), 20)
            listing.condition = sanitize_input(request.POST.get('condition', listing.condition), 20)
            
            category_id = request.POST.get('category', '')
            if category_id:
                try:
                    listing.category = Category.objects.get(id=int(category_id), is_active=True)
                except (Category.DoesNotExist, ValueError):
                    logger.warning(f"Catégorie invalide lors de la modification de listing : {category_id}")

            if 'image' in request.FILES:
                listing.image = request.FILES['image']
            
            listing.save()
            logger.info(f"✓ Post modifié: {listing.title}")
            
            return redirect('seller_dashboard')
        
        context = {
            'page_title': f'Éditer - {listing.title}',
            'listing': listing,
            'categories': Category.objects.filter(is_active=True),
            'conditions': Listing.CONDITION_CHOICES,
        }
        
        return render(request, 'app/seller_listing_edit.html', context)
    
    except Exception as e:
        logger.error(f"Erreur seller_listing_edit: {str(e)}")
        return redirect('seller_dashboard')
