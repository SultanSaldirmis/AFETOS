"""
3 rollü kimlik doğrulama/yetkilendirme mimarisi için testler:

  - Her rol girişten sonra doğru sayfaya yönleniyor mu?
  - Yanlış rol, yasak bir sayfaya girmeye çalışınca engelleniyor mu
    (403 ya da kendi sayfasına yönlendirme)?
  - Vatandaş SADECE kendi ihbarını görebiliyor mu?
  - Kayıt akışı doğru rolde (vatandaş) bir kullanıcı oluşturuyor mu?
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ekipler.models import Ekip
from ihbarlar.models import Ihbar

from .forms import tc_kimlik_no_gecerli_mi

User = get_user_model()


class GirisYonlendirmeTestleri(TestCase):
    """Her rol, login sonrası kendi ana sayfasına yönlenmeli."""

    def setUp(self):
        self.koordinator = User.objects.create_user(username='koordinator1', password='demo1234', is_staff=True)

        self.ekip = Ekip.objects.create(ad='Test Ekip', tur=Ekip.Tur.SAGLIK, lat=37.0, lng=37.0)
        self.saha_user = User.objects.create_user(username='saha1', password='demo1234')
        self.ekip.user = self.saha_user
        self.ekip.save(update_fields=['user'])

        self.vatandas_user = User.objects.create_user(username='5551112233', password='demo1234')

    def test_koordinator_ana_panele_yonlenir(self):
        yanit = self.client.post(reverse('login'), {'username': 'koordinator1', 'password': 'demo1234'})
        self.assertRedirects(yanit, reverse('dashboard:ana_panel'))

    def test_saha_ekip_uyesi_gorevime_yonlenir(self):
        yanit = self.client.post(reverse('login'), {'username': 'saha1', 'password': 'demo1234'})
        self.assertRedirects(yanit, reverse('gorevim'))

    def test_vatandas_vatandas_paneline_yonlenir(self):
        yanit = self.client.post(reverse('login'), {'username': '5551112233', 'password': 'demo1234'})
        self.assertRedirects(yanit, reverse('vatandas'))


class ErisimKontrolTestleri(TestCase):
    """Yanlış rol, yasak bir sayfaya giremiyor mu?"""

    def setUp(self):
        self.koordinator = User.objects.create_user(username='koordinator1', password='demo1234', is_staff=True)

        self.ekip = Ekip.objects.create(ad='Test Ekip', tur=Ekip.Tur.SAGLIK, lat=37.0, lng=37.0)
        self.saha_user = User.objects.create_user(username='saha1', password='demo1234')
        self.ekip.user = self.saha_user
        self.ekip.save(update_fields=['user'])

        self.vatandas_user = User.objects.create_user(username='5551112233', password='demo1234')

    def test_vatandas_yonetim_paneline_giremez(self):
        self.client.force_login(self.vatandas_user)
        yanit = self.client.get(reverse('dashboard:yonetim_paneli'))
        # personel_gerekli: staff değilse kendi ana sayfasına (vatandas) yönlendirir.
        self.assertRedirects(yanit, reverse('vatandas'))

    def test_saha_ekip_uyesi_ana_panele_giremez(self):
        self.client.force_login(self.saha_user)
        yanit = self.client.get(reverse('dashboard:ana_panel'))
        self.assertRedirects(yanit, reverse('gorevim'))

    def test_vatandas_gorevim_sayfasina_giremez(self):
        self.client.force_login(self.vatandas_user)
        yanit = self.client.get(reverse('gorevim'))
        self.assertRedirects(yanit, reverse('vatandas'))

    def test_koordinator_yonetim_paneline_girebilir(self):
        self.client.force_login(self.koordinator)
        yanit = self.client.get(reverse('dashboard:yonetim_paneli'))
        self.assertEqual(yanit.status_code, 200)

    def test_giris_yapmamis_kullanici_login_e_yonlendirilir(self):
        yanit = self.client.get(reverse('dashboard:ana_panel'))
        self.assertRedirects(yanit, f"{reverse('login')}?next={reverse('dashboard:ana_panel')}")

    def test_saha_ekip_uyesi_baska_ekibin_verisini_goremez(self):
        """
        gorevim view'ı SADECE request.user.ekip'i kullanmalı; başka bir
        ekibin adı/skoru sızdırılmamalı.
        """
        diger_ekip = Ekip.objects.create(ad='Başka Ekip', tur=Ekip.Tur.ARAMA_KURTARMA, lat=38.0, lng=38.0)

        self.client.force_login(self.saha_user)
        yanit = self.client.get(reverse('gorevim'))

        self.assertContains(yanit, 'Test Ekip')
        self.assertNotContains(yanit, 'Başka Ekip')


class VatandasIzolasyonTestleri(TestCase):
    """Vatandaş Paneli, kullanıcının SADECE kendi ihbarlarını göstermeli."""

    def setUp(self):
        self.vatandas_1 = User.objects.create_user(username='5551112233', password='demo1234')
        self.vatandas_2 = User.objects.create_user(username='5551112244', password='demo1234')

        self.ihbar_1 = Ihbar.objects.create(
            lat=37.0, lng=37.0, olay_turu=Ihbar.OlayTuru.YANGIN,
            aciklama='Vatandaş 1 ihbarı', bildiren=self.vatandas_1,
        )
        self.ihbar_2 = Ihbar.objects.create(
            lat=38.0, lng=38.0, olay_turu=Ihbar.OlayTuru.TIBBI,
            aciklama='Vatandaş 2 ihbarı', bildiren=self.vatandas_2,
        )

    def test_vatandas_sadece_kendi_ihbarini_gorur(self):
        self.client.force_login(self.vatandas_1)
        yanit = self.client.get(reverse('vatandas'))

        # Not: "Tıbbi" gibi olay türü isimlerini metinde aramak güvenilir
        # değil çünkü formdaki <select> seçenekleri de aynı kelimeleri
        # içeriyor (veriden bağımsız olarak). Bunun yerine view'ın
        # context'ine bakıp gerçekten hangi ihbarların döndüğünü kontrol
        # ediyoruz — bu, izolasyonu doğrudan ve yanlış-pozitifsiz test eder.
        self.assertEqual(list(yanit.context['ihbarlarim']), [self.ihbar_1])

    def test_vatandas_yeni_ihbar_gonderince_bildiren_otomatik_atanir(self):
        self.client.force_login(self.vatandas_1)
        self.client.post(reverse('vatandas'), {
            'lat': '37.5', 'lng': '37.5', 'olay_turu': 'enkaz',
            'aciklama': 'Yeni test ihbarı', 'tahmini_kisi_sayisi': 3, 'tahmini_yarali_sayisi': 1,
        })
        yeni_ihbar = Ihbar.objects.get(aciklama='Yeni test ihbarı')
        self.assertEqual(yeni_ihbar.bildiren, self.vatandas_1)


class KayitTestleri(TestCase):
    """Öz-kayıt akışı doğru rolde (vatandaş) bir kullanıcı oluşturmalı."""

    def test_kayit_vatandas_olusturur_ve_otomatik_giris_yapar(self):
        yanit = self.client.post(reverse('kayit'), {
            'ad_soyad': 'Yeni Vatandaş', 'telefon': '05559998877', 'tc_kimlik_no': '10000000146',
            'sifre': 'guclu-sifre-123', 'sifre_tekrar': 'guclu-sifre-123',
        })
        self.assertRedirects(yanit, reverse('vatandas'))

        kullanici = User.objects.get(username='05559998877')
        self.assertFalse(kullanici.is_staff)
        self.assertFalse(hasattr(kullanici, 'ekip') and kullanici.ekip is not None)
        self.assertEqual(kullanici.vatandas_profili.tc_kimlik_no, '10000000146')

        # Otomatik giriş yapıldığını, oturumun kurulduğunu doğrula.
        yanit2 = self.client.get(reverse('vatandas'))
        self.assertEqual(yanit2.status_code, 200)

    def test_ayni_telefonla_ikinci_kayit_reddedilir(self):
        User.objects.create_user(username='05551112233', password='demo1234')
        yanit = self.client.post(reverse('kayit'), {
            'ad_soyad': 'Tekrar Deneme', 'telefon': '05551112233', 'tc_kimlik_no': '10000000146',
            'sifre': 'guclu-sifre-123', 'sifre_tekrar': 'guclu-sifre-123',
        })
        self.assertEqual(yanit.status_code, 200)  # forma geri döner, kayıt olmaz
        self.assertContains(yanit, 'Bu telefon numarasıyla zaten bir hesap var.')
        self.assertEqual(User.objects.filter(username='05551112233').count(), 1)

    def test_geersiz_telefon_formati_reddedilir(self):
        yanit = self.client.post(reverse('kayit'), {
            'ad_soyad': 'Format Testi', 'telefon': '12345', 'tc_kimlik_no': '10000000146',
            'sifre': 'guclu-sifre-123', 'sifre_tekrar': 'guclu-sifre-123',
        })
        self.assertContains(yanit, 'Geçerli bir telefon numarası girin.')
        self.assertFalse(User.objects.filter(username='12345').exists())

    def test_eslesmeyen_sifreler_reddedilir(self):
        yanit = self.client.post(reverse('kayit'), {
            'ad_soyad': 'Şifre Testi', 'telefon': '05551239999', 'tc_kimlik_no': '10000000146',
            'sifre': 'guclu-sifre-123', 'sifre_tekrar': 'baska-sifre-456',
        })
        self.assertContains(yanit, 'Şifreler eşleşmiyor.')
        self.assertFalse(User.objects.filter(username='05551239999').exists())

    def test_kisa_sifre_reddedilir(self):
        yanit = self.client.post(reverse('kayit'), {
            'ad_soyad': 'Kısa Şifre', 'telefon': '05551230000', 'tc_kimlik_no': '10000000146',
            'sifre': 'kisa1', 'sifre_tekrar': 'kisa1',
        })
        self.assertEqual(yanit.status_code, 200)
        self.assertFalse(User.objects.filter(username='05551230000').exists())

    def test_gecersiz_tc_kimlik_no_reddedilir(self):
        yanit = self.client.post(reverse('kayit'), {
            'ad_soyad': 'TC Testi', 'telefon': '05551111111', 'tc_kimlik_no': '12345678901',
            'sifre': 'guclu-sifre-123', 'sifre_tekrar': 'guclu-sifre-123',
        })
        self.assertContains(yanit, 'Geçerli bir TC Kimlik Numarası girin.')
        self.assertFalse(User.objects.filter(username='05551111111').exists())

    def test_ayni_tc_kimlik_no_ile_ikinci_kayit_reddedilir(self):
        ilk = self.client.post(reverse('kayit'), {
            'ad_soyad': 'İlk Kişi', 'telefon': '05552220001', 'tc_kimlik_no': '10000000146',
            'sifre': 'guclu-sifre-123', 'sifre_tekrar': 'guclu-sifre-123',
        })
        self.assertRedirects(ilk, reverse('vatandas'))
        self.client.logout()

        ikinci = self.client.post(reverse('kayit'), {
            'ad_soyad': 'İkinci Kişi', 'telefon': '05552220002', 'tc_kimlik_no': '10000000146',
            'sifre': 'guclu-sifre-123', 'sifre_tekrar': 'guclu-sifre-123',
        })
        self.assertContains(ikinci, 'Bu TC Kimlik Numarasıyla zaten bir hesap var.')
        self.assertFalse(User.objects.filter(username='05552220002').exists())


class TcKimlikNoValidasyonTestleri(TestCase):
    """
    tc_kimlik_no_gecerli_mi — saf Python, resmi checksum algoritması.
    '10000000146' bilinen/yaygın kullanılan geçerli-formatlı bir örnek
    numaradır (gerçek bir kişiye ait değildir, sadece algoritmik olarak
    geçerlidir — bkz. fonksiyonun docstring'i).
    """

    def test_gecerli_tc_kabul_edilir(self):
        self.assertTrue(tc_kimlik_no_gecerli_mi('10000000146'))

    def test_11_haneden_kisa_reddedilir(self):
        self.assertFalse(tc_kimlik_no_gecerli_mi('123456789'))

    def test_11_haneden_uzun_reddedilir(self):
        self.assertFalse(tc_kimlik_no_gecerli_mi('123456789012'))

    def test_rakam_olmayan_karakter_reddedilir(self):
        self.assertFalse(tc_kimlik_no_gecerli_mi('1000000014a'))

    def test_ilk_hane_sifir_olamaz(self):
        self.assertFalse(tc_kimlik_no_gecerli_mi('01000000146'))

    def test_yanlis_checksum_reddedilir(self):
        # Son haneyi bozarak checksum'ı geçersiz kılıyoruz.
        self.assertFalse(tc_kimlik_no_gecerli_mi('10000000147'))


class LogoutTestleri(TestCase):
    """
    Django 4.1+'ta LogoutView sadece POST kabul ediyor. Tüm sayfalardaki
    çıkış linkleri <form method="post"> olmalı (GET/<a href> ile 405
    döner ve buton "çalışmıyormuş" gibi görünür — bkz. iyileştirme
    promptu adım 6b). Her üç rol için de gerçek oturum sonlandırmayı
    ve /login/'e yönlendirmeyi doğruluyoruz.
    """

    def setUp(self):
        self.koordinator = User.objects.create_user(username='koordinator1', password='demo1234', is_staff=True)

        self.ekip = Ekip.objects.create(ad='Test Ekip', tur=Ekip.Tur.SAGLIK, lat=37.0, lng=37.0)
        self.saha_user = User.objects.create_user(username='saha1', password='demo1234')
        self.ekip.user = self.saha_user
        self.ekip.save(update_fields=['user'])

        self.vatandas_user = User.objects.create_user(username='5551112233', password='demo1234')

    def _oturumu_sonlandirir_ve_login_e_yonlendirir(self, kullanici):
        self.client.force_login(kullanici)

        # GET ile logout artık 405 vermeli (Django 4.1+ varsayılanı) —
        # bu, template'lerde <a href="/logout/"> KULLANILMADIĞININ dolaylı
        # kanıtı; asıl kanıt POST'un başarıyla oturumu kapatması.
        get_yaniti = self.client.get(reverse('logout'))
        self.assertEqual(get_yaniti.status_code, 405)

        post_yaniti = self.client.post(reverse('logout'))
        self.assertRedirects(post_yaniti, reverse('login'))

        # Oturum gerçekten kapandı mı? Korumalı bir sayfa artık login'e düşmeli.
        kontrol = self.client.get(reverse('dashboard:ana_panel'))
        self.assertRedirects(kontrol, f"{reverse('login')}?next={reverse('dashboard:ana_panel')}")

    def test_koordinator_logout_yapabilir(self):
        self._oturumu_sonlandirir_ve_login_e_yonlendirir(self.koordinator)

    def test_saha_ekip_uyesi_logout_yapabilir(self):
        self._oturumu_sonlandirir_ve_login_e_yonlendirir(self.saha_user)

    def test_vatandas_logout_yapabilir(self):
        self._oturumu_sonlandirir_ve_login_e_yonlendirir(self.vatandas_user)

    def test_gorevim_sayfasinda_post_form_ile_cikis_linki_var(self):
        """Görevim'de (önceden hiç çıkış imkânı yoktu) artık bir POST formu olmalı."""
        self.client.force_login(self.saha_user)
        yanit = self.client.get(reverse('gorevim'))
        self.assertContains(yanit, f'action="{reverse("logout")}"')
        self.assertContains(yanit, 'method="post"')
