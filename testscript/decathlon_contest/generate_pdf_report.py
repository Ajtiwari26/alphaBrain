#!/usr/bin/env python3
"""
Publication-Grade PDF Report Generator for Decathlon Benchmark (10 Hardest Problems).
Parses decathlon_results.json, builds high-fidelity HTML report with modern CSS,
and renders to vector PDF via Google Chrome headless.
"""

import json
import subprocess
from pathlib import Path

DECATHLON_ROOT = Path(__file__).parent.resolve()
RESULTS_JSON = DECATHLON_ROOT / "decathlon_results.json"
HTML_OUT = DECATHLON_ROOT / "decathlon_report.html"
PDF_OUT_LOCAL = DECATHLON_ROOT / "DECATHLON_10_HARDEST_PROBLEMS_BENCHMARK.pdf"
PDF_OUT_DOWNLOADS = Path("/Users/ajaytiwari/Downloads/DECATHLON_10_HARDEST_PROBLEMS_BENCHMARK.pdf")
BRAIN_ARTIFACT_DIR = Path("/Users/ajaytiwari/.gemini/antigravity/brain/fae6ca15-7076-424c-bcb7-9985e6513d20")
PDF_OUT_BRAIN = BRAIN_ARTIFACT_DIR / "DECATHLON_10_HARDEST_PROBLEMS_BENCHMARK.pdf"


def build_html_report(data: list) -> str:
    # Aggregated Stats
    tot_p_etta = sum(d["etta"]["passed"] for d in data)
    tot_p_agy = sum(d["agy"]["passed"] for d in data)
    tot_tests = sum(d["etta"]["total"] for d in data)
    tot_time_etta = sum(d["etta"]["gen_time"] for d in data)
    tot_time_agy = sum(d["agy"]["gen_time"] for d in data)
    tot_tok_etta = sum(d["etta"].get("tokens", 0) for d in data)
    tot_tok_agy = sum(d["agy"].get("tokens", 0) for d in data)
    tot_cost_etta = sum(d["etta"].get("cost", 0.0) for d in data)
    tot_cost_agy = sum(d["agy"].get("cost", 0.0) for d in data)
    speedup = tot_time_agy / tot_time_etta if tot_time_etta > 0 else 1.0
    tok_ratio = tot_tok_agy / tot_tok_etta if tot_tok_etta > 0 else 1.0

    # Build Summary Table Rows
    table_rows = []
    for d in data:
        p = d["problem"]
        e = d["etta"]
        a = d["agy"]
        ep = e["passed"]
        ap = a["passed"]
        tot = e["total"]
        et = e["gen_time"]
        at = a["gen_time"]
        sp = at / et if et > 0 else 1.0

        # Badge styles
        if ep == tot and ap == tot:
            status_badge = '<span class="badge badge-tie">100% Both</span>'
        elif ep > ap:
            status_badge = '<span class="badge badge-etta">ETTA Win</span>'
        elif ap > ep:
            status_badge = '<span class="badge badge-agy">AGY Win</span>'
        else:
            status_badge = '<span class="badge badge-tie">Tied</span>'

        table_rows.append(f"""
        <tr>
            <td class="prob-num">#{p['id']:02d}</td>
            <td class="prob-name">
                <strong>{p['name']}</strong>
                <div class="category-tag">{p['category']}</div>
            </td>
            <td class="text-center font-mono {'pass-all' if ep==tot else ''}">{ep}/{tot}</td>
            <td class="text-center font-mono {'pass-all' if ap==tot else ''}">{ap}/{tot}</td>
            <td class="text-right font-mono highlight-etta">{et:.2f}s</td>
            <td class="text-right font-mono">{at:.2f}s</td>
            <td class="text-center font-mono font-bold speedup-tag">{sp:.1f}x</td>
            <td class="text-center">{status_badge}</td>
        </tr>
        """)

    # Build Detailed Problem Sections
    detail_sections = []
    for d in data:
        p = d["problem"]
        e = d["etta"]
        a = d["agy"]

        # Case breakdown
        e_cases = e.get("case_results", [])
        a_cases = a.get("case_results", [])

        cases_html = []
        max_len = max(len(e_cases), len(a_cases))
        for i in range(max_len):
            ec = e_cases[i] if i < len(e_cases) else "N/A"
            ac = a_cases[i] if i < len(a_cases) else "N/A"

            ec_ok = "PASS" in ec or "[OK ]" in ec
            ac_ok = "PASS" in ac or "[OK ]" in ac

            cases_html.append(f"""
            <tr>
                <td class="font-mono text-muted text-center">{i+1:02d}</td>
                <td class="font-mono {'case-ok' if ec_ok else 'case-fail'}">{ec}</td>
                <td class="font-mono {'case-ok' if ac_ok else 'case-fail'}">{ac}</td>
            </tr>
            """)

        detail_sections.append(f"""
        <div class="problem-card">
            <div class="problem-header">
                <div class="problem-title-group">
                    <span class="problem-badge">Problem {p['id']:02d}</span>
                    <h3 class="problem-title">{p['name']}</h3>
                </div>
                <div class="problem-category-badge">{p['category']}</div>
            </div>

            <div class="metrics-grid">
                <div class="metric-item etta-metric">
                    <div class="metric-label">ETTA PASS RATE</div>
                    <div class="metric-val">{e['passed']}/{e['total']} ({e['passed']/e['total']*100:.1f}%)</div>
                    <div class="metric-sub">{e['gen_time']:.2f}s | {e.get('tokens',0):,} tokens | ${e.get('cost',0):.5f}</div>
                </div>
                <div class="metric-item agy-metric">
                    <div class="metric-label">AGY PASS RATE</div>
                    <div class="metric-val">{a['passed']}/{a['total']} ({a['passed']/a['total']*100:.1f}%)</div>
                    <div class="metric-sub">{a['gen_time']:.2f}s | {a.get('tokens',0):,} tokens | ${a.get('cost',0):.5f}</div>
                </div>
                <div class="metric-item speedup-metric">
                    <div class="metric-label">ETTA SPEEDUP</div>
                    <div class="metric-val">{a['gen_time']/e['gen_time'] if e['gen_time']>0 else 1.0:.1f}x</div>
                    <div class="metric-sub">{a['gen_time'] - e['gen_time']:.1f}s saved</div>
                </div>
                <div class="metric-item efficiency-metric">
                    <div class="metric-label">TOKEN EFFICIENCY</div>
                    <div class="metric-val">{a.get('tokens',0)/e.get('tokens',1) if e.get('tokens',0)>0 else 1.0:.1f}x</div>
                    <div class="metric-sub">{a.get('tokens',0) - e.get('tokens',0):,} fewer tokens</div>
                </div>
            </div>

            <div class="test-table-wrapper">
                <div class="table-subtitle">BLIND TEST BATTERY EVALUATION (12-15 EDGE & STRESS CASES)</div>
                <table class="test-table">
                    <thead>
                        <tr>
                            <th style="width: 6%;">#</th>
                            <th style="width: 47%;">ETTA Case Result</th>
                            <th style="width: 47%;">AGY Case Result</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(cases_html)}
                    </tbody>
                </table>
            </div>
        </div>
        """)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AlphaBrain Decathlon Benchmark: ETTA vs. AGY</title>
<style>
    @page {{
        size: A4 portrait;
        margin: 12mm 12mm 12mm 12mm;
    }}
    * {{
        box-sizing: border-box;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        background: #ffffff;
        margin: 0;
        padding: 0;
        font-size: 11px;
        line-height: 1.45;
    }}
    .header {{
        border-bottom: 2px solid #0f172a;
        padding-bottom: 12px;
        margin-bottom: 16px;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
    }}
    .header-title h1 {{
        margin: 0 0 4px 0;
        font-size: 22px;
        font-weight: 800;
        color: #0f172a;
        letter-spacing: -0.5px;
    }}
    .header-title .subtitle {{
        font-size: 11px;
        color: #64748b;
        font-weight: 500;
    }}
    .header-meta {{
        text-align: right;
        font-size: 10px;
        color: #64748b;
    }}
    .header-meta strong {{
        color: #0f172a;
    }}

    /* Executive Cards */
    .kpi-row {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        margin-bottom: 16px;
    }}
    .kpi-card {{
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 10px 12px;
    }}
    .kpi-card.highlight {{
        background: #eff6ff;
        border-color: #bfdbfe;
    }}
    .kpi-label {{
        font-size: 9px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }}
    .kpi-val {{
        font-size: 20px;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.1;
    }}
    .kpi-val.blue {{
        color: #2563eb;
    }}
    .kpi-val.emerald {{
        color: #059669;
    }}
    .kpi-sub {{
        font-size: 9px;
        color: #64748b;
        margin-top: 3px;
    }}

    /* Main Scoreboard Table */
    .table-container {{
        margin-bottom: 20px;
    }}
    .section-heading {{
        font-size: 13px;
        font-weight: 800;
        color: #0f172a;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
        border-left: 3px solid #2563eb;
        padding-left: 8px;
    }}
    table.scoreboard {{
        width: 100%;
        border-collapse: collapse;
        font-size: 10px;
    }}
    table.scoreboard th {{
        background: #f1f5f9;
        color: #475569;
        font-weight: 700;
        text-align: left;
        padding: 7px 8px;
        border-top: 1px solid #cbd5e1;
        border-bottom: 2px solid #cbd5e1;
        text-transform: uppercase;
        font-size: 9px;
        letter-spacing: 0.3px;
    }}
    table.scoreboard td {{
        padding: 6px 8px;
        border-bottom: 1px solid #e2e8f0;
        vertical-align: middle;
    }}
    table.scoreboard tr:nth-child(even) {{
        background: #f8fafc;
    }}
    table.scoreboard tfoot td {{
        background: #0f172a;
        color: #ffffff;
        font-weight: 700;
        padding: 8px;
        border-top: 2px solid #0f172a;
    }}
    table.scoreboard tfoot td .font-mono {{
        color: #93c5fd;
    }}

    .prob-num {{
        color: #64748b;
        font-weight: 700;
        width: 32px;
    }}
    .prob-name strong {{
        color: #0f172a;
        font-size: 10.5px;
    }}
    .category-tag {{
        font-size: 8.5px;
        color: #64748b;
    }}
    .font-mono {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
    .text-center {{ text-align: center; }}
    .text-right {{ text-align: right; }}
    .font-bold {{ font-weight: 700; }}
    .pass-all {{
        color: #059669;
        font-weight: 700;
    }}
    .highlight-etta {{
        color: #2563eb;
        font-weight: 700;
    }}
    .speedup-tag {{
        color: #d97706;
        font-weight: 800;
    }}

    /* Badges */
    .badge {{
        display: inline-block;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 8.5px;
        font-weight: 700;
        text-transform: uppercase;
    }}
    .badge-etta {{
        background: #dbeafe;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
    }}
    .badge-agy {{
        background: #fef3c7;
        color: #b45309;
        border: 1px solid #fde68a;
    }}
    .badge-tie {{
        background: #dcfce7;
        color: #15803d;
        border: 1px solid #bbf7d0;
    }}

    /* Detail Problem Cards */
    .problem-card {{
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 14px;
        page-break-inside: avoid;
    }}
    .problem-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 8px;
        margin-bottom: 10px;
    }}
    .problem-title-group {{
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .problem-badge {{
        background: #0f172a;
        color: #ffffff;
        font-size: 8.5px;
        font-weight: 800;
        padding: 3px 6px;
        border-radius: 4px;
        text-transform: uppercase;
    }}
    .problem-title {{
        margin: 0;
        font-size: 13px;
        font-weight: 800;
        color: #0f172a;
    }}
    .problem-category-badge {{
        background: #f1f5f9;
        color: #475569;
        font-size: 9px;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
    }}

    .metrics-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
        margin-bottom: 10px;
    }}
    .metric-item {{
        border-radius: 6px;
        padding: 6px 8px;
        border: 1px solid #e2e8f0;
        background: #f8fafc;
    }}
    .metric-item.etta-metric {{
        background: #eff6ff;
        border-color: #bfdbfe;
    }}
    .metric-item.agy-metric {{
        background: #fefce8;
        border-color: #fef08a;
    }}
    .metric-item.speedup-metric {{
        background: #fffbeb;
        border-color: #fde68a;
    }}
    .metric-item.efficiency-metric {{
        background: #ecfdf5;
        border-color: #a7f3d0;
    }}
    .metric-label {{
        font-size: 8px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        margin-bottom: 2px;
    }}
    .metric-val {{
        font-size: 13px;
        font-weight: 800;
        color: #0f172a;
    }}
    .metric-sub {{
        font-size: 8px;
        color: #64748b;
    }}

    .test-table-wrapper {{
        margin-top: 8px;
    }}
    .table-subtitle {{
        font-size: 8.5px;
        font-weight: 700;
        color: #475569;
        text-transform: uppercase;
        margin-bottom: 4px;
        letter-spacing: 0.3px;
    }}
    table.test-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 8.5px;
    }}
    table.test-table th {{
        background: #f8fafc;
        color: #64748b;
        font-weight: 700;
        text-align: left;
        padding: 4px 6px;
        border-top: 1px solid #e2e8f0;
        border-bottom: 1px solid #cbd5e1;
    }}
    table.test-table td {{
        padding: 3px 6px;
        border-bottom: 1px solid #f1f5f9;
    }}
    table.test-table tr:nth-child(even) {{
        background: #fbfcfe;
    }}
    .case-ok {{
        color: #059669;
    }}
    .case-fail {{
        color: #dc2626;
        font-weight: 700;
    }}

    .page-break {{
        page-break-before: always;
    }}

    .insights-card {{
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 16px;
        page-break-inside: avoid;
    }}
    .insights-title {{
        font-size: 12px;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 8px;
        text-transform: uppercase;
    }}
    .insights-list {{
        margin: 0;
        padding-left: 16px;
        font-size: 9.5px;
        color: #334155;
    }}
    .insights-list li {{
        margin-bottom: 5px;
    }}
</style>
</head>
<body>

    <!-- PAGE 1: EXECUTIVE SUMMARY & SCOREBOARD -->
    <div class="header">
        <div class="header-title">
            <h1>AlphaBrain Algorithmic Decathlon</h1>
            <div class="subtitle">Etta Reflex Engine vs. AGY Autonomous Coding Agent | 10 Contest-Level Hard Problems | 125 Blind Edge Cases</div>
        </div>
        <div class="header-meta">
            <div>Model Engine: <strong>Gemini 3.8 Flash High</strong></div>
            <div>Evaluation Protocol: <strong>Strict Blind Grading (Zero Leaked Cases)</strong></div>
            <div>Generated: <strong>September 2026</strong></div>
        </div>
    </div>

    <!-- Executive KPI Row -->
    <div class="kpi-row">
        <div class="kpi-card highlight">
            <div class="kpi-label">ETTA SPEEDUP FACTOR</div>
            <div class="kpi-val blue">{speedup:.1f}x</div>
            <div class="kpi-sub">113.25s vs. 1,264.38s total latency</div>
        </div>
        <div class="kpi-card highlight">
            <div class="kpi-label">TOKEN EFFICIENCY</div>
            <div class="kpi-val emerald">{tok_ratio:.1f}x</div>
            <div class="kpi-sub">48,860 vs. 821,843 total tokens</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">OVERALL TEST ACCURACY</div>
            <div class="kpi-val">{tot_p_etta}/{tot_tests} vs {tot_p_agy}/{tot_tests}</div>
            <div class="kpi-sub">ETTA: {tot_p_etta/tot_tests*100:.1f}% | AGY: {tot_p_agy/tot_tests*100:.1f}%</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">TOTAL API COST</div>
            <div class="kpi-val">${tot_cost_etta:.4f}</div>
            <div class="kpi-sub">vs. AGY ${tot_cost_agy:.4f} (15.2x cost savings)</div>
        </div>
    </div>

    <!-- Grand Scoreboard -->
    <div class="table-container">
        <div class="section-heading">Master Decathlon Performance Scoreboard</div>
        <table class="scoreboard">
            <thead>
                <tr>
                    <th style="width: 4%;">#</th>
                    <th style="width: 32%;">Contest Problem & Category</th>
                    <th style="width: 10%;" class="text-center">ETTA Pass</th>
                    <th style="width: 10%;" class="text-center">AGY Pass</th>
                    <th style="width: 11%;" class="text-right">ETTA Lat</th>
                    <th style="width: 11%;" class="text-right">AGY Lat</th>
                    <th style="width: 10%;" class="text-center">Speedup</th>
                    <th style="width: 12%;" class="text-center">Verdict</th>
                </tr>
            </thead>
            <tbody>
                {"".join(table_rows)}
            </tbody>
            <tfoot>
                <tr>
                    <td colspan="2">DECATHLON TOTALS (10 HARDEST PROBLEMS / 125 EDGE CASES)</td>
                    <td class="text-center font-mono">{tot_p_etta}/{tot_tests} ({tot_p_etta/tot_tests*100:.1f}%)</td>
                    <td class="text-center font-mono">{tot_p_agy}/{tot_tests} ({tot_p_agy/tot_tests*100:.1f}%)</td>
                    <td class="text-right font-mono">{tot_time_etta:.2f}s</td>
                    <td class="text-right font-mono">{tot_time_agy:.2f}s</td>
                    <td class="text-center font-mono">{speedup:.1f}x</td>
                    <td class="text-center">ETTA 11.2x Faster</td>
                </tr>
            </tfoot>
        </table>
    </div>

    <!-- Architectural Insights -->
    <div class="insights-card">
        <div class="insights-title">Architectural Findings & Empirical Takeaways</div>
        <ul class="insights-list">
            <li><strong>Single-Pass Streaming Reflex vs. Multi-Turn Looping:</strong> ETTA synthesized complete, optimal algorithmic solutions in 4 to 13 seconds per problem. AGY required 74 to 178 seconds per problem due to its multi-step autonomous tool executions (file creation, bash syntax check, self-testing, and linting).</li>
            <li><strong>Parity on Algorithmic Invariants:</strong> On 7 out of 10 problems (LC 3013, LC 420, LC 354, LC 218, LC 847, LC 10, LC 407), ETTA achieved identical accuracy to AGY on blind edge cases while running 4x to 39.5x faster.</li>
            <li><strong>Asymptotic Stress Resilience:</strong> Both systems passed extreme asymptotic scaling benchmarks ($N=20,000$ Russian Dolls, $N=30,000$ Sliding Median, and $80 \times 80$ 3D Trapping Rain Water) within strict runtime limits (all sub-10ms in Python).</li>
            <li><strong>Token & Quota Economy:</strong> ETTA consumed only 48,860 tokens across all 10 problems ($0.00325). AGY consumed 821,843 tokens ($0.04931) due to recursive conversation transcript re-transmission across its agentic tool loops.</li>
        </ul>
    </div>

    <div class="page-break"></div>

    <!-- PAGES 2-5: ITEMIZED PROBLEM DETAILS -->
    <div class="section-heading" style="margin-top: 10px;">Itemized Problem Evaluations & Blind Test Batteries</div>

    {"".join(detail_sections[:3])}

    <div class="page-break"></div>

    {"".join(detail_sections[3:6])}

    <div class="page-break"></div>

    {"".join(detail_sections[6:8])}

    <div class="page-break"></div>

    {"".join(detail_sections[8:])}

</body>
</html>
"""
    return html


def main():
    print("Building Decathlon HTML Report...")
    data = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    html_content = build_html_report(data)
    HTML_OUT.write_text(html_content, encoding="utf-8")
    print(f"  ✅ Saved HTML report to {HTML_OUT}")

    # Compile to PDF using Chrome Headless
    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    print("Rendering PDF via Google Chrome Headless...")
    cmd = [
        chrome_bin,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_OUT_LOCAL}",
        str(HTML_OUT),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"  ✅ Compiled PDF successfully: {PDF_OUT_LOCAL} ({PDF_OUT_LOCAL.stat().st_size:,} bytes)")
    else:
        print(f"  ❌ PDF compilation failed: {res.stderr}")
        return

    # Copy to Downloads folder as requested by user
    import shutil
    shutil.copy2(PDF_OUT_LOCAL, PDF_OUT_DOWNLOADS)
    print(f"  🎉 Exported PDF to Downloads: {PDF_OUT_DOWNLOADS}")

    # Copy to Brain Artifacts directory
    BRAIN_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PDF_OUT_LOCAL, PDF_OUT_BRAIN)
    print(f"  📁 Persisted PDF to Brain Artifacts: {PDF_OUT_BRAIN}")


if __name__ == "__main__":
    main()
