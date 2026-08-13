"""
ihbarlar/services.py içindeki kümeleme orkestrasyonu için testler.

Bu testler, matematiksel/hesaplama mantığının kendisini değil (o zaten
olaylar/tests.py içinde saf fonksiyon seviyesinde test edildi), DB ile
etkileşimin doğru çalıştığını doğrular: yeni küme açma, mevcut kümeye
ekleme, merkez güncelleme, skorların güncellenmesi.
"""
from django.test import TestCase

from olaylar.models import OlayKumesi

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
