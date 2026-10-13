# MVP Implementation Plan

Hedef kitle: bu planı uygulayacak geliştirici ajan. Her iş paketi (WP) bağımsız
çalıştırılabilir, kendi kabul kriterleri ve testleri var.

Temel alınan MVP tanımı — README P0 dikeyi ve
[`GEORISK_PRODUCTION_ROADMAP_2026.md`](../../GEORISK_PRODUCTION_ROADMAP_2026.md) Stage 2–3:

> Bir bankadaki kredi/risk analisti 50–500 varlıklık bir teminat portföyü yükler;
> beş katmanlı EAL + adaptasyon + kaçınılan kayıp alır; ve bir denetçiye
> **geri çağrılabilir, doğrulanabilir** bir kanıt kaydı verebilir —
> hepsi `production_eligible=false` etiketi altında.

Bu tanıma göre eksikler aşağıda. Sıra bağımlılık sırasıdır.

Ajana verilecek komutlar en sonda: [Ajana verilecek komut](#ajana-verilecek-komut).

---

## Doğrulama notu

Bu analiz kod okunarak yapıldı. **Test suite bu konteynerde çalıştırılamadı** —
`.venv` yok, `fastapi` kurulu değil. Bu yüzden "mevcut durum" ifadeleri kod
referanslarına dayanıyor, geçen teste dayanmıyor. WP-0 bunu kapatır.

---

## Mevcut durum — çalışan ne var

Planı daraltmak için önce bunlar yeniden yapılmamalı:

| Var olan | Kanıt |
|---|---|
| Beş katmanlı pipeline sözleşmesi, tam | `app/pipeline/contract.py` — `HazardResult`, `ExposureResult`, `VulnerabilityResult`, `FinancialTranslationResult` (`eal_absolute`, `eal_pct_of_value`, `collateral_sensitivity`, `insurability`), `AdaptationEvidenceResult` (`avoided_loss`, `residual_eal`) |
| Hash zincirli append-only audit trail | `app/services/audit_trail.py` — `compute_record_hash`, `AppendOnlyAuditTrail.append/get/verify_chain` |
| Rate limit, gövde boyutu, upload limiti | `app/core/rate_limit.py`, `app/core/request_body_limit.py`, `app/api/portfolio.py:67-93`, `tests/test_api_limits.py` |
| Portföy ingest + kolon alias'ları | `app/services/portfolio_ingest.py:20` `_COLUMN_ALIASES` |
| Hariç tutulan varlıkların partition'ı | `analyzed[]` / `excluded[]` — STUBS #19 |
| Runtime mode kapısı (prod'da stub reddi) | `app/core/runtime_mode.py`, `assert_production_live_sources` |
| Country pack mimarisi | `app/packs/` (pack-tr), `app/nl_pilot/` |
| Async DB katmanı + Alembic | `app/db/`, `app/storage/case_repository.py`, `alembic/versions/202607040001_init_cases_schema.py` |
| 88 test dosyası, dizin bazlı organize | `tests/` |

Yani MVP'nin **hesap motoru** büyük ölçüde duruyor. Eksikler kimlik, kalıcılık,
kanıtın geri çağrılabilirliği ve giriş verisi tarafında.

---

## WP-0 · Baseline (kod yok)

**Amaç.** Plan boyunca kıyaslanacak bilinen-iyi bir durum.

**Adımlar.**
1. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt`
2. `PYTHONPATH=. pytest --deselect tests/test_live_connector_credentials.py::test_oras5_cdsapi_client_accepts_bare_uuid_key -q`
3. `cd frontend && npm ci && npx tsc -b && npx eslint .`
4. Sonuçları (geçen/düşen sayısı, süre, varsa kırmızılar) `docs/00-master/MVP_BASELINE.md` olarak yaz.

**Kabul.** Üç komut da yeşil, veya her kırmızı için kök nedeni yazılmış.
**Sınır.** Bu pakette ürün kodu değiştirilmez. Kırmızı test varsa düzeltmeyi WP'lere dağıt.

---

## WP-1 · Kimlik ve kiracılık

**Eksik.** **Hiç kimlik doğrulama yok.** `app/core/` içinde auth modülü yok; hiçbir
route'ta auth `Depends` yok; API key / organizasyon modeli yok. `/v1/portfolio/upload`,
`/v1/risk/score`, `/v1/cases` dahil her uç nokta herkese açık. Roadmap Stage 3 scoped
API key veya organizasyon/workspace auth istiyor. Çevresindeki sertleştirme (rate limit,
boyut limitleri) zaten var — eksik olan yalnızca kimlik.

**Yapılacak.**
1. `app/core/auth.py`: `ApiKey` modeli (hash'lenmiş secret, `organisation_id`, `scopes`, `expires_at`, `revoked_at`), `require_scopes(...)` FastAPI dependency'si.
2. Alembic migration: `organisations`, `api_keys` tabloları.
3. Scope seti: `risk:read`, `portfolio:write`, `evidence:read`, `reports:write`, `admin`.
4. Her router'a dependency ekle. `/v1/health` ve `/v1/release-manifest` açık kalır.
5. Rate limit anahtarını IP'den `organisation_id`'ye taşı (`app/core/rate_limit.py`, `app/core/client_ip.py` IP fallback olarak kalsın).
6. `scripts/` altına key üretme/iptal CLI'ı.

**Kabul.**
- Anahtarsız istek `401`, yetersiz scope `403` — ikisi de `ErrorEnvelope` formatında (`app/schemas/errors.py`).
- Anahtar gövde/log/hata mesajında asla görünmez; yalnızca hash saklanır.
- `tests/test_auth.py`: her korunan uç nokta için anahtarsız/geçersiz/süresi geçmiş/iptal edilmiş/yetersiz scope — beşi de.
- Mevcut testler `conftest.py` içinden verilen test anahtarıyla geçmeye devam eder.

**Sınır.** Kullanıcı/şifre, SSO, MFA bu pakette yok. Sadece makineden makineye API key.

**Açık kabul kriteri — organizasyon bazlı rate limit (madde 5).** Henüz karşılanmadı.
Rate limit middleware'i kimlik doğrulamadan önce çalışıyor; doğrulanmamış bir anahtara göre
kova seçmek, her istekte yeni anahtar göndererek limitin atlatılmasına izin veriyordu. Bu
yüzden limit şimdilik **istemci IP'sine** göre. IP bazlı limit organizasyon başına limit
gereksinimini **tamamlamaz**; doğrulanmış principal üzerinden, auth'tan sonra çalışan bir
limit gerekir.

**Karar (9 Ekim 2026) — demo erişimi.** Herkese açık demo, anahtarsız yalnızca sabit
sentetik veriyle ve izole demo kaynaklarıyla çalışabilir. Gerçek organizasyon verileri,
kayıtlı raporlar, batch sonuçları ve kalıcı yazma işlemleri kimlik doğrulaması ister;
`APP_ENV=demo` tek başına bu korumayı kaldırmaz. Özel API anahtarı frontend koduna veya
tarayıcıya konmaz.

Bugünkü durum: demo uçları izole **değil** — `/v1/demo/run` ve risk skorlaması ortak
snapshot store'a yazıyor, `/v1/portfolio/demo-run*` gerçek yüklemelerle aynı audit izine
ekliyor. Bu yüzden `production` ve `demo` ortamlarında API anahtarı her zaman zorunlu
(`API_KEY_REQUIRED=false` bu ortamlarda yok sayılır). Sonuç: yayındaki demo arayüzü, izole
anonim demo uçları kurulana kadar API'den `401` alır. Anonim demo için gereken (ayrı iş
emri): sabit preset girdili salt-okunur uçlar, ortak audit izine ve snapshot store'a
yazmayan ya da ayrı bir demo organizasyonuna/izine yazan bir yol, ve bunu ölçen testler.

---

## WP-2 · Kalıcı durum

**Eksik — iki yerde.**
1. `app/services/asset_snapshot_store.py:23` — `_store: dict[str, AssetSnapshot] = {}`. Snapshot'lar süreç belleğinde; restart'ta siliniyor. `/v1/cases` ve snapshot okuma yolları buna bağlı. (Roadmap GEO-72)
2. Audit trail dosya tabanlı JSONL ve **mount edilmiş volume yoksa geçici** (STUBS #20). Ürünün "denetlenebilir" iddiasını taşıyan yapı, sistemin en kalıcı olmayan parçası.

**Yapılacak.**
1. `asset_snapshots` tablosu + `app/storage/snapshot_repository.py`; `asset_snapshot_store` API'sini koruyarak arkasını Postgres'e al (in-memory implementasyon yalnızca test fixture'ı olarak kalsın).
2. `audit_trail_records` tablosu: `record_id`, `prev_hash`, `record_hash`, `payload` (JSONB), `created_at`, `organisation_id`. `AppendOnlyAuditTrail`'e `PostgresAuditTrailStore` backend'i ekle; dosya backend'i yerel geliştirme için kalsın.
3. `runs` tablosu: portföy çalıştırması başına bir satır (`run_id`, `organisation_id`, `portfolio_id`, `valuation_date`, `methodology_version`, `analyzed_count`, `excluded_count`, `created_at`).
   **WP-2 yalnızca tabloyu ve `RunRepository`'yi teslim eder;** gerçek portföy çalıştırmaları
   bu tabloya henüz yazmaz. Bağlantı WP-3'ün zorunlu kabul kriteridir (aşağıda "Açık kalan").
4. ~~`/v1/health` readiness'a zincir bütünlüğü kontrolü ekle (`verify_chain()` tip hash'i).~~
   **Superseded (9 Ekim 2026):** herkese açık sağlık uçları (`/health`, `/v1/health`) zincir
   bilgisi taşımaz — tip hash, kayıt sayısı ve bütünlük durumu kimliksiz çağırana açılmaz.
   Yerine: `GET /v1/audit-chain/verify` (scope `evidence:read`). Organizasyon doğrulanmış
   principal'dan türetilir; uç organizasyon argümanı almaz. Boş zincir `empty` döner, asla
   `intact` değil.

**Kabul.**
- `append` → süreç yeniden başlat → `get(record_id)` aynı kaydı döndürür, `verify_chain()` `True`.
- Hash zinciri tabloda da kırılmaz: `prev_hash` üzerinde FK/unique kısıt, `record_hash` unique.
- `tests/test_audit_trail_persistence.py` ve `tests/test_snapshot_repository.py` (aiosqlite ile).
- Alembic `upgrade head` → `downgrade -1` → `upgrade head` temiz çalışır.

**Sınır.** Veri taşıma (migration of existing JSONL) gerekmiyor — demo verisi.

**Zincir tasarımı (WP-2'de verilen kararlar).**
- **Zincir organizasyon başına bağımsızdır;** tek global zincirin organizasyon filtresiyle
  okunması değildir. Her organizasyonun kendi genesis kaydı (`prev_hash` = genesis), kendi
  tip'i ve kendi bağları var; `(organisation_id, prev_hash)` unique. Bir organizasyonun
  zincirini bozmak diğerinin doğrulamasını etkilemez.
- **`organisation_id` hash'lenen payload'un içindedir,** yalnızca kolon değildir. Aksi halde
  bir zincirin `organisation_id` kolonu topluca değiştirilince zincir başka organizasyona
  taşınır ve orada `intact` doğrulanırdı. Doğrulama, payload'daki sahibin zincirin sahibiyle
  aynı olmasını ister (`AUDIT_CHAIN_OWNER_MISMATCH`).
- **`get(record_id)` organizasyona bağlıdır:** başka organizasyonun kaydı "yok" ile aynı
  döner (`None`), varlığı sızmaz. WP-3'ün çapraz kiracı `404` kuralı buna dayanır.
- **`append` mevcut zinciri yeniden doğrulamaz.** Her yazmada tam zincir okumak gerekirdi;
  ayrıca bozuk zincir append ile onarılmaz (INV-03). Sonuç: kurcalanmış bir zincire eklenen
  kayıt bozuk bağın üstüne zincirlenir ve zincir `broken` kalır. Bozulmayı tespit etmek
  doğrulamanın işidir (`verify_chain_report`, `/v1/audit-chain/verify`), yazmanın değil.
- **Dosya izi tek global zincirdir** (organizasyon yok). Organizasyon bazlı bütünlük iddiası
  yalnızca veritabanı store'u için yapılabilir.

**Açık kalan — WP-3'ün sorumluluğu (karar, 9 Ekim 2026).** WP-2'nin kapsamı: veritabanı
tabloları, repository katmanı, snapshot kalıcılığı ve audit zinciri doğrulaması. WP-2
**uçtan uca run kalıcılığı sağlamaz:**
- Portföy çalıştırmaları hâlâ dosya izine yazıyor (`get_audit_trail()`, STUBS #20);
  `PostgresAuditTrailStore` hiçbir pipeline yolundan çağrılmıyor. `/v1/audit-chain/verify`
  her yanıtta `limits` içinde `AUDIT_STORE_NOT_WIRED` taşır ve pipeline'ın ürettiği kanıtın
  bütünlüğünü **henüz kanıtlamaz**.
- `RunRepository.create_run` testleri dışında hiçbir yerden çağrılmıyor; `runs` tablosu gerçek
  kullanımda boş kalır. Analiz/dışlama sayıları ve yöntem sürümü restart'ta hâlâ kaybolur.

Bu ikisinin bağlanması WP-3 madde 0'dır ve WP-3'ün **zorunlu kabul kriteridir** — teknik borç
değil. *(Durum: WP-3 PR'ında uygulandı — aşağıda WP-3 "Uygulama notları". Bu bölüm WP-2
sonundaki durumu kaydeder; silinmedi.)* WP-3 tamamlanmadan run kalıcılığı ve veritabanı audit izi production-ready ilan
edilmez. Bu karar kapsamı değiştirir; incelemede bulunan eksikliği (runs tablosunun
bağlanmaması) çözülmüş saymaz.

---

## WP-3 · Kanıt API'si

**Eksik.** `audit_id` her yanıtta dönüyor ama **hiçbir uçtan geri çağrılamıyor.**
`AppendOnlyAuditTrail.get()` ve `verify_chain()` servis katmanında var
(`app/services/audit_trail.py:225,228`), HTTP'ye açılmamış. Kanıt paketi ihracı da yok —
desen yalnızca NL pilotunda mevcut (`app/nl_pilot/pilot_evidence_pack.py`).

Bu, ürünün regüle alıcıya anlattığı farkın tam kendisi. MVP'de en yüksek değerli paket bu.

**Yapılacak.**
0. **Run ve audit kalıcılığı birlikte (WP-2'den devralınan, zorunlu).** Gerçek portföy
   çalıştırmaları `runs` tablosuna (`RunRepository`) ve veritabanı audit zincirine
   (`PostgresAuditTrailStore`, `organisation_id=principal.organisation_id`) **birlikte**
   bağlanır. İkisi aynı çalıştırmanın iki kanıtıdır; birbirinden bağımsız yazılmaları kanıt
   bütünlüğü riskidir.
   - **Invariant:** başarılı bir çalıştırmanın run satırı ve audit kaydı **aynı transaction
     içinde** kalıcılaşır; biri başarısız olursa ikisi de rollback edilir. Yarım kayıt
     (audit'siz run ya da run'sız audit) oluşmaz.
   - **Gereken tasarım değişikliği:** `PostgresAuditTrailStore.append` bugün kendi oturumunu
     açıp commit ediyor; çağıranın oturumunu/transaction'ını kabul edecek şekilde değişmeli.
     `RunRepository.create_run` yalnızca `flush` eder, commit'i çağırana bırakır. Tip
     yarışında (`IntegrityError`) yeniden deneme, run satırını da kapsayan transaction
     düzeyinde yapılır.
   - Run satırı ile audit kaydı birbirine bağlanır, böylece aynı çalıştırmaya ait oldukları
     doğrulanabilir.
   - Dosya izi yalnızca DB'siz yerel geliştirmede kalır. Bağlantı kurulunca
     `AUDIT_STORE_NOT_WIRED` limitini `/v1/audit-chain/verify` yanıtından kaldır ve bunu
     ölçen testi güncelle. Kanıt uçları kaydı `get(record_id, organisation_id=…)` ile okur.
1. `GET /v1/evidence/{audit_id}` → kimlik bloğu (`model_version`, `methodology_version`, `country_pack`, `source_commit`, `generated_at`), bütünlük bloğu (`request_hash`, `response_hash`, `prev_hash`, zincir durumu), kaynak manifesti (WP-4), limitler bloğu.
2. `GET /v1/evidence/{audit_id}/verify` → zinciri yeniden hesaplar, `{"chain": "intact" | "broken", "verified_at": ...}`.
3. `GET /v1/evidence/{audit_id}/export` → tek dosya JSON kanıt paketi; `app/nl_pilot/pilot_evidence_pack.py` desenini genelleştir.
4. Limitler bloğu veriden üretilir, elle yazılmaz: aktif stub'lar, `production_eligible`, `model_validated_for_use_case`, eksik horizon'lar.
5. Scope: `evidence:read`. Organizasyon izolasyonu — başka kiracının `audit_id`'si `404` (403 değil; varlığı sızdırma).

**Kabul.**
- Portföy çalıştırmasından dönen `audit_id` ile üç uç nokta da çalışır.
- Bloke/eksik kaynak yanıtta **görünür** kalır, sessizce düşmez (GEO-201 mantığı).
- Zincir bozulduğunda `verify` `broken` döner ve `GET /v1/evidence/{id}` sonucu **gizlemez**, iddiasını zayıflatır.
- `tests/test_evidence_api.py`: mutlu yol, çapraz kiracı 404, bozuk zincir, eksik horizon'un limitler bloğunda görünmesi.
- **Run + audit atomikliği (madde 0, zorunlu):** başarılı her portföy çalıştırması tam bir
  `runs` satırı ve ona bağlı bir veritabanı audit kaydı üretir. Audit append'i başarısız
  olunca run satırı kalmaz; run yazımı başarısız olunca audit kaydı kalmaz — ikisi de testle
  gösterilir (hata enjeksiyonuyla). Bu kriter karşılanmadan WP-3 tamamlanmış sayılmaz.

**Sınır.** PDF kanıt paketi bu pakette yok; mevcut `/v1/reports/risk/pdf` yolu ayrı.

**Uygulama notları (WP-3 PR'ı).**
- **Madde 0 — run + audit birlikte.** `app/services/portfolio_run_service.py`
  `execute_persisted_run`: organizasyonun DB tip'i okunur; senkron pipeline bellekteki bir
  `StagedAuditTrail` üzerinde çalışır (kayıtlar DB store'unun mühürleme kuralıyla, o tip'ten
  zincirlenir); sonra tüm kayıtlar ve run satırı **tek transaction'da** yazılır. Herhangi bir
  hata ikisini birlikte geri alır (`RUN_PERSISTENCE_FAILED`). Tip yarışı unique kısıtla
  reddedilir ve run yeni tip'e karşı yeniden hesaplanır (`AUDIT_CHAIN_CONTENDED` deneme
  bitince). Kayıt üretmeyen run reddedilir (`RUN_WITHOUT_AUDIT_RECORD`).
- **Bağ.** Her kaydın hash'lenen payload'una `organisation_id`, `source_commit` ve `run_id`
  mühürlenir — pipeline hangi yoldan yazarsa yazsın (EAL kaydı kullanıcı parametrelerini
  taşımadığı için parametre yolu yetmiyordu).
- **Bağlanan uçlar:** `/v1/portfolio/analyze`, `/v1/portfolio/demo-run`,
  `/v1/portfolio/demo-run/golden-*`. Bunlar artık kalıcı run yazdığı için demo-run uçları da
  `portfolio:write` ister. Yanıtlar `run_id` taşır.
- **DB yoksa:** yalnızca local/dev/test dosya izine düşer (STUBS #20; run satırı yok,
  `run_id: null`). `production` ve `demo` run'ı reddeder (`AUDIT_STORE_UNAVAILABLE`).
- `/v1/audit-chain/verify` artık `AUDIT_STORE_NOT_WIRED` taşımaz.
- **Kanıt uçları** `app/api/evidence.py`; bloklar `app/services/evidence_service.py`'de
  veriden üretilir: kimlik (yöntem sürümü, `data_versions`, `source_commit`, üretim zamanı),
  bütünlük (`request_hash`/`response_hash` = girdi/çıktıların kanonik sha256'sı, kayıt hash'i,
  zincir durumu), run satırı, limitler (sentetik girdiler, eksik horizon'lar,
  `production_eligible` ve `model_validated_for_use_case` release manifest'ten).
  `integrity_status` yalnızca kayıt hash'i tutar ve zincir `intact` ise `intact` olur (yoksa
  `broken`). "verified" denmez: glossary'de doğrulama, bağımsız yeniden hesaplamadır (INV-07); bu
  bir bütünlük ifadesidir, sayının doğrulandığı iddiası değildir.
- **Açık kalanlar (bu PR'da yok, yanıtta görünür):**
  - Kaynak manifesti WP-4'tür: `source_manifest.status = "not_available"`,
    `SOURCE_MANIFEST_NOT_AVAILABLE` limitlerde; yalnızca beyan edilen sürümler listelenir.
    *(WP-4 PR'ı ile: manifest taşıyan kayıtlarda `status = "recorded"`; manifest yazmayan kayıt
    türlerinde `not_available` kalır.)*
  - Kayıtlar ayrı bir `model_version` ve `country_pack` taşımıyor → `null` +
    `MODEL_VERSION_NOT_RECORDED` / `COUNTRY_PACK_NOT_RECORDED`.
  - Sentetik girdi tespiti beyan edilen kaynak/sürüm adlarında `stub`/`synthetic`/`fixture`
    aramasıdır; yapılandırılmış bir stub kaydı yok. Kaçırma limiti azaltır, bu yüzden
    `production_eligible` ve model doğrulama kapısı ayrıca, release manifest'ten gösterilir.
  - Kanıt ve verify çağrıları organizasyonun zincirini her seferinde baştan doğrular
    (O(N)). MVP hacmi için kabul edilebilir; büyüyünce kontrol noktası gerekir.

---

## WP-4 · Her sonuçta kaynak manifesti

**Eksik.** Connector provenance'ı bayrak düzeyinde var (`data_mode`, `uses_connector_fallback`)
ama sonuç başına **sürüm / lisans / alınma zamanı / uzamsal sınır / payload hash** kaydı yok.
WP-3'ün manifest bloğu buna dayanıyor.

**Yapılacak.**
1. `app/schemas/source_manifest.py`: `SourceRecord(source_id, version, retrieved_at, licence_state, spatial_bounds, payload_hash, used_for, state)`; `state ∈ {live, fixture, synthetic, degraded, blocked}`.
2. Her connector çağrısı bir `SourceRecord` üretir (`app/connectors/gee.py`, `app/connectors/cds_oras5.py`, `app/geo/raster_access.py`, pack curve yükleyicileri).
3. Manifest `PipelineContext` üzerinden taşınır ve audit trail payload'ına yazılır.
4. `app/core/data_source_registry.py` ile lisans durumu eşleştirilir; `licence_verified=false` olan kaynak `blocked` olur ve sonuca giremez.

**Kabul.**
- Her beş katmanlı çalıştırma, kullanılan her kaynak için bir satır üretir — kullanılmayan ama bloke olanlar dahil.
- `blocked` bir kaynak hiçbir sayıya katkı vermez; bunu doğrulayan test var.
- `tests/test_source_manifest.py`: live/fixture/degraded/blocked dördü.

**Sınır.** Yeni veri kaynağı bağlamak bu pakette yok; sadece mevcutların kaydı.

**Uygulama notları (WP-4 PR'ı).**
- Lisans kontrolü hesaplamadan **önce** çalışır: çağıranın verdiği bir `SourceRecord` bloke ise ve
  bir kullanım beyan ediyorsa (`used_for` boş değil) çalıştırma `SOURCE_LICENCE_NOT_VERIFIED` ile
  reddedilir; sonradan yeniden etiketleme yapılmaz. Lisans durumu yalnızca lisans kaydından
  (`config/data_source_operational.json`) gelir; çağıranın `licence_state` veya `state="synthetic"`
  beyanı muafiyet sağlamaz.
- `data_versions` girdileri: sabit kendi damgalarımız ve `synthetic`/`stub` etiketli sürümler
  `synthetic` (eğri katalogları anahtarına göre değil etiketine göre); diğerleri (`elevation`, `era5_temperature`, NL pilotunun snapshot damgaları)
  `unclassified` + `SOURCES_UNCLASSIFIED`.
- **Bilinen boşluk (karar 2026-10-10):** `unclassified` damgalar lisans kontrolünden geçmez. NL
  pilotu (gerçek ERA5 + Copernicus DEM) lisans kaydı olmadan çalışmaya devam eder; bu, limitlerde
  `SOURCES_UNCLASSIFIED` olarak görünür. Kapatmak için: connector'lar gerçek alınma yolundan
  `SourceRecord` üretsin, lisanslar `LicenceRecord`'a girilsin, sonra bu damgalar da kapıya alınsın.
- Madde 2 (connector'ların kayıt üretmesi) bu PR'da yok: `RasterAccess`'in canlı alınma yolu yok,
  her erişimci fixture veya sabit varsayılan okuyor; `live` etiketi yanıltıcı olurdu (STUBS #31).

---

## WP-5 · Tek skorlama yolu

**Eksik — ürün bütünlüğü açısından en riskli nokta.** İki paralel skorlama yolu var:

- `/v1/risk/score` ve `/v1/risk/batch` — `app/scoring/risk_score.py:_raw_component_values`, SHA-256 seeded 0–100 bileşenler. **Bu yoldaki her sayı sentetik** (STUBS #3, severity `output-shaping`). README'nin dokümante ettiği varsayılan uç nokta bu.
- Beş katmanlı pipeline — gerçek sözleşme, etiketli sentetik eğrilerle.

README zaten "banka/sigorta demolarını `/v1/risk/score` üzerinden çalıştırma" diyor.
Ama kapı dokümantasyonda, kodda değil.

**Yapılacak.**
1. `/v1/risk/score` ve `/v1/risk/batch` yanıtlarına zorunlu `scoring_path: "synthetic-components-v0.1"` alanı ekle ve `production_eligible=false`'ı sabitle.
2. `APP_ENV=production` altında bu iki uç noktayı `410 Gone` ile kapat (`app/core/runtime_mode.py` desenini kullan), yerine beş katmanlı uç noktaya yönlendir.
3. `/v1/risk/score`'u OpenAPI'de `deprecated=True` işaretle; README ve `docs/api/` güncelle.
4. Tek varlık için beş katmanlı uç nokta: `POST /v1/assets/analyze` — `/v1/portfolio/analyze`'ın tek varlıklı hali, aynı sözleşme.
5. `frontend/src/api.ts` ve demo preset'lerini yeni uç noktaya taşı.

**Kabul.**
- `APP_ENV=production` + `/v1/risk/score` → `410`, gövdede yeni uç noktanın adı.
- Tek varlık analizi beş katmanlı sonuç ve `audit_id` döner.
- `tests/test_scoring_path_gate.py`; mevcut `tests/test_risk_batch_and_validation.py` yeni alanla güncellenir.

**Sınır.** Sentetik yolu **silmeyin** — dev/demo'da kalıyor, yalnızca prod'da kapanıyor ve etiketleniyor.

---

## WP-6 · Geocoding ve ingest triyajı

**Eksik.** Geocoding **implement edilmemiş** (STUBS #19). Adres-only satırlar nedenle
hariç tutuluyor. Banka teminat portföyleri tipik olarak adres taşır, koordinat taşımaz —
yani bugün gerçek bir müşteri dosyasının büyük kısmı analiz edilemiyor. MVP'nin giriş
kapısındaki en büyük tek engel bu.

**Yapılacak.**
1. `app/services/geocoder.py`: `Geocoder` protokolü + `CountryPackGeocoder` (pack başına sağlayıcı) + `NullGeocoder` (varsayılan, bugünkü davranış).
2. pack-tr için bir sağlayıcı bağla; sonuçlar cache'lenir (`geocode_cache` tablosu) ve her sonuç bir `SourceRecord` üretir (WP-4) — geocode de bir veri kaynağıdır.
3. Belirsiz sonuçlar: tek en iyi eşleşmeyi **seçme**; `excluded` içinde `ambiguous` nedeni ve aday listesiyle döndür.
4. Ingest yanıt sözleşmesini genişlet: her hariç tutulan satır için `row`, `asset_id`, `reason` (enum), `offending_value`, `fixable: bool`.
5. Kolon eşleştirme onayı: `POST /v1/portfolio/upload` bir `mapping_proposal` döner; `POST /v1/portfolio/analyze` onaylanmış eşleştirmeyi `mapping` parametresiyle alır. Alias tahmini (`_COLUMN_ALIASES`) öneri olur, sessiz karar olmaz.

**Kabul.**
- Yalnızca adres taşıyan bir CSV analiz edilir; geocode edilemeyenler nedenle listelenir.
- `reason` bir enum — serbest metin değil; frontend filtreleri buna bağlanır.
- Hiçbir satır sessizce düşmez: `analyzed + excluded == total_rows` invariantı test edilir.
- `tests/test_geocoding.py`, `tests/test_portfolio_upload.py` genişletilir.

**Sınır.** Üçüncü taraf sağlayıcı sözleşmesi/lisansı yoksa `NullGeocoder` varsayılan kalır
ve kapı `licence_verified` üzerinden kapanır — sağlayıcı olmadan prod'a açılmaz.

---

## WP-7 · Horizon yoğunluk haritaları (2030/2050)

**Eksik.** İleriye dönük çıktılar **kapalı**: `app/loss/expected_loss.py`
`HORIZON_UNAVAILABLE_METHOD = "not_available_without_climate_scenario_data"`.
Sürümlenmiş CMIP6/CORDEX yoğunluk haritası verilmedikçe 2030/2050 kaybı **hiç emit edilmiyor**
(STUBS #16b — eski `×0.95 / ×1.05` uydurması bilinçli olarak kaldırılmış, doğru karar).

Sonuç: bugün "2050'de kayıp" gösteren bir demo boş döner. Tasarım ekranları bu alanları
içerdiği için bu, MVP'de kapatılması gereken bir sözleşme açığı.

**Yapılacak.**
1. `app/climate/horizon_maps.py`: sürümlenmiş horizon yoğunluk haritası şeması
   (`source_id`, `scenario` (SSP), `horizon` (2030/2050), `hazard_id`, `grid`, `version`, `licence_state`).
2. Pack-local veya çağrıcı tarafından sağlanan harita yükleme yolu; `ExpectedLossFinancialTranslation` bunu alır.
3. Harita yoksa davranış **aynen korunur** — horizon yok, `not_available_without_climate_scenario_data` damgası durur.
4. pack-tr ve pack-nl için en az bir senaryo × bir horizon × flood için gerçek harita bağla.

**Kabul.**
- Harita verildiğinde `scenario_deltas` dolu döner ve her delta kaynağını manifestte taşır.
- Harita verilmediğinde bugünkü davranış bit-bit aynı (regresyon testi).
- Horizon çıktısı asla mevcut yoğunluktan ölçeklenerek türetilmez — bunu yasaklayan test var.
- `tests/loss/test_horizon_maps.py`.

**Sınır.** Kendi downscaling'inizi yapmayın. Bu paket yalnızca **tüketim** yolu;
üretim Phase B (STUBS #11, #12).

---

## WP-8 · Asenkron batch

**Eksik.** `/v1/risk/batch` senkron (`app/api/risk.py`); `GET /v1/risk/batch/status/{task_id}`
var ama MVP hedefi 50–500 varlık ve beş katmanlı yol varlık başına çok daha pahalı.
500 varlıklı bir çalıştırma HTTP timeout'una girer.

**Yapılacak.**
1. `app/workers/` altında bir job runner (mevcut dizin boşsa en basit: DB-backed kuyruk, ayrı process gerekmeden `BackgroundTasks` + `runs` tablosu durum alanı).
2. `POST /v1/portfolio/analyze` → `202 Accepted` + `run_id`; `GET /v1/runs/{run_id}` → `queued | running | partial | complete | failed` + ilerleme (`analyzed/total`).
3. Idempotency: aynı `Idempotency-Key` ile ikinci çağrı yeni çalıştırma yaratmaz, mevcut `run_id`'yi döndürür.
4. Kısmi başarı birinci sınıf durum: `partial` → sonuç var, kapsamı dar.

**Kabul.**
- 500 varlıklı portföy timeout'suz tamamlanır.
- `partial` durumu `failed`'dan ayrı; kısmi sonuç okunabilir.
- `tests/test_async_batch_production.py` genişletilir (dosya zaten var).

**Sınır.** Redis/Celery getirmeyin; mevcut bağımlılık setiyle çözülebiliyorsa onunla çözün.

---

## WP-9 · Konsol (frontend)

**Eksik.** `frontend/` bugün: `PortfolioDemoPage` (beş adımlı anlatı), `RiskSnapshot`
bileşenleri, `RiskTilesPage`, `RiskMap`. Yok olanlar: kimlik ekranları, kanıt görüntüleyici,
upload triyaj arayüzü, varlık drill-down'ı, ortak token seti (sayfa başına ayrı CSS:
`App.css`, `portfolio-demo.css`, `pages/risk-tiles.css`, `pages/RiskSnapshot.css`), i18n.
Ayrıca `frontend/src/App.tsx` (33 KB) **hiçbir yerde mount edilmiyor** — landing markup'ı
`index.html` içinde; bu dosya ölü, üzerine inşa edilmemeli.

Tasarım kararları ve ekran spesifikasyonu hazır:
[`docs/03-frontend/MVP_P0_DESIGN_REQUIREMENTS.md`](../03-frontend/MVP_P0_DESIGN_REQUIREMENTS.md).
Chip sözlüğü, token seti, ekran yerleşimleri ve iki mobil görünüm orada tanımlı.

**Yapılacak — tasarım dokümanındaki sıraya göre.**
1. Token seti (P0-5) → `frontend/src/tokens.css`, dört sayfa CSS'i buna taşınır.
2. Trust chip bileşeni (P0-1) → dokuz durum, iki eksen, iki yuva.
3. Upload + triyaj ekranı (P0-3) → WP-6 sözleşmesine bağlanır.
4. Varlık drill-down (P0-4) → mevcut `components/snapshot/*` yeniden kullanılır.
5. Kanıt görüntüleyici (P0-2) → WP-3 uç noktalarına bağlanır.
6. Rota: `/console` → `src/spaShell.ts:2` `APP_ROUTE_RE`'ye ekle, `src/main.tsx`'e route, `vercel.json`'a rewrite.

**Kabul.**
- `npx tsc -b` ve `npx eslint .` yeşil.
- Kapsam rakamı tıklanabilir ve hariç tutulanları nedenleriyle listeliyor.
- `production_eligible=false` bandı kapatılamaz ve yazdırma/PDF çıktısında da görünür.
- Claim-control testi: frontend metinleri chip sözlüğüne karşı doğrulanır (Roadmap Stage 4).

**Sınır.** `App.tsx` üzerine inşa etmeyin. Native mobil uygulama yok — mobil görünümler
responsive web.

---

## WP-10 · Release ve ops kapısı

**Eksik.** `/health` DB yoksa `db: "skipped"` (`app/main.py:117-126`). Backup/restore
provası, incident runbook'u, rollback kaydı yok. Roadmap Stage 3 `platform_operational=true`
için bunları şart koşuyor.

**Yapılacak.**
1. `/v1/health/ready` ayrı uç nokta: DB bağlantısı, audit zinciri tip hash'i, pack yükleme, connector config durumu.
2. Restore provası: `scripts/restore_drill.sh` + sonucunu `release-manifest` çıktısına bağla.
3. `docs/ops/` altına incident response, rollback, evidence retention runbook'ları.
4. `GET /v1/release-manifest` (zaten var) `platform_operational` bayrağını gerçek kontrollere bağlasın.

**Kabul.** `platform_operational=true` yalnızca dört kontrol de geçtiğinde döner.

---

## Bağımlılık grafiği

```
WP-0 ──┬─> WP-1 ──┬─> WP-2 ──> WP-3 ──> WP-9 (adım 5)
       │          └─> WP-8
       ├─> WP-4 ──────────────> WP-3
       ├─> WP-5
       ├─> WP-6 ──────────────> WP-9 (adım 3)
       ├─> WP-7
       └─> WP-9 (adım 1-2, tasarım dokümanından, backend beklemez)
                                          WP-10 en son
```

Paralelleştirilebilir: WP-4, WP-5, WP-6, WP-7 birbirinden bağımsız.
Kritik yol: **WP-1 → WP-2 → WP-3**. Pilot satışını açan budur.

Phase B:

```
WP-11 ──┬─> WP-12a ──> WP-12b (yöntem kararına bağlı)
        └─> WP-13b (lisanslı kayıp verisi geldiğinde)

WP-13a  bağımsız — kamuya açık olay verisi, kendi kapısı
WP-14   WP-1 + WP-3 bitince
WP-15   WP-5 ile aynı turda (rapor sentetik yoldan taşınmalı)
```

WP-15'in ilk adımı MVP'ye sarkıyor: raporu beş katmanlı yola taşımak WP-5 ile aynı
PR'da yapılmalı, yoksa prod'da kapatılan sentetik yol rapor üzerinden açık kalır.

---

## Her WP için geçerli kurallar

1. **Dal.** Her WP kendi dalında; `claude/wp-<n>-<slug>`.
2. **Stub beyanı.** Yeni bir stub/fallback eklenirse [`STUBS.md`](../../STUBS.md)'ye severity'li satır eklenir. Beyansız stub review fail'i (`.cursor/rules/ci-stubs-honesty.mdc`).
3. **Dürüstlük kapısı.** Hiçbir WP `production_eligible` veya `model_validated_for_use_case` bayrağını `true`'ya çevirmez. Bunlar Stage 5 ampirik doğrulamasına bağlı.
4. **Testler.** Her WP'nin kabul kriterleri test olarak yazılır; `PYTHONPATH=. pytest` yeşil kalır.
5. **Sözleşme değişikliği.** Public yanıt şeması değişirse `docs/api/` ve README aynı PR'da güncellenir.
6. **Sentetik sayı sunumu.** `output-shaping` stub'ları regüle alıcıya üretim riski gibi gösterilmez — WP-5'in tüm gerekçesi bu.

---

## Ajana verilecek komut

Üç komut: tam seri, tek paket, kaldığı yerden devam. Hepsi aynı dosyayı
(`docs/00-master/MVP_IMPLEMENTATION_PLAN.md`) kaynak kabul eder, o yüzden
içeriğini komuta kopyalamaya gerek yok.

### A · Tam seri (WP-0 → WP-10)

```text
Bu repoda `docs/00-master/MVP_IMPLEMENTATION_PLAN.md` dosyasını oku. On iş paketi (WP-0 … WP-10)
tanımlı. Hepsini, dosyadaki bağımlılık sırasına göre, baştan sona uygula.

ÇALIŞMA BİÇİMİ
- Önce `AGENTS.md`'yi oku; dev ortamı, test komutu ve gotcha'lar orada.
- Her WP'ye başlamadan önce o paketin dokunacağı dosyaları gerçekten oku. Plandaki dosya
  referansları doğrulandı ama kod değişmiş olabilir; plan ile kod çelişirse kodu doğru kabul et
  ve çelişkiyi raporla.
- WP-0'ı atlama. Baseline kurulmadan hiçbir ürün kodu değiştirilmez.
- Her WP için sırayla: (1) kabul kriterlerini test olarak yaz, (2) testlerin kırmızı olduğunu gör,
  (3) implement et, (4) testleri yeşile al, (5) tüm suite'i çalıştır, (6) kendi diff'ini
  düşmanca oku — CI'ın bunu neden reddedeceğini ara ve bulduğunu düzelt, (7) commit + push.
- Test komutu: `PYTHONPATH=. pytest --deselect tests/test_live_connector_credentials.py::test_oras5_cdsapi_client_accepts_bare_uuid_key`
  Bu deselect zorunlu — o test ağ kısıtlı makinede canlı bağlantı açıp takılıyor.
- Frontend'e dokunan pakette ayrıca: `cd frontend && npx tsc -b && npx eslint .`
- Dal: her WP kendi dalında, `claude/wp-<n>-<slug>`. Her WP sonunda push et.
  Pull request AÇMA — ben isteyeceğim.
- Zaman veya tur sınırını düşünme. Derin çalış: tahmin etmek yerine oku, varsaymak yerine
  çalıştır, "muhtemelen geçer" yerine testi gör.

TAVİZ VERİLMEYEN KURALLAR
- `production_eligible` ve `model_validated_for_use_case` bayraklarını ASLA `true` yapma.
  Bunlar Stage 5 ampirik doğrulamasına bağlı ve bu planın hiçbir paketi onu kapsamıyor.
- Yeni bir stub, fallback, mock veya sentetik değer eklersen `STUBS.md`'ye severity'li bir satır
  ekle. Beyansız stub review fail'i.
- Bir sayıyı başka bir sayıdan ölçeklendirerek uydurma. Özellikle horizon çıktıları:
  mevcut yoğunluktan 2030/2050 türetmek yasak (STUBS #16b bunu bilinçli olarak kaldırmış).
- Testi geçirmek için testi devre dışı bırakma, skip etme veya zayıflatma.
- Kapsamı genişletme. Her WP'nin "Sınır" maddesi bağlayıcı.
- Çalıştırmadığın bir şeyin geçtiğini söyleme.

KARAR GEREKTİREN NOKTALAR — UYDURMA, SOR
Bunlara geldiğinde o paketi durdur, geri kalanına devam et, ve sonunda bana sor:
1. WP-6 geocoder sağlayıcısı: hangi servis, hangi lisans? Sağlayıcı kararı yoksa
   `NullGeocoder` varsayılan kalır ve paketin geri kalanı (triyaj sözleşmesi, kolon onayı)
   yine yapılır.
2. WP-2 Postgres: hangi host? Karar yoksa aiosqlite ile geliştir, migration'ları
   Postgres uyumlu yaz, deploy'u bırak.
3. Chip sözlüğündeki iki açık durum: `blocked` ve `not-validated` nereye oturuyor?
   (`docs/03-frontend/MVP_P0_DESIGN_REQUIREMENTS.md` P0-1 bölümü, "Açık kalan iki soru".)
   WP-9'da bu ikisi geçici adlarla render edilebilir ama claim-control testi yazılmaz.
4. WP-12b portföy korelasyon yöntemi: copula mı, uzamsal korelasyon uzunluğu mu,
   olay bazlı set mi? Karar yoksa WP-12b açılmaz — korelasyon iddiası etmeden
   varlık toplamı olarak kalır.
5. WP-13a için adlandırılacak olay: hangi sel olayı, hangi veri kesim tarihi?
   Ön kayıt donmadan footprint çalıştırması yapılmaz.

RAPORLAMA
Her WP bittiğinde kısa bir rapor yaz: ne değişti, hangi testler eklendi, suite durumu
(geçen/düşen sayısı), ve varsa planın yanlış çıktığı yer. Tüm seri bittiğinde
`docs/00-master/MVP_IMPLEMENTATION_LOG.md` olarak paket paket özet bırak.
```

### B · Tek paket

```text
Bu repoda `docs/00-master/MVP_IMPLEMENTATION_PLAN.md` dosyasını oku ve yalnızca <WP-3> paketini
uygula. Diğer paketlere dokunma.

Çalışma biçimi, test komutu, taviz verilmeyen kurallar ve raporlama için aynı dosyanın
"Ajana verilecek komut → A · Tam seri" bölümündeki maddelere uy. O paketin "Sınır" maddesi
bağlayıcı; kapsamı genişletme.

Dal: `claude/wp-3-<slug>`. Bitirince push et, pull request açma.
```

`<WP-3>` yerine istediğin paketi yaz. Bağımsız verilebilenler: **WP-4, WP-5, WP-6, WP-7**
(birbirini beklemezler). WP-2 → WP-3 ve WP-1 → WP-2 sırası zorunlu.

Phase B paketleri de aynı blokla verilir, ek iki şartla: **WP-12 ve WP-13, WP-11
bitmeden açılmaz** (gerçek horizon verisi olmadan ikisi de tohumlanmış sayıyı başka bir
tohumlanmış sayıyla değiştirir), ve **WP-14, WP-1 ile WP-3 bitmeden açılmaz**.
WP-13a bunun istisnası — kamuya açık olay verisiyle çalışır, kendi kapısı var, bağımsız
verilebilir. WP-15'in ilk adımı (raporu beş katmanlı yola taşımak) WP-5 ile aynı PR'da olur.

### C · Kaldığı yerden devam

```text
Bu repoda `docs/00-master/MVP_IMPLEMENTATION_PLAN.md` ve varsa
`docs/00-master/MVP_IMPLEMENTATION_LOG.md` dosyalarını oku. Hangi paketlerin bittiğini
log'dan ve git geçmişinden (`claude/wp-*` dalları) tespit et, bitmeyen ilk paketten devam et.

Bir paketin bittiğini varsayma — kabul kriterlerini gerçekten doğrula: ilgili testleri
çalıştır, uç noktaları çağır. Yarım kalmış bir paket bulursan tamamla, baştan yazma.

Diğer her şeyde "Ajana verilecek komut → A · Tam seri" bölümüne uy.
```

### Komutu neden bu kadar kısıtlı yazıyoruz

Kota sınırı olmayan bir ajanın tipik üç hatası: kapsamı genişletmek, testi geçirmek için
testi zayıflatmak, ve karar gerektiren bir noktada sormak yerine makul görünen bir şey
uydurmak. Yukarıdaki üç blok bu üçünü de adıyla yasaklıyor. Sınırsız bütçe derinlik için
harcanır — okumak, çalıştırmak, kendi diff'ini düşmanca gözden geçirmek — kapsam için değil.

---

# Phase B paketleri

MVP paketleri (WP-0…WP-10) kapandıktan sonra gelen, önceden "kapsam dışı" sayılan işler.
Beşi aynı türden değil: ikisi birbirine zincirli, biri zaten büyük ölçüde yazılmış ve
yalnızca dış girdi bekliyor, biri sıralama meselesi.

## WP-11 · Horizon veri hattı (CMIP6 / CORDEX tüketimi)

**Çerçeve düzeltmesi — en önemli madde.** Kendi downscaling'inizi **üretmeyin**.
Downscale edilmiş ürünler zaten yayımlanmış ve lisanslı olarak erişilebilir:
EURO-CORDEX / CORDEX-CORE (Copernicus CDS üzerinden), NEX-GDDP-CMIP6, ISIMIP3b.
Yapılacak iş bunları **tüketmek**; bir iklim modeli çalıştırmak değil.

Bu, ürünün kurum içinde yapabileceği bir iş. Kendi downscaling'i üretmek değil.

**Mevcut durum.** `app/climate/` boş (`__init__.py` dışında) — hazır boş bir ev.
CDS tarafındaki tesisat zaten var: `copernicus_cds_api_key`, Zarr açma yolu,
obstore destekli retry store, fsspec fallback (`app/connectors/cds_oras5.py`).
Yani veri çekme deseni kopyalanabilir, sıfırdan yazılmaz.

**Yapılacak.**
1. `app/climate/horizon_maps.py` — WP-7'nin tanımladığı sürümlenmiş harita şeması.
2. `app/climate/sources/cordex.py` — CDS'ten CORDEX regional projection okuma; ORAS5 connector'ının Zarr/retry desenini kullan.
3. `app/climate/regrid.py` — model gridinden varlık noktasına indirgeme. Yöntem **beyan edilir ve sürümlenir** (`regrid_method`, `regrid_version`); bilinear mi nearest mi conservative mi, hepsinin kaydı kalır.
4. `app/climate/bias_correction.py` — uygulanan düzeltme (quantile mapping, delta change, veya hiçbiri) beyan edilir ve sürümlenir. **Beyansız düzeltme yasak.**
5. Her harita bir `SourceRecord` üretir (WP-4): `source_id`, `scenario`, `horizon`, `version`, `licence_state`, `spatial_bounds`, `payload_hash`.
6. Lisans kapısı: `licence_verified=false` olan bir iklim kaynağı `blocked` olur ve hiçbir horizon çıktısına giremez.

**Kabul.**
- pack-tr ve pack-nl için en az bir senaryo (SSP2-4.5) × iki horizon (2030, 2050) × flood gerçek veriyle besleniyor.
- `scenario_deltas` dolu dönüyor ve her delta kaynağını, regrid ve bias-correction sürümünü manifestte taşıyor.
- Harita yoksa WP-7'nin davranışı bit-bit korunuyor (`not_available_without_climate_scenario_data`).
- Horizon çıktısı mevcut yoğunluktan ölçeklenerek **asla** türetilmiyor — bunu yasaklayan test duruyor.
- `tests/climate/test_cordex_ingestion.py`, `tests/climate/test_regrid.py`, `tests/climate/test_bias_correction.py`.

**Sınır.** İklim modeli koşmak, kendi downscaling'inizi üretmek, yeni bir bias-correction
yöntemi icat etmek — üçü de kapsam dışı. Yayımlanmış ürünü, beyan edilmiş yöntemle tüketmek.

---

## WP-12 · Scenario-Lab: tohumlanmış sezgiden gerçek modele

**Mevcut durum.** `app/services/scenario_lab_service.py` — `_seed()` ile SHA-256
tohumlanmış severity, affected, correlated shocks ve systemic score.
Disclaimer "v1 Deterministic Engine" (STUBS #11, #12, severity `output-shaping`).

**WP-11'e zincirli.** Gerçek horizon yoğunluk haritası olmadan Scenario-Lab'ı
"gerçek model" yapmanın yolu yok — tohumlanmış sayıyı başka bir tohumlanmış sayıyla
değiştirmiş olursunuz. Bu yüzden WP-11 bitmeden başlanmaz.

İki parçaya ayrılıyor, çünkü biri veri işi, diğeri modelleme işi:

### WP-12a · Varlık bazlı senaryo deltaları (WP-11 bitince yapılabilir)
`_seed`-güdümlü severity ve affected sayılarını, gerçek horizon haritalarından beş katmanlı
pipeline üzerinden hesaplanan deltalarla değiştir. Bu bir **yeniden kablolama** işi,
yeni bilim değil: pipeline sözleşmesi (`app/pipeline/contract.py`) ve
`ExpectedLossFinancialTranslation` zaten duruyor.

**Kabul.** Senaryo çıktısındaki her sayı beş katmanlı pipeline'dan türetilir;
`_seed` çağrısı Scenario-Lab'da kalmaz; disclaimer "v1 Deterministic Engine"dan
beyan edilmiş methodology sürümüne döner.

### WP-12b · Portföy korelasyonu ve sistemik yayılım (ayrı karar)
`_correlated_shocks` ve `_impact_propagation` WP-11 ile **çözülmüyor**. Bunlar varlıklar
arası korelasyon ve portföy agregasyonu soruları — beyan edilmiş bir yöntem gerektirir
(copula mı, uzamsal korelasyon uzunluğu mu, olay bazlı set mi).

**Sınır.** Yöntem seçilip yazılı olarak beyan edilmeden kod yazılmaz. Bu paket bir
yöntem dokümanıyla başlar, implementasyonla değil. Yöntem kararı verilmemişse WP-12b
açılmaz ve Scenario-Lab portföy çıktısı WP-12a'dan sonra da varlık toplamı olarak kalır —
korelasyon iddiası etmeden.

---

## WP-13 · Stage 5 ampirik doğrulama (gerçek olay back-test'i)

**Beklenmedik iyi haber: harness zaten yazılmış.** `app/validation/gate1/` içinde:

| Dosya | Ne yapıyor |
|---|---|
| `harness.py` | `run_comparison`, `Predictor` protokolü, **`LookaheadError`** — ileriye bakma yanlılığını kodda engelliyor |
| `pre_registration.py` | `PreRegistration`, `require_frozen()`, **`PreRegistrationNotFrozen`** — donmamış ön kayıtla çalıştırmayı reddediyor |
| `observed_loss.py` | `ObservedLossProvider` protokolü, `is_licensed_for_commercial_use()` kapısı, ve varsayılan olarak **reddeden** `UnlicensedObservedLossProvider` |
| `baselines.py` | `zero_loss`, `prior_mean`, `value_fraction` — naive karşılaştırmalar |
| `metrics.py` | `mae`, `rmse` |
| `model_adapter.py` | hazard tipi eşlemesi |
| `report.py` | sonuç raporu |

Protokol ve bağımsız gözden geçirme brief'i de yazılmış:
`docs/validation/DATA_CENTRE_EVENT_BACKTEST_PROTOCOL.md`,
`docs/validation/DATA_CENTRE_EXTERNAL_REVIEW_BRIEF.md` — data-centre dikeyi için,
ama RE/teminat dikeyine şablon olarak uyarlanabilir.

**Yani bu madde mühendislik işine bağlı değil.** Tam iki dış girdi bekliyor:

1. **Lisanslı gözlenmiş kayıp veri seti.** `is_licensed_for_commercial_use()` `True`
   dönen bir `ObservedLossProvider`. Sigorta kayıp verisi pahalı ve sözleşmeyle kısıtlı;
   bunu kod üretemez.
2. **Bağımsız gözden geçiren.** Sonuçlar görülmeden **önce** atanmış olması gerekiyor.
   Sonradan atanan bir gözden geçiren, gözden geçirme değildir.

**Ve bir sıralama şartı:** WP-11'den önce koşulmaz. Sentetik eğrileri back-test etmek
hiçbir şeyi doğrulamaz — daha kötüsü, doğrulanmış gibi görünen bir sayı üretir.

Lisanslı kayıp verisi henüz yok. Karar: **kamuya açık olay verisiyle başlanacak** —
ama bu farklı bir kapı, aynı kapının zayıf hali değil.

### WP-13a · Hazard footprint doğrulaması (kamuya açık olay verisi)

**Ne doğrular, ne doğrulamaz.** EM-DAT, Copernicus EMS, Dartmouth Flood Observatory gibi
kamuya açık kayıtlar **olay düzeyinde etki** verir, varlık düzeyinde parasal kayıp vermez.
Yani hazard yoğunluk haritasının gerçek bir olayın ayak izine oturup oturmadığını
doğrulayabilir; EAL'i doğrulayamaz.

Bu ayrımı korumak için **ayrı bir kapı** açılır. `app/schemas/release_manifest.py`
`ReleaseGateStates` docstring'i zaten "no gate implies another gate" diyor; desen hazır.

1. `ReleaseGateStates`'e `hazard_footprint_validated: bool = False` ekle.
2. **`all_gates_pass` tuple'ına EKLEME.** Üretim kapısını sertleştirmek bu paketin işi değil.
3. Yerine bir validator: `model_validated_for_use_case` yalnızca
   `hazard_footprint_validated` doğruysa `True` olabilir. Yani footprint doğrulaması
   kayıp doğrulamasının **önkoşulu** olur — yerine geçeni değil.
4. `app/validation/gate2/` altında footprint harness'ı: gözlenen olay ayak izi vs. modelin
   hazard yoğunluğu; metrikler kayıp metrikleri değil (hit rate, false alarm ratio,
   critical success index gibi kategorik skorlar).
5. Mevcut `gate1` dokunulmaz — o kayıp back-test'i, bu değil. İki harness ayrı kalır.
6. Ön kayıt mekaniği yeniden kullanılır: `pre_registration.py` ve `LookaheadError` aynı
   disiplini footprint çalıştırmasına da uygular.

**Kabul.**
- En az bir adlandırılmış sel olayı için footprint karşılaştırması koşuyor ve raporu üretiyor.
- `hazard_footprint_validated` bu çalıştırmayla `True` olabiliyor.
- `model_validated_for_use_case` **değişmiyor** — ve onu `hazard_footprint_validated`
  olmadan `True` yapmaya çalışan bir manifest validator tarafından reddediliyor.
- Hiçbir API yanıtı, rapor veya UI metni footprint doğrulamasını kayıp doğrulaması gibi
  sunamıyor; bunu kontrol eden claim-control testi var.
- `tests/validation/test_gate2_footprint.py`, `tests/test_release_manifest.py` genişletilir.

**Sınır.** Kamuya açık olay verisinden parasal kayıp türetmeyin. "Temsili kayıp oranı"
uydurmak bu paketin tek yasak işi — o anda WP-13b'yi sahte veriyle koşmuş olursunuz.

### WP-13b · EAL back-test'i (lisanslı kayıp verisi geldiğinde)

Veri seti gelmeden yapılabilecekler:
1. RE/teminat dikeyi için back-test protokolünü yaz (`docs/validation/DATA_CENTRE_EVENT_BACKTEST_PROTOCOL.md` şablon): adlandırılmış olay, donmuş veri kesim tarihi, örneklem çerçevesi, dışlama kuralları, metrikler, naive/incumbent baseline.
2. Ön kayıt dokümanını hazırla ve **donmadan** bırak — `require_frozen()` zaten korumalı.
3. Gözden geçiren brief'ini RE dikeyine uyarla (`DATA_CENTRE_EXTERNAL_REVIEW_BRIEF.md` şablon).
4. `ObservedLossProvider` adaptör iskeleti; `is_licensed_for_commercial_use()` `False`
   döner, dolayısıyla harness reddetmeye devam eder.
5. CI'da kapıyı kapalı tutan testi koru: lisanssız provider ile çalıştırma
   `ObservedLossDataUnavailable` ile düşer.

**Kabul.** Protokol ve ön kayıt yazılı; harness lisanssız veriyle hâlâ reddediyor;
`model_validated_for_use_case` **hâlâ `false`**. Bu paket o bayrağı çevirmez —
onu ancak donmuş ön kayıtla koşulmuş, bağımsız gözden geçirilmiş bir çalıştırma çevirir.

**Sınır.** Veri seti yoksa sahte veya "temsili" kayıp verisiyle back-test koşulmaz.
Kendi sonucunuzu kendiniz gözden geçirmezsiniz.

---

## WP-14 · Mobil (PWA, sonra gerekirse native)

**Sıralama şartı.** WP-1 (kimlik) ve WP-3 (kanıt API'si) bitmeden başlanmaz.
Kimliği ve geri çağrılabilir kanıtı olmayan bir mobil uygulama, fazladan adımı olan bir
mockup'tır.

Tasarım hazır: `docs/03-frontend/MVP_P0_DESIGN_REQUIREMENTS.md` ve `.design/`
altındaki iki mobil artboard (390×844) — salt-okunur varlık snapshot'ı ve saha triyajı.

### WP-14a · PWA
1. Mevcut React uygulamasına service worker; offline kabuk.
2. Saha triyajı için offline kuyruk: düzeltme cihazda saklanır, bağlantı gelince senkronlanır (WP-6'nın triyaj sözleşmesine yazar).
3. Kamera ve konum web API'leriyle — native gerekmiyor.
4. Önbelleğe alınan hiçbir sonuç `audit_id` + `model_version` olmadan gösterilmez; bayat kayıt `STALE` chip'i ve yaş ekiyle işaretlenir.

**Kabul.** Gerçek cihazda saha triyajı uçtan uca çalışır; uçak modunda kuyruğa alır,
bağlantı gelince senkronlar; `production_eligible=false` bandı mobilde kapatılamaz ve
scroll'da kaybolmaz.

### WP-14b · Native (yalnızca şu iki şart doğarsa)
Offline kanıt paketi ve arka plan senkronu gerçekten şart olursa: Expo / React Native,
tek kod tabanı, mevcut `frontend/src/api.ts` tipleri paylaşılır. İki ayrı native kod
tabanı (Swift + Kotlin) bu ürünün ölçeğinde savunulamaz.

**Sınır.** `production_eligible=false` iken App Store / Play Store listelemesi yapılmaz.
Mağaza açıklaması, ürünün kendi içinde reddettiği bir iddiayı dışarıya yazmak olur.
Ve geliştirici hesabına tasarım dosyası eklenmez — mağazaya **build** gider.

---

## WP-15 · TSRS / CSRD fiziksel risk açıklama desteği

**Kapsam içi ve kısmen zaten yazılmış.** Mevcut:
`app/regulation/esrs_mapping.py`, `esrs_registry.py`, `rules.py`, `verify.py`,
`registry.py` (lifecycle geçişleri), `app/reports/tcfd.py`.
Pazarlama sitesi bunu zaten satıyor: `/services/tsrs-compliance`,
`frontend/public/sustainability-reporting-standards-turkey-tsrs/`.

**Ve bugün duran bir bütünlük sorunu var — bu paketin ilk işi.**
`app/reports/tcfd.py:37` `build_tcfd_report` raporu `RiskScoreResponse` üzerinden üretiyor,
yani STUBS #3'teki **sentetik** skor yolundan. Açıklama şeklinde bir rapor, SHA-256
tohumlanmış sayılardan üretiliyor. WP-5 sentetik yolu prod'da kapatsa bile, bu rapor
üzerinden yol açık kalır.

**Yapılacak.**
1. **Raporu beş katmanlı yola taşı.** `build_tcfd_report` girdisini `RiskScoreResponse`'tan
   `FiveLayerPipelineResult`'a çevir. WP-5 ile aynı turda yapılmalı, yoksa kapatılan yol
   rapordan sızar.
2. **TSRS 2 fiziksel risk şablonu.** Bugün yalnızca TCFD var. TSRS'in fiziksel risk
   datapoint'leri için ayrı şablon; ESRS E1 fiziksel risk datapoint'leriyle eşleme
   `esrs_mapping.py` üzerinden.
3. **Açıklama kanıt paketi.** Her datapoint için: hangi sayı, hangi `audit_id`, hangi
   methodology sürümü, hangi chip durumu. WP-3'ün kanıt API'sine bağlanır — rapordaki
   her sayı tıklanıp kaynağına gidilebilir olmalı.
4. **Reg mapping = kanıt işaretçisi, uyum kararı değil.** Roadmap Stage 4 çıkış kriteri
   bunu şart koşuyor. Yapısal koruma: rapor şeması `compliant: bool` benzeri bir alan
   **taşımaz**; yalnızca `references: [{standard, paragraph, url}]` taşır.
5. **Registry uzlaştırması (GEO-197) önce.** Yeni enstrüman eklemeden (GEO-198) önce
   mevcut regülasyon registry'si uzlaştırılır — roadmap sıralaması bu.
6. Scope: `reports:write`; rapor üretimi kanıt kaydı bırakır (audit trail'e yazar).

**Kabul.**
- Hiçbir rapor, `audit_id` ve kaynak durumu (chip) olmadan bir sayı render etmiyor.
- Rapor şemasında uyum iddiası taşıyan bir alan yok; her regülasyon referansı işaretçi.
- `tests/regulation/test_disclosure_claims.py`: üretilen rapor metninde "complies",
  "uyumludur", "meets the requirement" türü iddia aranır ve bulunursa test düşer.
- Sentetik skor yolundan rapor üretmek artık mümkün değil (`tests/test_report_engine_script.py`
  genişletilir).
- `production_eligible=false` damgası raporun her sayfasında.

**Sınır.** Emisyon muhasebesi yok. Güvence (assurance) görüşü yok — rapor, müşterinin
açıklamasına **girdi**, açıklamanın kendisi değil. Bu ayrım rapor metninde açıkça yazılı olur.

---

## Kapsam dışı — kalanlar

Phase B paketleri açıldıktan sonra bilinçli olarak dışarıda kalanlar:

- **Kendi downscaling'ini üretmek.** WP-11 yayımlanmış ürünü tüketir; iklim modeli koşmaz.
- **Yeni bias-correction yöntemi icat etmek.** Beyan edilmiş, literatürde tanımlı yöntem kullanılır.
- **Portföy korelasyon modeli** — WP-12b bir yöntem kararına bağlı; karar yoksa açılmaz.
- **Kendi sonucunu kendi gözden geçirmek.** WP-13'ün bağımsız gözden geçireni dışarıdan gelir.
- **Emisyon muhasebesi / karbon hesaplayıcı.** README'nin "is not" tablosu ve
  `GEORISK_ENGINE_REPOSITIONING.md` bunu açıkça dışlıyor. Bu bir kapsam genişlemesi değil,
  **konumlandırma değişikliğidir** — ayrı bir karar olarak ele alınmalı.
  (Ayrımı için aşağıdaki nota bakın.)

### Not: ESG raporlamanın iki okuması

Karar verildi — **TSRS / CSRD fiziksel risk açıklama desteği** kapsama alındı (WP-15).
Emisyon muhasebesi dışarıda kalıyor: README'nin "is not" tablosu ve
`GEORISK_ENGINE_REPOSITIONING.md` bunu açıkça dışlıyor, ve onu eklemek bir kapsam
genişlemesi değil konumlandırma değişikliği olur — ayrı bir karar olarak ele alınmalı.
