"""
İhbar kümeleme (clustering) mantığı.

Bu modül de scoring.py gibi bilerek saf Python fonksiyonlarından oluşur:
Django ORM'e dokunmaz, PostGIS kullanmaz — düz Python'da haversine formülü
ile iki nokta arası mesafeyi hesaplar. DB sorgusu gerektiren orkestrasyon
(mevcut kümeleri çekmek, ihbarı kaydetmek vb.) ihbarlar/services.py
içindedir ve bu modüldeki fonksiyonları çağırır.
"""
import math
from dataclasses import dataclass
from typing import Optional


def haversine_mesafe_metre(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    İki (enlem, boylam) noktası arasındaki büyük çember (great-circle)
    mesafesini metre cinsinden döner. PostGIS kullanmıyoruz; bu prototipte
    dünya yarıçapı sabit alınarak düz Python ile hesaplanıyor.
    """
    DUNYA_YARICAPI_METRE = 6_371_000

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return DUNYA_YARICAPI_METRE * c


@dataclass(frozen=True)
class KumeAday:
    """Eşleştirme sırasında kullanılan minimal küme verisi (id + merkez konum)."""
    id: int
    merkez_lat: float
    merkez_lng: float


def eslesen_kumeyi_bul(
    lat: float,
    lng: float,
    adaylar: list[KumeAday],
    yaricap_metre: float,
) -> Optional[int]:
    """
    Verilen konuma yarıçap içinde kalan küme adayları arasından en yakın
    olanının id'sini döner. Yarıçap içinde hiçbir aday yoksa None döner
    (bu durumda çağıran taraf yeni bir küme açmalıdır).
    """
    en_yakin_id: Optional[int] = None
    en_yakin_mesafe: Optional[float] = None

    for aday in adaylar:
        mesafe = haversine_mesafe_metre(lat, lng, aday.merkez_lat, aday.merkez_lng)
        if mesafe <= yaricap_metre and (en_yakin_mesafe is None or mesafe < en_yakin_mesafe):
            en_yakin_mesafe = mesafe
            en_yakin_id = aday.id

    return en_yakin_id


def yeni_merkez_hesapla(
    mevcut_merkez_lat: float,
    mevcut_merkez_lng: float,
    mevcut_ihbar_sayisi: int,
    yeni_ihbar_lat: float,
    yeni_ihbar_lng: float,
) -> tuple[float, float]:
    """
    Kümeye yeni bir ihbar eklendiğinde merkezi, kümedeki tüm ihbarların
    ortalama konumu olacak şekilde artımlı (incremental mean) günceller.
    `mevcut_ihbar_sayisi`, yeni ihbar eklenmeden ÖNCEKİ ihbar sayısıdır.
    """
    n = max(mevcut_ihbar_sayisi, 0)
    yeni_lat = (mevcut_merkez_lat * n + yeni_ihbar_lat) / (n + 1)
    yeni_lng = (mevcut_merkez_lng * n + yeni_ihbar_lng) / (n + 1)
    return yeni_lat, yeni_lng
