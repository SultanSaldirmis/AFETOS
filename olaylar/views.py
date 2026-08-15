from django.http import JsonResponse
from django.shortcuts import render

from ekipler.models import Ekip
from hesaplar.decorators import personel_gerekli

from .models import OlayKumesi


@personel_gerekli
def harita(request):
    """
    Leaflet haritası sayfası. Veri, ayrı bir JSON endpoint'inden
    (harita_veri) çekilir. ?ekip=<id> query param'ı varsa (Ekipler
    sayfasındaki "Haritada gör" linkinden gelinmişse), sadece o ekip
    gösterilecek şekilde bir filtre rozeti render edilir — asıl
    filtreleme mantığı harita_veri'de, aynı param'la yapılır.
    """
    aktif_kumeler = OlayKumesi.objects.exclude(durum=OlayKumesi.Durum.TAMAMLANDI)

    ekip_filtre = None
    ekip_id = request.GET.get('ekip')
    if ekip_id:
        ekip_filtre = Ekip.objects.filter(id=ekip_id).first()

    context = {
        'aktif_kume_sayisi': aktif_kumeler.count(),
        'ekip_sayisi': Ekip.objects.count(),
        'ekip_filtre': ekip_filtre,
    }
    return render(request, 'olaylar/harita.html', context)


@personel_gerekli
def harita_veri(request):
    """
    Harita için olay kümeleri ve ekiplerin konum/durum verisini JSON olarak
    döner.

    ?ekip=<id> verilirse (Ekipler sayfasından "Haritada gör" ile
    gelindiğinde): sadece o ekip döner, olay kümeleri hiç dönmez — Ekipler
    sayfasının "sadece o ekip gösterilsin, diğerleri gizlensin" isteği.
    """
    ekip_id = request.GET.get('ekip')

    if ekip_id:
        kumeler_verisi = []
        ekipler_qs = Ekip.objects.filter(id=ekip_id)
    else:
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
                'renk_kod': kume.oncelik_renk_kod,
                'durum': kume.durum,
                'durum_gosterim': kume.get_durum_display(),
                'olay_turu_gosterim': ilk_ihbar.get_olay_turu_display() if ilk_ihbar else '—',
                'ihbar_sayisi': kume.ihbarlar.count(),
                'detay_url': f'/ihbarlar/{ilk_ihbar.id}/' if ilk_ihbar else None,
            })
        ekipler_qs = Ekip.objects.all()

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
        for ekip in ekipler_qs
    ]

    return JsonResponse({'kumeler': kumeler_verisi, 'ekipler': ekipler_verisi})
