"""
ihbarlar/services.py içindeki kümeleme orkestrasyonu için testler.

Bu testler, matematiksel/hesaplama mantığının kendisini değil (o zaten
olaylar/tests.py içinde saf fonksiyon seviyesinde test edildi), DB ile
etkileşimin doğru çalıştığını doğrular: yeni küme açma, mevcut kümeye
ekleme, merkez güncelleme, skorların güncellenmesi.
"""
import io
import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from olaylar.models import OlayKumesi

from .forms import IhbarForm
from .models import Ihbar
from .services import ihbari_kumeye_ata


class IhbariKumeyeAtaTestleri(TestCase):

    def test_ilk_ihbar_yeni_kume_acar(self):
        ihbar = Ihbar.objects.create(
            lat=37.0600, lng=37.3800, olay_turu='enkaz',
            aciklama='Enkaz altında insanlar var, kurtarma bekleniyor.',
            tahmini_kisi_sayisi=5, tahmini_yarali_sayisi=1,
        )
        kume = ihbari_kumeye_ata(ihbar)

        self.assertEqual(OlayKumesi.objects.count(), 1)
        ihbar.refresh_from_db()
        self.assertEqual(ihbar.olay_kumesi_id, kume.id)
        self.assertEqual(kume.merkez_lat, 37.0600)
        self.assertEqual(kume.merkez_lng, 37.3800)

    def test_yakin_ihbar_mevcut_kumeye_eklenir(self):
        ilk_ihbar = Ihbar.objects.create(
            lat=37.0600, lng=37.3800, olay_turu='enkaz',
            aciklama='Enkaz altında insanlar var.', tahmini_kisi_sayisi=5,
        )
        ilk_kume = ihbari_kumeye_ata(ilk_ihbar)

        # ~10-20 metre kayma, KUMELEME_YARICAPI_METRE (400m) içinde kalmalı.
        ikinci_ihbar = Ihbar.objects.create(
            lat=37.0601, lng=37.3801, olay_turu='enkaz',
            aciklama='Enkaz altından ses geliyor.', tahmini_kisi_sayisi=3,
        )
        ikinci_kume = ihbari_kumeye_ata(ikinci_ihbar)

        self.assertEqual(OlayKumesi.objects.count(), 1)
        self.assertEqual(ilk_kume.id, ikinci_kume.id)
        self.assertEqual(ikinci_kume.ihbarlar.count(), 2)

    def test_uzak_ihbar_yeni_kume_acar(self):
        Ihbar.objects.create(
            lat=37.0600, lng=37.3800, olay_turu='enkaz',
            aciklama='Enkaz altında insanlar var.', tahmini_kisi_sayisi=5,
        )
        ilk_ihbar = Ihbar.objects.first()
        ihbari_kumeye_ata(ilk_ihbar)

        # ~1 derece enlem farkı ~111km, yarıçapın çok dışında -> yeni küme.
        uzak_ihbar = Ihbar.objects.create(
            lat=38.0600, lng=37.3800, olay_turu='yangin',
            aciklama='Yangın var, alevler büyüyor.', tahmini_kisi_sayisi=2,
        )
        ihbari_kumeye_ata(uzak_ihbar)

        self.assertEqual(OlayKumesi.objects.count(), 2)

    def test_kume_skorlari_ihbar_eklendikce_guncellenir(self):
        ihbar = Ihbar.objects.create(
            lat=37.0600, lng=37.3800, olay_turu='tibbi',
            aciklama='Yaralı var, kanama mevcut, ambulans gerekiyor.',
            tahmini_kisi_sayisi=10, tahmini_yarali_sayisi=5,
        )
        kume = ihbari_kumeye_ata(ihbar)

        self.assertGreater(kume.guven_skoru, 0)
        self.assertGreater(kume.oncelik_skoru, 0)
        self.assertLessEqual(kume.guven_skoru, 100)
        self.assertLessEqual(kume.oncelik_skoru, 100)

    def test_dusuk_guven_skorlu_kume_dogrulaniyor_olarak_isaretlenir_ve_silinmez(self):
        # Tek, olay türüyle alakasız bir açıklama -> düşük güven skoru
        # bekleniyor -> küme SİLİNMEMELİ, sadece 'dogrulaniyor' olmalı.
        ihbar = Ihbar.objects.create(
            lat=37.0600, lng=37.3800, olay_turu='yangin',
            aciklama='bugün hava çok güzeldi', tahmini_kisi_sayisi=0,
        )
        kume = ihbari_kumeye_ata(ihbar)

        self.assertTrue(OlayKumesi.objects.filter(id=kume.id).exists())
        if kume.guven_skoru < 50:
            self.assertEqual(kume.durum, OlayKumesi.Durum.DOGRULANIYOR)

    def test_aynı_konumda_farkli_turler_ayri_kume_acar(self):
        # Madde 3: mesafe uysa bile olay_turu uymuyorsa AYNI kümeye eklenmez.
        yangin_ihbar = Ihbar.objects.create(
            lat=37.0600, lng=37.3800, olay_turu='yangin',
            aciklama='Yangın var, alevler büyüyor.', tahmini_kisi_sayisi=2,
        )
        ihbari_kumeye_ata(yangin_ihbar)

        # Aynı konum (~10m kayma), farklı tür (tibbi) -> yeni küme açılmalı.
        tibbi_ihbar = Ihbar.objects.create(
            lat=37.0601, lng=37.3801, olay_turu='tibbi',
            aciklama='Yaralı var, kanama mevcut.', tahmini_kisi_sayisi=1,
        )
        tibbi_kume = ihbari_kumeye_ata(tibbi_ihbar)

        self.assertEqual(OlayKumesi.objects.count(), 2)
        self.assertEqual(tibbi_kume.ihbarlar.count(), 1)

    def test_aynı_konumda_ayni_turler_ayni_kumede_birlesir(self):
        ilk = Ihbar.objects.create(
            lat=37.0600, lng=37.3800, olay_turu='yangin',
            aciklama='Yangın var, alevler büyüyor.', tahmini_kisi_sayisi=2,
        )
        ilk_kume = ihbari_kumeye_ata(ilk)

        ikinci = Ihbar.objects.create(
            lat=37.0601, lng=37.3801, olay_turu='yangin',
            aciklama='Duman her yeri kapladı.', tahmini_kisi_sayisi=1,
        )
        ikinci_kume = ihbari_kumeye_ata(ikinci)

        self.assertEqual(OlayKumesi.objects.count(), 1)
        self.assertEqual(ilk_kume.id, ikinci_kume.id)
        self.assertEqual(ikinci_kume.ihbarlar.count(), 2)

    def test_tamamlanmis_kumeye_yeni_ihbar_eklenmez(self):
        ihbar = Ihbar.objects.create(
            lat=37.0600, lng=37.3800, olay_turu='enkaz',
            aciklama='Enkaz altında insanlar var.', tahmini_kisi_sayisi=5,
        )
        kume = ihbari_kumeye_ata(ihbar)
        kume.durum = OlayKumesi.Durum.TAMAMLANDI
        kume.save()

        yeni_ihbar = Ihbar.objects.create(
            lat=37.0601, lng=37.3801, olay_turu='enkaz',
            aciklama='Enkaz altında insanlar var.', tahmini_kisi_sayisi=2,
        )
        yeni_kume = ihbari_kumeye_ata(yeni_ihbar)

        self.assertNotEqual(kume.id, yeni_kume.id)
        self.assertEqual(OlayKumesi.objects.count(), 2)


class IhbarFormValidasyonTestleri(TestCase):
    """
    IhbarForm sunucu taraflı validasyon kuralları — hem operatör hem
    vatandaş sayfası bu formu kullanıyor, testler ortak.
    """

    def _gecerli_veri(self, **override):
        veri = {
            'lat': 39.0, 'lng': 35.0, 'olay_turu': 'enkaz',
            'aciklama': 'Enkaz altında insanlar var, yardım gerekiyor.',
            'tahmini_kisi_sayisi': 5, 'tahmini_yarali_sayisi': 2,
        }
        veri.update(override)
        return veri

    @staticmethod
    def _resim_dosyasi(ad, format, content_type, boyut=(10, 10)):
        """
        Testler için GERÇEK, Pillow'un doğrulayabileceği bir görüntü dosyası
        üretir. Django'nun ImageField'i, formumuzun clean_fotograf'ından
        ÖNCE Pillow ile "bu gerçek bir resim mi" kontrolü yapıyor — rastgele
        bayt dizisi bu kontrolden geçemez, o yüzden sahte içerik kullanamayız.
        """
        arabellek = io.BytesIO()
        Image.new('RGB', boyut, color=(255, 0, 0)).save(arabellek, format=format)
        arabellek.seek(0)
        return SimpleUploadedFile(ad, arabellek.read(), content_type=content_type)

    def test_gecerli_veri_kabul_edilir(self):
        form = IhbarForm(data=self._gecerli_veri())
        self.assertTrue(form.is_valid(), form.errors)

    def test_turkiye_disi_lat_reddedilir(self):
        form = IhbarForm(data=self._gecerli_veri(lat=10.0))  # ör. ekvator civarı
        self.assertFalse(form.is_valid())
        self.assertIn('Konum Türkiye sınırları dışında görünüyor.', form.errors['lat'])

    def test_turkiye_disi_lng_reddedilir(self):
        form = IhbarForm(data=self._gecerli_veri(lng=100.0))
        self.assertFalse(form.is_valid())
        self.assertIn('Konum Türkiye sınırları dışında görünüyor.', form.errors['lng'])

    def test_negatif_kisi_sayisi_reddedilir(self):
        form = IhbarForm(data=self._gecerli_veri(tahmini_kisi_sayisi=-1))
        self.assertFalse(form.is_valid())
        self.assertIn('Kişi sayısı negatif olamaz.', form.errors['tahmini_kisi_sayisi'])

    def test_negatif_yarali_sayisi_reddedilir(self):
        form = IhbarForm(data=self._gecerli_veri(tahmini_yarali_sayisi=-1))
        self.assertFalse(form.is_valid())
        self.assertIn('Yaralı sayısı negatif olamaz.', form.errors['tahmini_yarali_sayisi'])

    def test_yarali_sayisi_kisi_sayisini_asamaz(self):
        form = IhbarForm(data=self._gecerli_veri(tahmini_kisi_sayisi=3, tahmini_yarali_sayisi=5))
        self.assertFalse(form.is_valid())
        self.assertIn('Yaralı sayısı toplam kişi sayısını aşamaz.', form.errors['tahmini_yarali_sayisi'])

    def test_kisa_aciklama_reddedilir(self):
        form = IhbarForm(data=self._gecerli_veri(aciklama='çok kısa'))
        self.assertFalse(form.is_valid())
        self.assertTrue(any('en az' in hata for hata in form.errors['aciklama']))

    def test_bos_olay_turu_reddedilir(self):
        form = IhbarForm(data=self._gecerli_veri(olay_turu=''))
        self.assertFalse(form.is_valid())
        self.assertIn('olay_turu', form.errors)

    def test_buyuk_fotograf_reddedilir(self):
        # Rastgele (yüksek entropili) piksel verisi PNG'de neredeyse hiç
        # sıkışmaz, bu yüzden gerçek bir 5MB+ dosya üretmek için kullanılır.
        boyut = (1500, 1500)
        rastgele_veri = os.urandom(boyut[0] * boyut[1] * 3)
        gorsel = Image.frombytes('RGB', boyut, rastgele_veri)
        arabellek = io.BytesIO()
        gorsel.save(arabellek, format='PNG')
        arabellek.seek(0)
        dosya = SimpleUploadedFile('foto.png', arabellek.read(), content_type='image/png')

        form = IhbarForm(data=self._gecerli_veri(), files={'fotograf': dosya})
        self.assertFalse(form.is_valid())
        self.assertIn('5MB', form.errors['fotograf'][0])

    def test_izin_verilmeyen_dosya_turu_reddedilir(self):
        # BMP, Pillow için GEÇERLİ bir resimdir (Django'nun ImageField
        # kontrolünden geçer) ama bizim izinli listemizde (jpg/png/webp) yok.
        dosya = self._resim_dosyasi('foto.bmp', format='BMP', content_type='image/bmp')
        form = IhbarForm(data=self._gecerli_veri(), files={'fotograf': dosya})
        self.assertFalse(form.is_valid())
        self.assertIn('JPG, PNG veya WEBP', form.errors['fotograf'][0])

    def test_gecerli_jpg_fotograf_kabul_edilir(self):
        dosya = self._resim_dosyasi('foto.jpg', format='JPEG', content_type='image/jpeg')
        form = IhbarForm(data=self._gecerli_veri(), files={'fotograf': dosya})
        self.assertTrue(form.is_valid(), form.errors)
