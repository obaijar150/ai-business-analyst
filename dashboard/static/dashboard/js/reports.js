(() => {
  const select = document.getElementById('report-dataset');
  const createButton = document.getElementById('report-create');
  const titleInput = document.getElementById('report-title');
  const errorBox = document.getElementById('report-error');
  const list = document.getElementById('report-list');
  if (!select) return;

  function el(tag, text) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; return n; }

  async function loadDatasets() {
    const response = await fetch('/api/datasets/', { credentials: 'same-origin' });
    if (!response.ok) throw new Error('Could not load datasets.');
    const datasets = await response.json();
    select.replaceChildren();
    datasets.forEach((d) => select.append(new Option(d.name, String(d.id))));
    if (!datasets.length) select.append(new Option('No datasets available', ''));
  }

  async function loadReports() {
    const response = await fetch('/api/reports/', { credentials: 'same-origin' });
    if (!response.ok) throw new Error('Could not load reports.');
    const reports = await response.json();
    list.replaceChildren();
    if (!reports.length) { list.append(el('li', 'No reports yet.')); return; }
    reports.forEach((report) => {
      const item = document.createElement('li');
      item.append(el('b', report.title));
      const viewButton = el('button', 'View');
      viewButton.className = 'subtle-button';
      viewButton.addEventListener('click', () => viewReport(report.id));
      const deleteButton = el('button', 'Delete');
      deleteButton.className = 'subtle-button';
      deleteButton.addEventListener('click', () => deleteReport(report.id));
      item.append(viewButton, deleteButton);
      item.append(el('small', ` ${new Date(report.created_at).toLocaleString()}`));
      list.append(item);
    });
  }

  async function createReport() {
    errorBox.hidden = true;
    if (!select.value) { errorBox.hidden = false; errorBox.textContent = 'Select a dataset first.'; return; }
    const response = await fetch('/api/reports/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_id: Number(select.value), title: titleInput.value.trim() || undefined }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) { errorBox.hidden = false; errorBox.textContent = payload.detail || 'Could not create report.'; return; }
    titleInput.value = '';
    await loadReports();
    await viewReport(payload.id);
  }

  async function viewReport(id) {
    const response = await fetch(`/api/reports/${id}/`, { credentials: 'same-origin' });
    if (!response.ok) return;
    const report = await response.json();
    document.getElementById('report-detail').hidden = false;
    document.getElementById('report-detail-title').textContent = report.title;
    document.getElementById('report-executive').textContent = report.executive_summary;
    const kpis = document.getElementById('report-kpis'); kpis.replaceChildren();
    (report.kpis || []).forEach((kpi) => kpis.append(el('li', `${kpi.label}: ${kpi.value}`)));
    const findings = document.getElementById('report-findings'); findings.replaceChildren();
    (report.findings || []).forEach((item) => findings.append(el('li', item)));
    const recs = document.getElementById('report-recommendations'); recs.replaceChildren();
    (report.recommendations || []).forEach((item) => recs.append(el('li', item)));
    const anomalies = document.getElementById('report-anomalies'); anomalies.replaceChildren();
    (report.anomalies || []).forEach((item) => anomalies.append(el('li', JSON.stringify(item))));
    document.getElementById('report-evidence').textContent = JSON.stringify(report.evidence || {}, null, 2);
  }

  async function deleteReport(id) {
    if (!confirm('Delete this report?')) return;
    await fetch(`/api/reports/${id}/`, { method: 'DELETE', credentials: 'same-origin' });
    await loadReports();
    document.getElementById('report-detail').hidden = true;
  }

  createButton.addEventListener('click', () => createReport().catch((e) => { errorBox.hidden = false; errorBox.textContent = e.message; }));
  Promise.all([loadDatasets(), loadReports()]).catch((e) => { errorBox.hidden = false; errorBox.textContent = e.message; });
})();
