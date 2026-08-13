"""
olaylar/scoring.py içindeki güven skoru fonksiyonları için birim testler.

Bu testler Django ORM'e dokunmaz (scoring.py saf Python olduğu için DB
gerektirmez), ama proje standardı gereği Django'nun test runner'ı ile
çalışacak şekilde TestCase kullanıyoruz.
"""
from django.test import TestCase

from .scoring import (
    IhbarVerisi,
    OlayKumesiOzeti,
    dogrulama_gerekli_mi,
    guven_skoru_hesapla,
    oncelik_skoru_hesapla,
)
from .services import KumeAday, eslesen_kumeyi_bul, haversine_mesafe_metre, yeni_merkez_hesapla


class GuvenSkoruHesaplaTestleri(TestCase):

    def test_bos_liste_sifir_doner(self):
        self.assertEqual(guven_skoru_hesapla([]), 0)

    def test_tek_ihbar_dusuk_taban_skor_uretir(self):
        ihbar = IhbarVerisi(
            aciklama='Binada çatlaklar var, deprem sonrası hasar oluştu.',
            olay_turu='deprem_hasari',
        )
        skor = guven_skoru_hesapla([ihbar])
        # Tek ihbar için taban skor düşük olmalı (tutarlı olsa bile 100'e
        # yakın olmamalı) — birden fazla bağımsız kaynak henüz yok.
        self.assertGreater(skor, 0)
        self.assertLess(skor, 60)

    def test_cok_sayida_tutarli_bagimsiz_ihbar_yuksek_skor_uretir(self):
        # Dokümandaki örnek: 8 bağımsız ihbar -> güven skoru ~96 civarı.
        ihbarlar = [
            IhbarVerisi(
                aciklama='Enkaz altından ses geliyor, kurtarma ekibi bekleniyor.',
                olay_turu='enkaz',
                fotograf_var=(i == 0),  # en az bir tanesinde fotoğraf var
                tahmini_kisi_sayisi=4,
            )
            for i in range(8)
        ]
        skor = guven_skoru_hesapla(ihbarlar)
        self.assertGreaterEqual(skor, 90)
        self.assertLessEqual(skor, 100)

    def test_tutarsiz_aciklama_skoru_dusurur(self):
        tutarli_ihbar = IhbarVerisi(
            aciklama='Yangın var, alevler yükseliyor, duman her yeri kapladı.',
            olay_turu='yangin',
        )
        tutarsiz_ihbar = IhbarVerisi(
            aciklama='Bugün hava çok güzeldi, markete gittim.',
            olay_turu='yangin',
        )
        skor_tutarli = guven_skoru_hesapla([tutarli_ihbar])
        skor_tutarsiz = guven_skoru_hesapla([tutarsiz_ihbar])
        self.assertGreater(skor_tutarli, skor_tutarsiz)

    def test_celiskili_kisi_sayilari_skoru_dusurur(self):
        tutarli_sayilar = [
            IhbarVerisi(aciklama='Enkaz altında insanlar var.', olay_turu='enkaz', tahmini_kisi_sayisi=5)
            for _ in range(4)
        ]
        celiskili_sayilar = [
            IhbarVerisi(aciklama='Enkaz altında insanlar var.', olay_turu='enkaz', tahmini_kisi_sayisi=n)
            for n in [1, 50, 2, 80]
        ]
        skor_tutarli = guven_skoru_hesapla(tutarli_sayilar)
        skor_celiskili = guven_skoru_hesapla(celiskili_sayilar)
        self.assertGreater(skor_tutarli, skor_celiskili)

    def test_fotograf_varsa_skor_artar(self):
        fotografsiz = IhbarVerisi(
            aciklama='Yaralı var, kanama mevcut, ambulans gerekiyor.',
            olay_turu='tibbi',
            fotograf_var=False,
        )
        fotografli = IhbarVerisi(
            aciklama='Yaralı var, kanama mevcut, ambulans gerekiyor.',
            olay_turu='tibbi',
            fotograf_var=True,
        )
        self.assertGreater(
            guven_skoru_hesapla([fotografli]),
            guven_skoru_hesapla([fotografsiz]),
        )

    def test_skor_daima_0_100_araliginda(self):
        # Aşırı tutarsız + çelişkili bir senaryoda bile skor negatif olmamalı.
        ihbarlar = [
            IhbarVerisi(aciklama='alakasız metin', olay_turu='yangin', tahmini_kisi_sayisi=n)
            for n in [1, 1000]
        ]
        skor = guven_skoru_hesapla(ihbarlar)
        self.assertGreaterEqual(skor, 0)
        self.assertLessEqual(skor, 100)


class DogrulamaGerekliMiTestleri(TestCase):

    def test_esik_altinda_dogrulama_gerekli(self):
        self.assertTrue(dogrulama_gerekli_mi(30))

    def test_esik_ustunde_dogrulama_gerekmez(self):
        self.assertFalse(dogrulama_gerekli_mi(70))

    def test_dusuk_skor_veri_silmez_sadece_isaretler(self):
        # Bu test aslında bir "davranış sözleşmesi" testi: fonksiyon bool
        # döner, herhangi bir silme/mutasyon işlemi yapmaz.
        sonuc = dogrulama_gerekli_mi(10)
        self.assertIsInstance(sonuc, bool)


class OncelikSkoruHesaplaTestleri(TestCase):

    def test_hafif_olay_dusuk_oncelik_uretir(self):
        ozet = OlayKumesiOzeti(
            toplam_etkilenen_kisi=1,
            toplam_yarali=0,
            baskin_olay_turu='diger',
            gecen_dakika=2,
        )
        skor = oncelik_skoru_hesapla(ozet)
        self.assertLess(skor, 40)

    def test_agir_olay_yuksek_oncelik_uretir(self):
        # Çok sayıda etkilenen/yaralı, yüksek riskli olay türü, uzun süredir
        # müdahale edilmemiş -> öncelik yüksek olmalı.
        ozet = OlayKumesiOzeti(
            toplam_etkilenen_kisi=150,
            toplam_yarali=20,
            baskin_olay_turu='enkaz',
            gecen_dakika=200,
        )
        skor = oncelik_skoru_hesapla(ozet)
        self.assertGreaterEqual(skor, 85)

    def test_daha_fazla_yarali_daha_yuksek_oncelik_uretir(self):
        az_yarali = OlayKumesiOzeti(
            toplam_etkilenen_kisi=10, toplam_yarali=1,
            baskin_olay_turu='tibbi', gecen_dakika=10,
        )
        cok_yarali = OlayKumesiOzeti(
            toplam_etkilenen_kisi=10, toplam_yarali=10,
            baskin_olay_turu='tibbi', gecen_dakika=10,
        )
        self.assertGreater(
            oncelik_skoru_hesapla(cok_yarali),
            oncelik_skoru_hesapla(az_yarali),
        )

    def test_zaman_gectikce_oncelik_artar(self):
        yeni = OlayKumesiOzeti(
            toplam_etkilenen_kisi=20, toplam_yarali=2,
            baskin_olay_turu='deprem_hasari', gecen_dakika=5,
        )
        eski = OlayKumesiOzeti(
            toplam_etkilenen_kisi=20, toplam_yarali=2,
            baskin_olay_turu='deprem_hasari', gecen_dakika=150,
        )
        self.assertGreater(
            oncelik_skoru_hesapla(eski),
            oncelik_skoru_hesapla(yeni),
        )

    def test_bilinmeyen_ulasilabilirlik_notr_varsayilan_kullanir(self):
        # ulasilabilirlik_puani verilmezse hata almadan nötr (50) varsayılanla
        # hesap yapılabilmeli.
        ozet = OlayKumesiOzeti(
            toplam_etkilenen_kisi=30, toplam_yarali=3,
            baskin_olay_turu='yangin', gecen_dakika=20,
        )
        skor = oncelik_skoru_hesapla(ozet)
        self.assertGreaterEqual(skor, 0)
        self.assertLessEqual(skor, 100)

    def test_dusuk_ulasilabilirlik_skoru_dusurur(self):
        kolay_ulasilir = OlayKumesiOzeti(
            toplam_etkilenen_kisi=20, toplam_yarali=2,
            baskin_olay_turu='yangin', gecen_dakika=15,
            ulasilabilirlik_puani=90,
        )
        zor_ulasilir = OlayKumesiOzeti(
            toplam_etkilenen_kisi=20, toplam_yarali=2,
            baskin_olay_turu='yangin', gecen_dakika=15,
            ulasilabilirlik_puani=10,
        )
        self.assertGreater(
            oncelik_skoru_hesapla(kolay_ulasilir),
            oncelik_skoru_hesapla(zor_ulasilir),
        )

    def test_skor_daima_0_100_araliginda(self):
        asiri_ozet = OlayKumesiOzeti(
            toplam_etkilenen_kisi=100000, toplam_yarali=100000,
            baskin_olay_turu='enkaz', gecen_dakika=100000,
            ulasilabilirlik_puani=1000,  # kasıtlı olarak aralık dışı
        )
        skor = oncelik_skoru_hesapla(asiri_ozet)
        self.assertGreaterEqual(skor, 0)
        self.assertLessEqual(skor, 100)


class HaversineMesafeTestleri(TestCase):

    def test_ayni_nokta_sifir_mesafe(self):
        mesafe = haversine_mesafe_metre(37.0, 37.0, 37.0, 37.0)
        self.assertAlmostEqual(mesafe, 0.0, places=6)

    def test_bilinen_mesafe_yaklasik_dogru(self):
        # İstanbul (Sultanahmet) - Kadıköy arası kabaca ~7-8 km'dir.
        istanbul_lat, istanbul_lng = 41.0055, 28.9769
        kadikoy_lat, kadikoy_lng = 40.9911, 29.0281
        mesafe_km = haversine_mesafe_metre(istanbul_lat, istanbul_lng, kadikoy_lat, kadikoy_lng) / 1000
        self.assertGreater(mesafe_km, 3)
        self.assertLess(mesafe_km, 10)

    def test_mesafe_simetriktir(self):
        m1 = haversine_mesafe_metre(37.06, 37.38, 37.07, 37.39)
        m2 = haversine_mesafe_metre(37.07, 37.39, 37.06, 37.38)
        self.assertAlmostEqual(m1, m2, places=6)


class EslesenKumeyiBulTestleri(TestCase):

    def test_yaricap_disindaysa_none_doner(self):
        adaylar = [KumeAday(id=1, merkez_lat=37.0, merkez_lng=37.0)]
        # ~1 derece enlem farkı ~111 km eder, yarıçapın (400m) çok dışında.
        sonuc = eslesen_kumeyi_bul(38.0, 37.0, adaylar, yaricap_metre=400)
        self.assertIsNone(sonuc)

    def test_yaricap_icindeyse_eslestirir(self):
        adaylar = [KumeAday(id=1, merkez_lat=37.0600, merkez_lng=37.3800)]
        # Çok küçük bir kayma (~10-20 metre civarı), 400m yarıçap içinde kalmalı.
        sonuc = eslesen_kumeyi_bul(37.0601, 37.3801, adaylar, yaricap_metre=400)
        self.assertEqual(sonuc, 1)

    def test_birden_fazla_adaydan_en_yakini_secer(self):
        adaylar = [
            KumeAday(id=1, merkez_lat=37.0700, merkez_lng=37.3900),  # uzak
            KumeAday(id=2, merkez_lat=37.0601, merkez_lng=37.3801),  # yakın
        ]
        sonuc = eslesen_kumeyi_bul(37.0600, 37.3800, adaylar, yaricap_metre=5000)
        self.assertEqual(sonuc, 2)

    def test_aday_yoksa_none_doner(self):
        self.assertIsNone(eslesen_kumeyi_bul(37.0, 37.0, [], yaricap_metre=400))


class YeniMerkezHesaplaTestleri(TestCase):

    def test_ilk_ihbarda_merkez_ihbarin_konumu_olur(self):
        lat, lng = yeni_merkez_hesapla(37.0, 37.0, 0, 37.1, 37.2)
        self.assertAlmostEqual(lat, 37.1)
        self.assertAlmostEqual(lng, 37.2)

    def test_ikinci_ihbar_ortalamayi_kaydirir(self):
        # Mevcut merkez tek ihbardan oluşuyor (37.0, 37.0); yeni ihbar (38.0, 38.0)
        # eklenince ortalama tam ortada (37.5, 37.5) olmalı.
        lat, lng = yeni_merkez_hesapla(37.0, 37.0, 1, 38.0, 38.0)
        self.assertAlmostEqual(lat, 37.5)
        self.assertAlmostEqual(lng, 37.5)
