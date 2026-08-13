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

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('ihbarlar/', include('ihbarlar.urls')),
    path('olaylar/', include('olaylar.urls')),
    path('ekipler/', include('ekipler.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
