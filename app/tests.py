from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from app.models import Category, Listing


class CreateListingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='TestPass123'
        )
        self.category = Category.objects.create(
            name='Cours Particuliers Test',
            slug='cours-particuliers-test',
            description='Cours particuliers pour étudiants',
            icon='fa-graduation-cap',
            color='#fec89a',
            order=1,
            is_active=True,
        )

    def test_get_create_listing_page(self):
        self.client.login(username='testuser', password='TestPass123')
        response = self.client.get(reverse('seller_listing_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Publier un Service')
        self.assertContains(response, self.category.name)

    def test_create_listing_redirects_to_post_detail_and_sets_message(self):
        self.client.login(username='testuser', password='TestPass123')
        image_content = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\xff\xff?\x00\x05\x00\x01\x01\x0d\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        image = SimpleUploadedFile('test.png', image_content, content_type='image/png')

        response = self.client.post(
            reverse('seller_listing_create'),
            data={
                'title': 'Cours privé de maths',
                'description': 'Je propose un cours complet de mathématiques pour étudiants UPC.',
                'category': str(self.category.id),
                'condition': 'SERVICE',
                'price_status': 'paid',
                'price': '25.00',
                'location': 'Campus',
                'whatsapp_number': '+212600000000',
                'image': image,
            },
            follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Listing.objects.count(), 1)
        listing = Listing.objects.first()
        self.assertRedirects(response, reverse('post_detail', kwargs={'slug': listing.slug}), fetch_redirect_response=False)
        self.assertContains(response, 'Votre service a été publié avec succès !')
        self.assertContains(response, listing.title)
