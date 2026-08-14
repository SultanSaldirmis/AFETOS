"""
deprem/views.py içindeki Kandilli proxy view'i için testler:
  - Kaynağa ulaşılamazsa hata fırlatmadan boş liste dönüyor mu?
  - 60sn içinde tekrar istek atılmıyor mu (cache)?
"""
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class KandilliProxyTestleri(TestCase):

    def setUp(self):
        cache.clear()
        self.koordinator = User.objects.create_user(
            username='koordinator1', password='demo1234', is_staff=True,
        )
        self.client.force_login(self.koordinator)

    def test_giris_yapmamis_kullanici_engellenir(self):
        self.client.logout()
        yanit = self.client.get(reverse('kandilli_proxy'))
        self.assertNotEqual(yanit.status_code, 200)

    @patch('deprem.views.requests.get')
    def test_basarili_yanit_oldugu_gibi_dondurulur(self, mock_get):
        sahte_veri = {'result': [{'title': 'TEST DEPREMI', 'mag': 3.2}]}
        mock_get.return_value.json.return_value = sahte_veri
        mock_get.return_value.raise_for_status.return_value = None

        yanit = self.client.get(reverse('kandilli_proxy'))

        self.assertEqual(yanit.status_code, 200)
        self.assertEqual(yanit.json(), sahte_veri)
        mock_get.assert_called_once()

    @patch('deprem.views.requests.get')
    def test_kaynaga_ulasilamazsa_bos_liste_ve_hata_doner(self, mock_get):
        mock_get.side_effect = requests.ConnectionError('bağlantı yok')

        yanit = self.client.get(reverse('kandilli_proxy'))

        self.assertEqual(yanit.status_code, 200)  # sayfa/istemci çökmüyor
        veri = yanit.json()
        self.assertEqual(veri['result'], [])
        self.assertIn('error', veri)

    @patch('deprem.views.requests.get')
    def test_zaman_asiminda_da_cokmez(self, mock_get):
        mock_get.side_effect = requests.Timeout('zaman aşımı')

        yanit = self.client.get(reverse('kandilli_proxy'))

        self.assertEqual(yanit.status_code, 200)
        self.assertEqual(yanit.json()['result'], [])

    @patch('deprem.views.requests.get')
    def test_60_saniye_icinde_tekrar_istek_atilmaz(self, mock_get):
        mock_get.return_value.json.return_value = {'result': []}
        mock_get.return_value.raise_for_status.return_value = None

        self.client.get(reverse('kandilli_proxy'))
        self.client.get(reverse('kandilli_proxy'))
        self.client.get(reverse('kandilli_proxy'))

        # Cache sayesinde 3 istekte de kaynağa sadece 1 kez gidilmeli.
        mock_get.assert_called_once()

    @patch('deprem.views.requests.get')
    def test_hatali_yanit_da_kisa_sureli_cachelenir(self, mock_get):
        mock_get.side_effect = requests.ConnectionError('bağlantı yok')

        self.client.get(reverse('kandilli_proxy'))
        self.client.get(reverse('kandilli_proxy'))

        # Hata durumu da cache'lendiği için kaynak kesintideyken her
        # istek tekrar dışarı çıkıp beklemeye girmemeli.
        mock_get.assert_called_once()
