from django.shortcuts import redirect, render

from dashboard.realtime import guncelleme_yayinla
from hesaplar.decorators import personel_gerekli, saha_ekip_gerekli
from olaylar.models import OlayKumesi

from .models import Ekip


@personel_gerekli
def liste(request):
    """
    Ekipler sayfası: KPI kartları (durum bazlı sayım) + tür filtre çipleri
    + tablo. Canlı güncelleme yok (proje kapsamı gereği sadece Ana Panel
    ve Harita canlı) — filtre değişince sayfa yeniden yüklenir.
    """
    tum_ekipler = Ekip.objects.select_related('mevcut_olay_kumesi')

    secili_tur = request.GET.get('tur', '')
    ekipler = tum_ekipler.filter(tur=secili_tur) if secili_tur else tum_ekipler
    ekipler = ekipler.order_by('tur', 'ad')

    context = {
        'ekipler': ekipler,
        'tur_secenekleri': Ekip.Tur.choices,
        'secili_tur': secili_tur,
        'kpi': {
            'toplam': tum_ekipler.count(),
            'bosta': tum_ekipler.filter(durum=Ekip.Durum.BOSTA).count(),
            'gorevde': tum_ekipler.filter(durum=Ekip.Durum.GOREVDE).count(),
            'yolda': tum_ekipler.filter(durum=Ekip.Durum.YOLDA).count(),
        },
    }
    return render(request, 'ekipler/liste.html', context)


@saha_ekip_gerekli
def gorevim(request):
    """
    Görevim sayfası (Saha Ekip Üyesi rolü): SADECE giriş yapan kullanıcının
    bağlı olduğu Ekip'in verisini gösterir — request.user.ekip üzerinden
    erişilir, başka bir ekibin verisi hiçbir şekilde sorgulanmaz/gösterilmez.
    """
    ekip = request.user.ekip
    kume = ekip.mevcut_olay_kumesi

    gorev_rozeti = {
        Ekip.Durum.YOLDA: {'bg': 'var(--high-bg)', 'border': 'rgba(240,138,36,.4)', 'renk': 'var(--high)', 'etiket': 'YOLDA'},
        Ekip.Durum.GOREVDE: {'bg': 'var(--med-bg)', 'border': 'rgba(62,139,214,.4)', 'renk': 'var(--med)', 'etiket': 'SAHADA'},
        Ekip.Durum.BOSTA: {'bg': 'var(--low-bg)', 'border': 'rgba(47,158,110,.4)', 'renk': 'var(--low)', 'etiket': 'BOŞTA'},
    }[ekip.durum]

    return render(request, 'ekipler/gorevim.html', {'ekip': ekip, 'kume': kume, 'rozet': gorev_rozeti})


@saha_ekip_gerekli
def gorevim_durum_guncelle(request):
    """
    Saha ekip üyesinin kendi görev adımını ilerletmesi: Yola Çıktım
    (durum=yolda) → Sahadayım (durum=gorevde) → Tamamlandı (küme
    'tamamlandi' olur, ekip serbest kalır/boşta döner). Sadece
    request.user.ekip üzerinde işlem yapar.
    """
    ekip = request.user.ekip
    if request.method == 'POST':
        adim = request.POST.get('adim')

        if adim == 'yolda':
            ekip.durum = Ekip.Durum.YOLDA
            ekip.save(update_fields=['durum'])

        elif adim == 'sahadayim':
            ekip.durum = Ekip.Durum.GOREVDE
            ekip.save(update_fields=['durum'])

        elif adim == 'tamamlandi' and ekip.mevcut_olay_kumesi is not None:
            kume = ekip.mevcut_olay_kumesi
            kume.durum = OlayKumesi.Durum.TAMAMLANDI
            kume.atanan_ekip = None
            kume.save(update_fields=['durum', 'atanan_ekip'])

            ekip.durum = Ekip.Durum.BOSTA
            ekip.mevcut_olay_kumesi = None
            ekip.save(update_fields=['durum', 'mevcut_olay_kumesi'])

            guncelleme_yayinla()  # Ana Panel/Harita'daki canlı dinleyicilere haber ver

    return redirect('gorevim')
