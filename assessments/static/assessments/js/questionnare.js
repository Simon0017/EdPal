/**
 * assessments/static/assessments/js/questionnare.js
 *
 * BACKEND PARSING (plain repeated keys, no formset prefixes):
 *   texts      = request.POST.getlist('question_text')
 *   weights    = request.POST.getlist('weight')
 *   q_types    = request.POST.getlist('question_type')
 *   ...iterate by index to assemble each question object.
 *
 *   choices linked to questions via:
 *   choice_question_index = request.POST.getlist('choice_question_index')
 *   → choice_question_index[i] is the 0-based index into question_text list.
 *
 *   Tags: request.POST.getlist('tag'), getlist('coupling_strength'), getlist('is_primary')
 *
 *   Optional JSON alternative: collect all data client-side and POST as
 *   application/json — mention to backend dev if they prefer that approach.
 */

'use strict';

/* ─────────────────────────────────────────────────────────────
   STATE
───────────────────────────────────────────────────────────────*/
const TOTAL_STEPS = 5;
let currentStep   = 1;

/* Question types that have choices */
const CHOICE_TYPES = new Set(['MCQ', 'MULTI_SELECT', 'LIKERT', 'RANKING']);

/* ─────────────────────────────────────────────────────────────
   STEPPER
───────────────────────────────────────────────────────────────*/
function updateStepper (step) {
  document.querySelectorAll('.qn-stepper__item').forEach(item => {
    const n = parseInt(item.dataset.step, 10);
    item.classList.remove('qn-stepper__item--active', 'qn-stepper__item--done');
    item.removeAttribute('aria-current');

    const dot = item.querySelector('.qn-stepper__dot');
    if (n === step) {
      item.classList.add('qn-stepper__item--active');
      item.setAttribute('aria-current', 'step');
    } else if (n < step) {
      item.classList.add('qn-stepper__item--done');
      dot.textContent = '✓';
    } else {
      dot.textContent = n;
    }
  });

  const fill = document.getElementById('qnStepperFill');
  fill.style.width = `${(step / TOTAL_STEPS) * 100}%`;
  fill.parentElement.setAttribute('aria-valuenow', step);
}

/* ─────────────────────────────────────────────────────────────
   STEP TRANSITIONS
───────────────────────────────────────────────────────────────*/
function goToStep (target) {
  if (target < 1 || target > TOTAL_STEPS) return;

  document.querySelectorAll('.qn-step').forEach(fs => fs.classList.add('hidden'));
  document.getElementById(`qnStep${target}`).classList.remove('hidden');

  const btnBack   = document.getElementById('qnBtnBack');
  const btnNext   = document.getElementById('qnBtnNext');
  const btnSubmit = document.getElementById('qnBtnSubmit');

  btnBack.disabled = target === 1;

  if (target === TOTAL_STEPS) {
    btnNext.classList.add('hidden');
    btnSubmit.classList.remove('hidden');
    buildReview();
  } else {
    btnNext.classList.remove('hidden');
    btnSubmit.classList.add('hidden');
  }

  currentStep = target;
  updateStepper(target);
  document.querySelector('.qn-wrap').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ─────────────────────────────────────────────────────────────
   STATUS BANNER
───────────────────────────────────────────────────────────────*/
function showStatus (msg, type = 'error') {
  const el   = document.getElementById('qnStatus');
  const icon = type === 'success' ? '✓' : '⚠';
  el.className = `qn-status qn-status--${type}`;
  el.innerHTML = `<span aria-hidden="true">${icon}</span><span>${msg}</span>`;
  el.classList.remove('hidden');
  el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function hideStatus () {
  document.getElementById('qnStatus').classList.add('hidden');
}

/* ─────────────────────────────────────────────────────────────
   REMAINING POINTS WIDGET
───────────────────────────────────────────────────────────────*/
function updatePointsWidget () {
  const maxScore = parseFloat(document.getElementById('id_max_score').value) || 0;
  const widget   = document.getElementById('qnPointsWidget');
  const valEl    = document.getElementById('qnPointsRemaining');
  const maxEl    = document.getElementById('qnPointsMax');

  if (!maxScore) {
    valEl.textContent = '—';
    maxEl.textContent = '';
    return;
  }

  /* Sum all weight inputs */
  const used = Array.from(document.querySelectorAll('input[name="weight"]'))
    .reduce((sum, el) => sum + (parseFloat(el.value) || 0), 0);

  const remaining = maxScore - used;
  valEl.textContent = remaining.toFixed(1);
  maxEl.textContent = `/ ${maxScore}`;

  widget.classList.remove('qn-points-widget--warn', 'qn-points-widget--over');
  if (remaining < 0)              widget.classList.add('qn-points-widget--over');
  else if (remaining < maxScore * 0.1) widget.classList.add('qn-points-widget--warn');
}

/* ─────────────────────────────────────────────────────────────
   HELPERS — small DOM builders
───────────────────────────────────────────────────────────────*/
function makeInput ({ type = 'text', name, id, placeholder = '', classes = 'form-input', required = false, min, max, step, value = '' }) {
  const el = document.createElement('input');
  el.type  = type;
  el.name  = name;
  if (id)          el.id          = id;
  if (placeholder) el.placeholder = placeholder;
  el.className     = classes;
  el.required      = required;
  if (min !== undefined) el.min = min;
  if (max !== undefined) el.max = max;
  if (step)              el.step = step;
  if (value)             el.value = value;
  return el;
}

function makeSelect ({ name, options, classes = 'form-input', ariaLabel = '' }) {
  const sel = document.createElement('select');
  sel.name  = name;
  sel.className = classes;
  if (ariaLabel) sel.setAttribute('aria-label', ariaLabel);
  options.forEach(({ value, label }) => {
    const o = document.createElement('option');
    o.value       = value;
    o.textContent = label;
    sel.appendChild(o);
  });
  return sel;
}

function makeLabel (text, forId) {
  const lbl = document.createElement('label');
  lbl.className = 'form-label';
  lbl.textContent = text;
  if (forId) lbl.htmlFor = forId;
  return lbl;
}

function makeFormGroup (...children) {
  const g = document.createElement('div');
  g.className = 'form-group';
  children.forEach(c => g.appendChild(c));
  return g;
}

function makeRemoveBtn (label) {
  const btn = document.createElement('button');
  btn.type      = 'button';
  btn.className = 'qn-entry__remove';
  btn.textContent = '✕';
  btn.setAttribute('aria-label', label);
  return btn;
}

/* ─────────────────────────────────────────────────────────────
   STEP 2 — TAG ENTRIES
───────────────────────────────────────────────────────────────*/
function buildTagEntry (index) {
  const entry = document.createElement('div');
  entry.className  = 'qn-entry';
  entry.dataset.index = index;

  const header = document.createElement('div');
  header.className = 'qn-entry__header';
  const title = document.createElement('span');
  title.className   = 'qn-entry__title';
  title.textContent = `Tag ${index + 1}`;
  const removeBtn = makeRemoveBtn(`Remove tag ${index + 1}`);
  removeBtn.addEventListener('click', () => {
    entry.remove();
    renumberEntries('tagList', 'Tag');
  });
  header.appendChild(title);
  header.appendChild(removeBtn);

  const grid = document.createElement('div');
  grid.className = 'qn-entry__grid';

  /* tag (text) */
  const tagInput = makeInput({ name: 'tag', placeholder: 'e.g. mathematics', required: true });
  tagInput.id = `tag_${index}_tag`;
  grid.appendChild(makeFormGroup(makeLabel('Tag *', tagInput.id), tagInput));

  /* coupling_strength */
  const csInput = makeInput({ type: 'number', name: 'coupling_strength', placeholder: '0.0 – 1.0', min: '0', max: '1', step: '0.01' });
  csInput.id = `tag_${index}_cs`;
  grid.appendChild(makeFormGroup(makeLabel('Coupling strength', csInput.id), csInput));

  /* is_primary checkbox */
  const primaryWrap = document.createElement('div');
  primaryWrap.className = 'form-group qn-toggle-group';
  const primaryChk = document.createElement('input');
  primaryChk.type  = 'checkbox';
  primaryChk.name  = 'is_primary';
  primaryChk.value = 'on';
  primaryChk.id    = `tag_${index}_primary`;
  primaryChk.className = 'toggle-checkbox';
  primaryWrap.appendChild(makeLabel('Primary?', primaryChk.id));
  primaryWrap.appendChild(primaryChk);
  grid.appendChild(primaryWrap);

  entry.appendChild(header);
  entry.appendChild(grid);
  return entry;
}

function renumberEntries (listId, prefix) {
  document.querySelectorAll(`#${listId} .qn-entry__title`).forEach((el, i) => {
    el.textContent = `${prefix} ${i + 1}`;
  });
  document.querySelectorAll(`#${listId} .qn-entry`).forEach((el, i) => {
    el.dataset.index = i;
  });
}

/* ─────────────────────────────────────────────────────────────
   STEP 3 — QUESTION ENTRIES
   Plain names — backend uses getlist('question_text') etc.
───────────────────────────────────────────────────────────────*/
const QUESTION_TYPES = [
  { value: 'MCQ',          label: 'Multiple Choice (MCQ)' },
  { value: 'MULTI_SELECT', label: 'Multi-Select' },
  { value: 'NUMERIC',      label: 'Numeric' },
  { value: 'TEXT',         label: 'Free Text' },
  { value: 'LIKERT',       label: 'Likert Scale' },
  { value: 'RANKING',      label: 'Ranking' },
];

function buildQuestionEntry (index) {
  const entry = document.createElement('div');
  entry.className  = 'qn-entry';
  entry.dataset.index = index;

  const header = document.createElement('div');
  header.className = 'qn-entry__header';
  const title = document.createElement('span');
  title.className   = 'qn-entry__title';
  title.textContent = `Question ${index + 1}`;
  const removeBtn = makeRemoveBtn(`Remove question ${index + 1}`);
  removeBtn.addEventListener('click', () => {
    entry.remove();
    renumberEntries('questionList', 'Question');
    updatePointsWidget();
  });
  header.appendChild(title);
  header.appendChild(removeBtn);

  const grid = document.createElement('div');
  grid.className = 'qn-entry__grid';

  /* question_text */
  const qtArea = document.createElement('textarea');
  qtArea.name        = 'question_text';
  qtArea.className   = 'form-input form-textarea';
  qtArea.rows        = 2;
  qtArea.placeholder = 'Question text…';
  qtArea.required    = true;
  qtArea.id          = `q_${index}_text`;
  const qtWrap = document.createElement('div');
  qtWrap.className = 'form-group qn-entry__col-full';
  qtWrap.appendChild(makeLabel('Question text *', qtArea.id));
  qtWrap.appendChild(qtArea);
  grid.appendChild(qtWrap);

  /* question_type */
  const typeSelect = makeSelect({ name: 'question_type', options: QUESTION_TYPES, ariaLabel: 'Question type' });
  typeSelect.id = `q_${index}_type`;
  grid.appendChild(makeFormGroup(makeLabel('Type', typeSelect.id), typeSelect));

  /* weight */
  const weightInput = makeInput({ type: 'number', name: 'weight', placeholder: '1', min: '0.01', step: '0.01' });
  weightInput.id = `q_${index}_weight`;
  weightInput.addEventListener('input', updatePointsWidget);
  grid.appendChild(makeFormGroup(makeLabel('Weight', weightInput.id), weightInput));

  /* max_points */
  const mpInput = makeInput({ type: 'number', name: 'max_points', placeholder: '10', min: '0.01', step: '0.01' });
  mpInput.id = `q_${index}_mp`;
  grid.appendChild(makeFormGroup(makeLabel('Max points', mpInput.id), mpInput));

  /* order */
  const orderInput = makeInput({ type: 'number', name: 'order', value: String(index + 1), min: '1', step: '1' });
  orderInput.id = `q_${index}_order`;
  grid.appendChild(makeFormGroup(makeLabel('Order', orderInput.id), orderInput));

  /* randomisation_group */
  const rgInput = makeInput({ name: 'randomisation_group', placeholder: 'group-a' });
  rgInput.id = `q_${index}_rg`;
  grid.appendChild(makeFormGroup(makeLabel('Randomisation group', rgInput.id), rgInput));

  /* is_required checkbox */
  const reqWrap = document.createElement('div');
  reqWrap.className = 'form-group qn-toggle-group';
  const reqChk = document.createElement('input');
  reqChk.type      = 'checkbox';
  reqChk.name      = 'is_required';
  reqChk.value     = 'on';
  reqChk.id        = `q_${index}_req`;
  reqChk.className = 'toggle-checkbox';
  reqChk.checked   = true;
  reqWrap.appendChild(makeLabel('Required?', reqChk.id));
  reqWrap.appendChild(reqChk);
  grid.appendChild(reqWrap);

  /* explanation */
  const exArea = document.createElement('textarea');
  exArea.name      = 'explanation';
  exArea.className = 'form-input form-textarea';
  exArea.rows      = 2;
  exArea.placeholder = 'Explanation shown after answer (optional)';
  exArea.id        = `q_${index}_ex`;
  const exWrap = document.createElement('div');
  exWrap.className = 'form-group qn-entry__col-full';
  exWrap.appendChild(makeLabel('Explanation', exArea.id));
  exWrap.appendChild(exArea);
  grid.appendChild(exWrap);

  /* numeric_config_raw — shown conditionally */
  const ncArea = document.createElement('textarea');
  ncArea.name      = 'numeric_config_raw';
  ncArea.className = 'form-input form-textarea qn-json-editor';
  ncArea.rows      = 3;
  ncArea.placeholder = '{"min": 0, "max": 100, "step": 1}';
  ncArea.id        = `q_${index}_nc`;
  const ncWrap = document.createElement('div');
  ncWrap.className = 'form-group qn-entry__col-full';
  ncWrap.style.display = 'none'; // hidden until type = NUMERIC
  ncWrap.appendChild(makeLabel('Numeric config (JSON)', ncArea.id));
  ncWrap.appendChild(ncArea);
  grid.appendChild(ncWrap);

  /* Show/hide numeric_config_raw based on type selection */
  typeSelect.addEventListener('change', () => {
    ncWrap.style.display = typeSelect.value === 'NUMERIC' ? '' : 'none';
    if (typeSelect.value !== 'NUMERIC') ncArea.value = '';
  });

  /* question_index (hidden — tells backend which question index this entry maps to) */
  const qiHidden = document.createElement('input');
  qiHidden.type  = 'hidden';
  qiHidden.name  = 'question_index';
  qiHidden.value = String(index);
  grid.appendChild(qiHidden);

  entry.appendChild(header);
  entry.appendChild(grid);
  return entry;
}

/* ─────────────────────────────────────────────────────────────
   STEP 4 — CHOICE ENTRIES
   choice_question_index associates each choice with a question.
───────────────────────────────────────────────────────────────*/
function getQuestionOptions () {
  const questions = document.querySelectorAll('#questionList .qn-entry');
  const opts = [{ value: '', label: '— select question —' }];
  questions.forEach((q, i) => {
    const textEl = q.querySelector('textarea[name="question_text"]');
    const label  = textEl ? (textEl.value.trim().slice(0, 40) || `Question ${i + 1}`) : `Question ${i + 1}`;
    opts.push({ value: String(i), label: `Q${i + 1}: ${label}` });
  });
  return opts;
}

function buildChoiceEntry (index) {
  const entry = document.createElement('div');
  entry.className  = 'qn-entry';
  entry.dataset.index = index;

  const header = document.createElement('div');
  header.className = 'qn-entry__header';
  const title = document.createElement('span');
  title.className   = 'qn-entry__title';
  title.textContent = `Choice ${index + 1}`;
  const removeBtn = makeRemoveBtn(`Remove choice ${index + 1}`);
  removeBtn.addEventListener('click', () => {
    entry.remove();
    renumberEntries('choiceList', 'Choice');
  });
  header.appendChild(title);
  header.appendChild(removeBtn);

  const grid = document.createElement('div');
  grid.className = 'qn-entry__grid';

  /* choice_question_index — links to a question by 0-based index */
  const qiSelect = makeSelect({ name: 'choice_question_index', options: getQuestionOptions(), ariaLabel: 'Associated question' });
  qiSelect.id = `c_${index}_qi`;
  grid.appendChild(makeFormGroup(makeLabel('For question', qiSelect.id), qiSelect));

  /* choice_key */
  const keyInput = makeInput({ name: 'choice_key', placeholder: 'A', required: true });
  keyInput.id = `c_${index}_key`;
  grid.appendChild(makeFormGroup(makeLabel('Key *', keyInput.id), keyInput));

  /* choice_text */
  const ctArea = document.createElement('textarea');
  ctArea.name      = 'choice_text';
  ctArea.className = 'form-input form-textarea';
  ctArea.rows      = 2;
  ctArea.placeholder = 'Choice text…';
  ctArea.required  = true;
  ctArea.id        = `c_${index}_text`;
  const ctWrap = document.createElement('div');
  ctWrap.className = 'form-group qn-entry__col-full';
  ctWrap.appendChild(makeLabel('Choice text *', ctArea.id));
  ctWrap.appendChild(ctArea);
  grid.appendChild(ctWrap);

  /* is_correct */
  const correctWrap = document.createElement('div');
  correctWrap.className = 'form-group qn-toggle-group';
  const correctChk = document.createElement('input');
  correctChk.type      = 'checkbox';
  correctChk.name      = 'is_correct';
  correctChk.value     = 'on';
  correctChk.id        = `c_${index}_correct`;
  correctChk.className = 'toggle-checkbox';
  correctWrap.appendChild(makeLabel('Correct?', correctChk.id));
  correctWrap.appendChild(correctChk);
  grid.appendChild(correctWrap);

  /* partial_score */
  const psInput = makeInput({ type: 'number', name: 'partial_score', placeholder: '0.0 – 1.0', min: '0', max: '1', step: '0.01' });
  psInput.id = `c_${index}_ps`;
  grid.appendChild(makeFormGroup(makeLabel('Partial score', psInput.id), psInput));

  /* order */
  const orderInput = makeInput({ type: 'number', name: 'choice_order', value: String(index + 1), min: '1', step: '1' });
  orderInput.id = `c_${index}_order`;
  grid.appendChild(makeFormGroup(makeLabel('Order', orderInput.id), orderInput));

  /* explanation */
  const exArea = document.createElement('textarea');
  exArea.name      = 'choice_explanation';
  exArea.className = 'form-input form-textarea';
  exArea.rows      = 2;
  exArea.placeholder = 'Explanation for this choice (optional)';
  exArea.id        = `c_${index}_ex`;
  const exWrap = document.createElement('div');
  exWrap.className = 'form-group qn-entry__col-full';
  exWrap.appendChild(makeLabel('Explanation', exArea.id));
  exWrap.appendChild(exArea);
  grid.appendChild(exWrap);

  entry.appendChild(header);
  entry.appendChild(grid);
  return entry;
}

/* ─────────────────────────────────────────────────────────────
   STEP 5 — REVIEW BUILDER
───────────────────────────────────────────────────────────────*/
function row (key, val) {
  const r = document.createElement('div');
  r.className = 'qn-review__row';
  r.innerHTML = `<span class="qn-review__key">${key}</span><span class="qn-review__val">${val || '—'}</span>`;
  return r;
}

function section (title, rows) {
  const s = document.createElement('div');
  s.className = 'qn-review__section';
  const t = document.createElement('div');
  t.className   = 'qn-review__section-title';
  t.textContent = title;
  s.appendChild(t);
  rows.forEach(r => s.appendChild(r));
  return s;
}

function buildReview () {
  const container = document.getElementById('qnReviewContent');
  container.innerHTML = '';

  /* Meta */
  container.appendChild(section('Questionnaire', [
    row('Title',        document.getElementById('id_title').value),
    row('Status',       document.getElementById('id_status').value),
    row('Max score',    document.getElementById('id_max_score').value),
    row('Time limit',   document.getElementById('id_time_limit_minutes').value + ' min'),
    row('Randomised',   document.getElementById('id_is_randomised').checked ? 'Yes' : 'No'),
  ]));

  /* Tags */
  const tags = Array.from(document.querySelectorAll('#tagList .qn-entry'));
  if (tags.length) {
    container.appendChild(section(`Tags (${tags.length})`,
      tags.map((t, i) => {
        const tag  = t.querySelector('input[name="tag"]').value;
        const cs   = t.querySelector('input[name="coupling_strength"]').value;
        const prim = t.querySelector('input[name="is_primary"]').checked;
        return row(`Tag ${i + 1}`, `${tag} | strength: ${cs || '—'} | primary: ${prim ? 'Yes' : 'No'}`);
      })
    ));
  }

  /* Questions */
  const questions = Array.from(document.querySelectorAll('#questionList .qn-entry'));
  if (questions.length) {
    container.appendChild(section(`Questions (${questions.length})`,
      questions.map((q, i) => {
        const text   = q.querySelector('textarea[name="question_text"]').value.slice(0, 60);
        const type   = q.querySelector('select[name="question_type"]').value;
        const weight = q.querySelector('input[name="weight"]').value;
        return row(`Q${i + 1} (${type})`, `${text}… | weight: ${weight}`);
      })
    ));
  }

  /* Choices */
  const choices = Array.from(document.querySelectorAll('#choiceList .qn-entry'));
  if (choices.length) {
    container.appendChild(section(`Choices (${choices.length})`,
      choices.map((c, i) => {
        const key  = c.querySelector('input[name="choice_key"]').value;
        const text = c.querySelector('textarea[name="choice_text"]').value.slice(0, 50);
        const qi   = c.querySelector('select[name="choice_question_index"]').value;
        const ok   = c.querySelector('input[name="is_correct"]').checked;
        return row(`Choice ${i + 1} → Q${parseInt(qi, 10) + 1}`, `[${key}] ${text} | correct: ${ok ? 'Yes' : 'No'}`);
      })
    ));
  }
}

/* ─────────────────────────────────────────────────────────────
   VALIDATION
───────────────────────────────────────────────────────────────*/
function validateStep () {
  hideStatus();

  if (currentStep === 1) {
    const title    = document.getElementById('id_title').value.trim();
    const maxScore = parseFloat(document.getElementById('id_max_score').value);
    const status   = document.getElementById('id_status').value;

    if (!title) {
      document.getElementById('err_title').textContent = 'Title is required.';
      showStatus('Please fill in all required fields.', 'error');
      return false;
    }
    document.getElementById('err_title').textContent = '';

    if (!maxScore || maxScore <= 0) {
      document.getElementById('err_max_score').textContent = 'Max score must be greater than zero.';
      showStatus('Max score must be greater than zero.', 'error');
      return false;
    }
    document.getElementById('err_max_score').textContent = '';

    if (status === 'PUBLISHED' && (!maxScore || maxScore <= 0)) {
      document.getElementById('err_status').textContent = 'Cannot publish without a valid max score.';
      return false;
    }
    document.getElementById('err_status').textContent = '';
  }

  if (currentStep === 3) {
    const questions = document.querySelectorAll('#questionList .qn-entry');
    if (!questions.length) {
      showStatus('Add at least one question.', 'error');
      return false;
    }

    const maxScore = parseFloat(document.getElementById('id_max_score').value) || 0;
    const totalWeight = Array.from(document.querySelectorAll('input[name="weight"]'))
      .reduce((s, el) => s + (parseFloat(el.value) || 0), 0);

    if (maxScore && totalWeight > maxScore) {
      showStatus(`Total weight (${totalWeight}) exceeds max score (${maxScore}). Adjust weights before continuing.`, 'error');
      return false;
    }

    /* Validate JSON for NUMERIC questions */
    let jsonOk = true;
    questions.forEach((q, i) => {
      const type = q.querySelector('select[name="question_type"]').value;
      if (type === 'NUMERIC') {
        const raw = q.querySelector('textarea[name="numeric_config_raw"]').value.trim();
        if (!raw) {
          showStatus(`Question ${i + 1}: Numeric config is required for NUMERIC type.`, 'error');
          jsonOk = false;
          return;
        }
        try {
          const parsed = JSON.parse(raw);
          if (!parsed.min === undefined || !parsed.max === undefined) throw new Error('missing keys');
          if (parsed.min >= parsed.max) throw new Error('min >= max');
        } catch (e) {
          showStatus(`Question ${i + 1}: Invalid numeric config JSON — ${e.message}`, 'error');
          jsonOk = false;
        }
      }
    });
    if (!jsonOk) return false;

    document.getElementById('err_questions').textContent = '';
  }

  if (currentStep === 4) {
    const choices = document.querySelectorAll('#choiceList .qn-entry');
    /* Check each choice has key + text */
    let ok = true;
    choices.forEach((c, i) => {
      const key  = c.querySelector('input[name="choice_key"]').value.trim();
      const text = c.querySelector('textarea[name="choice_text"]').value.trim();
      if (!key || !text) {
        showStatus(`Choice ${i + 1}: key and text are required.`, 'error');
        ok = false;
      }
    });
    if (!ok) return false;
    document.getElementById('err_choices').textContent = '';
  }

  return true;
}

/* ─────────────────────────────────────────────────────────────
   FORM DATA + SUBMIT
   Plain repeated keys — backend uses getlist() by name.
───────────────────────────────────────────────────────────────*/
function buildFormData () {
  const fd = new FormData();

  /* CSRF */
  const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]');
  if (csrf) fd.append('csrfmiddlewaretoken', csrf.value);

  /* Step 1 — meta */
  ['title','description','instructions','status','max_score','time_limit_minutes'].forEach(name => {
    const el = document.querySelector(`[name="${name}"]`);
    if (el) fd.append(name, el.value);
  });
  const rand = document.getElementById('id_is_randomised');
  fd.append('is_randomised', rand.checked ? 'on' : '');

  /* Step 2 — tags (plain repeated keys, ordered) */
  document.querySelectorAll('#tagList .qn-entry').forEach(entry => {
    fd.append('tag',               entry.querySelector('input[name="tag"]').value);
    fd.append('coupling_strength', entry.querySelector('input[name="coupling_strength"]').value);
    fd.append('is_primary',        entry.querySelector('input[name="is_primary"]').checked ? 'on' : '');
  });

  /* Step 3 — questions */
  document.querySelectorAll('#questionList .qn-entry').forEach((entry, i) => {
    fd.append('question_text',        entry.querySelector('textarea[name="question_text"]').value);
    fd.append('question_type',        entry.querySelector('select[name="question_type"]').value);
    fd.append('weight',               entry.querySelector('input[name="weight"]').value);
    fd.append('max_points',           entry.querySelector('input[name="max_points"]').value);
    fd.append('order',                entry.querySelector('input[name="order"]').value);
    fd.append('randomisation_group',  entry.querySelector('input[name="randomisation_group"]').value);
    fd.append('is_required',          entry.querySelector('input[name="is_required"]').checked ? 'on' : '');
    fd.append('explanation',          entry.querySelector('textarea[name="explanation"]').value);
    fd.append('numeric_config_raw',   entry.querySelector('textarea[name="numeric_config_raw"]').value);
    fd.append('question_index',       String(i));
  });

  /* Step 4 — choices */
  document.querySelectorAll('#choiceList .qn-entry').forEach(entry => {
    fd.append('choice_key',            entry.querySelector('input[name="choice_key"]').value);
    fd.append('choice_text',           entry.querySelector('textarea[name="choice_text"]').value);
    fd.append('is_correct',            entry.querySelector('input[name="is_correct"]').checked ? 'on' : '');
    fd.append('partial_score',         entry.querySelector('input[name="partial_score"]').value);
    fd.append('choice_order',          entry.querySelector('input[name="choice_order"]').value);
    fd.append('choice_explanation',    entry.querySelector('textarea[name="choice_explanation"]').value);
    fd.append('choice_question_index', entry.querySelector('select[name="choice_question_index"]').value);
  });

  return fd;
}

async function submitForm () {
  const submitBtn = document.getElementById('qnBtnSubmit');
  const loader    = document.getElementById('qnLoader');

  submitBtn.classList.add('loading');
  submitBtn.disabled = true;
  loader.classList.remove('hidden');

  try {
    const response = await fetch(window.QN_URL, {
      method : 'POST',
      body   : buildFormData(),
      headers: {
        'X-CSRFToken': (document.querySelector('input[name="csrfmiddlewaretoken"]') || {}).value || '',
      },
    });

    loader.classList.add('hidden');

    if (response.status === 201 || response.ok) {
      showStatus('Questionnaire created successfully! Redirecting…', 'success');
      setTimeout(() => { window.location.href = window.QN_URL; }, 1800);

    } else {
      let data = {};
      try { data = await response.json(); } catch { /* non-JSON */ }

      const errors = data.errors || data || {};
      const messages = [];

      if (typeof errors === 'object') {
        Object.entries(errors).forEach(([field, msgs]) => {
          const msg = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
          /* Try to show inline; fall back to banner */
          const el = document.getElementById(`err_${field}`);
          if (el) el.textContent = msg;
          else    messages.push(`${field}: ${msg}`);
        });
      } else {
        messages.push(String(errors));
      }

      showStatus(
        messages.length ? messages.join(' · ') : `Server error (${response.status}). Check fields above.`,
        'error'
      );
    }

  } catch (err) {
    loader.classList.add('hidden');
    showStatus('Network error. Please try again.', 'error');
    console.error('[Questionnaire] submit error:', err);

  } finally {
    submitBtn.classList.remove('loading');
    submitBtn.disabled = false;
  }
}

/* ─────────────────────────────────────────────────────────────
   BOOT
───────────────────────────────────────────────────────────────*/
function init () {
  /* Step navigation */
  document.getElementById('qnBtnNext').addEventListener('click', () => {
    if (validateStep()) goToStep(currentStep + 1);
  });
  document.getElementById('qnBtnBack').addEventListener('click', () => {
    goToStep(currentStep - 1);
  });

  /* Form submit */
  document.getElementById('qnForm').addEventListener('submit', e => {
    e.preventDefault();
    submitForm();
  });

  /* Dynamic add buttons */
  document.getElementById('addTag').addEventListener('click', () => {
    const list = document.getElementById('tagList');
    list.appendChild(buildTagEntry(list.children.length));
  });

  document.getElementById('addQuestion').addEventListener('click', () => {
    const list = document.getElementById('questionList');
    list.appendChild(buildQuestionEntry(list.children.length));
    updatePointsWidget();
  });

  document.getElementById('addChoice').addEventListener('click', () => {
    const list = document.getElementById('choiceList');
    list.appendChild(buildChoiceEntry(list.children.length));
  });

  /* Points widget updates when max_score changes */
  document.getElementById('id_max_score').addEventListener('input', updatePointsWidget);

  /* Seed starter entries */
  document.getElementById('tagList').appendChild(buildTagEntry(0));
  document.getElementById('questionList').appendChild(buildQuestionEntry(0));
  document.getElementById('choiceList').appendChild(buildChoiceEntry(0));

  goToStep(1);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}