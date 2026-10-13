from pydantic import BaseModel


class OceanFeatures(BaseModel):
    sst_trend_c_per_decade: float
    sst_anomaly_zscore: float
    sea_level_trend_mm_per_year: float
    ocean_variability_index: float
