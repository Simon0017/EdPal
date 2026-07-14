/**
 * careers/psychometric_assessment.js
 *
 * Handles the full psychometric assessment experience:
 *   - Paged (one question at a time) and scroll (all questions) modes
 *   - Progress bar updates
 *   - Choice selection (single, multi-select, numeric, text)
 *   - Answer persistence / autosave hooks
 *   - Validation before advance
 *   - Submission and success screen
 *   - Keyboard accessibility
 *   - Save & Exit
 *
 * Expects: window.CA_ASSESSMENT set by the template.
 *   { testSlug, testName, responseId, totalQuestions,
 *     displayMode, submitUrl, autosaveUrl, previousAnswers }
 */

'use strict';

const $ = id => document.getElementById(id);

/* ── CSRF ── */
function csrfToken() {
  return (
    document.querySelector('#caAssessmentCsrf input[name="csrfmiddlewaretoken"]')?.value || ''
  );
}

async function apiFetch(url, body) {
  const res = await fetch(url, {
    method:  'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken':  csrfToken(),
      'X-Requested-With': 'XMLHttpRequest',
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return res.json().catch(() => ({}));
}

/* ── Toast (reuses CaToast if assessment_modal.js is loaded, else standalone) ── */
function showToast(message, type = 'success') {
  if (window.CaToast) { window.CaToast.show(message, type); return; }
  const stack = $('caToastStack');
  if (!stack) return;
  const el = document.createElement('div');
  el.className = `ca-toast ca-toast--${type}`;
  el.setAttribute('role', type === 'error' ? 'alert' : 'status');
  el.innerHTML = `<span class="ca-toast__text">${message}</span>`;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

/* ─────────────────────────────────────────────
   STATE
───────────────────────────────────────────── */
const state = {
  currentIndex: 0,
  answers: {},          // { questionId: value | [values] }
  totalQuestions: 0,
  displayMode: 'paged',
  submitting: false,
};

/* ─────────────────────────────────────────────
   INITIALISE FROM WINDOW.CA_ASSESSMENT
───────────────────────────────────────────── */
function hydrate() {
  const cfg = window.CA_ASSESSMENT || {};
  state.totalQuestions = cfg.totalQuestions || 0;
  state.displayMode    = cfg.displayMode    || 'paged';

  // Pre-populate answers from a resumed session
  if (cfg.previousAnswers && typeof cfg.previousAnswers === 'object') {
    state.answers = Object.assign({}, cfg.previousAnswers);
  }
}

/* ─────────────────────────────────────────────
   PROGRESS BAR
───────────────────────────────────────────── */
function updateProgress(index) {
  const pct   = state.totalQuestions > 0
    ? Math.round(((index + 1) / state.totalQuestions) * 100)
    : 0;

  const fill  = $('caProgressFill');
  const label = $('caProgressPct');
  const navLbl = $('caNavLabel');
  const remaining = $('caRemainingCount');

  if (fill)      fill.style.width = pct + '%';
  if (label)     label.textContent = pct + '% complete';
  if (navLbl)    navLbl.textContent = `${index + 1} / ${state.totalQuestions}`;
  if (remaining) remaining.textContent = state.totalQuestions - index - 1;
}

/* ─────────────────────────────────────────────
   PAGED MODE — show/hide question wrappers
───────────────────────────────────────────── */
function showQuestion(index) {
  const wrappers = document.querySelectorAll('[data-q-index]');

  wrappers.forEach(w => {
    const i = parseInt(w.dataset.qIndex, 10);
    if (i === index) {
      w.hidden = false;
      // Smooth entrance
      const card = w.querySelector('.ca-question-card');
      if (card) {
        card.style.animation = 'none';
        requestAnimationFrame(() => {
          card.style.animation = 'cr-fade-up 0.3s ease';
        });
      }
    } else {
      w.hidden = true;
    }
  });

  state.currentIndex = index;
  updateProgress(index);
  updateNavButtons(index);
}

function updateNavButtons(index) {
  const prevBtn   = $('caPrevBtn');
  const nextBtn   = $('caNextBtn');
  const submitBtn = $('caSubmitBtn');
  const isLast    = index >= state.totalQuestions - 1;

  if (prevBtn) prevBtn.disabled = index === 0;

  if (nextBtn && submitBtn) {
    if (isLast) {
      nextBtn.classList.add('hidden');
      submitBtn.classList.remove('hidden');
    } else {
      nextBtn.classList.remove('hidden');
      submitBtn.classList.add('hidden');
    }
  }
}

/* ─────────────────────────────────────────────
   SCROLL MODE — reveal all questions
───────────────────────────────────────────── */
function initScrollMode() {
  document.querySelectorAll('[data-q-index]').forEach(w => { w.hidden = false; });

  // Replace nav bar with a single submit button
  const navBar = $('caNavBar');
  if (navBar) {
    navBar.innerHTML = `
      <button class="btn-primary" id="caSubmitBtn" type="button"
              style="font-size:0.9rem;padding:12px 32px;"
              aria-label="Submit assessment">
        Submit Assessment
      </button>`;
    // Re-wire submit
    $('caSubmitBtn')?.addEventListener('click', handleSubmit);
  }

  // Scroll-based progress update
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const idx = parseInt(entry.target.dataset.qIndex, 10);
        if (!isNaN(idx)) updateProgress(idx);
      }
    });
  }, { threshold: 0.5 });

  document.querySelectorAll('[data-q-index]').forEach(w => observer.observe(w));
}

/* ─────────────────────────────────────────────
   CHOICE SELECTION
───────────────────────────────────────────── */
function initChoices() {
  document.addEventListener('click', e => {
    const choice = e.target.closest('.ca-choice');
    if (!choice) return;

    const card       = choice.closest('.ca-question-card');
    const questionId = card?.dataset.questionId;
    const type       = card?.dataset.questionType;
    if (!questionId) return;

    if (type === 'MULTI_SELECT') {
      // Toggle individual selection
      const wasSelected = choice.classList.contains('ca-choice--selected');
      choice.classList.toggle('ca-choice--selected', !wasSelected);
      choice.setAttribute('aria-checked', String(!wasSelected));

      const selected = Array.from(card.querySelectorAll('.ca-choice--selected'))
        .map(c => c.dataset.choiceValue);
      state.answers[questionId] = selected;

    } else {
      // Single selection — deselect siblings
      card.querySelectorAll('.ca-choice').forEach(c => {
        c.classList.remove('ca-choice--selected');
        c.setAttribute('aria-checked', 'false');
      });
      choice.classList.add('ca-choice--selected');
      choice.setAttribute('aria-checked', 'true');
      state.answers[questionId] = choice.dataset.choiceValue;
    }

    // Clear any validation error on this question
    $(`ca-error-${questionId}`)?.classList.add('hidden');

    scheduleAutosave();
  });

  // Text / numeric inputs
  document.addEventListener('input', e => {
    const input = e.target;
    if (!input.name?.startsWith('answer_')) return;
    const questionId = input.name.replace('answer_', '');
    state.answers[questionId] = input.value;
    scheduleAutosave();
  });
}

/* ─────────────────────────────────────────────
   PRE-POPULATE ANSWERS (resume support)
───────────────────────────────────────────── */
function populatePreviousAnswers() {
  Object.entries(state.answers).forEach(([questionId, value]) => {
    const card = document.querySelector(`.ca-question-card[data-question-id="${questionId}"]`);
    if (!card) return;
    const type = card.dataset.questionType;

    if (type === 'MULTI_SELECT' && Array.isArray(value)) {
      value.forEach(v => {
        const choice = card.querySelector(`.ca-choice[data-choice-value="${v}"]`);
        choice?.classList.add('ca-choice--selected');
        choice?.setAttribute('aria-checked', 'true');
      });
    } else if (type === 'SINGLE_CHOICE' || type === 'MULTIPLE_CHOICE') {
      const choice = card.querySelector(`.ca-choice[data-choice-value="${value}"]`);
      choice?.classList.add('ca-choice--selected');
      choice?.setAttribute('aria-checked', 'true');
    } else {
      const input = card.querySelector(`[name="answer_${questionId}"]`);
      if (input) input.value = value;
    }
  });
}

/* ─────────────────────────────────────────────
   VALIDATION
───────────────────────────────────────────── */
function validateQuestion(index) {
  const wrapper    = document.querySelector(`[data-q-index="${index}"]`);
  const card       = wrapper?.querySelector('.ca-question-card');
  if (!card) return true;

  const questionId = card.dataset.questionId;
  const required   = card.dataset.required === 'true';
  const type       = card.dataset.questionType;
  const errorEl    = $(`ca-error-${questionId}`);

  if (!required) return true;

  let answered = false;

  if (['SINGLE_CHOICE', 'MULTIPLE_CHOICE'].includes(type)) {
    answered = !!card.querySelector('.ca-choice--selected');
  } else if (type === 'MULTI_SELECT') {
    answered = card.querySelectorAll('.ca-choice--selected').length > 0;
  } else {
    const input = card.querySelector(`[name="answer_${questionId}"]`);
    answered    = !!input?.value?.trim();
  }

  if (!answered && errorEl) {
    errorEl.textContent = 'This question requires a response before continuing.';
    errorEl.classList.remove('hidden');
    errorEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  return answered;
}

function validateAll() {
  let allValid = true;
  const total  = state.totalQuestions;

  for (let i = 0; i < total; i++) {
    if (!validateQuestion(i)) allValid = false;
  }

  return allValid;
}

/* ─────────────────────────────────────────────
   AUTOSAVE
   Fires 2 seconds after the last answer change.
   Implement the autosaveUrl endpoint to accept:
     POST { response_id, answers: { questionId: value } }
───────────────────────────────────────────── */
let autosaveTimer = null;

function scheduleAutosave() {
  // AUTOSAVE HOOK — fires 2s after last input change
  clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(doAutosave, 2000);
}

async function doAutosave() {
  const cfg = window.CA_ASSESSMENT || {};
  if (!cfg.autosaveUrl || !cfg.responseId) return;

  try {
    await apiFetch(cfg.autosaveUrl, {
      response_id: cfg.responseId,
      answers: state.answers,
    });
    // Silently succeeds — no toast needed for autosave
  } catch (_) {
    // Autosave failure is non-critical; do not distract the user
  }
}

/* ─────────────────────────────────────────────
   SUBMISSION
───────────────────────────────────────────── */
async function handleSubmit() {
  if (state.submitting) return;

  // Validate all questions before submitting
  if (!validateAll()) {
    if (state.displayMode === 'paged') {
      // In paged mode, jump to first unanswered question
      for (let i = 0; i < state.totalQuestions; i++) {
        if (!validateQuestion(i)) { showQuestion(i); break; }
      }
    }
    showToast('Please answer all required questions before submitting.', 'error');
    return;
  }

  state.submitting = true;

  const submitBtn = $('caSubmitBtn');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting…';
  }

  const cfg = window.CA_ASSESSMENT || {};

  try {
    await apiFetch(cfg.submitUrl, {
      response_id: cfg.responseId,
      answers: state.answers,
    });
    showSuccessScreen();
  } catch (err) {
    showToast(err.message || 'Submission failed. Please try again.', 'error');
    state.submitting = false;
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Submit Assessment';
    }
  }
}

function showSuccessScreen() {
  const page       = $('caAssessmentPage');
  const successEl  = $('caSuccessScreen');
  const questionsWrap = $('caQuestionsWrap');
  const progressWrap  = $('caProgressWrap');
  const headerEl      = document.querySelector('.ca-assessment-header');

  // Fade out current content
  [questionsWrap, progressWrap, headerEl].forEach(el => {
    if (el) el.style.display = 'none';
  });

  // Show success
  successEl?.classList.remove('hidden');
  successEl?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Focus management for accessibility
  requestAnimationFrame(() => {
    const firstAction = successEl?.querySelector('a, button');
    firstAction?.focus();
  });
}

/* ─────────────────────────────────────────────
   INSTRUCTIONS CARD → START
───────────────────────────────────────────── */
function initInstructionsCard() {
  const startBtn      = $('caStartBtn');
  const instructionsCard = $('caInstructionsCard');
  const questionsWrap = $('caQuestionsWrap');

  if (!startBtn || !instructionsCard || !questionsWrap) return;

  startBtn.addEventListener('click', () => {
    instructionsCard.style.opacity = '0';
    instructionsCard.style.transition = 'opacity 0.25s ease';
    setTimeout(() => {
      instructionsCard.style.display = 'none';
      questionsWrap.style.display = '';
      if (state.displayMode === 'paged') showQuestion(0);
    }, 250);
  });
}

/* ─────────────────────────────────────────────
   NAVIGATION (paged mode)
───────────────────────────────────────────── */
function initNavigation() {
  $('caPrevBtn')?.addEventListener('click', () => {
    if (state.currentIndex > 0) showQuestion(state.currentIndex - 1);
  });

  $('caNextBtn')?.addEventListener('click', () => {
    if (!validateQuestion(state.currentIndex)) return;
    if (state.currentIndex < state.totalQuestions - 1) {
      showQuestion(state.currentIndex + 1);
    }
  });

  $('caSubmitBtn')?.addEventListener('click', handleSubmit);

  // Keyboard: left/right arrow when not inside an input
  document.addEventListener('keydown', e => {
    if (state.displayMode !== 'paged') return;
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;
    if (e.key === 'ArrowRight') $('caNextBtn')?.click();
    if (e.key === 'ArrowLeft')  $('caPrevBtn')?.click();
  });
}

/* ─────────────────────────────────────────────
   SAVE & EXIT
───────────────────────────────────────────── */
function initSaveExit() {
  $('caSaveExitBtn')?.addEventListener('click', async () => {
    await doAutosave();
    window.location.href = window.CA_URLS?.careersDashboard || '/careers/';
  });
}

/* ─────────────────────────────────────────────
   BOOT
───────────────────────────────────────────── */
function init() {
  hydrate();
  initChoices();
  initNavigation();
  initInstructionsCard();
  initSaveExit();
  populatePreviousAnswers();

  if (state.displayMode === 'scroll') {
    initScrollMode();
  } else {
    // Paged mode — show first question (skip if instructions card is showing)
    const hasInstructions = !!$('caInstructionsCard');
    if (!hasInstructions) showQuestion(0);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
