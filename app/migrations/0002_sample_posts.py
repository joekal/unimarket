# Generated migration for sample posts/BATs data
from django.db import migrations

def create_sample_posts(apps, schema_editor):
    """Créer des données d'exemple pour les BATs"""
    # Nota: Esta migración puede ser ignorada si se prefiere crear datos manualmente
    # via admin o através de un script separado
    pass

def reverse_sample_posts(apps, schema_editor):
    """Supprimer les données d'exemple"""
    UploadedFile = apps.get_model('app', 'UploadedFile')
    UploadedFile.objects.filter(category='EXAM').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_sample_posts, reverse_sample_posts),
    ]
