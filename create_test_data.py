#!/usr/bin/env python
if __name__ == '__main__':
    import os
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unimarket.settings')
    django.setup()

from django.contrib.auth.models import User
from app.models import StudentProfile, UploadedFile, Review, Listing, Category
from django.utils import timezone
from decimal import Decimal
from django.core.files.base import ContentFile

print("Creating test data...")

# Créer deux utilisateurs
try:
    user1 = User.objects.get(username='testuser1')
    profile1 = user1.profile
except:
    user1 = User.objects.create_user(
        username='testuser1',
        first_name='Jean',
        last_name='Dupont',
        email='jean@test.com',
        password='Test1234'
    )
    profile1 = StudentProfile.objects.create(
        user=user1,
        phone='+243812345678',
        specialty='INFORMATIQUE'
    )
    print(f"Created user1: {user1.username}")

try:
    user2 = User.objects.get(username='testuser2')
    profile2 = user2.profile
except:
    user2 = User.objects.create_user(
        username='testuser2',
        first_name='Marie',
        last_name='Martin',
        email='marie@test.com',
        password='Test1234'
    )
    profile2 = StudentProfile.objects.create(
        user=user2,
        phone='+243887654321',
        specialty='MEDECINE'
    )
    print(f"Created user2: {user2.username}")

# Créer des documents
print("Creating test files...")

# Document gratuit
file_content = ContentFile(b"Test PDF content - Examen")
file_content.name = "test_exam.pdf"

try:
    doc1, created = UploadedFile.objects.get_or_create(
        title="Examen Mathématiques 2024",
        defaults={
            'uploader': profile1,
            'description': 'Ancien examen de mathématiques avec corrections',
            'category': 'EXAM',
            'subject': 'Mathématiques',
            'course_code': 'MATH101',
            'semester': 'S1',
            'year': 2024,
            'file': file_content,
            'is_public': True,
            'is_paid': False,
            'downloads_count': 15,
            'rating': Decimal('4.8')
        }
    )
    if created:
        print(f"Created document 1: {doc1.title}")
    else:
        print(f"Document 1 already exists")
except Exception as e:
    print(f"Error creating document 1: {e}")

# Document payant
file_content2 = ContentFile(b"Test PDF content - Notes")
file_content2.name = "test_notes.pdf"

try:
    doc2, created = UploadedFile.objects.get_or_create(
        title="Notes de Philosophie Avancée",
        defaults={
            'uploader': profile2,
            'description': 'Cours détaillé de philosophie avec explications',
            'category': 'NOTES',
            'subject': 'Philosophie',
            'course_code': 'PHIL201',
            'semester': 'S2',
            'year': 2025,
            'file': file_content2,
            'is_public': True,
            'is_paid': True,
            'price': Decimal('5.00'),
            'downloads_count': 8,
            'rating': Decimal('4.5')
        }
    )
    if created:
        print(f"Created document 2: {doc2.title}")
    else:
        print(f"Document 2 already exists")
except Exception as e:
    print(f"Error creating document 2: {e}")

# Créer des catégories et listings pour les reviews
print("Creating listings for reviews...")

try:
    category, created = Category.objects.get_or_create(
        name='Livres',
        defaults={'slug': 'livres', 'icon': 'fa-book'}
    )
    if created:
        print(f"Created category: {category.name}")
except Exception as e:
    print(f"Error creating category: {e}")

# Créer un listing
try:
    listing, created = Listing.objects.get_or_create(
        title="Livre de Mathématiques Avancées",
        defaults={
            'seller': profile1,
            'slug': 'livre-math-avances',
            'description': 'Excellent livre de références pour les mathématiques',
            'category': category,
            'price': None,
            'image': 'listings/default.jpg'
        }
    )
    if created:
        print(f"Created listing: {listing.title}")
except Exception as e:
    print(f"Error creating listing: {e}")

# Créer des reviews
print("Creating reviews...")

try:
    review1, created = Review.objects.get_or_create(
        reviewer=profile2,
        listing=listing,
        seller=profile1,
        defaults={
            'rating': 5,
            'title': 'Excellent service!',
            'comment': 'Très rapide et les notes sont vraiment excellentes. Je recommande fortement ce vendeur!',
            'is_verified_buyer': True
        }
    )
    if created:
        print(f"Created review 1 for {profile2.user.get_full_name()}")
except Exception as e:
    print(f"Error creating review 1: {e}")

try:
    review2, created = Review.objects.get_or_create(
        reviewer=profile1,
        listing=listing,
        seller=profile2,
        defaults={
            'rating': 4,
            'title': 'Bonne qualité',
            'comment': 'Les documents sont bien structurés et faciles à comprendre. Merci beaucoup!',
            'is_verified_buyer': True
        }
    )
    if created:
        print(f"Created review 2 for {profile1.user.get_full_name()}")
except Exception as e:
    print(f"Error creating review 2: {e}")

print("\nTest data creation complete!")
