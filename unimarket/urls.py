"""
URL configuration for unimarket project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
]

from django.http import HttpResponseRedirect
from django.templatetags.static import static as static_url
import os, random
from django.views.static import serve as static_serve
from django.urls import re_path


def media_with_fallback(request, path):
    """Serve media files from MEDIA_ROOT; if missing, redirect to sensible static fallbacks.

    - profiles/*  -> /static/img/bg-img/2_150.jpg
    - listings/*  -> random choice between /static/img/bg-img/20.jpg .. 30.jpg
    - otherwise    -> /static/img/bg-img/20.jpg
    """
    media_path = os.path.join(settings.MEDIA_ROOT, path)
    if os.path.exists(media_path):
        return static_serve(request, path, document_root=settings.MEDIA_ROOT)

    # Fallbacks
    if path.startswith('profiles/'):
        return HttpResponseRedirect(static_url('img/bg-img/2_150.jpg'))
    if path.startswith('listings/'):
        img = random.choice([f'img/bg-img/{i}.jpg' for i in range(20, 31)])
        return HttpResponseRedirect(static_url(img))
    return HttpResponseRedirect(static_url('img/bg-img/20.jpg'))


# Serve media files and provide fallbacks when missing
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', media_with_fallback),
]
