"use client";

import { useMemo } from "react";

import { formatIst, formatIstTime, parseApiDate } from "@/lib/datetimeIst";

export type VitalsTrendPoint = {
  at: string;
  pulse?: string | null;
  systolic?: string | null;
  diastolic?: string | null;
  spo2?: string | null;
  temperature_f?: string | null;
  weight?: string | null;
  hemoglobin?: string | null;
  gestational_weeks?: number | null;
  gestational_label?: string | null;
};

export type VitalsAlert = {
  code: string;
  severity: string;
  message: string;
};

type SeriesPoint = { t: number; y: number; label: string };

function num(v: string | null | undefined): number | null {
  if (v == null || v === "") return null;
  const n = Number(String(v).replace(/[^\d.-]/g, ""));
  return Number.isFinite(n) ? n : null;
}

function seriesFrom(
  points: VitalsTrendPoint[],
  pick: (p: VitalsTrendPoint) => number | null,
  opts: { byGestation: boolean },
): SeriesPoint[] {
  const { byGestation } = opts;
  const out: SeriesPoint[] = [];
  for (const p of points) {
    const y = pick(p);
    if (y == null) continue;
    if (byGestation) {
      const gw = p.gestational_weeks;
      if (gw == null || !Number.isFinite(gw)) continue;
      out.push({
        t: gw,
        y,
        label: p.gestational_label || `${gw.toFixed(1)}w`,
      });
    } else {
      const d = parseApiDate(p.at);
      if (Number.isNaN(d.getTime())) continue;
      out.push({ t: d.getTime(), y, label: formatIstTime(p.at) });
    }
  }
  out.sort((a, b) => a.t - b.t);
  return out;
}

function pathFor(
  series: SeriesPoint[],
  width: number,
  height: number,
  pad: number,
  yMin: number,
  yMax: number,
): string {
  if (series.length === 0) return "";
  const t0 = series[0].t;
  const t1 = series[series.length - 1].t;
  const spanT = Math.max(t1 - t0, 1e-6);
  const spanY = Math.max(yMax - yMin, 1e-6);
  const coords = series.map((p, i) => {
    const x =
      series.length === 1
        ? pad + (width - 2 * pad) / 2
        : pad + ((p.t - t0) / spanT) * (width - 2 * pad);
    const y = pad + (1 - (p.y - yMin) / spanY) * (height - 2 * pad);
    return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
  });
  return coords.join(" ");
}

function LineChart({
  title,
  series,
  color,
  unit,
  secondSeries,
  secondColor,
  xAxisHint,
}: {
  title: string;
  series: SeriesPoint[];
  color: string;
  unit: string;
  secondSeries?: SeriesPoint[];
  secondColor?: string;
  xAxisHint?: string;
}) {
  const width = 320;
  const height = 140;
  const pad = 16;

  const { yMin, yMax, d1, d2 } = useMemo(() => {
    const all = [...series, ...(secondSeries || [])];
    if (all.length === 0) {
      return { yMin: 0, yMax: 1, d1: "", d2: "" };
    }
    const ys = all.map((p) => p.y);
    let lo = Math.min(...ys);
    let hi = Math.max(...ys);
    if (lo === hi) {
      lo -= 1;
      hi += 1;
    }
    const padY = (hi - lo) * 0.12;
    lo -= padY;
    hi += padY;
    return {
      yMin: lo,
      yMax: hi,
      d1: pathFor(series, width, height, pad, lo, hi),
      d2: secondSeries
        ? pathFor(secondSeries, width, height, pad, lo, hi)
        : "",
    };
  }, [series, secondSeries]);

  if (series.length === 0 && (!secondSeries || secondSeries.length === 0)) {
    return null;
  }

  const last = series[series.length - 1];
  const last2 = secondSeries?.[secondSeries.length - 1];

  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          {title}
        </h4>
        <p className="font-mono text-xs text-slate-700">
          {last ? `${last.y}${unit}` : null}
          {last2 != null ? (
            <span className="text-slate-500">
              {" "}
              / {last2.y}
              {unit}
            </span>
          ) : null}
        </p>
      </div>
      <svg
        aria-label={title}
        className="mt-2 w-full"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
      >
        <line
          x1={pad}
          x2={width - pad}
          y1={height - pad}
          y2={height - pad}
          stroke="#cbd5e1"
          strokeWidth={1}
        />
        <line
          x1={pad}
          x2={pad}
          y1={pad}
          y2={height - pad}
          stroke="#cbd5e1"
          strokeWidth={1}
        />
        {d1 ? (
          <path d={d1} fill="none" stroke={color} strokeWidth={2.5} />
        ) : null}
        {d2 ? (
          <path
            d={d2}
            fill="none"
            stroke={secondColor || "#64748b"}
            strokeWidth={2.5}
          />
        ) : null}
        {series.map((p, i) => {
          const t0 = series[0].t;
          const t1 = series[series.length - 1].t;
          const spanT = Math.max(t1 - t0, 1e-6);
          const spanY = Math.max(yMax - yMin, 1e-6);
          const x =
            series.length === 1
              ? pad + (width - 2 * pad) / 2
              : pad + ((p.t - t0) / spanT) * (width - 2 * pad);
          const y = pad + (1 - (p.y - yMin) / spanY) * (height - 2 * pad);
          return (
            <circle key={`${p.t}-${i}`} cx={x} cy={y} r={3} fill={color} />
          );
        })}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-slate-500">
        <span>{series[0]?.label || ""}</span>
        <span>
          {xAxisHint || `${yMin.toFixed(0)}–${yMax.toFixed(0)}${unit}`}
        </span>
        <span>{series[series.length - 1]?.label || ""}</span>
      </div>
      {secondSeries && secondSeries.length > 0 ? (
        <p className="mt-1 text-[10px] text-slate-500">
          <span style={{ color }}>Systolic</span>
          {" · "}
          <span style={{ color: secondColor }}>Diastolic</span>
        </p>
      ) : null}
    </div>
  );
}

export default function VitalsTrendCharts({
  points,
  emptyHint,
  alerts,
}: {
  points: VitalsTrendPoint[];
  emptyHint?: string;
  alerts?: VitalsAlert[];
}) {
  const byGestation = useMemo(
    () => points.some((p) => p.gestational_weeks != null),
    [points],
  );

  const weight = useMemo(
    () => seriesFrom(points, (p) => num(p.weight), { byGestation }),
    [points, byGestation],
  );
  const systolic = useMemo(
    () => seriesFrom(points, (p) => num(p.systolic), { byGestation }),
    [points, byGestation],
  );
  const diastolic = useMemo(
    () => seriesFrom(points, (p) => num(p.diastolic), { byGestation }),
    [points, byGestation],
  );
  const hemoglobin = useMemo(
    () => seriesFrom(points, (p) => num(p.hemoglobin), { byGestation }),
    [points, byGestation],
  );

  if (points.length === 0) {
    return emptyHint ? (
      <p className="mt-2 text-sm text-slate-500">{emptyHint}</p>
    ) : null;
  }

  if (
    weight.length === 0 &&
    systolic.length === 0 &&
    diastolic.length === 0 &&
    hemoglobin.length === 0
  ) {
    return (
      <p className="mt-2 text-sm text-slate-500">
        No weight, BP, or hemoglobin values in saved vitals yet.
      </p>
    );
  }

  const xHint = byGestation ? "X: gestational weeks" : undefined;

  return (
    <div className="mt-3 space-y-3">
      {(alerts || []).length > 0 ? (
        <ul className="space-y-1">
          {(alerts || []).map((a) => (
            <li
              key={a.code + a.message}
              className={`rounded-lg border px-3 py-2 text-xs ${
                a.severity === "critical"
                  ? "border-red-300 bg-red-50 text-red-900"
                  : a.severity === "warn"
                    ? "border-amber-300 bg-amber-50 text-amber-950"
                    : "border-slate-200 bg-slate-50 text-slate-800"
              }`}
            >
              {a.message}
            </li>
          ))}
        </ul>
      ) : null}
      {byGestation ? (
        <p className="text-xs text-slate-600">
          Charts use gestational age (from LMP) on the X-axis.
        </p>
      ) : null}
      {weight.length > 0 ? (
        <LineChart
          title={byGestation ? "Weight vs gestation" : "Weight"}
          series={weight}
          color="#0f766e"
          unit=" kg"
          xAxisHint={xHint}
        />
      ) : null}
      {systolic.length > 0 || diastolic.length > 0 ? (
        <LineChart
          title={byGestation ? "BP vs gestation" : "Blood pressure"}
          series={systolic.length ? systolic : diastolic}
          color="#b45309"
          unit=""
          secondSeries={diastolic.length ? diastolic : undefined}
          secondColor="#0369a1"
          xAxisHint={xHint}
        />
      ) : null}
      {hemoglobin.length > 0 ? (
        <LineChart
          title={byGestation ? "Hemoglobin vs gestation" : "Hemoglobin"}
          series={hemoglobin}
          color="#9f1239"
          unit=" g/dL"
          xAxisHint={xHint}
        />
      ) : null}
      <ul className="max-h-36 space-y-1 overflow-y-auto text-xs text-slate-600">
        {points.map((p, i) => (
          <li key={`${p.at}-${i}`} className="font-mono">
            {p.gestational_label ? `${p.gestational_label} · ` : null}
            {formatIst(p.at)}
            {" · "}
            {[
              p.weight ? `wt ${p.weight}kg` : null,
              p.systolic || p.diastolic
                ? `BP ${p.systolic || "—"}/${p.diastolic || "—"}`
                : null,
              p.hemoglobin ? `Hb ${p.hemoglobin}` : null,
              p.pulse ? `pulse ${p.pulse}` : null,
            ]
              .filter(Boolean)
              .join(" · ") || "—"}
          </li>
        ))}
      </ul>
    </div>
  );
}
