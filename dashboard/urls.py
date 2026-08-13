from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.ana_panel, name='ana_panel'),
    path('yonetim/', views.yonetim_paneli, name='yonetim_paneli'),
    path('yonetim/kume/<int:kume_id>/durum/', views.kume_durum_guncelle, name='kume_durum_guncelle'),
    path('yonetim/kume/<int:kume_id>/ekip-ata/', views.kume_ekip_ata, name='kume_ekip_ata'),
]
