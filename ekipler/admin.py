from django.contrib import admin

from .models import Ekip


@admin.register(Ekip)
class EkipAdmin(admin.ModelAdmin):
    list_display = ('ad', 'tur', 'durum', 'mevcut_olay_kumesi', 'lat', 'lng')
    list_filter = ('tur', 'durum')
    search_fields = ('ad',)
