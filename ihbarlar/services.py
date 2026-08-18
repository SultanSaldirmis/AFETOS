"""
İhbar oluşturulduğunda ilgili olay kümesine atama katmanı.

Bu modül DB sorgusu yapan ince bir orkestrasyon katmanıdır: mesafe
hesaplama ve eşleştirme mantığının kendisi saf Python fonksiyonları olarak
olaylar/services.py içinde, güven/öncelik skoru hesaplama mantığı ise
olaylar/scoring.py içinde tanımlıdır (ikisi de DB'den bağımsız, ayrı ayrı
birim testlerle doğrulanmıştır). Burada sadece o fonksiyonları çağırıp
sonucu veritabanına yazıyoruz.
"""
from collections import Counter

from django.conf import settings
from django.utils import timezone

from olaylar.models import OlayKumesi
from olaylar.scoring import (
    IhbarVerisi,
    OlayKumesiOzeti,
    dogrulama_gerekli_mi,
    guven_skoru_hesapla,
    oncelik_skoru_hesapla,
)
from olaylar.services import KumeAday, eslesen_kumeyi_bul, yeni_merkez_hesapla


def ihbari_kumeye_ata(ihbar) -> OlayKumesi:
    """
    Verilen İhbar'ı mevcut olay kümelerinden birine ekler (yarıçap
    içindeyse) ya da yeni bir küme açar. Ardından kümenin güven ve öncelik
    skorlarını günceller. İhbar ve küme veritabanına kaydedilir.

    'tamamlandi' durumundaki kümeler eşleştirmeye dahil edilmez — kapanmış
    bir olaya yeni ihbar otomatik eklenmemeli.
    """
    yaricap_metre = getattr(settings, 'KUMELEME_YARICAPI_METRE', 400)

    # Küme modelinde ayrı bir olay_turu alanı yok; kümenin türü, içindeki
    # ihbarların (yeni türü karışması artık eslesen_kumeyi_bul tarafından
    # engellendiği için hepsi aynı olan) türünden türetilir. İlişkili hiç
    # ihbarı olmayan (teorik olarak imkansız ama savunmacı) bir küme
    # eşleştirmeye dahil edilmez.
    aktif_kumeler = OlayKumesi.objects.exclude(durum=OlayKumesi.Durum.TAMAMLANDI)
    adaylar = [
        KumeAday(id=k.id, merkez_lat=k.merkez_lat, merkez_lng=k.merkez_lng, olay_turu=ilk_ihbar.olay_turu)
        for k in aktif_kumeler
        if (ilk_ihbar := k.ihbarlar.first()) is not None
    ]

    eslesen_id = eslesen_kumeyi_bul(ihbar.lat, ihbar.lng, ihbar.olay_turu, adaylar, yaricap_metre)

    if eslesen_id is not None:
        kume = OlayKumesi.objects.get(id=eslesen_id)
        mevcut_ihbar_sayisi = kume.ihbarlar.count()
        kume.merkez_lat, kume.merkez_lng = yeni_merkez_hesapla(
            kume.merkez_lat, kume.merkez_lng, mevcut_ihbar_sayisi, ihbar.lat, ihbar.lng,
        )
    else:
        kume = OlayKumesi.objects.create(merkez_lat=ihbar.lat, merkez_lng=ihbar.lng)

    ihbar.olay_kumesi = kume
    ihbar.save(update_fields=['olay_kumesi'])

    _kume_skorlarini_guncelle(kume)
    return kume


def _kume_skorlarini_guncelle(kume: OlayKumesi) -> None:
    """
    Kümedeki güncel ihbar listesine bakarak güven ve öncelik skorlarını
    yeniden hesaplar ve kaydeder. Güven skoru eşik altına düşerse küme
    'dogrulaniyor' durumuna işaretlenir — hiçbir ihbar/küme SİLİNMEZ.
    """
    ihbarlar = list(kume.ihbarlar.all())

    guven_verisi = [
        IhbarVerisi(
            aciklama=i.aciklama,
            olay_turu=i.olay_turu,
            fotograf_var=bool(i.fotograf),
            tahmini_kisi_sayisi=i.tahmini_kisi_sayisi,
        )
        for i in ihbarlar
    ]
    kume.guven_skoru = guven_skoru_hesapla(guven_verisi)

    if ihbarlar:
        baskin_olay_turu = Counter(i.olay_turu for i in ihbarlar).most_common(1)[0][0]
        en_eski_ihbar_zamani = min(i.olusturulma_zamani for i in ihbarlar)
        gecen_dakika = (timezone.now() - en_eski_ihbar_zamani).total_seconds() / 60
    else:
        baskin_olay_turu = 'diger'
        gecen_dakika = 0

    ozet = OlayKumesiOzeti(
        toplam_etkilenen_kisi=sum(i.tahmini_kisi_sayisi for i in ihbarlar),
        toplam_yarali=sum(i.tahmini_yarali_sayisi for i in ihbarlar),
        baskin_olay_turu=baskin_olay_turu,
        gecen_dakika=gecen_dakika,
        birlesik_aciklama=' '.join(i.aciklama for i in ihbarlar if i.aciklama),
    )
    kume.oncelik_skoru = oncelik_skoru_hesapla(ozet)

    if dogrulama_gerekli_mi(kume.guven_skoru) and kume.durum == OlayKumesi.Durum.BEKLIYOR:
        kume.durum = OlayKumesi.Durum.DOGRULANIYOR

    kume.save()
