"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
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
from django.views.generic import TemplateView

from interviews.views import home, panel

from . import pwa

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('manifest.webmanifest', pwa.manifest, name='manifest'),
    path('sw.js', pwa.service_worker, name='service_worker'),
    path('cevrimdisi/', pwa.offline, name='offline'),
    path('', home, name='home'),
    path('panel/', panel, name='panel'),
    path('gizlilik/', TemplateView.as_view(template_name='legal/privacy.html'), name='privacy'),
    path('kvkk/', TemplateView.as_view(template_name='legal/kvkk.html'), name='kvkk'),
    path('', include('accounts.urls')),
    path('', include('interviews.urls')),
]
