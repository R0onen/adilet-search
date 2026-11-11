"""Generates infra/grafana/dashboards/adilet.json (edit here, then rerun: the JSON is build output).

    python infra/grafana/build_dashboard.py
"""

import json
from pathlib import Path

DATASOURCE = {"type": "prometheus", "uid": "prometheus"}
WIDTH = 12
HEIGHT = 8


def target(expr: str, legend: str) -> dict:
    return {"datasource": DATASOURCE, "expr": expr, "legendFormat": legend, "refId": legend[:20]}


def panel(title: str, targets: list[dict], unit: str = "short", description: str = "",
          threshold: float | None = None) -> dict:  # fmt: skip
    defaults: dict = {"unit": unit, "custom": {"fillOpacity": 8, "lineWidth": 2}}
    if threshold is not None:
        defaults["custom"]["thresholdsStyle"] = {"mode": "line"}
        defaults["thresholds"] = {
            "mode": "absolute",
            "steps": [{"color": "green", "value": None}, {"color": "red", "value": threshold}],
        }
    for index, item in enumerate(targets):
        item["refId"] = chr(ord("A") + index)
    return {
        "type": "timeseries",
        "title": title,
        "description": description,
        "datasource": DATASOURCE,
        "targets": targets,
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"},
                    "tooltip": {"mode": "multi"}},
    }  # fmt: skip


def quantile(q: float, metric: str, by: str = "", selector: str = "") -> str:
    group = f"le, {by}" if by else "le"
    return f"histogram_quantile({q}, sum by ({group}) (rate({metric}_bucket{selector}[5m])))"


PANELS = [
    panel(
        "Requests per second by endpoint",
        [target('sum by (path) (rate(http_requests_total{path!="/metrics"}[1m]))', "{{path}}")],
        unit="reqps",
    ),
    panel(
        "Search latency per stage (p95)",
        [target(quantile(0.95, "search_stage_latency_seconds", by="stage"), "{{stage}}")],
        unit="s",
        description="The red line is the 2 s target for the whole search.",
        threshold=2.0,
    ),
    panel(
        "Search latency, total (p50 / p95)",
        [
            target(quantile(0.5, "search_stage_latency_seconds", selector='{stage="total"}'), "p50"),
            target(quantile(0.95, "search_stage_latency_seconds", selector='{stage="total"}'), "p95"),
        ],
        unit="s",
        threshold=2.0,
    ),
    panel(
        "Error rate (5xx share)",
        [
            target(
                'sum(rate(http_requests_total{status=~"5.."}[5m])) '
                "/ clamp_min(sum(rate(http_requests_total[5m])), 0.001)",
                "5xx",
            ),
            target(
                'sum(rate(http_requests_total{status="429"}[5m])) '
                "/ clamp_min(sum(rate(http_requests_total[5m])), 0.001)",
                "429 rate limited",
            ),
        ],
        unit="percentunit",
    ),
    panel(
        "Zero-result rate",
        [
            target(
                "sum(rate(search_zero_results_total[5m])) "
                "/ clamp_min(sum(rate(search_requests_total[5m])), 0.001)",
                "zero results",
            )
        ],
        unit="percentunit",
    ),
    panel(
        "Degraded responses by component",
        [target("sum by (component) (rate(degraded_responses_total[5m]))", "{{component}}")],
        unit="reqps",
        description="semantic = full-text fallback; rerank = fused order; generation = no answer.",
    ),
    panel(
        "Answer time to first token (p50 / p95)",
        [
            target(quantile(0.5, "answer_ttft_seconds"), "p50"),
            target(quantile(0.95, "answer_ttft_seconds"), "p95"),
        ],
        unit="s",
    ),
    panel(
        "Feedback",
        [target("sum by (rating) (increase(feedback_total[1h]))", "{{rating}} (last hour)")],
    ),
    panel(
        "ML service latency (p95)",
        [target(quantile(0.95, "ml_request_duration_seconds", by="endpoint"), "{{endpoint}}")],
        unit="s",
    ),
    panel(
        "ML client errors and cache",
        [
            target("sum by (endpoint, kind) (rate(ml_client_errors_total[5m]))",
                   "error {{endpoint}} {{kind}}"),
            target("sum by (cache) (rate(cache_hits_total[5m]))", "cache hit {{cache}}"),
            target("sum by (cache) (rate(cache_misses_total[5m]))", "cache miss {{cache}}"),
        ],
        unit="reqps",
    ),  # fmt: skip
]


def main() -> None:
    for index, item in enumerate(PANELS):
        item["id"] = index + 1
        item["gridPos"] = {
            "x": (index % 2) * WIDTH, "y": (index // 2) * HEIGHT, "w": WIDTH, "h": HEIGHT
        }  # fmt: skip
    dashboard = {
        "uid": "adilet-search",
        "title": "Adilet Search",
        "tags": ["adilet"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "10s",
        "time": {"from": "now-30m", "to": "now"},
        "panels": PANELS,
    }
    out = Path(__file__).parent / "dashboards" / "adilet.json"
    out.write_text(json.dumps(dashboard, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out} with {len(PANELS)} panels")


if __name__ == "__main__":
    main()
