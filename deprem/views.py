"""
Kandilli Rasathanesi canlı deprem verisi — sadece HARİTADA GÖRSEL REFERANS
katmanı olarak gösterilir.

ÖNEMLİ (kapsam sınırı): Bu veri kesinlikle İhbar/OlayKümesi modeline
yazılmaz ve AFETOS'un kendi karar destek mekanizmasına (güven skoru,
öncelik skoru, kümeleme) hiçbir şekilde girdi olmaz — o mekanizma sadece
kullanıcı ihbarlarına dayanır. Burası salt bir proxy + görüntüleme katmanı.

Kaynak: https://api.orhanaydogdu.com.tr/deprem/kandilli/live — üçüncü
taraf, ücretsiz bir servis. Ticari kullanımda Boğaziçi Üniversitesi
Kandilli Rasathanesi'nden izin ve atıf gerekiyor; bu prototip/demo
kapsamında olduğumuz ve kaynağa atıf verdiğimiz (harita popup'ında
"Kaynak: Kandilli Rasathanesi") unutulmamalı.
"""
import requests
from django.core.cache import cache
from django.http import JsonResponse

from hesaplar.decorators import personel_gerekli

KANDILLI_API_URL = 'https://api.orhanaydogdu.com.tr/deprem/kandilli/live'
CACHE_ANAHTARI = 'kandilli_deprem_verisi'
CACHE_SURESI_SANIYE = 60
ISTEK_ZAMAN_ASIMI_SANIYE = 5


@personel_gerekli
def kandilli_proxy(request):
    """
    Tarayıcının doğrudan üçüncü parti API'ye istek atmasının önüne geçen
    proxy view (CORS/rate-limit riskini azaltır). Yanıt 60 saniye
    Django'nun cache framework'üyle (LocMemCache, prototip için yeterli)
    önbelleğe alınır — 60sn içindeki tekrar isteklerde kaynağa gidilmez.

    Kaynağa erişilemezse (zaman aşımı, ağ hatası, 5xx vb.) sayfa asla
    çökmez: boş sonuç listesi + {"error": "..."} JSON'u döner.
    """
    veri = cache.get(CACHE_ANAHTARI)
    if veri is not None:
        return JsonResponse(veri)

    try:
        yanit = requests.get(KANDILLI_API_URL, timeout=ISTEK_ZAMAN_ASIMI_SANIYE)
        yanit.raise_for_status()
        veri = yanit.json()
    except (requests.RequestException, ValueError):
        # ValueError: yanıt geçerli JSON değilse (json() içinde fırlar)
        veri = {'result': [], 'error': 'Kandilli verisine şu an ulaşılamıyor.'}
        # Hata sonucu kısa süreliğine cache'lenir ki kaynak kesintideyken
        # her istek tekrar tekrar dışarı çıkıp beklemeye girmesin.
        cache.set(CACHE_ANAHTARI, veri, timeout=CACHE_SURESI_SANIYE)
        return JsonResponse(veri)

    cache.set(CACHE_ANAHTARI, veri, timeout=CACHE_SURESI_SANIYE)
    return JsonResponse(veri)
