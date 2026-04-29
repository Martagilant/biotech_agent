# 🧬 Invivo Partners — Biotech Research Agent

> Investment-grade biotech research reports, generated in minutes.

[![Run Tests](https://github.com/Martagilant/biotech_agent/actions/workflows/test.yml/badge.svg)](https://github.com/Martagilant/biotech_agent/actions)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Martagilant/biotech_agent)

Type a disease name. Get a 12-section investor-grade HTML report with 14 charts, real clinical trial data, market sizing, competitive dynamics, and a named investment recommendation — in under 30 seconds from the curated database, or 3–6 minutes with a live API key.

---

## ⚡ Quickest start: GitHub Codespaces (no local setup)

1. Click **"Open in GitHub Codespaces"** badge above (or: Code → Codespaces → New codespace)
2. Wait ~60 seconds for the environment to build
3. Open `biotech_agent_notebook.ipynb` from the repo root
4. Run Cell 1 → Cell 2 → type your disease name

That's it. No local Python install, no dependency conflicts.

---

## 💻 Local setup (5 minutes)

### Prerequisites
- Python 3.10 or 3.11
- Git

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/Martagilant/biotech_agent.git
cd biotech_agent

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch Jupyter from the repo root (important — the notebook must
#    be run from here so that the biotech_agent/ package is importable)
jupyter notebook biotech_agent_notebook.ipynb
```

Your browser will open the notebook. Run the cells top to bottom.

> **Important:** Always launch Jupyter from the repo root directory (the folder containing `biotech_agent_notebook.ipynb` and the `biotech_agent/` subfolder). Do not move the notebook into the `biotech_agent/` subdirectory — the import paths depend on this layout.

---

## 🔑 API Key (optional — but unlocks all diseases)

**Without a key:** Works perfectly for the 13 curated diseases listed below, in ~30 seconds.

**With a key:** Works for *any* disease using live data from PubMed, ClinicalTrials.gov, Semantic Scholar, OpenFDA, and bioRxiv. Typical runtime: 3–6 minutes.

Get a free key at [console.anthropic.com](https://console.anthropic.com) — takes 2 minutes.

### How to set the key

**Option A — Environment variable** (recommended for local use):
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here   # Mac/Linux
set ANTHROPIC_API_KEY=sk-ant-your-key-here       # Windows
```

**Option B — In Cell 4 of the notebook** (paste and run, but do not commit):
```python
key = 'sk-ant-your-key-here'
```

**Option C — GitHub Codespaces secret** (most secure, persists across sessions):
1. Go to github.com → Settings → Codespaces → Secrets
2. Add `ANTHROPIC_API_KEY` with your key value
3. The secret is automatically available in every Codespace for this repo

---

## 🧪 Curated diseases (no API key needed)

Full 12-section reports with real trial data, market sizing, and investment intel:

| Disease | Key assets covered | Trials |
|---------|-------------------|--------|
| Alzheimer's disease | Lecanemab, donanemab, buntanetap, trontinemab, EVOKE | 15 |
| KRAS inhibitors | Sotorasib, adagrasib, RMC-6236, MRTX1133 | 11 |
| GLP-1 / obesity | Tirzepatide, orforglipron, CagriSema, retatrutide | 9 |
| Rheumatoid arthritis | Upadacitinib, deucravacitinib, nipocalimab | 8 |
| CAR-T cell therapy | Carvykti, CARTITUDE-5, allogeneic CAR-T | 9 |
| NASH / liver fibrosis | Resmetirom (approved), efruxifermin, pegozafermin | 9 |
| Sickle cell disease | Casgevy (CRISPR), mitapivat, inclacumab | 9 |
| Multiple sclerosis | Tolebrutinib, fenebrutinib, ublituximab | 9 |
| Atopic dermatitis | Dupilumab, amlitelimab, povorcitinib, orismilast | 10 |
| Glioblastoma | Vorasidenib, DCVax-L, TTFields combos | 9 |
| Spinal muscular atrophy | Nusinersen, risdiplam, apitegromab | 8 |
| Pancreatic cancer | FOLFIRINOX, olaparib, RMC-6236, mRNA-5671 | 12 |
| ALS / Lou Gehrig's | Tofersen, WVE-004, pridopidine (AMX0035 withdrawn) | 15 |

You can search by drug name too — `"tofersen"`, `"buntanetap"`, `"RMC-6236"` all match the right disease.

---

## 📊 What's in each report

Every report has 12 sections and 14 charts:

**Sections:**
1. Executive Summary — Invivo Partners verdict and investment stage
2. Scientific Summary — evidence quality and key mechanistic findings
3. Clinical Trial Landscape — full register table with all real NCT IDs
4. Market Sizing — TAM/SAM, patient funnel, new-entrant revenue ceiling
5. Pricing & Reimbursement — asset pricing, payor dynamics, biosimilar timeline
6. Patient Stratification — biomarkers, subpopulations, unmet need
7. Mechanism of Action Landscape — competitive map table by mechanism class
8. Critical Trial Analysis — asset-specific differential critique (not boilerplate)
9. Long-term Safety & Durability — 2-5yr signals, discontinuation rates
10. Pipeline & Regulatory — FDA-approved drugs, binary events calendar
11. Competitive Dynamics & M&A — franchise logic, acquisition targets, patent cliff
12. Investment Recommendation — named assets, pass/invest criteria, 5 diligence questions

**Charts (14 per report):**
Phase distribution · Stage funnel · Gantt timeline · Enrollment trend · Regulatory swimlane · Binary events calendar · MOA diversity · Sponsor chart · Radar quality profile · Quality heatmap · Waterfall ranking · Bubble chart · Risk-return matrix · Endpoint heatmap

---

## 🏗️ Project structure

```
biotech_agent/                        ← repo root, run Jupyter from here
├── biotech_agent_notebook.ipynb      ← start here
├── requirements.txt
├── biotech_agent/                    ← Python package
│   ├── __init__.py
│   ├── pipeline.py                   ← report orchestrator + CLI
│   ├── server.py                     ← FastAPI web server
│   ├── retrievers/
│   │   ├── data_retriever.py         ← PubMed, ClinicalTrials.gov, Semantic Scholar...
│   │   └── mock_data.py              ← 13-disease curated database (119 real trials)
│   ├── agents/
│   │   └── research_agent.py         ← LangGraph 6-node DAG
│   └── reports/
│       ├── infographics.py           ← 14 Matplotlib charts
│       └── report_generator.py       ← HTML report template
├── outputs/                          ← generated reports saved here
├── .devcontainer/                    ← GitHub Codespaces config
└── .github/workflows/                ← CI tests
```

---

## 🖥️ Alternative: Web interface

Instead of Jupyter, you can run a streaming web UI:

```bash
cd biotech_agent
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 — type any disease and watch progress stream in real time. The completed report opens in a new tab.

---

## ⚠️ Important notes

**Data integrity:** Every NCT trial ID, sponsor name, and trial result in the curated database is real. The agent never fabricates clinical data. For unknown diseases without live API access, it shows a clear "data not available" notice rather than invented content.

**Market figures:** The TAM and pricing numbers are directionally accurate estimates for framing purposes. For investment committee precision, verify against Evaluate Pharma, IQVIA, or GlobalData.

**Not investment advice:** This tool is for research and analysis. Always conduct independent due diligence before any investment decision.

---

## 📝 License

MIT — use freely, attribution appreciated.
