from django.db import models


class Ihbar(models.Model):
    """Vatandaş veya saha ekibi tarafından oluşturulan tekil bir afet ihbarı."""

    class OlayTuru(models.TextChoices):
        DEPREM_HASARI = 'deprem_hasari', 'Deprem Hasarı'
        YANGIN = 'yangin', 'Yangın'
        TIBBI = 'tibbi', 'Tıbbi'
        ENKAZ = 'enkaz', 'Enkaz'
        DIGER = 'diger', 'Diğer'

    # İhbarın bildirilen konumu
    lat = models.FloatField(verbose_name='Enlem')
    lng = models.FloatField(verbose_name='Boylam')

    olay_turu = models.CharField(
        max_length=20, choices=OlayTuru.choices, verbose_name='Olay Türü'
    )
    aciklama = models.TextField(verbose_name='Açıklama')

    tahmini_kisi_sayisi = models.PositiveIntegerField(
        default=0, verbose_name='Tahmini Etkilenen Kişi Sayısı'
    )
    tahmini_yarali_sayisi = models.PositiveIntegerField(
        default=0, verbose_name='Tahmini Yaralı Sayısı'
    )

    fotograf = models.ImageField(
        upload_to='ihbar_fotograflari/', null=True, blank=True, verbose_name='Fotoğraf'
    )

    olusturulma_zamani = models.DateTimeField(auto_now_add=True)

    # İhbar bir olay kümesine henüz atanmamışsa boş kalır (kümeleme mantığı
    # sonraki adımda haversine formülüyle otomatik atayacak).
    olay_kumesi = models.ForeignKey(
        'olaylar.OlayKumesi',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='ihbarlar',
        verbose_name='Olay Kümesi',
    )

    class Meta:
        verbose_name = 'İhbar'
        verbose_name_plural = 'İhbarlar'
        ordering = ['-olusturulma_zamani']

    def __str__(self):
        return f'{self.get_olay_turu_display()} — {self.olusturulma_zamani:%d.%m.%Y %H:%M}'
