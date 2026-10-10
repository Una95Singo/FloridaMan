import React, { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import GeographicFallback from "./GeographicFallback";
import {
  Layers,
  Plus,
  Minus,
  LocateFixed,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import "maplibre-gl/dist/maplibre-gl.css";
const line = (coordinates) => ({
  type: "Feature",
  properties: {},
  geometry: { type: "LineString", coordinates },
});
const point = (coordinates) => ({
  type: "Feature",
  properties: {},
  geometry: { type: "Point", coordinates },
});
export default function StormMap({ packet, compact = false }) {
  const container = useRef(null),
    map = useRef(null);
  const [svgZoom, setSvgZoom] = useState(1),
    [loaded, setLoaded] = useState(false),
    [error, setError] = useState(false),
    [layers, setLayers] = useState(false),
    [forecast, setForecast] = useState(true),
    [compare, setCompare] = useState(false),
    [previous, setPrevious] = useState(false);
  const geom = packet.geometry;
  useEffect(() => {
    let alive = true;
    setLoaded(false);
    setError(false);
    try {
      const m = new maplibregl.Map({
        container: container.current,
        style: {
          version: 8,
          sources: { land: { type: "geojson", data: "/geo/land.geojson" } },
          layers: [
            {
              id: "water",
              type: "background",
              paint: { "background-color": "#102c3e" },
            },
            {
              id: "shelf-outer",
              type: "line",
              source: "land",
              paint: {
                "line-color": "#24485a",
                "line-width": 30,
                "line-opacity": 0.25,
              },
            },
            {
              id: "shelf-inner",
              type: "line",
              source: "land",
              paint: {
                "line-color": "#2b5061",
                "line-width": 12,
                "line-opacity": 0.32,
              },
            },
            {
              id: "land",
              type: "fill",
              source: "land",
              paint: { "fill-color": "#40575a" },
            },
            {
              id: "coast",
              type: "line",
              source: "land",
              paint: {
                "line-color": "#85968d",
                "line-width": 0.75,
                "line-opacity": 0.65,
              },
            },
          ],
        },
        center: [-84.7, 26.2],
        zoom: 5.15,
        minZoom: 3.2,
        maxZoom: 9,
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        renderWorldCopies: false,
      });
      map.current = m;
      m.addControl(
        new maplibregl.AttributionControl({
          compact: true,
          customAttribution: "Natural Earth · Public domain",
        }),
        "bottom-left",
      );
      m.on("error", (e) => {
        if (alive && e.error?.message?.includes("land.geojson")) setError(true);
      });
      m.on("load", () => {
        if (!alive) return;
        setLoaded(true);
        m.addSource("observed", { type: "geojson", data: line(geom.observed) });
        m.addSource("forecast", { type: "geojson", data: line(geom.forecast) });
        m.addSource("previous", { type: "geojson", data: line(geom.previous) });
        m.addSource("cone", {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: { type: "Polygon", coordinates: [geom.cone] },
          },
        });
        m.addSource("dots", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: geom.observed.map(point),
          },
        });
        m.addSource("eye", {
          type: "geojson",
          data: point(geom.observed.at(-1)),
        });
        m.addLayer({
          id: "cone-fill",
          source: "cone",
          type: "fill",
          paint: { "fill-color": "#d5ad63", "fill-opacity": 0.18 },
        });
        m.addLayer({
          id: "cone-edge",
          source: "cone",
          type: "line",
          paint: {
            "line-color": "#dab777",
            "line-width": 1,
            "line-opacity": 0.35,
          },
        });
        m.addLayer({
          id: "previous-line",
          source: "previous",
          type: "line",
          layout: { visibility: "none" },
          paint: {
            "line-color": "#a9bdc0",
            "line-width": 2,
            "line-dasharray": [1, 3],
          },
        });
        m.addLayer({
          id: "observed-line",
          source: "observed",
          type: "line",
          paint: { "line-color": "#eddfbb", "line-width": 2.4 },
        });
        m.addLayer({
          id: "forecast-line",
          source: "forecast",
          type: "line",
          paint: {
            "line-color": "#e9c88a",
            "line-width": 2.4,
            "line-dasharray": [3, 2],
          },
        });
        m.addLayer({
          id: "dots-layer",
          source: "dots",
          type: "circle",
          paint: {
            "circle-radius": 3,
            "circle-color": "#ecd19c",
            "circle-stroke-width": 1,
            "circle-stroke-color": "#fff9e8",
          },
        });
        m.addLayer({
          id: "eye-glow",
          source: "eye",
          type: "circle",
          paint: {
            "circle-radius": 19,
            "circle-color": "#e1b970",
            "circle-opacity": 0.15,
            "circle-stroke-width": 1,
            "circle-stroke-color": "#c7a060",
          },
        });
        m.addLayer({
          id: "eye-mid",
          source: "eye",
          type: "circle",
          paint: {
            "circle-radius": 11,
            "circle-color": "#e1b970",
            "circle-opacity": 0.3,
            "circle-stroke-width": 1,
            "circle-stroke-color": "#f1d9a1",
          },
        });
        m.addLayer({
          id: "eye-dot",
          source: "eye",
          type: "circle",
          paint: {
            "circle-radius": 5,
            "circle-color": "#f1cd83",
            "circle-stroke-width": 2,
            "circle-stroke-color": "#fff6d8",
          },
        });
        const labels = [
          ["Tampa", -82.46, 27.95, "city"],
          ["Miami", -80.19, 25.77, "city"],
          ["Havana", -82.36, 23.11, "city"],
          ["Florida", -81.6, 28.6, "region"],
          ["Cuba", -80.6, 22, "region"],
          ["Gulf of Mexico", -88.0, 26.8, "ocean"],
          ["The Bahamas", -77.8, 24.5, "region"],
        ];
        labels.forEach(([name, lng, lat, type]) => {
          const el = document.createElement("span");
          el.className = "map-label " + type;
          el.textContent = name;
          new maplibregl.Marker({ element: el, anchor: "center" })
            .setLngLat([lng, lat])
            .addTo(m);
        });
        const mobile = window.innerWidth < 768;
        m.fitBounds(
          [
            [-90, 22],
            [-78.8, 30.4],
          ],
          {
            padding: compact
              ? 35
              : mobile
                ? { top: 45, bottom: 235, left: 15, right: 15 }
                : { top: 110, bottom: 100, left: 45, right: 65 },
            duration: 0,
          },
        );
      });
      const obs = new ResizeObserver(() => m.resize());
      obs.observe(container.current);
      return () => {
        alive = false;
        obs.disconnect();
        m.remove();
        map.current = null;
      };
    } catch {
      setError(true);
    }
  }, [packet.id, packet.version]);
  useEffect(() => {
    const m = map.current;
    if (!loaded || !m) return;
    ["cone-fill", "cone-edge", "forecast-line"].forEach((id) =>
      m.setLayoutProperty(
        id,
        "visibility",
        forecast && !previous ? "visible" : "none",
      ),
    );
    m.setLayoutProperty(
      "previous-line",
      "visibility",
      compare || previous ? "visible" : "none",
    );
  }, [loaded, forecast, compare, previous]);
  return (
    <div className={"storm-map " + (compact ? "compact" : "")}>
      <div
        ref={container}
        className="map-canvas"
        role="img"
        aria-label="Illustrative Gulf storm map. A synthetic track approaches Florida’s west coast. This does not establish insured exposure."
      />
      {!loaded && !error && (
        <div className="map-loading">Preparing the geography…</div>
      )}
      {error && (
        <GeographicFallback
          geometry={geom}
          forecast={forecast}
          compare={compare}
          previous={previous}
          zoom={svgZoom}
        />
      )}
      <div className="map-heading">
        <div className="map-tag">
          <span className="status-dot" />
          {packet.mode === "demo"
            ? "Synthetic replay"
            : "Pinned advisory"} · {packet.source_version}
        </div>
        <h1>{packet.storm}</h1>
        <p>
          {new Date(packet.as_of).toLocaleDateString(undefined, {
            day: "numeric",
            month: "long",
            year: "numeric",
          })}
        </p>
      </div>
      <div className="map-controls">
        <button
          aria-label="Map layers"
          aria-expanded={layers}
          onClick={() => setLayers(!layers)}
        >
          <Layers size={19} />
        </button>
        <button
          aria-label="Zoom in"
          onClick={() =>
            error
              ? setSvgZoom((z) => Math.min(3, z + 0.25))
              : map.current?.zoomIn()
          }
        >
          <Plus size={19} />
        </button>
        <button
          aria-label="Zoom out"
          onClick={() =>
            error
              ? setSvgZoom((z) => Math.max(0.5, z - 0.25))
              : map.current?.zoomOut()
          }
        >
          <Minus size={19} />
        </button>
        <button
          aria-label="Reset map view"
          onClick={() =>
            error
              ? setSvgZoom(1)
              : map.current?.flyTo({
                  center: [-84.7, 26.2],
                  zoom: 5.15,
                  duration: matchMedia("(prefers-reduced-motion: reduce)")
                    .matches
                    ? 0
                    : 350,
                })
          }
        >
          <LocateFixed size={19} />
        </button>
      </div>
      {layers && (
        <div className="layer-popover">
          <h3>Map layers</h3>
          <label>
            <input
              type="checkbox"
              checked={forecast}
              onChange={(e) => setForecast(e.target.checked)}
            />
            Forecast cone
          </label>
          <label>
            <input
              type="checkbox"
              checked={compare}
              onChange={(e) => setCompare(e.target.checked)}
            />
            Previous advisory
          </label>
          <p>Insured exposure unavailable.</p>
          <button className="text-btn" onClick={() => setLayers(false)}>
            Close layers
          </button>
        </div>
      )}
      <div className="map-legend">
        <span>
          <i className="observed-key" />
          Observed track
        </span>
        <span>
          <i className="forecast-key" />
          Forecast · illustrative
        </span>
      </div>
      <div className="map-timeline">
        <button
          aria-label="Previous advisory"
          className={previous ? "selected" : ""}
          onClick={() => setPrevious(true)}
        >
          <ChevronLeft size={16} />
          Previous
        </button>
        <div className="timeline-line">
          <i className={previous ? "prior" : ""} />
        </div>
        <button
          aria-label="Latest advisory"
          className={!previous ? "selected" : ""}
          onClick={() => setPrevious(false)}
        >
          Latest
          <ChevronRight size={16} />
        </button>
      </div>
      <div className="map-disclaimer">
        Natural Earth · Illustrative storm geometry
      </div>
    </div>
  );
}
