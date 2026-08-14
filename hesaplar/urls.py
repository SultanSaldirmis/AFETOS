from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

# Not: app_name kasıtlı olarak YOK — /login/, /kayit/, /logout/ isimsiz
# (namespace'siz) URL adlarıyla ({% url 'login' %} gibi) proje genelinde
# kullanılabiliyor, tıpkı /gorevim/ ve /vatandas/ gibi.
urlpatterns = [
    path('login/', views.RolBazliLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('kayit/', views.kayit, name='kayit'),
]
