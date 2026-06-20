from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.utils import timezone
import os

# ============================================================
# 1. PROFIL ÉTUDIANT
# ============================================================

class StudentProfile(models.Model):
    """Profil étendu pour les utilisateurs étudiants"""
    
    SPECIALTIES = [
        ('DROIT', 'Droit'),
        ('ECONOMIE', 'Économie'),
        ('MEDECINE', 'Médecine'),
        ('THEOLOGIE', 'Théologie'),
        ('INFORMATIQUE', 'Informatique'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    university = models.CharField(max_length=100, default='UPC')
    specialty = models.CharField(max_length=50, choices=SPECIALTIES, default='INFORMATIQUE')
    promotion = models.CharField(max_length=50, help_text="Ex: 2024-2025")
    
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, unique=True, null=True, blank=True)
    
    rating = models.DecimalField(default=5.0, max_digits=3, decimal_places=2, 
                                validators=[MinValueValidator(0), MaxValueValidator(5)])
    total_reviews = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Profil Étudiant"
        verbose_name_plural = "Profils Étudiants"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.university}"


# ============================================================
# 2. CATÉGORIES
# ============================================================

class Category(models.Model):
    """Catégories de produits/services"""
    
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, help_text="Classe FontAwesome (ex: fa-book)", default='fa-tag')
    color = models.CharField(max_length=7, default='#fec89a', help_text="Couleur hex")
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ============================================================
# 3. ANNONCES (LISTINGS)
# ============================================================

class Listing(models.Model):
    """Annonces/Offres du marché"""
    
    CONDITION_CHOICES = [
        ('NEW', 'Neuf'),
        ('LIKE_NEW', 'Comme neuf'),
        ('GOOD', 'Bon état'),
        ('FAIR', 'État correct'),
        ('SERVICE', 'Service'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('SOLD', 'Vendu/Complété'),
        ('ARCHIVED', 'Archivé'),
    ]
    
    CONTACT_CHOICES = [
        ('EMAIL', 'Email'),
        ('PHONE', 'Téléphone'),
        ('IN_PERSON', 'En personne'),
        ('BOTH', 'Email + Téléphone'),
    ]
    
    seller = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='listings')
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='listings')
    
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                help_text="Laisser vide pour gratuit")
    image = models.ImageField(upload_to='listings/')
    
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='LIKE_NEW')
    location = models.CharField(max_length=200, help_text="Bâtiment/Campus")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    contact_method = models.CharField(max_length=20, choices=CONTACT_CHOICES, default='EMAIL')
    
    # WhatsApp Contact
    whatsapp_number = models.CharField(max_length=20, blank=True, help_text="Numéro WhatsApp (ex: +213671234567)")
    
    views_count = models.IntegerField(default=0)
    contacts_count = models.IntegerField(default=0, help_text="Nombre de personnes qui ont contacté")
    is_featured = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Auto-archivé si non actualisé")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Annonce"
        verbose_name_plural = "Annonces"
        ordering = ['-is_featured', '-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['category', 'status']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_price_display(self):
        if self.price is None or self.price == 0:
            return "Gratuit"
        return f"$ {self.price}"


# ============================================================
# 4. IMAGES DES ANNONCES
# ============================================================

class ListingImage(models.Model):
    """Galerie d'images pour les annonces"""
    
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='listings/gallery/')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"Image - {self.listing.title}"


# ============================================================
# 4b. DEMANDES DE CONTACT (ANALYTICS)
# ============================================================

class ListingContact(models.Model):
    """Suivi des personnes qui contactent pour un service/produit"""
    
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='contacts')
    buyer = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='contacted_listings')
    
    buyer_email = models.EmailField()
    buyer_phone = models.CharField(max_length=20, blank=True)
    buyer_name = models.CharField(max_length=100, blank=True)
    
    message = models.TextField(blank=True, help_text="Message optionnel du demandeur")
    
    contacted_via = models.CharField(
        max_length=20,
        choices=[('WHATSAPP', 'WhatsApp'), ('EMAIL', 'Email'), ('PHONE', 'Téléphone'), ('PLATFORM', 'Platform')],
        default='PLATFORM'
    )
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Demande de Contact"
        verbose_name_plural = "Demandes de Contact"
        ordering = ['-created_at']
        unique_together = ('listing', 'buyer')
    
    def __str__(self):
        return f"{self.buyer_name or self.buyer.user.get_full_name()} → {self.listing.title}"


# ============================================================
# 5. FICHIERS UPLOADÉS (NOTES, DOCUMENTS)
# ============================================================

class UploadedFile(models.Model):
    """Fichiers uploadés (notes, documents, etc.)"""
    
    CATEGORY_CHOICES = [
        ('NOTES', 'Notes de cours'),
        ('EXAM', 'Examen/Correction'),
        ('SUMMARY', 'Résumé'),
        ('CHEAT_SHEET', 'Antisèche'),
        ('PROJECT', 'Projet'),
        ('RESOURCE', 'Ressource'),
        ('OTHER', 'Autre'),
    ]
    
    FILE_TYPE_CHOICES = [
        ('PDF', 'PDF'),
        ('DOCX', 'Word'),
        ('XLSX', 'Excel'),
        ('PPTX', 'PowerPoint'),
        ('IMG', 'Image'),
        ('ZIP', 'Archive'),
        ('TXT', 'Texte'),
        ('OTHER', 'Autre'),
    ]
    
    uploader = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='uploaded_files')
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    
    file = models.FileField(upload_to='documents/')
    subject = models.CharField(max_length=100, blank=True, help_text="Ex: Mathématiques")
    course_code = models.CharField(max_length=50, blank=True, help_text="Ex: MATH101")
    semester = models.CharField(max_length=50, blank=True, help_text="Ex: S1")
    year = models.IntegerField(default=timezone.now().year)
    
    downloads_count = models.IntegerField(default=0)
    rating = models.DecimalField(default=5.0, max_digits=3, decimal_places=2,
                                validators=[MinValueValidator(0), MaxValueValidator(5)])
    
    file_size = models.IntegerField(null=True, blank=True, help_text="Taille en bytes")
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='PDF')
    
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Fichier Uploadé"
        verbose_name_plural = "Fichiers Uploadés"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subject', 'year']),
            models.Index(fields=['category', 'is_public']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Déterminer le type de fichier
        if self.file:
            ext = os.path.splitext(self.file.name)[1].lower()
            ext_to_type = {
                '.pdf': 'PDF',
                '.doc': 'DOCX', '.docx': 'DOCX',
                '.xls': 'XLSX', '.xlsx': 'XLSX',
                '.ppt': 'PPTX', '.pptx': 'PPTX',
                '.jpg': 'IMG', '.jpeg': 'IMG', '.png': 'IMG', '.gif': 'IMG',
                '.zip': 'ZIP', '.rar': 'ZIP',
                '.txt': 'TXT',
            }
            self.file_type = ext_to_type.get(ext, 'OTHER')
            self.file_size = self.file.size
        super().save(*args, **kwargs)


# ============================================================
# 6. AVIS ET ÉVALUATIONS
# ============================================================

class Review(models.Model):
    """Avis et évaluations"""
    
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]
    
    reviewer = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='reviews_given')
    reviewer_name = models.CharField(max_length=100, blank=True, help_text="Optionnel: publié anonymement")
    
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, null=True, blank=True, related_name='reviews')
    seller = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='reviews_received')
    
    rating = models.IntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=200)
    comment = models.TextField(max_length=1000)
    
    is_verified_buyer = models.BooleanField(default=False)
    helpful_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Avis"
        verbose_name_plural = "Avis"
        ordering = ['-created_at']
        unique_together = ('reviewer', 'listing', 'seller')
    
    def __str__(self):
        return f"{self.rating}⭐ - {self.title}"


# ============================================================
# 7. MESSAGES PRIVÉS
# ============================================================

class Message(models.Model):
    """Messages privés entre utilisateurs"""
    
    sender = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='messages_sent')
    recipient = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='messages_received')
    
    subject = models.CharField(max_length=200)
    content = models.TextField()
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, blank=True)
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.subject} - {self.sender} → {self.recipient}"


# ============================================================
# 8. ANNONCES FAVORITES
# ============================================================

class Favorite(models.Model):
    """Annonces favorites"""
    
    user = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='favorites')
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'listing')
        verbose_name = "Favori"
        verbose_name_plural = "Favoris"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user} ❤️ {self.listing}"


# ============================================================
# 9. NEWSLETTER
# ============================================================

class NewsletterSubscription(models.Model):
    """Inscriptions newsletter"""
    
    FREQUENCY_CHOICES = [
        ('DAILY', 'Quotidienne'),
        ('WEEKLY', 'Hebdomadaire'),
        ('MONTHLY', 'Mensuelle'),
    ]
    
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    categories = models.ManyToManyField(Category, blank=True, related_name='subscribers')
    
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='WEEKLY')
    is_active = models.BooleanField(default=True)
    token = models.CharField(max_length=100, unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Inscription Newsletter"
        verbose_name_plural = "Inscriptions Newsletter"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.email


# ============================================================
# 10. MESSAGES DE CONTACT
# ============================================================

class ContactMessage(models.Model):
    """Messages du formulaire de contact"""
    
    CATEGORY_CHOICES = [
        ('GENERAL', 'Question générale'),
        ('SUPPORT', 'Support technique'),
        ('PARTNERSHIP', 'Partenariat'),
        ('ISSUE', 'Signaler un problème'),
        ('FEEDBACK', 'Retour/Suggestion'),
    ]
    
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='GENERAL')
    is_read = models.BooleanField(default=False)
    responded = models.BooleanField(default=False)
    response = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Message Contact"
        verbose_name_plural = "Messages Contact"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subject} - {self.email}"


# ============================================================
# 11. TRANSACTIONS (OPTIONNEL - POUR PAIEMENTS)
# ============================================================

class Transaction(models.Model):
    """Historique des transactions"""
    
    STATUS_CHOICES = [
        ('PENDING', 'En attente'),
        ('COMPLETED', 'Complétée'),
        ('FAILED', 'Échouée'),
        ('REFUNDED', 'Remboursée'),
    ]
    
    PAYMENT_METHODS = [
        ('TRANSFER', 'Virement bancaire'),
        ('CARD', 'Carte bancaire'),
        ('CASH', 'Espèces'),
        ('PAYPAL', 'PayPal'),
        ('CRYPTO', 'Cryptomonnaie'),
    ]
    
    buyer = models.ForeignKey(StudentProfile, on_delete=models.SET_NULL, null=True, related_name='purchases')
    seller = models.ForeignKey(StudentProfile, on_delete=models.SET_NULL, null=True, related_name='sales')
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, related_name='transactions')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    reference = models.CharField(max_length=100, unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Transaction {self.reference} - ${self.amount}"


# ============================================================
# 12. NOTIFICATIONS
# ============================================================

class Notification(models.Model):
    """Notifications utilisateur"""
    
    TYPE_CHOICES = [
        ('MESSAGE', 'Nouveau message'),
        ('REVIEW', 'Nouvel avis'),
        ('LISTING', 'Nouveau listing'),
        ('FAVORITE', 'Annonce favorite'),
        ('SYSTEM', 'Notification système'),
    ]
    
    user = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='notifications')
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    related_listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    action_url = models.CharField(max_length=500, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user}"
