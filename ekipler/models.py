from django.db import models


class Ekip(models.Model):
    """Sahada görev yapan müdahale ekibi (sağlık, arama-kurtarma, lojistik vb.)."""

    class Tur(models.TextChoices):
        SAGLIK = 'saglik', 'Sağlık'
        ARAMA_KURTARMA = 'arama_kurtarma', 'Arama Kurtarma'
        LOJISTIK = 'lojistik', 'Lojistik'

    class Durum(models.TextChoices):
        BOSTA = 'bosta', 'Boşta'
        YOLDA = 'yolda', 'Yolda'
        GOREVDE = 'gorevde', 'Görevde'

    ad = models.CharField(max_length=150, verbose_name='Ekip Adı')
    tur = models.CharField(max_length=20, choices=Tur.choices, verbose_name='Ekip Türü')

    # Ekibin güncel konumu (haversine mesafe hesapları için düz float alanlar)
    lat = models.FloatField(verbose_name='Enlem')
    lng = models.FloatField(verbose_name='Boylam')

    durum = models.CharField(
        max_length=20, choices=Durum.choices, default=Durum.BOSTA, verbose_name='Durum'
    )

    # Ekibin şu an atanmış olduğu olay kümesi (varsa). string referans
    # kullanıyoruz çünkü olaylar app'i de bu app'e referans veriyor.
    mevcut_olay_kumesi = models.ForeignKey(
        'olaylar.OlayKumesi',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='gorevli_ekipler',
        verbose_name='Mevcut Olay Kümesi',
    )

    olusturulma_zamani = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ekip'
        verbose_name_plural = 'Ekipler'

    def __str__(self):
        return f'{self.ad} ({self.get_tur_display()})'
