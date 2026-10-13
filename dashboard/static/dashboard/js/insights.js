(() => {
  const select = document.getElementById('insights-dataset');
  const loadButton = document.getElementById('insights-load');
  const errorBox = document.getElementById('insights-error');
  if (!select) return;

  async function loadDatasets() {
    const response = await fetch('/api/datasets/', { credentials: 'same-origin' });
    if (!response.ok) throw new Error('Could not load datasets.');
    const datasets = await response.json();
    select.replaceChildren();
    datasets.forEach((dataset) => select.append(new Option(dataset.name, String(dataset.id))));
    if (!datasets.length) select.append(new Option('No datasets available', ''));
  }

  function show(id) { const node = document.getElementById(id); if (node) node.hidden = false; }
  function el(tag, text) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; return node; }

  async function loadInsights() {
    errorBox.hidden = true;
    if (!select.value) { errorBox.hidden = false; errorBox.textContent = 'Select a dataset first.'; return; }
    const response = await fetch(`/api/insights/?dataset_id=${encodeURIComponent(select.value)}`, { credentials: 'same-origin' });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) { errorBox.hidden = false; errorBox.textContent = payload.detail || 'Could not load insights.'; return; }

    const kpiGrid = document.getElementById('kpi-grid');
    kpiGrid.replaceChildren();
    (payload.kpis || []).forEach((kpi) => {
      const card = el('div', '');
      card.className = 'kpi-card';
      card.append(el('div', kpi.label), el('b', String(kpi.value)));
      kpiGrid.append(card);
    });
    show('kpi-section');

    const chartGrid = document.getElementById('chart-grid');
    chartGrid.replaceChildren();
    (payload.charts || []).forEach((chart) => {
      const wrap = el('div', '');
      wrap.className = 'chart-wrap';
      const canvas = document.createElement('canvas');
      wrap.append(canvas);
      chartGrid.append(wrap);
      const cfg = { type: chart.type === 'pie' ? 'pie' : (chart.type === 'line' ? 'line' : 'bar'), data: {}, options: { plugins: { title: { display: true, text: chart.title || '' } } } };
      if (chart.labels && chart.values) {
        cfg.data = { labels: chart.labels, datasets: [{ label: chart.title || '', data: chart.values }] };
      } else if (chart.data) {
        cfg.data = { labels: chart.data.map((row) => row.name), datasets: [{ label: chart.y || '', data: chart.data.map((row) => row.value) }] };
      }
      try { new Chart(canvas, cfg); } catch (error) {}
    });
    if ((payload.charts || []).length) show('chart-section');

    const trendSection = document.getElementById('trend-section');
    if ((payload.trends && payload.trends.labels && payload.trends.labels.length) || payload.forecast) {
      show('trend-section');
      if (payload.trends && payload.trends.labels && payload.trends.labels.length) {
        const canvas = document.getElementById('trend-chart');
        new Chart(canvas, { type: 'line', data: { labels: payload.trends.labels, datasets: [{ label: payload.measure || '', data: payload.trends.values }] }, options: { plugins: { title: { display: true, text: 'Trend' } } } });
      }
    }

    const anomalyList = document.getElementById('anomaly-list');
    anomalyList.replaceChildren();
    (payload.anomalies || []).forEach((item) => {
      const text = item.period ? `${item.period}: ${item.reason} (${item.value})` : `Row ${item.row}: ${item.reason} (${item.value})`;
      anomalyList.append(el('li', text));
    });
    if ((payload.anomalies || []).length) show('anomaly-section');

    const recList = document.getElementById('recommendation-list');
    recList.replaceChildren();
    (payload.recommendations || []).forEach((item) => recList.append(el('li', item)));
    if ((payload.recommendations || []).length) show('recommendation-section');

    if (payload.forecast) {
      const recList2 = document.getElementById('recommendation-list');
      recList2.append(el('li', `Forecast for ${payload.forecast.period}: ${payload.forecast.value}`));
      show('recommendation-section');
    }
  }

  loadButton.addEventListener('click', () => loadInsights().catch((error) => { errorBox.hidden = false; errorBox.textContent = error.message; }));
  loadDatasets().catch((error) => { errorBox.hidden = false; errorBox.textContent = error.message; });
})();
