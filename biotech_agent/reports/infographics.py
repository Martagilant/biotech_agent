"""
Infographic generation: pipeline Gantt, quality heatmap, efficacy scatter,
regulatory timeline, efficacy comparison bars. All output as base64 PNG.
"""
import io
import base64
import logging
import re
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
import numpy as np

logger = logging.getLogger(__name__)

COLORS = {
    "phase1":    "#9EE8D0",
    "phase2":    "#5DCAA5",
    "phase3":    "#1D9E75",
    "phase4":    "#0F6E56",
    "approved":  "#3C3489",
    "completed": "#888780",
    "recruiting":"#378ADD",
    "active":    "#185FA5",
    "unknown":   "#B4B2A9",
    "red":       "#E24B4A",
    "amber":     "#EF9F27",
    "green":     "#639922",
    "text":      "#2C2C2A",
    "subtext":   "#5F5E5A",
    "border":    "#D3D1C7",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "axes.grid": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "text.color": COLORS["text"],
    "axes.labelcolor": COLORS["text"],
    "xtick.color": COLORS["subtext"],
    "ytick.color": COLORS["subtext"],
})


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode()
    plt.close(fig)
    return encoded


def _phase_color(phase_str: str) -> str:
    p = phase_str.upper()
    if "3" in p or "III" in p:
        return COLORS["phase3"]
    if "2" in p or "II" in p:
        return COLORS["phase2"]
    if "1" in p or "I" in p:
        return COLORS["phase1"]
    if "4" in p or "IV" in p:
        return COLORS["phase4"]
    return COLORS["unknown"]


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    for fmt in ["%Y-%m-%d", "%B %d, %Y", "%Y-%m", "%Y"]:
        try:
            return datetime.strptime(s[:len(fmt)], fmt)
        except Exception:
            continue
    return None


def generate_pipeline_gantt(trials: list[dict], query: str) -> str:
    """Horizontal Gantt chart of Phase 2/3 trials by start-completion date."""
    # Filter to trials with phase and date info
    valid = []
    for t in trials:
        phase = t.get("phase", "N/A")
        start = _parse_date(t.get("start_date", ""))
        end = _parse_date(t.get("completion_date", ""))
        if not start:
            continue
        if not end or end <= start:
            end = datetime(start.year + 3, start.month, 1)
        label = t.get("title", "")[:45] + ("…" if len(t.get("title","")) > 45 else "")
        nct = t.get("nct_id", "")
        valid.append({"label": f"{nct}: {label}", "start": start, "end": end, "phase": phase, "status": t.get("status","")})

    if not valid:
        # Return placeholder
        fig, ax = plt.subplots(figsize=(10, 2))
        ax.text(0.5, 0.5, "No trial timeline data available", ha="center", va="center", fontsize=12, color=COLORS["subtext"])
        ax.axis("off")
        ax.set_title(f"Pipeline Timeline: {query}", fontsize=13, fontweight="bold", color=COLORS["text"], pad=10)
        return _fig_to_base64(fig)

    # Sort by phase then start date
    def phase_order(p):
        p = p.upper()
        if "3" in p: return 0
        if "2" in p: return 1
        if "4" in p: return 2
        return 3
    valid.sort(key=lambda x: (phase_order(x["phase"]), x["start"]))
    valid = valid[:20]

    fig_h = max(4, len(valid) * 0.45 + 2)
    fig, ax = plt.subplots(figsize=(12, fig_h))

    today = datetime.now()
    min_date = min(v["start"] for v in valid)
    max_date = max(v["end"] for v in valid)

    for i, trial in enumerate(valid):
        color = _phase_color(trial["phase"])
        start_num = mdates.date2num(trial["start"])
        end_num = mdates.date2num(trial["end"])
        ax.barh(i, end_num - start_num, left=start_num, height=0.6,
                color=color, alpha=0.85, linewidth=0)

    # Today line
    ax.axvline(mdates.date2num(today), color=COLORS["red"], linewidth=1.2, linestyle="--", alpha=0.7, label="Today")

    ax.set_yticks(range(len(valid)))
    ax.set_yticklabels([v["label"] for v in valid], fontsize=7.5)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.tick_params(axis="x", labelsize=9)
    ax.set_xlim(mdates.date2num(min_date) - 90, mdates.date2num(max_date) + 90)
    ax.invert_yaxis()

    # Legend
    legend_patches = [
        mpatches.Patch(color=COLORS["phase3"], label="Phase 3"),
        mpatches.Patch(color=COLORS["phase2"], label="Phase 2"),
        mpatches.Patch(color=COLORS["phase1"], label="Phase 1"),
        mpatches.Patch(color=COLORS["unknown"], label="Other"),
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=8, frameon=False)
    ax.set_title(f"Clinical Pipeline Timeline: {query}", fontsize=13, fontweight="bold",
                 color=COLORS["text"], pad=12, loc="left")
    ax.spines["bottom"].set_color(COLORS["border"])
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_trial_quality_heatmap(trials: list[dict], query: str) -> str:
    """Heatmap: trials × quality dimensions, scored 1-3."""
    dimensions = ["Randomization", "Blinding", "Sample size", "Active comparator", "Endpoint quality", "Regulatory grade"]
    # Use Phase 2/3 trials
    key_trials = [t for t in trials if any(p in t.get("phase","") for p in ["2","3","II","III"])][:12]
    if not key_trials:
        key_trials = trials[:8]

    if not key_trials:
        fig, ax = plt.subplots(figsize=(10, 2))
        ax.text(0.5, 0.5, "No trial quality data available", ha="center", va="center", fontsize=12, color=COLORS["subtext"])
        ax.axis("off")
        ax.set_title(f"Trial Quality Heatmap: {query}", fontsize=13, fontweight="bold", color=COLORS["text"])
        return _fig_to_base64(fig)

    # Score heuristically from available metadata
    scores = []
    labels = []
    for trial in key_trials:
        phase = trial.get("phase", "")
        enrollment = trial.get("enrollment", 0)
        try:
            n = int(str(enrollment).replace(",", "")) if enrollment not in ("N/A", None, "") else 0
        except Exception:
            n = 0
        status = trial.get("status", "").upper()
        interventions = trial.get("interventions", [])
        outcomes = trial.get("primary_outcomes", [])

        rand_score = 3 if "PHASE3" in phase.upper() or "PHASE 3" in phase.upper() else (2 if "PHASE2" in phase.upper() or "PHASE 2" in phase.upper() else 1)
        blind_score = 3 if "PHASE3" in phase.upper() or "PHASE 3" in phase.upper() else 2
        sample_score = 3 if n >= 200 else (2 if n >= 50 else (1 if n > 0 else 1))
        # Check if placebo is in interventions
        has_placebo = any("placebo" in str(i).lower() for i in interventions)
        comparator_score = 3 if has_placebo else 2
        endpoint_score = 3 if any(kw in " ".join(outcomes).lower() for kw in ["survival", "mortality", "remission", "response rate", "progression"]) else 2
        reg_score = 3 if "PHASE3" in phase.upper() or "PHASE 3" in phase.upper() else (2 if "PHASE2" in phase.upper() or "PHASE 2" in phase.upper() else 1)

        scores.append([rand_score, blind_score, sample_score, comparator_score, endpoint_score, reg_score])
        nct = trial.get("nct_id", "")
        title_short = trial.get("title", "")[:30] + "…" if len(trial.get("title","")) > 30 else trial.get("title","")
        labels.append(f"{nct} ({phase[:7]})")

    scores_arr = np.array(scores)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "quality", ["#F7C1C1", "#FAC775", "#C0DD97"], N=3
    )

    fig_h = max(4, len(key_trials) * 0.55 + 2.5)
    fig, ax = plt.subplots(figsize=(10, fig_h))
    im = ax.imshow(scores_arr, cmap=cmap, vmin=1, vmax=3, aspect="auto")

    ax.set_xticks(range(len(dimensions)))
    ax.set_xticklabels(dimensions, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)

    # Add text annotations
    for i in range(len(labels)):
        for j in range(len(dimensions)):
            val = scores_arr[i, j]
            label_map = {1: "Low", 2: "Med", 3: "High"}
            ax.text(j, i, label_map[val], ha="center", va="center",
                    fontsize=7.5, color=COLORS["text"], fontweight="500")

    ax.set_title(f"Trial Methodology Quality Heatmap: {query}", fontsize=12, fontweight="bold",
                 color=COLORS["text"], pad=12, loc="left")
    ax.spines[:].set_visible(False)
    ax.tick_params(length=0)

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_ticks([1, 2, 3])
    cbar.set_ticklabels(["Low", "Med", "High"])
    cbar.ax.tick_params(labelsize=8)

    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_phase_distribution(trials: list[dict], query: str) -> str:
    """Bar chart of trial counts by phase and status."""
    from collections import Counter

    phase_counts = Counter()
    status_counts = Counter()
    for t in trials:
        phase = t.get("phase", "Unknown")
        status = t.get("status", "Unknown")
        # Normalise phase
        if "3" in phase or "III" in phase:
            phase_counts["Phase 3"] += 1
        elif "2" in phase or "II" in phase:
            phase_counts["Phase 2"] += 1
        elif "1" in phase or "I" in phase:
            phase_counts["Phase 1"] += 1
        elif "4" in phase or "IV" in phase:
            phase_counts["Phase 4"] += 1
        else:
            phase_counts["Other"] += 1

        if status.upper() in ("RECRUITING", "NOT_YET_RECRUITING"):
            status_counts["Recruiting"] += 1
        elif "ACTIVE" in status.upper():
            status_counts["Active"] += 1
        elif "COMPLETED" in status.upper():
            status_counts["Completed"] += 1
        elif "TERMINATED" in status.upper():
            status_counts["Terminated"] += 1
        else:
            status_counts["Other"] += 1

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Phase distribution
    phase_order = ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Other"]
    phase_vals = [phase_counts.get(p, 0) for p in phase_order]
    phase_colors = [COLORS["phase1"], COLORS["phase2"], COLORS["phase3"], COLORS["phase4"], COLORS["unknown"]]
    bars1 = ax1.bar(phase_order, phase_vals, color=phase_colors, width=0.6, linewidth=0)
    ax1.set_title("Trials by Phase", fontsize=12, fontweight="bold", color=COLORS["text"], pad=10, loc="left")
    ax1.set_ylabel("Number of trials", fontsize=10)
    ax1.spines["left"].set_color(COLORS["border"])
    ax1.spines["bottom"].set_color(COLORS["border"])
    ax1.tick_params(axis="x", labelsize=9)
    for bar, val in zip(bars1, phase_vals):
        if val > 0:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                     str(val), ha="center", va="bottom", fontsize=10, fontweight="500")

    # Status distribution
    status_order = ["Recruiting", "Active", "Completed", "Terminated", "Other"]
    status_vals = [status_counts.get(s, 0) for s in status_order]
    status_colors = [COLORS["recruiting"], COLORS["active"], COLORS["green"], COLORS["red"], COLORS["unknown"]]
    bars2 = ax2.bar(status_order, status_vals, color=status_colors, width=0.6, linewidth=0)
    ax2.set_title("Trials by Status", fontsize=12, fontweight="bold", color=COLORS["text"], pad=10, loc="left")
    ax2.set_ylabel("Number of trials", fontsize=10)
    ax2.spines["left"].set_color(COLORS["border"])
    ax2.spines["bottom"].set_color(COLORS["border"])
    ax2.tick_params(axis="x", labelsize=9)
    for bar, val in zip(bars2, status_vals):
        if val > 0:
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                     str(val), ha="center", va="bottom", fontsize=10, fontweight="500")

    fig.suptitle(f"Clinical Trial Landscape Overview: {query}", fontsize=13, fontweight="bold",
                 color=COLORS["text"], y=1.02)
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_sponsor_chart(trials: list[dict], query: str) -> str:
    """Horizontal bar chart of top sponsors by trial count."""
    from collections import Counter
    sponsor_counts = Counter(t.get("sponsor", "Unknown") for t in trials if t.get("sponsor"))
    top = sponsor_counts.most_common(15)
    if not top:
        fig, ax = plt.subplots(figsize=(10, 2))
        ax.text(0.5, 0.5, "No sponsor data available", ha="center", va="center", fontsize=12, color=COLORS["subtext"])
        ax.axis("off")
        return _fig_to_base64(fig)

    labels = [t[0][:40] for t in top]
    vals = [t[1] for t in top]
    colors = [COLORS["phase3"] if v >= 3 else COLORS["phase2"] if v >= 2 else COLORS["phase1"] for v in vals]

    fig_h = max(4, len(labels) * 0.4 + 2)
    fig, ax = plt.subplots(figsize=(10, fig_h))
    bars = ax.barh(range(len(labels)), vals, color=colors, height=0.6, linewidth=0)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlabel("Number of trials", fontsize=10)
    ax.spines["bottom"].set_color(COLORS["border"])
    for bar, val in zip(bars, vals):
        ax.text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2,
                str(val), va="center", fontsize=9, fontweight="500")
    ax.set_title(f"Top Sponsors by Trial Count: {query}", fontsize=12, fontweight="bold",
                 color=COLORS["text"], pad=10, loc="left")
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_all_charts(trials: list[dict], query: str) -> dict[str, str]:
    """Generate all charts and return base64-encoded PNG dict."""
    charts = {}
    try:
        charts["pipeline_gantt"] = generate_pipeline_gantt(trials, query)
    except Exception as e:
        logger.warning(f"Gantt chart error: {e}")
        charts["pipeline_gantt"] = ""
    try:
        charts["quality_heatmap"] = generate_trial_quality_heatmap(trials, query)
    except Exception as e:
        logger.warning(f"Heatmap error: {e}")
        charts["quality_heatmap"] = ""
    try:
        charts["phase_distribution"] = generate_phase_distribution(trials, query)
    except Exception as e:
        logger.warning(f"Phase distribution error: {e}")
        charts["phase_distribution"] = ""
    try:
        charts["sponsor_chart"] = generate_sponsor_chart(trials, query)
    except Exception as e:
        logger.warning(f"Sponsor chart error: {e}")
        charts["sponsor_chart"] = ""
    return charts


# ── New infographics (charts 5-14) ────────────────────────────────────────────

def generate_radar_chart(trials: list[dict], query: str) -> str:
    """Radar chart: trial quality profile across 6 methodology dimensions."""
    key_trials = [t for t in trials if any(p in t.get("phase","") for p in ["2","3","II","III"])][:6]
    if not key_trials:
        key_trials = trials[:4]
    if not key_trials:
        fig, ax = plt.subplots(figsize=(6,4))
        ax.text(0.5,0.5,"No trial data for radar chart",ha="center",va="center",fontsize=11,color=COLORS["subtext"])
        ax.axis("off"); return _fig_to_base64(fig)

    dimensions = ["Randomisation","Blinding","Sample size","Active comparator","Endpoint quality","Regulatory grade"]
    fig, ax = plt.subplots(figsize=(8,7), subplot_kw=dict(polar=True))
    angles = [n / float(len(dimensions)) * 2 * 3.14159 for n in range(len(dimensions))]
    angles += angles[:1]
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dimensions, size=9, color=COLORS["text"])
    ax.set_ylim(0,5)
    ax.set_yticks([1,2,3,4,5]); ax.set_yticklabels(["1","2","3","4","5"],size=7,color=COLORS["subtext"])
    ax.grid(color=COLORS["border"], linewidth=0.5)

    palette = [COLORS["phase3"],COLORS["phase2"],COLORS["phase1"],COLORS["phase4"],COLORS["active"],COLORS["recruiting"]]
    for idx, trial in enumerate(key_trials[:6]):
        phase = trial.get("phase","")
        try: n = int(str(trial.get("enrollment",0)).replace(",",""))
        except: n = 0
        interventions = trial.get("interventions",[])
        outcomes = trial.get("primary_outcomes",[])

        s_rand  = 3 if "3" in phase or "III" in phase else 2
        s_blind = 3 if "3" in phase or "III" in phase else 2
        s_size  = 3 if n>=300 else (2 if n>=100 else 1)
        s_comp  = 3 if any("placebo" in str(i).lower() for i in interventions) else 2
        s_end   = 3 if any(kw in " ".join(outcomes).lower() for kw in ["survival","remission","response rate","progression"]) else 2
        s_reg   = 3 if "3" in phase or "III" in phase else (2 if "2" in phase or "II" in phase else 1)

        vals = [s_rand,s_blind,s_size,s_comp,s_end,s_reg]
        vals += vals[:1]
        color = palette[idx % len(palette)]
        ax.plot(angles, vals, color=color, linewidth=1.5)
        ax.fill(angles, vals, color=color, alpha=0.08)

    nct = trial.get("nct_id","")
    ax.set_title(f"Trial quality profiles: {query[:40]}", size=11, fontweight="bold",
                 color=COLORS["text"], pad=20)
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_bubble_chart(trials: list[dict], query: str) -> str:
    """Bubble chart: efficacy proxy vs status quality vs enrollment size."""
    if not trials:
        fig, ax = plt.subplots(figsize=(9,5))
        ax.text(0.5,0.5,"No data",ha="center",va="center",fontsize=11,color=COLORS["subtext"])
        ax.axis("off"); return _fig_to_base64(fig)

    fig, ax = plt.subplots(figsize=(10,6))
    for t in trials[:12]:
        try: n = int(str(t.get("enrollment","0")).replace(",",""))
        except: n = 50
        phase = t.get("phase","")
        status = t.get("status","").upper()

        # Proxy x = methodology quality score (0-100)
        q = 0
        if "3" in phase or "III" in phase: q += 40
        elif "2" in phase or "II" in phase: q += 20
        if any("placebo" in str(i).lower() for i in t.get("interventions",[])):q+=20
        if n>=300: q+=25
        elif n>=100: q+=15
        outcomes_text = " ".join(t.get("primary_outcomes",[]))
        if any(kw in outcomes_text.lower() for kw in ["survival","mortality","remission"]): q+=15

        # Proxy y = pipeline maturity (later phase = higher)
        y = 80 if "COMPLET" in status else (60 if "ACTIVE" in status else (40 if "RECRUIT" in status else 20))
        y += np.random.uniform(-8,8)
        q += np.random.uniform(-5,5)

        color = _phase_color(phase)
        size  = max(30, min(400, n // 5))
        ax.scatter(q, y, s=size, color=color, alpha=0.7, linewidths=0.8, edgecolors=color)

        label = t.get("nct_id","")[:11]
        ax.annotate(label, (q,y), textcoords="offset points", xytext=(5,4),
                    fontsize=7, color=COLORS["subtext"])

    ax.set_xlabel("Trial methodology quality score (randomisation, comparator, power)", fontsize=9, color=COLORS["subtext"])
    ax.set_ylabel("Pipeline maturity (status)", fontsize=9, color=COLORS["subtext"])
    ax.set_title(f"Trial quality vs maturity — {query[:40]}", fontsize=11, fontweight="bold",
                 color=COLORS["text"], pad=10, loc="left")
    ax.spines["left"].set_color(COLORS["border"]); ax.spines["bottom"].set_color(COLORS["border"])

    legend_patches = [
        mpatches.Patch(color=COLORS["phase3"],label="Phase 3"),
        mpatches.Patch(color=COLORS["phase2"],label="Phase 2"),
        mpatches.Patch(color=COLORS["phase1"],label="Phase 1/other"),
    ]
    ax.legend(handles=legend_patches, fontsize=8, frameon=False, loc="lower right")
    ax.text(0.98,0.98,"Bubble size = enrollment",transform=ax.transAxes,fontsize=7,
            ha="right",va="top",color=COLORS["subtext"])
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_regulatory_swimlane(trials: list[dict], fda_docs: list[dict], query: str) -> str:
    """Regulatory pathway swimlane showing each asset's FDA/EMA stage."""
    stages = ["Phase 1","Phase 2","Phase 3","NDA/BLA","PDUFA","Approved"]

    assets = []
    for d in fda_docs[:4]:
        name = d.get("metadata",{}).get("brand_names",["?"])[0]
        assets.append({"name": name[:18], "stage": 5, "color": COLORS["phase3"], "detail":"FDA approved"})

    for t in trials[:10]:
        phase = t.get("phase","")
        status = t.get("status","").upper()
        if "3" in phase or "III" in phase:
            stage = 3 if "COMPLET" in status else 2
        elif "2" in phase or "II" in phase:
            stage = 1
        else:
            stage = 0
        name = t.get("nct_id","")[:11]
        completion = t.get("completion_date","")[:7]
        assets.append({"name":name,"stage":stage,"color":_phase_color(phase),"detail":completion})

    if not assets:
        fig, ax = plt.subplots(figsize=(10,2))
        ax.text(0.5,0.5,"No data",ha="center",va="center",fontsize=11,color=COLORS["subtext"])
        ax.axis("off"); return _fig_to_base64(fig)

    fig_h = max(3, len(assets)*0.55 + 2)
    fig, ax = plt.subplots(figsize=(12, fig_h))

    for s, stage_name in enumerate(stages):
        ax.text(s*2+0.5, len(assets)+0.3, stage_name, ha="center", va="bottom",
                fontsize=8, fontweight="bold", color=COLORS["subtext"])
        ax.axvline(s*2, color=COLORS["border"], linewidth=0.5, linestyle="--", alpha=0.5)

    for i, asset in enumerate(assets):
        y = len(assets) - i - 0.5
        stage_x = asset["stage"] * 2
        ax.barh(y, stage_x + 1.6, height=0.5, left=0, color=asset["color"], alpha=0.25, linewidth=0)
        ax.barh(y, 1.5, height=0.5, left=stage_x, color=asset["color"], alpha=0.85, linewidth=0)
        ax.text(-0.1, y, asset["name"], va="center", ha="right", fontsize=8, color=COLORS["text"])
        ax.text(stage_x+0.75, y, asset["detail"], va="center", ha="center", fontsize=6.5, color="white", fontweight="bold")

    ax.set_xlim(-3.5, len(stages)*2 + 0.5)
    ax.set_ylim(0, len(assets))
    ax.axis("off")
    ax.set_title(f"Regulatory pathway — {query[:40]}", fontsize=11, fontweight="bold",
                 color=COLORS["text"], pad=8, loc="left")
    try:
        fig.tight_layout()
    except Exception:
        pass
    return _fig_to_base64(fig)


def generate_waterfall_chart(trials: list[dict], query: str) -> str:
    """Waterfall: relative trial quality scores as ranked bars."""
    if not trials:
        fig, ax = plt.subplots(figsize=(9,4))
        ax.text(0.5,0.5,"No data",ha="center",va="center",fontsize=11,color=COLORS["subtext"])
        ax.axis("off"); return _fig_to_base64(fig)

    scored = []
    for t in trials:
        phase = t.get("phase","")
        try: n = int(str(t.get("enrollment","0")).replace(",",""))
        except: n = 0
        interventions = t.get("interventions",[])
        outcomes = t.get("primary_outcomes",[])
        score = 0
        if "3" in phase or "III" in phase: score += 40
        elif "2" in phase or "II" in phase: score += 20
        if n>=500: score+=25
        elif n>=200: score+=15
        elif n>=50: score+=8
        if any("placebo" in str(i).lower() for i in interventions): score+=15
        if any(kw in " ".join(outcomes).lower() for kw in ["survival","remission","response"]): score+=15
        if "COMPLET" in t.get("status","").upper(): score+=5
        scored.append({"id": t.get("nct_id","?")[:11], "score": score, "phase": phase})

    scored.sort(key=lambda x: x["score"], reverse=True)
    labels = [s["id"] for s in scored[:12]]
    values = [s["score"] for s in scored[:12]]
    colors = [_phase_color(s["phase"]) for s in scored[:12]]

    fig_w = max(8, len(labels)*0.9)
    fig, ax = plt.subplots(figsize=(fig_w, 5))
    bars = ax.bar(range(len(labels)), values, color=colors, width=0.7, linewidth=0)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("Composite methodology quality score", fontsize=9, color=COLORS["subtext"])
    ax.spines["left"].set_color(COLORS["border"]); ax.spines["bottom"].set_color(COLORS["border"])
    for bar, val in zip(bars, values):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.5, str(val),
                ha="center", va="bottom", fontsize=8, fontweight="500", color=COLORS["text"])
    ax.set_title(f"Trial quality ranking — {query[:40]}", fontsize=11, fontweight="bold",
                 color=COLORS["text"], pad=10, loc="left")
    legend_patches = [mpatches.Patch(color=COLORS["phase3"],label="Phase 3"),
                      mpatches.Patch(color=COLORS["phase2"],label="Phase 2"),
                      mpatches.Patch(color=COLORS["phase1"],label="Phase 1")]
    ax.legend(handles=legend_patches, fontsize=8, frameon=False)
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_funnel_chart(trials: list[dict], fda_docs: list[dict], query: str) -> str:
    """Pipeline stage funnel — asset counts per development stage."""
    from collections import Counter
    stage_counts = Counter()
    for t in trials:
        p = t.get("phase","").upper()
        if "3" in p or "III" in p: stage_counts["Phase 3"] += 1
        elif "2" in p or "II" in p: stage_counts["Phase 2"] += 1
        elif "1" in p or "I" in p:  stage_counts["Phase 1"] += 1
        else: stage_counts["Other"] += 1
    stage_counts["Approved"] = len(fda_docs)

    stages = ["Phase 1","Phase 2","Phase 3","Approved"]
    counts = [stage_counts.get(s,0) for s in stages]
    if sum(counts) == 0:
        fig, ax = plt.subplots(figsize=(8,3))
        ax.text(0.5,0.5,"No pipeline data",ha="center",va="center",fontsize=11,color=COLORS["subtext"])
        ax.axis("off"); return _fig_to_base64(fig)

    max_count = max(counts) or 1
    stage_colors = [COLORS["phase1"],COLORS["phase2"],COLORS["phase3"],COLORS["phase4"]]
    fig, ax = plt.subplots(figsize=(10, len(stages)*0.9 + 1.5))

    for i, (stage, count, color) in enumerate(zip(stages, counts, stage_colors)):
        width = 0.3 + 0.7 * (count / max_count)
        x_start = (1 - width) / 2
        bar = mpatches.FancyBboxPatch((x_start, i*1.1), width, 0.8,
                                       boxstyle="round,pad=0.02", linewidth=0,
                                       facecolor=color, alpha=0.85)
        ax.add_patch(bar)
        ax.text(0.5, i*1.1+0.4, f"{stage}  ({count} asset{'s' if count!=1 else ''})",
                ha="center", va="center", fontsize=10, fontweight="500",
                color=COLORS["text"])

    ax.set_xlim(0,1); ax.set_ylim(-0.2, len(stages)*1.1+0.3)
    ax.axis("off")
    ax.set_title(f"Pipeline funnel — {query[:40]}", fontsize=11, fontweight="bold",
                 color=COLORS["text"], pad=10, loc="left")
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_moa_chart(trials: list[dict], query: str) -> str:
    """MOA diversity: unique intervention types grouped and counted."""
    from collections import Counter
    all_interventions = []
    for t in trials:
        all_interventions.extend(t.get("interventions",[]))

    if not all_interventions:
        fig, ax = plt.subplots(figsize=(8,3))
        ax.text(0.5,0.5,"No intervention data",ha="center",va="center",fontsize=11,color=COLORS["subtext"])
        ax.axis("off"); return _fig_to_base64(fig)

    # Categorise by mechanism keywords
    moa_buckets = {
        "Antibody / biologic": ["mg","mcg","antibody","mab","zumab","lumab","tuzumab","ximab","mumab"],
        "Small molecule / oral": ["mg oral","mg bid","mg qd","mg daily","pill","tablet","capsule"],
        "Gene therapy": ["aav","lentiviral","crispr","gene therapy","autotemcel"],
        "Cell therapy": ["car-t","cart","cell therapy","autologous","allogeneic"],
        "Device / other": ["device","ttfields","fields","radiation","surgery"],
    }
    bucket_counts = Counter()
    for iv in all_interventions:
        iv_l = iv.lower()
        matched = False
        for bucket, keywords in moa_buckets.items():
            if any(kw in iv_l for kw in keywords):
                bucket_counts[bucket] += 1
                matched = True
                break
        if not matched:
            bucket_counts["Other"] += 1

    labels = list(bucket_counts.keys())
    values = list(bucket_counts.values())
    colors_list = [COLORS["phase3"],COLORS["phase2"],COLORS["phase1"],
                   COLORS["active"],COLORS["recruiting"],COLORS["unknown"]][:len(labels)]

    fig, ax = plt.subplots(figsize=(9, max(3, len(labels)*0.55+2)))
    bars = ax.barh(labels, values, color=colors_list, height=0.6, linewidth=0)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width()+0.05, bar.get_y()+bar.get_height()/2,
                str(val), va="center", fontsize=9, fontweight="500")
    ax.spines["bottom"].set_color(COLORS["border"])
    ax.set_xlabel("Number of trial arms / interventions", fontsize=9)
    ax.set_title(f"Mechanism of action diversity — {query[:40]}", fontsize=11, fontweight="bold",
                 color=COLORS["text"], pad=10, loc="left")
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_binary_events_timeline(trials: list[dict], query: str) -> str:
    """Timeline of trial completions — recent readouts and upcoming catalysts."""
    from datetime import datetime
    now = datetime.now()
    events = []
    for t in trials:
        cd = t.get("completion_date","")
        if not cd: continue
        try:
            dt = datetime.strptime(cd[:7], "%Y-%m")
            months_offset = (dt.year-now.year)*12 + (dt.month-now.month)
            # Include events within ±36 months of today
            if -36 <= months_offset <= 48:
                events.append({
                    "label": t.get("nct_id","")[:11],
                    "title": t.get("title","")[:45]+"…",
                    "phase": t.get("phase",""),
                    "date": dt,
                    "months": months_offset,
                    "past": months_offset < 0,
                })
        except: pass

    events.sort(key=lambda x: x["date"])
    upcoming = events[:16]

    if not upcoming:
        # Last resort: just plot all trials with any dates
        for t in trials[:8]:
            cd = t.get("completion_date","") or t.get("start_date","")
            if cd:
                try:
                    dt = datetime.strptime(cd[:7], "%Y-%m")
                    months_offset = (dt.year-now.year)*12 + (dt.month-now.month)
                    upcoming.append({"label": t.get("nct_id","")[:11], "title": t.get("title","")[:45],
                                     "phase": t.get("phase",""), "date": dt, "months": months_offset, "past": months_offset < 0})
                except: pass
        upcoming.sort(key=lambda x: x["date"])

    if not upcoming:
        fig, ax = plt.subplots(figsize=(10,2))
        ax.text(0.5,0.5,"No trial timeline data available",ha="center",va="center",fontsize=11,color=COLORS["subtext"])
        ax.axis("off"); return _fig_to_base64(fig)

    fig_h = max(3, len(upcoming)*0.5+2)
    fig, ax = plt.subplots(figsize=(12, fig_h))

    colors_urgency = {0:COLORS["red"],1:COLORS["amber"],2:COLORS["phase2"],3:COLORS["phase3"]}
    for i, ev in enumerate(upcoming):
        urgency = 0 if ev["months"]<=6 else (1 if ev["months"]<=12 else (2 if ev["months"]<=18 else 3))
        color = _phase_color(ev["phase"])
        ax.barh(i, ev["months"], height=0.5, color=color, alpha=0.75, linewidth=0)
        ax.text(-0.3, i, ev["label"], va="center", ha="right", fontsize=8, color=COLORS["text"])
        ax.text(ev["months"]+0.3, i, ev["date"].strftime("%b %Y"), va="center", ha="left", fontsize=7.5, color=COLORS["subtext"])

    ax.set_xlabel("Months from today to estimated completion", fontsize=9, color=COLORS["subtext"])
    ax.set_xlim(-6, max(ev["months"] for ev in upcoming)+8)
    ax.set_ylim(-0.5, len(upcoming))
    ax.set_yticks([])
    ax.axvline(0, color=COLORS["red"], linewidth=1.5, linestyle="--", alpha=0.6)
    ax.spines["bottom"].set_color(COLORS["border"])
    ax.set_title(f"Binary events calendar — {query[:40]}", fontsize=11, fontweight="bold",
                 color=COLORS["text"], pad=10, loc="left")
    legend_patches = [mpatches.Patch(color=COLORS["phase3"],label="Phase 3"),
                      mpatches.Patch(color=COLORS["phase2"],label="Phase 2"),
                      mpatches.Patch(color=COLORS["phase1"],label="Phase 1")]
    ax.legend(handles=legend_patches, fontsize=8, frameon=False, loc="lower right")
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_enrollment_trend(trials: list[dict], query: str) -> str:
    """Enrollment trend: cumulative patients per year across all trials."""
    from collections import defaultdict
    from datetime import datetime
    yearly = defaultdict(int)
    for t in trials:
        sd = t.get("start_date","")
        try:
            year = int(sd[:4])
            try: n = int(str(t.get("enrollment","0")).replace(",",""))
            except: n = 0
            if 2010 <= year <= 2027:
                yearly[year] += n
        except: pass

    if not yearly:
        fig, ax = plt.subplots(figsize=(9,4))
        ax.text(0.5,0.5,"No enrollment data",ha="center",va="center",fontsize=11,color=COLORS["subtext"])
        ax.axis("off"); return _fig_to_base64(fig)

    years = sorted(yearly.keys())
    cumulative = []
    total = 0
    for y in years:
        total += yearly[y]
        cumulative.append(total)

    fig, ax = plt.subplots(figsize=(10,5))
    ax.fill_between(years, cumulative, alpha=0.15, color=COLORS["phase3"])
    ax.plot(years, cumulative, color=COLORS["phase3"], linewidth=2.5, marker="o", markersize=5)
    for y, c in zip(years, cumulative):
        ax.annotate(f"{c:,}", (y,c), textcoords="offset points", xytext=(0,8),
                    ha="center", fontsize=8, color=COLORS["subtext"])
    ax.set_xlabel("Year trial started", fontsize=9, color=COLORS["subtext"])
    ax.set_ylabel("Cumulative patients enrolled", fontsize=9, color=COLORS["subtext"])
    ax.spines["left"].set_color(COLORS["border"]); ax.spines["bottom"].set_color(COLORS["border"])
    ax.set_title(f"Cumulative enrollment over time — {query[:40]}", fontsize=11, fontweight="bold",
                 color=COLORS["text"], pad=10, loc="left")
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_risk_return_matrix(trials: list[dict], fda_docs: list[dict], query: str) -> str:
    """Risk-return 2x2 scatter: scientific risk vs commercial potential."""
    if not trials and not fda_docs:
        fig, ax = plt.subplots(figsize=(7,5))
        ax.text(0.5,0.5,"No data",ha="center",va="center",fontsize=11,color=COLORS["subtext"])
        ax.axis("off"); return _fig_to_base64(fig)

    fig, ax = plt.subplots(figsize=(9,7))
    np.random.seed(42)

    for t in trials[:10]:
        phase = t.get("phase","")
        try: n = int(str(t.get("enrollment","0")).replace(",",""))
        except: n = 0
        interventions = t.get("interventions",[])
        outcomes = t.get("primary_outcomes",[])

        # X = scientific validation (0=early,100=validated)
        x = 10
        if "3" in phase or "III" in phase: x += 55
        elif "2" in phase or "II" in phase: x += 30
        if any("placebo" in str(i).lower() for i in interventions): x += 15
        if "COMPLET" in t.get("status","").upper(): x += 15
        x = min(95, x + np.random.uniform(-5,5))

        # Y = commercial potential proxy
        y = 20
        if n >= 1000: y += 50
        elif n >= 300: y += 35
        elif n >= 100: y += 20
        if any(kw in " ".join(outcomes).lower() for kw in ["survival","mortality"]): y += 20
        y = min(95, y + np.random.uniform(-8,8))

        color = _phase_color(phase)
        ax.scatter(x, y, s=180, color=color, alpha=0.75, zorder=5, linewidths=0.8, edgecolors=color)
        ax.annotate(t.get("nct_id","")[:11], (x,y), textcoords="offset points",
                    xytext=(5,4), fontsize=7.5, color=COLORS["subtext"])

    for d in fda_docs[:4]:
        name = d.get("metadata",{}).get("brand_names",["?"])[0][:10]
        x = 85 + np.random.uniform(-5,5)
        y = 70 + np.random.uniform(-10,10)
        ax.scatter(x, y, s=220, color=COLORS["phase4"], alpha=0.9, zorder=5,
                   marker="*", linewidths=0.5, edgecolors=COLORS["phase4"])
        ax.annotate(name, (x,y), textcoords="offset points", xytext=(5,4),
                    fontsize=7.5, color=COLORS["subtext"])

    ax.axvline(50, color=COLORS["border"], linewidth=0.8, linestyle="--")
    ax.axhline(50, color=COLORS["border"], linewidth=0.8, linestyle="--")
    ax.text(2, 95, "High risk\nHigh upside", fontsize=8, color=COLORS["subtext"], va="top")
    ax.text(52, 95, "Validated\nBlockbuster zone", fontsize=8, color=COLORS["subtext"], va="top")
    ax.text(2, 8, "High risk\nNiche", fontsize=8, color=COLORS["subtext"])
    ax.text(52, 8, "Validated\nNiche", fontsize=8, color=COLORS["subtext"])

    ax.set_xlabel("Scientific validation (early → validated)", fontsize=9, color=COLORS["subtext"])
    ax.set_ylabel("Commercial potential proxy", fontsize=9, color=COLORS["subtext"])
    ax.set_xlim(0,100); ax.set_ylim(0,100)
    ax.spines["left"].set_color(COLORS["border"]); ax.spines["bottom"].set_color(COLORS["border"])
    ax.set_title(f"Risk-return matrix — {query[:40]}", fontsize=11, fontweight="bold",
                 color=COLORS["text"], pad=10, loc="left")
    legend_patches = [mpatches.Patch(color=COLORS["phase3"],label="Phase 3"),
                      mpatches.Patch(color=COLORS["phase2"],label="Phase 2"),
                      mpatches.Patch(color=COLORS["phase4"],label="Approved ★")]
    ax.legend(handles=legend_patches, fontsize=8, frameon=False, loc="lower right")
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_endpoint_heatmap(trials: list[dict], query: str) -> str:
    """Endpoint usage heatmap: which endpoints appear across trials."""
    from collections import Counter
    endpoint_counter = Counter()
    for t in trials:
        for o in t.get("primary_outcomes",[]):
            o_short = o[:40]
            endpoint_counter[o_short] += 1

    if not endpoint_counter:
        fig, ax = plt.subplots(figsize=(8,3))
        ax.text(0.5,0.5,"No endpoint data",ha="center",va="center",fontsize=11,color=COLORS["subtext"])
        ax.axis("off"); return _fig_to_base64(fig)

    top_endpoints = endpoint_counter.most_common(12)
    labels = [e[0][:38] for e in top_endpoints]
    values = [e[1] for e in top_endpoints]
    colors_ep = [COLORS["phase3"] if v>=3 else (COLORS["phase2"] if v>=2 else COLORS["phase1"]) for v in values]

    fig_h = max(3, len(labels)*0.45+1.5)
    fig, ax = plt.subplots(figsize=(10, fig_h))
    bars = ax.barh(range(len(labels)), values, color=colors_ep, height=0.6, linewidth=0)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Number of trials using this endpoint", fontsize=9)
    ax.spines["bottom"].set_color(COLORS["border"])
    for bar, val in zip(bars, values):
        ax.text(bar.get_width()+0.05, bar.get_y()+bar.get_height()/2,
                str(val), va="center", fontsize=9, fontweight="500")
    ax.set_title(f"Primary endpoint frequency — {query[:40]}", fontsize=11, fontweight="bold",
                 color=COLORS["text"], pad=10, loc="left")
    fig.tight_layout()
    return _fig_to_base64(fig)


def generate_all_charts(trials: list[dict], query: str, fda_docs: list[dict] = None) -> dict[str, str]:
    """Generate all charts and return base64-encoded PNG dict."""
    if fda_docs is None:
        fda_docs = []
    charts = {}
    generators = {
        "pipeline_gantt":        lambda: generate_pipeline_gantt(trials, query),
        "quality_heatmap":       lambda: generate_trial_quality_heatmap(trials, query),
        "phase_distribution":    lambda: generate_phase_distribution(trials, query),
        "sponsor_chart":         lambda: generate_sponsor_chart(trials, query),
        "radar_chart":           lambda: generate_radar_chart(trials, query),
        "bubble_chart":          lambda: generate_bubble_chart(trials, query),
        "regulatory_swimlane":   lambda: generate_regulatory_swimlane(trials, fda_docs, query),
        "waterfall_chart":       lambda: generate_waterfall_chart(trials, query),
        "funnel_chart":          lambda: generate_funnel_chart(trials, fda_docs, query),
        "moa_chart":             lambda: generate_moa_chart(trials, query),
        "binary_events":         lambda: generate_binary_events_timeline(trials, query),
        "enrollment_trend":      lambda: generate_enrollment_trend(trials, query),
        "risk_return_matrix":    lambda: generate_risk_return_matrix(trials, fda_docs, query),
        "endpoint_heatmap":      lambda: generate_endpoint_heatmap(trials, query),
    }
    for name, fn in generators.items():
        try:
            charts[name] = fn()
        except Exception as e:
            logger.warning(f"Chart '{name}' error: {e}")
            charts[name] = ""
    return charts
