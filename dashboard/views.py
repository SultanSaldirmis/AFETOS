from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from ekipler.models import Ekip
from hesaplar.decorators import personel_gerekli
from ihbarlar.models import Ihbar
from olaylar.models import DestekTalebi, OlayKumesi

from .realtime import (
    destek_talepleri_baglami,
    guncelleme_yayinla,
    kume_ekip_onerileri,
    ozet_baglami,
)

# Öncelik seviyesi filtresi — theme.css'teki tier renk kodlarıyla (crit/
# high/med/low) aynı isimlendirme, skor aralıkları olaylar/models.py'deki
# oncelik_renk_kod property'siyle birebir eşleşiyor.
ONCELIK_SEVIYESI_ARALIKLARI = {
    'crit': (80, 100),
    'high': (60, 79),
    'med': (40, 59),
    'low': (0, 39),
}

SIRALAMA_SECENEKLERI = {
    'kritik': ('-oncelik_skoru', 'En Kritik'),
    'yeni': ('-olusturulma_zamani', 'En Yeni'),
    'guvenilir': ('-guven_skoru', 'En Güvenilir'),
}


@personel_gerekli
def ana_panel(request):
    """
    Giriş / Ana Panel: genel durum özeti + en kritik olay kümeleri +
    sağ sidebar (öncelik eşikleri / sistem durumu / son ihbarlar).
    Bağlam, realtime.ozet_baglami() ile aynı — WebSocket push'larıyla
    ilk sayfa yüklemesi arasında hesap tekrarı/sapması olmasın diye.
    """
    return render(request, 'dashboard/ana_panel.html', ozet_baglami())


def _yonetim_baglami(request, secili_kume):
    """Yönetim Paneli'nin sağ detay panelini render etmek için ortak bağlam (view + htmx partial'lar arasında paylaşılır)."""
    onerilen_ekipler, oneri_sebebi = ([], None)
    if secili_kume is not None:
        onerilen_ekipler, oneri_sebebi = kume_ekip_onerileri(secili_kume)
    return {
        'sel': secili_kume,
        'onerilen_ekipler': onerilen_ekipler,
        'oneri_sebebi': oneri_sebebi,
        'durum_secenekleri': OlayKumesi.Durum.choices,
        'ekipler_tumu': Ekip.objects.all(),
    }


@personel_gerekli
def yonetim_paneli(request):
    """
    Yönetim Paneli: sol tarafta filtrelenebilir/aranabilir/sıralanabilir
    olay listesi, sağ tarafta seçili olayın detayı + sistem önerisi, ayrıca
    bekleyen Destek Talepleri bölümü. Liste satırına tıklamak (htmx)
    sadece sağ paneli günceller, sayfa yenilenmez.
    """
    kumeler = OlayKumesi.objects.select_related('atanan_ekip').all()

    secili_durum = request.GET.get('durum', '')
    if secili_durum:
        kumeler = kumeler.filter(durum=secili_durum)

    secili_oncelik = request.GET.get('oncelik', '')
    if secili_oncelik in ONCELIK_SEVIYESI_ARALIKLARI:
        alt, ust = ONCELIK_SEVIYESI_ARALIKLARI[secili_oncelik]
        kumeler = kumeler.filter(oncelik_skoru__gte=alt, oncelik_skoru__lte=ust)

    secili_tur = request.GET.get('tur', '')
    if secili_tur:
        kumeler = kumeler.filter(ihbarlar__olay_turu=secili_tur).distinct()

    arama = request.GET.get('ara', '').strip()
    if arama:
        arama_filtresi = Q(ihbarlar__aciklama__icontains=arama) | Q(ihbarlar__olay_turu__icontains=arama)
        # "#42" ya da "42" gibi bir olay no'suyla da aranabilsin.
        sayisal_kisim = arama.lstrip('#')
        if sayisal_kisim.isdigit():
            arama_filtresi |= Q(id=int(sayisal_kisim))
        kumeler = kumeler.filter(arama_filtresi).distinct()

    secili_siralama = request.GET.get('sirala', 'kritik')
    siralama_alani = SIRALAMA_SECENEKLERI.get(secili_siralama, SIRALAMA_SECENEKLERI['kritik'])[0]
    kumeler = kumeler.order_by(siralama_alani)

    secili_id = request.GET.get('secili')
    secili_kume = None
    if secili_id:
        secili_kume = OlayKumesi.objects.filter(id=secili_id).first()
    if secili_kume is None:
        secili_kume = kumeler.first()

    context = {
        'kumeler': kumeler,
        'secili_durum': secili_durum,
        'secili_oncelik': secili_oncelik,
        'secili_tur': secili_tur,
        'arama': arama,
        'secili_siralama': secili_siralama,
        'durum_secenekleri': OlayKumesi.Durum.choices,
        'oncelik_secenekleri': [('crit', 'Kritik (80+)'), ('high', 'Yüksek (60–79)'), ('med', 'Orta (40–59)'), ('low', 'Düşük (<40)')],
        'olay_turu_secenekleri': Ihbar.OlayTuru.choices,
        'siralama_secenekleri': [(anahtar, etiket) for anahtar, (_, etiket) in SIRALAMA_SECENEKLERI.items()],
    }
    context.update(_yonetim_baglami(request, secili_kume))
    context.update(destek_talepleri_baglami())
    return render(request, 'dashboard/yonetim_paneli.html', context)


@personel_gerekli
def destek_talebi_guncelle(request, talebi_id):
    """
    Bir destek talebini işler: 'yonlendir' seçilen (boşta) ekibi o olay
    kümesine ek ekip olarak yollar (durum='yolda') ve talebi
    'yonlendirildi' yapar; 'kapat' talebi ek ekip göndermeden kapatır.
    Küme'nin ASIL atanan_ekip'i (ilk atama) değişmez — bu SADECE ek destek.
    """
    talep = get_object_or_404(DestekTalebi, id=talebi_id)
    if request.method == 'POST':
        eylem = request.POST.get('eylem')

        if eylem == 'yonlendir':
            ekip_id = request.POST.get('ekip_id')
            if ekip_id:
                ekip = get_object_or_404(Ekip, id=ekip_id)
                ekip.durum = Ekip.Durum.YOLDA
                ekip.mevcut_olay_kumesi = talep.olay_kumesi
                ekip.save(update_fields=['durum', 'mevcut_olay_kumesi'])
                talep.durum = DestekTalebi.Durum.YONLENDIRILDI
                talep.save(update_fields=['durum'])
                guncelleme_yayinla()

        elif eylem == 'kapat':
            talep.durum = DestekTalebi.Durum.KAPATILDI
            talep.save(update_fields=['durum'])
            guncelleme_yayinla()

    return render(request, 'dashboard/_destek_talepleri.html', destek_talepleri_baglami())


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
    Bir olay kümesine ekip atar: seçilen ekip 'yolda' durumuna geçer
    (dispatched — sahaya henüz varmadı) ve kümeye bağlanır. Kümeden önce
    atanmış farklı bir ekip varsa serbest bırakılır (durum='bosta').
    Küme hâlâ 'bekliyor'/'dogrulaniyor' durumundaysa 'mudahale_ediliyor'a
    geçer — atama fiilen müdahalenin başlaması demektir.

    "Öneriyi Uygula" butonu da bu endpoint'e (sistem önerisi listesindeki
    herhangi bir ekibin id'siyle) post eder.

    NOT: ekip.durum='yolda' olarak başlaması, Görevim sayfasındaki
    "Yola Çıktım → Sahadayım → Tamamlandı" 3 adımlı akışın tutarlı
    çalışması için gerekli — önceden doğrudan 'gorevde' atanıyordu, bu da
    ilk adımı anlamsız kılıyordu (bkz. iyileştirme promptu, adım 6a).
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
            if kume.durum in (OlayKumesi.Durum.BEKLIYOR, OlayKumesi.Durum.DOGRULANIYOR):
                kume.durum = OlayKumesi.Durum.MUDAHALE_EDILIYOR
            kume.save(update_fields=['atanan_ekip', 'durum'])

            ekip.durum = Ekip.Durum.YOLDA
            ekip.mevcut_olay_kumesi = kume
            ekip.save(update_fields=['durum', 'mevcut_olay_kumesi'])

            guncelleme_yayinla()

    return render(request, 'dashboard/_yonetim_detay.html', _yonetim_baglami(request, kume))
