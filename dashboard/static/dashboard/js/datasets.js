(() => {
  const form = document.getElementById('upload-form');
  if (!form) return;

  const fileInput = document.getElementById('dataset-file');
  const dropZone = document.getElementById('drop-zone');
  const message = document.getElementById('upload-message');
  const list = document.getElementById('dataset-list');
  const detailBody = document.getElementById('detail-body');
  const deleteButton = document.getElementById('delete-dataset');
  let selectedId = null;

  function csrfToken() {
    return form.querySelector('[name=csrfmiddlewaretoken]').value;
  }

  function setMessage(text, error = false) {
    message.textContent = text;
    message.classList.toggle('error', error);
  }

  async function api(url, options = {}) {
    const response = await fetch(url, {
      credentials: 'same-origin',
      ...options,
      headers: {'X-CSRFToken': csrfToken(), ...(options.headers || {})},
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const first = Object.values(body).flat(Infinity).find((value) => typeof value === 'string');
      throw new Error(first || `Request failed (${response.status}).`);
    }
    return response.status === 204 ? null : response.json();
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function prettyNumber(value) {
    return Number(value || 0).toLocaleString();
  }

  async function loadList(selectId = selectedId) {
    const datasets = await api('/api/datasets/');
    list.replaceChildren();
    document.getElementById('dataset-count').textContent = `${datasets.length} dataset${datasets.length === 1 ? '' : 's'}`;
    if (!datasets.length) {
      list.append(element('div', 'empty-datasets', 'No datasets yet. Upload a CSV or Excel file to begin.'));
      selectedId = null;
      showEmptyDetails();
      return;
    }
    datasets.forEach((dataset) => {
      const button = element('button', `dataset-list-item${dataset.id === selectId ? ' selected' : ''}`);
      button.type = 'button';
      button.setAttribute('aria-pressed', dataset.id === selectId ? 'true' : 'false');
      const icon = element('span', 'dataset-file-icon', dataset.file_type.toUpperCase() === 'CSV' ? '▤' : '▦');
      const copy = element('span', 'dataset-list-copy');
      copy.append(element('b', '', dataset.name), element('small', '', `${prettyNumber(dataset.row_count)} rows · ${dataset.column_count} columns · ${dataset.file_type.toUpperCase()}`));
      button.append(icon, copy, element('span', 'dataset-arrow', '›'));
      button.addEventListener('click', () => loadDetails(dataset.id));
      list.append(button);
    });
    if (selectId && datasets.some((item) => item.id === selectId)) await loadDetails(selectId);
    else await loadDetails(datasets[0].id);
  }

  function showEmptyDetails() {
    document.getElementById('detail-title').textContent = 'Dataset details';
    document.getElementById('detail-caption').textContent = 'Choose a dataset to see its columns and preview.';
    document.getElementById('stat-rows').textContent = '—';
    document.getElementById('stat-columns').textContent = '—';
    document.getElementById('stat-missing').textContent = '—';
    detailBody.replaceChildren(element('div', 'empty-details', 'Select a dataset from your list, or upload a CSV or Excel file to get started.'));
    deleteButton.hidden = true;
  }

  function addSectionTitle(parent, title, subtitle) {
    const heading = element('div', 'detail-section-heading');
    heading.append(element('h3', '', title), element('span', '', subtitle));
    parent.append(heading);
  }

  async function loadDetails(id) {
    try {
      const dataset = await api(`/api/datasets/${id}/`);
      selectedId = dataset.id;
      document.querySelectorAll('.dataset-list-item').forEach((item) => {
        const selected = item.querySelector('.dataset-list-copy b').textContent === dataset.name;
        item.classList.toggle('selected', selected);
        item.setAttribute('aria-pressed', selected ? 'true' : 'false');
      });
      document.getElementById('detail-title').textContent = dataset.name;
      document.getElementById('detail-caption').textContent = `${dataset.file_type.toUpperCase()} · Added ${new Date(dataset.created_at).toLocaleDateString()}`;
      document.getElementById('stat-rows').textContent = prettyNumber(dataset.row_count);
      document.getElementById('stat-columns').textContent = prettyNumber(dataset.column_count);
      document.getElementById('stat-missing').textContent = prettyNumber(dataset.statistics.missing_values);
      deleteButton.hidden = false;
      detailBody.replaceChildren();

      addSectionTitle(detailBody, 'Columns', `${dataset.columns.length} detected`);
      const columns = element('div', 'column-list');
      dataset.columns.forEach((column) => {
        const item = element('div', 'column-item');
        const copy = element('span', 'column-copy');
        copy.append(element('b', '', column.name), element('small', '', `${column.data_type} · ${prettyNumber(column.unique_values)} unique`));
        item.append(copy, element('span', 'column-missing', `${prettyNumber(column.missing_values)} missing`));
        columns.append(item);
      });
      detailBody.append(columns);

      const numericEntries = Object.entries(dataset.statistics.numeric || {});
      addSectionTitle(detailBody, 'Numeric statistics', numericEntries.length ? `${numericEntries.length} numeric column${numericEntries.length === 1 ? '' : 's'}` : 'No numeric columns detected');
      if (numericEntries.length) {
        const statsWrap = element('div', 'numeric-stats-wrap');
        const table = element('table', 'numeric-stats-table');
        const head = document.createElement('thead');
        const headerRow = document.createElement('tr');
        ['Column', 'Mean', 'Median', 'Min', 'Max'].forEach((label) => headerRow.append(element('th', '', label)));
        head.append(headerRow);
        const body = document.createElement('tbody');
        numericEntries.forEach(([name, stats]) => {
          const row = document.createElement('tr');
          [name, stats.mean, stats.median, stats.min, stats.max].forEach((value) => row.append(element('td', '', value == null ? '—' : typeof value === 'number' ? Number(value.toFixed(3)).toLocaleString() : String(value))));
          body.append(row);
        });
        table.append(head, body);
        statsWrap.append(table);
        detailBody.append(statsWrap);
      }

      const rows = dataset.metadata.preview || [];
      addSectionTitle(detailBody, 'Data preview', `First ${rows.length} of ${prettyNumber(dataset.row_count)} rows`);
      if (rows.length) {
        const wrap = element('div', 'table-wrap preview-wrap');
        const table = document.createElement('table');
        const head = document.createElement('thead');
        const header = document.createElement('tr');
        dataset.columns.forEach((column) => header.append(element('th', '', column.name)));
        head.append(header);
        const body = document.createElement('tbody');
        rows.forEach((dataRow) => {
          const row = document.createElement('tr');
          dataset.columns.forEach((column) => row.append(element('td', '', dataRow[column.name] == null ? '—' : String(dataRow[column.name]))));
          body.append(row);
        });
        table.append(head, body);
        wrap.append(table);
        detailBody.append(wrap);
      }
    } catch (error) {
      setMessage(error.message, true);
    }
  }

  function chooseFile(file) {
    if (!file) return;
    fileInput.files = (() => { const transfer = new DataTransfer(); transfer.items.add(file); return transfer.files; })();
    dropZone.classList.add('has-file');
    dropZone.querySelector('b').textContent = file.name;
    dropZone.querySelector('p').textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB · Ready to upload`;
    setMessage('');
  }

  document.getElementById('browse-button').addEventListener('click', () => fileInput.click());
  document.getElementById('inline-browse').addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('click', (event) => { if (!event.target.closest('button')) fileInput.click(); });
  dropZone.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); fileInput.click(); } });
  fileInput.addEventListener('change', () => chooseFile(fileInput.files[0]));
  ['dragenter', 'dragover'].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.add('dragging'); }));
  ['dragleave', 'drop'].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.remove('dragging'); }));
  dropZone.addEventListener('drop', (event) => chooseFile(event.dataTransfer.files[0]));

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!fileInput.files.length) { setMessage('Choose a CSV or Excel file first.', true); return; }
    const submit = document.getElementById('submit-upload');
    submit.disabled = true;
    submit.textContent = 'Uploading…';
    setMessage('');
    try {
      const dataset = await api('/api/datasets/', {method: 'POST', body: new FormData(form)});
      form.reset();
      dropZone.classList.remove('has-file');
      dropZone.querySelector('b').textContent = 'Drop your dataset here';
      const prompt = dropZone.querySelector('p');
      prompt.replaceChildren(document.createTextNode('or '));
      const browseLink = element('button', 'inline-upload', 'browse files');
      browseLink.type = 'button';
      browseLink.addEventListener('click', () => fileInput.click());
      prompt.append(browseLink, document.createTextNode(' · CSV or Excel, up to 25 MB'));
      setMessage('Dataset uploaded and analyzed.');
      await loadList(dataset.id);
    } catch (error) { setMessage(error.message, true); }
    finally { submit.disabled = false; submit.textContent = 'Upload dataset'; }
  });

  deleteButton.addEventListener('click', async () => {
    if (!selectedId) return;
    deleteButton.disabled = true;
    try {
      await api(`/api/datasets/${selectedId}/`, {method: 'DELETE'});
      selectedId = null;
      setMessage('Dataset deleted.');
      await loadList();
    } catch (error) { setMessage(error.message, true); }
    finally { deleteButton.disabled = false; }
  });

  loadList().catch((error) => {
    document.getElementById('dataset-count').textContent = 'Could not load datasets';
    list.replaceChildren(element('div', 'empty-datasets error', error.message));
  });
})();
