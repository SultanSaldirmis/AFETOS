from django.shortcuts import get_object_or_404, render

from ekipler.models import Ekip
from ihbarlar.models import Ihbar
from olaylar.models import OlayKumesi

from .realtime import guncelleme_yayinla


def ana_panel(request):
    """
    Giriş / Ana Panel: genel durum özeti + en kritik olay kümeleri.
    Bu adımda canlı değil (statik render); WebSocket ile canlı güncelleme
    adım 7'de eklenecek.
    """
    aktif_kumeler = OlayKumesi.objects.exclude(durum=OlayKumesi.Durum.TAMAMLANDI)

    context = {
        'kritik_kumeler': aktif_kumeler.order_by('-oncelik_skoru')[:8],
        'toplam_ihbar_sayisi': Ihbar.objects.count(),
        'aktif_kume_sayisi': aktif_kumeler.count(),
        'dogrulaniyor_sayisi': aktif_kumeler.filter(durum=OlayKumesi.Durum.DOGRULANIYOR).count(),
        'mudahale_sayisi': aktif_kumeler.filter(durum=OlayKumesi.Durum.MUDAHALE_EDILIYOR).count(),
        'bosta_ekip_sayisi': Ekip.objects.filter(durum=Ekip.Durum.BOSTA).count(),
        'toplam_ekip_sayisi': Ekip.objects.count(),
    }
    return render(request, 'dashboard/ana_panel.html', context)


def yonetim_paneli(request):
    """
    Yönetim Paneli: durum filtreleme + her küme satırında durum güncelleme
    ve ekip atama formları (htmx ile partial güncelleme, sayfa yenilenmez).
    """
    kumeler = OlayKumesi.objects.select_related('atanan_ekip').all()

    secili_durum = request.GET.get('durum', '')
    if secili_durum:
        kumeler = kumeler.filter(durum=secili_durum)

    context = {
        'kumeler': kumeler,
        'durum_secenekleri': OlayKumesi.Durum.choices,
        'secili_durum': secili_durum,
        'ekipler': Ekip.objects.all(),
    }
    return render(request, 'dashboard/yonetim_paneli.html', context)


def _kume_satiri_render(request, kume):
    return render(request, 'dashboard/_kume_satiri.html', {
        'kume': kume,
        'durum_secenekleri': OlayKumesi.Durum.choices,
        'ekipler': Ekip.objects.all(),
    })


def kume_durum_guncelle(request, kume_id):
    """Bir olay kümesinin durumunu günceller (htmx POST, sadece ilgili satırı yeniden render eder)."""
    kume = get_object_or_404(OlayKumesi, id=kume_id)
    if request.method == 'POST':
        yeni_durum = request.POST.get('durum')
        gecerli_durumlar = dict(OlayKumesi.Durum.choices)
        if yeni_durum in gecerli_durumlar:
            kume.durum = yeni_durum
            kume.save(update_fields=['durum'])
            guncelleme_yayinla()
    return _kume_satiri_render(request, kume)


def kume_ekip_ata(request, kume_id):
    """
    Bir olay kümesine ekip atar: seçilen ekip 'gorevde' durumuna geçer ve
    kümeye bağlanır. Kümeden önce atanmış farklı bir ekip varsa serbest
    bırakılır (durum='bosta').
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

    return _kume_satiri_render(request, kume)
