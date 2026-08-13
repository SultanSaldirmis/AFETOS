from django.http import JsonResponse
from django.shortcuts import render

from ekipler.models import Ekip

from .models import OlayKumesi


def harita(request):
    """Leaflet haritası sayfası. Veri, ayrı bir JSON endpoint'inden (harita_veri) çekilir."""
    return render(request, 'olaylar/harita.html')


def harita_veri(request):
    """
    Harita için olay kümeleri ve ekiplerin konum/durum verisini JSON olarak
    döner. Bu adımda basit bir HTTP GET; canlı güncelleme (WebSocket) adım
    7'de eklenecek — o zamana kadar sayfa yenilenerek veya bu endpoint
    tekrar çağrılarak güncellenebilir.
    """
    kumeler = OlayKumesi.objects.exclude(durum=OlayKumesi.Durum.TAMAMLANDI)

    kumeler_verisi = []
    for kume in kumeler:
        ilk_ihbar = kume.ihbarlar.first()
        kumeler_verisi.append({
            'id': kume.id,
            'lat': kume.merkez_lat,
            'lng': kume.merkez_lng,
            'oncelik_skoru': kume.oncelik_skoru,
            'guven_skoru': kume.guven_skoru,
            'renk': kume.oncelik_hex_renk,
            'durum': kume.durum,
            'durum_gosterim': kume.get_durum_display(),
            'ihbar_sayisi': kume.ihbarlar.count(),
            'detay_url': f'/ihbarlar/{ilk_ihbar.id}/' if ilk_ihbar else None,
        })

    ekipler_verisi = [
        {
            'id': ekip.id,
            'ad': ekip.ad,
            'tur': ekip.tur,
            'tur_gosterim': ekip.get_tur_display(),
            'lat': ekip.lat,
            'lng': ekip.lng,
            'durum': ekip.durum,
            'durum_gosterim': ekip.get_durum_display(),
        }
        for ekip in Ekip.objects.all()
    ]

    return JsonResponse({'kumeler': kumeler_verisi, 'ekipler': ekipler_verisi})
