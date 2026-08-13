from django.contrib import admin

from .models import OlayKumesi


@admin.register(OlayKumesi)
class OlayKumesiAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'durum', 'guven_skoru', 'oncelik_skoru', 'atanan_ekip',
        'olusturulma_zamani', 'guncellenme_zamani',
    )
    list_filter = ('durum',)
    ordering = ('-oncelik_skoru',)
