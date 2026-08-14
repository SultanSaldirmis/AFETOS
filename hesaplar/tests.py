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
            'ad_soyad': 'Yeni Vatandaş', 'telefon': '05559998877',
            'sifre': 'guclu-sifre-123', 'sifre_tekrar': 'guclu-sifre-123',
        })
        self.assertRedirects(yanit, reverse('vatandas'))

        kullanici = User.objects.get(username='05559998877')
        self.assertFalse(kullanici.is_staff)
        self.assertFalse(hasattr(kullanici, 'ekip') and kullanici.ekip is not None)

        # Otomatik giriş yapıldığını, oturumun kurulduğunu doğrula.
        yanit2 = self.client.get(reverse('vatandas'))
        self.assertEqual(yanit2.status_code, 200)

    def test_ayni_telefonla_ikinci_kayit_reddedilir(self):
        User.objects.create_user(username='05551112233', password='demo1234')
        yanit = self.client.post(reverse('kayit'), {
            'ad_soyad': 'Tekrar Deneme', 'telefon': '05551112233',
            'sifre': 'guclu-sifre-123', 'sifre_tekrar': 'guclu-sifre-123',
        })
        self.assertEqual(yanit.status_code, 200)  # forma geri döner, kayıt olmaz
        self.assertContains(yanit, 'Bu telefon numarasıyla zaten bir hesap var.')
        self.assertEqual(User.objects.filter(username='05551112233').count(), 1)

    def test_geersiz_telefon_formati_reddedilir(self):
        yanit = self.client.post(reverse('kayit'), {
            'ad_soyad': 'Format Testi', 'telefon': '12345',
            'sifre': 'guclu-sifre-123', 'sifre_tekrar': 'guclu-sifre-123',
        })
        self.assertContains(yanit, 'Geçerli bir telefon numarası girin.')
        self.assertFalse(User.objects.filter(username='12345').exists())

    def test_eslesmeyen_sifreler_reddedilir(self):
        yanit = self.client.post(reverse('kayit'), {
            'ad_soyad': 'Şifre Testi', 'telefon': '05551239999',
            'sifre': 'guclu-sifre-123', 'sifre_tekrar': 'baska-sifre-456',
        })
        self.assertContains(yanit, 'Şifreler eşleşmiyor.')
        self.assertFalse(User.objects.filter(username='05551239999').exists())

    def test_kisa_sifre_reddedilir(self):
        yanit = self.client.post(reverse('kayit'), {
            'ad_soyad': 'Kısa Şifre', 'telefon': '05551230000',
            'sifre': 'kisa1', 'sifre_tekrar': 'kisa1',
        })
        self.assertEqual(yanit.status_code, 200)
        self.assertFalse(User.objects.filter(username='05551230000').exists())
