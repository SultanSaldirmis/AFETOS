"""
Güven skoru hesaplama mantığı.

Bu modül bilerek saf Python fonksiyonlarından oluşur: Django modeline
gömülü değildir, ORM sorgusu içermez, bu yüzden birim testlerle kolayca
ve hızlıca doğrulanabilir. Fonksiyonlar OlayKumesi.guven_skoru alanını
doldurmak için bir view/service katmanından çağrılır (o bağlantı
kümeleme adımında kurulacak — bkz. proje yol haritası adım 4).

Güven skoru bileşenleri (proje tanımından):
  1. Aynı bölgeden gelen bağımsız ve benzer ihbarların artması güveni yükseltir.
  2. Konum ile açıklama arasındaki tutarlılık güven değerlendirmesinde kullanılır.
  3. Tekrarlı veya çelişkili bildirimler güven skorunu düşürebilir.
  4. Fotoğraf veya başka doğrulayıcı veri varsa ek güven sinyali olarak kullanılır.

ÖNEMLİ: Düşük güven skorlu ihbar/küme SİLİNMEZ; bu modül yalnızca bir skor
üretir. `dogrulama_gerekli_mi` eşik altı kümeleri işaretlemek için kullanılır,
hiçbir fonksiyon veri silme/gizleme işlemi yapmaz.
"""
from dataclasses import dataclass
from typing import Optional

from django.conf import settings


# Olay türüne göre açıklamada aranacak anahtar kelimeler. İhbarın açıklaması
# bildirilen olay_turu ile tutarlı mı diye basit bir sinyal olarak kullanılır.
# NOT: Bu liste basit bir sözlük eşleştirmesidir; gerçek bir NLP/metin
# analizi değildir, prototip amaçlıdır.
TEK_IHBAR_GUVEN_SKORU_TAVANI = 90

OLAY_TURU_ANAHTAR_KELIMELER = {
    'deprem_hasari': ['deprem', 'çökme', 'çöktü', 'yıkıl', 'çatlak', 'bina', 'duvar'],
    'yangin': ['yangın', 'yanıyor', 'alev', 'duman', 'ateş'],
    'tibbi': ['yaralı', 'kanama', 'bilinç', 'nefes', 'ambulans', 'sağlık', 'acil'],
    'enkaz': ['enkaz', 'göçük', 'altında kaldı', 'kurtarma', 'ses geliyor'],
    'diger': [],
}


@dataclass(frozen=True)
class IhbarVerisi:
    """
    Güven skoru hesaplamasında kullanılan minimal ihbar verisi.

    Django modeline (Ihbar) doğrudan bağımlı olmamak için ayrı bir veri
    sınıfı; Ihbar nesnelerinden bu sınıfa dönüşüm çağıran taraf
    (view/service) tarafından yapılır.
    """
    aciklama: str
    olay_turu: str
    fotograf_var: bool = False
    tahmini_kisi_sayisi: int = 0


def _ayar(ayar_adi: str, varsayilan):
    """settings.py'de tanımlıysa oradan, yoksa modül içi varsayılandan oku."""
    return getattr(settings, ayar_adi, varsayilan)


def _taban_skor_hesapla(bagimsiz_ihbar_sayisi: int) -> float:
    """
    Bağımsız ihbar sayısı arttıkça azalan getiriyle (diminishing returns)
    yükselen taban eğri. Örn. katsayı=0.65 iken: n=1 -> ~35, n=8 -> ~97.
    Bu, dokümandaki '8 bağımsız ihbar -> güven skoru ~96' örneğiyle uyumlu
    bir eğridir.

    NOT: Katsayı prototip/simülasyon amaçlı seçilmiştir, gerçek bir
    istatistiksel kalibrasyona dayanmaz.
    """
    katsayi = _ayar('GUVEN_BAGIMSIZ_IHBAR_KATSAYISI', 0.65)
    n = max(bagimsiz_ihbar_sayisi, 0)
    return 100 * (1 - katsayi ** n)


def _tutarlilik_orani_hesapla(ihbarlar: list[IhbarVerisi]) -> Optional[float]:
    """
    Her ihbarın açıklamasının, bildirilen olay_turu ile anahtar kelime
    bazında tutarlı olup olmadığını kontrol eder. 0-1 arası bir oran
    döner (tutarlı ihbar sayısı / değerlendirilebilir ihbar sayısı).
    Anahtar kelime listesi boşsa (örn. 'diger') o ihbar değerlendirmeye
    dahil edilmez. Değerlendirilebilir hiç ihbar yoksa None döner (nötr).
    """
    degerlendirilebilir = []
    for ihbar in ihbarlar:
        anahtar_kelimeler = OLAY_TURU_ANAHTAR_KELIMELER.get(ihbar.olay_turu, [])
        if not anahtar_kelimeler:
            continue
        aciklama_kucuk = (ihbar.aciklama or '').lower()
        tutarli = any(kelime in aciklama_kucuk for kelime in anahtar_kelimeler)
        degerlendirilebilir.append(tutarli)

    if not degerlendirilebilir:
        return None

    return sum(degerlendirilebilir) / len(degerlendirilebilir)


def _celiski_orani_hesapla(ihbarlar: list[IhbarVerisi]) -> float:
    """
    Aynı kümedeki ihbarların bildirdiği kişi sayıları birbirinden çok
    farklıysa (yüksek değişim katsayısı / CV) bu, çelişkili bilgi sinyali
    sayılır. 0-1 arası bir ceza oranı döner. Karşılaştırılabilir en az iki
    veri yoksa çelişki değerlendirilemez ve 0 döner.
    """
    kisi_sayilari = [i.tahmini_kisi_sayisi for i in ihbarlar if i.tahmini_kisi_sayisi > 0]
    if len(kisi_sayilari) < 2:
        return 0.0

    ortalama = sum(kisi_sayilari) / len(kisi_sayilari)
    if ortalama == 0:
        return 0.0

    varyans = sum((x - ortalama) ** 2 for x in kisi_sayilari) / len(kisi_sayilari)
    std_sapma = varyans ** 0.5
    degisim_katsayisi = std_sapma / ortalama  # coefficient of variation

    # CV teorik olarak sınırsız büyüyebilir; 0-1 aralığına sıkıştırıp
    # doğrudan ceza oranı olarak kullanıyoruz.
    return min(degisim_katsayisi, 1.0)


def guven_skoru_hesapla(ihbarlar: list[IhbarVerisi]) -> int:
    """
    Bir olay kümesindeki ihbar listesine bakarak 0-100 arası güven skoru
    üretir. Bileşenler:

      1. Taban skor    : bağımsız/benzer ihbar sayısı arttıkça yükselir.
      2. Tutarlılık     : açıklama ile olay türü tutarlıysa artırır, değilse azaltır.
      3. Çelişki cezası : bildirilen rakamlar (kişi sayısı) çok farklıysa düşürür.
      4. Fotoğraf bonusu: doğrulayıcı fotoğraf varsa küçük bir artış.

    İhbar listesi boşsa 0 döner. Sonuç her zaman 0-100 aralığına
    sıkıştırılır (clamp).
    """
    if not ihbarlar:
        return 0

    taban_skor = _taban_skor_hesapla(len(ihbarlar))

    tutarlilik_agirligi = _ayar('GUVEN_TUTARLILIK_AGIRLIGI', 12)
    tutarlilik_orani = _tutarlilik_orani_hesapla(ihbarlar)
    tutarlilik_duzeltmesi = 0.0
    if tutarlilik_orani is not None:
        # oran 0.5 iken nötr; 1.0'a yaklaştıkça pozitif, 0'a yaklaştıkça
        # negatif düzeltme uygulanır (-agirlik .. +agirlik aralığında).
        tutarlilik_duzeltmesi = (tutarlilik_orani - 0.5) * 2 * tutarlilik_agirligi

    celiski_agirligi = _ayar('GUVEN_CELISKI_CEZA_AGIRLIGI', 15)
    celiski_orani = _celiski_orani_hesapla(ihbarlar)
    celiski_cezasi = celiski_orani * celiski_agirligi

    fotograf_bonusu_degeri = _ayar('GUVEN_FOTOGRAF_BONUSU', 5)
    fotograf_bonusu = fotograf_bonusu_degeri if any(i.fotograf_var for i in ihbarlar) else 0

    skor = taban_skor + tutarlilik_duzeltmesi - celiski_cezasi + fotograf_bonusu
    skor = max(0, min(100, skor))

    # Tek ihbar tavanı: kümede tek bir (bağımsız) ihbar varsa — fotoğraf
    # olsa dahi — sonuç 90'ı geçemez. Güven, esas olarak BİRDEN FAZLA
    # bağımsız kaynağın aynı olayı doğrulamasından gelir; tek kaynak ne
    # kadar "iyi" görünürse görünsün bu üst sınırın altında kalmalı. 2+
    # bağımsız ihbar varsa bu tavan tamamen kalkar, skor 100'e kadar çıkabilir.
    if len(ihbarlar) == 1:
        skor = min(skor, TEK_IHBAR_GUVEN_SKORU_TAVANI)

    return int(round(skor))


def dogrulama_gerekli_mi(guven_skoru: int) -> bool:
    """
    Güven skoru belirlenen eşiğin (varsayılan 50) altındaysa True döner.
    Bu durumda çağıran taraf OlayKumesi.durum alanını 'dogrulaniyor' yapmalı
    — KESİNLİKLE silme/gizleme işlemi yapılmamalı.
    """
    esik = _ayar('GUVEN_DOGRULAMA_ESIGI', 50)
    return guven_skoru < esik


# ---------------------------------------------------------------------------
# Öncelik skoru
#
# Öncelik = kisi_etkisi + tibbi_aciliyet + olay_riski + ulasilabilirlik + zaman_faktoru
#
# Her bileşen 0-100 aralığına ayrı ayrı ölçeklenir, sonra settings.py'deki
# ONCELIK_AGIRLIKLARI ile ağırlıklandırılıp toplanır ve tekrar 0-100
# aralığına sıkıştırılır. Ağırlıklar ve doyma eşikleri gerçek afet
# operasyonlarında kullanılacak kesin/onaylı katsayılar DEĞİLDİR, sadece
# prototip/simülasyon amaçlıdır (bkz. settings.py yorumları).
#
# Bunun üzerine, ham ağırlıklı toplamdan (taban skor) SONRA bir "kritik
# kelime çarpanı" uygulanır — bkz. kritik_kelime_carpani.
# ---------------------------------------------------------------------------


# İhbar açıklamasında geçmesi öncelik skorunu artıran kritik kelimeler.
# Basit bir sözlük eşleştirmesidir, gerçek bir NLP/varlık tanıma değildir —
# prototip amaçlıdır.
KRITIK_KELIMELER = ['çocuk', 'bebek', 'kanama', 'nefes alamıyorum', 'bilinci kapalı', 'enkaz altında']


def kritik_kelime_carpani(aciklama: str) -> float:
    """
    Açıklama metninde KRITIK_KELIMELER'den kaç tanesinin geçtiğine göre bir
    çarpan döner: 0 eşleşme -> 0.0, 1 eşleşme -> 0.20, 2+ eşleşme -> 0.30.

    NOT: Türkçe case-folding için basit `.lower()` kullanılıyor; ICU
    tabanlı tam (örn. 'İ'/'I' Türkçe büyük/küçük harf) çözüm bu prototipte
    bilerek kullanılmıyor.
    """
    if not aciklama:
        return 0.0
    metin = aciklama.lower()
    eslesme = sum(1 for k in KRITIK_KELIMELER if k in metin)
    if eslesme == 0:
        return 0.0
    return 0.30 if eslesme >= 2 else 0.20


@dataclass(frozen=True)
class OlayKumesiOzeti:
    """
    Öncelik skoru hesaplamasında kullanılan, bir olay kümesini özetleyen
    minimal veri. Django modeline bağımlı değildir; OlayKumesi + ilişkili
    Ihbar nesnelerinden bu özetin çıkarılması çağıran tarafın (view/service)
    sorumluluğundadır.
    """
    toplam_etkilenen_kisi: int
    toplam_yarali: int
    baskin_olay_turu: str
    gecen_dakika: float
    # Ekibe olan mesafeye dayalı ulaşılabilirlik puanı (0-100, yüksek =
    # daha kolay ulaşılabilir). Adım 5'te (ekip önerisi) gerçek bir değerle
    # doldurulana kadar None bırakılabilir; bu durumda nötr varsayılan
    # kullanılır.
    ulasilabilirlik_puani: Optional[float] = None
    # Kümedeki tüm ihbarların açıklamaları birleştirilmiş hali (kritik
    # kelime çarpanı bu metin üzerinde aranır — bkz. kritik_kelime_carpani).
    birlesik_aciklama: str = ''


def _dogrusal_olcekle(deger: float, doyma_esigi: float) -> float:
    """
    0 ile doyma_esigi arasındaki bir değeri 0-100 aralığına doğrusal olarak
    ölçekler; doyma_esigi'ni geçen değerler 100'de sınırlanır (clamp).
    """
    if doyma_esigi <= 0:
        return 100.0
    return max(0.0, min(100.0, 100 * deger / doyma_esigi))


def oncelik_skoru_hesapla(ozet: OlayKumesiOzeti) -> int:
    """
    Bir olay kümesi özetine bakarak 0-100 arası öncelik skoru üretir.

    Bileşenler:
      - kisi_etkisi    : toplam etkilenen kişi sayısı arttıkça yükselir.
      - tibbi_aciliyet  : toplam yaralı sayısı arttıkça yükselir.
      - olay_riski      : olay türüne göre sabit bir risk puanı (OLAY_TURU_RISK_PUANLARI).
      - ulasilabilirlik : ekibin olaya ne kadar kolay ulaşabileceği (bilinmiyorsa nötr).
      - zaman_faktoru   : müdahale edilmeden geçen süre arttıkça yükselir (aciliyet artar).

    Sonuç, settings.ONCELIK_AGIRLIKLARI ile ağırlıklandırılmış toplamın
    0-100 aralığına yuvarlanmasıyla elde edilir.
    """
    kisi_etkisi_esigi = _ayar('ONCELIK_KISI_ETKISI_DOYMA_ESIGI', 100)
    yarali_esigi = _ayar('ONCELIK_YARALI_DOYMA_ESIGI', 15)
    zaman_esigi = _ayar('ONCELIK_ZAMAN_DOYMA_ESIGI_DAKIKA', 180)
    risk_puanlari = _ayar('OLAY_TURU_RISK_PUANLARI', {})
    varsayilan_risk = _ayar('ONCELIK_VARSAYILAN_OLAY_RISKI', 40)
    varsayilan_ulasilabilirlik = _ayar('ONCELIK_VARSAYILAN_ULASILABILIRLIK', 50)
    agirliklar = _ayar('ONCELIK_AGIRLIKLARI', {
        'kisi_etkisi': 0.25,
        'tibbi_aciliyet': 0.30,
        'olay_riski': 0.20,
        'ulasilabilirlik': 0.15,
        'zaman_faktoru': 0.10,
    })

    bilesen_puanlari = {
        'kisi_etkisi': _dogrusal_olcekle(ozet.toplam_etkilenen_kisi, kisi_etkisi_esigi),
        'tibbi_aciliyet': _dogrusal_olcekle(ozet.toplam_yarali, yarali_esigi),
        'olay_riski': risk_puanlari.get(ozet.baskin_olay_turu, varsayilan_risk),
        'ulasilabilirlik': (
            ozet.ulasilabilirlik_puani
            if ozet.ulasilabilirlik_puani is not None
            else varsayilan_ulasilabilirlik
        ),
        'zaman_faktoru': _dogrusal_olcekle(ozet.gecen_dakika, zaman_esigi),
    }

    taban_skor = sum(
        bilesen_puanlari[bilesen] * agirlik
        for bilesen, agirlik in agirliklar.items()
    )
    taban_skor = max(0, min(100, taban_skor))

    carpan = kritik_kelime_carpani(ozet.birlesik_aciklama)
    final_skor = min(100, taban_skor * (1 + carpan))

    return int(round(max(0, final_skor)))
