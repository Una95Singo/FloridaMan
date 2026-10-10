import React, { useEffect, useRef, useState } from "react";
import { geoMercator, geoPath } from "d3-geo";
export default function GeographicFallback({
  geometry,
  forecast,
  compare,
  previous,
  zoom = 1,
}) {
  const ref = useRef(null);
  const [land, setLand] = useState(null),
    [size, setSize] = useState([1000, 800]),
    [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    fetch("/geo/land.geojson")
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then((d) => {
        if (active) setLand(d);
      })
      .catch(() => setFailed(true));
    const ro = new ResizeObserver(([e]) =>
      setSize([e.contentRect.width, e.contentRect.height]),
    );
    ro.observe(ref.current);
    return () => {
      active = false;
      ro.disconnect();
    };
  }, []);
  const [w, h] = size,
    mobile = w < 600;
  const proj = geoMercator()
    .center([-84.8, 26.8])
    .translate([w * (mobile ? 0.47 : 0.55), h * (mobile ? 0.4 : 0.46)])
    .scale((mobile ? 1900 : 3400) * zoom)
    .clipExtent([
      [0, 0],
      [w, h],
    ]);
  const path = geoPath(proj);
  const route = (a) =>
    a.map((p, i) => (i ? "L" : "M") + proj(p).join(",")).join(" ");
  const eye = proj(geometry.observed.at(-1));
  return (
    <div ref={ref} className="geographic-fallback">
      {failed ? (
        <div className="map-failure">
          Map data unavailable. Evidence remains accessible.
        </div>
      ) : (
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${w} ${h}`}
          role="img"
          aria-label="Compatibility map rendered from Natural Earth geographic coordinates"
        >
          <defs>
            <radialGradient id="ocean-depth">
              <stop offset="0" stopColor="#1c4053" />
              <stop offset="1" stopColor="#0d2638" />
            </radialGradient>
            <linearGradient id="land-tones" x1="0" x2="1" y1="0" y2="1">
              <stop stopColor="#607471" />
              <stop offset="1" stopColor="#344d55" />
            </linearGradient>
            <pattern
              id="chart-grid"
              width="60"
              height="60"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M60 0H0V60"
                fill="none"
                stroke="#607f8a"
                strokeOpacity=".08"
                strokeWidth=".6"
              />
            </pattern>
          </defs>
          <rect width={w} height={h} fill="url(#ocean-depth)" />
          <rect width={w} height={h} fill="url(#chart-grid)" />
          {land && (
            <g>
              {[32, 20, 10].map((n, i) => (
                <path
                  key={n}
                  d={path(land)}
                  stroke={["#204558", "#294d5d", "#355965"][i]}
                  strokeWidth={n}
                  opacity=".4"
                  fill="none"
                />
              ))}
              <path
                d={path(land)}
                fill="url(#land-tones)"
                stroke="#83998f"
                strokeWidth=".8"
              />
            </g>
          )}
          {forecast && !previous && (
            <path
              d={route(geometry.cone) + "Z"}
              fill="#d5ad63"
              fillOpacity=".2"
              stroke="#d6b170"
              strokeOpacity=".45"
              strokeWidth="1"
            />
          )}
          {(compare || previous) && (
            <path
              d={route(geometry.previous)}
              fill="none"
              stroke="#a8bfc0"
              strokeWidth="2"
              strokeDasharray="2 7"
            />
          )}
          <path
            d={route(geometry.observed)}
            fill="none"
            stroke="#e9d7b2"
            strokeWidth="2"
          />
          {forecast && !previous && (
            <path
              d={route(geometry.forecast)}
              fill="none"
              stroke="#e5bd7a"
              strokeWidth="2"
              strokeDasharray="5 5"
            />
          )}
          {geometry.observed.map(([a, b], i) => {
            let [x, y] = proj([a, b]);
            return (
              <circle
                key={i}
                cx={x}
                cy={y}
                r="3"
                fill="#eec889"
                stroke="#fff3d4"
                strokeWidth="1"
              />
            );
          })}
          <circle
            cx={eye[0]}
            cy={eye[1]}
            r="23"
            fill="#d3a861"
            fillOpacity=".1"
            stroke="#d3a861"
            strokeOpacity=".3"
          />
          <circle
            cx={eye[0]}
            cy={eye[1]}
            r="14"
            fill="#d3a861"
            fillOpacity=".25"
            stroke="#efd49a"
          />
          <circle
            cx={eye[0]}
            cy={eye[1]}
            r="6"
            fill="#e8bd70"
            stroke="#fff5d7"
            strokeWidth="2"
          />
          {[
            ["Tampa", -82.46, 27.95],
            ["Miami", -80.19, 25.77],
            ["Havana", -82.36, 23.11],
          ].map(([n, a, b]) => {
            let [x, y] = proj([a, b]);
            return (
              <g key={n}>
                <circle cx={x} cy={y} r="2.5" fill="#dee7d9" />
                <text
                  x={x + 8}
                  y={y + 4}
                  fill="#cbdad7"
                  fontSize={mobile ? 11 : 13}
                  fontFamily="Source Sans 3"
                >
                  {n}
                </text>
              </g>
            );
          })}
          {[
            ["Florida", -81.8, 29],
            ["Cuba", -80.6, 22.4],
            ["The Bahamas", -77.8, 24.3],
          ].map(([n, a, b]) => {
            let [x, y] = proj([a, b]);
            return (
              <text
                key={n}
                x={x}
                y={y}
                fill="#a3b9b8"
                fontSize={mobile ? 9 : 11}
                textAnchor="middle"
                letterSpacing="2"
              >
                {n}
              </text>
            );
          })}
          <text
            x={proj([-89.2, 26.8])[0]}
            y={proj([-89.2, 26.8])[1]}
            fill="#8ba8b3"
            fontFamily="Source Serif 4"
            fontSize={mobile ? 17 : 24}
            fontStyle="italic"
            textAnchor="middle"
            letterSpacing="2"
          >
            <tspan x={proj([-89.2, 26.8])[0]}>Gulf of</tspan>
            <tspan x={proj([-89.2, 26.8])[0]} dy="1.5em">
              Mexico
            </tspan>
          </text>
        </svg>
      )}
    </div>
  );
}
