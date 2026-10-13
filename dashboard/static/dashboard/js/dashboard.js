(() => {
  const datasetCount = document.getElementById('metric-datasets');
  const analysisCount = document.getElementById('metric-analyses');
  const anomalyCount = document.getElementById('metric-anomalies');
  const recentAnalyses = document.getElementById('recent-analyses');
  const kpiList = document.getElementById('dashboard-kpi-list');
  const recList = document.getElementById('dashboard-recommendations');
  const anomalyList = document.getElementById('dashboard-anomalies');

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  async function load() {
    let datasets = [];
    try {
      const response = await fetch('/api/datasets/', { credentials: 'same-origin' });
      if (response.ok) datasets = await response.json();
    } catch (error) {}
    if (datasetCount) datasetCount.textContent = String(datasets.length);

    let analyses = [];
    try {
      const response = await fetch('/api/analyses/', { credentials: 'same-origin' });
      if (response.ok) analyses = await response.json();
    } catch (error) {}
    if (analysisCount) analysisCount.textContent = String(analyses.length);
    if (recentAnalyses) {
      recentAnalyses.replaceChildren();
      analyses.slice(0, 8).forEach((analysis) => {
        const item = el('div', '', 'activity-item');
        item.append(el('div', analysis.question));
        const small = el('small', `${analysis.dataset} · ${new Date(analysis.created_at).toLocaleString()}`);
        item.append(small);
        recentAnalyses.append(item);
      });
      if (!analyses.length) recentAnalyses.append(el('div', 'No analyses yet. Ask a question in AI Analyst.'));
    }

    if (!datasets.length) {
      if (kpiList) kpiList.append(el('div', 'Upload a dataset to generate insights.'));
      return;
    }

    try {
      const response = await fetch(`/api/insights/?dataset_id=${encodeURIComponent(datasets[0].id)}`, { credentials: 'same-origin' });
      if (!response.ok) return;
      const payload = await response.json();
      if (kpiList) {
        kpiList.replaceChildren();
        (payload.kpis || []).slice(0, 6).forEach((kpi) => {
          const row = el('div', '', 'activity-item');
          row.append(el('span', kpi.label));
          row.append(el('b', String(kpi.value)));
          kpiList.append(row);
        });
      }
      if (recList) {
        recList.replaceChildren();
        (payload.recommendations || []).forEach((text) => recList.append(el('li', text)));
      }
      if (anomalyList) {
        anomalyList.replaceChildren();
        (payload.anomalies || []).forEach((item) => {
          const text = item.period ? `${item.period}: ${item.reason}` : `Row ${item.row}: ${item.reason}`;
          anomalyList.append(el('li', text));
        });
        if (!(payload.anomalies || []).length) anomalyList.append(el('li', 'No anomalies detected.'));
      }
      if (anomalyCount) anomalyCount.textContent = String((payload.anomalies || []).length);
    } catch (error) {}
  }

  load().catch(() => {});
})();
