# Veri arşivi (çeyrek bazlı, izlenebilir dondurma)

Bu ağaç, **Quarterly Operational Review (QOR)** ve kurumsal **standartlaşma** sürecinin GitHub üzerinde **iz bırakan** parçasıdır. Amaç: belirli bir çeyrek için kullanılan metodoloji, standart metinleri ve (mümkünse) mühürlü çıktıların **o anki repo durumu** ile eşlenmesidir.

## Değişmezlik (immutability) ne anlama gelir?

Git **doğası gereği** geçmişi yeniden yazmadıkça commit’ler değişmez. “Asla değiştirilemez” operasyonel disiplin şu kurallarla sağlanır:

1. **`data/archive/YYYY-Qn/`** altına yalnızca **ekleme** yapılır; mevcut çeyrek dosyaları **yeniden yazılmaz** (typo düzeltmesi bile yeni çeyrek veya yeni patch commit politikasına bağlanır).  
2. Her çeyrek kapanışında bir **`archive/YYYY-Qn`** (veya `archive-YYYY-Qn`) **annotated Git tag** önerilir; tag, o çeyreğin manifest commit’ine kilitlenir.  
3. Büyük ham veri setleri repo boyutunu şişiriyorsa: manifest + checksum + **GitHub Release asset** veya kurumsal nesne depoda saklanır; burada yalnızca **referans ve doğrulama bilgisi** tutulur.

Detaylı operasyon: [docs/standards/github-archive-and-immutability.md](../docs/standards/github-archive-and-immutability.md).

## Dizinler

| Klasör | Açıklama |
| --- | --- |
| `2026-Q1/` | 2026 ilk çeyrek dondurma manifesti ve açıklamalar |

Yeni çeyrekler: `2026-Q2/`, `2026-Q3/`, … aynı şablonla eklenir.
