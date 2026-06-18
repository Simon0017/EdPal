/* user_questionnaires.js */

const csrf = () =>
  (document.querySelector('#qsCsrfForm input[name="csrfmiddlewaretoken"]') || {}).value || '';

function debounce(fn, wait = 350) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

/* ── State ── */
const state = {
  view:        'list',
  filter:      'all',
  search:      '',
  page:        1,
  hasMore:     false,
  items:       [],
};

/* ── Status badge ── */
function badgeHtml(status) {
  const map = {
    completed:   ['completed',   'Completed'],
    in_progress: ['in_progress', 'In Progress'],
    published:   ['published',   'New'],
    archived:    ['archived',    'Archived'],
  };
  const [cls, label] = map[status] || ['archived', status];
  return `<span class="qs-badge qs-badge--${cls}">${label}</span>`;
}

/* ── Render single item ── */
function renderItem(q) {
  const isList = state.view === 'list';
  const date = q.attempt_date
    ? new Date(q.attempt_date).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
    : (q.created_at ? new Date(q.created_at).toLocaleDateString() : '');

  const scoreHtml = q.percentage != null
    ? `<span class="qs-score">${q.percentage}%</span>`
    : '';

  const actionsHtml = buildActions(q);

  const leftHtml = `
    <div class="qs-item__left">
      <h3 class="qs-item__title">${escHtml(q.title)}</h3>
      ${q.description ? `<p class="qs-item__desc">${escHtml(q.description)}</p>` : ''}
      <div class="qs-item__meta">
        ${date ? `<span>${date}</span><span class="qs-item__meta-sep">&middot;</span>` : ''}
        ${badgeHtml(q.status)}
        ${q.attempt_count ? `<span class="qs-item__meta-sep">&middot;</span><span>${q.attempt_count} attempt${q.attempt_count !== 1 ? 's' : ''}</span>` : ''}
        ${scoreHtml ? `<span class="qs-item__meta-sep">&middot;</span>${scoreHtml}` : ''}
      </div>
    </div>
  `;

  if (isList) {
    return `
      <div class="qs-item" data-id="${q.id}" data-status="${q.status}">
        ${leftHtml}
        <div class="qs-item__actions">${actionsHtml}</div>
      </div>
    `;
  }

  return `
    <div class="qs-item" data-id="${q.id}" data-status="${q.status}">
      ${leftHtml}
      <div class="qs-item__actions">${actionsHtml}</div>
    </div>
  `;
}

function buildActions(q) {
  const parts = [];

  if (q.status === 'in_progress' && q.attempt_id) {
    parts.push(`<a href="${window.QS_ATTEMPT_URL.replace('1', q.id)}" class="qs-btn qs-btn--primary">Continue</a>`);
  } else if (q.status !== 'archived') {
    parts.push(`<a href="${window.QS_ATTEMPT_URL.replace('1', q.id)}" class="qs-btn qs-btn--primary">Start</a>`);
  }

  if (q.status === 'completed' && q.attempt_id) {
    parts.push(`<a href="${window.QS_RESULTS_URL}" class="qs-btn">View Results</a>`);
  }

  if (q.status === 'completed' && q.attempt_id) {
    parts.push(`<a href="${window.QS_ATTEMPT_URL.replace('1', q.id)}" class="qs-btn">Retake</a>`);
  }

  return parts.join('');
}

/* ── Render list ── */
function renderList(items, append = false) {
  const container = document.getElementById('qsContainer');
  const skeleton  = document.getElementById('qsSkeleton');
  const empty     = document.getElementById('qsEmpty');
  const loadWrap  = document.getElementById('qsLoadMoreWrap');

  if (skeleton) skeleton.remove();

  if (!append) container.innerHTML = '';

  if (!items.length && !append) {
    empty.classList.remove('hidden');
    loadWrap.classList.add('hidden');
    return;
  }

  empty.classList.add('hidden');
  items.forEach(q => {
    container.insertAdjacentHTML('beforeend', renderItem(q));
  });

  loadWrap.classList.toggle('hidden', !state.hasMore);
}

/* ── Fetch data ── */
async function fetchQuestionnaires(append = false) {
  const params = new URLSearchParams({
    format: 'json',
    page:   state.page,
  });
  if (state.filter !== 'all') params.set('status', state.filter);
  if (state.search) params.set('q', state.search);

  try {
    const res = await fetch(`${window.QS_LIST_URL}?${params}`, {
      headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    });
    if (!res.ok) throw new Error('fetch failed');
    const data = await res.json();

    if (!append) state.items = data.results || data.questionnaires || [];
    else state.items = state.items.concat(data.results || data.questionnaires || []);

    state.hasMore = !!data.next;

    fillSummary(data);
    renderList(append ? (data.results || data.questionnaires || []) : state.items, append);
  } catch (_) {
    const skeleton = document.getElementById('qsSkeleton');
    if (skeleton) skeleton.remove();
    document.getElementById('qsEmpty').classList.remove('hidden');
  }
}

function fillSummary(data) {
  const set = (id, v) => { const el = document.getElementById(id); if (el && v != null) el.textContent = v; };
  set('qsTotalAttempts', data.total_attempts ?? data.count ?? '—');
  set('qsBestScore',     data.best_score != null ? data.best_score + '%' : '—');
  set('qsActiveTopics',  data.active_topics ?? '—');
}

/* ── View toggle ── */
function setView(view) {
  state.view = view;
  const container = document.getElementById('qsContainer');
  container.className = `qs-container qs-container--${view}`;

  document.getElementById('qsListBtn').classList.toggle('qs-view-btn--active', view === 'list');
  document.getElementById('qsListBtn').setAttribute('aria-pressed', String(view === 'list'));
  document.getElementById('qsGridBtn').classList.toggle('qs-view-btn--active', view === 'grid');
  document.getElementById('qsGridBtn').setAttribute('aria-pressed', String(view === 'grid'));

  renderList(state.items);
}

/* ── Filter ── */
function setFilter(filter) {
  state.filter = filter;
  state.page   = 1;

  document.querySelectorAll('.qs-filter-btn').forEach(btn => {
    const active = btn.dataset.filter === filter;
    btn.classList.toggle('qs-filter-btn--active', active);
    btn.setAttribute('aria-pressed', String(active));
  });

  fetchQuestionnaires();
}

/* ── Boot ── */
function init() {
  
  fetchQuestionnaires();

  document.getElementById('qsListBtn').addEventListener('click', () => setView('list'));
  document.getElementById('qsGridBtn').addEventListener('click', () => setView('grid'));

  document.querySelectorAll('.qs-filter-btn').forEach(btn => {
    btn.addEventListener('click', () => setFilter(btn.dataset.filter));
  });

  const searchInput = document.getElementById('qsSearch');
  searchInput.addEventListener('input', debounce(() => {
    state.search = searchInput.value.trim();
    state.page   = 1;
    fetchQuestionnaires();
  }));

  document.getElementById('qsLoadMore').addEventListener('click', () => {
    state.page += 1;
    fetchQuestionnaires(true);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}