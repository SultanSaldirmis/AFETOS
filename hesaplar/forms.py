import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import VatandasProfili

User = get_user_model()

# Türkiye cep telefonu formatı: 05XXXXXXXXX (11 hane, 05 ile başlar).
TELEFON_DESENI = re.compile(r'^05\d{9}$')


def tc_kimlik_no_gecerli_mi(tc: str) -> bool:
    """
    TC Kimlik Numarası'nın resmi ALGORİTMİK (checksum) doğrulaması — saf
    Python, test edilebilir.

    NOT: Bu SADECE format/checksum kontrolüdür. Gerçek bir kimlik
    doğrulama servisine (MERNİS vb.) bağlanmıyoruz — bu, bilinçli bir
    prototip/demo kapsam kararı (bkz. proje promptu, madde 4).

    Kurallar:
      - 11 haneli, sadece rakam, ilk hane 0 olamaz
      - 10. hane: (1,3,5,7,9. hanelerin toplamı × 7 − 2,4,6,8. hanelerin
        toplamı) mod 10
      - 11. hane: ilk 10 hanenin toplamının mod 10'u
    """
    if not tc.isdigit() or len(tc) != 11:
        return False
    if tc[0] == '0':
        return False

    haneler = [int(rakam) for rakam in tc]
    tek_haneler_toplami = sum(haneler[0:9:2])   # 1,3,5,7,9. haneler
    cift_haneler_toplami = sum(haneler[1:8:2])  # 2,4,6,8. haneler

    hane_10 = ((tek_haneler_toplami * 7) - cift_haneler_toplami) % 10
    if hane_10 != haneler[9]:
        return False

    hane_11 = sum(haneler[0:10]) % 10
    if hane_11 != haneler[10]:
        return False

    return True


class VatandasKayitFormu(forms.Form):
    """
    Vatandaş öz-kayıt formu. Stok Django User modelinde telefon alanı
    olmadığı için, telefon numarasını benzersiz giriş kimliği (username)
    olarak kullanıyoruz — afet senaryosunda vatandaşlar için doğal bir
    kimlik (e-posta değil). ad_soyad, User.first_name/last_name'e bölünür.
    TC Kimlik No, ayrı bir VatandasProfili (OneToOne) modelinde tutulur.

    Sunucu taraflı validasyon:
      - telefon: 05XXXXXXXXX formatı (regex) + mükerrer kayıt engeli
      - TC kimlik no: 11 hane + resmi checksum algoritması + mükerrer engeli
      - şifre: Django'nun validate_password validator'ları (min 8 karakter dahil)
      - şifre + şifre tekrar eşleşmeli
    """
    ad_soyad = forms.CharField(
        label='Ad Soyad', max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    tc_kimlik_no = forms.CharField(
        label='TC Kimlik Numarası', max_length=11,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '11 haneli TC kimlik no', 'inputmode': 'numeric', 'maxlength': '11'}),
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

    def clean_tc_kimlik_no(self):
        tc = self.cleaned_data['tc_kimlik_no'].strip()
        if not tc_kimlik_no_gecerli_mi(tc):
            raise forms.ValidationError('Geçerli bir TC Kimlik Numarası girin.')
        if VatandasProfili.objects.filter(tc_kimlik_no=tc).exists():
            raise forms.ValidationError('Bu TC Kimlik Numarasıyla zaten bir hesap var.')
        return tc

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
        """Formdan yeni bir vatandaş User'ı + bağlı VatandasProfili'ni (TC kimlik no) oluşturur."""
        ad_soyad = self.cleaned_data['ad_soyad'].strip()
        ad, _, soyad = ad_soyad.partition(' ')

        kullanici = User.objects.create_user(
            username=self.cleaned_data['telefon'],
            password=self.cleaned_data['sifre'],
            first_name=ad,
            last_name=soyad,
            is_staff=False,
        )
        VatandasProfili.objects.create(
            kullanici=kullanici,
            tc_kimlik_no=self.cleaned_data['tc_kimlik_no'],
        )
        return kullanici
