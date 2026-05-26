/**
 * assessments/static/assessments/js/questionnaire_manage.js
 *
 * GET  window.QM_LIST_URL              → list of questionnaires
 * GET  window.QM_DETAIL_URL({id})      → full detail + statistics
 * POST window.QM_SAVE_URL({id})        → save edits (JSON body)
 *
 * JSON GET response shape: see inline JSDoc at parseDetail().
 * If your backend returns a different shape, adapt parseDetail() and parseStat().
 */

'use strict';

/* ─────────────────────────────────────────────────────────────
   STATE
───────────────────────────────────────────────────────────────*/
let allQuestionnaires = [];   // full list from server
let filteredList      = [];   // after search/filter
let activeId          = null; // currently selected questionnaire id
let activeDetail      = null; // full detail object from GET
let viewMode          = localStorage.getItem('qm_view') || 'grid'; // 'grid' | 'list'
let splitOpen         = false;

/* ─────────────────────────────────────────────────────────────
   CSRF
───────────────────────────────────────────────────────────────*/
const csrf = () =>
  (document.querySelector('#qmCsrfForm input[name="csrfmiddlewaretoken"]') || {}).value || '';

/* ─────────────────────────────────────────────────────────────
   URLS — replace {id} placeholder
───────────────────────────────────────────────────────────────*/
const detailUrl = id => window.QM_DETAIL_URL.replace('{id}', id) + '?include=full';
const saveUrl   = id => window.QM_SAVE_URL.replace('{id}', id);

/* ─────────────────────────────────────────────────────────────
   TOAST
───────────────────────────────────────────────────────────────*/
function toast (msg, type = 'info', duration = 3500) {
  const container = document.getElementById('qmToastContainer');
  const el = document.createElement('div');
  const icons = { success: '✓', error: '⚠', info: 'ℹ' };
  el.className   = `qm-toast qm-toast--${type}`;
  el.innerHTML   = `<span aria-hidden="true">${icons[type] || ''}</span><span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add('qm-toast--leaving');
    el.addEventListener('animationend', () => el.remove(), { once: true });
  }, duration);
}

/* ─────────────────────────────────────────────────────────────
   DATE FORMATTING
───────────────────────────────────────────────────────────────*/
function fmtDate (iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

/* ─────────────────────────────────────────────────────────────
   STATUS BADGE HTML
───────────────────────────────────────────────────────────────*/
function badgeHtml (status) {
  return `<span class="qm-status-badge qm-status-badge--${status}">${status}</span>`;
}

/* ─────────────────────────────────────────────────────────────
   1. INITIAL LIST LOAD
───────────────────────────────────────────────────────────────*/
async function loadList () {
  // Allow server-preloaded data to skip the AJAX call
  if (window.QM_INITIAL && Array.isArray(window.QM_INITIAL)) {
    allQuestionnaires = window.QM_INITIAL;
    applyFilter();
    return;
  }

  try {
    const res  = await fetch(window.QM_LIST_URL, { headers: { 'X-CSRFToken': csrf() } });
    const data = await res.json();
    // Accepts { results: [] } (DRF pagination) or plain []
    allQuestionnaires = Array.isArray(data) ? data : (data.results || []);
    applyFilter();
  } catch (err) {
    toast('Failed to load questionnaires.', 'error');
    console.error('[QM] list fetch error:', err);
    document.getElementById('qmCards').innerHTML = '';
    document.getElementById('qmEmpty').classList.remove('hidden');
  }
}

/* ─────────────────────────────────────────────────────────────
   2. FILTER / SEARCH
───────────────────────────────────────────────────────────────*/
function applyFilter () {
  const query  = document.getElementById('qmSearch').value.toLowerCase();
  const status = document.getElementById('qmStatusFilter').value;

  filteredList = allQuestionnaires.filter(q => {
    const matchText   = !query  || q.title.toLowerCase().includes(query)
                                || (q.description || '').toLowerCase().includes(query);
    const matchStatus = !status || q.status === status;
    return matchText && matchStatus;
  });

  renderCards();
  if (splitOpen) renderSplitList();
}

/* ─────────────────────────────────────────────────────────────
   3. CARD RENDERING
───────────────────────────────────────────────────────────────*/
function renderCards () {
  const container = document.getElementById('qmCards');
  const empty     = document.getElementById('qmEmpty');
  const countEl   = document.getElementById('qmGridCount');

  countEl.textContent = filteredList.length;

  if (!filteredList.length) {
    container.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  container.innerHTML = filteredList.map(q => `
    <article
      class="qm-card"
      role="listitem"
      tabindex="0"
      data-id="${q.id}"
      aria-label="${q.title}"
    >
      <div class="qm-card__header">
        <h3 class="qm-card__title">${q.title}</h3>
        ${badgeHtml(q.status)}
      </div>
      <p class="qm-card__desc">${q.description || 'No description.'}</p>
      <div class="qm-card__stats">
        <div class="qm-card__stat">
          <span class="qm-card__stat-val">${q.attempt_count ?? '—'}</span>
          <span>Attempts</span>
        </div>
        <div class="qm-card__stat">
          <span class="qm-card__stat-val">${q.participant_count ?? '—'}</span>
          <span>Participants</span>
        </div>
        <div class="qm-card__stat">
          <span class="qm-card__stat-val">${q.max_score ?? '—'}</span>
          <span>Max pts</span>
        </div>
      </div>
      <div class="qm-card__footer">
        <span>Modified ${fmtDate(q.date_modified)}</span>
        <span>Created ${fmtDate(q.date_created)}</span>
      </div>
    </article>
  `).join('');

  // Click + keyboard handlers
  container.querySelectorAll('.qm-card').forEach(card => {
    card.addEventListener('click',   () => openDetail(parseInt(card.dataset.id, 10)));
    card.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openDetail(parseInt(card.dataset.id, 10));
      }
    });
  });
}

/* ─────────────────────────────────────────────────────────────
   4. VIEW TOGGLE (grid / list)
───────────────────────────────────────────────────────────────*/
function setViewMode (mode) {
  viewMode = mode;
  localStorage.setItem('qm_view', mode);

  const container = document.getElementById('qmCards');
  container.className = `qm-cards qm-cards--${mode}`;

  document.getElementById('qmBtnGrid').classList.toggle('qm-view-btn--active', mode === 'grid');
  document.getElementById('qmBtnList').classList.toggle('qm-view-btn--active', mode === 'list');
}

/* ─────────────────────────────────────────────────────────────
   5. OPEN DETAIL — switch to split view + fetch full data
───────────────────────────────────────────────────────────────*/
async function openDetail (id) {
  activeId = id;
  splitOpen = true;

  // Show split, hide grid
  document.getElementById('qmGridView').classList.add('hidden');
  const split = document.getElementById('qmSplit');
  split.classList.remove('hidden');

  // Build left panel list
  renderSplitList();
  highlightSplitItem(id);

  // Show loader, hide content
  showDetailLoader(true);

  try {
    const res  = await fetch(detailUrl(id), { headers: { 'X-CSRFToken': csrf() } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    activeDetail = await res.json();
    renderDetail(activeDetail);
  } catch (err) {
    toast('Failed to load questionnaire details.', 'error');
    console.error('[QM] detail fetch error:', err);
    showDetailLoader(false);
  }
}

function showDetailLoader (loading) {
  document.getElementById('qmDetailLoader').classList.toggle('hidden', !loading);
  document.getElementById('qmDetailContent').classList.toggle('hidden', loading);
}

/* ─────────────────────────────────────────────────────────────
   6. SPLIT LEFT LIST
───────────────────────────────────────────────────────────────*/
function renderSplitList (filterQuery = '') {
  const ul   = document.getElementById('qmSplitList');
  const list = filterQuery
    ? allQuestionnaires.filter(q => q.title.toLowerCase().includes(filterQuery))
    : allQuestionnaires;

  ul.innerHTML = list.map(q => `
    <li
      class="qm-split-item ${q.id === activeId ? 'qm-split-item--active' : ''}"
      data-id="${q.id}"
      tabindex="0"
      role="option"
      aria-selected="${q.id === activeId}"
    >
      <span class="qm-split-item__title">${q.title}</span>
      <span class="qm-split-item__meta">
        ${badgeHtml(q.status)}
        <span>${fmtDate(q.date_modified)}</span>
      </span>
    </li>
  `).join('');

  ul.querySelectorAll('.qm-split-item').forEach(item => {
    const id = parseInt(item.dataset.id, 10);
    item.addEventListener('click',   () => id !== activeId && openDetail(id));
    item.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); id !== activeId && openDetail(id); }
    });
  });
}

function highlightSplitItem (id) {
  document.querySelectorAll('.qm-split-item').forEach(el => {
    const active = parseInt(el.dataset.id, 10) === id;
    el.classList.toggle('qm-split-item--active', active);
    el.setAttribute('aria-selected', active);
  });
}

/* ─────────────────────────────────────────────────────────────
   7. RENDER DETAIL (stats tab + edit tab)
───────────────────────────────────────────────────────────────*/
function renderDetail (data) {
  showDetailLoader(false);

  document.getElementById('qmDetailTitle').textContent = data.title;
  document.getElementById('qmDetailBadge').className   = `qm-status-badge qm-status-badge--${data.status}`;
  document.getElementById('qmDetailBadge').textContent = data.status;
  document.getElementById('qmBtnSave').classList.remove('hidden');
  document.getElementById('qmBtnDelete').classList.remove('hidden');

  renderStats(data);
  populateEditForm(data);
  updatePointsWidget();
}

/* ─────────────────────────────────────────────────────────────
   8. STATISTICS TAB
───────────────────────────────────────────────────────────────*/
function statCard (label, value, mod = '') {
  return `
    <div class="qm-stat-card">
      <span class="qm-stat-card__label">${label}</span>
      <span class="qm-stat-card__value ${mod}">${value ?? '—'}</span>
    </div>`;
}

function renderStats (data) {
  const s = data.statistics || {};

  document.getElementById('qmStatsGrid').innerHTML =
    statCard('Attempts',        s.attempt_count,               '') +
    statCard('Participants',    s.participant_count,            '') +
    statCard('Avg score',       s.average_score != null ? s.average_score.toFixed(1) : '—', 'qm-stat-card__value--primary') +
    statCard('Highest score',   s.highest_score,                'qm-stat-card__value--success') +
    statCard('Lowest score',    s.lowest_score,                 'qm-stat-card__value--error') +
    statCard('Completion rate', s.completion_rate != null ? `${s.completion_rate.toFixed(1)}%` : '—', '');

  document.getElementById('qmDetailMeta').innerHTML = [
    ['Status',        badgeHtml(data.status)],
    ['Max score',     data.max_score],
    ['Time limit',    data.time_limit_minutes ? `${data.time_limit_minutes} min` : '—'],
    ['Randomised',    data.is_randomised ? 'Yes' : 'No'],
    ['Created',       fmtDate(data.date_created)],
    ['Modified',      fmtDate(data.date_modified)],
    ['Questions',     (data.questions || []).length],
  ].map(([k, v]) => `
    <div class="qm-meta-row">
      <span class="qm-meta-key">${k}</span>
      <span class="qm-meta-val">${v ?? '—'}</span>
    </div>`).join('');

  const tags = data.tags || [];
  document.getElementById('qmDetailTagsView').innerHTML = tags.length
    ? tags.map(t => `
        <span class="qm-tag-chip-view ${t.is_primary ? 'qm-tag-chip-view--primary' : ''}">
          ${t.tag}${t.is_primary ? ' ★' : ''}
          <small style="opacity:.7">${t.coupling_strength != null ? ` (${t.coupling_strength})` : ''}</small>
        </span>`).join('')
    : '<span style="color:var(--text-muted);font-size:.875rem">No tags.</span>';
}

/* ─────────────────────────────────────────────────────────────
   9. EDIT FORM POPULATION
───────────────────────────────────────────────────────────────*/
function val (id, v)  { const el = document.getElementById(id); if (el) el.value   = v ?? ''; }
function chk (id, v)  { const el = document.getElementById(id); if (el) el.checked = !!v; }

function populateEditForm (data) {
  val('qme_title',        data.title);
  val('qme_description',  data.description);
  val('qme_instructions', data.instructions);
  val('qme_status',       data.status);
  val('qme_max_score',    data.max_score);
  val('qme_time_limit',   data.time_limit_minutes);
  chk('qme_randomised',   data.is_randomised);

  renderEditTags(data.tags || []);
  renderEditQuestions(data.questions || []);
}

/* ── Tags editor ── */
function renderEditTags (tags) {
  const list = document.getElementById('qmEditTagList');
  list.innerHTML = '';
  tags.forEach((t, i) => list.appendChild(buildTagEditRow(t, i)));
}

function buildTagEditRow (tag, i) {
  const entry = document.createElement('div');
  entry.className  = 'qn-entry';
  entry.dataset.tagId = tag.id || '';

  entry.innerHTML = `
    <div class="qn-entry__header">
      <span class="qn-entry__title">Tag ${i + 1}${tag.id ? '' : ' (new)'}</span>
      <button type="button" class="qn-entry__remove" aria-label="Remove tag">✕</button>
    </div>
    <div class="qn-entry__grid">
      <div class="form-group">
        <label class="form-label">Tag name</label>
        <input class="form-input qme-tag-name" type="text" value="${tag.tag || ''}" placeholder="e.g. Biology" />
      </div>
      <div class="form-group">
        <label class="form-label">Coupling strength</label>
        <input class="form-input qme-tag-cs" type="number" min="0" max="1" step="0.01" value="${tag.coupling_strength ?? ''}" />
      </div>
      <div class="form-group qm-toggle-row">
        <label class="form-label">Primary?</label>
        <input class="toggle-checkbox qme-tag-primary" type="checkbox" ${tag.is_primary ? 'checked' : ''} />
      </div>
    </div>
  `;

  entry.querySelector('.qn-entry__remove').addEventListener('click', () => entry.remove());
  return entry;
}

/* ── Questions editor ── */
function renderEditQuestions (questions) {
  const list = document.getElementById('qmEditQuestionList');
  list.innerHTML = '';
  questions.forEach((q, i) => list.appendChild(buildQuestionCard(q, i)));
}

const Q_TYPES = ['MCQ','MULTI_SELECT','NUMERIC','TEXT','LIKERT','RANKING'];

function buildQuestionCard (q, i) {
  const card = document.createElement('div');
  card.className    = 'qm-q-card';
  card.dataset.qId  = q.id || '';

  card.innerHTML = `
    <div class="qm-q-card__header">
      <span class="qm-q-card__handle" aria-hidden="true">⠿</span>
      <span class="qm-q-card__label">${q.question_text || `Question ${i + 1}`}</span>
      <span class="qm-q-card__type-badge">${q.question_type || 'MCQ'}</span>
      <div class="qm-q-card__actions">
        <button type="button" class="qm-q-card__btn qm-btn-move-up"   aria-label="Move up"   title="Move up">↑</button>
        <button type="button" class="qm-q-card__btn qm-btn-move-down" aria-label="Move down" title="Move down">↓</button>
        <button type="button" class="qm-q-card__btn qm-btn-toggle-q"  aria-label="Collapse"  title="Collapse">⌄</button>
        <button type="button" class="qm-q-card__btn qm-q-card__btn--del qm-btn-del-q" aria-label="Delete question">✕</button>
      </div>
    </div>
    <div class="qm-q-card__body">
      <div class="form-group qm-q-col-full">
        <label class="form-label">Question text</label>
        <textarea class="form-input form-textarea qme-q-text" rows="2">${q.question_text || ''}</textarea>
      </div>
      <div class="form-group">
        <label class="form-label">Type</label>
        <select class="form-input qme-q-type">
          ${Q_TYPES.map(t => `<option value="${t}" ${q.question_type === t ? 'selected' : ''}>${t}</option>`).join('')}
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Weight</label>
        <input class="form-input qme-q-weight" type="number" min="0.01" step="0.01" value="${q.weight ?? ''}" />
      </div>
      <div class="form-group">
        <label class="form-label">Max points</label>
        <input class="form-input qme-q-maxpts" type="number" min="0.01" step="0.01" value="${q.max_points ?? ''}" />
      </div>
      <div class="form-group">
        <label class="form-label">Order</label>
        <input class="form-input qme-q-order" type="number" min="1" step="1" value="${q.order ?? i + 1}" />
      </div>
      <div class="form-group">
        <label class="form-label">Randomisation group</label>
        <input class="form-input qme-q-rg" type="text" value="${q.randomisation_group || ''}" placeholder="group-a" />
      </div>
      <div class="form-group qm-toggle-row">
        <label class="form-label">Required?</label>
        <input class="toggle-checkbox qme-q-required" type="checkbox" ${q.is_required ? 'checked' : ''} />
      </div>
      <div class="form-group qm-q-col-full qme-numeric-wrap" style="display:${q.question_type === 'NUMERIC' ? '' : 'none'}">
        <label class="form-label">Numeric config (JSON)</label>
        <textarea class="form-input form-textarea qn-json-editor qme-q-numeric" rows="2">${q.numeric_config ? JSON.stringify(q.numeric_config, null, 2) : ''}</textarea>
      </div>
      <div class="form-group qm-q-col-full">
        <label class="form-label">Explanation</label>
        <textarea class="form-input form-textarea qme-q-explanation" rows="2">${q.explanation || ''}</textarea>
      </div>
      <!-- Choices -->
      <div class="form-group qm-q-col-full">
        <label class="form-label">Choices</label>
        <div class="qm-choices-list qme-choices"></div>
        <button type="button" class="btn-outline qme-add-choice" style="margin-top:var(--spacing-xs);font-size:.8rem;padding:.3rem .75rem">+ Add choice</button>
      </div>
    </div>
  `;

  /* Populate existing choices */
  const choicesEl = card.querySelector('.qme-choices');
  (q.choices || []).forEach(c => choicesEl.appendChild(buildChoiceRow(c)));

  /* Type change → show/hide numeric config */
  card.querySelector('.qme-q-type').addEventListener('change', function () {
    card.querySelector('.qme-numeric-wrap').style.display = this.value === 'NUMERIC' ? '' : 'none';
    card.querySelector('.qm-q-card__type-badge').textContent = this.value;
  });

  /* Weight changes → update points widget */
  card.querySelector('.qme-q-weight').addEventListener('input', updatePointsWidget);

  /* Header click → collapse body */
  card.querySelector('.qm-q-card__header').addEventListener('click', e => {
    if (e.target.closest('button')) return;
    card.querySelector('.qm-q-card__body').classList.toggle('collapsed');
  });

  /* Update label on text change */
  card.querySelector('.qme-q-text').addEventListener('input', function () {
    card.querySelector('.qm-q-card__label').textContent = this.value || `Question ${i + 1}`;
  });

  /* Move up / down */
  card.querySelector('.qm-btn-move-up').addEventListener('click', () => {
    const prev = card.previousElementSibling;
    if (prev) card.parentNode.insertBefore(card, prev);
  });
  card.querySelector('.qm-btn-move-down').addEventListener('click', () => {
    const next = card.nextElementSibling;
    if (next) card.parentNode.insertBefore(next, card);
  });

  /* Toggle collapse button */
  card.querySelector('.qm-btn-toggle-q').addEventListener('click', () => {
    card.querySelector('.qm-q-card__body').classList.toggle('collapsed');
  });

  /* Delete question */
  card.querySelector('.qm-btn-del-q').addEventListener('click', () => {
    if (confirm('Delete this question?')) { card.remove(); updatePointsWidget(); }
  });

  /* Add choice button */
  card.querySelector('.qme-add-choice').addEventListener('click', () => {
    choicesEl.appendChild(buildChoiceRow({}));
  });

  return card;
}

function buildChoiceRow (c) {
  const row = document.createElement('div');
  row.className    = 'qm-choice-row';
  row.dataset.cId  = c.id || '';

  row.innerHTML = `
    <input class="form-input qme-c-key" type="text"   value="${c.choice_key || ''}" placeholder="A" style="text-align:center;font-weight:700" />
    <input class="form-input qme-c-text" type="text"  value="${c.choice_text || ''}" placeholder="Choice text…" />
    <input class="toggle-checkbox qme-c-correct" type="checkbox" title="Correct?" ${c.is_correct ? 'checked' : ''} />
    <input class="form-input qme-c-score" type="number" value="${c.partial_score ?? ''}" min="0" max="1" step="0.01" placeholder="0.0" style="width:4rem" />
    <button type="button" class="qm-choice-row__remove" aria-label="Remove choice">✕</button>
  `;

  row.querySelector('.qm-choice-row__remove').addEventListener('click', () => row.remove());
  return row;
}

/* ─────────────────────────────────────────────────────────────
   10. REMAINING POINTS WIDGET
───────────────────────────────────────────────────────────────*/
function updatePointsWidget () {
  const max    = parseFloat(document.getElementById('qme_max_score').value) || 0;
  const used   = Array.from(document.querySelectorAll('.qme-q-weight'))
                   .reduce((s, el) => s + (parseFloat(el.value) || 0), 0);
  const widget = document.getElementById('qmEditPoints');

  document.getElementById('qmPointsUsed').textContent = used.toFixed(1);
  document.getElementById('qmPointsMax').textContent  = `/ ${max}`;

  widget.classList.remove('qn-points-widget--warn', 'qn-points-widget--over');
  if (used > max)               widget.classList.add('qn-points-widget--over');
  else if (used > max * 0.9)    widget.classList.add('qn-points-widget--warn');
}

/* ─────────────────────────────────────────────────────────────
   11. BUILD SAVE PAYLOAD
───────────────────────────────────────────────────────────────*/
function buildPayload () {
  const g = id => document.getElementById(id);

  /* Tags */
  const tags = Array.from(document.querySelectorAll('#qmEditTagList .qn-entry')).map(entry => ({
    id:                entry.dataset.tagId ? parseInt(entry.dataset.tagId, 10) : undefined,
    tag:               entry.querySelector('.qme-tag-name').value.trim(),
    coupling_strength: parseFloat(entry.querySelector('.qme-tag-cs').value) || null,
    is_primary:        entry.querySelector('.qme-tag-primary').checked,
  }));

  /* Questions */
  const questions = Array.from(document.querySelectorAll('#qmEditQuestionList .qm-q-card')).map((card, i) => {
    const choices = Array.from(card.querySelectorAll('.qme-choices .qm-choice-row')).map(row => ({
      id:            row.dataset.cId  ? parseInt(row.dataset.cId, 10) : undefined,
      choice_key:    row.querySelector('.qme-c-key').value.trim().toUpperCase(),
      choice_text:   row.querySelector('.qme-c-text').value.trim(),
      is_correct:    row.querySelector('.qme-c-correct').checked,
      partial_score: parseFloat(row.querySelector('.qme-c-score').value) || 0,
      order:         i + 1,
    }));

    const numericRaw = card.querySelector('.qme-q-numeric').value.trim();
    let numeric_config = null;
    if (numericRaw) {
      try { numeric_config = JSON.parse(numericRaw); } catch { /* invalid JSON handled server-side */ }
    }

    return {
      id:                  card.dataset.qId ? parseInt(card.dataset.qId, 10) : undefined,
      question_text:       card.querySelector('.qme-q-text').value.trim(),
      question_type:       card.querySelector('.qme-q-type').value,
      weight:              parseFloat(card.querySelector('.qme-q-weight').value) || null,
      max_points:          parseFloat(card.querySelector('.qme-q-maxpts').value) || null,
      order:               parseInt(card.querySelector('.qme-q-order').value, 10) || i + 1,
      randomisation_group: card.querySelector('.qme-q-rg').value.trim() || null,
      is_required:         card.querySelector('.qme-q-required').checked,
      explanation:         card.querySelector('.qme-q-explanation').value.trim(),
      numeric_config,
      choices,
    };
  });

  return {
    id:                  activeId,
    title:               g('qme_title').value.trim(),
    description:         g('qme_description').value.trim(),
    instructions:        g('qme_instructions').value.trim(),
    status:              g('qme_status').value,
    max_score:           parseFloat(g('qme_max_score').value) || null,
    time_limit_minutes:  parseInt(g('qme_time_limit').value, 10) || null,
    is_randomised:       g('qme_randomised').checked,
    tags,
    questions,
  };
}

/* ─────────────────────────────────────────────────────────────
   12. SAVE
───────────────────────────────────────────────────────────────*/
async function saveEdits () {
  const btn     = document.getElementById('qmBtnSave');
  const errEl   = document.getElementById('qmEditError');

  errEl.classList.add('hidden');
  btn.classList.add('loading');
  btn.disabled = true;

  const payload = buildPayload();

  // Client-side guard: total weight vs max_score
  const totalWeight = (payload.questions || []).reduce((s, q) => s + (q.weight || 0), 0);
  if (payload.max_score && totalWeight > payload.max_score) {
    errEl.textContent = `Total weight (${totalWeight}) exceeds max score (${payload.max_score}).`;
    errEl.classList.remove('hidden');
    btn.classList.remove('loading');
    btn.disabled = false;
    return;
  }

  try {
    const res = await fetch(saveUrl(activeId), {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken':  csrf(),
      },
      body: JSON.stringify(payload),
    });

    if (res.ok || res.status === 200 || res.status === 201) {
      const updated = await res.json();
      activeDetail  = updated;

      // Refresh stats tab and header
      document.getElementById('qmDetailTitle').textContent = updated.title || payload.title;
      renderStats(updated);

      // Refresh card in left list
      const idx = allQuestionnaires.findIndex(q => q.id === activeId);
      if (idx > -1) {
        allQuestionnaires[idx] = { ...allQuestionnaires[idx], ...updated };
        renderSplitList();
        highlightSplitItem(activeId);
      }

      toast('Questionnaire saved!', 'success');
      switchTab('stats');

    } else {
      let data = {};
      try { data = await res.json(); } catch { /* not JSON */ }
      const msg = typeof data.errors === 'object'
        ? Object.entries(data.errors).map(([f, m]) => `${f}: ${Array.isArray(m) ? m.join(' ') : m}`).join(' · ')
        : (data.error || data.detail || `Server error ${res.status}`);
      errEl.textContent = msg;
      errEl.classList.remove('hidden');
      toast('Save failed. See errors above.', 'error');
    }

  } catch (err) {
    errEl.textContent = 'Network error. Please try again.';
    errEl.classList.remove('hidden');
    toast('Network error.', 'error');
    console.error('[QM] save error:', err);

  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

/* ─────────────────────────────────────────────────────────────
   13. TABS
───────────────────────────────────────────────────────────────*/
function switchTab (tab) {
  const panels = { stats: 'qmPanelStats', edit: 'qmPanelEdit' };
  const btns   = { stats: 'qmTabStats',   edit: 'qmTabEdit'   };

  Object.entries(panels).forEach(([key, panelId]) => {
    const active = key === tab;
    document.getElementById(panelId).classList.toggle('hidden', !active);
    const btn = document.getElementById(btns[key]);
    btn.classList.toggle('qm-tab--active', active);
    btn.setAttribute('aria-selected', active);
  });

  // Show Save button only on edit tab
  document.getElementById('qmBtnSave').classList.toggle('hidden', tab !== 'edit');
}

/* ─────────────────────────────────────────────────────────────
   14. CLOSE SPLIT VIEW
───────────────────────────────────────────────────────────────*/
function closeSplit () {
  splitOpen  = false;
  activeId   = null;
  activeDetail = null;
  document.getElementById('qmSplit').classList.add('hidden');
  document.getElementById('qmGridView').classList.remove('hidden');
  applyFilter();
}

/* ─────────────────────────────────────────────────────────────
   15. KEYBOARD NAVIGATION
───────────────────────────────────────────────────────────────*/
function initKeyboard () {
  document.addEventListener('keydown', e => {
    if (!splitOpen) return;

    if (e.key === 'Escape') { closeSplit(); return; }

    const items = Array.from(document.querySelectorAll('.qm-split-item'));
    if (!items.length) return;

    const activeIdx = items.findIndex(el => parseInt(el.dataset.id, 10) === activeId);

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const next = items[Math.min(activeIdx + 1, items.length - 1)];
      if (next) { next.focus(); openDetail(parseInt(next.dataset.id, 10)); }
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = items[Math.max(activeIdx - 1, 0)];
      if (prev) { prev.focus(); openDetail(parseInt(prev.dataset.id, 10)); }
    }
  });
}

/* ─────────────────────────────────────────────────────────────
   16. EDIT — ADD TAG / QUESTION
───────────────────────────────────────────────────────────────*/
function initEditButtons () {
  document.getElementById('qmAddTag').addEventListener('click', () => {
    const list = document.getElementById('qmEditTagList');
    list.appendChild(buildTagEditRow({}, list.children.length));
  });

  document.getElementById('qmAddQuestion').addEventListener('click', () => {
    const list = document.getElementById('qmEditQuestionList');
    list.appendChild(buildQuestionCard({}, list.children.length));
    updatePointsWidget();
  });

  document.getElementById('qme_max_score').addEventListener('input', updatePointsWidget);
}

/* ─────────────────────────────────────────────────────────────
   BOOT
───────────────────────────────────────────────────────────────*/
function init () {
  // Apply initial view mode
  setViewMode(viewMode);

  // View toggle
  document.getElementById('qmBtnGrid').addEventListener('click', () => setViewMode('grid'));
  document.getElementById('qmBtnList').addEventListener('click', () => setViewMode('list'));

  // Search + filter
  const debounce = (fn, ms = 250) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
  document.getElementById('qmSearch').addEventListener('input', debounce(applyFilter));
  document.getElementById('qmStatusFilter').addEventListener('change', applyFilter);

  // Split panel controls
  document.getElementById('qmBtnCloseSplit').addEventListener('click', closeSplit);
  document.getElementById('qmSplitSearch').addEventListener('input', debounce(function () {
    renderSplitList(this.value.toLowerCase());
    highlightSplitItem(activeId);
  }));

  // Tabs
  document.getElementById('qmTabStats').addEventListener('click', () => switchTab('stats'));
  document.getElementById('qmTabEdit').addEventListener('click',  () => switchTab('edit'));

  // Save
  document.getElementById('qmBtnSave').addEventListener('click', saveEdits);

  // Edit panel dynamic buttons
  initEditButtons();

  // Keyboard shortcuts
  initKeyboard();

  // Load list
  loadList();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}