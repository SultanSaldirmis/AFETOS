"""
WebSocket üzerinden canlı güncelleme yayını + paylaşılan bağlam (context)
fonksiyonları.

Bu modül, durum değiştiren bir işlemden SONRA view katmanı tarafından
çağrılır (yeni ihbar, küme durumu güncelleme, ekip atama, destek talebi).
Sorumluluğu güncel özet HTML'ini render edip 'afetos_canli' grubuna
yaymaktır; domain mantığına (skor hesaplama, kümeleme) dokunmaz.

Sadece Ana Panel, Harita ve Yönetim Paneli sayfaları bu yayını dinler
(proje kapsamı gereği diğer sayfalarda canlı güncelleme yok — Görevim
sayfası da aynı kanalı dinler ama sadece "bir şey değişti, sayfayı
yenile" sinyali olarak kullanır, ayrı bir partial almaz).

NOT: `kume_ekip_onerileri` ve `destek_talepleri_baglami` burada (views.py
yerine) tanımlı çünkü dashboard/views.py zaten bu modülden import ediyor
— tersi yönde bir import (realtime.py -> views.py) döngüsel import'a yol
açardı.
"""
from collections import Counter

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from ekipler.models import Ekip
from ekipler.services import EkipAday, uygun_ekipleri_sirala
from ihbarlar.models import Ihbar
from olaylar.models import DestekTalebi, OlayKumesi

GRUP_ADI = 'afetos_canli'

# Sistem Önerisi kutusunda gösterilecek en fazla ekip sayısı — tek bir
# öneri yerine sıralı bir liste (rakip projeden esinlenen iyileştirme,
# madde 3). Filtreleme/sıralama mantığı AYNI (ekipler/services.py); burada
# sadece sonucu kesiyoruz.
ONERI_LISTESI_UZUNLUGU = 4


def kume_ekip_onerileri(kume, adet=ONERI_LISTESI_UZUNLUGU):
    """
    Bir olay kümesi için sıralı 'Sistem Önerisi' listesi hesaplar (en fazla
    `adet` kayıt): kümedeki baskın olay türüne uygun VE boşta olan
    ekipleri, mesafeye göre yakından uzağa sıralar. ekipler.services'teki
    `uygun_ekipleri_sirala` fonksiyonunu OLDUĞU GİBİ kullanır — filtreleme/
    sıralama mantığı burada tekrar yazılmıyor, sadece `[:adet]` ile
    kesiliyor. Yönetim Paneli'ndeki olay detayı VE Destek Talepleri bölümü
    tarafından ORTAK kullanılır (aynı algoritma, iki farklı yerde).

    Döner: (öneri_listesi, sebep_metni). Liste elemanları:
        {'ekip': Ekip, 'mesafe_km': float, 'ilk_mi': bool}
    """
    ihbarlar = list(kume.ihbarlar.all())
    if not ihbarlar:
        return [], None

    baskin_tur = Counter(i.olay_turu for i in ihbarlar).most_common(1)[0][0]
    baskin_tur_gosterim = Ihbar.OlayTuru(baskin_tur).label

    ekip_adaylari = [
        EkipAday(id=e.id, tur=e.tur, lat=e.lat, lng=e.lng, durum=e.durum)
        for e in Ekip.objects.all()
    ]
    onerileri = uygun_ekipleri_sirala(baskin_tur, kume.merkez_lat, kume.merkez_lng, ekip_adaylari)[:adet]

    if not onerileri:
        return [], f'"{baskin_tur_gosterim}" türü için şu an boşta uygun ekip yok.'

    ekip_map = {e.id: e for e in Ekip.objects.filter(id__in=[o.ekip_id for o in onerileri])}
    liste = [
        {
            'ekip': ekip_map[oneri.ekip_id],
            'mesafe_km': oneri.mesafe_metre / 1000,
            'ilk_mi': (i == 0),
        }
        for i, oneri in enumerate(onerileri)
    ]
    return liste, f'"{baskin_tur_gosterim}" türüne uygun, mesafeye göre sıralı.'


def destek_talepleri_baglami() -> dict:
    """
    Bekleyen destek taleplerini + her biri için (mevcut ekip önerisi
    algoritmasıyla, adet=1) önerilen ek ekibi hazırlar. Yönetim Paneli'nin
    hem ilk yüklemesi hem htmx/WS partial güncellemeleri bunu kullanır.
    """
    talepler = (
        DestekTalebi.objects.filter(durum=DestekTalebi.Durum.BEKLIYOR)
        .select_related('olay_kumesi', 'talep_eden_ekip')
    )
    satirlar = []
    for talep in talepler:
        onerileri, _ = kume_ekip_onerileri(talep.olay_kumesi, adet=1)
        satirlar.append({
            'talep': talep,
            'onerilen_ekip': onerileri[0]['ekip'] if onerileri else None,
        })
    return {'destek_talepleri': satirlar}


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
        'bekleyen_destek_talebi_sayisi': DestekTalebi.objects.filter(durum=DestekTalebi.Durum.BEKLIYOR).count(),
    }


def guncelleme_yayinla() -> None:
    """
    Güncel özeti + bekleyen destek talepleri panelini 'afetos_canli'
    grubuna yayınlar (aynı mesajda iki ayrı hx-swap-oob bloğu).

    - Ana Panel bunu htmx'in WebSocket eklentisiyle dinler ve gelen HTML'i
      (hx-swap-oob ile) doğrudan DOM'a uygular — sayfa yenilenmez.
    - Yönetim Paneli de aynı şekilde dinler; sadece kendi id'siyle eşleşen
      "#destek-talepleri-panel" bloğunu günceller (Destek İste akışı,
      madde 2 — koordinatöre "anlık bildirim").
    - Harita sayfası aynı mesajı ham WebSocket ile dinler; mesajın içeriğiyle
      ilgilenmez, sadece "bir şey değişti" sinyali olarak kullanıp
      /olaylar/harita/veri/ endpoint'ini tekrar çeker.
    - Görevim sayfası da aynı sinyali "sayfayı yenile" olarak kullanır.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return  # kanal katmanı yapılandırılmamışsa (ör. bazı test ortamları) sessizce geç

    ozet_html = render_to_string('dashboard/_ozet_icerik.html', ozet_baglami())
    destek_html = render_to_string('dashboard/_destek_talepleri.html', destek_talepleri_baglami())

    icerik = (
        f'<div id="dashboard-ozet" hx-swap-oob="true">{ozet_html}</div>'
        f'<div id="destek-talepleri-panel" hx-swap-oob="true">{destek_html}</div>'
    )

    async_to_sync(channel_layer.group_send)(
        GRUP_ADI,
        {'type': 'guncelleme.gonder', 'icerik': icerik},
    )
