# MVP P0 — Design Gereksinimleri

Durum: taslak · Kapsam: `frontend/` (React SPA) · Öncelik: P0 (MVP kapsamı)

Bu doküman, GeoRisk Engine MVP sürümü için **design tarafından teslim edilmesi gereken**
P0 işleri tanımlar. P1 ve kapsam dışı maddeler en sonda listelenmiştir.

Dayanak: [`GEORISK_ENGINE_REPOSITIONING.md`](../../GEORISK_ENGINE_REPOSITIONING.md),
[`GEORISK_PRODUCTION_ROADMAP_2026.md`](../../GEORISK_PRODUCTION_ROADMAP_2026.md) (Stage 2–4),
[`STUBS.md`](../../STUBS.md).

---

## Bugünkü UI durumu (yeniden çizilmemesi gerekenler)

| Var olan | Dosya | Notu |
|---|---|---|
| 5 adımlı portföy anlatısı (Upload → Hazard → Expected loss → Adaptation → Avoided loss) | `frontend/src/pages/PortfolioDemoPage.tsx` | Ürünün ana hikâyesi; iskelet doğru |
| Verification walkthrough (pipeline EAL vs recomputed EAL, MDR, vulnerability) | aynı dosya | Kanıt anlatısının çekirdeği |
| Tek varlık snapshot bileşenleri | `frontend/src/components/snapshot/*` | Header, metric grid, risk dimension bars, signal list, analyst verdict, timeline |
| Risk tiles ve harita | `frontend/src/pages/RiskTilesPage.tsx`, `frontend/src/RiskMap.tsx` | |
| Golden demo kısayolları (Antalya, Rotterdam Port) | `PortfolioDemoPage.tsx` | Alıcı demosu için korunmalı |
| TR/EN pazarlama sayfaları | `frontend/public/*` | Uygulama UI'ından ayrı |

**Yok:** login/workspace kabuğu, i18n altyapısı, ortak design system.
Stil bugün sayfa başına ayrı dosyalarda: `App.css`, `portfolio-demo.css`,
`pages/risk-tiles.css`, `pages/RiskSnapshot.css`.

---

## P0-1 · Trust & Claim Chip sistemi

**Problem.** Ürünün farkı "auditable evidence" iddiası, ancak güven sinyalleri arayüzde
dağınık ve tutarsız: `MethodBadge`, `data_mode: live | stub`, `production_eligible=false`,
fixture/live ayrımı, sentetik v0.x eğri etiketi. `STUBS.md` #3 gereği her sayısal değerin
bugün sentetik olduğu okunabilir olmalı.

**Palet.** Dört aile, üç renk + nötr. Değerler `frontend/src/index.css` token
ölçeğinden alınır; yeni renk türetilmez.

| Aile | Chip | Değer | Anlamı |
|---|---|---|---|
| teal | `VERIFIED` | `#2ec990` (teal-400) | Kaynak doğrulandı, lisans incelendi |
| teal | `LIVE` | `#5dcaa5` (teal-300) | Gerçek connector yanıtı, bu çalıştırmada alındı |
| amber | `FIXTURE` | `#ef9f27` *tint* | Deterministik test verisi — tekrarlanabilir, gerçek değil |
| amber | `SYNTHETIC` | `#ef9f27` (amber-500) | Etiketli sentetik hasar eğrisi |
| kırmızı | `DEGRADED` | `#e24b4a` *tint* | Birincil kaynak düştü, sonuç yedek yolla üretildi |
| kırmızı | `NOT_ELIGIBLE` | `#e24b4a` (red-500) | Karar amaçlı kullanılamaz |
| nötr | `MODELLED` | `#c3cedb` | Değer bir modelden çıktı, ölçüm değil |
| nötr | `DERIVED` | `#9aa8ba` | Başka değerlerden hesaplandı |
| nötr | `STALE` | `#9aa8ba` + kap: zemin `#101a2b`, kenar `#3b4d68` | Değer güncel çalıştırmadan gelmiyor |

**Tint / solid ayrımı.** Aynı ailede iki adım: *tint* = metin ailenin 500'ü, kenarlık
alfa `0.28`, zemin alfa `0.10`. *Solid* = aynı metin, kenarlık alfa `0.6`.
Aile hue'su durumu değil **sınıfı** anlatır; adım, sınıf içindeki şiddeti.

**İki eksen, iki yuva.** `LIVE / FIXTURE / SYNTHETIC / VERIFIED` "girdi nereden geldi"
sorusunu, `MODELLED / DERIVED / STALE` ise "bu değer girdisinden ne kadar uzak ve ne
kadar eski" sorusunu cevaplar. Bunlar **ayrı eksenler**; nötr ailenin ayrı bir renk
ailesi olması bunun doğru refleksi. Ancak bu iki eksen aynı chip yuvasında yarışmamalı:
bir değer aynı anda `LIVE` ve `STALE` olabilir. Kaynak yuvası solda, türetme yuvası
sağda, sabit sırayla.

**STALE'e metin eki zorunlu.** `STALE` ile `DERIVED` yalnızca kap ile ayrılıyor
(koyu zemin + parlak kenar). Bu fark, rapora %60 ölçekte yapıştırılan bir ekran
görüntüsünde kayboluyor — ve kredi dosyasında en tehlikeli durum tam olarak bu: bayat
bir sayının güncel görünmesi. Chip yaşı taşımalı: `STALE · 14d`.

**Yerleşim ölçekleri.**
1. **Değer** — sayının yanında satır içi (kaynak yuvası + varsa türetme yuvası)
2. **Bölüm** — bölüm başlığıyla aynı hizada; o bölümdeki **en zayıf** değerin durumu
3. **Sayfa** — kapatılamayan üst bant; yalnızca `NOT_ELIGIBLE` buraya çıkar

**Açık kalan iki soru.** Eski sözlükteki `blocked` (kaynak sonuca giremedi) ve
`not-validated` (bu kullanım için ampirik doğrulama yok) yeni dokuzlukta karşılıksız.
`blocked` manifest satırında hâlâ gerekli — kırmızı ailenin üçüncü adımı mı olacak,
yoksa chip değil satır durumu mu? `not-validated` ise `NOT_ELIGIBLE` içine mi katlanıyor?
Bu ikisi cevaplanmadan claim-control testi yazılamaz.

**Kabul kriterleri.**
- Ekranda kaynağı belirsiz tek bir sayı kalmaz.
- Aynı durum her ekranda aynı görünür ve aynı string'i kullanır.
- İki eksen aynı yuvada çakışmaz.
- Roadmap Stage 4 "claim-control tests across API, reports and frontend wording" maddesi
  bu sözlüğe karşı otomatik test edilebilir.

---

## P0-2 · Evidence / Audit Viewer ekranı

**Problem.** `audit_id` API yanıtlarında var (`/v1/risk/score`, `/v1/risk/batch`,
`industrial_verification.linked_audit_id`) ancak UI'da hiçbir karşılığı yok. Regüle
alıcıya farkı anlatan tek ekran budur ve MVP'de eksiktir.

**Kapsam.** `audit_id` ile açılan tek ekran:
- Kimlik bloğu: `audit_id`, `generated_at`, `model_version`, methodology sürümü.
- Source manifest: kullanılan her veri kaynağı, sürümü, lisans durumu, tarihi, sınırları.
- Hash / bütünlük bölümü: girdi ve yanıt hash'leri, zincir durumu.
- Limitation panel: bu sonucun neyi **söylemediği** (ör. yükseklik gözlemi sel olasılığı değildir).
- Kanıt indirme: JSON evidence + rapor bağlantısı.
- Sonuca geri dönüş: bu audit'in ürettiği portföy/varlık ekranına link.

**Design teslimatı.** Ekran düzeni, uzun manifest listesi için tablo/akordeon deseni,
hash gösterimi (kısaltma + kopyala), "kanıt bloke" ve "kanıt eksik" durumlarının görünümü,
paylaşılabilir/yazdırılabilir hali.

**Kabul kriterleri.**
- Bir `audit_id` ile gelen kişi, o sonucu yeniden üretmek için gereken her referansı ekranda görür.
- Eksik veya bloke kanıt, sonucu gizlemeden ama sonuç iddiasını zayıflatarak gösterilir (GEO-201 mantığı).

---

## P0-3 · Portfolio upload akışının tam tasarımı

**Problem.** Bugün akış "dosya seç + valuation date"ten ibaret. Sonuçta
`Analyzed assets 87/120` gibi bir kapsam rakamı görünüyor, ancak **kalan varlıklara ne olduğu
görülemiyor**. Alıcının ilk sorduğu soru budur.

**Kapsam.**
1. **Kolon eşleştirme:** yüklenen CSV/XLSX kolonlarının asset şemasına eşlenmesi, otomatik tahmin + manuel düzeltme.
2. **Satır bazlı doğrulama:** zorunlu alan eksik, geçersiz koordinat, geçersiz para birimi/değer, tarih formatı.
3. **Triyaj listesi:** analiz dışı kalan her varlık ve nedeni (geocode başarısız, kapsam dışı ülke/pack yok, değer eksik), filtrelenebilir ve dışa aktarılabilir.
4. **Yeniden çalıştırma:** düzeltilen satırlarla tekrar deneme, önceki çalıştırmayı kaybetmeden.
5. **Sınırlar:** batch limiti, dosya boyutu limiti ve aşıldığında görünen mesaj (Stage 3 rate/size/batch limitleri).

**Kabul kriterleri.**
- Kapsam rakamı her zaman tıklanabilir; tıklanınca dışarıda kalan varlıklar nedenleriyle listelenir.
- Hiçbir varlık sessizce düşmez.

---

## P0-4 · Asset detail drill-down

**Problem.** Portföy tablosundan tek varlığa inen bir yol yok. `components/snapshot/*`
bileşenleri bu ekranın yaklaşık %60'ı, ancak portföy bağlamına bağlı değil.

**Kapsam.** Portföy tablosundaki satırdan açılan varlık ekranı:
- Beş katmanın tek varlık için şelale (waterfall) gösterimi: hazard → vulnerability → EAL → adaptation → avoided loss.
- Varlık konumu ve çevresel bağlam haritası.
- Horizon değerleri (bugün / 2030 / 2050) tek yerde.
- O varlığa ait `audit_id` ve P0-2 ekranına link.
- Mevcut snapshot bileşenlerinin yeniden kullanımı; yeni görsel dil üretilmemesi.

**Kabul kriterleri.**
- Portföy → varlık → kanıt yolu kesintisiz.
- Şelalede her adımın kaynağı P0-1 chip'leriyle etiketli.

---

## P0-5 · Design system / token seti

**Problem.** Sayfa başına ayrı CSS dosyaları (`App.css`, `portfolio-demo.css`,
`risk-tiles.css`, `RiskSnapshot.css`) var; ortak token yok. Her yeni ekranın maliyeti
artıyor ve aynı kavram farklı sayfada farklı görünüyor.

**Yüzeyler ve metin.**

| Rol | Değer | Kaynak |
|---|---|---|
| Sayfa zemini | `#0a1628` | `--ink` |
| Panel | `#131f33` | türetildi |
| Inset / koyu zemin | `#101a2b` | verildi |
| Kenarlık | `#22304a` | türetildi |
| Vurgulu kenarlık | `#3b4d68` | verildi |
| Gövde metni | `#e6edf5` | türetildi |
| İkincil metin | `#9aa8ba` | verildi |
| Birincil aksan | `#2ec990` | `--teal-400` |

Panel, inset ve kenarlık değerleri verilen üç ankraja (`#9aa8ba`, `#101a2b`, `#3b4d68`)
göre türetildi; canvas'taki gerçek değerler farklıysa tek satırda düzeltilir.

**Tipografi.** Inter. Başlıklar **800** ağırlık, tracking `-0.02em`. Gövde 400/500.
Sayı, kimlik, hash ve chip metni `tabular-nums`. Chip metni koddaki string ile birebir
aynı — çeviri tooltip'e girer, chip'e girmez.

**Risk bandı skalası.** Üç aile + nötr sistemine oturur; ayrı bir hue açılmaz:

| Band | Değer |
|---|---|
| `LOW` | `#5dcaa5` (teal-300) |
| `MODERATE` | `#ef9f27` (amber-500) |
| `HIGH` | `#e24b4a` (red-500) |
| `SEVERE` | `#b3352f` (red, koyu adım) |

`HIGH` ve `SEVERE` gri tonda birbirine yakın — bu yüzden band **her yerde metin
etiketiyle** çıkar, hue tek başına anlamı taşımaz. Dört band yerine üçe inmek
(aile başına bir band) daha temiz olur; bu bir ürün kararı, tasarım kararı değil.

**Diğer.**
- Panel radius 12px, kontrol radius 8–10px, chip radius 4px.
- Kontrol yüksekliği masaüstünde 36px, dokunmalı yüzeylerde en az 44px.
- **Sayı biçimleri:** para (TRY/EUR/USD), yüzde, büyük sayı kısaltması, belirsizlik aralığı.
- **Tablo deseni:** yoğunluk, sıralama, sabit başlık, satır seçimi, sayfalama.
- **Durum ekranları:** boş, yükleniyor, hata, **kısmi başarı**, **degraded** —
  son ikisi hata değildir, hatadan ayrı görsel dile sahiptirler.
- **Erişilebilirlik:** kontrast, klavye navigasyonu, odak görünürlüğü, `aria` etiketleri —
  Stage 2 çıkış kriteri "API/UI contract and accessibility tests pass" bunu şart koşuyor.

**Kabul kriterleri.**
- Mevcut dört sayfa tek token setiyle yeniden ifade edilebilir.
- Kısmi başarı ve degraded, hata ile karıştırılmayacak biçimde ayrı.
- Hiçbir renk token seti dışından gelmez.

---

## Teslim sırası

1. P0-5 token seti + P0-1 chip sistemi (diğer üçünün ön koşulu)
2. P0-3 upload akışı
3. P0-4 asset drill-down
4. P0-2 evidence viewer

P0-2 en son geliyor çünkü chip sözlüğü ve token seti oturmadan kanıt ekranı yeniden çizilir.

---

## P0 kapsamı dışında (referans)

**P1:** senaryo/horizon karşılaştırma UI'ı · adaptation seçenek karşılaştırma tablosu
(maliyet / avoided loss / residual risk / geri ödeme) · rapor & export merkezi
(`/v1/reports/risk`, `/v1/reports/risk/pdf` uçları var, UI yok) · asenkron batch job
durumu ve ilerleme · harita katman/legend tasarımı · auth/workspace kabuğu ve API key
yönetimi (Stage 3) · TR/EN i18n.

**Kapsam dışı:** genel amaçlı climate map explorer · widget sürüklenen özelleştirilebilir
dashboard · emisyon/ESG modülü. README'deki "is not" tablosu bunları dışlıyor; MVP'ye
eklemek konumlandırmayı bozar.
