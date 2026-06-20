# Generated migration to update categories

from django.db import migrations
from django.utils.text import slugify


def create_new_categories(apps, schema_editor):
    """Crée les nouvelles catégories"""
    Category = apps.get_model('app', 'Category')
    
    # Supprimer toutes les catégories existantes
    Category.objects.all().delete()
    
    # Liste des nouvelles catégories
    categories = [
        {
            'name': 'Livres & Supports',
            'icon': 'fa-book',
            'color': '#fec89a',
            'order': 1,
        },
        {
            'name': 'Documents Académiques',
            'icon': 'fa-file-text',
            'color': '#f5a962',
            'order': 2,
        },
        {
            'name': 'Cours Particuliers',
            'icon': 'fa-graduation-cap',
            'color': '#d48f3f',
            'order': 3,
        },
        {
            'name': 'Anciens Examens',
            'icon': 'fa-pencil-square-o',
            'color': '#c87d2e',
            'order': 4,
        },
        {
            'name': 'Assistance Technique',
            'icon': 'fa-cogs',
            'color': '#b86b1e',
            'order': 5,
        },
        {
            'name': 'Ressources Professionnelles',
            'icon': 'fa-briefcase',
            'color': '#a8590f',
            'order': 6,
        },
        {
            'name': 'Autres Services',
            'icon': 'fa-ellipsis-h',
            'color': '#9a4700',
            'order': 7,
        },
    ]
    
    # Créer les catégories
    for cat in categories:
        Category.objects.create(
            name=cat['name'],
            slug=slugify(cat['name']),
            icon=cat['icon'],
            color=cat['color'],
            order=cat['order'],
            is_active=True,
            description=''
        )


def reverse_categories(apps, schema_editor):
    """Annule la migration (supprime les catégories)"""
    Category = apps.get_model('app', 'Category')
    Category.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_listing_contacts_count_listing_whatsapp_number_and_more'),
    ]

    operations = [
        migrations.RunPython(create_new_categories, reverse_categories),
    ]
