"""
Rakip projeden esinlenen ek özellikler (madde 2 ve 3) için testler:

  - kume_ekip_onerileri: tekli değil, mesafeye göre sıralı bir liste (en
    fazla ONERI_LISTESI_UZUNLUGU) döndürüyor mu; ilk eleman "ilk_mi" mi?
  - Destek Talebi akışı: saha ekibi talep oluşturabiliyor mu, Yönetim
    Paneli bunu gösterip "yönlendir"/"kapat" ile işleyebiliyor mu; mevcut
    atanan_ekip (ilk atama) bu süreçte DEĞİŞMİYOR mu?
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ekipler.models import Ekip
from ihbarlar.models import Ihbar
from ihbarlar.services import ihbari_kumeye_ata
from olaylar.models import DestekTalebi, OlayKumesi

from .realtime import kume_ekip_onerileri

User = get_user_model()


def _ihbar_ve_kume_olustur(olay_turu='enkaz', lat=37.5858, lng=36.9371):
    ihbar = Ihbar.objects.create(
        lat=lat, lng=lng, olay_turu=olay_turu,
        aciklama='Test ihbarı — enkaz altında insanlar var.',
        tahmini_kisi_sayisi=5, tahmini_yarali_sayisi=1,
    )
    return ihbari_kumeye_ata(ihbar)


class KumeEkipOnerileriTestleri(TestCase):
    """Madde 3: tekli öneri yerine mesafeye göre sıralı liste (en fazla 4)."""

    def setUp(self):
        self.kume = _ihbar_ve_kume_olustur()
        # 6 tane uygun (arama_kurtarma, boşta) ekip — sınırın (4) üzerinde,
        # kesmenin gerçekten çalıştığını görebilmek için.
        self.ekipler = [
            Ekip.objects.create(
                ad=f'AK-{i}', tur=Ekip.Tur.ARAMA_KURTARMA,
                lat=37.5858 + i * 0.01, lng=36.9371 + i * 0.01,
                durum=Ekip.Durum.BOSTA,
            )
            for i in range(6)
        ]

    def test_en_fazla_dort_oneri_doner(self):
        onerileri, _ = kume_ekip_onerileri(self.kume)
        self.assertLessEqual(len(onerileri), 4)
        self.assertGreater(len(onerileri), 0)

    def test_ilk_oneri_en_yakin_ekiptir_ve_ilk_mi_true(self):
        onerileri, _ = kume_ekip_onerileri(self.kume)
        self.assertTrue(onerileri[0]['ilk_mi'])
        self.assertEqual(onerileri[0]['ekip'].ad, 'AK-0')  # en yakın (0.01 kayma en az)
        self.assertFalse(onerileri[1]['ilk_mi'])

    def test_mesafeye_gore_artan_sirada(self):
        onerileri, _ = kume_ekip_onerileri(self.kume)
        mesafeler = [o['mesafe_km'] for o in onerileri]
        self.assertEqual(mesafeler, sorted(mesafeler))

    def test_gorevdeki_ekip_listeye_girmez(self):
        self.ekipler[0].durum = Ekip.Durum.GOREVDE
        self.ekipler[0].save(update_fields=['durum'])
        onerileri, _ = kume_ekip_onerileri(self.kume)
        self.assertNotIn('AK-0', [o['ekip'].ad for o in onerileri])


class DestekTalebiAkisiTestleri(TestCase):
    """Madde 2: Görevim'den destek talebi + Yönetim Paneli'nden işleme."""

    def setUp(self):
        self.koordinator = User.objects.create_user(username='koordinator1', password='demo1234', is_staff=True)

        self.kume = _ihbar_ve_kume_olustur()
        self.atanan_ekip = Ekip.objects.create(
            ad='AFAD Arama Kurtarma-1', tur=Ekip.Tur.ARAMA_KURTARMA,
            lat=37.5858, lng=36.9371, durum=Ekip.Durum.GOREVDE,
            mevcut_olay_kumesi=self.kume,
        )
        self.kume.atanan_ekip = self.atanan_ekip
        self.kume.save(update_fields=['atanan_ekip'])

        self.saha_user = User.objects.create_user(username='saha1', password='demo1234')
        self.atanan_ekip.user = self.saha_user
        self.atanan_ekip.save(update_fields=['user'])

        self.destek_ekibi = Ekip.objects.create(
            ad='AFAD Arama Kurtarma-2', tur=Ekip.Tur.ARAMA_KURTARMA,
            lat=37.586, lng=36.9373, durum=Ekip.Durum.BOSTA,
        )

    def test_saha_ekip_uyesi_destek_talebi_olusturabilir(self):
        self.client.force_login(self.saha_user)
        yanit = self.client.post(reverse('gorevim_destek_talebi_olustur'), {
            'aciklama': 'Ağır ekipman ve ek personel lazım.',
        })
        self.assertRedirects(yanit, reverse('gorevim'))

        talep = DestekTalebi.objects.get(olay_kumesi=self.kume)
        self.assertEqual(talep.talep_eden_ekip, self.atanan_ekip)
        self.assertEqual(talep.durum, DestekTalebi.Durum.BEKLIYOR)
        self.assertEqual(talep.aciklama, 'Ağır ekipman ve ek personel lazım.')

    def test_yonetim_paneli_bekleyen_talebi_gosterir(self):
        DestekTalebi.objects.create(olay_kumesi=self.kume, talep_eden_ekip=self.atanan_ekip, aciklama='Yardım lazım.')
        self.client.force_login(self.koordinator)
        yanit = self.client.get(reverse('dashboard:yonetim_paneli'))
        self.assertContains(yanit, 'Destek Talepleri')
        self.assertContains(yanit, self.atanan_ekip.ad)

    def test_yonlendir_ek_ekibi_yolda_yapar_ama_asil_atanan_ekip_degismez(self):
        talep = DestekTalebi.objects.create(olay_kumesi=self.kume, talep_eden_ekip=self.atanan_ekip)
        self.client.force_login(self.koordinator)

        yanit = self.client.post(
            reverse('dashboard:destek_talebi_guncelle', args=[talep.id]),
            {'eylem': 'yonlendir', 'ekip_id': self.destek_ekibi.id},
        )
        self.assertEqual(yanit.status_code, 200)

        talep.refresh_from_db()
        self.destek_ekibi.refresh_from_db()
        self.kume.refresh_from_db()

        self.assertEqual(talep.durum, DestekTalebi.Durum.YONLENDIRILDI)
        self.assertEqual(self.destek_ekibi.durum, Ekip.Durum.YOLDA)
        self.assertEqual(self.destek_ekibi.mevcut_olay_kumesi_id, self.kume.id)
        # Kümenin ASIL atanan ekibi (ilk atama) değişmemeli:
        self.assertEqual(self.kume.atanan_ekip_id, self.atanan_ekip.id)

    def test_kapat_ek_ekip_gondermeden_talebi_kapatir(self):
        talep = DestekTalebi.objects.create(olay_kumesi=self.kume, talep_eden_ekip=self.atanan_ekip)
        self.client.force_login(self.koordinator)

        self.client.post(reverse('dashboard:destek_talebi_guncelle', args=[talep.id]), {'eylem': 'kapat'})

        talep.refresh_from_db()
        self.destek_ekibi.refresh_from_db()
        self.assertEqual(talep.durum, DestekTalebi.Durum.KAPATILDI)
        self.assertEqual(self.destek_ekibi.durum, Ekip.Durum.BOSTA)  # dokunulmadı
