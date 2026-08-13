from django.urls import path

from . import views

app_name = 'olaylar'

urlpatterns = [
    path('harita/', views.harita, name='harita'),
    path('harita/veri/', views.harita_veri, name='harita_veri'),
]
