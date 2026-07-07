/**
 * accounts/static/accounts/js/reset_password.js
 *
 * EXPECTED DOM:
 *   #resetForm                     — the form element
 *   #id_new_password               — new password input
 *   #id_new_password_confirm       — confirm password input
 *   #rp-status                     — error/info banner (aria-live)
 *   #rp-toast                      — success toast
 *   .rp-meter__fill / #rp-pw-strength-text — strength meter UI
 *   #rp-submit / .rp-submit-spinner — submit button + spinner
 *   .input-toggle-pw                — password show/hide buttons (shared w/ registration)
 *
 * ENDPOINT:
 *   POSTs to window.location.href — uid/token are already part of the path,
 *   so no URL needs to be injected by the template.
 *
 * RESPONSE CONTRACT (JSON):
 *   Success: { success: true, message?: string }
 *   Failure: { success: false, errors: { new_password: [...], new_password_confirm: [...] } }
 *            or { success: false, error: "generic message" }
 */

'use strict';

/* ─────────────────────────────────────────────────────────────
   CONFIG — tweak redirect target / delay here
───────────────────────────────────────────────────────────────*/
const REDIRECT_URL   = window.REDIRECT_URL;   // change to dashboard URL if view auto-logs-in
const REDIRECT_DELAY = 1000;                 // ms, per spec ("short delay, e.g., 1s")
const MIN_LENGTH     = 8;

/* ─────────────────────────────────────────────────────────────
   CSRF — DOM first, cookie fallback
───────────────────────────────────────────────────────────────*/
function getCsrfToken () {
  const domToken = document.querySelector('input[name="csrfmiddlewaretoken"]');
  if (domToken && domToken.value) return domToken.value;

  // Fallback: read csrftoken cookie (Django's default cookie name)
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  if (match) return decodeURIComponent(match[1]);

  console.warn('[ResetPassword] No CSRF token found in DOM or cookies. Request may be rejected.');
  return '';
}

/* ─────────────────────────────────────────────────────────────
   REDUCED MOTION CHECK
───────────────────────────────────────────────────────────────*/
const prefersReducedMotion = () =>
  window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ─────────────────────────────────────────────────────────────
   PASSWORD STRENGTH — heuristic scoring 0–4
───────────────────────────────────────────────────────────────*/
function estimateStrength (pw) {
  if (!pw) return 0;

  let score = 0;
  if (pw.length >= MIN_LENGTH) score++;
  if (pw.length >= 12)         score++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) score++;

  return Math.min(score, 4);
}

const STRENGTH_LABELS = ['', 'Weak', 'Fair', 'Good', 'Strong'];

function updateStrengthMeter (pw) {
  const score = estimateStrength(pw);
  const fill  = document.getElementById('rp-meter-fill');
  const text  = document.getElementById('rp-pw-strength-text');
  const track = fill.closest('.rp-meter');

  fill.dataset.strength = score;
  text.dataset.strength = score;
  text.textContent      = pw ? STRENGTH_LABELS[score] : '';
  track.parentElement.setAttribute('aria-valuenow', score);
}

/* ─────────────────────────────────────────────────────────────
   FIELD ERROR HELPERS
───────────────────────────────────────────────────────────────*/
function setFieldError (fieldName, message) {
  const errEl = document.getElementById(`rp-err-${fieldName.replace(/_/g, '-')}`);
  const input = document.querySelector(`[name="${fieldName}"]`);
  if (errEl) errEl.textContent = message;
  if (input) input.classList.add('input-error');
}

function clearFieldError (fieldName) {
  const errEl = document.getElementById(`rp-err-${fieldName.replace(/_/g, '-')}`);
  const input = document.querySelector(`[name="${fieldName}"]`);
  if (errEl) errEl.textContent = '';
  if (input) input.classList.remove('input-error');
}

function clearAllErrors () {
  ['new-password', 'new-password-confirm'].forEach(id => {
    const el = document.getElementById(`rp-err-${id}`);
    if (el) el.textContent = '';
  });
  document.querySelectorAll('.form-input').forEach(i => i.classList.remove('input-error'));
  hideStatus();
}

/* ─────────────────────────────────────────────────────────────
   STATUS BANNER
───────────────────────────────────────────────────────────────*/
function showStatus (message, type = 'error') {
  const el = document.getElementById('rp-status');
  el.className = `rp-status rp-status--${type}`;
  el.textContent = message;
  el.classList.remove('hidden');
}

function hideStatus () {
  document.getElementById('rp-status').classList.add('hidden');
}

/* ─────────────────────────────────────────────────────────────
   CLIENT-SIDE VALIDATION
───────────────────────────────────────────────────────────────*/
function validateForm () {
  let ok = true;
  clearAllErrors();

  const pw      = document.getElementById('id_new_password').value;
  const confirm = document.getElementById('id_new_password_confirm').value;

  if (!pw) {
    setFieldError('new_password', 'Password is required.');
    ok = false;
  } else if (pw.length < MIN_LENGTH) {
    setFieldError('new_password', `Password must be at least ${MIN_LENGTH} characters.`);
    ok = false;
  }

  if (!confirm) {
    setFieldError('new_password_confirm', 'Please confirm your new password.');
    ok = false;
  } else if (pw && confirm && pw !== confirm) {
    setFieldError('new_password_confirm', 'Passwords do not match.');
    ok = false;
  }

  return ok;
}

/* ─────────────────────────────────────────────────────────────
   SUCCESS TOAST
───────────────────────────────────────────────────────────────*/
function showToast (message) {
  const toast = document.getElementById('rp-toast');
  toast.querySelector('.rp-toast__text').textContent = message;
  toast.classList.remove('hidden');
}

/* ─────────────────────────────────────────────────────────────
   PASSWORD VISIBILITY TOGGLE — shared markup pattern w/ registration
───────────────────────────────────────────────────────────────*/
function initPasswordToggles () {
  document.querySelectorAll('.input-toggle-pw').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      const isText = target.type === 'text';
      target.type  = isText ? 'password' : 'text';
      btn.setAttribute('aria-label', isText ? 'Show password' : 'Hide password');
    });
  });
}

/* ─────────────────────────────────────────────────────────────
   SUBMIT HANDLER
───────────────────────────────────────────────────────────────*/
async function handleSubmit (e) {
  e.preventDefault();

  if (!validateForm()) return;

  const form      = document.getElementById('resetForm');
  const submitBtn = document.getElementById('rp-submit');
  const inputs    = form.querySelectorAll('input');

  const formData = new FormData(form);

  // Loading state — disable inputs, show spinner
  submitBtn.classList.add('loading');
  submitBtn.disabled = true;
  inputs.forEach(i => i.disabled = true);

  const csrf     = getCsrfToken();
  
  try {
    // POST to the current URL — uid/token are already in the path.
    const response = await fetch(window.location.href, {
      method:  'POST',
      body:    formData,
      headers: { 'X-CSRFToken': csrf },
    });

    let data = {};
    try { data = await response.json(); }
    catch {
      console.warn('[ResetPassword] Server did not return JSON. Treating as generic error.');
    }

    if (response.ok && (data.success === true || response.status === 200 || response.status === 201)) {
      // ── SUCCESS ──
      showToast(data.message || 'Password updated! Redirecting…');
      showStatus(data.message || 'Your password has been reset successfully.', 'success');

      setTimeout(() => {
        window.location.href = REDIRECT_URL;
      }, REDIRECT_DELAY);

    } else {
      // ── FAILURE (400/401 or success:false) ──
      if (data.errors && typeof data.errors === 'object') {
        Object.entries(data.errors).forEach(([field, msgs]) => {
          const msg = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
          setFieldError(field, msg);
        });
        showStatus('Please fix the errors below and try again.', 'error');
      } else {
        showStatus(data.error || data.message || 'This reset link may be invalid or expired.', 'error');
      }

      // Re-enable form for retry
      inputs.forEach(i => i.disabled = false);
      submitBtn.classList.remove('loading');
      submitBtn.disabled = false;
    }

  } catch (networkErr) {
    showStatus('Network error. Please check your connection and try again.', 'error');
    console.error('[ResetPassword] fetch error:', networkErr);

    inputs.forEach(i => i.disabled = false);
    submitBtn.classList.remove('loading');
    submitBtn.disabled = false;
  }
}

/* ─────────────────────────────────────────────────────────────
   BOOT
───────────────────────────────────────────────────────────────*/
function init () {
  // Theme toggle — shared system with registration/login
  const themeBtn = document.getElementById('themeToggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const isDark = document.documentElement.classList.toggle('theme-dark');
      localStorage.setItem('reg_theme', isDark ? 'dark' : 'light');
    });
  }

  // Strength meter — live update on input
  const pwInput = document.getElementById('id_new_password');
  if (pwInput) {
    pwInput.addEventListener('input', () => {
      updateStrengthMeter(pwInput.value);
      clearFieldError('new_password');
    });
  }

  const confirmInput = document.getElementById('id_new_password_confirm');
  if (confirmInput) {
    confirmInput.addEventListener('input', () => clearFieldError('new_password_confirm'));
  }

  // Password show/hide
  initPasswordToggles();

  // Form submit — intercepted; falls back to native POST if JS fails to attach
  const form = document.getElementById('resetForm');
  if (form) form.addEventListener('submit', handleSubmit);

  // Respect reduced motion: strip toast/card animation classes if needed
  if (prefersReducedMotion()) {
    document.documentElement.classList.add('rp-reduced-motion');
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}