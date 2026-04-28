"""
Main pipeline orchestrator: ties retrieval → LangGraph agent → infographics → report.
Can be run as a standalone script or imported by the FastAPI server.
"""
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from retrievers.data_retriever import retrieve_all
from retrievers.mock_data import get_mock_data
from agents.research_agent import biotech_agent, AgentState
from reports.infographics import generate_all_charts
from reports.report_generator import generate_html_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _docs_to_dicts(doc_list) -> list:
    """Convert Document objects or dicts to plain dicts safely."""
    result = []
    for d in doc_list:
        if hasattr(d, "to_dict"):
            result.append(d.to_dict())
        elif isinstance(d, dict):
            result.append(d)
    return result


async def run_pipeline(query: str, progress_callback=None) -> dict:
    """
    Full pipeline: query -> retrieve -> agent -> charts -> report.
    Returns dict with 'html', 'state', 'charts', 'retrieval_stats'.
    """
    def progress(msg: str):
        logger.info(msg)
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass

    start = time.time()
    progress(f"Starting pipeline for: {query}")

    # Step 1: Data retrieval
    progress("Retrieving from PubMed, ClinicalTrials.gov, Semantic Scholar, FDA, bioRxiv...")
    try:
        retrieval_data = await retrieve_all([query])
    except Exception as e:
        logger.warning(f"Retrieval error: {e}")
        retrieval_data = {
            "total_count": 0, "all_documents": [], "pubmed": [],
            "clinical_trials": [], "fda": [], "semantic_scholar": [], "biorxiv": [],
            "stats": {"pubmed": 0, "clinical_trials": 0, "fda": 0, "semantic_scholar": 0, "biorxiv": 0}
        }

    # Fallback to curated database if live APIs unavailable
    if retrieval_data["total_count"] == 0:
        progress("Live APIs unavailable — checking curated research database...")
        retrieval_data = get_mock_data(query)
        matched = retrieval_data.get("matched_disease")
        if matched:
            progress(f"Matched curated dataset: '{matched}' ({retrieval_data['total_count']} documents)")
        else:
            progress(f"No curated match for '{query}' — report will note data limitations.")
    else:
        s = retrieval_data["stats"]
        progress(f"Retrieved {retrieval_data['total_count']} docs — "
                 f"PubMed:{s['pubmed']} Trials:{s['clinical_trials']} FDA:{s['fda']} SS:{s['semantic_scholar']}")

    # Step 2: Build initial agent state
    progress("Building agent state...")
    initial_state = {
        "query": query,
        "query_terms": [query],
        "mesh_terms": [],
        "icd_codes": [],
        "all_documents": _docs_to_dicts(retrieval_data["all_documents"]),
        "clinical_trials": _docs_to_dicts(retrieval_data["clinical_trials"]),
        "fda_docs": _docs_to_dicts(retrieval_data["fda"]),
        "pubmed_docs": _docs_to_dicts(retrieval_data["pubmed"]),
        "scientific_summary": "",
        "trial_landscape": "",
        "trial_landscape_structured": [],
        "trial_critique": "",
        "pipeline_regulatory": "",
        "competitive_landscape": "",
        "investor_narrative": "",
        "market_sizing": "",
        "pricing_reimbursement": "",
        "patient_stratification": "",
        "moa_landscape": "",
        "long_term_safety": "",
        "competitive_dynamics": "",
        "investment_recommendation": "",
        "progress_log": [],
        "errors": [],
    }

    # Step 3: Run LangGraph agent
    progress("Running LangGraph agent (6 nodes: expansion, synthesis, trials, critique, pipeline, narrative)...")
    config = {"recursion_limit": 50}
    try:
        final_state = biotech_agent.invoke(initial_state, config=config)
    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise

    for log_entry in final_state.get("progress_log", []):
        progress(f"  [agent] {log_entry}")
    for err in final_state.get("errors", []):
        logger.warning(f"  [agent warn] {err}")

    progress("Agent complete.")

    # Step 4: Generate infographics
    progress("Generating charts (Gantt, heatmap, phase distribution, sponsor chart)...")
    trials_structured = final_state.get("trial_landscape_structured", [])

    # Rebuild from raw if node didn't populate structured list
    if not trials_structured:
        trials_structured = [
            {
                "nct_id": d.get("metadata", {}).get("nct_id", ""),
                "title": d.get("title", ""),
                "phase": d.get("metadata", {}).get("phase", "N/A"),
                "status": d.get("metadata", {}).get("status", "N/A"),
                "enrollment": d.get("metadata", {}).get("enrollment", "N/A"),
                "sponsor": d.get("metadata", {}).get("sponsor", "N/A"),
                "interventions": d.get("metadata", {}).get("interventions", []),
                "primary_outcomes": d.get("metadata", {}).get("primary_outcomes", []),
                "start_date": d.get("metadata", {}).get("start_date", ""),
                "completion_date": d.get("metadata", {}).get("completion_date", ""),
                "conditions": d.get("metadata", {}).get("conditions", []),
            }
            for d in initial_state["clinical_trials"]
        ]

    charts = generate_all_charts(trials_structured, query, fda_docs=_docs_to_dicts(retrieval_data['fda']))
    n_charts = sum(1 for v in charts.values() if v)
    progress(f"Generated {n_charts}/4 charts.")

    # Step 5: Assemble HTML report
    progress("Assembling investor report HTML...")
    html_report = generate_html_report(
        query=query,
        agent_state=final_state,
        charts=charts,
        retrieval_stats=retrieval_data,
        trials=trials_structured,
    )

    elapsed = time.time() - start
    progress(f"Done — {len(html_report) // 1024}KB report in {elapsed:.1f}s")

    return {
        "html": html_report,
        "state": final_state,
        "charts": charts,
        "retrieval_stats": retrieval_data,
        "elapsed_seconds": elapsed,
    }


def run_sync(query: str, progress_callback=None) -> dict:
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import nest_asyncio; nest_asyncio.apply()
        return loop.run_until_complete(run_pipeline(query, progress_callback=progress_callback))
    else:
        return asyncio.run(run_pipeline(query, progress_callback=progress_callback))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Biotech Research Agent")
    parser.add_argument("query", help="Disease or treatment (e.g. 'Alzheimer disease')")
    parser.add_argument("--output", default="report.html", help="Output HTML file")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    result = run_sync(args.query, progress_callback=lambda m: print(f"  {m}"))
    Path(args.output).write_text(result["html"], encoding="utf-8")
    print(f"\nSaved: {args.output} ({len(result['html'])//1024}KB) in {result['elapsed_seconds']:.1f}s")
