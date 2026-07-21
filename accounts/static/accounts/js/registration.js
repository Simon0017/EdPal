/**
 * FILE: accounts/static/accounts/js/registration.js
 * PURPOSE: Multi-step registration form logic.
 *
 * DEPENDENCIES:
 *   - window.REGISTRATION_URL must be set in the template:
 *       <script>window.REGISTRATION_URL = "{% url 'user_regisration' %}";</script>
 *   - A hidden {% csrf_token %} input inside #registrationForm so FormData
 *     captures `csrfmiddlewaretoken` automatically.
 *
 * CAREER FORMSET KEYS (Step 3):
 *   career-{i}-career, career-{i}-rank
 *   If your backend uses a Django ModelFormset, also include:
 *     career-TOTAL_FORMS, career-INITIAL_FORMS, career-MIN_NUM_FORMS, career-MAX_NUM_FORMS
 *   This file appends those management keys automatically before POST.
 *
 * SUBJECT FORMSET KEYS (Step 4):
 *   subject-{i}-subject, subject-{i}-grade, subject-{i}-is_active
 *   Same management key pattern as careers.
 */

'use strict';

/* ─────────────────────────────────────────────────────────────
   CONSTANTS & STATE
───────────────────────────────────────────────────────────────*/
const TOTAL_STEPS  = 4;
const MAX_CAREERS  = 4;

// Options are loaded live from the DB via search endpoints — no hardcoding.

let currentStep = 1;

/* ─────────────────────────────────────────────────────────────
   DEBOUNCE — limits how often we hit the search endpoints
───────────────────────────────────────────────────────────────*/
/**
 * Returns a debounced version of fn that fires after `wait` ms of silence.
 * Prevents a DB query on every keypress.
 */
function debounce (fn, wait = 350) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

/* ─────────────────────────────────────────────────────────────
   LIVE-SEARCH AUTOCOMPLETE WIDGET
   Builds a text input + floating dropdown that queries the server.
   The chosen item's DB id is stored in a hidden <input> for POST.

   Usage:
     buildAutocomplete({
       searchUrl : window.SEARCH_CAREERS_URL,   // endpoint
       inputId   : 'career_0_search',           // visible text box id
       hiddenName: 'career-0-career',           // hidden field name (what Django gets)
       placeholder: 'Search careers…',
       container : parentElement,               // where to mount
     })
───────────────────────────────────────────────────────────────*/
function buildAutocomplete ({ searchUrl, inputId, hiddenName, placeholder, container }) {
  const wrap = document.createElement('div');
  wrap.className = 'autocomplete-wrap';

  // Visible search input
  const searchInput = document.createElement('input');
  searchInput.className   = 'form-input';
  searchInput.type        = 'text';
  searchInput.id          = inputId;
  searchInput.placeholder = placeholder;
  searchInput.autocomplete = 'off';
  searchInput.setAttribute('aria-autocomplete', 'list');
  searchInput.setAttribute('aria-haspopup', 'listbox');

  // Hidden input that carries the chosen DB id to FormData / Django
  const hiddenInput = document.createElement('input');
  hiddenInput.type  = 'hidden';
  hiddenInput.name  = hiddenName;
  hiddenInput.value = '';

  // Chip showing selected item (replaces search box when chosen)
  const chipWrap = document.createElement('div');
  chipWrap.style.display = 'none';

  // Dropdown list
  const dropdown = document.createElement('div');
  dropdown.className = 'autocomplete-dropdown';
  dropdown.setAttribute('role', 'listbox');

  wrap.appendChild(searchInput);
  wrap.appendChild(hiddenInput);
  wrap.appendChild(chipWrap);
  wrap.appendChild(dropdown);
  container.appendChild(wrap);

  let focusedIndex = -1;

  function renderOptions (items) {
    dropdown.innerHTML = '';
    focusedIndex = -1;

    if (!items.length) {
      const empty = document.createElement('div');
      empty.className = 'autocomplete-option autocomplete-option--empty';
      empty.textContent = 'No results found.';
      dropdown.appendChild(empty);
    } else {
      items.forEach(({ id, name }) => {
        const opt = document.createElement('div');
        opt.className = 'autocomplete-option';
        opt.setAttribute('role', 'option');
        opt.dataset.id   = id;
        opt.dataset.name = name;
        opt.textContent  = name;
        opt.addEventListener('mousedown', e => {
          // mousedown fires before blur so we can capture the click
          e.preventDefault();
          selectItem(id, name);
        });
        dropdown.appendChild(opt);
      });
    }
    dropdown.classList.add('open');
  }

  function selectItem (id, name) {
    hiddenInput.value      = id;
    searchInput.style.display = 'none';
    dropdown.classList.remove('open');

    // Show chip
    chipWrap.style.display = 'block';
    chipWrap.innerHTML = '';
    const chip = document.createElement('span');
    chip.className = 'autocomplete-chip';
    chip.innerHTML = `${name} <button type="button" class="autocomplete-chip__remove" aria-label="Remove ${name}">✕</button>`;
    chip.querySelector('button').addEventListener('click', () => {
      hiddenInput.value         = '';
      chipWrap.style.display    = 'none';
      chipWrap.innerHTML        = '';
      searchInput.style.display = '';
      searchInput.value         = '';
      searchInput.focus();
    });
    chipWrap.appendChild(chip);
  }

  // Debounced fetch — fires 350 ms after the user stops typing
  const doSearch = debounce(async (query) => {
    if (!query || query.length < 2) { dropdown.classList.remove('open'); return; }

    // Show loading state
    dropdown.innerHTML = '<div class="autocomplete-option autocomplete-option--loading">Searching…</div>';
    dropdown.classList.add('open');

    try {
      const res  = await fetch(`${searchUrl}?query=${encodeURIComponent(query)}`);
      const data = await res.json();

      if (!data.success) {
        renderOptions([]);
        return;
      }

      // View returns { success: true, message: { id: name, ... } }
      // Convert object → array of { id, name }
      const items = Array.isArray(data.message)
          ? data.message.map(item => ({ id: item.id, name: item.title ?? item.name }))
          : Object.entries(data.message).map(([id, name]) => ({ id, name }));
      console.log(data);
      
      console.log(items);
      
      renderOptions(items);

    } catch (err) {
      dropdown.innerHTML = '<div class="autocomplete-option autocomplete-option--empty">Search failed.</div>';
      console.error('[Autocomplete] search error:', err);
    }
  }, 350);

  searchInput.addEventListener('input', () => doSearch(searchInput.value.trim()));

  // Keyboard navigation inside dropdown
  searchInput.addEventListener('keydown', e => {
    const opts = dropdown.querySelectorAll('.autocomplete-option:not(.autocomplete-option--empty):not(.autocomplete-option--loading)');
    if (!opts.length) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      focusedIndex = Math.min(focusedIndex + 1, opts.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      focusedIndex = Math.max(focusedIndex - 1, 0);
    } else if (e.key === 'Enter' && focusedIndex >= 0) {
      e.preventDefault();
      const opt = opts[focusedIndex];
      selectItem(opt.dataset.id, opt.dataset.name);
      return;
    } else if (e.key === 'Escape') {
      dropdown.classList.remove('open');
      return;
    }

    opts.forEach((o, i) => o.classList.toggle('focused', i === focusedIndex));
  });

  // Close dropdown when focus leaves the widget
  searchInput.addEventListener('blur', () => {
    // Small delay so mousedown on an option fires first
    setTimeout(() => dropdown.classList.remove('open'), 150);
  });

  return { hiddenInput, searchInput };
}

/* ─────────────────────────────────────────────────────────────
   THEME
───────────────────────────────────────────────────────────────*/
const THEME_KEY = 'reg_theme';

/**
 * Apply saved theme immediately on page load — prevents flash of wrong theme.
 */
function applyStoredTheme () {
  const saved = localStorage.getItem(THEME_KEY);
  // Default: dark
  if (saved === 'light') {
    document.documentElement.classList.remove('theme-dark');
  } else {
    document.documentElement.classList.add('theme-dark');
  }
}

function toggleTheme () {
  const isDark = document.documentElement.classList.toggle('theme-dark');
  localStorage.setItem(THEME_KEY, isDark ? 'dark' : 'light');
}

/* ─────────────────────────────────────────────────────────────
   STEPPER UI
───────────────────────────────────────────────────────────────*/

/**
 * Update stepper dots, progress bar, and step counter text.
 * @param {number} step — 1-based current step
 */
function updateStepper (step) {
  document.getElementById('stepNumber').textContent = step;

  // Progress bar width
  const fill = document.getElementById('stepperFill');
  fill.style.width = `${(step / TOTAL_STEPS) * 100}%`;
  fill.parentElement.setAttribute('aria-valuenow', step);

  // Dot states
  document.querySelectorAll('.stepper__item').forEach(item => {
    const n = parseInt(item.dataset.step, 10);
    item.classList.remove('stepper__item--active', 'stepper__item--done');
    item.removeAttribute('aria-current');

    if (n === step) {
      item.classList.add('stepper__item--active');
      item.setAttribute('aria-current', 'step');
    } else if (n < step) {
      item.classList.add('stepper__item--done');
      // Replace number with checkmark for done steps
      item.querySelector('.stepper__dot').textContent = '✓';
    } else {
      // Restore number for future steps
      item.querySelector('.stepper__dot').textContent = n;
    }
  });
}

/* ─────────────────────────────────────────────────────────────
   STEP TRANSITIONS
───────────────────────────────────────────────────────────────*/

/**
 * Show the target fieldset, hide others, update nav buttons.
 * @param {number} targetStep
 */
function goToStep (targetStep) {
  if (targetStep < 1 || targetStep > TOTAL_STEPS) return;

  // Hide all steps
  document.querySelectorAll('.reg-step').forEach(fs => fs.classList.add('hidden'));

  // Show target
  document.getElementById(`step${targetStep}`).classList.remove('hidden');

  // Nav buttons
  const btnBack   = document.getElementById('btnBack');
  const btnNext   = document.getElementById('btnNext');
  const btnSubmit = document.getElementById('btnSubmit');

  btnBack.disabled = targetStep === 1;

  if (targetStep === TOTAL_STEPS) {
    btnNext.classList.add('hidden');
    btnSubmit.classList.remove('hidden');
  } else {
    btnNext.classList.remove('hidden');
    btnSubmit.classList.add('hidden');
  }

  currentStep = targetStep;
  updateStepper(targetStep);

  // Scroll card into view smoothly
  document.querySelector('.reg-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ─────────────────────────────────────────────────────────────
   VALIDATION
───────────────────────────────────────────────────────────────*/

/** Display an error under a field */
function setError (id, message) {
  const el = document.getElementById(`err_${id}`);
  if (!el) return;
  el.textContent = message;
  const input = document.querySelector(`[name="${id}"], #id_${id}`);
  if (input) input.classList.add('input-error');
}

/** Clear error under a field */
function clearError (id) {
  const el = document.getElementById(`err_${id}`);
  if (!el) return;
  el.textContent = '';
  const input = document.querySelector(`[name="${id}"], #id_${id}`);
  if (input) input.classList.remove('input-error');
}

/** Basic email regex */
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Validate the current step.
 * Returns true if valid, false otherwise.
 */
function validateCurrentStep () {
  let valid = true;

  if (currentStep === 1) {
    const fields = ['username','first_name','last_name','email','password','password_confirm'];
    fields.forEach(f => clearError(f));

    const get = id => document.getElementById(`id_${id}`).value.trim();

    if (!get('username'))     { setError('username',     'Username is required.');    valid = false; }
    if (!get('first_name'))   { setError('first_name',   'First name is required.');  valid = false; }
    if (!get('last_name'))    { setError('last_name',    'Last name is required.');   valid = false; }

    if (!get('email')) {
      setError('email', 'Email is required.');
      valid = false;
    } else if (!EMAIL_RE.test(get('email'))) {
      setError('email', 'Enter a valid email address.');
      valid = false;
    }

    if (!get('password')) {
      setError('password', 'Password is required.');
      valid = false;
    } else if (document.getElementById('id_password').value.length < 8) {
      setError('password', 'Password must be at least 8 characters.');
      valid = false;
    }

    if (!document.getElementById('id_password_confirm').value) {
      setError('password_confirm', 'Please confirm your password.');
      valid = false;
    } else if (
      document.getElementById('id_password').value !==
      document.getElementById('id_password_confirm').value
    ) {
      setError('password_confirm', 'Passwords do not match.');
      valid = false;
    }
  }

  // Steps 2: no required fields client-side
  if (currentStep === 3) {
    // Each career entry must have a selected career (hidden input non-empty)
    // and a rank value
    const careerEntries = document.querySelectorAll('#careerList .dynamic-list__entry');
    const errEl = document.getElementById('err_careers');
    let careerOk = true;

    careerEntries.forEach((entry, i) => {
      const hidden = entry.querySelector(`input[name="career"]`);
      const rank   = entry.querySelector(`input[name="rank"]`);
      if (!hidden || !hidden.value) {
        careerOk = false;
      }
      if (!rank || !rank.value) {
        careerOk = false;
      }
    });

    if (!careerOk) {
      errEl.textContent = 'Please select a career and rank for each entry, or remove empty rows.';
      valid = false;
    } else {
      errEl.textContent = '';
    }
  }

  if (currentStep === 4) {
    // Each subject entry must have a selected subject
    const subjectEntries = document.querySelectorAll('#subjectList .dynamic-list__entry');
    const errEl = document.getElementById('err_subjects');
    let subjectOk = true;

    subjectEntries.forEach((entry, i) => {
      const hidden = entry.querySelector(`input[name="subject"]`);
      if (!hidden || !hidden.value) subjectOk = false;
    });

    if (!subjectOk) {
      errEl.textContent = 'Please select a subject for each entry, or remove empty rows.';
      valid = false;
    } else {
      errEl.textContent = '';
    }
  }

  // Steps 2–4 have no hard required fields client-side (server validates)
  return valid;
}

/* ─────────────────────────────────────────────────────────────
   DYNAMIC CAREER LIST (Step 3)
───────────────────────────────────────────────────────────────*/

/** Build a single career entry row with live-search autocomplete */
function buildCareerEntry (index) {
  const entry = document.createElement('div');
  entry.className = 'dynamic-list__entry';
  entry.dataset.index = index;

  // Rank number input
  const rankLabel = document.createElement('label');
  rankLabel.className = 'form-label sr-only';
  rankLabel.htmlFor = `career_${index}_rank`;
  rankLabel.textContent = `Career ${index + 1} rank`;

  const rankInput = document.createElement('input');
  rankInput.className   = 'form-input';
  rankInput.type        = 'number';
  rankInput.id          = `career_${index}_rank`;
  rankInput.name        = `rank`;
  rankInput.min         = '1';
  rankInput.max         = '4';
  rankInput.value       = index + 1;
  rankInput.placeholder = 'Rank';
  rankInput.setAttribute('aria-label', `Career preference ${index + 1} rank`);

  // Autocomplete search for career (posts DB id as career-{i}-career)
  const careerLabel = document.createElement('label');
  careerLabel.className = 'form-label sr-only';
  careerLabel.textContent = `Career ${index + 1}`;

  // Wrapper div for rank + autocomplete side-by-side
  const fields = document.createElement('div');
  fields.className = 'dynamic-list__fields';

  const rankWrap = document.createElement('div');
  rankWrap.appendChild(rankLabel);
  rankWrap.appendChild(rankInput);

  const searchWrap = document.createElement('div');
  searchWrap.appendChild(careerLabel);

  // buildAutocomplete mounts itself into searchWrap
  buildAutocomplete({
    searchUrl : window.SEARCH_CAREERS_URL,
    inputId   : `career_${index}_search`,
    hiddenName: `career`,   // Django field name
    placeholder: 'Search careers…',
    container  : searchWrap,
  });

  fields.appendChild(rankWrap);
  fields.appendChild(searchWrap);

  // Remove button
  const removeBtn = document.createElement('button');
  removeBtn.type      = 'button';
  removeBtn.className = 'dynamic-list__remove';
  removeBtn.textContent = '✕';
  removeBtn.setAttribute('aria-label', `Remove career preference ${index + 1}`);
  removeBtn.addEventListener('click', () => removeEntry('careerList', index, updateAddCareerButton));

  entry.appendChild(fields);
  entry.appendChild(removeBtn);
  return entry;
}

function addCareerEntry () {
  const list = document.getElementById('careerList');
  const currentCount = list.children.length;
  if (currentCount >= MAX_CAREERS) return;

  list.appendChild(buildCareerEntry(currentCount));
  updateAddCareerButton();
}

function updateAddCareerButton () {
  const list  = document.getElementById('careerList');
  const btn   = document.getElementById('addCareer');
  btn.disabled = list.children.length >= MAX_CAREERS;
}

/* ─────────────────────────────────────────────────────────────
   DYNAMIC SUBJECT LIST (Step 4)
───────────────────────────────────────────────────────────────*/

/** Build a single subject entry row with live-search autocomplete */
function buildSubjectEntry (index) {
  const entry = document.createElement('div');
  entry.className = 'dynamic-list__entry';
  entry.dataset.index = index;

  // Subject autocomplete (posts DB id as subject-{i}-subject)
  const subjectLabel = document.createElement('label');
  subjectLabel.className = 'form-label sr-only';
  subjectLabel.textContent = `Subject ${index + 1}`;

  const subjectWrap = document.createElement('div');
  subjectWrap.appendChild(subjectLabel);

  buildAutocomplete({
    searchUrl : window.SEARCH_SUBJECTS_URL,
    inputId   : `subject_${index}_search`,
    hiddenName: `subject`,   // Django field name
    placeholder: 'Search subjects…',
    container  : subjectWrap,
  });

  // Grade input
  const gradeLabel = document.createElement('label');
  gradeLabel.className = 'form-label sr-only';
  gradeLabel.htmlFor = `subject_${index}_grade`;
  gradeLabel.textContent = `Grade for subject ${index + 1}`;

  const gradeInput = document.createElement('input');
  gradeInput.className   = 'form-input';
  gradeInput.type        = 'text';
  gradeInput.id          = `grade`;
  gradeInput.name        = `grade`;
  gradeInput.placeholder = 'Grade';
  gradeInput.maxLength   = 5;
  gradeInput.setAttribute('aria-label', `Grade for subject ${index + 1}`);

  const gradeWrap = document.createElement('div');
  gradeWrap.appendChild(gradeLabel);
  gradeWrap.appendChild(gradeInput);

  // Active checkbox
  const activeLabel = document.createElement('label');
  activeLabel.className = 'toggle-label';
  activeLabel.htmlFor = `subject_${index}_is_active`;

  const activeCheck = document.createElement('input');
  activeCheck.type      = 'checkbox';
  activeCheck.className = 'toggle-checkbox';
  activeCheck.id        = `subject_${index}_is_active`;
  activeCheck.name      = `is_active`;
  activeCheck.checked   = true;
  activeCheck.value     = 'on';

  activeLabel.appendChild(activeCheck);
  activeLabel.appendChild(document.createTextNode('Active'));

  const fields = document.createElement('div');
  fields.className = 'dynamic-list__fields dynamic-list__fields--subject';
  fields.appendChild(subjectWrap);
  fields.appendChild(gradeWrap);
  fields.appendChild(activeLabel);

  const removeBtn = document.createElement('button');
  removeBtn.type      = 'button';
  removeBtn.className = 'dynamic-list__remove';
  removeBtn.textContent = '✕';
  removeBtn.setAttribute('aria-label', `Remove subject ${index + 1}`);
  removeBtn.addEventListener('click', () => removeEntry('subjectList', index, () => {}));

  entry.appendChild(fields);
  entry.appendChild(removeBtn);
  return entry;
}

function addSubjectEntry () {
  const list = document.getElementById('subjectList');
  list.appendChild(buildSubjectEntry(list.children.length));
}

/* ─────────────────────────────────────────────────────────────
   GENERIC ENTRY REMOVAL
   Removes the entry at `indexToRemove` and re-indexes remaining.
───────────────────────────────────────────────────────────────*/
function removeEntry (listId, indexToRemove, afterCallback) {
  const list = document.getElementById(listId);
  const entries = Array.from(list.children);

  // Find by data-index
  const toRemove = entries.find(e => parseInt(e.dataset.index, 10) === indexToRemove);
  if (toRemove) toRemove.remove();

  // Re-index remaining entries' input names and ids
  Array.from(list.children).forEach((entry, newIndex) => {
    entry.dataset.index = newIndex;
    entry.querySelectorAll('input, select').forEach(el => {
      // Update name: career-2-rank → career-0-rank
      if (el.name) {
        // Explode by hyphen, swap the index safely, and join back
        let parts = el.name.split('-');
        if (parts.length >= 3) {
          parts[1] = newIndex; 
          el.name = parts.join('-');
        }
      }
      // Update id: uses both - and _ separators (career_2_rank vs career-2-rank)
      if (el.id)   el.id   = el.id.replace(/[_-]\d+[_-]/, m => m.replace(/\d+/, newIndex));
    });
  });

  if (typeof afterCallback === 'function') afterCallback();
}

/* ─────────────────────────────────────────────────────────────
   AVATAR PREVIEW
───────────────────────────────────────────────────────────────*/
function initAvatarPreview () {
  const fileInput   = document.getElementById('id_avatar');
  const imgEl       = document.getElementById('avatarImg');
  const placeholder = document.querySelector('.avatar-preview__placeholder');

  if (!fileInput) return;

  fileInput.addEventListener('change', () => {
    const file = fileInput.files[0];
    if (!file) return;

    // Guard: 5 MB limit
    if (file.size > 5 * 1024 * 1024) {
      setError('avatar', 'File exceeds 5 MB limit.');
      fileInput.value = '';
      return;
    }
    clearError('avatar');

    const reader = new FileReader();
    reader.onload = e => {
      imgEl.src = e.target.result;
      imgEl.classList.remove('hidden');
      placeholder.style.display = 'none';
    };
    reader.readAsDataURL(file);
  });
}

/* ─────────────────────────────────────────────────────────────
   PASSWORD VISIBILITY TOGGLE
───────────────────────────────────────────────────────────────*/
function initPasswordToggles () {
  document.querySelectorAll('.input-toggle-pw').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      const isText = target.type === 'text';
      target.type = isText ? 'password' : 'text';
      btn.setAttribute('aria-label', isText ? 'Show password' : 'Hide password');
      btn.textContent = isText ? '👁' : '🙈';
    });
  });
}

/* ─────────────────────────────────────────────────────────────
   SERVER ERROR MAPPING
   Maps JSON error keys from Django back to form field error spans.
───────────────────────────────────────────────────────────────*/

/**
 * @param {Object} errors — Django's form.errors dict (key: [message, ...])
 */
function applyServerErrors (errors) {
  const banner = document.getElementById('globalError');
  const messages = [];

  Object.entries(errors).forEach(([field, errs]) => {
    const msg = Array.isArray(errs) ? errs.join(' ') : String(errs);
    const el  = document.getElementById(`err_${field}`);
    if (el) {
      el.textContent = msg;
      const input = document.querySelector(`[name="${field}"], #id_${field}`);
      if (input) input.classList.add('input-error');
    } else {
      // Fallback: collect in banner
      messages.push(`${field}: ${msg}`);
    }
  });

  if (messages.length) {
    banner.textContent = messages.join('\n');
    banner.classList.remove('hidden');
  }

  // Jump to step 1 if step-1 field has an error
  const step1Fields = ['username','first_name','last_name','email','password','password_confirm'];
  if (step1Fields.some(f => errors[f])) goToStep(1);
}

/* ─────────────────────────────────────────────────────────────
   FORM DATA ASSEMBLY
   Collects ALL step data into one FormData before POST.
───────────────────────────────────────────────────────────────*/

/**
 * Build and return a FormData from the entire form.
 * Dynamic lists have already written their named inputs into the DOM,
 * so standard FormData construction captures them.
 * We also add Django formset management keys.
 */
function buildFormData () {
  const form = document.getElementById('registrationForm');
  const fd   = new FormData(form); // captures CSRF token + all named inputs + file

  return fd;
}

/* ─────────────────────────────────────────────────────────────
   FORM SUBMISSION
───────────────────────────────────────────────────────────────*/
async function submitRegistration () {
  const submitBtn = document.getElementById('btnSubmit');
  const banner    = document.getElementById('globalError');

  // Clear previous global error
  banner.textContent = '';
  banner.classList.add('hidden');

  // Loading state
  submitBtn.classList.add('loading');
  submitBtn.disabled = true;

  const fd  = buildFormData();
  const url = window.REGISTRATION_URL; // injected by template

  try {
    const response = await fetch(url, {
      method: 'POST',
      body: fd,
      // Do NOT set Content-Type — browser sets multipart boundary automatically
      headers: {
        // X-CSRFToken header is a belt-and-suspenders addition alongside the
        // hidden form input already inside FormData.
        'X-CSRFToken': (document.querySelector('input[name="csrfmiddlewaretoken"]') || {}).value || '',
      },
    });

    if (response.status === 201) {
      // ── SUCCESS ──
      document.getElementById('registrationForm').classList.add('hidden');
      document.getElementById('successPanel').classList.remove('hidden');

      // Redirect after 2.5 s (adjust URL as needed)
      setTimeout(() => {
        window.location.href = '/accounts/user-dashboard';
      }, 2500);

    } else if (response.status === 400) {
      // ── VALIDATION ERRORS from Django ──
      let data;
      try { data = await response.json(); } catch { data = {}; }
      const errors = data.errors || data || {};
      applyServerErrors(errors);

    } else {
      // ── UNEXPECTED ERROR ──
      banner.textContent = `Unexpected error (HTTP ${response.status}). Please try again.`;
      banner.classList.remove('hidden');
    }

  } catch (networkErr) {
    banner.textContent = 'Network error. Please check your connection and try again.';
    banner.classList.remove('hidden');
    console.error('[Registration] fetch error:', networkErr);

  } finally {
    submitBtn.classList.remove('loading');
    submitBtn.disabled = false;
  }
}

/* ─────────────────────────────────────────────────────────────
   KEYBOARD NAVIGATION
   Allow Enter to advance steps (except textarea).
───────────────────────────────────────────────────────────────*/
function initKeyboardNav () {
  document.getElementById('registrationForm').addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    if (e.target.tagName === 'TEXTAREA') return; // let Enter work in textarea
    if (e.target.tagName === 'BUTTON') return;   // let button handle itself

    e.preventDefault();
    if (currentStep < TOTAL_STEPS) {
      document.getElementById('btnNext').click();
    } else {
      document.getElementById('btnSubmit').click();
    }
  });
}

/* ─────────────────────────────────────────────────────────────
   BOOT
───────────────────────────────────────────────────────────────*/
function init () {
  // 1. Apply stored theme (run ASAP to prevent flicker — also called in <head>)
  applyStoredTheme();

  // 2. Theme toggle
  const themeBtn = document.getElementById('themeToggle');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

  // 3. Initialise dynamic lists with one starter entry each
  addCareerEntry();
  addSubjectEntry();

  // 4. Wire "add" buttons
  document.getElementById('addCareer').addEventListener('click', addCareerEntry);
  document.getElementById('addSubject').addEventListener('click', addSubjectEntry);

  // 5. Step navigation buttons
  document.getElementById('btnNext').addEventListener('click', () => {
    if (validateCurrentStep()) goToStep(currentStep + 1);
  });

  document.getElementById('btnBack').addEventListener('click', () => {
    goToStep(currentStep - 1);
  });

  // 6. Form submit
  document.getElementById('registrationForm').addEventListener('submit', e => {
    e.preventDefault();
    submitRegistration();
  });

  // 7. Avatar preview
  initAvatarPreview();

  // 8. Password toggles
  initPasswordToggles();

  // 9. Keyboard nav
  initKeyboardNav();

  // 10. Render initial step
  goToStep(1);
}

// Run after DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}