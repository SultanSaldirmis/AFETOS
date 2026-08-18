from django.contrib import admin

from .models import DestekTalebi, OlayKumesi


@admin.register(OlayKumesi)
class OlayKumesiAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'durum', 'guven_skoru', 'oncelik_skoru', 'atanan_ekip',
        'olusturulma_zamani', 'guncellenme_zamani',
    )
    list_filter = ('durum',)
    ordering = ('-oncelik_skoru',)


@admin.register(DestekTalebi)
class DestekTalebiAdmin(admin.ModelAdmin):
    list_display = ('id', 'olay_kumesi', 'talep_eden_ekip', 'durum', 'olusturulma_zamani')
    list_filter = ('durum',)
