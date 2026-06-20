from django.contrib import admin
from .models import (
    StudentProfile, Category, Listing, ListingImage, 
    UploadedFile, Review, Message, Favorite,
    NewsletterSubscription, ContactMessage, Transaction, Notification
)

# ============================================================
# PROFIL ÉTUDIANT
# ============================================================

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'university', 'specialty', 'promotion', 'rating', 'is_verified', 'created_at')
    list_filter = ('university', 'specialty', 'is_verified', 'is_active', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'user__email', 'university')
    readonly_fields = ('rating', 'total_reviews', 'created_at', 'updated_at')
    fieldsets = (
        ('Utilisateur', {'fields': ('user',)}),
        ('Informations Académiques', {'fields': ('university', 'specialty', 'promotion')}),
        ('Profil Public', {'fields': ('profile_picture', 'bio', 'phone')}),
        ('Vérification', {'fields': ('is_verified', 'verification_token')}),
        ('Statistiques', {'fields': ('rating', 'total_reviews')}),
        ('Statut', {'fields': ('is_active',)}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )
    
    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    get_full_name.short_description = 'Utilisateur'


# ============================================================
# CATÉGORIES
# ============================================================

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'color', 'order', 'is_active')
    list_filter = ('is_active', 'order')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('order', 'name')


# ============================================================
# ANNONCES (LISTINGS)
# ============================================================

class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 3
    fields = ('image', 'order')
    ordering = ('order',)


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'price', 'status', 'views_count', 'is_featured', 'created_at')
    list_filter = ('status', 'category', 'condition', 'is_featured', 'created_at')
    search_fields = ('title', 'description', 'seller__user__username')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('views_count', 'created_at', 'updated_at', 'slug')
    inlines = [ListingImageInline]
    
    fieldsets = (
        ('Vendeur', {'fields': ('seller',)}),
        ('Annonce', {'fields': ('title', 'slug', 'description', 'category')}),
        ('Prix & Condition', {'fields': ('price', 'condition')}),
        ('Image', {'fields': ('image',)}),
        ('Localisation & Contact', {'fields': ('location', 'contact_method')}),
        ('Statut', {'fields': ('status', 'is_featured', 'is_active')}),
        ('Expiration', {'fields': ('expires_at',)}),
        ('Statistiques', {'fields': ('views_count',)}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )
    
    def get_price_display(self, obj):
        return obj.get_price_display()
    get_price_display.short_description = 'Prix'


# ============================================================
# FICHIERS UPLOADÉS
# ============================================================

@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploader', 'category', 'subject', 'file_type', 'downloads_count', 'rating', 'is_public', 'created_at')
    list_filter = ('category', 'file_type', 'is_public', 'year', 'created_at')
    search_fields = ('title', 'description', 'subject', 'course_code', 'uploader__user__username')
    readonly_fields = ('file_type', 'file_size', 'downloads_count', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Uploadeur', {'fields': ('uploader',)}),
        ('Informations', {'fields': ('title', 'description', 'category')}),
        ('Cours', {'fields': ('subject', 'course_code', 'semester', 'year')}),
        ('Fichier', {'fields': ('file', 'file_type', 'file_size')}),
        ('Statistiques', {'fields': ('downloads_count', 'rating')}),
        ('Visibilité', {'fields': ('is_public', 'expires_at')}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )


# ============================================================
# AVIS
# ============================================================

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('title', 'rating', 'reviewer', 'seller', 'helpful_count', 'is_verified_buyer', 'created_at')
    list_filter = ('rating', 'is_verified_buyer', 'created_at')
    search_fields = ('title', 'comment', 'reviewer__user__username', 'seller__user__username')
    readonly_fields = ('created_at', 'updated_at', 'helpful_count')
    
    fieldsets = (
        ('Évaluateur', {'fields': ('reviewer', 'reviewer_name')}),
        ('Évalué', {'fields': ('seller', 'listing')}),
        ('Avis', {'fields': ('rating', 'title', 'comment')}),
        ('Vérification', {'fields': ('is_verified_buyer', 'helpful_count')}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )


# ============================================================
# MESSAGES
# ============================================================

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'recipient', 'is_read', 'listing', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('subject', 'content', 'sender__user__username', 'recipient__user__username')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Correspondance', {'fields': ('sender', 'recipient', 'listing')}),
        ('Contenu', {'fields': ('subject', 'content')}),
        ('Statut', {'fields': ('is_read',)}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )


# ============================================================
# FAVORIS
# ============================================================

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'listing', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__user__username', 'listing__title')
    readonly_fields = ('created_at',)


# ============================================================
# NEWSLETTER
# ============================================================

@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'frequency', 'is_active', 'created_at')
    list_filter = ('frequency', 'is_active', 'created_at')
    search_fields = ('email', 'name')
    readonly_fields = ('token', 'created_at', 'updated_at')
    filter_horizontal = ('categories',)


# ============================================================
# MESSAGES DE CONTACT
# ============================================================

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'email', 'category', 'is_read', 'responded', 'created_at')
    list_filter = ('category', 'is_read', 'responded', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Contact', {'fields': ('name', 'email', 'phone')}),
        ('Message', {'fields': ('subject', 'category', 'message')}),
        ('Traitement', {'fields': ('is_read', 'responded', 'response')}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )


# ============================================================
# TRANSACTIONS
# ============================================================

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'buyer', 'seller', 'amount', 'status', 'payment_method', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('reference', 'buyer__user__username', 'seller__user__username')
    readonly_fields = ('reference', 'created_at', 'completed_at')
    
    fieldsets = (
        ('Parties', {'fields': ('buyer', 'seller', 'listing')}),
        ('Montant', {'fields': ('amount', 'payment_method')}),
        ('Statut', {'fields': ('status', 'reference')}),
        ('Dates', {'fields': ('created_at', 'completed_at')}),
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'type', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'user__user__username')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Destinataire', {'fields': ('user',)}),
        ('Contenu', {'fields': ('title', 'message', 'type')}),
        ('Lien', {'fields': ('related_listing', 'action_url')}),
        ('Statut', {'fields': ('is_read',)}),
        ('Date', {'fields': ('created_at',)}),
    )
