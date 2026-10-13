# Proprietary methodology statement — Thermal capacity proxy

**Internal · GeoRisk Engine**  
**Not legal advice:** Bu metin **patent başvurusu veya marka tescili yerine geçmez**. Fikri mülkiyet stratejisi için bağımsız **patent vekili / hukuk danışmanı** ile görüşülmelidir.

**Metodoloji mülkiyeti (kurumsal kayıt):** Termal kapasite proxy’sine ilişkin parametre setleri, kalibrasyon politikaları ve müşteriye özel genişletmeler **GRC yönetişimi** altında **ticari sır** olarak sınıflandırılır. Dokümantasyon sorumluluğu ve proprietary metin bakımı: **Ebru Özpolat**, Senior GRC Executive *(unvan kurumsal dizin ile uyumlu tutulmalıdır)*.

---

## 1. Purpose

**Termal Kapasite Proxy** olarak adlandırılan gösterge, Landsat türevli yüzey sıcaklığı özetinin, kuruluş içi tanımlı bir referans bandına göre **yüzde ölçekli bir işletme yoğunluğu proxy’sine** dönüştürülmesini ifade eder. Çıktı **gerçek üretim kapasitesi veya tonaj** ile özdeş kabul edilmez.

---

## 2. Proprietary classification

Aşağıdakiler ticari sırlar veya **“Proprietary Methodology”** kapsamında değerlendirilir:

- Referans sıcaklık ve alt band seçimi politikası  
- Yuvarlama ve gösterim disiplini (ör. iki ondalık yüzde puanı)  
- Dashboard ve raporlarda bu göstergenin nasıl sunulduğu ve feragat ile ilişkilendirildiği  
- Gelecekte saha verisi ile yapılacak kalibrasyon prosedürleri  

Bu öğeler **kamuya açık whitepaper’da** tam olarak açıklanmaz; müşteriye özel paylaşım **NDA ve sözleşme** ile sınırlıdır.

---

## 3. Patent / trade secret — kurumsal not

- **Patent:** Teknik yenilik, önceki teknik ve saklama stratejisi ülkeye göre değişir; başvuru kararı profesyonel danışmanlık gerektirir.  
- **Ticari sır:** Süreç ve parametreler gizli tutularak lisanslama modele bağlanabilir.  
- **Marka:** “GeoRisk Engine”, mühür ve rapor düzeni için ayrı marka stratejisi değerlendirilir.

---

## 4. Related documents

- Kamuya açık özet: [whitepaper-operational-verification-public.md](./whitepaper-operational-verification-public.md)  
- Trafo / lojistik hattı (ayrı proprietary beyan): [proprietary-transformer-logistics-capacity-proxy.md](./proprietary-transformer-logistics-capacity-proxy.md)  
- Buluş bildirimi taslağı ve kademeli FM stratejisi (iç): [ip-bulus-bildirimi-ve-fikri-mulkiyet-stratejisi-tr.md](./ip-bulus-bildirimi-ve-fikri-mulkiyet-stratejisi-tr.md)  
- DD paketi (NDA): [due-diligence/technical-overview-under-nda.md](./due-diligence/technical-overview-under-nda.md)  
- Kod konumu (iç): `app/scoring/capacity_proxy.py` *(erişim iç politika ile)*
