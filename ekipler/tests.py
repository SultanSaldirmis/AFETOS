"""
ekipler/services.py içindeki ekip önerisi algoritması için birim testler.

Saf Python fonksiyonları test ediliyor (DB gerekmez), TestCase proje
standardı gereği kullanılıyor.
"""
from django.test import TestCase

from .services import EkipAday, en_uygun_ekibi_oner, uygun_ekipleri_sirala


class UygunEkipleriSiralaTestleri(TestCase):

    def test_gorevdeki_ekip_listeye_girmez(self):
        adaylar = [
            EkipAday(id=1, tur='saglik', lat=37.06, lng=37.38, durum='gorevde'),
        ]
        sonuc = uygun_ekipleri_sirala('tibbi', 37.06, 37.38, adaylar)
        self.assertEqual(sonuc, [])

    def test_yoldaki_ekip_listeye_girmez(self):
        adaylar = [
            EkipAday(id=1, tur='saglik', lat=37.06, lng=37.38, durum='yolda'),
        ]
        sonuc = uygun_ekipleri_sirala('tibbi', 37.06, 37.38, adaylar)
        self.assertEqual(sonuc, [])

    def test_yanlis_turdeki_bosta_ekip_listeye_girmez(self):
        adaylar = [
            EkipAday(id=1, tur='lojistik', lat=37.06, lng=37.38, durum='bosta'),
        ]
        # 'tibbi' olayı için sadece 'saglik' türü uygun.
        sonuc = uygun_ekipleri_sirala('tibbi', 37.06, 37.38, adaylar)
        self.assertEqual(sonuc, [])

    def test_uygun_bosta_ekip_onerilir(self):
        adaylar = [
            EkipAday(id=1, tur='saglik', lat=37.0601, lng=37.3801, durum='bosta'),
        ]
        sonuc = uygun_ekipleri_sirala('tibbi', 37.0600, 37.3800, adaylar)
        self.assertEqual(len(sonuc), 1)
        self.assertEqual(sonuc[0].ekip_id, 1)

    def test_mesafeye_gore_yakindan_uzaga_siralanir(self):
        uzak = EkipAday(id=1, tur='arama_kurtarma', lat=37.20, lng=37.50, durum='bosta')
        yakin = EkipAday(id=2, tur='arama_kurtarma', lat=37.0601, lng=37.3801, durum='bosta')
        sonuc = uygun_ekipleri_sirala('enkaz', 37.0600, 37.3800, [uzak, yakin])
        self.assertEqual([o.ekip_id for o in sonuc], [2, 1])

    def test_karma_durum_ve_turdeki_ekipler_dogru_filtrelenir(self):
        bosta_uygun = EkipAday(id=1, tur='arama_kurtarma', lat=37.0601, lng=37.3801, durum='bosta')
        bosta_uygunsuz_tur = EkipAday(id=2, tur='saglik', lat=37.0601, lng=37.3801, durum='bosta')
        gorevde_uygun = EkipAday(id=3, tur='arama_kurtarma', lat=37.0601, lng=37.3801, durum='gorevde')
        sonuc = uygun_ekipleri_sirala(
            'deprem_hasari', 37.0600, 37.3800,
            [bosta_uygun, bosta_uygunsuz_tur, gorevde_uygun],
        )
        self.assertEqual([o.ekip_id for o in sonuc], [1])

    def test_tercih_sirasi_mesafeden_once_gelir(self):
        # 'deprem_hasari' için tercih sırası: arama_kurtarma, sonra lojistik.
        # Lojistik ekip çok daha yakın olsa bile arama_kurtarma önce gelmeli.
        yakin_lojistik = EkipAday(id=1, tur='lojistik', lat=37.0601, lng=37.3801, durum='bosta')
        uzak_arama_kurtarma = EkipAday(id=2, tur='arama_kurtarma', lat=37.20, lng=37.50, durum='bosta')
        sonuc = uygun_ekipleri_sirala(
            'deprem_hasari', 37.0600, 37.3800, [yakin_lojistik, uzak_arama_kurtarma],
        )
        self.assertEqual(sonuc[0].ekip_id, 2)

    def test_bilinmeyen_olay_turu_bos_liste_doner(self):
        adaylar = [EkipAday(id=1, tur='saglik', lat=37.06, lng=37.38, durum='bosta')]
        sonuc = uygun_ekipleri_sirala('gecersiz_tur', 37.06, 37.38, adaylar)
        self.assertEqual(sonuc, [])


class EnUygunEkibiOnerTestleri(TestCase):

    def test_aday_yoksa_none_doner(self):
        self.assertIsNone(en_uygun_ekibi_oner('tibbi', 37.06, 37.38, []))

    def test_en_yakin_uygun_ekibi_oner(self):
        uzak = EkipAday(id=1, tur='saglik', lat=37.20, lng=37.50, durum='bosta')
        yakin = EkipAday(id=2, tur='saglik', lat=37.0601, lng=37.3801, durum='bosta')
        oneri = en_uygun_ekibi_oner('tibbi', 37.0600, 37.3800, [uzak, yakin])
        self.assertEqual(oneri.ekip_id, 2)
