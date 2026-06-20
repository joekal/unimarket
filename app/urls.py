from django.urls import path, re_path
from . import views

# Configuration des URLs pour l'application UniMarket
# À inclure dans le urls.py principal du projet avec:
# path('', include('yourapp.urls'))

urlpatterns = [
    path('', views.index, name='home'),
    path('about/', views.about, name='about'),
    path('services/', views.services, name='services'),
    path('contact/', views.contact, name='contact'),
    path('posts/', views.posts, name='posts'),
    re_path(r'^posts/(?P<slug>[-\w]+)/$', views.post_detail, name='post_detail'),
    re_path(r'^posts/(?P<slug>[-\w]+)/contact/$', views.post_contact, name='post_contact'),
    path('search/', views.search, name='search'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.profile_update, name='profile_update'),
    path('upload/', views.upload, name='upload'),
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/listing/create/', views.create_listing, name='seller_listing_create'),
    path('seller/listing/<slug:slug>/edit/', views.seller_listing_edit, name='seller_listing_edit'),
    path('newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
    path('review/add/', views.add_review, name='add_review'),
]
