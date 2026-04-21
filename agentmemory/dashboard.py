"""Web dashboard for browsing and managing AgentMemory.

Run with: agentmemory dashboard
Requires: pip install fastapi uvicorn
"""

from __future__ import annotations

from typing import Any

from .core import MemoryEngine, MemoryEntry

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
except ImportError as e:
    raise ImportError(
        "Dashboard requires fastapi. Install with: pip install fastapi uvicorn"
    ) from e

app = FastAPI(title="AgentMemory Dashboard", version="0.1.0")

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AgentMemory Dashboard</title>
<style>
  :root { --bg:#0f0f23; --panel:#1a1a2e; --text:#e0e0e0; --accent:#4cc9f0; --muted:#888; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); }
  header { padding:1rem 2rem; border-bottom:1px solid #333; display:flex; justify-content:space-between; align-items:center; }
  header h1 { margin:0; font-size:1.4rem; color:var(--accent); }
  .container { max-width:1200px; margin:0 auto; padding:1.5rem 2rem; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:1rem; margin-bottom:1.5rem; }
  .card { background:var(--panel); padding:1rem; border-radius:8px; }
  .card h3 { margin:0 0 .5rem; font-size:.85rem; text-transform:uppercase; color:var(--muted); }
  .card .big { font-size:1.8rem; font-weight:700; color:var(--accent); }
  .filters { display:flex; gap:.5rem; flex-wrap:wrap; margin-bottom:1rem; }
  .filters input, .filters select { padding:.5rem .8rem; border-radius:6px; border:none; background:var(--panel); color:var(--text); font-size:.9rem; }
  .filters button { padding:.5rem 1rem; border-radius:6px; border:none; background:var(--accent); color:#000; font-weight:600; cursor:pointer; }
  table { width:100%; border-collapse:collapse; font-size:.9rem; }
  th, td { text-align:left; padding:.6rem .8rem; border-bottom:1px solid #333; }
  th { color:var(--muted); text-transform:uppercase; font-size:.75rem; }
  .badge { display:inline-block; padding:.15rem .5rem; border-radius:4px; font-size:.75rem; font-weight:600; }
  .badge-fact { background:#2a4d3e; color:#4ade80; }
  .badge-decision { background:#3e3a2a; color:#facc15; }
  .badge-action { background:#2a3a4d; color:#60a5fa; }
  .badge-preference { background:#4d2a4d; color:#f472b6; }
  .badge-error { background:#4d2a2a; color:#f87171; }
  .confidence { font-size:.8rem; color:var(--muted); }
  .empty { color:var(--muted); padding:2rem; text-align:center; }
</style>
</head>
<body>
<header><h1>AgentMemory Dashboard</h1><span id="project-label"></span></header>
<div class="container">
  <div class="grid" id="stats"></div>
  <div class="filters">
    <input type="text" id="project-input" placeholder="Project name" value="">
    <input type="text" id="search-input" placeholder="Search memories...">
    <select id="category-filter"><option value="">All categories</option><option>fact</option><option>decision</option><option>action</option><option>preference</option><option>error</option></select>
    <button onclick="loadData()">Load</button>
    <button onclick="captureMemory()">+ Capture</button>
  </div>
  <div id="memories"></div>
</div>
<script>
let currentProject = '';

async function fetchJSON(url) { const r=await fetch(url); return r.json(); }

async function loadStats(project) {
  const data = await fetchJSON('/api/stats?project='+encodeURIComponent(project));
  const el=document.getElementById('stats');
  el.innerHTML=`
    <div class="card"><h3>Total Memories</h3><div class="big">${data.total_memories||0}</div></div>
    <div class="card"><h3>Projects</h3><div class="big">${data.projects||0}</div></div>
    <div class="card"><h3>Sessions</h3><div class="big">${data.sessions||0}</div></div>
    <div class="card"><h3>Categories</h3><div class="big">${Object.keys(data.by_category||{}).length}</div></div>
  `;
}

async function loadMemories(project, keyword='', category='') {
  currentProject = project;
  document.getElementById('project-label').textContent = project || 'All projects';
  let url = '/api/memories?project='+encodeURIComponent(project);
  if(category) url += '&category='+encodeURIComponent(category);
  if(keyword) url = '/api/search?project='+encodeURIComponent(project)+'&keyword='+encodeURIComponent(keyword);
  const data = await fetchJSON(url);
  const memories = data.memories || data.results || [];
  const el=document.getElementById('memories');
  if(!memories.length){ el.innerHTML='<div class="empty">No memories found.</div>'; return; }
  let html='<table><tr><th>ID</th><th>Category</th><th>Content</th><th>Source</th><th>Time</th></tr>';
  for(const m of memories){
    html+=`<tr>
      <td>#${m.id}</td>
      <td><span class="badge badge-${m.category}">${m.category}</span></td>
      <td>${m.content.substring(0,120)}${m.content.length>120?'...':''}<br><span class="confidence">confidence: ${(m.confidence||1).toFixed(2)}</span></td>
      <td>${m.source||'-'}</td>
      <td>${(m.timestamp||'').replace('T',' ').substring(0,16)}</td>
    </tr>`;
  }
  html+='</table>';
  el.innerHTML=html;
}

async function loadData(){
  const p=document.getElementById('project-input').value;
  const k=document.getElementById('search-input').value;
  const c=document.getElementById('category-filter').value;
  await loadStats(p);
  await loadMemories(p,k,c);
}

async function captureMemory(){
  const p=prompt('Project:', currentProject); if(!p) return;
  const content=prompt('Memory content:'); if(!content) return;
  const category=prompt('Category (fact/decision/action/preference/error):','fact')||'fact';
  await fetch('/api/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:p,content,category})});
  loadData();
}

loadData();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.get("/api/stats")
def api_stats(project: str = "") -> dict[str, Any]:
    engine = MemoryEngine()
    data = engine.stats()
    if project:
        data["project_memories"] = len(engine.recall(project=project, limit=10000))
    return data


@app.get("/api/memories")
def api_memories(
    project: str = "",
    category: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    engine = MemoryEngine()
    memories = engine.recall(
        project=project or None,
        category=category or None,
        limit=limit,
    )
    return {
        "memories": [
            {
                "id": m.id,
                "content": m.content,
                "category": m.category,
                "confidence": m.confidence,
                "source": m.source,
                "tags": m.tags,
                "timestamp": m.timestamp,
                "session_id": m.session_id,
            }
            for m in memories
        ]
    }


@app.get("/api/search")
def api_search(
    project: str = "",
    keyword: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    engine = MemoryEngine()
    results = engine.search(keyword, project=project or None, limit=limit)
    return {
        "results": [
            {
                "id": m.id,
                "content": m.content,
                "category": m.category,
                "confidence": m.confidence,
                "source": m.source,
                "tags": m.tags,
                "timestamp": m.timestamp,
            }
            for m in results
        ]
    }


@app.post("/api/capture")
def api_capture(payload: dict[str, Any]) -> dict[str, Any]:
    engine = MemoryEngine()
    import os
    import uuid

    project = payload.get("project", "default")
    entry = MemoryEntry(
        project=project,
        session_id=os.environ.get("AGENTMEMORY_SESSION", str(uuid.uuid4())[:8]),
        category=payload.get("category", "fact"),
        content=payload["content"],
        confidence=payload.get("confidence", 1.0),
        source=payload.get("source", "dashboard"),
        tags=payload.get("tags", ""),
    )
    memory_id = engine.store(entry)
    return {"status": "stored", "memory_id": memory_id}


@app.get("/api/projects")
def api_projects() -> dict[str, Any]:
    engine = MemoryEngine()
    # Fetch distinct projects from DB
    conn = engine._connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT project FROM memories ORDER BY project"
        ).fetchall()
        return {"projects": [row["project"] for row in rows]}
    finally:
        engine._close(conn)


@app.get("/api/graph")
def api_graph(
    project: str = "",
    backend: str = "tfidf",
) -> dict[str, Any]:
    from .graph import build_memory_graph

    engine = MemoryEngine()
    return build_memory_graph(engine, project or "default", backend=backend)


@app.get("/api/timeline")
def api_timeline(
    project: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    from .graph import get_timeline

    engine = MemoryEngine()
    return {"timeline": get_timeline(engine, project or "default", limit=limit)}


@app.get("/api/clusters")
def api_clusters(
    project: str = "",
) -> dict[str, Any]:
    from .graph import get_category_clusters

    engine = MemoryEngine()
    return get_category_clusters(engine, project or "default")


def run_dashboard(host: str = "127.0.0.1", port: int = 8745) -> None:
    """Run the dashboard server."""
    try:
        import uvicorn
    except ImportError as e:
        raise ImportError(
            "Dashboard requires uvicorn. Install with: pip install uvicorn"
        ) from e

    uvicorn.run(app, host=host, port=port, log_level="warning")
