(() => {
  const form = document.getElementById('analyst-form');
  if (!form) return;

  const select = document.getElementById('analyst-dataset');
  const chat = document.getElementById('chat-area');
  const empty = document.getElementById('chat-empty');
  const questionInput = document.getElementById('analyst-question');
  const sendButton = document.getElementById('analyst-send');
  const errorBox = document.getElementById('analyst-error');

  function csrfToken() {
    return form.querySelector('[name=csrfmiddlewaretoken]').value;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function addMessage(role, text) {
    if (empty) empty.remove();
    const message = el('article', `chat-message ${role}`);
    message.setAttribute('aria-label', role === 'user' ? 'Your message' : 'AI Analyst response');
    message.append(el('div', 'message-role', role === 'user' ? 'You' : 'AI Analyst'));
    message.append(el('p', 'message-text', text));
    chat.append(message);
    message.scrollIntoView({block: 'nearest', behavior: 'smooth'});
    return message;
  }

  function addResultTable(parent, result) {
    if (!result || !result.columns || result.columns.length === 0) return;
    const section = el('div', 'answer-results');
    section.append(el('h3', '', 'Calculated result'));
    const wrap = el('div', 'table-wrap answer-table-wrap');
    const table = document.createElement('table');
    const head = document.createElement('thead');
    const headRow = document.createElement('tr');
    result.columns.forEach((column) => headRow.append(el('th', '', column)));
    head.append(headRow);
    const body = document.createElement('tbody');
    (result.rows || []).forEach((values) => {
      const row = document.createElement('tr');
      values.forEach((value) => {
        const display = value == null ? '—' : typeof value === 'number' ? Number(value).toLocaleString(undefined, {maximumFractionDigits: 12}) : String(value);
        row.append(el('td', '', display));
      });
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    section.append(wrap);
    parent.append(section);
  }

  function addEvidence(parent, evidence) {
    if (!evidence) return;
    const section = el('section', 'answer-evidence');
    section.setAttribute('aria-label', 'Evidence for this answer');
    section.append(el('h3', '', 'Evidence'));

    const source = el('p', 'evidence-source');
    source.append(el('b', '', 'Dataset: '), document.createTextNode(evidence.dataset || 'Selected dataset'));
    section.append(source);
    const period = el('p', 'evidence-source');
    period.append(el('b', '', 'Period: '), document.createTextNode(evidence.period || 'All dataset rows; no period filter was applied.'));
    section.append(period);

    [
      ['Fact', evidence.fact],
      ['Calculation', evidence.calculation],
      ['Interpretation', evidence.interpretation],
      ['Recommendation', evidence.recommendation],
    ].forEach(([label, entries]) => {
      const group = el('div', 'evidence-group');
      group.append(el('h4', '', label));
      const list = document.createElement('ul');
      (Array.isArray(entries) ? entries : entries ? [entries] : []).forEach((entry) => {
        list.append(el('li', '', String(entry)));
      });
      if (!list.childElementCount) list.append(el('li', '', 'None provided.'));
      group.append(list);
      section.append(group);
    });
    parent.append(section);
  }

  function addChart(parent, chart, result) {
    if (!chart || !result || !Array.isArray(result.columns) || !Array.isArray(result.rows)) return;
    const xi = result.columns.indexOf(chart.x);
    const yi = result.columns.indexOf(chart.y);
    if (xi < 0 || yi < 0) return;
    const wrap = el('div', 'chart-wrap');
    const canvas = document.createElement('canvas');
    canvas.className = 'analyst-chart';
    wrap.append(canvas);
    parent.append(wrap);

    const labels = result.rows.map((row) => row[xi]);
    const values = result.rows.map((row) => {
      const value = row[yi];
      return typeof value === 'number' ? value : Number(value);
    });

    const config = {
      type: chart.type,
      data: {
        labels,
        datasets: [{ label: chart.y, data: values, backgroundColor: 'rgba(84, 94, 234, 0.55)', borderColor: 'rgba(84, 94, 234, 1)', borderWidth: 1 }],
      },
      options: {
        responsive: true,
        plugins: { title: { display: true, text: chart.title }, legend: { display: chart.type !== 'pie' } },
      },
    };

    if (chart.type === 'scatter') {
      config.data = {
        datasets: [{ label: chart.y, data: result.rows.map((row) => ({ x: Number(row[xi]), y: Number(row[yi]) })) }],
      };
    }

    try { new Chart(canvas, config); } catch (error) { wrap.remove(); }
  }

  async function loadDatasets() {
    const response = await fetch('/api/datasets/', {credentials: 'same-origin'});
    if (!response.ok) throw new Error('Could not load your datasets. Refresh the page and try again.');
    const datasets = await response.json();
    select.replaceChildren();
    if (!datasets.length) {
      select.append(new Option('No datasets available', ''));
      select.disabled = true;
      errorBox.hidden = false;
      errorBox.textContent = 'Upload a dataset before asking the AI Analyst a question.';
      return;
    }
    select.append(new Option('Select a dataset…', ''));
    datasets.forEach((dataset) => select.append(new Option(dataset.name, String(dataset.id))));
    select.disabled = false;
  }

  select.addEventListener('change', () => {
    errorBox.hidden = true;
    chat.replaceChildren();
    chat.append(el('div', 'chat-empty', 'Ask a question about the selected dataset to get started.'));
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorBox.hidden = true;
    const question = questionInput.value.trim();
    if (!select.value) {
      errorBox.hidden = false;
      errorBox.textContent = 'Select a dataset first.';
      return;
    }
    if (!question) return;

    addMessage('user', question);
    questionInput.value = '';
    sendButton.disabled = true;
    sendButton.textContent = 'Thinking…';
    const loading = addMessage('assistant loading', 'Inspecting the dataset and calculating results…');
    try {
      const response = await fetch('/api/analyze/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken()},
        body: JSON.stringify({dataset_id: Number(select.value), question}),
      });
      const payload = await response.json().catch(() => ({}));
      loading.remove();
      if (!response.ok) {
        errorBox.hidden = false;
        errorBox.textContent = payload.detail || Object.values(payload).flat(Infinity).find((item) => typeof item === 'string') || 'The analysis could not be completed. Try again.';
        addMessage('assistant error', errorBox.textContent);
        return;
      }
      const answer = addMessage('assistant', payload.explanation || payload.answer || 'Analysis complete.');
      addResultTable(answer, payload.result);
      addEvidence(answer, payload.evidence);
      addChart(answer, payload.chart, payload.result);
    } catch (error) {
      loading.remove();
      errorBox.hidden = false;
      errorBox.textContent = 'Could not reach the analysis service. Check your connection and try again.';
      addMessage('assistant error', errorBox.textContent);
    } finally {
      sendButton.disabled = false;
      sendButton.innerHTML = 'Send <span>↑</span>';
      questionInput.focus();
    }
  });

  questionInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  loadDatasets().catch((error) => {
    select.replaceChildren(new Option('Datasets could not be loaded', ''));
    select.disabled = true;
    errorBox.hidden = false;
    errorBox.textContent = error.message;
  });
})();
