"""
WebSocket üzerinden canlı güncelleme yayını.

Bu modül, durum değiştiren bir işlemden SONRA view katmanı tarafından
çağrılır (yeni ihbar, küme durumu güncelleme, ekip atama). Sorumluluğu
sadece güncel özet HTML'ini render edip 'afetos_canli' grubuna yaymaktır;
domain mantığına (skor hesaplama, kümeleme) dokunmaz.

Sadece Ana Panel ve Harita sayfaları bu yayını dinler (proje kapsamı
gereği diğer sayfalarda canlı güncelleme yok).
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from ekipler.models import Ekip
from ihbarlar.models import Ihbar
from olaylar.models import OlayKumesi

GRUP_ADI = 'afetos_canli'


def ozet_baglami() -> dict:
    """
    Ana Panel'in gösterdiği özet verinin tazesini çıkarır. Hem views.ana_panel
    (ilk sayfa yüklemesi) hem de bu modüldeki guncelleme_yayinla (WebSocket
    push'ları) AYNI fonksiyonu kullanır — kod tekrarı yok, iki yerin
    birbirinden sapması riski yok.
    """
    aktif_kumeler = OlayKumesi.objects.exclude(durum=OlayKumesi.Durum.TAMAMLANDI)

    en_eski_dogrulama = (
        aktif_kumeler.filter(durum=OlayKumesi.Durum.DOGRULANIYOR)
        .order_by('olusturulma_zamani').first()
    )
    en_eski_dogrulama_dakika = None
    if en_eski_dogrulama:
        en_eski_dogrulama_dakika = int(
            (timezone.now() - en_eski_dogrulama.olusturulma_zamani).total_seconds() / 60
        )

    return {
        'kritik_kumeler': aktif_kumeler.order_by('-oncelik_skoru')[:8],
        'toplam_ihbar_sayisi': Ihbar.objects.count(),
        'aktif_kume_sayisi': aktif_kumeler.count(),
        'kritik_kume_sayisi': aktif_kumeler.filter(oncelik_skoru__gte=80).count(),
        'dogrulaniyor_sayisi': aktif_kumeler.filter(durum=OlayKumesi.Durum.DOGRULANIYOR).count(),
        'en_eski_dogrulama_dakika': en_eski_dogrulama_dakika,
        'mudahale_sayisi': aktif_kumeler.filter(durum=OlayKumesi.Durum.MUDAHALE_EDILIYOR).count(),
        'bosta_ekip_sayisi': Ekip.objects.filter(durum=Ekip.Durum.BOSTA).count(),
        'gorevde_ekip_sayisi': Ekip.objects.exclude(durum=Ekip.Durum.BOSTA).count(),
        'toplam_ekip_sayisi': Ekip.objects.count(),
        'son_guncellenen_kume': OlayKumesi.objects.order_by('-guncellenme_zamani').first(),
        'kumeleme_yaricapi': getattr(settings, 'KUMELEME_YARICAPI_METRE', 400),
        'son_ihbarlar': Ihbar.objects.select_related('olay_kumesi').order_by('-olusturulma_zamani')[:6],
    }


def guncelleme_yayinla() -> None:
    """
    Güncel özeti 'afetos_canli' grubuna yayınlar.

    - Ana Panel bunu htmx'in WebSocket eklentisiyle dinler ve gelen HTML'i
      (hx-swap-oob ile) doğrudan DOM'a uygular — sayfa yenilenmez.
    - Harita sayfası aynı mesajı ham WebSocket ile dinler; mesajın içeriğiyle
      ilgilenmez, sadece "bir şey değişti" sinyali olarak kullanıp
      /olaylar/harita/veri/ endpoint'ini tekrar çeker.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return  # kanal katmanı yapılandırılmamışsa (ör. bazı test ortamları) sessizce geç

    ozet_html = render_to_string('dashboard/_ozet_icerik.html', ozet_baglami())
    icerik = f'<div id="dashboard-ozet" hx-swap-oob="true">{ozet_html}</div>'

    async_to_sync(channel_layer.group_send)(
        GRUP_ADI,
        {'type': 'guncelleme.gonder', 'icerik': icerik},
    )
