from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render, resolve_url

from .decorators import kullanicinin_ana_sayfasi
from .forms import VatandasKayitFormu


def _canli_istatistikler() -> dict:
    """
    Login/Kayıt sayfalarının sol panelindeki 'canlı sistem durumu' şeridi
    için gerçek sayılar (mockup'taki gibi sabit/sahte değil). Buradaki
    import'lar fonksiyon içinde: hesaplar app'i diğer app'lere bağımlı
    olmasın, sadece bu görsel şerit için gerektiğinde çekiliyor.
    """
    from ekipler.models import Ekip
    from ihbarlar.models import Ihbar
    from olaylar.models import OlayKumesi

    return {
        'toplam_ihbar': Ihbar.objects.count(),
        'aktif_kume': OlayKumesi.objects.exclude(durum=OlayKumesi.Durum.TAMAMLANDI).count(),
        'sahadaki_ekip': Ekip.objects.exclude(durum=Ekip.Durum.BOSTA).count(),
    }


class RolBazliLoginView(LoginView):
    """
    Django'nun kendi LoginView'i; tek fark, sabit bir LOGIN_REDIRECT_URL
    yerine kullanıcının rolüne göre (koordinatör/saha ekip/vatandaş) doğru
    sayfaya yönlendirmesi. ?next= parametresi varsa (ör. korumalı bir
    sayfadan login'e düşüldüyse) LoginView'in kendi mantığı onu korur;
    biz sadece "next yoksa nereye gidilecek" varsayılanını değiştiriyoruz.
    """
    template_name = 'hesaplar/login.html'
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return resolve_url(kullanicinin_ana_sayfasi(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_canli_istatistikler())
        return context


def kayit(request):
    """
    Vatandaş öz-kayıt sayfası. Oluşturulan kullanıcı otomatik giriş yapar
    ve Vatandaş Paneli'ne yönlendirilir. is_staff=False, ekip bağlantısı yok.
    """
    if request.user.is_authenticated:
        return redirect(kullanicinin_ana_sayfasi(request.user))

    if request.method == 'POST':
        form = VatandasKayitFormu(request.POST)
        if form.is_valid():
            kullanici = form.kaydet()
            login(request, kullanici)
            return redirect('vatandas')
    else:
        form = VatandasKayitFormu()

    context = {'form': form}
    context.update(_canli_istatistikler())
    return render(request, 'hesaplar/kayit.html', context)
