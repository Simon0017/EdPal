/**
 * assessments/static/assessments/js/questionnaire_attempt.js
 *
 * DEPENDS ON (injected by template):
 *   window.ATTEMPT_URL      — POST endpoint
 *   window.QUESTIONNAIRE_ID — questionnaire pk
 *   window.QA_DATA          — full questionnaire JSON from server
 *
 * POST payload:
 *   { questionnaire_id, answers: [{ question_id, answer_value }], send_email: bool }
 *
 * SUCCESS response expected:
 *   { score, percentage, passed, feedback, details, email_sent, max_score }
 */

'use strict';

/* ─────────────────────────────────────────────────────────────
   STATE
───────────────────────────────────────────────────────────────*/
let questions    = [];          // ordered array from QA_DATA.questions
let answers      = {};          // { question_id: answer_value }
let mode         = 'longform';  // 'longform' | 'step'
let currentStep  = 0;           // 0-based index, step mode only
let timerHandle  = null;
let secondsLeft  = 0;

/* ─────────────────────────────────────────────────────────────
   CSRF
───────────────────────────────────────────────────────────────*/
const csrf = () =>
  (document.querySelector('#qaCsrfForm input[name="csrfmiddlewaretoken"]') || {}).value || '';

/* ─────────────────────────────────────────────────────────────
   INIT
───────────────────────────────────────────────────────────────*/
function init () {
    
  const data = window.QA_DATA;
  if (!data || !Array.isArray(data.questions)) {
    document.getElementById('qaSkeleton').innerHTML =
      '<p style="color:var(--color-error)">Failed to load questionnaire data.</p>';
    return;
  }

  questions = data.questions || [];

  // Hide skeleton
  document.getElementById('qaSkeleton').remove();

  // Render all questions
  renderAllQuestions();
  renderOverview();

  // Timer
  if (data.time_limit_minutes) {
    secondsLeft = data.time_limit_minutes * 60;
    startTimer();
  } else {
    const timerEl = document.getElementById('qaTimer');
    if (timerEl) timerEl.style.display = 'none';
  }

  // Mode buttons
  document.getElementById('qaBtnLongForm').addEventListener('click', () => setMode('longform'));
  document.getElementById('qaBtnStepMode').addEventListener('click', () => setMode('step'));

  // Step nav
  document.getElementById('qaBtnPrev').addEventListener('click', () => navigateStep(-1));
  document.getElementById('qaBtnNext').addEventListener('click', () => navigateStep(1));

  // Submit
  document.getElementById('qaBtnSubmit').addEventListener('click', handleSubmit);

  // Modal close
  document.getElementById('qaModalClose').addEventListener('click', closeModal);
  document.getElementById('qaModalBackdrop').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
  });

  // Email resend in modal
  document.getElementById('qaModalSendEmail').addEventListener('click', () => sendEmail());

  // Set initial mode (long-form default)
  setMode('longform');
}

/* ─────────────────────────────────────────────────────────────
   RENDER ALL QUESTIONS
───────────────────────────────────────────────────────────────*/
function renderAllQuestions () {
  const container = document.getElementById('qaQuestions');
  container.innerHTML = '';

  questions.forEach((q, i) => {
    const card = buildQuestionCard(q, i);
    container.appendChild(card);
  });
}

/* ─────────────────────────────────────────────────────────────
   QUESTION CARD BUILDER
───────────────────────────────────────────────────────────────*/
function buildQuestionCard (q, index) {
  const card = document.createElement('div');
  card.className     = 'qa-question-card';
  card.id            = `qa-card-${q.id}`;
  card.dataset.qId   = q.id;
  card.dataset.index = index;

  // Header
  const header = document.createElement('div');
  header.className = 'qa-q-header';

  const numBadge = document.createElement('div');
  numBadge.className   = 'qa-q-number';
  numBadge.textContent = index + 1;

  const meta = document.createElement('div');
  meta.className = 'qa-q-meta';

  const text = document.createElement('p');
  text.className   = 'qa-q-text';
  text.textContent = q.question_text;

  const badges = document.createElement('div');
  badges.className = 'qa-q-badges';
  badges.innerHTML = `<span class="qa-q-type-badge">${q.question_type}</span>
    ${q.is_required ? '<span class="qa-q-required-badge">Required</span>' : ''}`;

  meta.appendChild(text);
  meta.appendChild(badges);
  header.appendChild(numBadge);
  header.appendChild(meta);
  card.appendChild(header);

  // Answer area — delegated by type
  const answerArea = buildAnswerArea(q);
  card.appendChild(answerArea);

  // Explanation hint (shown after interaction if present)
  if (q.explanation) {
    const hint = document.createElement('div');
    hint.className = 'qa-explanation-hint hidden';
    hint.id        = `qa-hint-${q.id}`;
    hint.innerHTML = `
      <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14" aria-hidden="true" style="flex-shrink:0;color:var(--color-primary)">
        <path fill-rule="evenodd" d="M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0Zm-7-4a1 1 0 1 1-2 0 1 1 0 0 1 2 0ZM9 9a.75.75 0 0 0 0 1.5h.253a.25.25 0 0 1 .244.304l-.459 2.066A1.75 1.75 0 0 0 10.747 15H11a.75.75 0 0 0 0-1.5h-.253a.25.25 0 0 1-.244-.304l.459-2.066A1.75 1.75 0 0 0 9.253 9H9Z" clip-rule="evenodd"/>
      </svg>
      <span>${q.explanation}</span>`;
    card.appendChild(hint);
  }

  return card;
}

/* ─────────────────────────────────────────────────────────────
   ANSWER AREA — delegates to type-specific builders
───────────────────────────────────────────────────────────────*/
function buildAnswerArea (q) {
  const wrap = document.createElement('div');
  wrap.className = 'qa-answer-area';

  switch (q.question_type) {
    case 'MCQ':          wrap.appendChild(buildMCQ(q));          break;
    case 'MULTI':
    case 'MULTI_SELECT': wrap.appendChild(buildMultiSelect(q));  break;
    case 'TEXT':         wrap.appendChild(buildText(q));         break;
    case 'NUMERIC':      wrap.appendChild(buildNumeric(q));      break;
    case 'LIKERT':       wrap.appendChild(buildLikert(q));       break;
    case 'RANKING':      wrap.appendChild(buildRanking(q));      break;
    default:             wrap.appendChild(buildText(q));         break;
  }

  return wrap;
}

/* ── MCQ — single radio ── */
function buildMCQ (q) {
  const list = document.createElement('div');
  list.className = 'qa-choices';

  (q.choices || []).forEach(c => {
    const label = document.createElement('label');
    label.className = 'qa-choice-label';
    label.htmlFor   = `qa-${q.id}-${c.choice_key}`;

    const radio = document.createElement('input');
    radio.type      = 'radio';
    radio.className = 'qa-choice-input';
    radio.name      = `qa-mcq-${q.id}`;
    radio.id        = `qa-${q.id}-${c.choice_key}`;
    radio.value     = c.choice_key;

    radio.addEventListener('change', () => {
      recordAnswer(q.id, c.choice_key);
      // Update selected styling
      list.querySelectorAll('.qa-choice-label').forEach(l => l.classList.remove('qa-choice-label--selected'));
      label.classList.add('qa-choice-label--selected');
      showHint(q.id);
    });

    const keySpan  = document.createElement('span');
    keySpan.className   = 'qa-choice-key';
    keySpan.textContent = c.choice_key;

    const textSpan = document.createElement('span');
    textSpan.textContent = c.choice_text;

    label.appendChild(radio);
    label.appendChild(keySpan);
    label.appendChild(textSpan);
    list.appendChild(label);
  });

  return list;
}

/* ── MULTI_SELECT — checkboxes ── */
function buildMultiSelect (q) {
  const list = document.createElement('div');
  list.className = 'qa-choices';

  const updateMulti = () => {
    const selected = Array.from(list.querySelectorAll('input:checked')).map(i => i.value);
    recordAnswer(q.id, selected.length ? selected : null);
    showHint(q.id);
  };

  (q.choices || []).forEach(c => {
    const label = document.createElement('label');
    label.className = 'qa-choice-label';
    label.htmlFor   = `qa-${q.id}-${c.choice_key}`;

    const chk = document.createElement('input');
    chk.type      = 'checkbox';
    chk.className = 'qa-choice-input';
    chk.id        = `qa-${q.id}-${c.choice_key}`;
    chk.value     = c.choice_key;

    chk.addEventListener('change', () => {
      label.classList.toggle('qa-choice-label--selected', chk.checked);
      updateMulti();
    });

    const keySpan  = document.createElement('span');
    keySpan.className   = 'qa-choice-key';
    keySpan.textContent = c.choice_key;

    const textSpan = document.createElement('span');
    textSpan.textContent = c.choice_text;

    label.appendChild(chk);
    label.appendChild(keySpan);
    label.appendChild(textSpan);
    list.appendChild(label);
  });

  return list;
}

/* ── TEXT — textarea ── */
function buildText (q) {
  const ta = document.createElement('textarea');
  ta.className   = 'form-input form-textarea qa-text-answer';
  ta.placeholder = 'Type your answer here…';
  ta.rows        = 5;
  ta.setAttribute('aria-label', `Answer for question ${q.id}`);

  // Debounced record
  let debTimer;
  ta.addEventListener('input', () => {
    clearTimeout(debTimer);
    debTimer = setTimeout(() => {
      recordAnswer(q.id, ta.value.trim() || null);
    }, 400);
  });

  return ta;
}

/* ── NUMERIC — number input with config ── */
function buildNumeric (q) {
  const cfg  = q.numeric_config || {};
  const wrap = document.createElement('div');
  wrap.className = 'qa-numeric-wrap';

  const input = document.createElement('input');
  input.type      = 'number';
  input.className = 'form-input qa-numeric-input';
  if (cfg.min !== undefined) input.min  = cfg.min;
  if (cfg.max !== undefined) input.max  = cfg.max;
  if (cfg.step)              input.step = cfg.step;
  input.placeholder = cfg.min !== undefined ? `${cfg.min} – ${cfg.max}` : 'Enter a number';
  input.setAttribute('aria-label', `Numeric answer for question ${q.id}`);

  input.addEventListener('change', () => {
    const v = parseFloat(input.value);
    recordAnswer(q.id, isNaN(v) ? null : v);
  });

  wrap.appendChild(input);

  if (cfg.unit) {
    const unit = document.createElement('span');
    unit.className   = 'qa-numeric-unit';
    unit.textContent = cfg.unit;
    wrap.appendChild(unit);
  }

  if (cfg.min !== undefined && cfg.max !== undefined) {
    const hint = document.createElement('p');
    hint.className   = 'qa-numeric-hint';
    hint.textContent = `Range: ${cfg.min} – ${cfg.max}${cfg.step ? ` (step ${cfg.step})` : ''}${cfg.unit ? ` ${cfg.unit}` : ''}`;
    wrap.appendChild(hint);
  }

  return wrap;
}

/* ── LIKERT — styled radio scale ── */
function buildLikert (q) {
  const row  = document.createElement('div');
  row.className = 'qa-likert';
  row.setAttribute('role', 'group');
  row.setAttribute('aria-label', 'Likert scale');

  (q.choices || []).forEach(c => {
    const option = document.createElement('div');
    option.className = 'qa-likert-option';

    const radio = document.createElement('input');
    radio.type  = 'radio';
    radio.name  = `qa-likert-${q.id}`;
    radio.id    = `qa-l-${q.id}-${c.choice_key}`;
    radio.value = c.choice_key;

    const btn = document.createElement('label');
    btn.className = 'qa-likert-btn';
    btn.htmlFor   = radio.id;
    btn.setAttribute('role', 'radio');
    btn.textContent = c.choice_key;

    const labelText = document.createElement('span');
    labelText.className   = 'qa-likert-text';
    labelText.textContent = c.choice_text;

    radio.addEventListener('change', () => {
      // Update all btn styles
      row.querySelectorAll('.qa-likert-btn').forEach(b => b.classList.remove('qa-likert-btn--selected'));
      btn.classList.add('qa-likert-btn--selected');
      recordAnswer(q.id, c.choice_key);
      showHint(q.id);
    });

    option.appendChild(radio);
    option.appendChild(btn);
    option.appendChild(labelText);
    row.appendChild(option);
  });

  return row;
}

/* ── RANKING — drag-to-reorder ── */
function buildRanking (q) {
  const list = document.createElement('div');
  list.className = 'qa-ranking';

  const updateRanking = () => {
    const order = Array.from(list.children).map(item => item.dataset.key);
    recordAnswer(q.id, order);
  };

  let dragSrc = null;

  (q.choices || []).forEach((c, i) => {
    const item = document.createElement('div');
    item.className       = 'qa-ranking-item';
    item.draggable       = true;
    item.dataset.key     = c.choice_key;
    item.dataset.qId     = q.id;

    item.innerHTML = `
      <span class="qa-ranking-handle" aria-hidden="true">
        <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
          <path d="M7 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm0 6a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm0 6a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm6-12a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm0 6a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm0 6a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z"/>
        </svg>
      </span>
      <span class="qa-ranking-rank">${i + 1}</span>
      <span class="qa-ranking-text">${c.choice_text}</span>`;

    /* Drag events */
    item.addEventListener('dragstart', e => {
      dragSrc = item;
      item.classList.add('qa-ranking-item--dragging');
      e.dataTransfer.effectAllowed = 'move';
    });

    item.addEventListener('dragend', () => {
      item.classList.remove('qa-ranking-item--dragging');
      list.querySelectorAll('.qa-ranking-item').forEach(i => i.classList.remove('qa-ranking-item--over'));
      // Re-number ranks
      Array.from(list.children).forEach((el, idx) => {
        el.querySelector('.qa-ranking-rank').textContent = idx + 1;
      });
      updateRanking();
    });

    item.addEventListener('dragover', e => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (item !== dragSrc) item.classList.add('qa-ranking-item--over');
    });

    item.addEventListener('dragleave', () => item.classList.remove('qa-ranking-item--over'));

    item.addEventListener('drop', e => {
      e.preventDefault();
      if (!dragSrc || dragSrc === item) return;
      const allItems = Array.from(list.children);
      const srcIdx   = allItems.indexOf(dragSrc);
      const tgtIdx   = allItems.indexOf(item);
      if (srcIdx < tgtIdx) item.after(dragSrc);
      else                  item.before(dragSrc);
    });

    list.appendChild(item);
  });

  // Record initial order
  updateRanking();
  return list;
}

/* ─────────────────────────────────────────────────────────────
   RECORD ANSWER
───────────────────────────────────────────────────────────────*/
function recordAnswer (questionId, value) {
  const prev = answers[questionId];
  answers[questionId] = value;

  // Update card border state
  const card = document.getElementById(`qa-card-${questionId}`);
  if (card) {
    const q = questions.find(q => q.id === questionId);
    const answered = value !== null && value !== undefined &&
                     !(Array.isArray(value) && value.length === 0) &&
                     value !== '';
    card.classList.toggle('qa-question-card--answered', answered);
    card.classList.remove('qa-question-card--required-unanswered');
  }

  // Update overview dot
  updateOverviewDot(questionId);
}

/* ─────────────────────────────────────────────────────────────
   SHOW HINT after answering
───────────────────────────────────────────────────────────────*/
function showHint (questionId) {
  const hint = document.getElementById(`qa-hint-${questionId}`);
  if (hint) hint.classList.remove('hidden');
}

/* ─────────────────────────────────────────────────────────────
   OVERVIEW PANEL
───────────────────────────────────────────────────────────────*/
function renderOverview () {
  const listEl = document.getElementById('qaOverviewList');
  listEl.innerHTML = '';

  questions.forEach((q, i) => {
    const dot = document.createElement('div');
    dot.className   = `qa-overview__dot${q.is_required ? ' qa-overview__dot--required' : ''}`;
    dot.id          = `qa-dot-${q.id}`;
    dot.textContent = i + 1;
    dot.title       = q.question_text.slice(0, 60);
    dot.setAttribute('role', 'button');
    dot.setAttribute('tabindex', '0');
    dot.setAttribute('aria-label', `Jump to question ${i + 1}`);

    dot.addEventListener('click', () => jumpToQuestion(i));
    dot.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); jumpToQuestion(i); }
    });

    listEl.appendChild(dot);
  });
}

function updateOverviewDot (questionId) {
  const dot      = document.getElementById(`qa-dot-${questionId}`);
  const answered = isAnswered(questionId);
  if (dot) dot.classList.toggle('qa-overview__dot--answered', answered);
}

function isAnswered (questionId) {
  const v = answers[questionId];
  if (v === null || v === undefined || v === '') return false;
  if (Array.isArray(v) && v.length === 0) return false;
  return true;
}

function jumpToQuestion (index) {
  if (mode === 'step') {
    currentStep = index;
    renderStep();
  } else {
    const card = document.getElementById(`qa-card-${questions[index].id}`);
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

/* ─────────────────────────────────────────────────────────────
   MODE SWITCHING
───────────────────────────────────────────────────────────────*/
function setMode (newMode) {
  mode = newMode;

  const btnLong = document.getElementById('qaBtnLongForm');
  const btnStep = document.getElementById('qaBtnStepMode');
  const progress = document.getElementById('qaProgress');
  const stepNav  = document.getElementById('qaStepNav');
  const container = document.getElementById('qaQuestions');

  btnLong.classList.toggle('qa-mode-btn--active', newMode === 'longform');
  btnStep.classList.toggle('qa-mode-btn--active', newMode === 'step');
  btnLong.setAttribute('aria-pressed', newMode === 'longform');
  btnStep.setAttribute('aria-pressed', newMode === 'step');

  if (newMode === 'step') {
    container.classList.add('qa-questions--step');
    progress.classList.remove('hidden');
    stepNav.classList.remove('hidden');
    // Hide submit in main area, show only on last step
    syncStepSubmitVisibility();
    renderStep();
  } else {
    container.classList.remove('qa-questions--step');
    progress.classList.add('hidden');
    stepNav.classList.add('hidden');
    // Show submit always in longform
    document.getElementById('qaSubmitArea').classList.remove('hidden');
    // Clear current class from all cards
    document.querySelectorAll('.qa-question-card').forEach(c => c.classList.remove('qa-question-card--current'));
    updateOverviewAllDots();
  }
}

/* ─────────────────────────────────────────────────────────────
   STEP MODE RENDERING
───────────────────────────────────────────────────────────────*/
function renderStep () {
  document.querySelectorAll('.qa-question-card').forEach((c, i) => {
    c.classList.toggle('qa-question-card--current', i === currentStep);
  });

  // Update overview current dot
  document.querySelectorAll('.qa-overview__dot').forEach((d, i) => {
    d.classList.toggle('qa-overview__dot--current', i === currentStep);
  });

  // Progress bar
  const pct = questions.length > 1 ? (currentStep / (questions.length - 1)) * 100 : 100;
  document.getElementById('qaProgressFill').style.width = `${pct}%`;
  document.getElementById('qaProgressLabel').textContent =
    `Question ${currentStep + 1} of ${questions.length}`;
  document.getElementById('qaProgress').setAttribute('aria-valuenow', Math.round(pct));

  // Step counter
  document.getElementById('qaStepCounter').textContent =
    `${currentStep + 1} / ${questions.length}`;

  // Prev / Next buttons
  document.getElementById('qaBtnPrev').disabled = currentStep === 0;
  document.getElementById('qaBtnNext').textContent =
    currentStep === questions.length - 1 ? 'Finish' : 'Next';

  syncStepSubmitVisibility();
}

function navigateStep (delta) {
  const next = currentStep + delta;
  if (next < 0 || next > questions.length - 1) return;

  if (delta > 0 && next === questions.length) {
    // Reached end — scroll submit into view
    document.getElementById('qaSubmitArea').scrollIntoView({ behavior: 'smooth', block: 'center' });
    return;
  }

  currentStep = next;
  renderStep();
}

function syncStepSubmitVisibility () {
  const isLast = currentStep === questions.length - 1;
  document.getElementById('qaSubmitArea').classList.toggle('hidden', mode === 'step' && !isLast);
}

function updateOverviewAllDots () {
  questions.forEach(q => updateOverviewDot(q.id));
}

/* ─────────────────────────────────────────────────────────────
   TIMER
───────────────────────────────────────────────────────────────*/
function startTimer () {
  const display = document.getElementById('qaTimerDisplay');
  const timer   = document.getElementById('qaTimer');
  if (!display) return;

  timerHandle = setInterval(() => {
    secondsLeft--;

    const m = Math.floor(secondsLeft / 60);
    const s = secondsLeft % 60;
    display.textContent = `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;

    if (secondsLeft <= 60)  timer.classList.add('qa-timer--warning');
    if (secondsLeft <= 15)  { timer.classList.remove('qa-timer--warning'); timer.classList.add('qa-timer--danger'); }

    if (secondsLeft <= 0) {
      clearInterval(timerHandle);
      display.textContent = '00:00';
      handleSubmit(null, true); // auto-submit on timeout
    }
  }, 1000);
}

/* ─────────────────────────────────────────────────────────────
   VALIDATION
───────────────────────────────────────────────────────────────*/
function validate () {
  const unanswered = questions.filter(q => q.is_required && !isAnswered(q.id));

  if (unanswered.length) {
    // Mark cards
    unanswered.forEach(q => {
      const card = document.getElementById(`qa-card-${q.id}`);
      if (card) card.classList.add('qa-question-card--required-unanswered');
    });

    const msgEl  = document.getElementById('qaValidationMsg');
    const textEl = document.getElementById('qaValidationText');
    textEl.textContent = `${unanswered.length} required question${unanswered.length > 1 ? 's' : ''} unanswered. Please review before submitting.`;
    msgEl.classList.remove('hidden');
    msgEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return false;
  }

  document.getElementById('qaValidationMsg').classList.add('hidden');
  return true;
}

/* ─────────────────────────────────────────────────────────────
   BUILD PAYLOAD
───────────────────────────────────────────────────────────────*/
function buildPayload () {
  const answersArr = questions.map(q => ({
    question_id:  q.id,
    answer_value: answers[q.id] !== undefined ? answers[q.id] : null,
  }));

  return {
    questionnaire_id: window.QUESTIONNAIRE_ID,
    answers:          answersArr,
    send_email:       document.getElementById('qaSendEmail').checked,
  };
}

/* ─────────────────────────────────────────────────────────────
   SUBMIT
───────────────────────────────────────────────────────────────*/
async function handleSubmit (e, forced = false) {
  if (!forced && !validate()) return;

  if (timerHandle) clearInterval(timerHandle);

  const btn = document.getElementById('qaBtnSubmit');
  btn.classList.add('loading');
  btn.disabled = true;
  
  try {
    const res = await fetch(window.ATTEMPT_URL, {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken':  csrf(),
      },
      body: JSON.stringify(buildPayload()),
    });

    if (res.ok || res.status === 201 || res.status === 200) {
      const data = await res.json();
      openModal(data);
    } else {
      let data = {};
      try { data = await res.json(); } catch { /* non-JSON */ }
      showSubmitError(data.error || data.detail || `Server error (${res.status}). Please try again.`);
    }

  } catch (err) {
    showSubmitError('Network error. Check your connection and try again.');
    console.error('[Attempt] submit error:', err);

  } finally {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

function showSubmitError (msg) {
  const msgEl  = document.getElementById('qaValidationMsg');
  const textEl = document.getElementById('qaValidationText');
  textEl.textContent = msg;
  msgEl.classList.remove('hidden');
  msgEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

/* ─────────────────────────────────────────────────────────────
   MODAL — open with result data
   Expected: { score, max_score, percentage, passed, feedback, details, email_sent }
───────────────────────────────────────────────────────────────*/
function openModal (data) {
  const backdrop = document.getElementById('qaModalBackdrop');
  backdrop.classList.remove('hidden');
  backdrop.removeAttribute('aria-hidden');
  document.getElementById('qaModal').focus();

  // Percentage
  const pct = data.percentage != null ? Math.round(data.percentage) : 0;
  document.getElementById('qaModalPct').textContent   = `${pct}%`;

  // Score ring animation — circumference of r=40 circle = 2π×40 ≈ 251.2
  const ringFill = document.getElementById('qaRingFill');
  const offset   = 251.2 - (pct / 100) * 251.2;
  // Trigger reflow before animating
  requestAnimationFrame(() => {
    ringFill.style.strokeDashoffset = offset;
    ringFill.style.stroke = pct >= 50 ? 'var(--color-success)' : 'var(--color-error)';
  });

  // Grade / pass label
  const grade    = deriveGrade(pct);
  const passed   = data.passed != null ? data.passed : pct >= 50;
  document.getElementById('qaModalGrade').textContent = grade;

  // Score display
  const scoreStr = data.score != null
    ? `${data.score}${data.max_score ? ' / ' + data.max_score : ''}`
    : `${pct}%`;
  document.getElementById('qaModalScore').textContent = scoreStr;

  const statusEl = document.getElementById('qaModalStatus');
  statusEl.textContent = passed ? 'Passed' : 'Not passed';
  statusEl.className   = `qa-modal__score-val ${passed ? 'qa-modal__score-val--pass' : 'qa-modal__score-val--fail'}`;

  // Feedback
  const fbEl = document.getElementById('qaModalFeedback');
  if (data.feedback) {
    const items = Array.isArray(data.feedback) ? data.feedback : [data.feedback];
    fbEl.innerHTML = `<ul>${items.map(f => `<li>${f}</li>`).join('')}</ul>`;
  } else if (data.details) {
    fbEl.innerHTML = `<p>${data.details}</p>`;
  } else {
    fbEl.innerHTML = `<p>${passed ? 'Well done! Keep it up.' : 'Review the material and try again.'}</p>`;
  }

  // Email row
  const emailRow = document.getElementById('qaModalEmailRow');
  if (!data.email_sent) {
    emailRow.classList.remove('hidden');
  } else {
    emailRow.classList.add('hidden');
  }

  // Store result id for optional email resend
  if (data.attempt_id) {
    document.getElementById('qaModalSendEmail').dataset.attemptId = data.attempt_id;
  }
}

function closeModal () {
  const backdrop = document.getElementById('qaModalBackdrop');
  backdrop.classList.add('hidden');
  backdrop.setAttribute('aria-hidden', 'true');
}

/* Grade helper — returns KCSE-style letter or simple pass/fail label */
function deriveGrade (pct) {
  if (pct >= 80) return 'A';
  if (pct >= 70) return 'B';
  if (pct >= 60) return 'C';
  if (pct >= 50) return 'D';
  return 'E';
}

/* ─────────────────────────────────────────────────────────────
   OPTIONAL EMAIL RESEND from modal
───────────────────────────────────────────────────────────────*/
async function sendEmail () {
  const btn       = document.getElementById('qaModalSendEmail');
  const attemptId = btn.dataset.attemptId;
  if (!attemptId) return;

  btn.disabled    = true;
  btn.textContent = 'Sending…';

  try {
    const res = await fetch(window.ATTEMPT_URL, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify({ resend_email: true, attempt_id: attemptId }),
    });

    if (res.ok) {
      btn.textContent = 'Email sent!';
      document.getElementById('qaModalEmailRow').classList.add('hidden');
    } else {
      btn.disabled    = false;
      btn.textContent = 'Try again';
    }
  } catch {
    btn.disabled    = false;
    btn.textContent = 'Failed — retry';
  }
}

/* ─────────────────────────────────────────────────────────────
   BOOT
───────────────────────────────────────────────────────────────*/
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}