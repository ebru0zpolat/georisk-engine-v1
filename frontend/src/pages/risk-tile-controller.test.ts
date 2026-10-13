import assert from "node:assert/strict";
import test from "node:test";

import {
  createRiskTileController,
  RISK_LAYER_ID,
  RISK_SOURCE_ID,
  type RasterMapContract,
} from "./risk-tile-controller.ts";

class MockMap implements RasterMapContract {
  loaded = false;
  disposed = false;
  failAdd = false;
  layers = new Map<string, object>();
  sources = new Map<string, object>();
  loadHandler: (() => void) | undefined;

  getLayer(id: string): unknown { return this.layers.get(id); }
  removeLayer(id: string): void { this.layers.delete(id); }
  getSource(id: string): unknown { return this.sources.get(id); }
  removeSource(id: string): void { this.sources.delete(id); }
  addSource(id: string, source: object): void {
    if (this.disposed || this.failAdd) throw new Error("source unavailable");
    this.sources.set(id, source);
  }
  addLayer(layer: object): void {
    if (this.disposed || this.failAdd) throw new Error("layer unavailable");
    this.layers.set((layer as { id: string }).id, layer);
  }
  isStyleLoaded(): boolean { return this.loaded; }
  once(_event: "load", handler: () => void): void { this.loadHandler = handler; }
  off(_event: "load", handler: () => void): void {
    if (this.loadHandler === handler) this.loadHandler = undefined;
  }
  finishLoad(): void { this.loaded = true; this.loadHandler?.(); }
}

test("load uses the newest selection and preserves raster contract", () => {
  const map = new MockMap();
  const controller = createRiskTileController(map, "https://api.example/v1", "total_risk");
  controller.bind();
  assert.equal(controller.select("water"), false);
  map.finishLoad();
  assert.deepEqual(map.sources.get(RISK_SOURCE_ID), {
    type: "raster",
    tiles: ["https://api.example/v1/tiles/water/{z}/{x}/{y}.png"],
    tileSize: 256,
    minzoom: 0,
    maxzoom: 12,
  });
  assert.deepEqual(map.layers.get(RISK_LAYER_ID), {
    id: RISK_LAYER_ID,
    type: "raster",
    source: RISK_SOURCE_ID,
    paint: { "raster-opacity": 0.65 },
  });
});

test("post-load and repeated selection replace rather than duplicate", () => {
  const map = new MockMap(); map.loaded = true;
  const controller = createRiskTileController(map, "http://localhost:8002/v1", "total_risk");
  assert.equal(controller.select("climate"), true);
  assert.equal(controller.select("climate"), true);
  assert.equal(map.layers.size, 1);
  assert.equal(map.sources.size, 1);
});

test("dispose removes handlers/resources and prevents late-load activation", () => {
  const map = new MockMap();
  const controller = createRiskTileController(map, "/v1", "total_risk");
  controller.bind();
  controller.dispose();
  map.disposed = true;
  map.finishLoad();
  assert.equal(map.loadHandler, undefined);
  assert.equal(map.layers.size, 0);
  assert.equal(map.sources.size, 0);
  assert.equal(controller.activate(), false);
});

test("style/source failure does not claim activation", () => {
  const map = new MockMap(); map.loaded = true; map.failAdd = true;
  const controller = createRiskTileController(map, "/v1", "total_risk");
  assert.equal(controller.activate(), false);
  assert.equal(map.layers.size, 0);
});
