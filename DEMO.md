# AFETOS — Demo Senaryosu

Bu doküman, projenin özgün değerini (güven skoru + öncelik skoru + ihbar
kümeleme + ekip önerisi tek pakette) uçtan uca göstermek için hazırlanmış
adım adım bir demo akışıdır.

## Hazırlık

```bash
python manage.py seed_demo
python manage.py runserver
```

`seed_demo` komutu **mevcut İhbar/OlayKümesi/Ekip verisini temizleyip**
şunları oluşturur (gerçek skor/kümeleme algoritmasıyla, elle atanmış
sayılarla DEĞİL):

- **6 ekip** — Kahramanmaraş ve Hatay bölgesine dağılmış, farklı tür
  (arama_kurtarma / sağlık / lojistik) ve durumda (boşta / görevde / yolda)
- **3 önceden oluşturulmuş olay kümesi**:
  - **Küme A** (Kahramanmaraş merkez, enkaz, 4 tutarlı ihbar) → yüksek güven (~91), orta-yüksek öncelik (~68)
  - **Küme B** (Kahramanmaraş, tıbbi, 2 ihbar) → orta güven (~68)
  - **Küme C** (Hatay, yangın, 1 doğrulanmamış ihbar) → düşük güven (~47), **silinmedi**, "Doğrulanıyor" durumunda
- **5 rol bazlı test kullanıcısı** (tümünün şifresi `demo1234`):

| Kullanıcı adı | Rol | Girince nereye gider |
|---|---|---|
| `koordinator1` | Yönetici/Koordinatör (`is_staff=True`) | Ana Panel (`/`) — tüm sayfalara erişir |
| `saha1` | Saha Ekip Üyesi (AFAD Arama Kurtarma-1'e bağlı) | Görevim (`/gorevim/`) |
| `saha2` | Saha Ekip Üyesi (Sağlık Ekibi-1'e bağlı) | Görevim (`/gorevim/`) |
| `5551112233` | Vatandaş (Küme A'daki ilk ihbarı bildirmiş) | Vatandaş Paneli (`/vatandas/`) |
| `5551112244` | Vatandaş | Vatandaş Paneli (`/vatandas/`) |

Aşağıdaki demo adımları **koordinatör olarak giriş yapmayı** varsayar
(`http://localhost:8000/login/` → `koordinator1` / `demo1234`).

> Not: Yeni açılan bir küme, ilk ihbarında genelde düşük güvenle başladığı
> için sistem onu otomatik "Doğrulanıyor" durumuna alır. Bu durum
> **otomatik geri alınmaz** — güven skoru sonradan yükselse bile, kümeyi
> ilerletmek (ör. "Müdahale Ediliyor") bilerek bir insan kararı olarak
> Yönetim Paneli'nden yapılır. Bu, sistemin "karar vermez, karar
> vericiye yardımcı olur" ilkesiyle tutarlıdır.

## Adım Adım Demo

### 1) Mevcut olayları haritada gör
`http://localhost:8000/olaylar/harita/` adresine git. Üç bölgede renkli
marker'lar (kümeler) ve altı ekip marker'ı görünmeli. Marker'a tıklayınca
öncelik/güven skorunu ve ihbar sayısını gösteren popup açılır.

### 2) Yeni bir kritik ihbar oluştur
`http://localhost:8000/ihbarlar/olustur/` sayfasına git ve **Küme A'nın
hemen yanında** (yani ~400m yarıçap içinde), yüksek kişi/yaralı sayılı,
tıbbi ihtiyaç belirten bir ihbar gir:

| Alan | Değer |
|---|---|
| Enlem (lat) | `37.5862` |
| Boylam (lng) | `36.9374` |
| Olay Türü | Tıbbi |
| Açıklama | "Enkaz bölgesinde çok sayıda yaralı var, acil tıbbi müdahale gerekiyor." |
| Tahmini Etkilenen | 30 |
| Tahmini Yaralı | 12 |

Gönder.

### 3-4) Sistem ihbarı kaydeder, önceki ihbarlarla ilişkisini kurar
Form gönderilince sistem otomatik olarak ihbar detay sayfasına yönlendirir.
Sayfada **"Olay Kümesi Değerlendirmesi (#…)"** kartında, bu ihbarın
**Küme A'ya eklendiğini** (aynı küme ID'si, artan ihbar sayısı) göreceksin
— konum yakınlığı sayesinde ayrı bir küme açılmadı, mevcut olayla
ilişkilendirildi (haversine tabanlı kümeleme, adım 4).

### 5) Güven skoru ve doğrulama durumu
Aynı kartta öncelik skoru, güven skoru ve küme durumu gösterilir. 5 ihbara
çıkan kümenin güven skoru daha da yükselmiş olmalı (bağımsız ihbar sayısı
arttıkça güven artıyor — adım 2'deki algoritma).

### 6) Sistem uygun ekip önerir
Sayfanın altındaki **"Önerilen Ekip"** kartında, tıbbi ihtiyaca uygun ve şu
an boşta olan bir sağlık ekibinin (ör. *Sağlık Ekibi-1*) önerildiğini
göreceksin — kural tabanlı eşleştirme + mesafe sıralaması (adım 5).

### 7) Yönetici ekibi atar ve durumu günceller
`http://localhost:8000/yonetim/` (Yönetim Paneli) sayfasına git:
1. İlgili kümenin satırında **"Ekip Ata"** açılır menüsünden önerilen
   ekibi seç ve **Ata**'ya bas.
2. Aynı satırda **Durum** açılır menüsünden **"Müdahale Ediliyor"**'u seç.

Her iki işlem de htmx ile sadece o satırı günceller, sayfa yenilenmez.

### 8) Canlı güncellemeyi izle
7. adımı uygulamadan ÖNCE, ayrı bir tarayıcı sekmesinde
`http://localhost:8000/` (Ana Panel) veya `/olaylar/harita/` sayfasını aç.
Yönetim Paneli'nde ekip atayıp durumu güncellediğinde, **diğer sekmedeki
sayfa hiç yenilenmeden** (WebSocket üzerinden) güncel öncelik/güven
skorlarını, yeni durumu ve atanan ekibi anında göstermeli (adım 7).

## Sıfırdan tekrar denemek için
```bash
python manage.py seed_demo
```
Bu, önceki demo sırasında eklediğiniz ihbar ve atamalar dahil tüm
İhbar/OlayKümesi/Ekip verisini temizleyip senaryoyu baştan kurar.
