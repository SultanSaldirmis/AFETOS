from django.contrib import admin

from .models import VatandasProfili


@admin.register(VatandasProfili)
class VatandasProfiliAdmin(admin.ModelAdmin):
    list_display = ('kullanici', 'tc_kimlik_no')
    search_fields = ('tc_kimlik_no', 'kullanici__username')
