from django.conf import settings
from django.db import models


class VatandasProfili(models.Model):
    """
    Vatandaş kullanıcılara özel ek bilgiler — stok Django User modelinde
    TC Kimlik No alanı olmadığı için OneToOne bir profil modeli olarak
    tutuluyor (User modelini genişletmek yerine). Sadece Kayıt Ol formundan
    (hesaplar/forms.py) oluşturulan vatandaşlar için dolu olur.
    """
    kullanici = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vatandas_profili',
        verbose_name='Kullanıcı',
    )
    # NOT: Bu sadece ALGORİTMİK format/checksum doğrulaması — gerçek bir
    # kimlik doğrulama servisine (MERNİS vb.) bağlanmıyor. Prototip/demo
    # kapsamı budur (bkz. hesaplar/forms.py tc_kimlik_no_gecerli_mi).
    tc_kimlik_no = models.CharField(
        max_length=11, unique=True, verbose_name='TC Kimlik Numarası',
    )

    class Meta:
        verbose_name = 'Vatandaş Profili'
        verbose_name_plural = 'Vatandaş Profilleri'

    def __str__(self):
        return f'{self.kullanici.username} — {self.tc_kimlik_no}'
