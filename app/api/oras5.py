from fastapi import APIRouter

from app.connectors.cds_oras5 import CDSOras5Connector, Oras5PointRequest
from app.core.config import settings
from app.core.runtime_mode import oras5_uses_stub

router = APIRouter()
connector = CDSOras5Connector()


@router.get("/oras5/features")
def oras5_features(latitude: float, longitude: float):
    payload = Oras5PointRequest(latitude=latitude, longitude=longitude)
    features = connector.fetch_features(payload)
    data_mode = "stub" if oras5_uses_stub(settings) else "live"
    return {
        **features,
        "data_mode": data_mode,
        "production_eligible": False,
    }
