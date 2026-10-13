"""Termal proxy üzerinden basit Kapasite Kullanım Oranı (KKO) tahmini.

Bu fonksiyon **uydu sıcaklığı ile gerçek üretim hacmini özdeşleştirmez**; örnek bir doğrusal
ölçekleme şemasıdır. Kalibrasyon saha verisi ve kurumsal onay olmadan genellenmez.

Varsayılan referans: Çimsa Afyon için örnek **tam kapasite** sıcaklığı ``baseline_temp``;
``standby_floor_c`` altı **%0** kabul edilir.
"""

from __future__ import annotations

DEFAULT_BASELINE_TEMP_C = 20.11
DEFAULT_STANDBY_FLOOR_C = 15.0


def estimate_capacity(
    temp: float,
    *,
    baseline_temp: float = DEFAULT_BASELINE_TEMP_C,
    standby_floor_c: float = DEFAULT_STANDBY_FLOOR_C,
) -> float:
    """Map thermal proxy °C to a capped percentage in ``[0, 100]``.

    Linear ramp from ``standby_floor_c`` (0 %) to ``baseline_temp`` (100 %).
    """
    if temp < standby_floor_c:
        return 0.0
    denom = baseline_temp - standby_floor_c
    if denom <= 0:
        raise ValueError("baseline_temp must be greater than standby_floor_c")
    capacity = ((temp - standby_floor_c) / denom) * 100.0
    return float(min(100.0, round(capacity, 2)))


def format_estimated_production_capacity(pct: float) -> str:
    """Kısa dashboard etiketi (ör. ``≈83.2%``). Uydu proxy’sidir; gerçek üretim tonajı değildir."""
    return f"≈{pct:.1f}%"


def format_capacity_pct_precise(pct: float) -> str:
    """İki ondalık yüzde puanı (örn. ``99.02%``, ``83.17%``).

    ``estimate_capacity`` zaten 2 ondalığa yuvarlar; burada gösterim tutarlıdır.
    Kurumsal kıyaslarda **0.01–0.02 p.p.** farkları korumak için kullanılır.
    """
    return f"{pct:.2f}%"
