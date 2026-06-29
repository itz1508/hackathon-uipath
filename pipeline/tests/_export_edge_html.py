"""Export Edge backend scan results to HTML report."""
import json
import sys
from pathlib import Path

_PIPELINE_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _PIPELINE_DIR.parent

run_root = _PIPELINE_DIR / "proof" / "edge_run"

# Collect all artifacts
runs_dir = run_root / "runs"
all_artifacts = {}
for run_dir in sorted(runs_dir.iterdir()):
    if run_dir.is_dir():
        for f in sorted(run_dir.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            all_artifacts[f.name] = data

scan = all_artifacts.get("01_scan_snapshot.json", {})
presim = all_artifacts.get("02_5_pre_simulation_package.json", {})
handoff = all_artifacts.get("02_handoff_statement.json", {})
raw_stmt = all_artifacts.get("02_raw_statement.json", {})

findings = scan.get("findings", [])
score = presim.get("confidence_score", 0)
status = presim.get("confidence_status", "")
sim_ready = presim.get("simulation_ready", False)
isolation_required = presim.get("isolation_required", False)

# Graders
code_graders = presim.get("required_code_grader_results", [])
weighted_graders = presim.get("weighted_grader_results", [])

score_class = "pass" if sim_ready else "fail"

# Build findings rows
findings_rows = ""
for f in findings:
    sev = f.get("severity", "info")
    cat = f.get("category", "")[:55]
    file = f.get("relative_path", "") or ""
    msg = (f.get("message", "") or "")[:90]
    findings_rows += f'<tr><td class="sev-{sev}">{sev}</td><td>{cat}</td><td>{file}</td><td>{msg}</td></tr>\n'

# Build grader rows
code_grader_rows = ""
for g in code_graders:
    passed = "✓" if g.get("passed") else "✗"
    cls = "pass" if g.get("passed") else "fail"
    code_grader_rows += f'<tr><td>{g.get("grader_id","")}</td><td class="{cls}">{passed}</td><td>{g.get("score",0):.1f}</td><td>{g.get("reason","")[:60]}</td></tr>\n'

weighted_grader_rows = ""
for g in weighted_graders:
    passed = "✓" if g.get("passed") else "✗"
    cls = "pass" if g.get("passed") else "fail"
    weighted_grader_rows += f'<tr><td>{g.get("grader_id","")}</td><td>{g.get("score",0):.1f}</td><td>{g.get("weight",0)}</td><td class="{cls}">{passed}</td><td>{g.get("reason","")[:50]}</td></tr>\n'

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Edge Backend — Scan Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 2rem; }}
h1 {{ color: #58a6ff; font-size: 1.8rem; margin-bottom: 0.3rem; }}
h2 {{ color: #7ee787; margin-top: 2rem; margin-bottom: 0.8rem; }}
h3 {{ color: #d2a8ff; margin-top: 1.2rem; margin-bottom: 0.5rem; }}
.meta {{ color: #8b949e; font-size: 0.85rem; margin-bottom: 1.5rem; }}
.score-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 1.5rem; text-align: center; margin-bottom: 1.5rem; }}
.score-value {{ font-size: 3rem; font-weight: 800; }}
.score-value.pass {{ color: #3fb950; }}
.score-value.fail {{ color: #f85149; }}
.score-meta {{ color: #8b949e; margin-top: 0.5rem; }}
.badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }}
.badge-pass {{ background: rgba(63,185,80,0.15); color: #3fb950; }}
.badge-fail {{ background: rgba(248,81,73,0.15); color: #f85149; }}
table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; margin-bottom: 1rem; }}
th {{ background: #21262d; color: #58a6ff; padding: 0.7rem; text-align: left; font-size: 0.8rem; text-transform: uppercase; }}
td {{ padding: 0.5rem 0.7rem; border-top: 1px solid #21262d; font-size: 0.85rem; }}
.pass {{ color: #3fb950; }}
.fail {{ color: #f85149; }}
.sev-high {{ color: #f85149; font-weight: 600; }}
.sev-medium {{ color: #f0883e; }}
.sev-low {{ color: #d2a8ff; }}
.sev-info {{ color: #8b949e; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
.summary-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1rem; text-align: center; }}
.summary-card .val {{ font-size: 1.5rem; font-weight: 700; color: #58a6ff; }}
.summary-card .lbl {{ font-size: 0.75rem; color: #8b949e; margin-top: 0.2rem; }}
</style>
</head>
<body>

<h1>Edge Backend — Scan Report</h1>
<p class="meta">Target: {_PIPELINE_DIR} | Engine: edge_backend v0</p>

<div class="score-card">
    <div class="score-value {score_class}">{score:.2f}%</div>
    <div class="score-meta">
        Confidence Status: <span class="badge badge-{'pass' if sim_ready else 'fail'}">{status}</span>
        | Threshold: 93.91%
        | Simulation Ready: <span class="{'pass' if sim_ready else 'fail'}">{sim_ready}</span>
        | Isolation Required: {isolation_required}
    </div>
</div>

<div class="summary-grid">
    <div class="summary-card"><div class="val">{len(findings)}</div><div class="lbl">Total Findings</div></div>
    <div class="summary-card"><div class="val">{sum(1 for f in findings if f.get('severity')=='high')}</div><div class="lbl">High</div></div>
    <div class="summary-card"><div class="val">{sum(1 for f in findings if f.get('severity')=='medium')}</div><div class="lbl">Medium</div></div>
    <div class="summary-card"><div class="val">{sum(1 for f in findings if f.get('severity')=='low')}</div><div class="lbl">Low</div></div>
    <div class="summary-card"><div class="val">{sum(1 for f in findings if f.get('severity')=='info')}</div><div class="lbl">Info</div></div>
    <div class="summary-card"><div class="val">{len(code_graders)}</div><div class="lbl">Code Graders</div></div>
    <div class="summary-card"><div class="val">{len(weighted_graders)}</div><div class="lbl">Weighted Graders</div></div>
</div>

<h2>Findings ({len(findings)})</h2>
<table>
<thead><tr><th>Severity</th><th>Category</th><th>File</th><th>Message</th></tr></thead>
<tbody>
{findings_rows}
</tbody>
</table>

<h2>Graders</h2>

<h3>Code Graders (Blockers) — {len(code_graders)}</h3>
<table>
<thead><tr><th>Grader</th><th>Passed</th><th>Score</th><th>Reason</th></tr></thead>
<tbody>
{code_grader_rows if code_grader_rows else '<tr><td colspan="4">No code grader data available</td></tr>'}
</tbody>
</table>

<h3>Weighted Graders — {len(weighted_graders)}</h3>
<table>
<thead><tr><th>Grader</th><th>Score</th><th>Weight</th><th>Passed</th><th>Reason</th></tr></thead>
<tbody>
{weighted_grader_rows if weighted_grader_rows else '<tr><td colspan="5">No weighted grader data available</td></tr>'}
</tbody>
</table>

</body>
</html>
"""

out_path = _PIPELINE_DIR / "proof" / "edge_scan_report.html"
out_path.write_text(html, encoding="utf-8")
print(f"HTML report saved: {out_path}")
print(f"Size: {out_path.stat().st_size / 1024:.1f} KB")
print(f"Score: {score:.2f}% | Status: {status} | Simulation Ready: {sim_ready}")
