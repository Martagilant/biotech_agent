"""
FastAPI server with Server-Sent Events (SSE) streaming progress.
Single input endpoint: POST /stream-report  {"query": "disease name"}
"""
import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from pipeline import run_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Biotech Research Agent",
    description="AI-powered biotech research report generator for VC investors",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory report store — keyed by report_id UUID.
# Reports are served via GET /report/{report_id} to avoid embedding
# large HTML payloads (500KB–1MB) in a single SSE data line, which
# exceeds nginx/browser SSE buffer limits and silently truncates.
_report_store: dict[str, str] = {}

PIPELINE_TIMEOUT_SECONDS = 600  # 10-minute hard cap


class ReportRequest(BaseModel):
    query: str


# ── Landing page ──────────────────────────────────────────────────────────────
LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Biotech Research Agent</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Lora:wght@600&family=Inter:wght@300;400;500;600&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', sans-serif;
    background: #FAFAF8;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px 16px;
    color: #1A1917;
  }
  .logo { font-family: 'Lora', Georgia, serif; font-size: 13px; font-weight: 600; letter-spacing: 0.15em; text-transform: uppercase; color: #1D9E75; margin-bottom: 32px; }
  h1 { font-family: 'Lora', serif; font-size: 40px; font-weight: 600; text-align: center; line-height: 1.2; max-width: 580px; margin-bottom: 16px; }
  p.sub { font-size: 15px; color: #5F5E5A; text-align: center; max-width: 480px; margin-bottom: 40px; line-height: 1.6; }
  .card {
    background: white;
    border: 1px solid #E8E6DF;
    border-radius: 16px;
    padding: 40px 48px;
    width: 100%;
    max-width: 560px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.04);
  }
  label { display: block; font-size: 12px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #5F5E5A; margin-bottom: 10px; }
  input[type="text"] {
    width: 100%;
    padding: 14px 18px;
    font-size: 16px;
    font-family: 'Inter', sans-serif;
    border: 1.5px solid #D3D1C7;
    border-radius: 10px;
    outline: none;
    background: #FAFAF8;
    color: #1A1917;
    transition: border-color 0.15s;
    margin-bottom: 16px;
  }
  input[type="text"]:focus { border-color: #1D9E75; background: white; }
  button {
    width: 100%;
    padding: 15px;
    font-size: 15px;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
    background: #1D9E75;
    color: white;
    border: none;
    border-radius: 10px;
    cursor: pointer;
    transition: background 0.15s, transform 0.1s;
    letter-spacing: 0.01em;
  }
  button:hover { background: #0F6E56; }
  button:active { transform: scale(0.98); }
  button:disabled { background: #9FE1CB; cursor: not-allowed; transform: none; }
  .examples { margin-top: 24px; }
  .examples p { font-size: 12px; color: #888780; margin-bottom: 10px; }
  .example-tags { display: flex; flex-wrap: wrap; gap: 8px; }
  .tag {
    padding: 5px 14px;
    background: #F1EFE8;
    border-radius: 20px;
    font-size: 12px;
    cursor: pointer;
    color: #3d3d3a;
    border: 1px solid #E8E6DF;
    transition: all 0.15s;
  }
  .tag:hover { background: #E1F5EE; border-color: #9FE1CB; color: #0F6E56; }
  #progress-overlay {
    display: none;
    position: fixed; inset: 0;
    background: rgba(250,250,248,0.95);
    z-index: 100;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px;
  }
  #progress-overlay.active { display: flex; }
  .spinner {
    width: 44px; height: 44px;
    border: 3px solid #E8E6DF;
    border-top-color: #1D9E75;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-bottom: 24px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  #progress-title { font-family: 'Lora', serif; font-size: 22px; font-weight: 600; margin-bottom: 12px; }
  #progress-log {
    max-width: 500px;
    width: 100%;
    background: white;
    border: 1px solid #E8E6DF;
    border-radius: 10px;
    padding: 16px 20px;
    font-size: 12px;
    font-family: monospace;
    color: #5F5E5A;
    max-height: 200px;
    overflow-y: auto;
    margin-top: 12px;
  }
  .log-line { padding: 2px 0; border-bottom: 1px solid #F1EFE8; }
  .log-line:last-child { border-bottom: none; }
  .log-line::before { content: '→ '; color: #1D9E75; }
</style>
</head>
<body>
  <div class="logo">⬡ Biotech Intelligence</div>
  <h1>Investor-grade research, on demand</h1>
  <p class="sub">Enter any disease or treatment. Our AI agent retrieves current scientific literature, maps the clinical pipeline, and generates a VC-ready briefing document in minutes.</p>

  <div class="card">
    <label for="query-input">Disease or treatment</label>
    <input type="text" id="query-input" placeholder="e.g. Alzheimer disease, GLP-1 agonists, KRAS inhibitors..." autocomplete="off"/>
    <button id="generate-btn" onclick="generateReport()">Generate Investor Report →</button>
    <div class="examples">
      <p>Try an example:</p>
      <div class="example-tags">
        <span class="tag" onclick="setQuery('Alzheimer disease')">Alzheimer disease</span>
        <span class="tag" onclick="setQuery('GLP-1 receptor agonists')">GLP-1 agonists</span>
        <span class="tag" onclick="setQuery('KRAS G12C inhibitors')">KRAS inhibitors</span>
        <span class="tag" onclick="setQuery('CAR-T cell therapy')">CAR-T therapy</span>
        <span class="tag" onclick="setQuery('NASH fibrosis')">NASH fibrosis</span>
        <span class="tag" onclick="setQuery('sickle cell disease gene therapy')">Sickle cell gene therapy</span>
      </div>
    </div>
  </div>

  <div id="progress-overlay">
    <div class="spinner"></div>
    <div id="progress-title">Generating report…</div>
    <div style="font-size:13px;color:#888;margin-bottom:16px;">This typically takes 3–6 minutes</div>
    <div id="progress-log"></div>
  </div>

  <script>
    function setQuery(text) {
      document.getElementById('query-input').value = text;
      document.getElementById('query-input').focus();
    }

    function addLog(msg) {
      const log = document.getElementById('progress-log');
      const line = document.createElement('div');
      line.className = 'log-line';
      line.textContent = msg;
      log.appendChild(line);
      log.scrollTop = log.scrollHeight;
    }

    async function generateReport() {
      const query = document.getElementById('query-input').value.trim();
      if (!query) { alert('Please enter a disease or treatment name.'); return; }

      const btn = document.getElementById('generate-btn');
      btn.disabled = true;
      btn.textContent = 'Generating…';

      const overlay = document.getElementById('progress-overlay');
      overlay.classList.add('active');
      document.getElementById('progress-title').textContent = `Researching: ${query}`;
      document.getElementById('progress-log').innerHTML = '';

      try {
        const response = await fetch('/stream-report', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({query})
        });

        if (!response.ok) throw new Error(`Server error: ${response.status}`);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let reportId = null;

        while (true) {
          const {done, value} = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, {stream: true});
          const lines = buffer.split('\\n');
          buffer = lines.pop();
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const parsed = JSON.parse(line.slice(6));
              if (parsed.type === 'progress') {
                addLog(parsed.message);
              } else if (parsed.type === 'complete') {
                reportId = parsed.report_id;
              } else if (parsed.type === 'error') {
                throw new Error(parsed.message);
              }
            } catch(e) { /* malformed line, skip */ }
          }
        }

        if (reportId) {
          // Fetch the report HTML from the store endpoint and open in new tab
          window.open(`/report/${reportId}`, '_blank');
        }
      } catch(err) {
        addLog('Error: ' + err.message);
        alert('An error occurred: ' + err.message);
      } finally {
        overlay.classList.remove('active');
        btn.disabled = false;
        btn.textContent = 'Generate Investor Report →';
      }
    }

    document.addEventListener('DOMContentLoaded', () => {
      document.getElementById('query-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') generateReport();
      });
    });
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def landing():
    return HTMLResponse(content=LANDING_HTML)


@app.post("/stream-report")
async def stream_report(request: ReportRequest):
    """
    SSE endpoint: streams progress events, then emits a 'complete' event
    containing only a report_id. The full HTML is stored server-side and
    served via GET /report/{report_id} to avoid SSE buffer overflow on
    large reports (500KB–1MB with embedded base64 chart images).
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if len(query) > 200:
        raise HTTPException(status_code=400, detail="Query too long")

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()

        def progress_cb(msg: str):
            # Called from within the same event loop (create_task, not thread),
            # so put_nowait is safe and avoids the run_coroutine_threadsafe pattern.
            try:
                queue.put_nowait({"type": "progress", "message": msg})
            except asyncio.QueueFull:
                pass

        async def run_with_progress():
            try:
                result = await run_pipeline(query, progress_callback=progress_cb)
                report_id = str(uuid.uuid4())
                _report_store[report_id] = result["html"]
                queue.put_nowait({"type": "complete", "report_id": report_id})
            except Exception as e:
                logger.exception(f"Pipeline error for query '{query}': {e}")
                queue.put_nowait({"type": "error", "message": str(e)})
            finally:
                queue.put_nowait(None)  # sentinel

        task = asyncio.create_task(run_with_progress())

        try:
            # Apply a hard timeout to the entire pipeline run
            deadline = asyncio.get_event_loop().time() + PIPELINE_TIMEOUT_SECONDS

            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    task.cancel()
                    yield 'data: {"type": "error", "message": "Pipeline timed out after 10 minutes"}\n\n'
                    break

                try:
                    item = await asyncio.wait_for(queue.get(), timeout=min(30.0, remaining))
                except asyncio.TimeoutError:
                    yield 'data: {"type": "progress", "message": "Still working..."}\n\n'
                    continue

                if item is None:
                    break

                yield f"data: {json.dumps(item)}\n\n"

                if item.get("type") in ("complete", "error"):
                    break

        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/report/{report_id}", response_class=HTMLResponse)
async def get_report(report_id: str):
    """
    Serve a generated report by ID. Reports are stored in memory for the
    lifetime of the server process. In production, swap _report_store for
    Redis with a TTL (e.g. 24h).
    """
    html = _report_store.get(report_id)
    if not html:
        raise HTTPException(status_code=404, detail="Report not found or expired")
    return HTMLResponse(content=html)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "reports_in_memory": len(_report_store),
    }
