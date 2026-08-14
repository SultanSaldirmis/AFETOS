import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

# Türkiye cep telefonu formatı: 05XXXXXXXXX (11 hane, 05 ile başlar).
TELEFON_DESENI = re.compile(r'^05\d{9}$')


class VatandasKayitFormu(forms.Form):
    """
    Vatandaş öz-kayıt formu. Stok Django User modelinde telefon alanı
    olmadığı için, telefon numarasını benzersiz giriş kimliği (username)
    olarak kullanıyoruz — afet senaryosunda vatandaşlar için doğal bir
    kimlik (e-posta değil). ad_soyad, User.first_name/last_name'e bölünür.

    Sunucu taraflı validasyon:
      - telefon: 05XXXXXXXXX formatı (regex) + mükerrer kayıt engeli
      - şifre: Django'nun validate_password validator'ları (min 8 karakter dahil)
      - şifre + şifre tekrar eşleşmeli
    """
    ad_soyad = forms.CharField(
        label='Ad Soyad', max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    telefon = forms.CharField(
        label='Telefon', max_length=11,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ör. 05551112233'}),
    )
    sifre = forms.CharField(
        label='Şifre',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    sifre_tekrar = forms.CharField(
        label='Şifre Tekrar',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    def clean_telefon(self):
        telefon = self.cleaned_data['telefon'].strip().replace(' ', '')
        if not TELEFON_DESENI.match(telefon):
            raise forms.ValidationError('Geçerli bir telefon numarası girin.')
        if User.objects.filter(username=telefon).exists():
            raise forms.ValidationError('Bu telefon numarasıyla zaten bir hesap var.')
        return telefon

    def clean_sifre(self):
        sifre = self.cleaned_data['sifre']
        validate_password(sifre)
        return sifre

    def clean(self):
        cleaned = super().clean()
        sifre = cleaned.get('sifre')
        sifre_tekrar = cleaned.get('sifre_tekrar')
        if sifre and sifre_tekrar and sifre != sifre_tekrar:
            self.add_error('sifre_tekrar', 'Şifreler eşleşmiyor.')
        return cleaned

    def kaydet(self):
        """Formdan yeni bir vatandaş User'ı oluşturur (is_staff=False, ekip bağlantısı yok)."""
        ad_soyad = self.cleaned_data['ad_soyad'].strip()
        ad, _, soyad = ad_soyad.partition(' ')

        return User.objects.create_user(
            username=self.cleaned_data['telefon'],
            password=self.cleaned_data['sifre'],
            first_name=ad,
            last_name=soyad,
            is_staff=False,
        )
