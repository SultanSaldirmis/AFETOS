from django import forms
from django.core.validators import MinValueValidator

from .models import Ihbar

# Türkiye'nin kabaca coğrafi sınırları — bunun dışındaki koordinatlar
# muhtemelen bir girdi hatasıdır (ör. lat/lng ters girilmiş).
TURKIYE_LAT_ARALIGI = (35, 43)
TURKIYE_LNG_ARALIGI = (25, 45)

ACIKLAMA_MIN_UZUNLUK = 10

MAKS_FOTOGRAF_BOYUTU_MB = 5
MAKS_FOTOGRAF_BOYUTU_BYTE = MAKS_FOTOGRAF_BOYUTU_MB * 1024 * 1024
IZIN_VERILEN_FOTOGRAF_ICERIK_TURLERI = {'image/jpeg', 'image/png', 'image/webp'}
IZIN_VERILEN_FOTOGRAF_UZANTILARI = {'.jpg', '.jpeg', '.png', '.webp'}


class IhbarForm(forms.ModelForm):
    """
    Yeni ihbar oluşturma formu — hem operatör (İhbar Oluştur) hem vatandaş
    (Vatandaş Paneli) sayfası AYNI formu kullanır, kod tekrarı yok.

    Sunucu taraflı validasyon:
      - lat/lng Türkiye sınırları içinde olmalı
      - kişi/yaralı sayısı negatif olamaz
      - yaralı sayısı toplam kişi sayısını aşamaz (çapraz kontrol)
      - açıklama en az 10 karakter, olay_turu + açıklama zorunlu
      - fotoğraf (opsiyonel): en fazla 5MB, sadece jpg/png/webp
    """

    # tahmini_* alanlarını burada açıkça tanımlıyoruz ki MinValueValidator
    # ve hata mesajı üzerinde tam kontrolümüz olsun (model PositiveIntegerField
    # zaten negatifi engeller, ama bunu form seviyesinde de netleştiriyoruz).
    # initial=0: bu alanlar Vatandaş Paneli'nde GİZLİ bir input olarak
    # +/- stepper'a bağlı (bkz. _vatandas_form.html). initial verilmezse
    # sayfa ilk yüklendiğinde (kullanıcı hiç +/-'a basmadan) input'un
    # gerçek değeri boş kalıyor; alan required olduğu için tarayıcının
    # kendi HTML5 doğrulaması bunu geçersiz sayıyor, ama input gizli
    # olduğu için odaklanıp uyarı gösteremiyor ve form SESSİZCE hiçbir
    # şey yapmadan gönderilmiyor (gerçek bir bug'du, test sırasında
    # yakalandı). initial=0 + aşağıdaki novalidate ile bu artık imkansız.
    tahmini_kisi_sayisi = forms.IntegerField(
        required=True, initial=0,
        validators=[MinValueValidator(0, message='Kişi sayısı negatif olamaz.')],
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
    )
    tahmini_yarali_sayisi = forms.IntegerField(
        required=True, initial=0,
        validators=[MinValueValidator(0, message='Yaralı sayısı negatif olamaz.')],
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
    )

    class Meta:
        model = Ihbar
        fields = [
            'lat', 'lng', 'olay_turu', 'aciklama',
            'tahmini_kisi_sayisi', 'tahmini_yarali_sayisi', 'fotograf',
        ]
        widgets = {
            # lat/lng elle girilmez — operatör ve vatandaş formlarında da
            # sadece mini/mobil haritaya tıklayarak (veya GPS ile) seçilir,
            # bu yüzden gizli alan (bkz. _form.html / _vatandas_form.html).
            'lat': forms.HiddenInput(),
            'lng': forms.HiddenInput(),
            'olay_turu': forms.Select(attrs={'class': 'form-select'}),
            'aciklama': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Olayı kısaca anlatın...'}),
            'fotograf': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Model alanları zaten blank=False (varsayılan) olduğu için required
        # oluyor; burada bilinçli olarak açıkça teyit ediyoruz.
        self.fields['olay_turu'].required = True
        self.fields['aciklama'].required = True

    def clean_lat(self):
        lat = self.cleaned_data['lat']
        alt, ust = TURKIYE_LAT_ARALIGI
        if not (alt <= lat <= ust):
            raise forms.ValidationError('Konum Türkiye sınırları dışında görünüyor.')
        return lat

    def clean_lng(self):
        lng = self.cleaned_data['lng']
        alt, ust = TURKIYE_LNG_ARALIGI
        if not (alt <= lng <= ust):
            raise forms.ValidationError('Konum Türkiye sınırları dışında görünüyor.')
        return lng

    def clean_aciklama(self):
        aciklama = self.cleaned_data.get('aciklama', '').strip()
        if len(aciklama) < ACIKLAMA_MIN_UZUNLUK:
            raise forms.ValidationError(
                f'Açıklama en az {ACIKLAMA_MIN_UZUNLUK} karakter olmalı — daha anlamlı bir açıklama girin.'
            )
        return aciklama

    def clean_fotograf(self):
        fotograf = self.cleaned_data.get('fotograf')
        if not fotograf:
            return fotograf

        if fotograf.size > MAKS_FOTOGRAF_BOYUTU_BYTE:
            raise forms.ValidationError(f'Fotoğraf {MAKS_FOTOGRAF_BOYUTU_MB}MB’ı aşamaz.')

        icerik_turu = getattr(fotograf, 'content_type', None)
        uzanti = ('.' + fotograf.name.rsplit('.', 1)[-1].lower()) if '.' in fotograf.name else ''
        if icerik_turu not in IZIN_VERILEN_FOTOGRAF_ICERIK_TURLERI and uzanti not in IZIN_VERILEN_FOTOGRAF_UZANTILARI:
            raise forms.ValidationError('Sadece JPG, PNG veya WEBP formatında fotoğraf yükleyebilirsiniz.')

        return fotograf

    def clean(self):
        cleaned = super().clean()
        kisi = cleaned.get('tahmini_kisi_sayisi')
        yarali = cleaned.get('tahmini_yarali_sayisi')
        if kisi is not None and yarali is not None and yarali > kisi:
            self.add_error('tahmini_yarali_sayisi', 'Yaralı sayısı toplam kişi sayısını aşamaz.')
        return cleaned
