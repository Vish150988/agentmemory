"""Web dashboard for browsing and managing CrossAgentMemory.

Run with: crossagentmemory dashboard
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

app = FastAPI(title="crossagentmemory dashboard", version="0.1.0")

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>crossagentmemory dashboard</title>
<style>
  :root[data-theme="dark"] {
    --bg:#0f0f23; --panel:#1a1a2e; --text:#e0e0e0; --accent:#4cc9f0;
    --muted:#888; --border:#333; --success:#4ade80; --danger:#f87171;
    --badge-fact-bg:#2a4d3e; --badge-fact-text:#4ade80;
    --badge-decision-bg:#3e3a2a; --badge-decision-text:#facc15;
    --badge-action-bg:#2a3a4d; --badge-action-text:#60a5fa;
    --badge-preference-bg:#4d2a4d; --badge-preference-text:#f472b6;
    --badge-error-bg:#4d2a2a; --badge-error-text:#f87171;
  }
  :root[data-theme="light"] {
    --bg:#f8f9fa; --panel:#ffffff; --text:#212529; --accent:#0d6efd;
    --muted:#6c757d; --border:#dee2e6; --success:#198754; --danger:#dc3545;
    --badge-fact-bg:#d1e7dd; --badge-fact-text:#0f5132;
    --badge-decision-bg:#fff3cd; --badge-decision-text:#664d03;
    --badge-action-bg:#cfe2ff; --badge-action-text:#084298;
    --badge-preference-bg:#f8d7da; --badge-preference-text:#842029;
    --badge-error-bg:#f5c2c7; --badge-error-text:#58151c;
  }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); transition:background .2s,color .2s; }
  header { padding:1rem 2rem; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:.5rem; }
  header h1 { margin:0; font-size:1.4rem; color:var(--accent); }
  .container { max-width:1400px; margin:0 auto; padding:1.5rem 2rem; display:grid; grid-template-columns:1fr 300px; gap:1.5rem; }
  @media (max-width:900px){ .container{ grid-template-columns:1fr; } }
  .main { min-width:0; }
  .sidebar { display:flex; flex-direction:column; gap:1rem; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:1rem; margin-bottom:1.5rem; }
  .card { background:var(--panel); padding:1rem; border-radius:8px; border:1px solid var(--border); }
  .card h3 { margin:0 0 .5rem; font-size:.75rem; text-transform:uppercase; color:var(--muted); }
  .card .big { font-size:1.6rem; font-weight:700; color:var(--accent); }
  .filters { display:flex; gap:.5rem; flex-wrap:wrap; margin-bottom:1rem; align-items:center; }
  .filters input, .filters select { padding:.5rem .8rem; border-radius:6px; border:1px solid var(--border); background:var(--panel); color:var(--text); font-size:.9rem; }
  .filters button { padding:.5rem 1rem; border-radius:6px; border:none; background:var(--accent); color:#fff; font-weight:600; cursor:pointer; }
  .filters button.secondary { background:transparent; color:var(--accent); border:1px solid var(--accent); }
  table { width:100%; border-collapse:collapse; font-size:.9rem; }
  th, td { text-align:left; padding:.6rem .8rem; border-bottom:1px solid var(--border); }
  th { color:var(--muted); text-transform:uppercase; font-size:.75rem; cursor:pointer; user-select:none; }
  th:hover { color:var(--accent); }
  th .sort-indicator { margin-left:.3rem; font-size:.6rem; opacity:.6; }
  .badge { display:inline-block; padding:.15rem .5rem; border-radius:4px; font-size:.75rem; font-weight:600; }
  .badge-fact { background:var(--badge-fact-bg); color:var(--badge-fact-text); }
  .badge-decision { background:var(--badge-decision-bg); color:var(--badge-decision-text); }
  .badge-action { background:var(--badge-action-bg); color:var(--badge-action-text); }
  .badge-preference { background:var(--badge-preference-bg); color:var(--badge-preference-text); }
  .badge-error { background:var(--badge-error-bg); color:var(--badge-error-text); }
  .confidence { font-size:.8rem; color:var(--muted); }
  .empty { color:var(--muted); padding:2rem; text-align:center; }
  .recent-item { padding:.6rem; border-bottom:1px solid var(--border); font-size:.85rem; }
  .recent-item .meta { font-size:.75rem; color:var(--muted); margin-top:.2rem; }
  .recent-item .cat { font-size:.7rem; text-transform:uppercase; font-weight:600; }
  .delete-btn { background:var(--danger); color:#fff; border:none; border-radius:4px; padding:.2rem .5rem; font-size:.75rem; cursor:pointer; }
  .theme-toggle { background:var(--panel); border:1px solid var(--border); color:var(--text); padding:.4rem .8rem; border-radius:6px; cursor:pointer; font-size:.85rem; }
  .refresh-indicator { font-size:.75rem; color:var(--muted); margin-left:auto; }
</style>
</head>
<body>
<header>
  <h1>crossagentmemory dashboard</h1>
  <span id="project-label" style="color:var(--muted);font-size:.9rem;"></span>
  <span class="refresh-indicator" id="refresh-indicator"></span>
  <button class="theme-toggle" onclick="toggleTheme()">🌓 Theme</button>
</header>
<div class="container">
  <div class="main">
    <div class="grid" id="stats"></div>
    <div class="filters">
      <select id="project-select"><option value="">All projects</option></select>
      <input type="text" id="search-input" placeholder="Search memories...">
      <select id="category-filter"><option value="">All categories</option><option>fact</option><option>decision</option><option>action</option><option>preference</option><option>error</option></select>
      <button onclick="loadData()">Load</button>
      <button onclick="exportJSON()">⬇ Export JSON</button>
      <button class="secondary" onclick="captureMemory()">+ Capture</button>
    </div>
    <div id="memories"></div>
  </div>
  <div class="sidebar">
    <div class="card"><h3>Recent Captures</h3><div id="recent"></div></div>
    <div class="card"><h3>Projects</h3><div id="project-list"></div></div>
  </div>
</div>
<script>
let currentProject = '';
let autoRefresh = null;
let currentSort = { column: 'id', direction: 'asc' };
let allMemories = [];

function getTheme(){ return localStorage.getItem('theme') || 'dark'; }
function setTheme(t){ document.documentElement.setAttribute('data-theme', t); localStorage.setItem('theme', t); }
function toggleTheme(){ setTheme(getTheme()==='dark' ? 'light' : 'dark'); }
setTheme(getTheme());

async function fetchJSON(url) { const r=await fetch(url); return r.json(); }

async function loadProjects() {
  const data = await fetchJSON('/api/projects');
  const sel = document.getElementById('project-select');
  sel.innerHTML = '<option value="">All projects</option>';
  (data.projects || []).forEach(p => {
    const opt = document.createElement('option'); opt.value = p; opt.textContent = p;
    sel.appendChild(opt);
  });
  const list = document.getElementById('project-list');
  if(!data.projects.length){ list.innerHTML='<div class="empty">No projects</div>'; return; }
  list.innerHTML = (data.projects || []).map(p => `<div class="recent-item" style="cursor:pointer;" onclick="selectProject('${p.replace(/'/g,"\\'")}')">${p}</div>`).join('');
}

function selectProject(p) {
  document.getElementById('project-select').value = p;
  loadData();
}

function computeStats(memories) {
  const byCategory = {};
  memories.forEach(m => {
    byCategory[m.category] = (byCategory[m.category] || 0) + 1;
  });
  const sessions = new Set(memories.map(m => m.session_id).filter(Boolean));
  return {
    total_memories: memories.length,
    projects: new Set(memories.map(m => m.project)).size,
    sessions: sessions.size,
    by_category: byCategory
  };
}

function renderStats(stats) {
  const el = document.getElementById('stats');
  el.innerHTML = `
    <div class="card"><h3>Total Memories</h3><div class="big">${stats.total_memories||0}</div></div>
    <div class="card"><h3>Projects</h3><div class="big">${stats.projects||0}</div></div>
    <div class="card"><h3>Sessions</h3><div class="big">${stats.sessions||0}</div></div>
    <div class="card"><h3>Categories</h3><div class="big">${Object.keys(stats.by_category||{}).length}</div></div>
  `;
}

async function loadRecent() {
  const data = await fetchJSON('/api/memories?limit=5');
  const el = document.getElementById('recent');
  const mems = data.memories || [];
  if(!mems.length){ el.innerHTML='<div class="empty">No memories yet</div>'; return; }
  el.innerHTML = mems.map(m => `
    <div class="recent-item">
      <span class="cat badge badge-${m.category}">${m.category}</span>
      <div>${m.content.substring(0,60)}${m.content.length>60?'...':''}</div>
      <div class="meta">#${m.id} · ${(m.timestamp||'').replace('T',' ').substring(0,16)}</div>
    </div>
  `).join('');
}

function sortMemories(memories, column, direction) {
  return [...memories].sort((a, b) => {
    let va = a[column] || '';
    let vb = b[column] || '';
    if (column === 'id' || column === 'confidence') {
      va = parseFloat(va) || 0;
      vb = parseFloat(vb) || 0;
    } else {
      va = String(va).toLowerCase();
      vb = String(vb).toLowerCase();
    }
    if (va < vb) return direction === 'asc' ? -1 : 1;
    if (va > vb) return direction === 'asc' ? 1 : -1;
    return 0;
  });
}

function toggleSort(column) {
  if (currentSort.column === column) {
    currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
  } else {
    currentSort.column = column;
    currentSort.direction = 'asc';
  }
  renderMemories(allMemories);
}

function renderMemories(memories) {
  allMemories = memories;
  const sorted = sortMemories(memories, currentSort.column, currentSort.direction);
  const el = document.getElementById('memories');
  if(!sorted.length){ el.innerHTML='<div class="empty">No memories found.</div>'; return; }

  const sortIcon = (col) => currentSort.column === col ? (currentSort.direction === 'asc' ? '▲' : '▼') : '⇅';

  let html = `<table>
    <tr>
      <th onclick="toggleSort('id')">ID<span class="sort-indicator">${sortIcon('id')}</span></th>
      <th onclick="toggleSort('category')">Category<span class="sort-indicator">${sortIcon('category')}</span></th>
      <th onclick="toggleSort('content')">Content<span class="sort-indicator">${sortIcon('content')}</span></th>
      <th onclick="toggleSort('source')">Source<span class="sort-indicator">${sortIcon('source')}</span></th>
      <th onclick="toggleSort('confidence')">Confidence<span class="sort-indicator">${sortIcon('confidence')}</span></th>
      <th onclick="toggleSort('timestamp')">Time<span class="sort-indicator">${sortIcon('timestamp')}</span></th>
      <th></th>
    </tr>`;
  for(const m of sorted){
    html+=`<tr>
      <td>#${m.id}</td>
      <td><span class="badge badge-${m.category}">${m.category}</span></td>
      <td>${escapeHtml(m.content.substring(0,120))}${m.content.length>120?'...':''}<br><span class="confidence">${m.tags ? 'tags: ' + escapeHtml(m.tags) : ''}</span></td>
      <td>${escapeHtml(m.source||'-')}</td>
      <td>${(m.confidence||1).toFixed(2)}</td>
      <td>${(m.timestamp||'').replace('T',' ').substring(0,16)}</td>
      <td>
        <button class="delete-btn" style="background:var(--accent);margin-right:.3rem;" onclick="editMemory(${m.id},'${escapeHtml(m.content).replace(/'/g,'&#39;')}','${m.category}',${m.confidence},'${escapeHtml(m.tags||'').replace(/'/g,'&#39;')}')">✎</button>
        <button class="delete-btn" onclick="deleteMemory(${m.id})">×</button>
      </td>
    </tr>`;
  }
  html+='</table>';
  el.innerHTML=html;
}

async function loadMemories(project, keyword='', category='') {
  currentProject = project;
  document.getElementById('project-label').textContent = project || 'All projects';
  let url = '/api/memories?project='+encodeURIComponent(project);
  if(category) url += '&category='+encodeURIComponent(category);
  if(keyword) url = '/api/search?project='+encodeURIComponent(project)+'&keyword='+encodeURIComponent(keyword);
  const data = await fetchJSON(url);
  const memories = data.memories || data.results || [];
  renderMemories(memories);
  // Update KPIs from the filtered data
  renderStats(computeStats(memories));
}

async function editMemory(id, content, category, confidence, tags){
  const newContent = prompt('Content:', content);
  if(newContent === null) return;
  const newCategory = prompt('Category (fact/decision/action/preference/error):', category);
  if(newCategory === null) return;
  const newConfidence = prompt('Confidence (0.0 - 1.0):', confidence);
  if(newConfidence === null) return;
  const newTags = prompt('Tags (comma-separated):', tags);
  if(newTags === null) return;

  const updates = {content: newContent, category: newCategory, confidence: parseFloat(newConfidence), tags: newTags};
  const resp = await fetch('/api/memories/'+id, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(updates)});
  const result = await resp.json();
  if(result.status === 'updated'){
    loadData();
  } else {
    alert('Update failed: ' + result.status);
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

async function loadData(){
  const p=document.getElementById('project-select').value;
  const k=document.getElementById('search-input').value;
  const c=document.getElementById('category-filter').value;
  await Promise.all([loadMemories(p,k,c), loadRecent()]);
  document.getElementById('refresh-indicator').textContent = 'Updated '+new Date().toLocaleTimeString();
}

async function deleteMemory(id){
  if(!confirm('Delete memory #'+id+'?')) return;
  await fetch('/api/memories/'+id,{method:'DELETE'});
  loadData();
}

async function captureMemory(){
  const p=document.getElementById('project-select').value || prompt('Project:','default'); if(!p) return;
  const content=prompt('Memory content:'); if(!content) return;
  const category=prompt('Category (fact/decision/action/preference/error):','fact')||'fact';
  await fetch('/api/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:p,content,category})});
  loadData();
}

async function exportJSON(){
  const p=document.getElementById('project-select').value;
  const data = await fetchJSON('/api/export?project='+encodeURIComponent(p));
  const blob = new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'crossagentmemory-export-'+(p||'all')+'.json';
  a.click();
  URL.revokeObjectURL(url);
}

if(autoRefresh) clearInterval(autoRefresh);
autoRefresh = setInterval(loadData, 10000);

loadProjects().then(loadData);
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
    limit: int = 100000,
) -> dict[str, Any]:
    engine = MemoryEngine()
    memories = engine.recall(
        project=project or None,
        category=category or None,
        limit=limit,
    )
    # Sort by ID ascending for consistent ordering
    memories = sorted(memories, key=lambda m: m.id)
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
    # Sort by ID ascending
    results = sorted(results, key=lambda m: m.id)
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
        session_id=os.environ.get("CROSSAGENTMEMORY_SESSION", str(uuid.uuid4())[:8]),
        category=payload.get("category", "fact"),
        content=payload["content"],
        confidence=payload.get("confidence", 1.0),
        source=payload.get("source", "dashboard"),
        tags=payload.get("tags", ""),
    )
    memory_id = engine.store(entry)
    return {"status": "stored", "memory_id": memory_id}


@app.delete("/api/memories/{memory_id}")
def api_delete_memory(memory_id: int) -> dict[str, Any]:
    engine = MemoryEngine()
    deleted = engine.delete_memory(memory_id)
    return {"status": "deleted" if deleted else "not_found", "memory_id": memory_id}


@app.patch("/api/memories/{memory_id}")
def api_update_memory(memory_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    engine = MemoryEngine()
    allowed = {"content", "category", "confidence", "tags"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    if not updates:
        return {"status": "no_changes", "memory_id": memory_id}
    updated = engine.update_memory(memory_id, updates)
    return {"status": "updated" if updated else "not_found", "memory_id": memory_id}


@app.get("/api/projects")
def api_projects() -> dict[str, Any]:
    engine = MemoryEngine()
    return {"projects": engine.list_projects()}


@app.get("/api/export")
def api_export(project: str = "") -> dict[str, Any]:
    engine = MemoryEngine()
    memories = engine.recall(project=project or None, limit=100000)
    return {
        "exported_at": __import__("datetime")
        .datetime.now(__import__("datetime").timezone.utc)
        .isoformat(),
        "project": project or "all",
        "count": len(memories),
        "memories": [
            {
                "id": m.id,
                "project": m.project,
                "session_id": m.session_id,
                "timestamp": m.timestamp,
                "category": m.category,
                "content": m.content,
                "confidence": m.confidence,
                "source": m.source,
                "tags": m.tags,
                "metadata": m.metadata,
            }
            for m in memories
        ],
    }


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
        raise ImportError("Dashboard requires uvicorn. Install with: pip install uvicorn") from e

    uvicorn.run(app, host=host, port=port, log_level="warning")
