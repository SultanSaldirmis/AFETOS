from collections import Counter

from django.shortcuts import get_object_or_404, render

from ekipler.models import Ekip
from ekipler.services import EkipAday, en_uygun_ekibi_oner
from hesaplar.decorators import personel_gerekli
from ihbarlar.models import Ihbar
from olaylar.models import OlayKumesi

from .realtime import guncelleme_yayinla, ozet_baglami


@personel_gerekli
def ana_panel(request):
    """
    Giriş / Ana Panel: genel durum özeti + en kritik olay kümeleri +
    sağ sidebar (öncelik eşikleri / sistem durumu / son ihbarlar).
    Bağlam, realtime.ozet_baglami() ile aynı — WebSocket push'larıyla
    ilk sayfa yüklemesi arasında hesap tekrarı/sapması olmasın diye.
    """
    return render(request, 'dashboard/ana_panel.html', ozet_baglami())


def _kume_onerisi(kume):
    """
    Bir olay kümesi için 'Sistem Önerisi' hesaplar: kümedeki baskın olay
    türüne ve boşta/mesafe uygunluğuna göre önerilen ekip + insan-okur
    bir gerekçe metni. ekipler.services (adım 5) mantığını yeniden
    kullanır — burada tekrar bir algoritma yazılmıyor.
    """
    ihbarlar = list(kume.ihbarlar.all())
    if not ihbarlar:
        return None, None

    baskin_tur = Counter(i.olay_turu for i in ihbarlar).most_common(1)[0][0]
    baskin_tur_gosterim = Ihbar.OlayTuru(baskin_tur).label

    ekip_adaylari = [
        EkipAday(id=e.id, tur=e.tur, lat=e.lat, lng=e.lng, durum=e.durum)
        for e in Ekip.objects.all()
    ]
    oneri = en_uygun_ekibi_oner(baskin_tur, kume.merkez_lat, kume.merkez_lng, ekip_adaylari)
    if oneri is None:
        return None, f'"{baskin_tur_gosterim}" türü için şu an boşta uygun ekip yok.'

    ekip = Ekip.objects.get(id=oneri.ekip_id)
    mesafe_km = oneri.mesafe_metre / 1000
    sebep = f'"{baskin_tur_gosterim}" türüne uygun, ~{mesafe_km:.1f} km mesafede ve boşta.'
    return ekip, sebep


def _yonetim_baglami(request, secili_kume):
    """Yönetim Paneli'nin sağ detay panelini render etmek için ortak bağlam (view + htmx partial'lar arasında paylaşılır)."""
    onerilen_ekip, oneri_sebebi = (None, None)
    if secili_kume is not None:
        onerilen_ekip, oneri_sebebi = _kume_onerisi(secili_kume)
    return {
        'sel': secili_kume,
        'onerilen_ekip': onerilen_ekip,
        'oneri_sebebi': oneri_sebebi,
        'durum_secenekleri': OlayKumesi.Durum.choices,
        'ekipler_tumu': Ekip.objects.all(),
    }


@personel_gerekli
def yonetim_paneli(request):
    """
    Yönetim Paneli: sol tarafta filtrelenebilir olay listesi, sağ tarafta
    seçili olayın detayı + sistem önerisi. Liste satırına tıklamak (htmx)
    sadece sağ paneli günceller, sayfa yenilenmez.
    """
    kumeler = OlayKumesi.objects.select_related('atanan_ekip').all()

    secili_durum = request.GET.get('durum', '')
    if secili_durum:
        kumeler = kumeler.filter(durum=secili_durum)

    secili_id = request.GET.get('secili')
    secili_kume = None
    if secili_id:
        secili_kume = OlayKumesi.objects.filter(id=secili_id).first()
    if secili_kume is None:
        secili_kume = kumeler.first()

    context = {
        'kumeler': kumeler,
        'secili_durum': secili_durum,
        'durum_secenekleri': OlayKumesi.Durum.choices,
    }
    context.update(_yonetim_baglami(request, secili_kume))
    return render(request, 'dashboard/yonetim_paneli.html', context)


@personel_gerekli
def kume_detay_partial(request, kume_id):
    """Sol listede bir satıra tıklanınca (htmx GET) sadece sağ detay panelini döner."""
    kume = get_object_or_404(OlayKumesi, id=kume_id)
    return render(request, 'dashboard/_yonetim_detay.html', _yonetim_baglami(request, kume))


@personel_gerekli
def kume_durum_guncelle(request, kume_id):
    """Bir olay kümesinin durumunu günceller (htmx POST) ve sağ detay panelini yeniden render eder."""
    kume = get_object_or_404(OlayKumesi, id=kume_id)
    if request.method == 'POST':
        yeni_durum = request.POST.get('durum')
        gecerli_durumlar = dict(OlayKumesi.Durum.choices)
        if yeni_durum in gecerli_durumlar:
            kume.durum = yeni_durum
            kume.save(update_fields=['durum'])
            guncelleme_yayinla()
    return render(request, 'dashboard/_yonetim_detay.html', _yonetim_baglami(request, kume))


@personel_gerekli
def kume_ekip_ata(request, kume_id):
    """
    Bir olay kümesine ekip atar: seçilen ekip 'gorevde' durumuna geçer ve
    kümeye bağlanır. Kümeden önce atanmış farklı bir ekip varsa serbest
    bırakılır (durum='bosta'). "Öneriyi Uygula" butonu da bu endpoint'e
    (sistem önerisinin ekip id'siyle) post eder.
    """
    kume = get_object_or_404(OlayKumesi, id=kume_id)
    if request.method == 'POST':
        ekip_id = request.POST.get('ekip_id')
        if ekip_id:
            ekip = get_object_or_404(Ekip, id=ekip_id)

            onceki_ekip = kume.atanan_ekip
            if onceki_ekip is not None and onceki_ekip.id != ekip.id:
                onceki_ekip.durum = Ekip.Durum.BOSTA
                onceki_ekip.mevcut_olay_kumesi = None
                onceki_ekip.save(update_fields=['durum', 'mevcut_olay_kumesi'])

            kume.atanan_ekip = ekip
            kume.save(update_fields=['atanan_ekip'])

            ekip.durum = Ekip.Durum.GOREVDE
            ekip.mevcut_olay_kumesi = kume
            ekip.save(update_fields=['durum', 'mevcut_olay_kumesi'])

            guncelleme_yayinla()

    return render(request, 'dashboard/_yonetim_detay.html', _yonetim_baglami(request, kume))
