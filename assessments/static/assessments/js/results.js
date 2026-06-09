/* results.js */

const csrf = () =>
  (document.querySelector('#rsCsrfForm input[name="csrfmiddlewaretoken"]') || {}).value || '';

function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

/* ── Fetch all results ── */
async function loadResults() {
  try {
    
    const data = window.DATA;

    fillStrip(data);
    renderRows(data.results || data.attempts || []);
  } catch (_) {
    const skeleton = document.getElementById('rsSkeleton');
    if (skeleton) skeleton.remove();
    document.getElementById('rsEmpty').classList.remove('hidden');
  }
}

function fillStrip(data) {
  const set = (id, v) => { const el = document.getElementById(id); if (el && v != null) el.textContent = v; };
  set('rsCompleted', data.completed ?? data.total ?? '—');
  set('rsAvgPct',    data.avg_pct != null   ? data.avg_pct + '%'   : '—');
  set('rsBest',      data.best_score != null ? data.best_score + '%' : '—');
  set('rsPassed',    data.passed ?? '—');
}

function renderRows(attempts) {
  const list     = document.getElementById('rsList');
  const skeleton = document.getElementById('rsSkeleton');
  const empty    = document.getElementById('rsEmpty');

  if (skeleton) skeleton.remove();

  if (!attempts.length) {
    empty.classList.remove('hidden');
    return;
  }

  list.innerHTML = '';
  attempts.forEach(a => {
    const el = document.createElement('div');
    el.className = 'rs-row';
    el.setAttribute('tabindex', '0');
    el.setAttribute('role', 'button');
    el.setAttribute('aria-label', `Open result: ${a.title}`);

    const date = a.completed_at
      ? new Date(a.completed_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
      : '';

    const passed = a.passed != null
      ? `<span class="rs-badge rs-badge--${a.passed ? 'pass' : 'fail'}">${a.passed ? 'Passed' : 'Failed'}</span>`
      : '';

    el.innerHTML = `
      <div>
        <h3 class="rs-row__title">${escHtml(a.title || a.questionnaire_title || '')}</h3>
        <div class="rs-row__meta">
          ${date ? `<span>${date}</span>` : ''}
          ${a.attempt_number ? `<span>&middot;</span><span>Attempt #${a.attempt_number}</span>` : ''}
          ${passed}
        </div>
      </div>
      <span class="rs-row__score">${a.percentage != null ? a.percentage + '%' : '—'}</span>
      <svg class="rs-row__arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9,18 15,12 9,6"/></svg>
    `;

    el.addEventListener('click',  () => openModal(a));
    el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openModal(a); } });

    list.appendChild(el);
  });
}

/* ── Modal ── */
function openModal(attempt) {
  const backdrop = document.getElementById('rsModalBackdrop');
  backdrop.classList.remove('hidden');
  document.body.style.overflow = 'hidden';

  populateModal(attempt);

  // Focus modal for accessibility
  requestAnimationFrame(() => {
    document.getElementById('rsModalClose').focus();
  });
}

function closeModal() {
  document.getElementById('rsModalBackdrop').classList.add('hidden');
  document.body.style.overflow = '';
  document.getElementById('rsEmailToggle').checked = false;
  document.getElementById('rsEmailStatus').textContent = '';
  // Store current attempt id for download/review
  delete document.getElementById('rsModalBackdrop').dataset.attemptId;
}

function populateModal(attempt) {
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v ?? '—'; };

  set('rsModalTitle', attempt.title || attempt.questionnaire_title || 'Result');
  set('rsModalPct',   attempt.percentage != null ? attempt.percentage + '%' : '—');
  set('rsModalRaw',   attempt.raw_score ?? '—');
  set('rsModalMax',   attempt.max_score ?? '—');
  set('rsModalPercentile', attempt.percentile_rank != null ? attempt.percentile_rank + 'th' : '—');

  // Time taken
  if (attempt.started_at && attempt.completed_at) {
    const ms = new Date(attempt.completed_at) - new Date(attempt.started_at);
    set('rsModalTime', formatDuration(ms));
  } else {
    set('rsModalTime', '—');
  }

  // Animate ring
  animateRing(attempt.percentage || 0);

  // Badges
  const badgesEl = document.getElementById('rsModalBadges');
  badgesEl.innerHTML = '';
  if (attempt.passed != null) {
    const b = document.createElement('span');
    b.className = `rs-badge rs-badge--${attempt.passed ? 'pass' : 'fail'}`;
    b.textContent = attempt.passed ? 'Passed' : 'Failed';
    badgesEl.appendChild(b);
  }
  if (attempt.attempt_number) {
    const b = document.createElement('span');
    b.style.cssText = 'font-size:0.68rem;opacity:0.5;padding:2px 6px;';
    b.textContent = `Attempt #${attempt.attempt_number}`;
    badgesEl.appendChild(b);
  }

  // Breakdown
  renderBreakdown(attempt.breakdown || []);

  // Career highlights
  renderModalCareers(attempt.career_highlights || []);

  // Store attempt id on backdrop for action buttons
  document.getElementById('rsModalBackdrop').dataset.attemptId = attempt.attempt_id || attempt.id || '';

  // Wire action buttons
  const reviewBtn = document.getElementById('rsReviewBtn');
  if (attempt.attempt_id || attempt.id) {
    reviewBtn.href = `${window.RS_ATTEMPT_URL}?review=${attempt.attempt_id || attempt.id}`;
  } else {
    reviewBtn.removeAttribute('href');
    reviewBtn.style.opacity = '0.4';
    reviewBtn.style.pointerEvents = 'none';
  }
}

function animateRing(pct) {
  const circumference = 326.73;
  const fill = document.getElementById('rsRingFill');
  if (!fill) return;
  const offset = circumference - (pct / 100) * circumference;
  // Reset first for re-animation
  fill.style.transition = 'none';
  fill.style.strokeDashoffset = String(circumference);
  requestAnimationFrame(() => {
    fill.style.transition = 'stroke-dashoffset 1s cubic-bezier(0.4, 0, 0.2, 1)';
    fill.style.strokeDashoffset = String(offset);
  });
}

function renderBreakdown(breakdown) {
  const el = document.getElementById('rsBreakdown');
  const section = document.getElementById('rsSubscoreSection');
  if (!el) return;

  if (!breakdown.length) {
    section.style.display = 'none';
    return;
  }

  section.style.display = '';
  el.innerHTML = '';
  const max = Math.max(...breakdown.map(b => b.max || 1));

  breakdown.forEach(b => {
    const pct = Math.round(((b.score || 0) / (b.max || 1)) * 100);
    const item = document.createElement('div');
    item.className = 'rs-breakdown-item';
    item.innerHTML = `
      <span class="rs-breakdown-item__label">${escHtml(b.label)}</span>
      <div class="rs-breakdown-item__bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100" aria-label="${escHtml(b.label)}">
        <div class="rs-breakdown-item__fill" style="width:0%" data-target="${pct}%"></div>
      </div>
      <span class="rs-breakdown-item__val">${b.score}/${b.max}</span>
    `;
    el.appendChild(item);
  });

  // Animate bars
  requestAnimationFrame(() => {
    el.querySelectorAll('.rs-breakdown-item__fill').forEach(bar => {
      bar.style.width = bar.dataset.target;
    });
  });
}

function renderModalCareers(careers) {
  const el = document.getElementById('rsModalCareers');
  const section = document.getElementById('rsCareerSection');
  if (!el) return;

  if (!careers.length) {
    section.style.display = 'none';
    return;
  }

  section.style.display = '';
  el.innerHTML = '';
  careers.forEach(c => {
    const div = document.createElement('div');
    div.className = 'rs-modal-career';
    div.innerHTML = `
      <span class="rs-modal-career__title">${escHtml(c.title)}</span>
      <span class="rs-modal-career__weight">${c.recommendation_weight != null ? Math.round(c.recommendation_weight * 100) + '%' : ''}</span>
    `;
    el.appendChild(div);
  });
}

/* ── Email toggle ── */
function handleEmailToggle(attemptId) {
  const checked = document.getElementById('rsEmailToggle').checked;
  const statusEl = document.getElementById('rsEmailStatus');

  if (!attemptId) return;

  fetch(window.RS_LIST_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrf(),
    },
    body: JSON.stringify({ action: 'send_email', attempt_id: attemptId, send: checked }),
  })
    .then(r => r.json())
    .then(data => {
      statusEl.textContent = data.email_sent ? 'Email sent.' : (data.error || 'Could not send.');
    })
    .catch(() => {
      statusEl.textContent = 'Request failed.';
    });
}

/* ── Download ── */
function handleDownload(attemptId) {
  if (!attemptId) return;
  window.open(`${window.RS_LIST_URL}?download=pdf&attempt=${attemptId}`, '_blank', 'noopener');
}

/* ── Helpers ── */
function formatDuration(ms) {
  const total = Math.round(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/* ── Boot ── */
function init() {
  loadResults();

  document.getElementById('rsModalClose').addEventListener('click', closeModal);

  document.getElementById('rsModalBackdrop').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });

  document.getElementById('rsEmailToggle').addEventListener('change', () => {
    const attemptId = document.getElementById('rsModalBackdrop').dataset.attemptId;
    handleEmailToggle(attemptId);
  });

  document.getElementById('rsDownloadBtn').addEventListener('click', () => {
    const attemptId = document.getElementById('rsModalBackdrop').dataset.attemptId;
    handleDownload(attemptId);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}