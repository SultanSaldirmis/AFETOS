"""
Demo senaryosu için başlangıç (seed) verisi oluşturur.

Bu komut, projenin demo senaryosundaki 1. adımı ("Sistemde önceden
oluşturulmuş örnek afet olayları haritada gösterilir") için gereken
verinin tamamını hazırlar:

  - Birkaç ekip (farklı tür ve durumda)
  - Birkaç ÖNCEDEN OLUŞTURULMUŞ olay kümesi — bunlar rastgele/elle
    skorlanmış DEĞİL; gerçek ihbarlar tek tek oluşturulup
    ihbarlar.services.ihbari_kumeye_ata() ile kümeleniyor, böylece
    güven/öncelik skorları gerçek algoritma tarafından hesaplanıyor
    (adım 2-5'teki mantığın aynısı).

Kalan demo adımları (yeni kritik ihbar oluşturma, ekip atama, durum
güncelleme, canlı güncellemeyi izleme) canlı demo sırasında elle
yapılır — bkz. DEMO.md.

Kullanım:
    python manage.py seed_demo          # önce mevcut veriyi temizler, sonra tohumlar
    python manage.py seed_demo --ekle   # mevcut veriyi SİLMEDEN üzerine ekler
"""
from django.core.management.base import BaseCommand

from ekipler.models import Ekip
from ihbarlar.models import Ihbar
from ihbarlar.services import ihbari_kumeye_ata
from olaylar.models import OlayKumesi


class Command(BaseCommand):
    help = 'Demo senaryosu için örnek ekip ve afet olayı (ihbar/küme) verisi oluşturur.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ekle', action='store_true',
            help='Mevcut İhbar/OlayKümesi/Ekip verisini SİLMEDEN üzerine ekler (varsayılan: önce temizler).',
        )

    def handle(self, *args, **options):
        if not options['ekle']:
            self.stdout.write('Mevcut İhbar, OlayKümesi ve Ekip kayıtları temizleniyor...')
            Ihbar.objects.all().delete()
            OlayKumesi.objects.all().delete()
            Ekip.objects.all().delete()

        self._ekipleri_olustur()
        self._onceden_olusturulmus_olaylari_olustur()

        self.stdout.write(self.style.SUCCESS(
            f'\nTamamlandı: {Ekip.objects.count()} ekip, '
            f'{OlayKumesi.objects.count()} olay kümesi, '
            f'{Ihbar.objects.count()} ihbar oluşturuldu.\n'
            'Demo akışı için DEMO.md dosyasına bakın.'
        ))

    def _ekipleri_olustur(self):
        """Kahramanmaraş/Hatay bölgesine dağılmış, farklı tür ve durumda örnek ekipler."""
        ekipler = [
            # ad, tür, lat, lng, durum
            ('AFAD Arama Kurtarma-1', Ekip.Tur.ARAMA_KURTARMA, 37.5858, 36.9371, Ekip.Durum.BOSTA),
            ('Sağlık Ekibi-1', Ekip.Tur.SAGLIK, 37.5900, 36.9300, Ekip.Durum.BOSTA),
            ('AFAD Arama Kurtarma-2', Ekip.Tur.ARAMA_KURTARMA, 36.2028, 36.1602, Ekip.Durum.BOSTA),
            ('Lojistik Destek-1', Ekip.Tur.LOJISTIK, 36.2100, 36.1500, Ekip.Durum.BOSTA),
            ('Sağlık Ekibi-2', Ekip.Tur.SAGLIK, 37.6100, 36.9500, Ekip.Durum.GOREVDE),
            ('Arama Kurtarma-3', Ekip.Tur.ARAMA_KURTARMA, 37.8000, 38.2700, Ekip.Durum.YOLDA),
        ]
        for ad, tur, lat, lng, durum in ekipler:
            Ekip.objects.create(ad=ad, tur=tur, lat=lat, lng=lng, durum=durum)
        self.stdout.write(f'  {len(ekipler)} ekip oluşturuldu.')

    def _onceden_olusturulmus_olaylari_olustur(self):
        """
        Üç ayrı bölgede, gerçek kümeleme/skor algoritmasından geçen örnek
        olaylar. Her ihbar tek tek oluşturulup ihbari_kumeye_ata() ile
        işlenir — skorlar elle atanmıyor, gerçek hesaplamadan geliyor.
        """
        # --- Küme A: Kahramanmaraş merkez — çok sayıda tutarlı, bağımsız
        #     ihbar -> yüksek güven + yüksek öncelik (kritik, kırmızı).
        kume_a_ihbarlari = [
            ('Enkaz altında insanlar var, çığlık sesleri duyuluyor.', 12, 4),
            ('Bina tamamen çöktü, enkaz altında kalanlar olduğu söyleniyor.', 15, 6),
            ('Enkazdan ses geliyor, kurtarma ekibi bekleniyor.', 10, 3),
            ('Çok katlı bina yıkıldı, enkaz altında aile var.', 8, 2),
        ]
        for aciklama, kisi, yarali in kume_a_ihbarlari:
            ihbar = Ihbar.objects.create(
                lat=37.5858 + 0.0006, lng=36.9371 + 0.0004, olay_turu=Ihbar.OlayTuru.ENKAZ,
                aciklama=aciklama, tahmini_kisi_sayisi=kisi, tahmini_yarali_sayisi=yarali,
            )
            ihbari_kumeye_ata(ihbar)

        # --- Küme B: Kahramanmaraş'ta farklı bir nokta — tıbbi ihtiyaç,
        #     orta seviye ihbar sayısı -> orta güven/öncelik (mavi/turuncu).
        kume_b_ihbarlari = [
            ('Yaralılar var, kanama mevcut, ambulans gerekiyor.', 6, 4),
            ('Sağlık ekibi bekleniyor, yaralı sayısı artıyor.', 5, 3),
        ]
        for aciklama, kisi, yarali in kume_b_ihbarlari:
            ihbar = Ihbar.objects.create(
                lat=37.5950, lng=36.9450, olay_turu=Ihbar.OlayTuru.TIBBI,
                aciklama=aciklama, tahmini_kisi_sayisi=kisi, tahmini_yarali_sayisi=yarali,
            )
            ihbari_kumeye_ata(ihbar)

        # --- Küme C: Hatay — tek, doğrulanmamış ihbar -> düşük güven
        #     skoru bekleniyor, sistem bunu SİLMEZ, 'dogrulaniyor' yapar.
        tek_ihbar = Ihbar.objects.create(
            lat=36.2028, lng=36.1602, olay_turu=Ihbar.OlayTuru.YANGIN,
            aciklama='Uzaktan duman görüldü, kaynağı net değil.',
            tahmini_kisi_sayisi=2, tahmini_yarali_sayisi=0,
        )
        ihbari_kumeye_ata(tek_ihbar)

        toplam_ihbar = len(kume_a_ihbarlari) + len(kume_b_ihbarlari) + 1
        self.stdout.write(f'  3 olay kümesi, {toplam_ihbar} ihbar oluşturuldu (gerçek skor algoritmasıyla).')
