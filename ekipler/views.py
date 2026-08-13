from django.shortcuts import render

from .models import Ekip


def liste(request):
    """Ekipler sayfası: tür, konum, durum ve varsa aktif görev bilgisi (canlı güncelleme yok, statik liste)."""
    ekipler = Ekip.objects.select_related('mevcut_olay_kumesi').order_by('tur', 'ad')
    return render(request, 'ekipler/liste.html', {'ekipler': ekipler})
