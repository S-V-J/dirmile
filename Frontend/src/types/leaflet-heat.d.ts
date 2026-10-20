import * as L from "leaflet";

declare module "leaflet" {
  interface HeatLayerOptions {
    minOpacity?: number;
    maxZoom?: number;
    max?: number;
    radius?: number;
    blur?: number;
    gradient?: Record<number, string>;
  }

  interface HeatLayer extends L.Layer {
    setLatLngs(latlngs: Array<[number, number, number]>): HeatLayer;
    addLatLng(latlng: [number, number, number]): HeatLayer;
    setOptions(options: HeatLayerOptions): HeatLayer;
    setMax(max: number): HeatLayer;
  }

  function heatLayer(
    latlngs: Array<[number, number, number]>,
    options?: HeatLayerOptions
  ): HeatLayer;
}
