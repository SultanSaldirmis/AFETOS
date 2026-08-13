from django.urls import path

from . import views

app_name = 'ihbarlar'

urlpatterns = [
    path('olustur/', views.olustur, name='olustur'),
    path('<int:ihbar_id>/', views.detay, name='detay'),
]
