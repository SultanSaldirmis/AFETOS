from django import forms

from .models import Ihbar


class IhbarForm(forms.ModelForm):
    """Yeni ihbar oluşturma formu (İhbar Oluştur sayfası, htmx ile gönderilir)."""

    class Meta:
        model = Ihbar
        fields = [
            'lat', 'lng', 'olay_turu', 'aciklama',
            'tahmini_kisi_sayisi', 'tahmini_yarali_sayisi', 'fotograf',
        ]
        widgets = {
            'lat': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'ör. 37.0600'}),
            'lng': forms.NumberInput(attrs={'class': 'form-control', 'step': 'any', 'placeholder': 'ör. 37.3800'}),
            'olay_turu': forms.Select(attrs={'class': 'form-select'}),
            'aciklama': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Olayı kısaca anlatın...'}),
            'tahmini_kisi_sayisi': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'tahmini_yarali_sayisi': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'fotograf': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
