"""
LangGraph research agent — investment-grade output.

Fixes applied from VC critique:
1. Market sizing node — TAM/SAM/patient funnel/revenue ceiling
2. Pricing & reimbursement node — payor dynamics, biosimilar timelines, rebate pressure
3. Patient stratification node — biomarker landscape, subpopulations, unmet need
4. MOA landscape node — mechanistic grouping table, true competitive map (no garbled data)
5. Long-term safety node — 2-5yr surveillance, durability, discontinuation rates
6. Competitive dynamics node — franchise logic, BD motivations, acquirer landscape
7. Investment recommendation node — named asset, specific catalyst, clear pass/proceed
8. Boilerplate removal — all disease-specific copy, no Alzheimer carry-over into AD reports
9. Trial critique — asset-specific differential analysis, not identical checkbox text
"""
import json
import logging
import os
import operator
from typing import TypedDict, Annotated
from datetime import datetime

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


# ─── State schema ─────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    # Input
    query: str
    query_terms: list
    mesh_terms: list
    icd_codes: list
    # Retrieval
    all_documents: list
    clinical_trials: list
    fda_docs: list
    pubmed_docs: list
    # Core nodes (existing)
    scientific_summary: str
    trial_landscape: str
    trial_landscape_structured: list
    trial_critique: str
    pipeline_regulatory: str
    competitive_landscape: str
    investor_narrative: str
    # New analytical nodes
    market_sizing: str
    pricing_reimbursement: str
    patient_stratification: str
    moa_landscape: str
    long_term_safety: str
    competitive_dynamics: str
    investment_recommendation: str
    # Tracking
    progress_log: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]


# ─── LLM helper ───────────────────────────────────────────────────────────────

def _get_llm(temperature: float = 0.2):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    try:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-sonnet-4-5",
            temperature=temperature,
            max_tokens=4096,
            anthropic_api_key=api_key,
        )
    except Exception as e:
        logger.warning(f"LLM init failed: {e}")
        return None


def _llm_call(llm, system: str, prompt: str) -> str | None:
    if llm is None:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        return response.content
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
        return None


# ─── Disease intelligence helper ─────────────────────────────────────────────

def _get_intel(query: str) -> dict:
    """Fetch disease-specific investment intelligence from mock_data."""
    try:
        import sys
        sys.path.insert(0, ".")
        from retrievers.mock_data import get_disease_intel, _match_disease
        matched = _match_disease(query)
        return get_disease_intel(matched) if matched else {}
    except Exception:
        return {}


def _fmt_usd(val) -> str:
    if val is None:
        return "Not available"
    if val >= 1:
        return f"${val:.1f}B"
    return f"${val*1000:.0f}M"


def _fmt_patients(val) -> str:
    if val is None:
        return "Not available"
    if val >= 1:
        return f"{val:.1f}M"
    return f"{val*1000:.0f}K"


# ─── Static synthesis helpers ─────────────────────────────────────────────────

def _static_query_expansion(query: str) -> dict:
    q_lower = query.lower()
    mappings = {
        "alzheimer": (["Alzheimer disease","amyloid beta","tau protein","dementia","lecanemab","donanemab"],
                      ["Alzheimer Disease [MeSH]","Amyloid beta-Peptides [MeSH]"], ["G30"]),
        "kras":      (["KRAS G12C","sotorasib","adagrasib","RAS mutation","NSCLC KRAS"],
                      ["Proto-Oncogene Proteins p21(ras) [MeSH]"], ["C34"]),
        "glp-1":     (["GLP-1 receptor agonist","semaglutide","tirzepatide","obesity treatment"],
                      ["Glucagon-Like Peptide-1 Receptor [MeSH]","Obesity [MeSH]"], ["E11","E66"]),
        "rheumatoid": (["rheumatoid arthritis","JAK inhibitor","TNF inhibitor","methotrexate"],
                       ["Arthritis, Rheumatoid [MeSH]"], ["M05"]),
        "cart":      (["CAR-T cell","chimeric antigen receptor","CD19","BCMA","lymphoma"],
                      ["Receptors, Chimeric Antigen [MeSH]"], ["C81","C83"]),
        "nash":      (["NASH","NAFLD","liver fibrosis","steatohepatitis","resmetirom"],
                      ["Non-alcoholic Fatty Liver Disease [MeSH]"], ["K76"]),
        "sickle":    (["sickle cell disease","HbS","vaso-occlusive","gene therapy"],
                      ["Anemia, Sickle Cell [MeSH]"], ["D57"]),
        "sclerosis": (["multiple sclerosis","relapsing MS","BTK inhibitor","ocrelizumab"],
                      ["Multiple Sclerosis [MeSH]"], ["G35"]),
        "dermatitis":( ["atopic dermatitis","eczema","dupilumab","JAK inhibitor","TYK2"],
                       ["Dermatitis, Atopic [MeSH]"], ["L20"]),
        "glioblastoma":(["glioblastoma","GBM","IDH glioma","TTFields","temozolomide"],
                        ["Glioblastoma [MeSH]"], ["C71"]),
        "muscular":  (["spinal muscular atrophy","SMA","SMN1","nusinersen","risdiplam"],
                      ["Muscular Atrophy, Spinal [MeSH]"], ["G12"]),
        "pancreatic":(["pancreatic cancer","PDAC","KRAS G12D","gemcitabine","FOLFIRINOX"],
                      ["Pancreatic Neoplasms [MeSH]"], ["C25"]),
    }
    terms = [query]
    mesh = []
    icd = []
    for key, (t, m, i) in mappings.items():
        if key in q_lower:
            terms = t
            mesh = m
            icd = i
            break
    return {"query_terms": terms, "mesh_terms": mesh, "icd_codes": icd}


def _static_literature_synthesis(query: str, docs: list) -> str:
    if not docs:
        return (
            f"## Scientific summary: {query}\n\n"
            f"### Data availability notice\n"
            f"No literature retrieved for **{query}** — network access to PubMed and "
            f"Semantic Scholar is required. Set `ANTHROPIC_API_KEY` and ensure live API access.\n"
        )
    recent = [d for d in docs if d.get("recency_boost", 1.0) > 1.0]
    older  = [d for d in docs if d.get("recency_boost", 1.0) <= 1.0]
    themes = []
    all_abs = " ".join(d.get("abstract","") for d in docs[:10]).lower()
    if any(w in all_abs for w in ["phase 3","phase iii","randomized","randomised"]):
        themes.append("Phase 3 randomised controlled trial evidence available")
    if any(w in all_abs for w in ["fda approved","fda approval","approved","kisunla","leqembi","rezdiffra","casgevy"]):
        themes.append("Regulatory approvals exist in this indication")
    if any(w in all_abs for w in ["biomarker","stratification","subgroup","enrichment"]):
        themes.append("Biomarker-based patient stratification strategies under investigation")
    if any(w in all_abs for w in ["mechanism","pathway","signaling","receptor","target"]):
        themes.append("Mechanistic understanding is well-characterised across multiple MOAs")
    if any(w in all_abs for w in ["resistance","rebound","discontinu","durable"]):
        themes.append("Durability and resistance data emerging from longer follow-up studies")

    lines = [f"## Scientific summary: {query}\n"]
    lines.append(f"### Evidence base\n{len(docs)} documents retrieved — {len(recent)} published "
                 f"within 24 months, {len(older)} older. "
                 f"{'Evidence base includes recent Phase 3 data.' if recent else 'Evidence base primarily historical.'}\n")
    if themes:
        lines.append("### Key evidence themes")
        for t in themes: lines.append(f"- {t}")
        lines.append("")
    lines.append("### Recent findings (last 24 months)")
    if recent:
        for d in recent[:4]:
            lines.append(f"**{d.get('title','Untitled')}** ({d.get('date','')[:7]})")
            lines.append(f"{d.get('abstract','')[:500]}\n")
    else:
        lines.append(f"No publications within the last 24 months in curated database. "
                     f"Live PubMed retrieval recommended.\n")
    if older:
        lines.append("### Foundational evidence")
        for d in older[:3]:
            lines.append(f"- **{d.get('title','')}** ({d.get('date','')[:7]}): "
                         f"{d.get('abstract','')[:200]}")
    return "\n".join(lines)


def _static_trial_landscape(query: str, ct_docs: list) -> tuple:
    if not ct_docs:
        return (
            f"## Clinical trial landscape: {query}\n\n"
            f"No clinical trial data in curated database. Live ClinicalTrials.gov retrieval required.", []
        )
    structured = []
    for d in ct_docs:
        meta = d.get("metadata", {})
        structured.append({
            "nct_id": meta.get("nct_id",""),
            "title": d.get("title",""),
            "phase": meta.get("phase","N/A"),
            "status": meta.get("status","N/A"),
            "enrollment": meta.get("enrollment","N/A"),
            "sponsor": meta.get("sponsor","N/A"),
            "interventions": meta.get("interventions",[]),
            "primary_outcomes": meta.get("primary_outcomes",[]),
            "start_date": meta.get("start_date",""),
            "completion_date": meta.get("completion_date",""),
            "conditions": meta.get("conditions",[]),
        })
    phase_counts, status_counts, sponsors = {}, {}, set()
    for t in structured:
        p, s = t["phase"], t["status"].upper()
        for lbl, key in [("Phase 3","3"),("Phase 2","2"),("Phase 1","1")]:
            if key in p or ("III" if key=="3" else "II" if key=="2" else "I") in p:
                phase_counts[lbl] = phase_counts.get(lbl, 0) + 1; break
        for lbl, keys in [("Recruiting",["RECRUITING"]),("Active",["ACTIVE"]),
                           ("Completed",["COMPLETED"]),("Terminated",["TERMINATED"])]:
            if any(k in s for k in keys):
                status_counts[lbl] = status_counts.get(lbl, 0) + 1; break
        if t["sponsor"]: sponsors.add(t["sponsor"])

    lines = [f"## Clinical trial landscape: {query}\n"]
    lines.append("### Trial overview")
    for k, v in sorted(phase_counts.items()): lines.append(f"- **{k}**: {v} trial{'s' if v>1 else ''}")
    for k, v in sorted(status_counts.items()): lines.append(f"- **{k}**: {v} trial{'s' if v>1 else ''}")
    lines.append("")
    p3 = [t for t in structured if "3" in t["phase"] or "III" in t["phase"]]
    if p3:
        lines.append("### Phase 3 programme")
        for t in p3:
            comp = t["completion_date"][:7] if t["completion_date"] else "TBD"
            outcomes = "; ".join(t["primary_outcomes"][:2]) or "Not specified"
            lines.append(f"**{t['nct_id']}** — {t['title']}")
            lines.append(f"  Status: {t['status']} | N={t['enrollment']} | "
                         f"Sponsor: {t['sponsor']} | Est. completion: {comp}")
            lines.append(f"  Primary endpoint: {outcomes}\n")
    p2 = [t for t in structured if "2" in t["phase"] or "II" in t["phase"]]
    if p2:
        lines.append("### Phase 2 pipeline")
        for t in p2[:6]:
            comp = t["completion_date"][:7] if t["completion_date"] else "TBD"
            lines.append(f"**{t['nct_id']}** — {t['title'][:65]} (N={t['enrollment']}, completion: {comp})")

    p1 = [t for t in structured if ("1" in t["phase"] or "I" in t["phase"])
          and "2" not in t["phase"] and "II" not in t["phase"]
          and "3" not in t["phase"] and "III" not in t["phase"]]
    if p1:
        lines.append("### Phase 1 / early-stage")
        for t in p1[:4]:
            comp = t["completion_date"][:7] if t["completion_date"] else "TBD"
            lines.append(f"**{t['nct_id']}** — {t['title'][:65]} (N={t['enrollment']}, completion: {comp})")
    if sponsors:
        lines.append(f"\n### Sponsor landscape\nActive sponsors: {', '.join(sorted(sponsors)[:10])}")
    all_outcomes = []
    for t in structured: all_outcomes.extend(t.get("primary_outcomes",[]))
    unique = list(set(all_outcomes))[:8]
    if unique:
        lines.append(f"\n### Endpoint landscape\nPrimary endpoints in use: {'; '.join(unique)}")
    return "\n".join(lines), structured


def _static_trial_critique(query: str, ct_docs: list) -> str:
    """Asset-specific critique — differential analysis, not identical checkboxes."""
    if not ct_docs:
        return f"## Critical trial analysis: {query}\n\nNo trial data available."

    key_trials = [d for d in ct_docs
                  if any(p in d.get("metadata",{}).get("phase","") for p in ["2","3","II","III"])][:10]
    # Also include Phase 1 trials with notable enrollment or named assets
    p1_notable = [d for d in ct_docs
                  if d not in key_trials and
                  ("PHASE1" in d.get("metadata",{}).get("phase","").upper()) and
                  (int(str(d.get("metadata",{}).get("enrollment","0")).replace(",","") or "0") >= 25 or
                   any(kw in d.get("title","").lower() for kw in ["rmc-","mrtx","mrna","vaccine","1/2","phase 1/2"]))][:3]
    key_trials = key_trials + p1_notable
    if not key_trials: key_trials = ct_docs[:6]

    # Build per-trial differential critique
    lines = [f"## Critical trial analysis: {query}\n"]

    # First pass: gather stats across trials to enable comparison
    trial_scores = []
    for d in key_trials:
        meta = d.get("metadata", {})
        phase = meta.get("phase","")
        try: n = int(str(meta.get("enrollment",0)).replace(",",""))
        except: n = 0
        interventions = meta.get("interventions",[])
        outcomes = meta.get("primary_outcomes",[])
        status = meta.get("status","").upper()
        sponsor = meta.get("sponsor","")
        nct = meta.get("nct_id","")

        has_placebo = any("placebo" in str(i).lower() for i in interventions)
        has_active_comp = any(not ("placebo" in str(i).lower() or nct[:7] in str(i))
                              for i in interventions if i)
        is_p3 = "3" in phase or "III" in phase
        is_p2 = "2" in phase or "II" in phase
        is_completed = "COMPLET" in status
        outcomes_text = " ".join(outcomes).lower()
        has_hard_endpoint = any(kw in outcomes_text for kw in
                                ["survival","mortality","hospitalisation","event-free"])
        has_surrogate = any(kw in outcomes_text for kw in
                            ["biomarker","change from baseline","score","rate"])

        # Extract drug name from title/interventions
        drug_name = ""
        title = d.get("title","")
        for word in title.split():
            if len(word) > 6 and word[0].isupper() and word not in ["Phase","Study","Trial","Randomized","Placebo"]:
                drug_name = word
                break
        if not drug_name: drug_name = interventions[0][:25] if interventions else "Index drug"

        trial_scores.append({
            "nct": nct, "drug": drug_name, "title": title, "phase": phase,
            "n": n, "status": status, "sponsor": sponsor,
            "interventions": interventions, "outcomes": outcomes,
            "has_placebo": has_placebo, "has_active_comp": has_active_comp,
            "is_p3": is_p3, "is_p2": is_p2, "is_completed": is_completed,
            "has_hard_endpoint": has_hard_endpoint, "has_surrogate": has_surrogate,
        })

    # Compute median N for context
    ns = [t["n"] for t in trial_scores if t["n"] > 0]
    median_n = sorted(ns)[len(ns)//2] if ns else 300

    # Per-trial differential critique
    for t in trial_scores:
        lines.append(f"### {t['nct']}: {t['title'][:65]}")
        lines.append(f"**Phase:** {t['phase']} | **Status:** {t['status']} | "
                     f"**N:** {t['n']:,} | **Sponsor:** {t['sponsor'][:40]}")
        lines.append("")

        # Comparator design — most important for regulatory/commercial
        if t["has_active_comp"]:
            lines.append(f"- **Comparator design:** Active comparator present — "
                         f"{', '.join([i for i in t['interventions'] if 'placebo' not in i.lower()][:2])}. "
                         f"Appropriate for a crowded indication with established SOC.")
        elif t["has_placebo"] and not t["has_active_comp"]:
            lines.append(f"- **Comparator design:** ⚠ Placebo-controlled only — no active comparator against SOC. "
                         f"Regulatory risk: FDA increasingly expects SOC comparator in indications with established therapy. "
                         f"Payer/prescriber adoption risk: physicians will demand head-to-head data before switching patients.")
        else:
            lines.append(f"- **Comparator design:** ⚠ Comparator unclear from trial registry — verify protocol.")

        # Sample size vs field context
        if t["n"] == 0:
            lines.append(f"- **Sample size:** Not reported in registry — verify ClinicalTrials.gov directly.")
        elif t["n"] < 100:
            lines.append(f"- **Sample size:** ⚠ Small (N={t['n']:,}) — underpowered for registration; "
                         f"Phase 2 signal-finding only.")
        elif t["n"] < median_n * 0.6 and t["is_p3"]:
            lines.append(f"- **Sample size:** ⚠ Below-median for field (N={t['n']:,} vs median {median_n:,}). "
                         f"Verify power calculation supports the stated primary endpoint.")
        else:
            lines.append(f"- **Sample size:** ✓ N={t['n']:,} — {'well-powered' if t['n']>=300 else 'adequately powered'} "
                         f"for Phase {'3' if t['is_p3'] else '2'} registration endpoint.")

        # Endpoint quality
        endpoint_str = "; ".join(t["outcomes"][:2]) or "Not specified"
        if t["has_hard_endpoint"]:
            lines.append(f"- **Endpoint quality:** ✓ Hard clinical endpoint ({endpoint_str}) — "
                         f"regulatory-grade and patient-relevant.")
        elif t["has_surrogate"] and t["is_p3"]:
            lines.append(f"- **Endpoint quality:** ⚠ Surrogate endpoint ({endpoint_str}) — "
                         f"regulatory acceptance depends on validation. "
                         f"Commercial adoption requires demonstration of real-world clinical benefit.")
        else:
            lines.append(f"- **Primary endpoint:** {endpoint_str}")

        # Blinding/randomisation
        if t["is_p3"]:
            lines.append(f"- **Randomisation/blinding:** Double-blind RCT design expected for Phase 3. "
                         f"{'Results available — verify published paper for allocation concealment details.' if t['is_completed'] else 'Protocol not yet published — blinding quality unconfirmed.'}")
        else:
            lines.append(f"- **Randomisation/blinding:** Phase 2 — randomisation expected but blinding rigor variable.")

        # Field-specific methodological flags
        query_l = query.lower()
        if any(w in query_l for w in ["atopic","eczema","dermatitis"]):
            lines.append(f"- **AD-specific note:** Placebo response in AD trials is high (IGA 0/1 ~12-17% on placebo). "
                         f"Absolute treatment difference matters more than p-value alone. "
                         f"16-week endpoints may not capture durability — 52-week and OLE data critical for commercial positioning.")
        elif any(w in query_l for w in ["alzheimer","dementia","cognitive"]):
            lines.append(f"- **AD-specific note:** CDR-SB and iADRS effect sizes of 0.3-0.5 points are statistically "
                         f"significant but clinical meaningfulness is debated. FDA accepted these endpoints; "
                         f"prescribers and payors are more sceptical. ARIA monitoring adds real-world friction.")
        elif any(w in query_l for w in ["kras","nsclc","cancer","oncology","pdac","glioblastoma","pancreatic"]):
            lines.append(f"- **Oncology note:** OS endpoint preferred by regulators; PFS surrogate accepted "
                         f"with confirmatory OS data required. ORR acceptable for accelerated approval. "
                         f"Patient crossover in control arm inflates OS HR — adjust interpretation accordingly.")
        elif any(w in query_l for w in ["multiple sclerosis","ms "]):
            lines.append(f"- **MS-specific note:** ARR is accepted primary endpoint but 6-month or 12-month CDP "
                         f"is the gold standard for progressive MS. BTK inhibitors are the first class targeting "
                         f"CNS-resident B-cells and microglia — expect regulatory guidance to evolve.")
        elif any(w in query_l for w in ["nash","nafld","liver","mash"]):
            lines.append(f"- **NASH-specific note:** Histological endpoints (NASH resolution, fibrosis stage) "
                         f"require liver biopsy — regulatory standard but enriches for motivated patients. "
                         f"Non-invasive surrogate endpoints (MRI-PDFF, ELF) being validated for confirmatory trials.")
        elif any(w in query_l for w in ["sickle","scd"]):
            lines.append(f"- **SCD-specific note:** VOC rate endpoint has high variability and depends heavily on "
                         f"patient diary compliance. Gene therapy trials use single-arm designs against external controls "
                         f"— regulatory acceptance depends on robust natural history data.")
        elif any(w in query_l for w in ["obesity","glp","weight","bmi"]):
            lines.append(f"- **Obesity note:** % weight loss and ≥5%/≥10%/≥15% responder rates are dual FDA "
                         f"co-primary endpoints. CV outcomes trial (MACE) increasingly expected for broad label. "
                         f"Weight regain post-discontinuation must be addressed in labelling.")

        lines.append("")

    # Cross-trial comparison
    completed_p3 = [t for t in trial_scores if t["is_p3"] and t["is_completed"]]
    active_p3 = [t for t in trial_scores if t["is_p3"] and not t["is_completed"]]
    if len(trial_scores) > 1:
        lines.append("### Cross-trial comparative assessment")
        lines.append(f"**Total trials analysed:** {len(trial_scores)} "
                     f"({len(completed_p3)} Phase 3 completed, {len(active_p3)} Phase 3 active/recruiting, "
                     f"{len([t for t in trial_scores if t['is_p2']])} Phase 2)")

        no_active_comp = [t for t in trial_scores if not t["has_active_comp"] and t["is_p3"]]
        if no_active_comp:
            lines.append(f"⚠ **Comparator gap:** {len(no_active_comp)} Phase 3 trial(s) use placebo-only design "
                         f"({', '.join(t['nct'] for t in no_active_comp)}). "
                         f"Head-to-head data against SOC will be required by prescribers and payors regardless of FDA approval.")

        small_trials = [t for t in trial_scores if t["is_p3"] and 0 < t["n"] < 300]
        if small_trials:
            lines.append(f"⚠ **Power concern:** {len(small_trials)} Phase 3 trial(s) below N=300 threshold "
                         f"({', '.join(t['nct'] for t in small_trials)}) — verify statistical power calculations.")

        ns = [t["n"] for t in trial_scores if t["n"] > 0]
        if ns:
            lines.append(f"**Enrollment range:** {min(ns):,} – {max(ns):,} patients across trials "
                         f"(median {sorted(ns)[len(ns)//2]:,})")

    # Overall evidence quality
    p3_count = len([t for t in trial_scores if t["is_p3"]])
    completed_count = len([t for t in trial_scores if t["is_completed"]])
    has_active_comp_count = len([t for t in trial_scores if t["has_active_comp"]])
    avg_n = sum(t["n"] for t in trial_scores if t["n"]>0) / max(1, len([t for t in trial_scores if t["n"]>0]))

    if p3_count >= 2 and completed_count >= 1 and avg_n >= 400:
        rating = "**Strong**"
        rationale = "Multiple Phase 3 trials, at least one completed, adequate enrollment."
    elif p3_count >= 1 and avg_n >= 200:
        rating = "**Moderate**"
        rationale = "Phase 3 evidence present but limited by sample size or comparator design."
    else:
        rating = "**Weak / Preliminary**"
        rationale = "Phase 2 evidence only or underpowered Phase 3 programmes."

    lines.append(f"\n### Overall evidence quality: {rating}")
    lines.append(f"{rationale}")
    if has_active_comp_count < len([t for t in trial_scores if t["is_p3"]]):
        lines.append(f"Note: {p3_count - has_active_comp_count} of {p3_count} Phase 3 trial(s) lack active comparator arms — "
                     f"this is a commercial and regulatory risk, not only a methodological one.")

    lines.append("\n### Methodological caveats")
    lines.append("- Critique based on trial registry metadata and published abstracts; "
                 "full statistical analysis plans not available")
    lines.append("- Effect sizes and confidence intervals require access to published full papers for complete evaluation")
    lines.append("- Open-label extension data should not be conflated with double-blind primary endpoint results")
    lines.append("- Real-world effectiveness typically 15-25% below clinical trial efficacy due to adherence and population heterogeneity")

    return "\n".join(lines)


def _static_market_sizing(query: str, ct_docs: list, fda_docs: list, intel: dict) -> str:
    market = intel.get("market", {})
    lines = [f"## Market sizing: {query}\n"]

    m2024 = market.get("global_market_2024_usd_bn")
    m2030 = market.get("global_market_2030_usd_bn")
    cagr  = market.get("cagr_pct")

    if m2024:
        lines.append("### Total addressable market")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Global market 2024 | {_fmt_usd(m2024)} |")
        lines.append(f"| Global market 2030 (projected) | {_fmt_usd(m2030)} |")
        lines.append(f"| CAGR 2024–2030 | {cagr}% |")
        if market.get("us_patients_total_mn"):
            lines.append(f"| US patients (total indication) | {_fmt_patients(market['us_patients_total_mn'])} |")
        if market.get("us_moderate_severe_mn"):
            lines.append(f"| US moderate-severe patients | {_fmt_patients(market['us_moderate_severe_mn'])} |")
        if market.get("us_treatment_eligible_mn"):
            lines.append(f"| US treatment-eligible (current SOC access) | {_fmt_patients(market['us_treatment_eligible_mn'])} |")
        lines.append("")
        if market.get("market_note"):
            lines.append(f"### Market context\n{market['market_note']}\n")
        if market.get("key_geographies"):
            lines.append(f"### Key geographies\n{', '.join(market['key_geographies'])}\n")
    else:
        n_trials = len(ct_docs)
        n_approved = len(fda_docs)
        lines.append(f"Market sizing data not available in curated database for this indication. "
                     f"Based on pipeline signals: {n_trials} active trials and {n_approved} approved therapies "
                     f"suggest a {'substantial' if n_trials>5 else 'developing'} commercial market.")
        lines.append("\nFor investment-grade market analysis, recommend accessing:")
        lines.append("- Evaluate Pharma global epidemiology database")
        lines.append("- IQVIA market intelligence (prescription volume, market share)")
        lines.append("- GlobalData disease prevalence reports")

    # Revenue ceiling estimate
    if m2024 and market.get("us_treatment_eligible_mn"):
        eli = market["us_treatment_eligible_mn"]
        pricing = intel.get("pricing", {})
        net_price = pricing.get("lead_asset_net_price_est_usd", 20000)
        # New entrant realistic scenario: 5-15% share at year 5
        lo = eli * 0.05 * net_price / 1e9
        mid = eli * 0.10 * net_price / 1e9
        hi = eli * 0.15 * net_price / 1e9

        def _rev(val_bn):
            if val_bn >= 0.1:
                return f"~${val_bn:.1f}B"
            else:
                return f"~${val_bn*1000:.0f}M"

        lines.append(f"### New entrant revenue ceiling (US only)")
        lines.append(f"At net price ~${net_price:,.0f}/year, with {_fmt_patients(eli)} US treatment-eligible patients:")
        lines.append(f"- **Conservative (5% share at Year 5):** {_rev(lo)} annual US revenue")
        lines.append(f"- **Base case (10% share):** {_rev(mid)} annual US revenue")
        lines.append(f"- **Bull case (15% share):** {_rev(hi)} annual US revenue")
        lines.append(f"\nNote: penetration assumption depends heavily on differentiation data, formulary positioning, "
                     f"and payor step-therapy requirements.")

    return "\n".join(lines)


def _static_pricing_reimbursement(query: str, fda_docs: list, intel: dict) -> str:
    pricing = intel.get("pricing", {})
    lines = [f"## Pricing and reimbursement: {query}\n"]

    if pricing.get("lead_asset_list_price_usd"):
        lines.append("### Current pricing landscape")
        lines.append(f"| Asset | List price (USD/yr) | Est. net price (USD/yr) |")
        lines.append(f"|-------|--------------------|-----------------------|")
        for d in fda_docs[:5]:
            meta = d.get("metadata", {})
            brand = meta.get("brand_names", ["?"])[0]
            generic = meta.get("generic_names", ["?"])[0]
            # Extract price from abstract
            import re
            abstract = d.get("abstract", "")
            price_match = re.search(r'\$([0-9,]+(?:\.[0-9]+)?)', abstract)
            price_str = f"~${price_match.group(1)}" if price_match else "See label"
            lines.append(f"| {brand} ({generic}) | {price_str} | Est. 40-55% rebate |")
        lines.append("")
        lines.append(f"**SOC baseline cost:** ~${pricing['soc_annual_cost_usd']:,}/year\n")

    if pricing.get("payor_note"):
        lines.append(f"### Payor environment\n{pricing['payor_note']}\n")

    if pricing.get("biosimilar_timeline"):
        lines.append(f"### Biosimilar/generic timeline\n{pricing['biosimilar_timeline']}\n")

    if pricing.get("pricing_risk"):
        risk = pricing["pricing_risk"]
        risk_color = "🔴" if "High" in risk else ("🟡" if "Moderate" in risk else "🟢")
        lines.append(f"### Pricing risk: {risk_color} {risk}\n")

    # Generic payor guidance if no intel
    if not pricing.get("lead_asset_list_price_usd"):
        lines.append("### Payor environment\n")
        lines.append("- Step therapy requirements are standard in most chronic indications with ≥2 approved agents")
        lines.append("- New entrants typically achieve 40-60% rebates off list price to secure Tier 2 formulary placement")
        lines.append("- CMS IRA drug negotiation authority applies to top-spend Medicare drugs — relevant for high-cost biologics")
        lines.append("- Value-based contracts tied to real-world outcomes are increasingly required by major payers")

    lines.append("### New entrant pricing considerations")
    lines.append("- Demonstrable superiority on ≥1 clinical dimension is required to price at or above existing SOC")
    lines.append("- Oral formulations (where applicable) typically price 15-25% below injectable equivalents "
                 "despite comparable efficacy — access/convenience premium is real but limited")
    lines.append("- Companion diagnostic requirements add $300-600/patient to initiation cost "
                 "but can support premium pricing for biomarker-selected populations")
    lines.append("- Real-world evidence programmes are increasingly required by payers as condition of coverage "
                 "— budget this into commercialisation costs ($5-15M/year)")

    return "\n".join(lines)


def _static_patient_stratification(query: str, intel: dict) -> str:
    strat = intel.get("patient_stratification", {})
    lines = [f"## Patient stratification and biomarker landscape: {query}\n"]

    if strat.get("key_biomarkers"):
        lines.append("### Key predictive biomarkers")
        for b in strat["key_biomarkers"]:
            lines.append(f"- {b}")
        lines.append("")

    if strat.get("subpopulations"):
        lines.append("### Patient subpopulations and differentiation opportunities")
        for sp in strat["subpopulations"]:
            lines.append(f"- {sp}")
        lines.append("")

    if strat.get("unmet_need"):
        lines.append(f"### Critical unmet need\n{strat['unmet_need']}\n")

    if not strat.get("key_biomarkers"):
        lines.append("### Patient stratification framework\n")
        lines.append("Biomarker-based patient selection is the primary differentiator in competitive indications. "
                     "Key questions for investment diligence:\n")
        lines.append("1. **Predictive biomarker:** Is there a validated marker that identifies likely responders? "
                     "Enriched trials de-risk development and support premium pricing.")
        lines.append("2. **Diagnostic accessibility:** Can the biomarker be measured in routine clinical practice "
                     "(blood test) or does it require specialised imaging or biopsy?")
        lines.append("3. **Sub-population sizing:** Does the biomarker-selected population represent a commercially "
                     "viable patient number, or does enrichment create an orphan-disease economics problem?")
        lines.append("4. **Unmet sub-populations:** Which patient segments are systematically excluded from "
                     "current trials (paediatric, elderly, racial minorities, comorbid patients)?")

    return "\n".join(lines)


def _static_moa_landscape(query: str, intel: dict, ct_docs: list, fda_docs: list) -> str:
    moa = intel.get("moa_landscape", {})
    lines = [f"## Mechanism of action landscape: {query}\n"]

    if moa:
        lines.append("### MOA competitive map")
        lines.append("| Mechanism | Assets | Status |")
        lines.append("|-----------|--------|--------|")
        for mechanism, assets in moa.items():
            for asset in assets:
                # Determine status from asset name
                if "(approved)" in asset.lower():
                    status = "✓ Approved"
                    asset_clean = asset.replace(" (approved)","").replace(" — SOC benchmark","").strip()
                elif "ph3" in asset.lower() or "phase 3" in asset.lower():
                    status = "Phase 3"
                    asset_clean = asset
                elif "ph2" in asset.lower() or "phase 2" in asset.lower():
                    status = "Phase 2"
                    asset_clean = asset
                elif "ph1" in asset.lower() or "phase 1" in asset.lower():
                    status = "Phase 1"
                    asset_clean = asset
                elif "failed" in asset.lower():
                    status = "✗ Failed"
                    asset_clean = asset.replace(" (Ph2 failed)","").replace(" (Ph3 failed)","").strip()
                else:
                    status = "Pipeline"
                    asset_clean = asset
                lines.append(f"| {mechanism} | {asset_clean} | {status} |")
        lines.append("")

        # MOA diversity assessment
        approved_moas = {k for k, v in moa.items() if any("approved" in a.lower() for a in v)}
        pipeline_moas = {k for k, v in moa.items() if any("ph3" in a.lower() or "ph2" in a.lower() for a in v)}
        lines.append("### MOA diversity assessment")
        lines.append(f"- **Approved mechanisms:** {len(approved_moas)} distinct MOAs with regulatory validation")
        lines.append(f"- **Pipeline mechanisms:** {len(pipeline_moas)} MOAs in Phase 2/3 development")
        lines.append(f"- **Total MOA diversity:** {len(moa)} distinct mechanisms active in this indication")
        if len(approved_moas) >= 3:
            lines.append("- **Implication:** High MOA diversity in approved space — "
                         "new entrants require clear mechanistic differentiation, not just incremental efficacy.")
        elif len(approved_moas) == 1:
            lines.append("- **Implication:** Single approved MOA creates significant white space "
                         "for mechanistically differentiated pipeline assets.")
        else:
            lines.append("- **Implication:** Two approved MOAs — the field is establishing mechanistic breadth; "
                         "pipeline assets must differentiate on mechanism or patient population.")
    else:
        # Build from raw trial data instead of intel
        from collections import Counter
        intervention_counter = Counter()
        for t in ct_docs:
            for iv in t.get("metadata",{}).get("interventions",[]):
                iv_clean = iv.strip()
                if iv_clean and "placebo" not in iv_clean.lower() and len(iv_clean) > 3:
                    # Don't include dose variants as separate mechanisms
                    base = iv_clean.split(" ")[0]
                    intervention_counter[base] += 1

        fda_names = []
        for d in fda_docs:
            meta = d.get("metadata",{})
            brands = meta.get("brand_names",[])
            generics = meta.get("generic_names",[])
            if brands: fda_names.append(f"{brands[0]} ({generics[0] if generics else 'N/A'})")

        lines.append("### Approved therapies")
        if fda_names:
            for name in fda_names: lines.append(f"- {name} ✓ FDA approved")
        else:
            lines.append("- No approved therapies identified in curated database")

        lines.append("\n### Active pipeline interventions (from trial registry)")
        for drug, count in sorted(intervention_counter.items(), key=lambda x: -x[1])[:12]:
            lines.append(f"- {drug} ({count} trial arm{'s' if count>1 else ''})")

        lines.append("\n⚠ Full mechanistic grouping requires curated MOA database entry for this indication. "
                     "The above is derived from trial registry data and may group dose variants as separate agents.")

    return "\n".join(lines)


def _static_long_term_safety(query: str, intel: dict, ct_docs: list, fda_docs: list) -> str:
    safety = intel.get("long_term_safety", {})
    lines = [f"## Long-term safety and durability: {query}\n"]

    if safety.get("key_signals"):
        lines.append("### Established safety signals")
        for signal in safety["key_signals"]:
            lines.append(f"- {signal}")
        lines.append("")

    if safety.get("durability"):
        lines.append(f"### Treatment durability\n{safety['durability']}\n")

    if safety.get("discontinuation_rate"):
        lines.append(f"### Real-world discontinuation rates\n{safety['discontinuation_rate']}\n")

    if not safety.get("key_signals"):
        # Generic long-term safety framework
        lines.append("### Long-term safety framework\n")
        lines.append("Clinical trial safety data (typically 12-24 weeks) is insufficient for chronic indications. "
                     "Key long-term safety questions for investor diligence:\n")
        lines.append("**1. Immunosuppression risk:** For biologics targeting immune pathways — "
                     "serious infection rate at 2-5 years vs placebo and vs SOC comparators")
        lines.append("**2. Malignancy signal:** Sustained immunomodulation requires long-term cancer surveillance "
                     "(particularly lymphoproliferative disease for B-cell/T-cell targeting agents)")
        lines.append("**3. Disease rebound:** What happens upon treatment discontinuation? "
                     "Rebound disease activity undermines the commercial durability of chronic therapies")
        lines.append("**4. Organ toxicity:** Liver (ALT/AST), renal, cardiac surveillance "
                     "for small molecule agents with on-target or off-target effects")
        lines.append("**5. Vaccine response:** Does treatment blunt vaccine efficacy? "
                     "Increasingly important post-COVID for biologic therapies targeting B/T cells")

    lines.append("### Investment implication")
    lines.append("Phase 3 label safety data represents ~12-24 months of exposure. "
                 "Post-marketing commitments (PMCs) and REMS programmes can significantly affect "
                 "commercial uptake, prescriber confidence, and liability exposure. "
                 "The difference between a clean long-term safety profile and a class boxed warning "
                 "can represent a 2-3× difference in peak market share for otherwise equivalent efficacy.")

    return "\n".join(lines)


def _static_competitive_dynamics(query: str, intel: dict, ct_docs: list, fda_docs: list) -> str:
    dynamics = intel.get("competitive_dynamics", {})
    lines = [f"## Competitive dynamics and M&A landscape: {query}\n"]

    if dynamics.get("franchise_logic"):
        lines.append(f"### Incumbent franchise logic\n{dynamics['franchise_logic']}\n")

    if dynamics.get("acquirer_landscape"):
        lines.append(f"### Acquirer landscape\n{dynamics['acquirer_landscape']}\n")

    if dynamics.get("bd_signal"):
        lines.append(f"### Business development signal\n{dynamics['bd_signal']}\n")

    if dynamics.get("patent_cliff"):
        lines.append(f"### Patent / exclusivity timeline\n{dynamics['patent_cliff']}\n")

    if dynamics.get("venture_opportunity"):
        lines.append(f"### Venture opportunity assessment\n{dynamics['venture_opportunity']}\n")

    if not dynamics.get("franchise_logic"):
        # Generic competitive dynamics framework
        sponsors = list(set(d.get("metadata",{}).get("sponsor","") for d in ct_docs if d.get("metadata",{}).get("sponsor","")))
        approved_sponsors = [d.get("metadata",{}).get("manufacturer",["Unknown"])[0] for d in fda_docs]

        lines.append("### Competitive landscape\n")
        if approved_sponsors:
            lines.append(f"**Current market holders:** {', '.join(set(approved_sponsors[:5]))}")
        if sponsors:
            lines.append(f"**Pipeline sponsors:** {', '.join(sorted(sponsors)[:8])}")
        lines.append("")
        lines.append("### M&A framework\nKey M&A signals to monitor:")
        lines.append("- **Build vs buy:** Large pharma entering this indication without internal pipeline will acquire")
        lines.append("- **Platform value:** Assets with multi-indication potential command 30-50% premium vs single-indication")
        lines.append("- **Data readouts as catalysts:** Phase 3 positive readouts typically trigger 6-12 month acquisition windows")
        lines.append("- **Distressed assets:** Phase 3 failures by competitors create licensing/acquisition opportunities at discount")

    return "\n".join(lines)


def _static_investment_recommendation(
    query: str, intel: dict, ct_docs: list, fda_docs: list,
    scientific_summary: str, trial_critique: str,
    market_sizing: str, competitive_dynamics: str
) -> str:
    market = intel.get("market", {})
    pricing = intel.get("pricing", {})
    dynamics = intel.get("competitive_dynamics", {})
    lines = [f"## Investment recommendation: {query}\n"]

    # Determine stage — with CNS/rare disease modifier
    p3_count = sum(1 for d in ct_docs if "3" in d.get("metadata",{}).get("phase","") or "III" in d.get("metadata",{}).get("phase",""))
    p2_count = sum(1 for d in ct_docs if "2" in d.get("metadata",{}).get("phase","") or "II" in d.get("metadata",{}).get("phase",""))
    approved_count = len(fda_docs)
    completing_soon = [d for d in ct_docs
                       if d.get("metadata",{}).get("completion_date","")[:4] in ["2025","2026","2027"]]
    sponsors = list(set(d.get("metadata",{}).get("sponsor","") for d in ct_docs if d.get("metadata",{}).get("sponsor","")))
    m2030 = market.get("global_market_2030_usd_bn", 0) or 0
    us_eligible = market.get("us_treatment_eligible_mn", 0) or 0
    is_small_rare = us_eligible < 0.05   # <50K US patients = rare disease economics
    is_cns = any(w in query.lower() for w in ["als","alzheimer","parkinson","huntington","neuro","brain",
                                               "sclerosis","muscular atrophy","glioblastoma","sma"])

    # For rare CNS indications with high Phase 3 failure rates, don't call Stage III
    # just because there are multiple approved agents — the commercial opportunity is structurally different
    if approved_count >= 2 and p3_count >= 3 and not is_small_rare:
        stage = "Stage III — Commercial execution bet"
        stage_note = ("The field has validated biology and multiple approved therapies. "
                      "Investment value creation requires superior commercial execution, "
                      "differentiated positioning, or a disruptive pricing/access model.")
        verdict_color = "🟡"
    elif approved_count >= 1 and p3_count >= 1:
        stage = "Stage II — Development risk bet"
        stage_note = ("Proof-of-concept established with ≥1 approval. Primary risk is "
                      "Phase 3 execution and regulatory pathway. Binary event-driven returns.")
        if is_small_rare:
            stage_note += (" Note: rare disease economics apply — "
                           "orphan drug exclusivity and premium pricing offset small patient numbers, "
                           "but market ceiling is structurally limited.")
        verdict_color = "🟡"
    elif p2_count >= 2:
        stage = "Stage I — Scientific bet"
        stage_note = ("Phase 2 signal present but Phase 3 translation unproven. "
                      "High scientific and clinical execution risk; highest potential returns.")
        verdict_color = "🔴"
    else:
        stage = "Pre-clinical / Early clinical"
        stage_note = "Insufficient clinical evidence to stage the investment opportunity."
        verdict_color = "⚪"

    lines.append(f"### Investment stage: {verdict_color} {stage}")
    lines.append(f"{stage_note}\n")

    # Overall verdict
    venture_opp = dynamics.get("venture_opportunity", "")
    bd_signal = dynamics.get("bd_signal", "")

    lines.append("### Partner-level verdict")
    if is_small_rare and bd_signal:
        # Rare disease: specific M&A/asset-focused verdict
        lines.append("**Selective interest — precision medicine bet.** "
                     "Small patient population limits revenue ceiling but orphan economics support premium pricing. "
                     "Investment thesis must be asset-specific: identify the single most differentiated platform "
                     "or genetically-defined asset with robust biomarker data, not a broad-indication play.")
    elif m2030 >= 10 and approved_count <= 2 and p3_count >= 2:
        lines.append("**Proceed to deeper diligence.** Large market with room for additional entrants and "
                     "mechanistic differentiation in the late-stage pipeline warrants further investigation.")
    elif m2030 >= 5 and p3_count >= 1:
        lines.append("**Selective interest.** Market is meaningful but competitive. "
                     "Deep diligence warranted only on specifically differentiated assets — "
                     "generic 'me-too' positioning will not generate venture-scale returns.")
    elif approved_count >= 4:
        lines.append("**Cautious.** Market is mature with ≥4 approved therapies. "
                     "New entrant commercial path requires compelling differentiation data or "
                     "a novel access/pricing model. High bar for venture participation at this stage.")
    else:
        lines.append("**Watch list.** Insufficient data for a near-term investment decision. "
                     "Monitor Phase 3 readouts as catalysts for re-evaluation.")

    # Specific actionable items
    lines.append("\n### Actionable items for IC consideration")
    if bd_signal:
        lines.append(f"**M&A angle:** {bd_signal}")

    if completing_soon:
        ncts = [d.get("metadata",{}).get("nct_id","") for d in completing_soon[:3]]
        years = sorted(set(d.get("metadata",{}).get("completion_date","")[:4] for d in completing_soon[:3]))
        lines.append(f"**Near-term catalysts:** {len(completing_soon)} trial readout(s) expected "
                     f"in {'/'.join(years)} ({', '.join(ncts[:3])}). "
                     f"These are the binary events that will define entry valuation.")

    if venture_opp:
        lines.append(f"**Venture opportunity:** {venture_opp}")

    # What would make us pass
    lines.append("\n### Pass criteria")
    lines.append("We would **not** proceed if:")
    lines.append(f"- Lead asset is placebo-controlled only in an indication with established active SOC "
                 f"(regulatory risk + prescriber adoption risk)")
    lines.append(f"- No biomarker stratification strategy in a crowded indication "
                 f"(cannot define differentiated patient population)")
    lines.append(f"- Platform limited to a single MOA in a multi-MOA competitive field "
                 f"(no optionality if lead mechanism disappoints)")
    lines.append(f"- Founding team lacks direct regulatory and commercial experience in this indication")

    # What would make us invest — derive from disease context
    lines.append("\n### Invest criteria")
    lines.append("We would **proceed** if:")
    q_lower = query.lower()
    if any(w in q_lower for w in ["pancreatic","pdac"]):
        lines.append("- KRAS G12D inhibition with Phase 2 ORR >20% and PFS >4 months in PDAC — "
                     "validates the largest unaddressed oncogene in solid tumours")
        lines.append("- Combination strategy demonstrating extended DOR >8 months — "
                     "addresses the universal acquired resistance to single-agent KRAS inhibition")
        lines.append("- Platform with G12D + G12V coverage (pan-KRAS) — addresses 80%+ of KRAS-mutant PDAC")
        lines.append("- Early detection or ctDNA monitoring technology — shifts diagnosis to Stage I where 5-year survival is 40%+")
    elif any(w in q_lower for w in ["alzheimer","dementia","amyloid","lecanemab"]):
        lines.append("- Mechanism addressing tau, neuroinflammation, or synaptic targets — "
                     "orthogonal to approved amyloid-clearing antibodies")
        lines.append("- Oral or SC formulation removing infusion centre requirement — "
                     "massive access advantage over IV anti-amyloid antibodies")
        lines.append("- APOE4-safe profile — enables the ~15% of AD patients currently near-contraindicated")
        lines.append("- Prevention indication data — shifts addressable population from 400K to 5M+ US patients")
    elif any(w in q_lower for w in ["kras","nsclc kras","kras g12c"]):
        lines.append("- G12D or pan-KRAS coverage — extends beyond the approved G12C market into G12D PDAC and NSCLC")
        lines.append("- Combination strategy overcoming acquired resistance at 5-6 months — "
                     "doubles effective treatment duration")
        lines.append("- CNS-penetrant formulation — addresses brain metastasis subset (~30% of KRAS NSCLC)")
    elif any(w in q_lower for w in ["cart","car-t","chimeric"]):
        lines.append("- Allogeneic manufacturing platform with off-the-shelf availability — "
                     "eliminates 4-6 week wait and manufacturing failure rate")
        lines.append("- First-line MM data (CARTITUDE-5 equivalent) — expands addressable population 5×")
        lines.append("- Autoimmune disease application — CAR-T in SLE, MG, AAV opens 10× larger market")
    elif any(w in q_lower for w in ["sickle","scd"]):
        lines.append("- Oral disease-modifying agent with efficacy approaching gene therapy — "
                     "accessible to the 95%+ of SCD patients who cannot access gene therapy")
        lines.append("- HbF induction without myeloablation — disease modification without "
                     "the toxicity, cost, and access barriers of conditioning-based gene therapy")
    elif any(w in q_lower for w in ["glp","semaglutide","obesity","tirzepatide"]):
        lines.append("- Oral non-peptide GLP-1 with comparable efficacy to injectable — "
                     "10× larger addressable market via injection-averse patients")
        lines.append("- Weight maintenance mechanism — addresses rebound after discontinuation, "
                     "which affects ~70% of patients within 1 year")
        lines.append("- GLP-1 application in CNS/neurodegeneration — AD, Parkinson's, NASH combo")
    elif any(w in q_lower for w in ["multiple sclerosis","ms "]):
        lines.append("- BTK inhibitor with CNS penetrance addressing microglial/progressive MS — "
                     "first class to target CNS-resident pathology in progressive disease")
        lines.append("- Clean liver safety profile vs evobrutinib — resolves the class DILI concern")
        lines.append("- 6-month CDP data in PPMS/SPMS — establishes neuroprotective effect beyond ARR")
    elif any(w in q_lower for w in ["atopic","eczema","dermatitis"]):
        lines.append("- TYK2-class mechanism with efficacy comparable to JAK1 but without the boxed warning — "
                     "captures prescribers blocked from upadacitinib/abrocitinib by CV risk concerns")
        lines.append("- Durable remission off-treatment data — OX40L/OX40 pathway may enable treatment holidays")
        lines.append("- Oral formulation in an injection-dominated class — expands primary care prescribing")
    else:
        lines.append("- Mechanistically differentiated asset with validated biomarker for patient selection")
        lines.append("- Phase 2 data with durable response and manageable safety profile")
        lines.append("- Clear path to registration with identified Phase 3 endpoint and regulatory precedent")
        lines.append("- Platform with multi-indication optionality beyond lead programme")

    # Diligence questions — also disease-aware
    lines.append("\n### Key diligence questions for management")
    if any(w in q_lower for w in ["pancreatic","pdac"]):
        lines.append("1. What is the Phase 2 ORR threshold that would trigger a Phase 3 decision, and when does that data read?")
        lines.append("2. What combination strategy is planned to address acquired resistance at 5-6 months?")
        lines.append("3. What is the companion diagnostic development plan for KRAS G12D mutation testing at community oncology centres?")
        lines.append("4. What is the regulatory precedent for PDAC approval — accelerated (ORR) vs full (OS)?")
        lines.append("5. What is the partnership/out-licensing strategy — standalone commercialisation or collaboration with an oncology-experienced large pharma?")
    elif any(w in q_lower for w in ["cart","car-t"]):
        lines.append("1. What is the manufacturing failure rate and turnaround time, and what is the roadmap to allogeneic?")
        lines.append("2. What is the COGS at commercial scale and what ASP is required for the business model?")
        lines.append("3. What is the strategy for the secondary malignancy FDA investigation — REMS update or additional monitoring?")
        lines.append("4. What is the evidence for durability beyond 24 months, and how does the company define functional cure?")
        lines.append("5. What is the plan for CARTITUDE-5 equivalent expansion to earlier lines of therapy?")
    elif any(w in q_lower for w in ["alzheimer","dementia"]):
        lines.append("1. What is the APOE4 safety profile and is there a plan for APOE4 homozygote exclusion or dose modification?")
        lines.append("2. What is the CMS coverage strategy — how will the company demonstrate real-world effectiveness for registry patients?")
        lines.append("3. What combination data with an approved anti-amyloid antibody is planned?")
        lines.append("4. What is the prevention indication strategy and timeline for label expansion to presymptomatic AD?")
        lines.append("5. What is the MRI monitoring infrastructure plan and estimated per-patient administration cost?")
    else:
        lines.append("1. What is the head-to-head data strategy versus current SOC, and what trial design would be required?")
        lines.append("2. What is the manufacturing COGS at commercial scale and net price required for target margins?")
        lines.append("3. What is the partnership/acquisition strategy — independent commercial build or large-pharma collaboration?")
        lines.append("4. What does the 2-5 year safety programme look like, and what is the contingency for an unexpected signal?")
        lines.append("5. What is the regulatory precedent for primary endpoints, and what label claims are realistically achievable?")

    return "\n".join(lines)


def _static_pipeline_regulatory(query: str, ct_docs: list, fda_docs: list) -> str:
    lines = [f"## Pipeline and regulatory landscape: {query}\n"]
    if fda_docs:
        lines.append("### Currently approved therapies (FDA)")
        for d in fda_docs:
            meta = d.get("metadata", {})
            brands = meta.get("brand_names", [])
            generics = meta.get("generic_names", [])
            name = f"{brands[0] if brands else 'Unknown'} ({generics[0] if generics else 'N/A'})"
            lines.append(f"**{name}**\n{d.get('abstract','')[:500]}\n")
    else:
        lines.append("### Currently approved therapies\nNone identified in curated database.\n")

    p3 = [d for d in ct_docs if "3" in d.get("metadata",{}).get("phase","") or "III" in d.get("metadata",{}).get("phase","")]
    if p3:
        lines.append("### Late-stage pipeline (Phase 3)")
        for d in p3:
            meta = d.get("metadata",{})
            comp = meta.get("completion_date","TBD")[:7]
            lines.append(f"- **{meta.get('nct_id','')}**: {d.get('title','')[:70]} "
                         f"| {meta.get('sponsor','')} | Est. completion: {comp}")
        lines.append("")

    p2 = [d for d in ct_docs if "2" in d.get("metadata",{}).get("phase","") or "II" in d.get("metadata",{}).get("phase","")]
    if p2:
        lines.append("### Mid-stage pipeline (Phase 2)")
        for d in p2[:5]:
            meta = d.get("metadata",{})
            lines.append(f"- **{meta.get('nct_id','')}**: {d.get('title','')[:70]} "
                         f"| N={meta.get('enrollment','?')} | {meta.get('status','')}")
        lines.append("")

    lines.append("### Regulatory environment")
    if fda_docs:
        lines.append("- Regulatory precedent established: FDA has approved therapies in this indication")
        lines.append("- Likely pathway: standard NDA/BLA; accelerated approval possible if "
                     "surrogate endpoint validated and unmet need demonstrated")
        lines.append("- Label breadth: post-approval label expansion for paediatric, severe, "
                     "or comorbid populations is a common value-creation strategy")
    else:
        lines.append("- No prior approvals: regulatory pathway being established in real time")
        lines.append("- Breakthrough Therapy Designation if early data show substantial improvement over SOC")
        lines.append("- Orphan Drug Designation (if applicable): 7-year US market exclusivity + tax credits")

    completing = [d for d in ct_docs
                  if d.get("metadata",{}).get("completion_date","")[:4] in ["2025","2026","2027"]]
    if completing:
        lines.append("\n### Near-term binary events calendar")
        for d in completing[:5]:
            meta = d.get("metadata",{})
            lines.append(f"- **{meta.get('nct_id','')}** ({d.get('title','')[:55]}): "
                         f"Est. completion {meta.get('completion_date','')[:7]} — "
                         f"primary endpoint readout anticipated within 6-12 months of completion")

    return "\n".join(lines)


def _static_investor_narrative(
    query: str, scientific_summary: str, trial_landscape: str, trial_critique: str,
    pipeline_regulatory: str, competitive_landscape: str, market_sizing: str,
    pricing_reimbursement: str, patient_stratification: str, moa_landscape: str,
    long_term_safety: str, competitive_dynamics: str, investment_recommendation: str,
    ct_docs: list, fda_docs: list
) -> str:
    if not ct_docs and not fda_docs:
        return (
            f"## EXECUTIVE SUMMARY: {query.upper()}\n\n"
            f"### Data availability notice\n"
            f"**{query}** is not in the curated database and live API access was unavailable.\n\n"
            f"Set `ANTHROPIC_API_KEY` with live network access and re-run for a fully-populated report.\n\n"
            f"**Curated diseases:** Alzheimer · KRAS G12C · GLP-1/obesity · Rheumatoid arthritis · "
            f"CAR-T · NASH · Sickle cell · Multiple sclerosis · Atopic dermatitis · "
            f"Glioblastoma · SMA · Pancreatic cancer\n"
        )

    p3_count = sum(1 for d in ct_docs if "3" in d.get("metadata",{}).get("phase","") or "III" in d.get("metadata",{}).get("phase",""))
    p2_count = sum(1 for d in ct_docs if "2" in d.get("metadata",{}).get("phase","") or "II" in d.get("metadata",{}).get("phase",""))
    approved_count = len(fda_docs)
    sponsors = list(set(d.get("metadata",{}).get("sponsor","") for d in ct_docs if d.get("metadata",{}).get("sponsor","")))
    completing_soon = [d for d in ct_docs
                       if d.get("metadata",{}).get("completion_date","")[:4] in ["2025","2026"]]

    if approved_count >= 2 and p3_count >= 3:
        maturity = "**Mature** — multiple approved therapies, competitive Phase 3 landscape"
        stage = "Stage III commercial execution bet"
        signal = (f"Differentiation-or-exit. {approved_count} approved therapies establish the field; "
                  f"{p3_count} simultaneous Phase 3 programmes create crowding risk. "
                  f"New capital should enter only with a clearly differentiated asset — "
                  f"MOA novelty, cleaner safety profile, superior durability data, or "
                  f"a biomarker-stratified patient population thesis.")
    elif approved_count >= 1 and p3_count >= 1:
        maturity = "**Emerging-mature** — first approvals in market, late-stage pipeline building"
        stage = "Stage II development risk bet"
        signal = (f"Selective interest. The first approval validates the biology; "
                  f"{p3_count} Phase 3 programme(s) represent binary event opportunities. "
                  f"Entry valuation should be anchored to Phase 3 readout timing and differentiation data.")
    else:
        maturity = "**Early** — Phase 1/2 evidence only"
        stage = "Stage I scientific bet"
        signal = "High-risk/high-reward. Scientific plausibility established but clinical translation unproven."

    lines = [f"## EXECUTIVE SUMMARY: {query.upper()}\n"]
    lines.append(f"**Scientific maturity:** {maturity}\n")
    lines.append(f"**Pipeline snapshot:** {len(ct_docs)} total trials | {p3_count} Phase 3 | "
                 f"{p2_count} Phase 2 | {approved_count} FDA-approved therapies | "
                 f"{len(sponsors)} active sponsors\n")
    lines.append(f"**Investment stage:** {stage}\n")
    lines.append(f"**Investment signal:** {signal}\n")

    if completing_soon:
        ncts = [d.get("metadata",{}).get("nct_id","") for d in completing_soon[:3]]
        lines.append(f"**Near-term catalysts:** {len(completing_soon)} trial(s) completing 2025–2026 "
                     f"({', '.join(ncts[:3])}) — primary binary events defining the near-term investment case.\n")

    # Pull key insight from investment recommendation
    if investment_recommendation:
        # Find the line immediately after "Partner-level verdict" heading
        rec_text_lines = investment_recommendation.split("\n")
        verdict_line = ""
        for i, l in enumerate(rec_text_lines):
            if "Partner-level verdict" in l:
                # Get next non-empty line
                for j in range(i+1, min(i+4, len(rec_text_lines))):
                    stripped = rec_text_lines[j].strip()
                    if stripped:
                        verdict_line = stripped.replace("**","")
                        break
                break
        if not verdict_line:
            # Fallback: first bold line with Proceed/Cautious/Watch/Pass
            for l in rec_text_lines:
                if any(w in l for w in ["Proceed","Cautious","Watch","Pass","proceed","pass"]) and l.strip():
                    verdict_line = l.replace("**","").strip()
                    break
        if verdict_line:
            lines.append(f"**Invivo Partners verdict:** {verdict_line}\n")

    return "\n".join(lines)


# ─── Node functions ───────────────────────────────────────────────────────────

def node_query_expansion(state: AgentState) -> dict:
    logger.info(f"[Node 0] Query expansion: {state['query']}")
    llm = _get_llm()
    if llm:
        prompt = (f'Given the disease or treatment: "{state["query"]}" — '
                  f'return ONLY valid JSON (no markdown): '
                  f'{{"primary_terms":["..."],"mesh_terms":["..."],"icd_codes":["..."],"all_terms":["...6-10 terms..."]}}')
        text = _llm_call(llm, "You are a biomedical search specialist. Return only JSON.", prompt)
        if text:
            try:
                text = text.strip()
                if text.startswith("```"): text = text.split("```")[1]; text = text[4:] if text.startswith("json") else text
                parsed = json.loads(text.strip())
                return {"query_terms": parsed.get("all_terms",[state["query"]]),
                        "mesh_terms": parsed.get("mesh_terms",[]),
                        "icd_codes": parsed.get("icd_codes",[]),
                        "progress_log": [f"LLM query expansion: {len(parsed.get('all_terms',[]))} terms"],
                        "errors": []}
            except Exception as e:
                logger.warning(f"LLM expansion parse error: {e}")
    expanded = _static_query_expansion(state["query"])
    return {**expanded, "progress_log": [f"Query expanded ({len(expanded['query_terms'])} terms)"], "errors": []}


def node_literature_synthesis(state: AgentState) -> dict:
    logger.info("[Node 1] Literature synthesis")
    llm = _get_llm(0.15)
    docs = [d for d in state.get("all_documents",[]) if d.get("source") in ("pubmed","semantic_scholar","biorxiv")][:20]
    if llm and docs:
        doc_text = "\n".join(f"[{i}] {'★' if d.get('credibility_tier')==1 else '○'} {d['title']} ({d.get('date','')[:7]})\n{d['abstract'][:400]}"
                             for i, d in enumerate(docs[:15],1))
        system = ("You are a senior biomedical scientist preparing a synthesis for VC investors in biotech. "
                  "Be precise, evidence-graded, and explicitly note where evidence is from preprints or limited studies.")
        prompt = (f"Synthesise the scientific literature for: {state['query']}\n\nDOCUMENTS:\n{doc_text}\n\n"
                  f"Cover: 1) Mechanistic understanding 2) State of evidence 3) Key recent findings 4) Open questions 5) Evidence gaps. "
                  f"Be specific about effect sizes and study limitations. Do NOT use Alzheimer-specific terminology (CDR-SB, ARIA, amyloid) "
                  f"unless the query is actually about Alzheimer disease.")
        text = _llm_call(llm, system, prompt)
        if text:
            return {"scientific_summary": text, "progress_log": [f"LLM literature synthesis ({len(docs)} docs)"], "errors": []}
    summary = _static_literature_synthesis(state["query"], docs or state.get("pubmed_docs",[]))
    return {"scientific_summary": summary, "progress_log": [f"Static literature synthesis ({len(docs)} docs)"], "errors": []}


def node_trial_mapping(state: AgentState) -> dict:
    logger.info("[Node 2] Trial landscape mapping")
    llm = _get_llm(0.1)
    ct_docs = state.get("clinical_trials",[])
    if llm and ct_docs:
        trial_text = "\n".join(
            f"NCT:{d.get('metadata',{}).get('nct_id','')} | {d.get('metadata',{}).get('phase','')} | "
            f"{d.get('metadata',{}).get('status','')} | N:{d.get('metadata',{}).get('enrollment','')} | "
            f"Sponsor:{d.get('metadata',{}).get('sponsor','')} | {d['title'][:55]}"
            for d in ct_docs[:25])
        system = "You are a clinical development analyst mapping the trial landscape for VC investors. Be specific with NCT IDs, enrollment, and completion dates."
        prompt = (f"Map the clinical trial landscape for: {state['query']}\n\nTRIALS:\n{trial_text}\n\n"
                  f"Provide: 1) Trial count by phase/status 2) Phase 3 details with endpoints and completion dates "
                  f"3) Phase 2 pipeline 4) Sponsor landscape 5) Endpoint patterns 6) Key readout timeline 2025-2027")
        text = _llm_call(llm, system, prompt)
        if text:
            structured = [{"nct_id":d.get("metadata",{}).get("nct_id",""),"title":d.get("title",""),
                           "phase":d.get("metadata",{}).get("phase","N/A"),"status":d.get("metadata",{}).get("status","N/A"),
                           "enrollment":d.get("metadata",{}).get("enrollment","N/A"),"sponsor":d.get("metadata",{}).get("sponsor","N/A"),
                           "interventions":d.get("metadata",{}).get("interventions",[]),"primary_outcomes":d.get("metadata",{}).get("primary_outcomes",[]),
                           "start_date":d.get("metadata",{}).get("start_date",""),"completion_date":d.get("metadata",{}).get("completion_date",""),
                           "conditions":d.get("metadata",{}).get("conditions",[])} for d in ct_docs]
            return {"trial_landscape":text,"trial_landscape_structured":structured,
                    "progress_log":[f"LLM trial mapping ({len(ct_docs)} trials)"],"errors":[]}
    landscape_text, structured = _static_trial_landscape(state["query"], ct_docs)
    return {"trial_landscape":landscape_text,"trial_landscape_structured":structured,
            "progress_log":[f"Static trial mapping ({len(ct_docs)} trials)"],"errors":[]}


def node_trial_critique(state: AgentState) -> dict:
    logger.info("[Node 3] Trial critique")
    llm = _get_llm(0.1)
    ct_docs = state.get("clinical_trials",[])
    key_trials = [d for d in ct_docs if any(p in d.get("metadata",{}).get("phase","") for p in ["2","3","II","III"])][:12]
    if not key_trials: key_trials = ct_docs[:8]
    if llm and key_trials:
        trial_text = "\n".join(
            f"--- {d.get('metadata',{}).get('nct_id','')} ---\n"
            f"Title: {d.get('title','')}\nPhase:{d.get('metadata',{}).get('phase','')} "
            f"N:{d.get('metadata',{}).get('enrollment','')} Status:{d.get('metadata',{}).get('status','')}\n"
            f"Interventions:{','.join(d.get('metadata',{}).get('interventions',[])[:3])}\n"
            f"Outcomes:{','.join(d.get('metadata',{}).get('primary_outcomes',[])[:2])}\n"
            f"Abstract:{d.get('abstract','')[:400]}"
            for d in key_trials)
        system = ("You are a senior biostatistician and clinical trial methodologist at a tier-1 biotech VC. "
                  "Provide asset-specific differential critique — NOT identical boilerplate for each trial. "
                  "Highlight key differences between trials. Be specific about this indication's methodological standards.")
        prompt = (f"Critically evaluate trial evidence for: {state['query']}\n\nTRIALS:\n{trial_text}\n\n"
                  f"For each trial provide SPECIFIC critique (not identical text): comparator design adequacy, "
                  f"sample size vs field median, endpoint quality and regulatory grade, blinding rigor. "
                  f"Then: cross-trial comparison identifying the strongest and weakest evidence; "
                  f"overall evidence quality rating (Strong/Moderate/Weak) with specific rationale; "
                  f"top 3 methodological risks for this specific indication. "
                  f"Do NOT use Alzheimer terminology (CDR-SB, ARIA, ADAS-Cog) unless query is about Alzheimer.")
        text = _llm_call(llm, system, prompt)
        if text:
            return {"trial_critique":text,"progress_log":[f"LLM trial critique ({len(key_trials)} trials)"],"errors":[]}
    critique = _static_trial_critique(state["query"], ct_docs)
    return {"trial_critique":critique,"progress_log":[f"Static trial critique ({len(key_trials)} trials)"],"errors":[]}


def node_pipeline_regulatory(state: AgentState) -> dict:
    logger.info("[Node 4] Pipeline & regulatory")
    llm = _get_llm(0.1)
    ct_docs = state.get("clinical_trials",[])
    fda_docs = state.get("fda_docs",[])
    if llm:
        ct_text = "\n".join(f"Phase:{d.get('metadata',{}).get('phase','')} | {d['title'][:60]} | "
                            f"Sponsor:{d.get('metadata',{}).get('sponsor','')} | Completion:{d.get('metadata',{}).get('completion_date','')[:7]}"
                            for d in ct_docs[:20])
        fda_text = "\n".join(f"- {d['title']}: {d['abstract'][:300]}" for d in fda_docs[:6])
        system = "You are a regulatory affairs specialist and biotech pipeline analyst writing for VC investors."
        prompt = (f"Pipeline and regulatory landscape for: {state['query']}\n\nPIPELINE:\n{ct_text or 'None.'}\n\n"
                  f"FDA APPROVED:\n{fda_text or 'None.'}\n\n"
                  f"Provide: approved therapies with mechanism and commercial context; Phase 3 pipeline with differentiation vs SOC; "
                  f"Phase 2 pipeline; regulatory environment (precedent, likely pathway, breakthrough/orphan designations); "
                  f"binary event calendar for 2025-2027.")
        text = _llm_call(llm, system, prompt)
        if text:
            return {"pipeline_regulatory":text,"progress_log":["LLM pipeline & regulatory"],"errors":[]}
    return {"pipeline_regulatory":_static_pipeline_regulatory(state["query"], ct_docs, fda_docs),
            "progress_log":["Static pipeline & regulatory"],"errors":[]}


def node_new_analytics(state: AgentState) -> dict:
    """Single node that generates all new analytical sections from intel + data."""
    logger.info("[Node 5] New analytics (market, pricing, MOA, safety, dynamics)")
    query = state["query"]
    ct_docs = state.get("clinical_trials",[])
    fda_docs = state.get("fda_docs",[])
    intel = _get_intel(query)
    llm = _get_llm(0.2)

    if llm and intel:
        # Use LLM with intel as context for richer output
        intel_summary = json.dumps({k: v for k, v in intel.items() if k != "moa_landscape"}, indent=2)[:3000]
        system = ("You are a partner-level biotech investor at a tier-1 VC fund. "
                  "Write investment-grade analysis sections for an IC memo. Be specific, opinionated, and actionable.")

        def llm_section(section_name: str, prompt: str) -> str:
            text = _llm_call(llm, system, f"For {query}:\n\n{prompt}\n\nIntelligence context:\n{intel_summary}")
            return text or ""

        market = llm_section("market", "Write a market sizing section with TAM/SAM, patient funnel, revenue ceiling for a new entrant, and market context. Use specific numbers from the intelligence context.") or _static_market_sizing(query, ct_docs, fda_docs, intel)
        pricing = llm_section("pricing", "Write a pricing and reimbursement section covering current asset pricing, payor environment, biosimilar timeline, and pricing risk for new entrants. Be specific.") or _static_pricing_reimbursement(query, fda_docs, intel)
        strat = llm_section("stratification", "Write a patient stratification section covering key biomarkers, patient subpopulations, and the critical unmet need.") or _static_patient_stratification(query, intel)
        safety = llm_section("safety", "Write a long-term safety section covering key safety signals, treatment durability, and discontinuation rates. Be specific about what the 2-5 year data shows.") or _static_long_term_safety(query, intel, ct_docs, fda_docs)
        dynamics = llm_section("dynamics", "Write a competitive dynamics and M&A section covering incumbent franchise logic, acquirer landscape, BD signals, patent cliff, and venture opportunity.") or _static_competitive_dynamics(query, intel, ct_docs, fda_docs)
        moa = _static_moa_landscape(query, intel, ct_docs, fda_docs)  # Always static — table format
    else:
        market   = _static_market_sizing(query, ct_docs, fda_docs, intel)
        pricing  = _static_pricing_reimbursement(query, fda_docs, intel)
        strat    = _static_patient_stratification(query, intel)
        moa      = _static_moa_landscape(query, intel, ct_docs, fda_docs)
        safety   = _static_long_term_safety(query, intel, ct_docs, fda_docs)
        dynamics = _static_competitive_dynamics(query, intel, ct_docs, fda_docs)

    return {
        "market_sizing": market,
        "pricing_reimbursement": pricing,
        "patient_stratification": strat,
        "moa_landscape": moa,
        "long_term_safety": safety,
        "competitive_dynamics": dynamics,
        "competitive_landscape": dynamics,  # also populate original field for backwards compat
        "progress_log": ["Analytics: market, pricing, MOA, safety, competitive dynamics"],
        "errors": [],
    }


def node_investment_recommendation(state: AgentState) -> dict:
    logger.info("[Node 6] Investment recommendation")
    llm = _get_llm(0.3)
    ct_docs = state.get("clinical_trials",[])
    fda_docs = state.get("fda_docs",[])
    intel = _get_intel(state["query"])

    if llm:
        context = "\n\n".join([
            f"MARKET SIZING:\n{state.get('market_sizing','')[:800]}",
            f"TRIAL CRITIQUE:\n{state.get('trial_critique','')[:800]}",
            f"COMPETITIVE DYNAMICS:\n{state.get('competitive_dynamics','')[:800]}",
            f"PRICING:\n{state.get('pricing_reimbursement','')[:600]}",
            f"PATIENT STRATIFICATION:\n{state.get('patient_stratification','')[:600]}",
        ])
        system = ("You are a partner at Invivo Partners, a biotech VC fund. "
                  "Write an investment recommendation section for the IC memo. "
                  "Be direct, opinionated, and actionable. Name specific assets. Give a clear verdict. "
                  "Include: investment stage (I/II/III), partner-level verdict (proceed/cautious/pass), "
                  "specific M&A angle, named catalysts, pass criteria, invest criteria, "
                  "and 5 specific diligence questions for management.")
        prompt = (f"Write the investment recommendation for: {state['query']}\n\n"
                  f"Context:\n{context}\n\n"
                  f"This section must be actionable enough to support an IC discussion. "
                  f"Do NOT use generic language. Be specific about which assets are most investable and why.")
        text = _llm_call(llm, system, prompt)
        if text:
            rec = text
        else:
            rec = _static_investment_recommendation(
                state["query"], intel, ct_docs, fda_docs,
                state.get("scientific_summary",""), state.get("trial_critique",""),
                state.get("market_sizing",""), state.get("competitive_dynamics",""))
    else:
        rec = _static_investment_recommendation(
            state["query"], intel, ct_docs, fda_docs,
            state.get("scientific_summary",""), state.get("trial_critique",""),
            state.get("market_sizing",""), state.get("competitive_dynamics",""))

    return {"investment_recommendation": rec, "progress_log": ["Investment recommendation assembled"], "errors": []}


def node_investor_narrative(state: AgentState) -> dict:
    logger.info("[Node 7] Investor narrative / executive summary")
    llm = _get_llm(0.3)
    ct_docs = state.get("clinical_trials",[])
    fda_docs = state.get("fda_docs",[])

    if llm:
        system = ("You are a partner at Invivo Partners writing an executive summary for an IC memo. "
                  "Lead with the investment signal. Be direct. Use specific data and asset names. "
                  "This will be read by partners who have 90 seconds — make every sentence count.")
        context = "\n\n".join([
            f"SCIENTIFIC SUMMARY:\n{state.get('scientific_summary','')[:600]}",
            f"TRIAL LANDSCAPE:\n{state.get('trial_landscape','')[:500]}",
            f"MARKET SIZING:\n{state.get('market_sizing','')[:500]}",
            f"INVESTMENT RECOMMENDATION:\n{state.get('investment_recommendation','')[:800]}",
        ])
        prompt = (f"Write the executive summary for: {state['query']}\n\n{context}\n\n"
                  f"Include: scientific maturity rating, pipeline snapshot (specific numbers), "
                  f"investment stage verdict, the single most important investment signal, "
                  f"top risk and top opportunity, near-term catalysts with names and dates, "
                  f"Invivo Partners verdict (1 sentence).")
        text = _llm_call(llm, system, prompt)
        if text:
            return {"investor_narrative": text, "progress_log": ["LLM executive summary"], "errors": []}

    narrative = _static_investor_narrative(
        query=state["query"],
        scientific_summary=state.get("scientific_summary",""),
        trial_landscape=state.get("trial_landscape",""),
        trial_critique=state.get("trial_critique",""),
        pipeline_regulatory=state.get("pipeline_regulatory",""),
        competitive_landscape=state.get("competitive_landscape",""),
        market_sizing=state.get("market_sizing",""),
        pricing_reimbursement=state.get("pricing_reimbursement",""),
        patient_stratification=state.get("patient_stratification",""),
        moa_landscape=state.get("moa_landscape",""),
        long_term_safety=state.get("long_term_safety",""),
        competitive_dynamics=state.get("competitive_dynamics",""),
        investment_recommendation=state.get("investment_recommendation",""),
        ct_docs=ct_docs, fda_docs=fda_docs,
    )
    return {"investor_narrative": narrative, "progress_log": ["Static executive summary"], "errors": []}


# ─── Graph assembly ───────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("query_expansion",       node_query_expansion)
    graph.add_node("literature_synthesis",  node_literature_synthesis)
    graph.add_node("trial_mapping",         node_trial_mapping)
    graph.add_node("trial_critique_node",        node_trial_critique)
    graph.add_node("pipeline_regulatory_node",   node_pipeline_regulatory)
    graph.add_node("new_analytics",         node_new_analytics)
    graph.add_node("investment_recommendation_node", node_investment_recommendation)
    graph.add_node("investor_narrative_node",    node_investor_narrative)

    graph.set_entry_point("query_expansion")
    graph.add_edge("query_expansion",      "literature_synthesis")
    graph.add_edge("query_expansion",      "trial_mapping")
    graph.add_edge("literature_synthesis", "trial_critique_node")
    graph.add_edge("trial_mapping",        "trial_critique_node")
    graph.add_edge("trial_critique_node",       "pipeline_regulatory_node")
    graph.add_edge("pipeline_regulatory_node",  "new_analytics")
    graph.add_edge("new_analytics",        "investment_recommendation_node")
    graph.add_edge("investment_recommendation_node", "investor_narrative_node")
    graph.add_edge("investor_narrative_node",   END)

    return graph.compile()


biotech_agent = build_graph()
