"""Minimal web panel for the H5 ligand database."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

ADMIN_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BIMOS · Ligandos</title>
<style>
  :root { color-scheme: light dark; --bg:#f6f7fb; --panel:#fff; --text:#172033; --muted:#667085; --line:#d9deea; --accent:#155eef; --danger:#b42318; }
  @media (prefers-color-scheme: dark) { :root { --bg:#101828; --panel:#172033; --text:#eef2ff; --muted:#a5b4cf; --line:#2b3a55; --accent:#84adff; --danger:#f97066; } }
  * { box-sizing:border-box; }
  body { margin:0; font:14px/1.45 system-ui,Segoe UI,Roboto,sans-serif; background:var(--bg); color:var(--text); }
  header { padding:20px 24px; border-bottom:1px solid var(--line); background:var(--panel); display:flex; gap:16px; align-items:baseline; flex-wrap:wrap; }
  h1 { margin:0; font-size:20px; }
  main { padding:20px 24px 48px; display:grid; grid-template-columns:minmax(0,1fr) 330px; gap:20px; }
  @media (max-width: 900px) { main { grid-template-columns:1fr; } }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px; }
  .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-bottom:12px; }
  input, button, select { font:inherit; }
  input, select { padding:9px 10px; border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--text); min-width:0; }
  button { padding:9px 12px; border:1px solid transparent; border-radius:8px; background:var(--accent); color:#fff; cursor:pointer; }
  button.secondary { background:transparent; border-color:var(--line); color:var(--text); }
  button.danger { background:var(--danger); }
  table { width:100%; border-collapse:collapse; }
  th, td { text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
  th { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
  td.actions { white-space:nowrap; display:flex; gap:6px; }
  td.actions button { padding:5px 8px; font-size:12px; }
  .muted { color:var(--muted); }
  .status { min-height:20px; color:var(--muted); }
  .status.error { color:var(--danger); }
  form { display:grid; gap:10px; }
  label { display:grid; gap:4px; color:var(--muted); font-size:12px; }
  .split { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  code { font-size:12px; }
</style>
</head>
<body>
<header>
  <h1>Gestión de ligandos</h1>
  <span class="muted">H5 · PostgreSQL · token Bearer</span>
</header>
<main>
  <section class="card">
    <div class="row">
      <input id="q" placeholder="Nombre, CID o SMILES" style="flex:1">
      <input id="source" placeholder="Fuente" style="width:150px">
      <button id="search">Buscar</button>
    </div>
    <div class="row">
      <label style="flex:1">Token de API <input id="token" type="password" placeholder="BIMOS_API_TOKEN"></label>
      <button id="save-token" class="secondary">Guardar token</button>
      <button id="reload" class="secondary">Recargar</button>
    </div>
    <div id="status" class="status"></div>
    <table>
      <thead><tr><th>Nombre</th><th>CID</th><th>SMILES</th><th>logP</th><th>Masa</th><th>Fuente</th><th></th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </section>
  <aside class="card">
    <h2 id="form-title" style="margin-top:0;font-size:16px">Nuevo ligando</h2>
    <form id="ligand-form">
      <label>CID <input id="cid" required maxlength="64"></label>
      <label>Nombre <input id="name" required maxlength="256"></label>
      <label>SMILES <input id="smiles" maxlength="2048"></label>
      <div class="split">
        <label>logP <input id="logp" type="number" step="any"></label>
        <label>Masa molar <input id="molar_mass" type="number" step="any" min="0"></label>
      </div>
      <label>Fuente <input id="source-form" maxlength="128"></label>
      <div class="row" style="margin:0">
        <button type="submit">Guardar</button>
        <button type="button" id="cancel" class="secondary">Cancelar</button>
      </div>
    </form>
    <p class="muted" style="margin-bottom:0">La baja es lógica: el registro deja de aparecer pero conserva historial.</p>
  </aside>
  <section class="card" style="grid-column:1/-1">
    <h2 style="margin-top:0;font-size:16px">Tokens de API</h2>
    <div class="row">
      <input id="token-name" placeholder="Nombre del usuario" style="flex:1">
      <select id="token-role"><option value="viewer">viewer</option><option value="editor">editor</option><option value="admin">admin</option></select>
      <button id="token-create">Crear token</button>
    </div>
    <div id="token-once" class="status"></div>
    <table>
      <thead><tr><th>Nombre</th><th>Rol</th><th>Creado</th><th></th></tr></thead>
      <tbody id="token-rows"></tbody>
    </table>
  </section>
</main>
<script>
const $ = (id) => document.getElementById(id);
let editingCid = null;

function token() { return sessionStorage.getItem('bimos_token') || ''; }
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function status(message, isError = false) {
  const el = $('status');
  el.textContent = message;
  el.className = 'status' + (isError ? ' error' : '');
}
async function api(path, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  headers['Content-Type'] = 'application/json';
  if (token()) headers.Authorization = 'Bearer ' + token();
  const response = await fetch(path, Object.assign({}, options, {headers}));
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || response.statusText);
  return data;
}
function resetForm() {
  editingCid = null;
  $('form-title').textContent = 'Nuevo ligando';
  $('cid').disabled = false;
  for (const id of ['cid','name','smiles','logp','molar_mass','source-form']) $(id).value = '';
}
function edit(item) {
  editingCid = item.cid;
  $('form-title').textContent = 'Editar ' + item.cid;
  $('cid').disabled = true;
  $('cid').value = item.cid;
  $('name').value = item.name || '';
  $('smiles').value = item.smiles || '';
  $('logp').value = item.logp ?? '';
  $('molar_mass').value = item.molar_mass ?? '';
  $('source-form').value = item.source || '';
  $('name').focus();
}
function rowHtml(item) {
  return '<tr>' +
    '<td>' + escapeHtml(item.name) + '</td>' +
    '<td><code>' + escapeHtml(item.cid) + '</code></td>' +
    '<td class="muted">' + escapeHtml(item.smiles || '') + '</td>' +
    '<td>' + escapeHtml(item.logp ?? '') + '</td>' +
    '<td>' + escapeHtml(item.molar_mass ?? '') + '</td>' +
    '<td>' + escapeHtml(item.source || '') + '</td>' +
    '<td class="actions"><button data-edit="' + escapeHtml(item.cid) + '" class="secondary">Editar</button>' +
    '<button data-delete="' + escapeHtml(item.cid) + '" class="danger">Baja</button></td>' +
    '</tr>';
}
async function loadTokens() {
  try {
    const data = await api('/api/v1/tokens');
    $('token-rows').innerHTML = data.length ? data.map((item) =>
      '<tr><td>' + escapeHtml(item.name) + '</td><td>' + escapeHtml(item.role) + '</td><td class="muted">' + escapeHtml(item.created_at) + '</td>' +
      '<td class="actions"><button data-revoke="' + item.id + '" class="danger">Revocar</button></td></tr>'
    ).join('') : '<tr><td colspan="4" class="muted">Sin tokens adicionales.</td></tr>';
  } catch (error) {
    $('token-rows').innerHTML = '<tr><td colspan="4" class="muted">' + escapeHtml(error.message) + '</td></tr>';
  }
}
async function load() {
  try {
    const params = new URLSearchParams({q: $('q').value.trim(), limit: '200'});
    if ($('source').value.trim()) params.set('source', $('source').value.trim());
    const data = await api('/api/v1/ligands?' + params.toString());
    $('rows').innerHTML = data.items.length ? data.items.map(rowHtml).join('') : '<tr><td colspan="7" class="muted">Sin resultados.</td></tr>';
    status(data.total + ' ligando(s) activo(s). Mostrando ' + data.items.length + '.');
  } catch (error) {
    status(error.message, true);
  }
}
async function submit(event) {
  event.preventDefault();
  const payload = {
    name: $('name').value.trim(),
    smiles: $('smiles').value.trim() || null,
    logp: $('logp').value === '' ? null : Number($('logp').value),
    molar_mass: $('molar_mass').value === '' ? null : Number($('molar_mass').value),
    source: $('source-form').value.trim() || null,
  };
  try {
    if (editingCid) {
      await api('/api/v1/ligands/' + encodeURIComponent(editingCid), {method: 'PATCH', body: JSON.stringify(payload)});
      status('Ligando actualizado.');
    } else {
      payload.cid = $('cid').value.trim();
      await api('/api/v1/ligands', {method: 'POST', body: JSON.stringify(payload)});
      status('Ligando creado.');
    }
    resetForm();
    await load();
  } catch (error) {
    status(error.message, true);
  }
}
async function deactivate(cid) {
  if (!confirm('¿Dar de baja lógica a ' + cid + '?')) return;
  try {
    await api('/api/v1/ligands/' + encodeURIComponent(cid), {method: 'DELETE'});
    status('Ligando dado de baja.');
    await load();
  } catch (error) {
    status(error.message, true);
  }
}
$('save-token').addEventListener('click', () => {
  sessionStorage.setItem('bimos_token', $('token').value.trim());
  status('Token guardado en esta pestaña.');
  loadTokens();
});
$('token-create').addEventListener('click', async () => {
  try {
    const data = await api('/api/v1/tokens', {method: 'POST', body: JSON.stringify({name: $('token-name').value.trim(), role: $('token-role').value})});
    $('token-once').textContent = 'Token creado (se muestra una sola vez): ' + data.token;
    $('token-name').value = '';
    await loadTokens();
  } catch (error) {
    $('token-once').textContent = error.message;
    $('token-once').className = 'status error';
  }
});
$('token-rows').addEventListener('click', async (event) => {
  const id = event.target.getAttribute('data-revoke');
  if (!id) return;
  if (!confirm('¿Revocar este token?')) return;
  try {
    await api('/api/v1/tokens/' + encodeURIComponent(id), {method: 'DELETE'});
    await loadTokens();
  } catch (error) {
    $('token-once').textContent = error.message;
    $('token-once').className = 'status error';
  }
});
$('search').addEventListener('click', load);
$('reload').addEventListener('click', load);
$('cancel').addEventListener('click', resetForm);
$('ligand-form').addEventListener('submit', submit);
$('rows').addEventListener('click', (event) => {
  const editCid = event.target.getAttribute('data-edit');
  const deleteCid = event.target.getAttribute('data-delete');
  if (editCid) {
    const row = event.target.closest('tr');
    const cells = row.querySelectorAll('td');
    edit({name: cells[0].textContent, cid: editCid, smiles: cells[2].textContent, logp: cells[3].textContent, molar_mass: cells[4].textContent, source: cells[5].textContent});
  }
  if (deleteCid) deactivate(deleteCid);
});
$('token').value = token();
load();
loadTokens();
</script>
</body>
</html>
"""


@router.get("/admin/ligands", response_class=HTMLResponse, include_in_schema=False)
def ligand_admin_panel() -> HTMLResponse:
    return HTMLResponse(ADMIN_HTML)
