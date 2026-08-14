from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from dashboard.realtime import guncelleme_yayinla
from ekipler.models import Ekip
from ekipler.services import EkipAday, en_uygun_ekibi_oner
from hesaplar.decorators import personel_gerekli
from olaylar.scoring import dogrulama_gerekli_mi

from .forms import IhbarForm
from .models import Ihbar
from .services import ihbari_kumeye_ata


@personel_gerekli
def olustur(request):
    """
    Yeni ihbar oluşturma sayfası (htmx ile gönderilir). Kayıt başarılıysa
    ihbar, kümeleme servisi (adım 4) ile bir olay kümesine atanır ve
    kullanıcı ihbar detay sayfasına yönlendirilir.
    """
    if request.method == 'POST':
        form = IhbarForm(request.POST, request.FILES)
        if form.is_valid():
            ihbar = form.save()
            ihbari_kumeye_ata(ihbar)
            guncelleme_yayinla()

            detay_url = reverse('ihbarlar:detay', args=[ihbar.id])
            if request.headers.get('HX-Request'):
                # htmx'e tam sayfa yönlendirmesi yaptırıyoruz.
                response = render(request, 'ihbarlar/_yonlendiriliyor.html')
                response['HX-Redirect'] = detay_url
                return response
            return redirect(detay_url)

        # Form geçersiz: htmx isteğiyse sadece form parçasını, değilse
        # tüm sayfayı hatalarla birlikte yeniden render et.
        if request.headers.get('HX-Request'):
            return render(request, 'ihbarlar/_form.html', {'form': form})
        return render(request, 'ihbarlar/olustur.html', {'form': form})

    form = IhbarForm()
    return render(request, 'ihbarlar/olustur.html', {'form': form})


@personel_gerekli
def detay(request, ihbar_id):
    """
    İhbar detay sayfası: ihbar bilgileri + (varsa) bağlı olduğu olay
    kümesinin güven/öncelik skoru, durumu ve önerilen ekip.

    Operatör/koordinatör sayfasıdır (Ana Panel, Harita, Yönetim'deki
    "Detay" linklerinden ulaşılır); vatandaşlar kendi ihbarlarını
    /vatandas/ üzerinden görür, bu sayfayı görmez.
    """
    ihbar = get_object_or_404(Ihbar, id=ihbar_id)
    kume = ihbar.olay_kumesi

    onerilen_ekip = None
    if kume is not None:
        ekip_adaylari = [
            EkipAday(id=e.id, tur=e.tur, lat=e.lat, lng=e.lng, durum=e.durum)
            for e in Ekip.objects.all()
        ]
        oneri = en_uygun_ekibi_oner(ihbar.olay_turu, kume.merkez_lat, kume.merkez_lng, ekip_adaylari)
        if oneri is not None:
            onerilen_ekip = Ekip.objects.get(id=oneri.ekip_id)

    context = {
        'ihbar': ihbar,
        'kume': kume,
        'onerilen_ekip': onerilen_ekip,
        'dogrulama_gerekli': dogrulama_gerekli_mi(kume.guven_skoru) if kume else False,
    }
    return render(request, 'ihbarlar/detay.html', context)


@login_required
def vatandas(request):
    """
    Vatandaş Paneli: kullanıcının kendi bildirdiği ihbarların listesi +
    yeni ihbar oluşturma formu. GET'te sadece bildiren=request.user olan
    kayıtlar listelenir (başka vatandaşın ihbarı asla gösterilmez);
    POST'ta yeni ihbara bildiren otomatik atanır.
    """
    if request.method == 'POST':
        form = IhbarForm(request.POST, request.FILES)
        if form.is_valid():
            ihbar = form.save(commit=False)
            ihbar.bildiren = request.user
            ihbar.save()
            ihbari_kumeye_ata(ihbar)
            guncelleme_yayinla()

            if request.headers.get('HX-Request'):
                # htmx'e tam sayfa yönlendirmesi yaptırıyoruz (liste sekmesi
                # de tazelensin diye tüm sayfa yeniden yüklenir).
                response = render(request, 'ihbarlar/_yonlendiriliyor.html')
                response['HX-Redirect'] = reverse('vatandas')
                return response
            return redirect('vatandas')

        # Form geçersiz: htmx isteğiyse sadece form parçasını yeniden render et.
        if request.headers.get('HX-Request'):
            return render(request, 'ihbarlar/_vatandas_form.html', {'form': form})
    else:
        form = IhbarForm()

    kendi_ihbarlarim = Ihbar.objects.filter(bildiren=request.user)
    return render(request, 'ihbarlar/vatandas.html', {'form': form, 'ihbarlarim': kendi_ihbarlarim})
