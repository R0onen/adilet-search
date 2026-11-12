/** Small dependency-free SVG charts. Each chart has a text alternative for screen readers. */

const WIDTH = 560;
const HEIGHT = 190;
const PAD = { top: 14, right: 12, bottom: 26, left: 44 };

type Point = { label: string; value: number | null };

function scaleMax(values: number[], floor = 1): number {
  const max = Math.max(floor, ...values);
  const step = 10 ** Math.floor(Math.log10(max));
  return Math.ceil(max / step) * step;
}

export function LineChart({
  title,
  points,
  unit = '',
  reference,
}: {
  title: string;
  points: Point[];
  unit?: string;
  /** A horizontal target line, e.g. 2000 ms. */
  reference?: { value: number; label: string };
}) {
  const known = points.filter(
    (point): point is { label: string; value: number } => point.value !== null,
  );
  if (!known.length) return <p className="admin-empty">Нет данных за период</p>;
  const max = scaleMax([...known.map((point) => point.value), reference?.value ?? 0]);
  const innerWidth = WIDTH - PAD.left - PAD.right;
  const innerHeight = HEIGHT - PAD.top - PAD.bottom;
  const x = (index: number) =>
    PAD.left + (points.length === 1 ? innerWidth / 2 : (index / (points.length - 1)) * innerWidth);
  const y = (value: number) => PAD.top + innerHeight - (value / max) * innerHeight;
  // Days without a value break the line instead of being drawn as zero.
  const segments: string[] = [];
  let current: string[] = [];
  points.forEach((point, index) => {
    if (point.value === null) {
      if (current.length) segments.push(current.join(' '));
      current = [];
    } else current.push(`${x(index).toFixed(1)},${y(point.value).toFixed(1)}`);
  });
  if (current.length) segments.push(current.join(' '));
  const labelEvery = Math.max(1, Math.ceil(points.length / 7));
  const summary = known.map((point) => `${point.label}: ${point.value}${unit}`).join('; ');
  return (
    <svg
      className="admin-chart"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      role="img"
      aria-label={`${title}. ${summary}`}
    >
      {[0, 0.5, 1].map((share) => (
        <g key={share}>
          <line
            x1={PAD.left}
            x2={WIDTH - PAD.right}
            y1={y(max * share)}
            y2={y(max * share)}
            className="chart-grid"
          />
          <text x={PAD.left - 6} y={y(max * share) + 4} textAnchor="end" className="chart-tick">
            {Math.round(max * share)}
          </text>
        </g>
      ))}
      {reference && (
        <g>
          <line
            x1={PAD.left}
            x2={WIDTH - PAD.right}
            y1={y(reference.value)}
            y2={y(reference.value)}
            className="chart-reference"
          />
          <text
            x={WIDTH - PAD.right}
            y={y(reference.value) - 4}
            textAnchor="end"
            className="chart-tick"
          >
            {reference.label}
          </text>
        </g>
      )}
      {segments.map((segment, index) => (
        <polyline key={index} points={segment} className="chart-line" />
      ))}
      {points.map(
        (point, index) =>
          point.value !== null && (
            <circle key={point.label} cx={x(index)} cy={y(point.value)} r={3} className="chart-dot">
              <title>{`${point.label}: ${point.value}${unit}`}</title>
            </circle>
          ),
      )}
      {points.map(
        (point, index) =>
          index % labelEvery === 0 && (
            <text
              key={point.label}
              x={x(index)}
              y={HEIGHT - 6}
              textAnchor="middle"
              className="chart-tick"
            >
              {point.label.slice(5)}
            </text>
          ),
      )}
    </svg>
  );
}

export function BarList({
  title,
  items,
}: {
  title: string;
  items: { label: string; value: number }[];
}) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  if (!total) return <p className="admin-empty">Нет данных за период</p>;
  return (
    <ul className="bar-list" aria-label={title}>
      {items.map((item) => (
        <li key={item.label}>
          <span className="bar-label">{item.label}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${(item.value / total) * 100}%` }} />
          </span>
          <span className="bar-value">
            {item.value} · {((item.value / total) * 100).toFixed(0)}%
          </span>
        </li>
      ))}
    </ul>
  );
}

const STAGES = ['embed', 'retrieve', 'fuse', 'rerank'] as const;
const STAGE_LABELS: Record<string, string> = {
  embed: 'эмбеддинг',
  retrieve: 'поиск',
  fuse: 'слияние',
  rerank: 'реранкинг',
  other: 'прочее',
};

/** Where the search time went, as one stacked bar. */
export function TimingBar({ timing }: { timing: Record<string, number | undefined> }) {
  const total = timing.total ?? 0;
  const parts = STAGES.map((stage) => ({ stage: stage as string, ms: timing[stage] ?? 0 })).filter(
    (part) => part.ms > 0,
  );
  const rest = total - parts.reduce((sum, part) => sum + part.ms, 0);
  if (rest > 0) parts.push({ stage: 'other', ms: rest });
  if (!total || !parts.length) return <p className="admin-empty">Нет данных о времени</p>;
  return (
    <div>
      <div className="timing-bar" role="img" aria-label={`Всего ${total} мс`}>
        {parts.map((part) => (
          <span
            key={part.stage}
            className={`timing-part timing-${part.stage}`}
            style={{ width: `${(part.ms / total) * 100}%` }}
            title={`${STAGE_LABELS[part.stage]}: ${part.ms} мс`}
          />
        ))}
      </div>
      <ul className="timing-legend">
        {parts.map((part) => (
          <li key={part.stage}>
            <span className={`timing-swatch timing-${part.stage}`} />
            {STAGE_LABELS[part.stage]}: {part.ms} мс
          </li>
        ))}
        <li>всего: {total} мс</li>
      </ul>
    </div>
  );
}
