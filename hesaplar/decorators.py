"""
Rol bazlı erişim kontrolü için ortak yardımcılar.

3 rol var: Yönetici/Koordinatör (is_staff=True), Saha Ekip Üyesi
(request.user.ekip var), Vatandaş (diğer herkes). Bu modül, view'ların
üstüne eklenen decorator'ları ve "bu kullanıcı hangi sayfaya ait"
mantığını tek yerde tutar — her app kendi view'ında tekrar yazmasın diye.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect


def kullanicinin_ana_sayfasi(user):
    """Bir kullanıcının rolüne göre gitmesi gereken ana sayfanın URL adını döner."""
    if user.is_staff:
        return 'dashboard:ana_panel'
    if hasattr(user, 'ekip') and user.ekip is not None:
        return 'gorevim'
    return 'vatandas'


def personel_gerekli(view_func):
    """
    Sadece is_staff=True kullanıcıların (Yönetici/Koordinatör) erişebildiği
    sayfalar için. Giriş yapmamışsa login'e, giriş yapmış ama staff
    değilse kendi rolüne uygun ana sayfaya yönlendirir.
    """
    @wraps(view_func)
    @login_required
    def sarmalayici(request, *args, **kwargs):
        if not request.user.is_staff:
            return redirect(kullanicinin_ana_sayfasi(request.user))
        return view_func(request, *args, **kwargs)
    return sarmalayici


def saha_ekip_gerekli(view_func):
    """
    Sadece bir Ekip kaydına bağlı kullanıcıların (Saha Ekip Üyesi)
    erişebildiği sayfalar için (ör. /gorevim/).
    """
    @wraps(view_func)
    @login_required
    def sarmalayici(request, *args, **kwargs):
        if not (hasattr(request.user, 'ekip') and request.user.ekip is not None):
            if request.user.is_staff:
                return redirect('dashboard:ana_panel')
            return redirect('vatandas')
        return view_func(request, *args, **kwargs)
    return sarmalayici
