from django.contrib import admin

from .models import Ihbar


@admin.register(Ihbar)
class IhbarAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'olay_turu', 'tahmini_kisi_sayisi', 'tahmini_yarali_sayisi',
        'olay_kumesi', 'bildiren', 'olusturulma_zamani',
    )
    list_filter = ('olay_turu',)
    search_fields = ('aciklama',)
