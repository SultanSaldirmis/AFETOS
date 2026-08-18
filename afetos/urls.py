"""
URL configuration for afetos project.

Sayfa route'ları (dashboard, harita, ihbar oluşturma vb.) sonraki adımlarda
ilgili app'lerin kendi urls.py dosyalarından include edilecek. Bu adımda
sadece admin paneli ve geliştirme ortamında medya dosyalarının servis
edilmesi ayarlandı.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from deprem import views as deprem_views
from ekipler import views as ekipler_views
from ihbarlar import views as ihbarlar_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('hesaplar.urls')),
    path('', include('dashboard.urls')),
    path('ihbarlar/', include('ihbarlar.urls')),
    path('olaylar/', include('olaylar.urls')),
    path('ekipler/', include('ekipler.urls')),
    # Rol bazlı sayfalar kasıtlı olarak app prefix'i almadan, kök seviyede:
    path('gorevim/', ekipler_views.gorevim, name='gorevim'),
    path('gorevim/durum/', ekipler_views.gorevim_durum_guncelle, name='gorevim_durum_guncelle'),
    path('gorevim/destek-talebi/', ekipler_views.gorevim_destek_talebi_olustur, name='gorevim_destek_talebi_olustur'),
    path('vatandas/', ihbarlar_views.vatandas, name='vatandas'),
    # Üçüncü parti veri proxy'si — AFETOS'un kendi karar destek
    # mekanizmasından tamamen bağımsız, sadece harita için görsel katman:
    path('api/kandilli/', deprem_views.kandilli_proxy, name='kandilli_proxy'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
