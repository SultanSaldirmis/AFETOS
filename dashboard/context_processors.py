from django.urls import reverse


def nav_sekmeleri(request):
    """
    Header'daki (sadece Yönetici/Koordinatör'e görünen) navigasyon
    sekmelerini tüm template'lere sağlar — her view'da tekrar tekrar
    tanımlamamak için context processor olarak kayıtlı (settings.py).
    """
    return {
        'nav_sekmeleri': [
            (reverse('dashboard:ana_panel'), 'Ana Panel'),
            (reverse('olaylar:harita'), 'Harita'),
            (reverse('ihbarlar:olustur'), 'İhbar Oluştur'),
            (reverse('ekipler:liste'), 'Ekipler'),
            (reverse('dashboard:yonetim_paneli'), 'Yönetim'),
        ]
    }
