
'use strict';

/* ─────────────────────────────────────────────────────────────
   CONSTANTS & STATE
───────────────────────────────────────────────────────────────*/
const TOTAL_STEPS  = 4;
const MAX_CAREERS  = 4;

// Career options — extend or fetch dynamically if needed
const CAREER_OPTIONS = [
  { value: '',          label: '— select career —' },
  { value: 'engineer',  label: 'Software Engineer' },
  { value: 'designer',  label: 'UX/UI Designer' },
  { value: 'doctor',    label: 'Medicine / Doctor' },
  { value: 'teacher',   label: 'Education / Teacher' },
  { value: 'lawyer',    label: 'Law / Lawyer' },
  { value: 'finance',   label: 'Finance / Accounting' },
  { value: 'science',   label: 'Research / Science' },
  { value: 'other',     label: 'Other' },
];

// Subject options — extend as needed
const SUBJECT_OPTIONS = [
  { value: '',           label: '— select subject —' },
  { value: 'math',       label: 'Mathematics' },
  { value: 'english',    label: 'English' },
  { value: 'science',    label: 'Science' },
  { value: 'history',    label: 'History' },
  { value: 'geography',  label: 'Geography' },
  { value: 'ict',        label: 'ICT / Computer Science' },
  { value: 'art',        label: 'Art & Design' },
  { value: 'pe',         label: 'Physical Education' },
  { value: 'other',      label: 'Other' },
];

let currentStep = 1;

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

  // Steps 2–4 have no hard required fields client-side (server validates)
  return valid;
}

/* ─────────────────────────────────────────────────────────────
   DYNAMIC CAREER LIST (Step 3)
───────────────────────────────────────────────────────────────*/

/** Build a single career entry row */
function buildCareerEntry (index) {
  const entry = document.createElement('div');
  entry.className = 'dynamic-list__entry';
  entry.dataset.index = index;

  // Rank field
  const rankLabel = document.createElement('label');
  rankLabel.className = 'form-label sr-only';
  rankLabel.htmlFor = `career_${index}_rank`;
  rankLabel.textContent = `Career ${index + 1} rank`;

  const rankInput = document.createElement('input');
  rankInput.className = 'form-input';
  rankInput.type      = 'number';
  rankInput.id        = `career_${index}_rank`;
  rankInput.name      = `career-${index}-rank`;
  rankInput.min       = '1';
  rankInput.max       = '4';
  rankInput.value     = index + 1;
  rankInput.placeholder = 'Rank';
  rankInput.setAttribute('aria-label', `Career preference ${index + 1} rank`);

  // Career select
  const careerLabel = document.createElement('label');
  careerLabel.className = 'form-label sr-only';
  careerLabel.htmlFor = `career_${index}_career`;
  careerLabel.textContent = `Career ${index + 1}`;

  const select = document.createElement('select');
  select.className = 'form-input';
  select.id        = `career_${index}_career`;
  select.name      = `career-${index}-career`;
  select.setAttribute('aria-label', `Career preference ${index + 1}`);

  CAREER_OPTIONS.forEach(opt => {
    const o = document.createElement('option');
    o.value = opt.value;
    o.textContent = opt.label;
    select.appendChild(o);
  });

  const fields = document.createElement('div');
  fields.className = 'dynamic-list__fields';
  fields.appendChild(rankLabel);
  fields.appendChild(rankInput);
  fields.appendChild(careerLabel);
  fields.appendChild(select);

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

function buildSubjectEntry (index) {
  const entry = document.createElement('div');
  entry.className = 'dynamic-list__entry';
  entry.dataset.index = index;

  // Subject select
  const subjectLabel = document.createElement('label');
  subjectLabel.className = 'form-label sr-only';
  subjectLabel.htmlFor = `subject_${index}_subject`;
  subjectLabel.textContent = `Subject ${index + 1}`;

  const select = document.createElement('select');
  select.className = 'form-input';
  select.id        = `subject_${index}_subject`;
  select.name      = `subject-${index}-subject`;
  select.setAttribute('aria-label', `Subject ${index + 1}`);

  SUBJECT_OPTIONS.forEach(opt => {
    const o = document.createElement('option');
    o.value = opt.value;
    o.textContent = opt.label;
    select.appendChild(o);
  });

  // Grade input
  const gradeLabel = document.createElement('label');
  gradeLabel.className = 'form-label sr-only';
  gradeLabel.htmlFor = `subject_${index}_grade`;
  gradeLabel.textContent = `Grade for subject ${index + 1}`;

  const gradeInput = document.createElement('input');
  gradeInput.className    = 'form-input';
  gradeInput.type         = 'text';
  gradeInput.id           = `subject_${index}_grade`;
  gradeInput.name         = `subject-${index}-grade`;
  gradeInput.placeholder  = 'Grade';
  gradeInput.maxLength    = 5;
  gradeInput.setAttribute('aria-label', `Grade for subject ${index + 1}`);

  // Active checkbox
  const activeLabel = document.createElement('label');
  activeLabel.className = 'toggle-label';
  activeLabel.htmlFor = `subject_${index}_is_active`;

  const activeCheck = document.createElement('input');
  activeCheck.type      = 'checkbox';
  activeCheck.className = 'toggle-checkbox';
  activeCheck.id        = `subject_${index}_is_active`;
  activeCheck.name      = `subject-${index}-is_active`;
  activeCheck.checked   = true;
  activeCheck.value     = 'on';

  activeLabel.appendChild(activeCheck);
  activeLabel.appendChild(document.createTextNode('Active'));

  const fields = document.createElement('div');
  fields.className = 'dynamic-list__fields dynamic-list__fields--subject';
  fields.appendChild(subjectLabel);
  fields.appendChild(select);
  fields.appendChild(gradeLabel);
  fields.appendChild(gradeInput);
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

  // Re-index remaining entries' input names
  Array.from(list.children).forEach((entry, newIndex) => {
    entry.dataset.index = newIndex;
    entry.querySelectorAll('input, select').forEach(el => {
      if (el.name) {
        // Replace the numeric index in name, e.g. career-2-rank → career-0-rank
        el.name = el.name.replace(/-\d+-/, `-${newIndex}-`);
        el.id   = el.id.replace(/_\d+_/, `_${newIndex}_`);
      }
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

  // ── Career formset management keys ──
  const careerCount = document.getElementById('careerList').children.length;
  fd.set('career-TOTAL_FORMS',   careerCount);
  fd.set('career-INITIAL_FORMS', '0');
  fd.set('career-MIN_NUM_FORMS', '0');
  fd.set('career-MAX_NUM_FORMS', String(MAX_CAREERS));

  // ── Subject formset management keys ──
  const subjectCount = document.getElementById('subjectList').children.length;
  fd.set('subject-TOTAL_FORMS',   subjectCount);
  fd.set('subject-INITIAL_FORMS', '0');
  fd.set('subject-MIN_NUM_FORMS', '0');
  fd.set('subject-MAX_NUM_FORMS', '1000');

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
        window.location.href = '/accounts/login/?registered=1';
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