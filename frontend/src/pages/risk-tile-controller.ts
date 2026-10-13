export const RISK_SOURCE_ID = "georisk-risk-tiles";
export const RISK_LAYER_ID = "georisk-risk-raster";

export type RiskTileLayerId = "total_risk" | "climate" | "water";

export interface RasterMapContract {
  getLayer(id: string): unknown;
  removeLayer(id: string): void;
  getSource(id: string): unknown;
  removeSource(id: string): void;
  addSource(id: string, source: object): void;
  addLayer(layer: object): void;
  isStyleLoaded(): boolean | void;
  once(event: "load", handler: () => void): void;
  off(event: "load", handler: () => void): void;
}

export interface RiskTileController {
  bind(): void;
  select(layerId: RiskTileLayerId): boolean;
  activate(): boolean;
  dispose(): void;
}

export function createRiskTileController(
  map: RasterMapContract,
  apiBase: string,
  initialLayer: RiskTileLayerId,
): RiskTileController {
  let selected = initialLayer;
  let disposed = false;

  const activate = (): boolean => {
    if (disposed || !map.isStyleLoaded()) return false;
    try {
      if (map.getLayer(RISK_LAYER_ID)) map.removeLayer(RISK_LAYER_ID);
      if (map.getSource(RISK_SOURCE_ID)) map.removeSource(RISK_SOURCE_ID);
      map.addSource(RISK_SOURCE_ID, {
        type: "raster",
        tiles: [`${apiBase}/tiles/${selected}/{z}/{x}/{y}.png`],
        tileSize: 256,
        minzoom: 0,
        maxzoom: 12,
      });
      map.addLayer({
        id: RISK_LAYER_ID,
        type: "raster",
        source: RISK_SOURCE_ID,
        paint: { "raster-opacity": 0.65 },
      });
      return true;
    } catch {
      return false;
    }
  };

  const onLoad = (): void => {
    activate();
  };

  return {
    bind(): void {
      if (!disposed) map.once("load", onLoad);
    },
    select(layerId: RiskTileLayerId): boolean {
      selected = layerId;
      return activate();
    },
    activate,
    dispose(): void {
      if (disposed) return;
      disposed = true;
      map.off("load", onLoad);
      try {
        if (map.getLayer(RISK_LAYER_ID)) map.removeLayer(RISK_LAYER_ID);
        if (map.getSource(RISK_SOURCE_ID)) map.removeSource(RISK_SOURCE_ID);
      } catch {
        // Map teardown remains safe even when style/source state is already unavailable.
      }
    },
  };
}
