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
  .badge-valid { background:#d1e7dd; color:#0f5132; }
  .badge-expired { background:#f8d7da; color:#842029; }
  .badge-future { background:#fff3cd; color:#664d03; }
  .confidence { font-size:.8rem; color:var(--muted); }
  .empty { color:var(--muted); padding:2rem; text-align:center; }
  .recent-item { padding:.6rem; border-bottom:1px solid var(--border); font-size:.85rem; }
  .recent-item .meta { font-size:.75rem; color:var(--muted); margin-top:.2rem; }
  .recent-item .cat { font-size:.7rem; text-transform:uppercase; font-weight:600; }
  .delete-btn { background:var(--danger); color:#fff; border:none; border-radius:4px; padding:.2rem .5rem; font-size:.75rem; cursor:pointer; }
  .theme-toggle { background:var(--panel); border:1px solid var(--border); color:var(--text); padding:.4rem .8rem; border-radius:6px; cursor:pointer; font-size:.85rem; }
  .refresh-indicator { font-size:.75rem; color:var(--muted); margin-left:auto; }
  .view-toggle { background:var(--panel); border:1px solid var(--border); color:var(--text); padding:.4rem .8rem; border-radius:6px; cursor:pointer; font-size:.85rem; }
  .view-toggle.active { background:var(--accent); color:#fff; border-color:var(--accent); }
  #graph-view { display:none; }
  #kg-canvas { width:100%; height:600px; border:1px solid var(--border); border-radius:8px; background:var(--panel); }
  .kg-controls { display:flex; gap:.5rem; margin-bottom:.5rem; flex-wrap:wrap; }
  .kg-controls input { padding:.4rem .6rem; border-radius:6px; border:1px solid var(--border); background:var(--panel); color:var(--text); font-size:.85rem; }
  .kg-tooltip { position:absolute; background:var(--panel); border:1px solid var(--border); padding:.5rem; border-radius:6px; font-size:.8rem; pointer-events:none; display:none; z-index:100; }
  .kg-detail { background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:1rem; margin-top:.5rem; font-size:.85rem; }
  .kg-detail h4 { margin:0 0 .5rem; color:var(--accent); }
  .kg-detail .edge-item { padding:.2rem 0; border-bottom:1px solid var(--border); }
  .kg-detail .edge-item:last-child { border-bottom:none; }
  .graph-indicator { font-size:.75rem; color:var(--accent); margin-left:.3rem; }
</style>
</head>
<body>
<header>
  <h1>crossagentmemory dashboard</h1>
  <span id="project-label" style="color:var(--muted);font-size:.9rem;"></span>
  <span class="refresh-indicator" id="refresh-indicator"></span>
  <div style="display:flex;gap:.5rem;align-items:center;">
    <button class="view-toggle active" id="btn-memories" onclick="showView('memories')">Memories</button>
    <button class="view-toggle" id="btn-graph" onclick="showView('graph')">Knowledge Graph</button>
    <button class="theme-toggle" onclick="toggleTheme()">🌓 Theme</button>
  </div>
</header>
<div class="container">
  <div class="main">
    <div class="grid" id="stats"></div>
    <div class="filters">
      <select id="project-select"><option value="">All projects</option></select>
      <input type="text" id="search-input" placeholder="Search memories...">
      <select id="category-filter"><option value="">All categories</option><option>fact</option><option>decision</option><option>action</option><option>preference</option><option>error</option></select>
      <input type="text" id="user-filter" placeholder="User ID" style="width:100px">
      <input type="text" id="tenant-filter" placeholder="Tenant ID" style="width:100px">
      <input type="text" id="at-time-filter" placeholder="Valid at (ISO)" style="width:140px">
      <button onclick="loadData()">Load</button>
      <button onclick="exportJSON()">⬇ Export JSON</button>
      <button class="secondary" onclick="captureMemory()">+ Capture</button>
    </div>
    <div id="memories"></div>
    <div id="graph-view">
      <div class="kg-controls">
        <input type="text" id="kg-start" placeholder="Start entity">
        <input type="text" id="kg-end" placeholder="End entity">
        <button onclick="findKgPaths()">Find Paths</button>
        <input type="text" id="kg-filter" placeholder="Filter nodes..." oninput="filterKgNodes()">
        <button class="secondary" onclick="loadKgGraph()">Refresh Graph</button>
      </div>
      <canvas id="kg-canvas"></canvas>
      <div id="kg-tooltip" class="kg-tooltip"></div>
      <div id="kg-detail" class="kg-detail" style="display:none;"></div>
    </div>
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
let kgMemoryMap = new Set();

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
      <th onclick="toggleSort('confidence')">Conf<span class="sort-indicator">${sortIcon('confidence')}</span></th>
      <th>User</th>
      <th>Tenant</th>
      <th>Valid From</th>
      <th>Valid Until</th>
      <th onclick="toggleSort('timestamp')">Time<span class="sort-indicator">${sortIcon('timestamp')}</span></th>
      <th></th>
    </tr>`;
  const now = new Date().toISOString();
  for(const m of sorted){
    const vf = m.valid_from ? m.valid_from.substring(0,10) : '-';
    const vu = m.valid_until ? m.valid_until.substring(0,10) : '-';
    let validityBadge = '';
    if(m.valid_until && m.valid_until < now){
      validityBadge = '<span class="badge badge-expired">Expired</span>';
    } else if(m.valid_from && m.valid_from > now){
      validityBadge = '<span class="badge badge-future">Future</span>';
    } else if(m.valid_from || m.valid_until){
      validityBadge = '<span class="badge badge-valid">Valid</span>';
    }
    const graphIndicator = kgMemoryMap.has(m.id) ? '<span class="graph-indicator" title="In knowledge graph">◈</span>' : '';
    html+=`<tr>
      <td>#${m.id}</td>
      <td><span class="badge badge-${m.category}">${m.category}</span> ${validityBadge}</td>
      <td>${escapeHtml(m.content.substring(0,100))}${m.content.length>100?'...':''}${graphIndicator}<br><span class="confidence">${m.tags ? 'tags: ' + escapeHtml(m.tags) : ''}</span></td>
      <td>${escapeHtml(m.source||'-')}</td>
      <td>${(m.confidence||1).toFixed(2)}</td>
      <td>${escapeHtml(m.user_id||'-')}</td>
      <td>${escapeHtml(m.tenant_id||'-')}</td>
      <td>${vf}</td>
      <td>${vu}</td>
      <td>${(m.timestamp||'').replace('T',' ').substring(0,16)}</td>
      <td>
        <button class="delete-btn" style="background:var(--accent);margin-right:.3rem;" onclick="editMemory(${m.id},'${escapeHtml(m.content).replace(/'/g,'&#39;')}','${m.category}',${m.confidence},'${escapeHtml(m.tags||'').replace(/'/g,'&#39;')}','${escapeHtml(m.user_id||'').replace(/'/g,'&#39;')}','${escapeHtml(m.tenant_id||'').replace(/'/g,'&#39;')}','${escapeHtml(m.valid_from||'').replace(/'/g,'&#39;')}','${escapeHtml(m.valid_until||'').replace(/'/g,'&#39;')}')">✎</button>
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
  const userId = document.getElementById('user-filter').value;
  const tenantId = document.getElementById('tenant-filter').value;
  const atTime = document.getElementById('at-time-filter').value;
  // Fetch graph memory map in parallel
  try {
    const mapData = await fetchJSON('/api/kg/memory_map?project='+encodeURIComponent(project||'default'));
    kgMemoryMap = new Set(mapData.memory_ids||[]);
  } catch(e) { kgMemoryMap = new Set(); }
  let url = '/api/memories?project='+encodeURIComponent(project);
  if(category) url += '&category='+encodeURIComponent(category);
  if(userId) url += '&user_id='+encodeURIComponent(userId);
  if(tenantId) url += '&tenant_id='+encodeURIComponent(tenantId);
  if(atTime) url += '&at_time='+encodeURIComponent(atTime);
  if(keyword) {
    url = '/api/search?project='+encodeURIComponent(project)+'&keyword='+encodeURIComponent(keyword);
    if(userId) url += '&user_id='+encodeURIComponent(userId);
    if(tenantId) url += '&tenant_id='+encodeURIComponent(tenantId);
    if(atTime) url += '&at_time='+encodeURIComponent(atTime);
  }
  const data = await fetchJSON(url);
  const memories = data.memories || data.results || [];
  renderMemories(memories);
  // Update KPIs from the filtered data
  renderStats(computeStats(memories));
}

async function editMemory(id, content, category, confidence, tags, userId, tenantId, validFrom, validUntil){
  const newContent = prompt('Content:', content);
  if(newContent === null) return;
  const newCategory = prompt('Category (fact/decision/action/preference/error):', category);
  if(newCategory === null) return;
  const newConfidence = prompt('Confidence (0.0 - 1.0):', confidence);
  if(newConfidence === null) return;
  const newTags = prompt('Tags (comma-separated):', tags);
  if(newTags === null) return;
  const newUserId = prompt('User ID:', userId);
  if(newUserId === null) return;
  const newTenantId = prompt('Tenant ID:', tenantId);
  if(newTenantId === null) return;
  const newValidFrom = prompt('Valid from (ISO or empty):', validFrom);
  if(newValidFrom === null) return;
  const newValidUntil = prompt('Valid until (ISO or empty):', validUntil);
  if(newValidUntil === null) return;

  const updates = {
    content: newContent, category: newCategory, confidence: parseFloat(newConfidence), tags: newTags,
    user_id: newUserId, tenant_id: newTenantId, valid_from: newValidFrom, valid_until: newValidUntil
  };
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
  const userId=prompt('User ID (optional):','')||'';
  const tenantId=prompt('Tenant ID (optional):','')||'';
  const validFrom=prompt('Valid from (ISO, optional):','')||'';
  const validUntil=prompt('Valid until (ISO, optional):','')||'';
  await fetch('/api/capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:p,content,category,user_id:userId,tenant_id:tenantId,valid_from:validFrom,valid_until:validUntil})});
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

function showView(view) {
  document.getElementById('memories').style.display = view==='memories' ? 'block' : 'none';
  document.querySelector('.filters').style.display = view==='memories' ? 'flex' : 'none';
  document.getElementById('graph-view').style.display = view==='graph' ? 'block' : 'none';
  document.getElementById('btn-memories').classList.toggle('active', view==='memories');
  document.getElementById('btn-graph').classList.toggle('active', view==='graph');
  if(view==='graph') loadKgGraph();
}

// ─── Knowledge Graph Canvas Renderer ───
let kgNodes=[], kgEdges=[], kgNodeMap={}, kgCtx=null, kgCanvas=null;
let kgDragNode=null, kgHoverNode=null, kgOffsetX=0, kgOffsetY=0;
let kgSelectedNode=null, kgPathSet=new Set();
let kgFilterText='';

function _kgPosKey(project) { return 'kg_pos_'+project; }

async function loadKgGraph() {
  const project = document.getElementById('project-select').value || 'default';
  const data = await fetchJSON('/api/kg?project='+encodeURIComponent(project));
  const saved = JSON.parse(localStorage.getItem(_kgPosKey(project))||'{}');
  kgNodes = (data.nodes||[]).map(n => ({
    ...n,
    x: saved[n.id] ? saved[n.id][0] : Math.random()*600+100,
    y: saved[n.id] ? saved[n.id][1] : Math.random()*400+100,
    vx:0, vy:0, visible:true
  }));
  kgEdges = (data.edges||[]).map(e => ({...e}));
  kgNodeMap = {};
  kgNodes.forEach(n => kgNodeMap[n.id] = n);
  kgFilterText = '';
  document.getElementById('kg-filter').value = '';
  initKgCanvas();
  kgAnimate();
}

function initKgCanvas() {
  kgCanvas = document.getElementById('kg-canvas');
  const rect = kgCanvas.parentElement.getBoundingClientRect();
  kgCanvas.width = rect.width;
  kgCanvas.height = 600;
  kgCtx = kgCanvas.getContext('2d');
  kgCanvas.onmousedown = kgMouseDown;
  kgCanvas.onmousemove = kgMouseMove;
  kgCanvas.onmouseup = kgMouseUp;
  kgCanvas.onmouseleave = kgMouseUp;
  kgCanvas.onclick = kgMouseClick;
}

function kgMouseDown(e) {
  const rect = kgCanvas.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  for(const n of kgNodes) {
    if(!n.visible) continue;
    const dx = mx - n.x, dy = my - n.y;
    if(dx*dx + dy*dy < 400) { kgDragNode = n; kgOffsetX = dx; kgOffsetY = dy; return; }
  }
}
function kgMouseMove(e) {
  const rect = kgCanvas.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  if(kgDragNode) {
    kgDragNode.x = mx - kgOffsetX;
    kgDragNode.y = my - kgOffsetY;
    kgSavePositions();
    return;
  }
  kgHoverNode = null;
  for(const n of kgNodes) {
    if(!n.visible) continue;
    const dx = mx - n.x, dy = my - n.y;
    if(dx*dx + dy*dy < 400) kgHoverNode = n;
  }
  const tip = document.getElementById('kg-tooltip');
  if(kgHoverNode) {
    tip.style.display = 'block'; tip.style.left = (e.clientX+10)+'px'; tip.style.top = (e.clientY+10)+'px';
    tip.innerHTML = `<b>${escapeHtml(kgHoverNode.name)}</b><br><span style="color:var(--muted)">${kgHoverNode.type}</span>`;
  } else { tip.style.display = 'none'; }
}
function kgMouseUp() { kgDragNode = null; }

function kgSavePositions() {
  const project = document.getElementById('project-select').value || 'default';
  const saved = {};
  for(const n of kgNodes) saved[n.id] = [n.x, n.y];
  localStorage.setItem(_kgPosKey(project), JSON.stringify(saved));
}

async function kgMouseClick(e) {
  if(kgDragNode) return;
  if(kgHoverNode) {
    kgSelectedNode = kgHoverNode;
    await showKgNodeDetail(kgHoverNode);
  } else {
    kgSelectedNode = null;
    document.getElementById('kg-detail').style.display = 'none';
  }
}

async function showKgNodeDetail(node) {
  const project = document.getElementById('project-select').value || 'default';
  const detail = document.getElementById('kg-detail');
  detail.style.display = 'block';
  detail.innerHTML = `<h4>${escapeHtml(node.name)} <span style="color:var(--muted);font-size:.75rem;">[${node.type}]</span></h4><div>Loading...</div>`;
  try {
    const data = await fetchJSON('/api/kg/node/'+node.id+'?project='+encodeURIComponent(project));
    let html = `<h4>${escapeHtml(node.name)} <span style="color:var(--muted);font-size:.75rem;">[${node.type}]</span></h4>`;
    if(data.edges && data.edges.length) {
      html += `<div style="margin-bottom:.5rem;font-weight:600;">Connections:</div>`;
      for(const edge of data.edges) {
        const otherId = edge.source_id===node.id ? edge.target_id : edge.source_id;
        const other = kgNodeMap[otherId];
        const dir = edge.source_id===node.id ? '→' : '←';
        html += `<div class="edge-item">${dir} ${other ? escapeHtml(other.name) : '#'+otherId} <span style="color:var(--muted)">(${edge.relation})</span></div>`;
      }
    }
    if(data.memory_ids && data.memory_ids.length) {
      html += `<div style="margin-top:.5rem;font-weight:600;">Source memories: ${data.memory_ids.map(id => '#'+id).join(', ')}</div>`;
    }
    detail.innerHTML = html;
  } catch(err) {
    detail.innerHTML = `<h4>${escapeHtml(node.name)}</h4><div style="color:var(--danger)">Failed to load details</div>`;
  }
}

function filterKgNodes() {
  kgFilterText = document.getElementById('kg-filter').value.toLowerCase();
  for(const n of kgNodes) {
    n.visible = !kgFilterText || n.name.toLowerCase().includes(kgFilterText) || n.type.toLowerCase().includes(kgFilterText);
  }
}

function kgAnimate() {
  if(document.getElementById('graph-view').style.display === 'none') return;
  kgSimulate();
  kgDraw();
  requestAnimationFrame(kgAnimate);
}

function kgSimulate() {
  const W = kgCanvas.width, H = kgCanvas.height;
  const visibleNodes = kgNodes.filter(n => n.visible);
  // Repulsion
  for(let i=0;i<visibleNodes.length;i++) {
    for(let j=i+1;j<visibleNodes.length;j++) {
      const a = visibleNodes[i], b = visibleNodes[j];
      let dx = a.x - b.x, dy = a.y - b.y;
      let dist = Math.sqrt(dx*dx+dy*dy) || 1;
      const f = 2000/(dist*dist);
      dx /= dist; dy /= dist;
      a.vx += dx*f; a.vy += dy*f;
      b.vx -= dx*f; b.vy -= dy*f;
    }
  }
  // Spring attraction
  for(const e of kgEdges) {
    const a = kgNodeMap[e.source], b = kgNodeMap[e.target];
    if(!a || !b || !a.visible || !b.visible) continue;
    let dx = b.x - a.x, dy = b.y - a.y;
    let dist = Math.sqrt(dx*dx+dy*dy) || 1;
    const f = (dist-120)*0.003;
    dx /= dist; dy /= dist;
    a.vx += dx*f; a.vy += dy*f;
    b.vx -= dx*f; b.vy -= dy*f;
  }
  // Center gravity
  for(const n of visibleNodes) {
    n.vx += (W/2 - n.x)*0.0005;
    n.vy += (H/2 - n.y)*0.0005;
    n.vx *= 0.9; n.vy *= 0.9;
    n.x += n.vx; n.y += n.vy;
    n.x = Math.max(20, Math.min(W-20, n.x));
    n.y = Math.max(20, Math.min(H-20, n.y));
  }
}

function kgDraw() {
  const ctx = kgCtx, W = kgCanvas.width, H = kgCanvas.height;
  ctx.clearRect(0,0,W,H);
  // Draw edges
  ctx.lineWidth = 1.5;
  for(const e of kgEdges) {
    const a = kgNodeMap[e.source], b = kgNodeMap[e.target];
    if(!a || !b || !a.visible || !b.visible) continue;
    const isPath = kgPathSet.has(e.source+'-'+e.target) || kgPathSet.has(e.target+'-'+e.source);
    ctx.strokeStyle = isPath ? (getTheme()==='dark' ? '#4ade80' : '#198754') : (getTheme()==='dark' ? '#555' : '#ccc');
    ctx.lineWidth = isPath ? 3 : 1.5;
    ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
    const mx = (a.x+b.x)/2, my = (a.y+b.y)/2;
    ctx.fillStyle = getTheme()==='dark' ? '#888' : '#666';
    ctx.font = '10px sans-serif';
    ctx.fillText(e.relation, mx+4, my);
  }
  // Draw nodes
  for(const n of kgNodes) {
    if(!n.visible) continue;
    ctx.beginPath();
    const radius = n===kgSelectedNode ? 12 : (n===kgHoverNode ? 10 : 7);
    ctx.arc(n.x, n.y, radius, 0, Math.PI*2);
    ctx.fillStyle = kgNodeColor(n.type);
    ctx.fill();
    ctx.strokeStyle = n===kgSelectedNode ? (getTheme()==='dark' ? '#4ade80' : '#198754') : (getTheme()==='dark' ? '#fff' : '#333');
    ctx.lineWidth = n===kgSelectedNode ? 3 : 1.5;
    ctx.stroke();
    ctx.fillStyle = getTheme()==='dark' ? '#e0e0e0' : '#212529';
    ctx.font = '11px sans-serif';
    ctx.fillText(n.name, n.x+10, n.y+3);
  }
}

function kgNodeColor(type) {
  const map = {
    technology:'#4cc9f0', library:'#60a5fa', concept:'#a78bfa',
    decision:'#facc15', team:'#4ade80', person:'#f472b6', product:'#fb923c'
  };
  return map[type] || '#9ca3af';
}

function getTheme(){ return localStorage.getItem('theme') || 'dark'; }

async function findKgPaths() {
  const project = document.getElementById('project-select').value || 'default';
  const start = document.getElementById('kg-start').value;
  const end = document.getElementById('kg-end').value;
  if(!start || !end) return alert('Enter start and end entities');
  const data = await fetchJSON('/api/kg/paths?project='+encodeURIComponent(project)+'&start='+encodeURIComponent(start)+'&end='+encodeURIComponent(end));
  if(!data.paths || !data.paths.length) return alert('No paths found');
  kgPathSet.clear();
  for(const edge of data.paths[0]) {
    kgPathSet.add(edge.source+'-'+edge.target);
  }
  // Auto-show start node detail
  const startNode = kgNodes.find(n => n.name.toLowerCase() === start.toLowerCase());
  if(startNode) { kgSelectedNode = startNode; showKgNodeDetail(startNode); }
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
def api_stats(
    project: str = "",
    user_id: str = "",
    tenant_id: str = "",
) -> dict[str, Any]:
    engine = MemoryEngine()
    data = engine.stats(
        user_id=user_id or None,
        tenant_id=tenant_id or None,
    )
    if project:
        data["project_memories"] = len(
            engine.recall(
                project=project,
                limit=10000,
                user_id=user_id or None,
                tenant_id=tenant_id or None,
            )
        )
    return data


@app.get("/api/memories")
def api_memories(
    project: str = "",
    category: str = "",
    user_id: str = "",
    tenant_id: str = "",
    at_time: str = "",
    limit: int = 100000,
) -> dict[str, Any]:
    engine = MemoryEngine()
    memories = engine.recall(
        project=project or None,
        category=category or None,
        user_id=user_id or None,
        tenant_id=tenant_id or None,
        at_time=at_time or None,
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
                "user_id": m.user_id,
                "tenant_id": m.tenant_id,
                "valid_from": m.valid_from,
                "valid_until": m.valid_until,
            }
            for m in memories
        ]
    }


@app.get("/api/search")
def api_search(
    project: str = "",
    keyword: str = "",
    user_id: str = "",
    tenant_id: str = "",
    at_time: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    engine = MemoryEngine()
    results = engine.search(
        keyword,
        project=project or None,
        user_id=user_id or None,
        tenant_id=tenant_id or None,
        at_time=at_time or None,
        limit=limit,
    )
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
                "user_id": m.user_id,
                "tenant_id": m.tenant_id,
                "valid_from": m.valid_from,
                "valid_until": m.valid_until,
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
        user_id=payload.get("user_id", ""),
        tenant_id=payload.get("tenant_id", ""),
        valid_from=payload.get("valid_from", ""),
        valid_until=payload.get("valid_until", ""),
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
    allowed = {
        "content", "category", "confidence", "tags",
        "user_id", "tenant_id", "valid_from", "valid_until",
    }
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


@app.get("/api/kg")
def api_kg(
    project: str = "",
) -> dict[str, Any]:
    from .knowledge_graph import get_graph_for_project

    engine = MemoryEngine()
    return get_graph_for_project(project or "default", db_path=engine.db_path)


@app.get("/api/kg/paths")
def api_kg_paths(
    project: str = "",
    start: str = "",
    end: str = "",
    max_depth: int = 5,
) -> dict[str, Any]:
    from .knowledge_graph import find_paths

    engine = MemoryEngine()
    paths = find_paths(
        project or "default",
        start,
        end,
        max_depth=max_depth,
        db_path=engine.db_path,
    )
    return {"paths": paths}


@app.get("/api/kg/memory_map")
def api_kg_memory_map(
    project: str = "",
) -> dict[str, Any]:
    """Return memory IDs that have associated graph edges."""
    import sqlite3

    engine = MemoryEngine()
    conn = sqlite3.connect(engine.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT DISTINCT memory_id FROM graph_edges WHERE project = ? AND memory_id IS NOT NULL",
            (project or "default",),
        ).fetchall()
        return {"memory_ids": [row["memory_id"] for row in rows]}
    finally:
        conn.close()


@app.get("/api/kg/node/{node_id}")
def api_kg_node(node_id: int, project: str = "") -> dict[str, Any]:
    """Get node details, connected edges, and related memory IDs."""
    import sqlite3

    engine = MemoryEngine()
    conn = sqlite3.connect(engine.db_path)
    conn.row_factory = sqlite3.Row
    try:
        node = conn.execute(
            "SELECT * FROM graph_nodes WHERE id = ?", (node_id,)
        ).fetchone()
        if not node:
            return {"error": "Node not found"}
        edges = conn.execute(
            "SELECT * FROM graph_edges WHERE project = ? AND (source_id = ? OR target_id = ?)",
            (project or "default", node_id, node_id),
        ).fetchall()
        memory_ids = list({
            e["memory_id"] for e in edges
            if e["memory_id"] is not None
        })
        return {
            "node": dict(node),
            "edges": [dict(e) for e in edges],
            "memory_ids": memory_ids,
        }
    finally:
        conn.close()


@app.post("/api/conflicts/resolve")
def api_resolve_conflicts(payload: dict[str, Any]) -> dict[str, Any]:
    from .conflict_resolution import scan_and_resolve_project

    engine = MemoryEngine()
    project = payload.get("project", "default")
    strategy = payload.get("strategy", "decay")
    decay_amount = payload.get("decay_amount", 0.3)
    actions = scan_and_resolve_project(engine, project, strategy=strategy, decay_amount=decay_amount)
    return {"resolved": len(actions), "actions": actions}


def run_dashboard(host: str = "127.0.0.1", port: int = 8745) -> None:
    """Run the dashboard server."""
    try:
        import uvicorn
    except ImportError as e:
        raise ImportError("Dashboard requires uvicorn. Install with: pip install uvicorn") from e

    uvicorn.run(app, host=host, port=port, log_level="warning")
