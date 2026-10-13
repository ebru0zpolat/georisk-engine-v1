import { useEffect, useRef, useState } from "react";
import { Map as MapLibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import "./risk-tiles.css";
import { createRiskTileController, type RiskTileController, type RiskTileLayerId } from "./risk-tile-controller";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8002/v1";
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels/style.json";

// Marmara pilot bbox served by GET /v1/tiles/{layer}/{z}/{x}/{y}.png
const MARMARA_CENTER: [number, number] = [28.25, 40.75];

const TILE_LAYERS = [
  { id: "total_risk", label: "Toplam Risk" },
  { id: "climate", label: "İklim" },
  { id: "water", label: "Su Stresi" },
] as const;

function RiskTilesPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const controllerRef = useRef<RiskTileController | null>(null);
  const [activeLayer, setActiveLayer] = useState<RiskTileLayerId>("total_risk");

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: MAP_STYLE,
      center: MARMARA_CENTER,
      zoom: 7,
      attributionControl: false,
    });
    const controller = createRiskTileController(map, API_BASE, "total_risk");
    controllerRef.current = controller;
    controller.bind();

    return () => {
      controller.dispose();
      map.remove();
      controllerRef.current = null;
    };
    // Map is created once; layer switching is handled below.
  }, []);

  useEffect(() => {
    controllerRef.current?.select(activeLayer);
  }, [activeLayer]);

  return (
    <div className="risk-tiles-page">
      <div className="risk-tiles-panel">
        <h1>GeoRisk Harita Katmanları</h1>
        <p className="risk-tiles-subtitle">Marmara pilot — {`/v1/tiles/{layer}/{z}/{x}/{y}.png`}</p>
        <div className="risk-tiles-switcher" role="tablist" aria-label="Risk katmanı seç">
          {TILE_LAYERS.map((layer) => (
            <button
              key={layer.id}
              role="tab"
              aria-selected={layer.id === activeLayer}
              className={layer.id === activeLayer ? "active" : ""}
              onClick={() => setActiveLayer(layer.id)}
            >
              {layer.label}
            </button>
          ))}
        </div>
        <div className="risk-tiles-legend">
          <span className="swatch low" /> Düşük
          <span className="swatch medium" /> Orta
          <span className="swatch high" /> Yüksek
        </div>
      </div>
      <div ref={containerRef} className="risk-tiles-map" />
    </div>
  );
}

export default RiskTilesPage;
