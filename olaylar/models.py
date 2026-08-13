from django.db import models


class OlayKumesi(models.Model):
    """
    Birbirine yakın ve muhtemelen aynı olayı anlatan ihbarların gruplandığı küme.

    Güven skoru ve öncelik skoru burada tutulur; hesaplama mantığı bilerek
    modelin İÇİNDE değil, ayrı bir services/scoring modülünde saf Python
    fonksiyonları olarak yazılacak (sonraki adımlarda).
    """

    class Durum(models.TextChoices):
        BEKLIYOR = 'bekliyor', 'Bekliyor'
        DOGRULANIYOR = 'dogrulaniyor', 'Doğrulanıyor'
        MUDAHALE_EDILIYOR = 'mudahale_ediliyor', 'Müdahale Ediliyor'
        TAMAMLANDI = 'tamamlandi', 'Tamamlandı'

    # Kümedeki ihbarların ortalama konumu (yeni ihbar geldikçe güncellenir)
    merkez_lat = models.FloatField(verbose_name='Merkez Enlem')
    merkez_lng = models.FloatField(verbose_name='Merkez Boylam')

    # 0-100 aralığında; hesaplama scoring.py içindeki saf fonksiyonlarla yapılır
    guven_skoru = models.PositiveSmallIntegerField(default=0, verbose_name='Güven Skoru')
    oncelik_skoru = models.PositiveSmallIntegerField(default=0, verbose_name='Öncelik Skoru')

    durum = models.CharField(
        max_length=20, choices=Durum.choices, default=Durum.BEKLIYOR, verbose_name='Durum'
    )

    atanan_ekip = models.ForeignKey(
        'ekipler.Ekip',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='atandigi_olay_kumeleri',
        verbose_name='Atanan Ekip',
    )

    olusturulma_zamani = models.DateTimeField(auto_now_add=True)
    guncellenme_zamani = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Olay Kümesi'
        verbose_name_plural = 'Olay Kümeleri'
        ordering = ['-oncelik_skoru', '-olusturulma_zamani']

    def __str__(self):
        return f'Olay Kümesi #{self.pk} — {self.get_durum_display()} (öncelik: {self.oncelik_skoru})'

    @property
    def oncelik_renk(self) -> str:
        """
        Öncelik skoruna göre Bootstrap renk sınıfı döner (harita/panelde
        renk kodlu gösterim için). Bu SADECE görsel bir kategorilendirmedir,
        skor hesaplama mantığı değildir — o olaylar/scoring.py içindedir.
        """
        if self.oncelik_skoru >= 80:
            return 'danger'
        if self.oncelik_skoru >= 60:
            return 'warning'
        if self.oncelik_skoru >= 40:
            return 'info'
        return 'success'

    @property
    def oncelik_hex_renk(self) -> str:
        """Leaflet marker'ları için oncelik_renk'in hex karşılığı."""
        return {
            'danger': '#dc3545',
            'warning': '#fd7e14',
            'info': '#0dcaf0',
            'success': '#198754',
        }[self.oncelik_renk]
