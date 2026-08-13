from django.urls import path

from . import views

app_name = 'ekipler'

urlpatterns = [
    path('', views.liste, name='liste'),
]
