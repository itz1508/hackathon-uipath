"""Resolution Report HTML Renderer.

Takes a ResolutionReport dict and renders it to a clean HTML file.
Shows: Summary, A vs B comparison, Diff, Resolution breakdown, Metrics.
No raw phase logs. No internal pipeline details. Just the proof object.

Usage:
    from resolution_report_html import render_report_html
    html = render_report_html(report_dict)
"""
from __future__ import annotations

from typing import Any


def _esc(text: Any) -> str:
    """Escape HTML entities."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _score_bar(score: float, label: str, color: str) -> str:
    """Render a score bar with threshold marker."""
    width = min(100, max(2, score))
    threshold = 93.91
    bar_color = "#3fb950" if score >= threshold else color
    return f"""
    <div class="score-bar-container">
        <div class="score-bar-label">{_esc(label)}</div>
        <div class="score-bar-track">
            <div class="score-bar-fill" style="width:{width}%;background:{bar_color};">
                {score:.2f}%
            </div>
            <div class="threshold-marker" style="left:{threshold}%;" title="93.91% threshold"></div>
        </div>
    </div>"""


def _gauge(label: str, value: float) -> str:
    """Render a circular-style gauge as a card."""
    color = "#3fb950" if value >= 80 else ("#f0883e" if value >= 50 else "#f85149")
    return f"""
    <div class="gauge-card">
        <div class="gauge-value" style="color:{color};">{value:.1f}%</div>
        <div class="gauge-label">{_esc(label)}</div>
        <div class="gauge-track">
            <div class="gauge-fill" style="width:{min(100, value)}%;background:{color};"></div>
        </div>
    </div>"""


def _status_badge(status: str) -> str:
    """Render a status badge."""
    colors = {
        "fully_resolved": ("#3fb950", "#0d1117"),
        "partially_resolved": ("#f0883e", "#0d1117"),
        "failed": ("#f85149", "#ffffff"),
        "unknown": ("#8b949e", "#ffffff"),
    }
    bg, fg = colors.get(status, colors["unknown"])
    display = status.replace("_", " ").title()
    return f'<span class="status-badge" style="background:{bg};color:{fg};">{display}</span>'


def render_report_html(report: dict[str, Any]) -> str:
    """Render the full resolution report as HTML."""
    summary = report.get("summary", {})
    runs = report.get("runs", {})
    diff = report.get("diff", {})
    resolution = report.get("resolution", [])
    metrics = report.get("metrics", {})

    run_a = runs.get("A", {})
    run_b = runs.get("B", {})

    # ── Section 1: Summary ──
    summary_html = f"""
    <section class="section">
        <h2>Summary</h2>
        <div class="summary-grid">
            <div class="summary-card">
                <div class="card-value">{summary.get('initial_score', 0):.2f}%</div>
                <div class="card-label">Initial Score (A)</div>
            </div>
            <div class="summary-card">
                <div class="card-value">{summary.get('final_score', 0):.2f}%</div>
                <div class="card-label">Final Score (B)</div>
            </div>
            <div class="summary-card">
                <div class="card-value delta-{'pos' if summary.get('delta_score', 0) >= 0 else 'neg'}">{summary.get('delta_score', 0):+.2f}%</div>
                <div class="card-label">Delta</div>
            </div>
            <div class="summary-card">
                <div class="card-value">{summary.get('resolved', 0)}/{summary.get('total_issues', 0)}</div>
                <div class="card-label">Resolved</div>
            </div>
            <div class="summary-card status-card">
                {_status_badge(summary.get('status', 'unknown'))}
                <div class="card-label">Status</div>
            </div>
        </div>
    </section>"""

    # ── Section 2: A vs B Comparison ──
    comparison_html = f"""
    <section class="section">
        <h2>A vs B Comparison</h2>
        <div class="comparison-grid">
            <div class="run-card run-a">
                <h3>Run A — Isolation OFF</h3>
                {_score_bar(run_a.get('score', 0), 'Score', '#da3633')}
                <div class="run-stats">
                    <div class="stat"><span class="stat-val">{run_a.get('ready_count', 0)}</span> Ready</div>
                    <div class="stat"><span class="stat-val">{run_a.get('isolated_count', 0)}</span> Isolated</div>
                    <div class="stat"><span class="stat-val">{run_a.get('resolved_count', 0)}</span> Resolved</div>
                    <div class="stat"><span class="stat-val">{run_a.get('unresolved_count', 0)}</span> Unresolved</div>
                    <div class="stat">Sim Ready: <span class="stat-val">{'✓' if run_a.get('simulation_ready') else '✗'}</span></div>
                </div>
            </div>
            <div class="run-card run-b">
                <h3>Run B — Isolation ON</h3>
                {_score_bar(run_b.get('score', 0), 'Score', '#238636')}
                <div class="run-stats">
                    <div class="stat"><span class="stat-val">{run_b.get('ready_count', 0)}</span> Ready</div>
                    <div class="stat"><span class="stat-val">{run_b.get('isolated_count', 0)}</span> Isolated</div>
                    <div class="stat"><span class="stat-val">{run_b.get('resolved_count', 0)}</span> Resolved</div>
                    <div class="stat"><span class="stat-val">{run_b.get('unresolved_count', 0)}</span> Unresolved</div>
                    <div class="stat">Sim Ready: <span class="stat-val">{'✓' if run_b.get('simulation_ready') else '✗'}</span></div>
                </div>
            </div>
        </div>
    </section>"""

    # ── Section 3: Diff ──
    resolution_delta = diff.get("resolution_delta", [])
    diff_rows = ""
    for item in resolution_delta:
        sa = item.get("status_a", "—")
        sb = item.get("status_b", "—")
        changed = sa != sb
        row_class = "changed" if changed else ""
        arrow_class = "arrow-improved" if sb == "resolved" and sa != "resolved" else ("arrow-regressed" if sa == "resolved" and sb != "resolved" else "")
        diff_rows += f"""
            <tr class="{row_class}">
                <td class="item-id">{_esc(item.get('item_id', ''))}</td>
                <td class="status-cell status-{sa}">{sa}</td>
                <td class="arrow-cell {arrow_class}">→</td>
                <td class="status-cell status-{sb}">{sb}</td>
            </tr>"""

    score_delta = diff.get("score_delta", {})
    diff_html = f"""
    <section class="section">
        <h2>Diff — A vs B</h2>
        <div class="diff-summary">
            Score: {score_delta.get('before', 0):.2f}% → {score_delta.get('after', 0):.2f}%
        </div>
        <table class="diff-table">
            <thead>
                <tr>
                    <th>Item ID</th>
                    <th>Status A</th>
                    <th></th>
                    <th>Status B</th>
                </tr>
            </thead>
            <tbody>
                {diff_rows}
            </tbody>
        </table>
    </section>"""

    # ── Section 4: Resolution Breakdown ──
    resolution_rows = ""
    for item in resolution:
        result_class = item.get("result", "unknown")
        resolution_rows += f"""
            <tr class="res-{result_class}">
                <td class="item-id">{_esc(item.get('issue_id', ''))}</td>
                <td>{_esc(item.get('type', ''))}</td>
                <td>{_esc(item.get('cause', ''))}</td>
                <td>{_esc(item.get('action', ''))}</td>
                <td class="result-cell result-{result_class}">{_esc(item.get('result', ''))}</td>
            </tr>"""

    resolution_html = f"""
    <section class="section">
        <h2>Resolution Breakdown</h2>
        <table class="resolution-table">
            <thead>
                <tr>
                    <th>Issue ID</th>
                    <th>Type</th>
                    <th>Cause</th>
                    <th>Action</th>
                    <th>Result</th>
                </tr>
            </thead>
            <tbody>
                {resolution_rows}
            </tbody>
        </table>
    </section>"""

    # ── Section 5: Metrics ──
    metrics_html = f"""
    <section class="section">
        <h2>Metrics</h2>
        <div class="metrics-grid">
            {_gauge('Scan Coverage', metrics.get('scan_coverage', 0))}
            {_gauge('Analysis Confidence', metrics.get('analysis_confidence', 0))}
            {_gauge('Simulation Success', metrics.get('simulation_success_rate', 0))}
            {_gauge('Isolation Effectiveness', metrics.get('isolation_effectiveness', 0))}
            {_gauge('Pipeline Stability', metrics.get('pipeline_stability', 0))}
        </div>
    </section>"""

    # ── Full HTML ──
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resolution Report — {_esc(report.get('report_id', '')[:8])}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            padding: 2rem;
            line-height: 1.5;
        }}
        h1 {{
            color: #58a6ff;
            font-size: 1.6rem;
            margin-bottom: 0.3rem;
        }}
        .meta {{
            color: #8b949e;
            font-size: 0.85rem;
            margin-bottom: 2rem;
        }}
        .meta code {{
            background: #161b22;
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
            font-size: 0.8rem;
        }}
        h2 {{
            color: #58a6ff;
            font-size: 1.2rem;
            margin-bottom: 1rem;
            padding-bottom: 0.4rem;
            border-bottom: 1px solid #21262d;
        }}
        .section {{
            margin-bottom: 2.5rem;
        }}

        /* Summary Grid */
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
        }}
        .summary-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.2rem;
            text-align: center;
        }}
        .card-value {{
            font-size: 1.6rem;
            font-weight: 700;
            color: #f0f6fc;
        }}
        .card-value.delta-pos {{ color: #3fb950; }}
        .card-value.delta-neg {{ color: #f85149; }}
        .card-label {{
            font-size: 0.8rem;
            color: #8b949e;
            margin-top: 0.3rem;
        }}
        .status-badge {{
            display: inline-block;
            padding: 0.3rem 0.8rem;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        .status-card {{ display: flex; flex-direction: column; align-items: center; justify-content: center; }}

        /* Comparison */
        .comparison-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }}
        .run-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.5rem;
        }}
        .run-card h3 {{
            color: #f0f6fc;
            font-size: 1rem;
            margin-bottom: 1rem;
        }}
        .run-a {{ border-left: 3px solid #da3633; }}
        .run-b {{ border-left: 3px solid #238636; }}
        .run-stats {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.5rem;
            margin-top: 1rem;
        }}
        .stat {{
            font-size: 0.85rem;
            color: #8b949e;
        }}
        .stat-val {{
            color: #f0f6fc;
            font-weight: 600;
        }}

        /* Score bars */
        .score-bar-container {{ margin-bottom: 0.5rem; }}
        .score-bar-label {{
            font-size: 0.75rem;
            color: #8b949e;
            margin-bottom: 0.2rem;
        }}
        .score-bar-track {{
            position: relative;
            background: #21262d;
            border-radius: 4px;
            height: 24px;
            overflow: visible;
        }}
        .score-bar-fill {{
            height: 100%;
            border-radius: 4px;
            display: flex;
            align-items: center;
            padding-left: 8px;
            font-size: 0.75rem;
            font-weight: 700;
            color: #fff;
            min-width: 50px;
            transition: width 0.3s;
        }}
        .threshold-marker {{
            position: absolute;
            top: -2px;
            bottom: -2px;
            width: 2px;
            background: #f0883e;
            border-radius: 1px;
        }}
        .threshold-marker::after {{
            content: '93.91%';
            position: absolute;
            top: -16px;
            left: -14px;
            font-size: 0.6rem;
            color: #f0883e;
            white-space: nowrap;
        }}

        /* Diff table */
        .diff-summary {{
            font-size: 0.9rem;
            color: #8b949e;
            margin-bottom: 1rem;
            padding: 0.5rem 1rem;
            background: #161b22;
            border-radius: 6px;
            border: 1px solid #30363d;
        }}
        .diff-table, .resolution-table {{
            width: 100%;
            border-collapse: collapse;
            background: #161b22;
            border-radius: 8px;
            overflow: hidden;
        }}
        .diff-table th, .resolution-table th {{
            background: #21262d;
            color: #58a6ff;
            padding: 0.7rem 0.8rem;
            text-align: left;
            font-size: 0.8rem;
            text-transform: uppercase;
        }}
        .diff-table td, .resolution-table td {{
            padding: 0.6rem 0.8rem;
            border-top: 1px solid #21262d;
            font-size: 0.85rem;
        }}
        .item-id {{ font-weight: 600; color: #f0f6fc; }}
        .status-cell {{ font-weight: 500; }}
        .status-resolved {{ color: #3fb950; }}
        .status-unresolved {{ color: #f85149; }}
        .status-not_run {{ color: #8b949e; }}
        .arrow-cell {{ text-align: center; color: #8b949e; }}
        .arrow-improved {{ color: #3fb950; font-weight: bold; }}
        .arrow-regressed {{ color: #f85149; font-weight: bold; }}
        tr.changed {{ background: #1c2128; }}

        /* Resolution table */
        .result-cell {{ font-weight: 600; }}
        .result-resolved {{ color: #3fb950; }}
        .result-unresolved {{ color: #f85149; }}
        .result-isolated {{ color: #f0883e; }}

        /* Metrics */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 1rem;
        }}
        .gauge-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.2rem;
            text-align: center;
        }}
        .gauge-value {{
            font-size: 1.5rem;
            font-weight: 700;
        }}
        .gauge-label {{
            font-size: 0.75rem;
            color: #8b949e;
            margin: 0.3rem 0;
        }}
        .gauge-track {{
            background: #21262d;
            border-radius: 4px;
            height: 6px;
            margin-top: 0.5rem;
            overflow: hidden;
        }}
        .gauge-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }}

        /* Responsive */
        @media (max-width: 768px) {{
            .comparison-grid {{ grid-template-columns: 1fr; }}
            .summary-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <h1>Resolution Report</h1>
    <div class="meta">
        ID: <code>{_esc(report.get('report_id', ''))}</code> |
        Fixture: <code>{_esc(report.get('fixture', ''))}</code> |
        Hash: <code>{_esc(report.get('fixture_hash', '')[:16])}...</code> |
        Generated: {_esc(report.get('timestamp', ''))}
    </div>

    {summary_html}
    {comparison_html}
    {diff_html}
    {resolution_html}
    {metrics_html}

    <div class="meta" style="margin-top:2rem;text-align:center;">
        Resolution Report — A/B Comparison Mode — Pipeline Proof Object
    </div>
</body>
</html>"""

    return html
