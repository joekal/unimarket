from .models import Category


def active_categories(request):
    """Fournit les catégories actives aux templates pour la navigation globale."""
    return {
        'categories': Category.objects.filter(is_active=True).order_by('order')
    }
