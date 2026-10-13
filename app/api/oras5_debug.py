from fastapi import APIRouter, HTTPException
import xarray as xr

from app.core.config import settings

router = APIRouter()


def _ensure_enabled():
    if settings.app_env not in {"local", "dev"}:
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/oras5/vars")
def list_vars():
    _ensure_enabled()
    if not settings.oras5_zarr_url:
        return {"configured": False}

    ds = xr.open_zarr(settings.oras5_zarr_url, consolidated=True)
    return {
        "configured": True,
        "variables": list(ds.data_vars),
        "coords": list(ds.coords),
        "dims": dict(ds.dims),
    }


@router.get("/oras5/status")
def status():
    _ensure_enabled()
    return {
        "configured": settings.oras5_zarr_url is not None,
        "fallback_mode": settings.oras5_zarr_url is None,
        "dataset": "reanalysis-oras5-timeseries",
    }
