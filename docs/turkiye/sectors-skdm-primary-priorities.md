# Birincil öncelikli sektörler (SKDM kapsamı)

Bu not, **yüksek enerji yoğunluğu** ve **doğrudan / dolaylı emisyon** profili nedeniyle yeşil standart ve denetim baskısının güçlü olduğu sektörleri **ürün ve metodoloji önceliği** olarak listeler. **SKDM** ifadesi burada **iç önceliklendirme etiketi** olarak kullanılır (belirli bir resmi kamu sınıflandırması adı iddia edilmez; kurum içi matris adınızla özelleştirilebilir).

**Feragat:** Aşağıdaki korelasyon ve “ideal aday” ifadeleri **hipotetik çerçevedir**; tesis bazında kaynak ayırımı, düzenleyici uygunluk veya **resmi beyanı tek başına çürütme / ispatlama** garantisi verilmez. Avrupa alıcılarına sunulacak materyal **objektif uydu türevli çapraz kanıt** olarak konumlanmalı; **kesin hukuki delil** dili kullanılmamalıdır.

---

## 1. Yüksek enerji ve bacalı süreçler

### 1.1 Demir ve çelik

- **Profil:** Yüksek kömür / enerji kullanımı ve bacalı süreçler; NO₂ ve CO ile üretim yoğunluğu arasında **literatürde ve saha çalışmalarında** çeşitli korelasyon örnekleri bulunur (meteoroloji ve bölgesel arka plan karışımı ile belirsizlik yüksek kalabilir).  
- **Uydu okuması:** Sentinel-5P **L3** NO₂ ve CO sütunları, sabit AOI üzerinde **operasyonel hareketlilik proxy’si** olarak kullanılabilir; **üretim tonajı doğrudan ölçümü değildir**.  
- **Standart hizası:** [docs/standards/cement-data-acceptance-and-processing.md](../standards/cement-data-acceptance-and-processing.md) ile aynı L3 disiplinine yakın üretim hattı; sektöre özel `docs/standards/` eki (çelik) yol haritasında genişletilir.

### 1.2 Alüminyum

- **Profil:** Elektroliz nedeniyle **Scope 2 (elektrik)** yoğunluğu yüksektir; tesis çevresinde gece aydınlatması ve vardiya deseni **VIIRS DNB** ile **aktivite proxy’si** olarak okunabilir.  
- **Uydu okuması:** VIIRS `avg_rad` + **`cf_cvg`** şeffaflığı; NO₂/CO ile birlikte **enerji maliyeti / operasyonel yoğunluk** tartışması için bağlam.  
- **Sınır:** Elektrik karışımı şebeke kaynaklıdır; uydu **tek başına elektrik faturası doğrulaması** sunmaz.

---

## 2. Enerji ve lojistik yoğunluklu sektörler

Bu grup, trafo hattındaki **lojistik + aktivite proxy** mantığının **doğrudan uyarlanabileceği** örnekleri içerir (kurumsal kalibrasyon ve proprietary katsayılar ayrı).

### 2.1 Otomotiv ve batarya üretimi

- **Profil:** Karmaşık tedarik zinciri nedeniyle **Scope 3** payı yüksektir; fabrika sahası ve çevresinde **ağır vasıta trafiği** NO₂ ve trafik kaynaklı sinyallerle **dolaylı** ilişkilendirilebilir.  
- **Uyarı:** Şehir / OSB içi trafik **çoklu kaynak** karıştırır; “sevkiyat yoğunluğu = üretim hacmi” iddiası **ayrı doğrulama** gerektirir.

### 2.2 Enerji üretimi (termik ve doğalgaz santralleri)

- **Profil:** Bacadan termal imza ve gaz türevli emisyon bileşenleri **Landsat + Sentinel** çizgisinde okunabilir.  
- **Ölçülü dil:** Uydu özeti, santralin **anlık kapasite kullanımını resmi beyanlardan önce bağımsız olarak kanıtlar** ifadesi yerine: **resmi beyanlarla uydu türevli çapraz soru ve erken uyarı** dili kullanılmalıdır (regülasyon ve ölçüm belirsizliği).

---

## 3. Gübre ve kimyasallar

- **Profil:** Amonyak ve benzeri süreçler, Sentinel-5P ürün ailesinde **seçili gaz / sütun** bileşenleri ile **belirgin imza** gösterebilir (ürün bandı ve maske politikası tesise özel seçilir).  
- **Kullanım:** Beyan edilen emisyonlarla **çapraz zaman serisi** ve anomali tespiti; **kimyasal kimlik çözümlemesi** tek başına uydu ile tamamlanmaz.

---

## 4. Kapalı devre modeline katkı

| Avantaj | Açıklama |
| --- | --- |
| **Veri seti çeşitliliği** | Farklı sektörlerden gelen seriler, aynı metrik üçgeni (termal / emisyon / aktivite-lojistik) altında **model ve kalibrasyon** için daha geniş örnek uzayı sunar; “isabet” iddiası **tesise özel doğrulama** ile desteklenmelidir. |
| **Yeşil Mutabakat uyumu** | İhracat odaklı sanayi için paketler, alıcı tarafta **şeffaflık ve izlenebilirlik** dilinde sunulur; **düzenleyici uygunluk garantisi** değildir. |

Operasyonel çerçeve: **[georisk-sealed-index-closed-loop-publishing.md](./georisk-sealed-index-closed-loop-publishing.md)**.

---

## İlgili dosyalar

- Standartlar dizini: [../standards/README.md](../standards/README.md)  
- Trafo veri kabul standardı: [../standards/transformer-data-acceptance-and-processing.md](../standards/transformer-data-acceptance-and-processing.md)  
- Kamu whitepaper: [whitepaper-operational-verification-public.md](./whitepaper-operational-verification-public.md)
