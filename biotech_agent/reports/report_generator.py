"""
Report generator: assembles all agent outputs and infographics into
a polished investor-grade HTML report.
"""
import html
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

REPORT_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;1,400&family=Inter:wght@300;400;500;600&display=swap');

  :root {
    --bg: #FAFAF8;
    --surface: #FFFFFF;
    --border: #E8E6DF;
    --text: #1A1917;
    --sub: #5F5E5A;
    --accent: #1D9E75;
    --accent2: #534AB7;
    --warn: #BA7517;
    --danger: #A32D2D;
    --radius: 10px;
    --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04);
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    font-size: 15px;
    line-height: 1.75;
    padding: 0;
  }

  .report-wrapper { max-width: 920px; margin: 0 auto; padding: 48px 32px 80px; }

  /* Cover */
  .cover {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 48px 48px 40px;
    margin-bottom: 40px;
    box-shadow: var(--shadow);
    position: relative;
    overflow: hidden;
  }
  .cover::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
  }
  .cover-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 16px;
  }
  .cover-title {
    font-family: 'Lora', Georgia, serif;
    font-size: 36px;
    font-weight: 600;
    line-height: 1.2;
    color: var(--text);
    margin-bottom: 16px;
  }
  .cover-subtitle { font-size: 16px; color: var(--sub); margin-bottom: 28px; }
  .cover-meta {
    display: flex; gap: 24px; flex-wrap: wrap;
    font-size: 12px; color: var(--sub);
    border-top: 1px solid var(--border);
    padding-top: 20px;
  }
  .cover-meta span strong { color: var(--text); }

  /* Stats row */
  .stats-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 16px;
    margin-bottom: 40px;
  }
  .stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
    box-shadow: var(--shadow);
  }
  .stat-label { font-size: 11px; color: var(--sub); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }
  .stat-value { font-size: 28px; font-weight: 600; color: var(--accent); }
  .stat-sub { font-size: 11px; color: var(--sub); margin-top: 2px; }

  /* Sections */
  .section {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    margin-bottom: 28px;
    box-shadow: var(--shadow);
    overflow: hidden;
  }
  .section-header {
    padding: 20px 28px 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .section-number {
    width: 28px; height: 28px;
    border-radius: 50%;
    background: var(--accent);
    color: white;
    font-size: 12px;
    font-weight: 600;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }
  .section-title { font-size: 16px; font-weight: 600; color: var(--text); }
  .section-body { padding: 24px 28px; }

  /* Markdown-like content rendering */
  .content h2 { font-size: 17px; font-weight: 600; margin: 24px 0 10px; color: var(--text); }
  .content h3 { font-size: 15px; font-weight: 600; margin: 20px 0 8px; color: var(--text); }
  .content p { margin-bottom: 14px; }
  .content ul, .content ol { margin: 0 0 14px 20px; }
  .content li { margin-bottom: 6px; }
  .content strong { font-weight: 600; }
  .content em { font-style: italic; }
  .content code { font-family: monospace; background: #F1EFE8; padding: 1px 5px; border-radius: 3px; font-size: 13px; }

  /* Charts */
  .chart-grid { display: grid; grid-template-columns: 1fr; gap: 24px; }
  .chart-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--shadow);
  }
  .chart-card img { width: 100%; display: block; }
  .chart-label {
    padding: 12px 20px;
    font-size: 11px;
    color: var(--sub);
    border-top: 1px solid var(--border);
    text-align: center;
  }

  /* Trial table */
  .trial-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .trial-table th {
    background: #F1EFE8;
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--sub);
    border-bottom: 1px solid var(--border);
  }
  .trial-table td {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
  }
  .trial-table tr:last-child td { border-bottom: none; }
  .trial-table tr:hover td { background: #F9F8F5; }
  /* Inline markdown tables rendered from section text */
  .md-table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 8px 0; }
  .md-table th {
    background: var(--accent2); color: #fff; padding: 9px 14px;
    text-align: left; font-weight: 600; font-size: 12px;
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  .md-table td {
    padding: 9px 14px; border-bottom: 1px solid var(--border);
    vertical-align: top; font-size: 13px; line-height: 1.5;
  }
  .md-table tr.alt td { background: #FAFAF8; }
  .md-table tr:hover td { background: #F3F2EE; }
  .md-table tr:last-child td { border-bottom: none; }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
  }
  .badge-phase3 { background: #E1F5EE; color: #0F6E56; }
  .badge-phase2 { background: #9FE1CB; color: #04342C; }
  .badge-phase1 { background: #E6F1FB; color: #0C447C; }
  .badge-other  { background: #F1EFE8; color: #5F5E5A; }
  .badge-recruiting { background: #E6F1FB; color: #185FA5; }
  .badge-completed { background: #EAF3DE; color: #3B6D11; }
  .badge-active { background: #FAEEDA; color: #633806; }

  /* Risk tags */
  .risk-tag {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    margin: 3px 3px 3px 0;
  }
  .risk-high { background: #FCEBEB; color: #A32D2D; }
  .risk-med  { background: #FAEEDA; color: #854F0B; }
  .risk-low  { background: #EAF3DE; color: #3B6D11; }

  /* Footer */
  .report-footer {
    text-align: center;
    font-size: 11px;
    color: var(--sub);
    padding: 32px 0 0;
    border-top: 1px solid var(--border);
    margin-top: 40px;
  }

  /* Executive summary highlight */
  .exec-summary {
    background: linear-gradient(135deg, #F0FFF8 0%, #EEF0FF 100%);
    border: 1px solid #C0E8D4;
    border-radius: var(--radius);
    padding: 28px 32px;
    margin-bottom: 28px;
  }
  .exec-summary .exec-label {
    font-size: 11px; font-weight: 600; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--accent); margin-bottom: 12px;
  }

  @media print {
    body { background: white; }
    .section, .chart-card, .stat-card { box-shadow: none; }
  }
</style>
"""


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 2

def _is_separator_row(line: str) -> bool:
    import re as _re
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return False
    inner = s[1:-1]
    return all(_re.match(r"^[\s\-:]+$", cell) for cell in inner.split("|"))

def _parse_table_row(line: str) -> list:
    s = line.strip()
    if s.startswith("|"): s = s[1:]
    if s.endswith("|"):   s = s[:-1]
    return [cell.strip() for cell in s.split("|")]

def _render_md_table(rows: list) -> str:
    if not rows:
        return ""
    thead = rows[0]
    tbody = rows[1:]
    th_cells = "".join(f"<th>{_inline_markdown(c)}</th>" for c in thead)
    tr_rows = ""
    for i, row in enumerate(tbody):
        cells = "".join(f"<td>{_inline_markdown(c)}</td>" for c in row)
        stripe = ' class="alt"' if i % 2 else ""
        tr_rows += f"<tr{stripe}>{cells}</tr>"
    return (
        '<div style="overflow-x:auto;margin:12px 0">' +
        '<table class="md-table">' +
        f"<thead><tr>{th_cells}</tr></thead>" +
        f"<tbody>{tr_rows}</tbody>" +
        "</table></div>"
    )

def _markdown_to_html(text: str) -> str:
    """Markdown-to-HTML: headers, bold/italic, lists, numbered lists, pipe tables."""
    if not text:
        return "<p>No data available.</p>"
    import re as _re

    lines = text.split("\n")
    processed = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_table_row(line) or _is_separator_row(line):
            block = []
            while i < len(lines) and (_is_table_row(lines[i]) or _is_separator_row(lines[i])):
                block.append(lines[i])
                i += 1
            rows = []
            for bline in block:
                if _is_separator_row(bline):
                    continue
                rows.append(_parse_table_row(bline))
            if rows:
                processed.append("__TABLE__:" + "\x00".join(
                    "\x01".join(cell for cell in row) for row in rows
                ))
        else:
            processed.append(line)
            i += 1

    html_lines = []
    in_list = False
    in_ol = False

    def close_lists():
        nonlocal in_list, in_ol
        if in_list:  html_lines.append("</ul>"); in_list = False
        if in_ol:    html_lines.append("</ol>"); in_ol = False

    for line in processed:
        if line.startswith("__TABLE__:"):
            close_lists()
            payload = line[len("__TABLE__:"):]
            rows = [[c for c in row.split("\x01")] for row in payload.split("\x00")]
            html_lines.append(_render_md_table(rows))
        elif line.startswith("## "):
            close_lists()
            html_lines.append(f'<h2>{_inline_markdown(line[3:])}</h2>')
        elif line.startswith("### "):
            close_lists()
            html_lines.append(f'<h3>{_inline_markdown(line[4:])}</h3>')
        elif line.startswith("#### "):
            close_lists()
            html_lines.append(f'<h4>{_inline_markdown(line[5:])}</h4>')
        elif line.startswith("# "):
            close_lists()
            html_lines.append(f'<h2>{_inline_markdown(line[2:])}</h2>')
        elif _re.match(r'^[-*_]{3,}\s*$', line.strip()):
            close_lists()
            html_lines.append("<hr>")
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                if in_ol: html_lines.append("</ol>"); in_ol = False
                html_lines.append("<ul>"); in_list = True
            html_lines.append(f"<li>{_inline_markdown(line[2:])}</li>")
        elif _re.match(r'^\d+[.)]\s', line):
            if not in_ol:
                if in_list: html_lines.append("</ul>"); in_list = False
                html_lines.append("<ol>"); in_ol = True
            content = _re.sub(r'^\d+[.)]\s+', '', line)
            html_lines.append(f"<li>{_inline_markdown(content)}</li>")
        elif not line.strip():
            close_lists()
            html_lines.append("")
        else:
            close_lists()
            html_lines.append(f"<p>{_inline_markdown(line)}</p>")

    close_lists()
    return "\n".join(html_lines)


def _inline_markdown(text: str) -> str:
    """Handle bold, italic, inline code."""
    import re
    text = html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def _phase_badge(phase: str) -> str:
    p = phase.upper()
    if "3" in p or "III" in p:
        return f'<span class="badge badge-phase3">{html.escape(phase)}</span>'
    if "2" in p or "II" in p:
        return f'<span class="badge badge-phase2">{html.escape(phase)}</span>'
    if "1" in p or "I" in p:
        return f'<span class="badge badge-phase1">{html.escape(phase)}</span>'
    return f'<span class="badge badge-other">{html.escape(phase)}</span>'


def _status_badge(status: str) -> str:
    s = status.upper()
    if "RECRUIT" in s:
        return f'<span class="badge badge-recruiting">{html.escape(status)}</span>'
    if "COMPLET" in s:
        return f'<span class="badge badge-completed">{html.escape(status)}</span>'
    if "ACTIVE" in s:
        return f'<span class="badge badge-active">{html.escape(status)}</span>'
    return f'<span class="badge badge-other">{html.escape(status)}</span>'


def build_trial_table(trials: list[dict]) -> str:
    if not trials:
        return "<p style='color:#888'>No trial data available.</p>"
    rows = ""
    for t in trials[:30]:
        nct = t.get("nct_id", "N/A")
        nct_link = f'<a href="https://clinicaltrials.gov/study/{nct}" target="_blank" style="color:#1D9E75;text-decoration:none">{html.escape(nct)}</a>'
        title = html.escape(t.get("title", "")[:60])
        phase = _phase_badge(t.get("phase", "N/A"))
        status = _status_badge(t.get("status", "N/A"))
        enrollment = html.escape(str(t.get("enrollment", "N/A")))
        sponsor = html.escape(t.get("sponsor", "N/A")[:35])
        completion = html.escape(t.get("completion_date", "N/A")[:7])
        outcomes = html.escape(", ".join(t.get("primary_outcomes", [])[:2])[:60])
        rows += f"""
        <tr>
          <td>{nct_link}</td>
          <td>{title}</td>
          <td>{phase}</td>
          <td>{status}</td>
          <td style="text-align:center">{enrollment}</td>
          <td>{sponsor}</td>
          <td>{completion}</td>
        </tr>"""
    return f"""
    <div style="overflow-x:auto">
    <table class="trial-table">
      <thead>
        <tr>
          <th>NCT ID</th><th>Title</th><th>Phase</th><th>Status</th>
          <th>N</th><th>Sponsor</th><th>Est. Completion</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    </div>"""


def build_chart_html(charts: dict, key: str, caption: str) -> str:
    b64 = charts.get(key, "")
    if not b64:
        return f'<p style="color:#888;font-size:13px">Chart not available: {caption}</p>'
    return f"""
    <div class="chart-card">
      <img src="data:image/png;base64,{b64}" alt="{html.escape(caption)}" loading="lazy"/>
      <div class="chart-label">{html.escape(caption)}</div>
    </div>"""


def generate_html_report(
    query: str,
    agent_state: dict,
    charts: dict,
    retrieval_stats: dict,
    trials: list[dict],
) -> str:
    now = datetime.now().strftime("%B %d, %Y")
    total_docs = retrieval_stats.get("total_count", 0)
    n_trials = retrieval_stats.get("stats", {}).get("clinical_trials", 0)
    n_pubmed = retrieval_stats.get("stats", {}).get("pubmed", 0)
    n_fda = retrieval_stats.get("stats", {}).get("fda", 0)

    exec_summary_html = _markdown_to_html(agent_state.get("investor_narrative", ""))
    scientific_html = _markdown_to_html(agent_state.get("scientific_summary", ""))
    trial_landscape_html = _markdown_to_html(agent_state.get("trial_landscape", ""))
    critique_html = _markdown_to_html(agent_state.get("trial_critique", ""))
    pipeline_html = _markdown_to_html(agent_state.get("pipeline_regulatory", ""))
    competitive_html = _markdown_to_html(agent_state.get("competitive_landscape", ""))
    market_html = _markdown_to_html(agent_state.get("market_sizing", ""))
    pricing_html = _markdown_to_html(agent_state.get("pricing_reimbursement", ""))
    strat_html = _markdown_to_html(agent_state.get("patient_stratification", ""))
    moa_html = _markdown_to_html(agent_state.get("moa_landscape", ""))
    safety_html = _markdown_to_html(agent_state.get("long_term_safety", ""))
    dynamics_html = _markdown_to_html(agent_state.get("competitive_dynamics", ""))
    rec_html = _markdown_to_html(agent_state.get("investment_recommendation", ""))
    trial_table_html = build_trial_table(trials)

    report = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Biotech Research Report: {html.escape(query)}</title>
{REPORT_CSS}
</head>
<body>
<div class="report-wrapper">

  <!-- COVER -->
  <div class="cover">
    <div class="cover-label">AI-Generated Biotech Intelligence · VC Investor Briefing</div>
    <div class="cover-title">{html.escape(query.title())}</div>
    <div class="cover-subtitle">Market sizing · competitive pipeline · regulatory landscape · investment recommendation</div>
    <div class="cover-meta">
      <span><strong>Date:</strong> {now}</span>
      <span><strong>Sources:</strong> PubMed, ClinicalTrials.gov, Semantic Scholar, FDA, bioRxiv</span>
      <span><strong>Documents analysed:</strong> {total_docs}</span>
      <span><strong>Report type:</strong> Preliminary Investment Briefing</span>
    </div>
  </div>

  <!-- STATS ROW -->
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-label">Literature sources</div>
      <div class="stat-value">{n_pubmed}</div>
      <div class="stat-sub">PubMed articles</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Clinical trials</div>
      <div class="stat-value">{n_trials}</div>
      <div class="stat-sub">ClinicalTrials.gov records</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">FDA records</div>
      <div class="stat-value">{n_fda}</div>
      <div class="stat-sub">Drug labels analysed</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Total documents</div>
      <div class="stat-value">{total_docs}</div>
      <div class="stat-sub">Across all sources</div>
    </div>
  </div>

  <!-- EXECUTIVE SUMMARY & INVESTMENT IMPLICATIONS -->
  <div class="exec-summary">
    <div class="exec-label">Executive Summary &amp; Investment Implications</div>
    <div class="content">{exec_summary_html}</div>
  </div>

  <!-- SECTION 1: SCIENTIFIC SUMMARY -->
  <div class="section">
    <div class="section-header">
      <div class="section-number">1</div>
      <div class="section-title">Scientific Summary</div>
    </div>
    <div class="section-body">
      <div class="content">{scientific_html}</div>
    </div>
  </div>

  <!-- SECTION 2: CLINICAL TRIAL LANDSCAPE -->
  <div class="section">
    <div class="section-header">
      <div class="section-number">2</div>
      <div class="section-title">Clinical Trial Landscape</div>
    </div>
    <div class="section-body">
      <div class="content">{trial_landscape_html}</div>
      <div style="margin-top: 24px;">
        <h3 style="font-size:14px;font-weight:600;margin-bottom:14px;color:#5F5E5A;text-transform:uppercase;letter-spacing:0.06em;">Trial Register</h3>
        {trial_table_html}
      </div>
    </div>
  </div>

  <!-- SECTION 3: INFOGRAPHICS -->
  <div class="section">
    <div class="section-header">
      <div class="section-number">3</div>
      <div class="section-title">Data Visualisations</div>
    </div>
    <div class="section-body">
      <h3 style="font-size:13px;font-weight:600;color:var(--sub);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:14px;">Pipeline overview</h3>
      <div class="chart-grid" style="margin-bottom:24px;">
        {build_chart_html(charts, "phase_distribution", "Trial count by phase and status")}
        {build_chart_html(charts, "funnel_chart", "Development stage funnel — asset counts from Phase 1 through approved")}
        {build_chart_html(charts, "pipeline_gantt", "Pipeline Gantt — all trials by start and estimated completion date")}
        {build_chart_html(charts, "enrollment_trend", "Cumulative patient enrollment over time")}
      </div>
      <h3 style="font-size:13px;font-weight:600;color:var(--sub);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:14px;">Competitive and regulatory</h3>
      <div class="chart-grid" style="margin-bottom:24px;">
        {build_chart_html(charts, "regulatory_swimlane", "Regulatory pathway — where each asset sits in the FDA/EMA process")}
        {build_chart_html(charts, "binary_events", "Binary events calendar — upcoming trial completions and readouts")}
        {build_chart_html(charts, "moa_chart", "Mechanism of action diversity across trial arms")}
        {build_chart_html(charts, "sponsor_chart", "Top sponsors by active trial count")}
      </div>
      <h3 style="font-size:13px;font-weight:600;color:var(--sub);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:14px;">Trial quality and investment analysis</h3>
      <div class="chart-grid">
        {build_chart_html(charts, "radar_chart", "Radar — trial methodology quality profiles across 6 dimensions")}
        {build_chart_html(charts, "quality_heatmap", "Quality heatmap — Phase 2/3 trials scored on six methodological dimensions")}
        {build_chart_html(charts, "waterfall_chart", "Trial quality ranking — composite methodology scores")}
        {build_chart_html(charts, "bubble_chart", "Bubble chart — trial quality vs pipeline maturity (bubble = enrollment)")}
        {build_chart_html(charts, "risk_return_matrix", "Risk-return matrix — scientific validation vs commercial potential")}
        {build_chart_html(charts, "endpoint_heatmap", "Primary endpoint frequency — most-used endpoints across trials")}
      </div>
    </div>
  </div>

  <!-- SECTION 4: MARKET SIZING -->
  <div class="section">
    <div class="section-header">
      <div class="section-number">4</div>
      <div class="section-title">Market Sizing &amp; Commercial Opportunity</div>
    </div>
    <div class="section-body">
      <div class="content">{market_html}</div>
    </div>
  </div>

  <!-- SECTION 5: PRICING & REIMBURSEMENT -->
  <div class="section">
    <div class="section-header">
      <div class="section-number">5</div>
      <div class="section-title">Pricing &amp; Reimbursement</div>
    </div>
    <div class="section-body">
      <div class="content">{pricing_html}</div>
    </div>
  </div>

  <!-- SECTION 6: PATIENT STRATIFICATION -->
  <div class="section">
    <div class="section-header">
      <div class="section-number">6</div>
      <div class="section-title">Patient Stratification &amp; Biomarker Landscape</div>
    </div>
    <div class="section-body">
      <div class="content">{strat_html}</div>
    </div>
  </div>

  <!-- SECTION 7: MOA LANDSCAPE -->
  <div class="section">
    <div class="section-header">
      <div class="section-number">7</div>
      <div class="section-title">Mechanism of Action Landscape</div>
    </div>
    <div class="section-body">
      <div class="content">{moa_html}</div>
    </div>
  </div>

  <!-- SECTION 8: CRITICAL TRIAL ANALYSIS -->
  <div class="section">
    <div class="section-header">
      <div class="section-number">8</div>
      <div class="section-title">Critical Trial Analysis</div>
    </div>
    <div class="section-body">
      <div class="content">{critique_html}</div>
    </div>
  </div>

  <!-- SECTION 9: LONG-TERM SAFETY & DURABILITY -->
  <div class="section">
    <div class="section-header">
      <div class="section-number">9</div>
      <div class="section-title">Long-term Safety &amp; Durability</div>
    </div>
    <div class="section-body">
      <div class="content">{safety_html}</div>
    </div>
  </div>

  <!-- SECTION 10: PIPELINE & REGULATORY -->
  <div class="section">
    <div class="section-header">
      <div class="section-number">10</div>
      <div class="section-title">Pipeline &amp; Regulatory Landscape</div>
    </div>
    <div class="section-body">
      <div class="content">{pipeline_html}</div>
    </div>
  </div>

  <!-- SECTION 11: COMPETITIVE DYNAMICS & M&A -->
  <div class="section">
    <div class="section-header">
      <div class="section-number">11</div>
      <div class="section-title">Competitive Dynamics &amp; M&amp;A Landscape</div>
    </div>
    <div class="section-body">
      <div class="content">{dynamics_html}</div>
    </div>
  </div>

  <!-- SECTION 12: INVESTMENT RECOMMENDATION -->
  <div class="section" style="border: 2px solid var(--accent); box-shadow: 0 2px 12px rgba(29,158,117,0.12);">
    <div class="section-header" style="background: linear-gradient(135deg, #F0FFF8 0%, #EEF0FF 100%); border-bottom: 1px solid var(--border);">
      <div class="section-number" style="background: var(--accent2);">12</div>
      <div class="section-title" style="color: var(--accent2);">Investment Recommendation — Invivo Partners</div>
    </div>
    <div class="section-body">
      <div class="content">{rec_html}</div>
    </div>
  </div>

  <!-- FOOTER -->
  <div class="report-footer">
    <p>This report was generated by an AI research agent and is intended for preliminary investment screening only.</p>
    <p>All findings should be independently verified before making investment decisions.</p>
    <p style="margin-top:8px">Generated {now} · {html.escape(query)} · Sources: PubMed, ClinicalTrials.gov, Semantic Scholar, OpenFDA, bioRxiv</p>
  </div>

</div>
</body>
</html>"""

    return report
