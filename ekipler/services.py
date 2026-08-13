"""
Ekip önerisi algoritması.

Saf Python fonksiyonları: Django ORM'e dokunmaz, mesafe hesabı için
olaylar/services.py içindeki haversine fonksiyonunu yeniden kullanır (kod
tekrarı yok). DB sorgusu yapan orkestrasyon (uygun ekipleri çekmek vb.)
bu dosyanın DIŞINDA, view/service katmanında yapılmalıdır.

Amaç 'en yakın ekip' değil, 'olaya uygun VE ulaşması makul olan en uygun
ekip'tir — bu yüzden ekip durumu (boşta/görevde/yolda) filtreye MUTLAKA
girer, sadece mesafeye bakılmaz.
"""
from dataclasses import dataclass

from django.conf import settings

from olaylar.services import haversine_mesafe_metre


@dataclass(frozen=True)
class EkipAday:
    """Ekip önerisi hesaplamasında kullanılan minimal ekip verisi."""
    id: int
    tur: str
    lat: float
    lng: float
    durum: str  # 'bosta' | 'yolda' | 'gorevde'


@dataclass(frozen=True)
class EkipOnerisi:
    """Sıralanmış ekip önerisi sonucundaki tek bir kayıt."""
    ekip_id: int
    mesafe_metre: float


def _gerekli_ekip_turleri(olay_turu: str) -> list[str]:
    """Olay türüne göre uygun ekip türlerini (öncelik sırasıyla) döner."""
    eslestirme = getattr(settings, 'EKIP_ONERISI_OLAY_TURU_ESLESTIRME', {})
    return eslestirme.get(olay_turu, [])


def uygun_ekipleri_sirala(
    olay_turu: str,
    olay_lat: float,
    olay_lng: float,
    ekip_adaylari: list[EkipAday],
) -> list[EkipOnerisi]:
    """
    Verilen olay türüne uygun VE boşta olan ekipleri, olaya olan mesafeye
    göre yakından uzağa sıralı olarak döner. Görevde/yolda olan ekipler
    hiçbir zaman öneri listesine girmez — sadece mesafeye bakılmaz.

    Uygunluk, ekip türünün `_gerekli_ekip_turleri` listesinde olmasıyla
    belirlenir; liste öncelik sırasını da taşır, bu yüzden sonuç önce
    tercih sırasına (mapping'teki index), sonra mesafeye göre sıralanır.
    """
    gerekli_turler = _gerekli_ekip_turleri(olay_turu)
    if not gerekli_turler:
        return []

    tur_onceligi = {tur: sira for sira, tur in enumerate(gerekli_turler)}

    uygun_adaylar = [
        ekip for ekip in ekip_adaylari
        if ekip.durum == 'bosta' and ekip.tur in tur_onceligi
    ]

    # Önce tercih sırasına (mapping'teki index), sonra mesafeye göre sırala.
    uygun_adaylar.sort(key=lambda ekip: (
        tur_onceligi[ekip.tur],
        haversine_mesafe_metre(olay_lat, olay_lng, ekip.lat, ekip.lng),
    ))

    return [
        EkipOnerisi(
            ekip_id=ekip.id,
            mesafe_metre=haversine_mesafe_metre(olay_lat, olay_lng, ekip.lat, ekip.lng),
        )
        for ekip in uygun_adaylar
    ]


def en_uygun_ekibi_oner(
    olay_turu: str,
    olay_lat: float,
    olay_lng: float,
    ekip_adaylari: list[EkipAday],
) -> EkipOnerisi | None:
    """Sıralı öneri listesindeki ilk (en uygun) ekibi döner, yoksa None."""
    onerileri = uygun_ekipleri_sirala(olay_turu, olay_lat, olay_lng, ekip_adaylari)
    return onerileri[0] if onerileri else None
