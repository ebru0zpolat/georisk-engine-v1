# ESG Watch — karbon ayak izi denetim matrisi (Trafo Primary Audit)

Uzman denetçi için veri boru hatlarının **çapraz sorgu** amacı (proxy; resmi doğrulama değildir).

| Veri kaynağı | Karbon ayak izi metriği | Denetim hedefi |
| --- | --- | --- |
| Sentinel-5P NO₂ (L3) | Scope 2 (dolaylı enerji) | Tesisin enerji kullanım yoğunluğu ile beyan edilen emisyonların **uydu ile çapraz** tutarlılığı |
| Sentinel-5P CO (L3) | Scope 1 (doğrudan emisyon) | Yanma ve ısıl işlem / test aktivitesi için **bağımsız bağlam sinyali** |
| VIIRS Nighttime Lights (`avg_rad`) | Operasyonel canlılık | Gece vardiyaları ve aydınlatma ile **operasyonel yoğunluk**; kapasite proxy’si proprietary katmanda |

Landsat termal (çatı düzlemi) bu matriste **yardımcı fiziksel bağlam** olarak raporda yer alır; KAFİ Scope sınıfı tek başına termalden türetilmez.
