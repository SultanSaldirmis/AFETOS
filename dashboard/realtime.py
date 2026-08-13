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
from django.template.loader import render_to_string

from ekipler.models import Ekip
from ihbarlar.models import Ihbar
from olaylar.models import OlayKumesi

GRUP_ADI = 'afetos_canli'


def _ozet_baglami() -> dict:
    """Ana Panel'in gösterdiği özet verinin tazesini çıkarır (views.ana_panel ile aynı sorgular)."""
    aktif_kumeler = OlayKumesi.objects.exclude(durum=OlayKumesi.Durum.TAMAMLANDI)
    return {
        'kritik_kumeler': aktif_kumeler.order_by('-oncelik_skoru')[:8],
        'toplam_ihbar_sayisi': Ihbar.objects.count(),
        'aktif_kume_sayisi': aktif_kumeler.count(),
        'dogrulaniyor_sayisi': aktif_kumeler.filter(durum=OlayKumesi.Durum.DOGRULANIYOR).count(),
        'mudahale_sayisi': aktif_kumeler.filter(durum=OlayKumesi.Durum.MUDAHALE_EDILIYOR).count(),
        'bosta_ekip_sayisi': Ekip.objects.filter(durum=Ekip.Durum.BOSTA).count(),
        'toplam_ekip_sayisi': Ekip.objects.count(),
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

    ozet_html = render_to_string('dashboard/_ozet_icerik.html', _ozet_baglami())
    icerik = f'<div id="dashboard-ozet" hx-swap-oob="true">{ozet_html}</div>'

    async_to_sync(channel_layer.group_send)(
        GRUP_ADI,
        {'type': 'guncelleme.gonder', 'icerik': icerik},
    )
