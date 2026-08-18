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
    def oncelik_renk_kod(self) -> str:
        """
        Öncelik skoruna göre theme.css'teki tier adını döner ('crit',
        'high', 'med', 'low' — bkz. static/css/theme.css :root
        değişkenleri: --crit/--high/--med/--low ve *-bg varyantları).
        Bu SADECE görsel bir kategorilendirmedir, skor hesaplama mantığı
        değildir — o olaylar/scoring.py içindedir.
        """
        if self.oncelik_skoru >= 80:
            return 'crit'
        if self.oncelik_skoru >= 60:
            return 'high'
        if self.oncelik_skoru >= 40:
            return 'med'
        return 'low'

    @property
    def oncelik_hex_renk(self) -> str:
        """Leaflet marker'ları için oncelik_renk_kod'un hex karşılığı (theme.css ile birebir)."""
        return {
            'crit': '#E5484D',
            'high': '#F08A24',
            'med': '#3E8BD6',
            'low': '#2F9E6E',
        }[self.oncelik_renk_kod]


class DestekTalebi(models.Model):
    """
    Sahadaki bir ekibin, üzerinde çalıştığı olay için ek yardım talebi.
    Ekip görevin herhangi bir aşamasında (durum güncelleme akışından
    bağımsız) talep açabilir — bkz. ekipler/views.gorevim_destek_talebi_olustur.
    Koordinatör bunu Yönetim Paneli'nde ayrı bir bölümde görür ve mevcut
    ekip önerisi algoritmasıyla (ekipler/services.py) ek bir ekip
    önerilir; bu model güven/öncelik skoru veya kümeleme mantığına
    KESİNLİKLE dokunmaz.
    """

    class Durum(models.TextChoices):
        BEKLIYOR = 'bekliyor', 'Bekliyor'
        YONLENDIRILDI = 'yonlendirildi', 'Yönlendirildi'
        KAPATILDI = 'kapatildi', 'Kapatıldı'

    olay_kumesi = models.ForeignKey(
        OlayKumesi, on_delete=models.CASCADE, related_name='destek_talepleri',
        verbose_name='Olay Kümesi',
    )
    talep_eden_ekip = models.ForeignKey(
        'ekipler.Ekip', on_delete=models.CASCADE, related_name='destek_talepleri',
        verbose_name='Talep Eden Ekip',
    )
    aciklama = models.TextField(blank=True, verbose_name='Açıklama')
    durum = models.CharField(
        max_length=20, choices=Durum.choices, default=Durum.BEKLIYOR, verbose_name='Durum',
    )
    olusturulma_zamani = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Destek Talebi'
        verbose_name_plural = 'Destek Talepleri'
        ordering = ['-olusturulma_zamani']

    def __str__(self):
        return f'Destek Talebi #{self.pk} — {self.talep_eden_ekip.ad} (Küme #{self.olay_kumesi_id})'
