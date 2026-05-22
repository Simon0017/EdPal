/**
 * FILE: accounts/static/accounts/js/forgot_password.js
 * PURPOSE: Forgot-password page logic.
 *
 * DEPENDS ON (injected by template):
 *   window.FORGOT_PASSWORD_URL — {% url 'forgot_password' %}
 *   window.LOGIN_URL           — {% url 'user_login' %}
 *   window.REGISTER_URL        — {% url 'user_regisration' %}
 *
 * VIDEO + THEME: identical pattern to login.js (same PEXELS_SOURCES,
 *   same THEME_KEY 'reg_theme', same initVideo / applyStoredTheme / toggleTheme).
 *
 * FLOW:
 *   1. User fills in email → validates → POST to FORGOT_PASSWORD_URL
 *   2. On HTTP 200/201 → hide form view, show fp-sent panel with the email
 *   3. On 400 → show inline errors
 *   4. Resend button re-submits with a 60-second cooldown to prevent spam
 */

'use strict';

/* ─────────────────────────────────────────────────────────────
   VIDEO SOURCES — same list as login.js
───────────────────────────────────────────────────────────────*/
const PEXELS_SOURCES = [
  'https://player.vimeo.com/external/558524836.sd.mp4?s=c4b7c4aef3eb4be7bef30cb476e5bd3e91e8bbf2&profile_id=165&oauth2_token_id=57447761',
  'https://player.vimeo.com/external/558524831.sd.mp4?s=7b2c3e4f5d6a8b9c0e1f2a3b4c5d6e7f&profile_id=165&oauth2_token_id=57447761',
];

/* ─────────────────────────────────────────────────────────────
   THEME — same key as registration + login
───────────────────────────────────────────────────────────────*/
const THEME_KEY = 'reg_theme';

function applyStoredTheme () {
  const saved = localStorage.getItem(THEME_KEY);
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
   VIDEO — identical to login.js
───────────────────────────────────────────────────────────────*/
function initVideo () {
  const video    = document.getElementById('loginVideo');
  const fallback = document.getElementById('loginFallback');
  if (!video) return;

  // Random source each load
  const src = PEXELS_SOURCES[Math.floor(Math.random() * PEXELS_SOURCES.length)];
  video.src = src;

  // Slow-motion cinematic playback
  video.addEventListener('canplay', () => {
    video.playbackRate = 0.55;
    video.classList.remove('video-locked');
  }, { once: true });

  function showFallback () {
    video.style.display = 'none';
    fallback.classList.add('visible');
  }

  video.addEventListener('error', showFallback);

  // Safety timeout — show fallback if canplay never fires within 6 s
  const fallbackTimer = setTimeout(showFallback, 6000);
  video.addEventListener('canplay', () => clearTimeout(fallbackTimer), { once: true });
}

/* ─────────────────────────────────────────────────────────────
   STATUS / ERROR HELPERS — same API shape as login.js
───────────────────────────────────────────────────────────────*/
function showStatus (message, type = 'error') {
  const el = document.getElementById('loginStatus'); // reused id from login
  el.className = `login-status login-status--${type}`;
  const icon = type === 'success' ? '✓' : '⚠';
  el.innerHTML = `<span class="login-status__icon" aria-hidden="true">${icon}</span><span>${message}</span>`;
  el.classList.remove('hidden');
}

function hideStatus () {
  const el = document.getElementById('loginStatus');
  if (el) el.classList.add('hidden');
}

function setFieldError (fieldId, message) {
  const errEl = document.getElementById(`err_${fieldId}`);
  const input = document.getElementById(`id_${fieldId}`);
  if (errEl) errEl.textContent = message;
  if (input) input.classList.add('input-error');
}

function clearFieldError (fieldId) {
  const errEl = document.getElementById(`err_${fieldId}`);
  const input = document.getElementById(`id_${fieldId}`);
  if (errEl) errEl.textContent = '';
  if (input) input.classList.remove('input-error');
}

/* ─────────────────────────────────────────────────────────────
   EMAIL VALIDATION
───────────────────────────────────────────────────────────────*/
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validateEmail () {
  const val = document.getElementById('id_email').value.trim();
  if (!val) {
    setFieldError('email', 'Email address is required.');
    return false;
  }
  if (!EMAIL_RE.test(val)) {
    setFieldError('email', 'Please enter a valid email address.');
    return false;
  }
  return true;
}

/* ─────────────────────────────────────────────────────────────
   SENT VIEW — swap form out, show confirmation panel
───────────────────────────────────────────────────────────────*/
function showSentView (email) {
  // Hide form, show confirmation
  document.getElementById('fpFormView').classList.add('hidden');

  const sentView = document.getElementById('fpSentView');
  sentView.classList.remove('hidden');

  // Inject the submitted email into the message
  const strongEl = sentView.querySelector('#fpSentEmail strong');
  if (strongEl) strongEl.textContent = email;
}

/* ─────────────────────────────────────────────────────────────
   RESEND COOLDOWN — 60-second countdown, prevents spam
───────────────────────────────────────────────────────────────*/
let resendCooldownTimer = null;

function startResendCooldown () {
  const btn       = document.getElementById('fpResendBtn');
  const countdown = document.getElementById('fpResendCooldown');
  const SECONDS   = 60;
  let remaining   = SECONDS;

  btn.disabled = true;
  countdown.classList.remove('hidden');

  function tick () {
    countdown.textContent = `You can resend in ${remaining}s`;
    if (remaining <= 0) {
      clearInterval(resendCooldownTimer);
      btn.disabled = false;
      countdown.classList.add('hidden');
      countdown.textContent = '';
      return;
    }
    remaining--;
  }

  tick(); // run immediately so there's no 1-second blank
  resendCooldownTimer = setInterval(tick, 1000);
}

/* ─────────────────────────────────────────────────────────────
   CORE SUBMIT — shared by both the form submit and resend button
───────────────────────────────────────────────────────────────*/
async function sendResetRequest (email, { isResend = false } = {}) {
  const btn = isResend
    ? document.getElementById('fpResendBtn')
    : document.getElementById('btnForgot');

  btn.classList.add('loading');
  btn.disabled = true;
  hideStatus();

  // Build FormData manually for resend (form may be hidden by then)
  const fd = new FormData();
  fd.append('email', email);

  // Grab CSRF token from the hidden input (still in DOM even when form is hidden)
  const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
  if (csrfInput) fd.append('csrfmiddlewaretoken', csrfInput.value);

  try {
    const response = await fetch(window.FORGOT_PASSWORD_URL, {
      method : 'POST',
      body   : fd,
      headers: {
        'X-CSRFToken': csrfInput ? csrfInput.value : '',
      },
    });

    if (response.ok || response.status === 200 || response.status === 201) {
      if (isResend) {
        // Stay on sent view, just show a brief success note + restart cooldown
        showStatus('Reset email resent successfully.', 'success');
        startResendCooldown();
      } else {
        showSentView(email);
        startResendCooldown();
      }

    } else if (response.status === 400 || response.status === 404 || response.status === 422) {
      let data = {};
      try { data = await response.json(); } catch { /* ignore non-JSON */ }

      if (data.errors && typeof data.errors === 'object') {
        Object.entries(data.errors).forEach(([field, msgs]) => {
          const msg = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
          // If form view is visible, show inline; otherwise show banner
          if (!document.getElementById('fpFormView').classList.contains('hidden')) {
            setFieldError(field, msg);
          } else {
            showStatus(msg, 'error');
          }
        });
      } else {
        const msg = data.error || data.message || data.detail
          || 'We could not find an account with that email address.';
        showStatus(msg, 'error');
      }

      // If form was hidden (resend), scroll status into view
      if (isResend) {
        document.getElementById('loginStatus').scrollIntoView({ behavior: 'smooth', block: 'center' });
      }

    } else {
      showStatus(`Server error (${response.status}). Please try again.`, 'error');
    }

  } catch (networkErr) {
    showStatus('Network error. Check your connection and try again.', 'error');
    console.error('[ForgotPassword] fetch error:', networkErr);

  } finally {
    btn.classList.remove('loading');
    // Re-enable the form submit btn only (resend has its own cooldown)
    if (!isResend) btn.disabled = false;
  }
}

/* ─────────────────────────────────────────────────────────────
   FORM SUBMIT HANDLER
───────────────────────────────────────────────────────────────*/
async function handleForgotSubmit (e) {
  e.preventDefault();
  clearFieldError('email');
  hideStatus();

  if (!validateEmail()) return;

  const email = document.getElementById('id_email').value.trim();
  await sendResetRequest(email, { isResend: false });
}

/* ─────────────────────────────────────────────────────────────
   RESEND BUTTON HANDLER
───────────────────────────────────────────────────────────────*/
async function handleResend () {
  // Re-use the last submitted email stored in the sent view
  const strongEl = document.querySelector('#fpSentEmail strong');
  const email    = strongEl ? strongEl.textContent.trim() : '';
  if (!email) return;
  await sendResetRequest(email, { isResend: true });
}

/* ─────────────────────────────────────────────────────────────
   LINK WIRING — set hrefs from injected window.* URLs
───────────────────────────────────────────────────────────────*/
function initLinks () {
  const backToLogin  = document.getElementById('backToLogin');
  const sentBackBtn  = document.getElementById('fpSentBackBtn');
  const registerLink = document.getElementById('registerLink');

  if (backToLogin  && window.LOGIN_URL)    backToLogin.href    = window.LOGIN_URL;
  if (sentBackBtn  && window.LOGIN_URL)    sentBackBtn.href    = window.LOGIN_URL;
  if (registerLink && window.REGISTER_URL) registerLink.href   = window.REGISTER_URL;
}

/* ─────────────────────────────────────────────────────────────
   BOOT
───────────────────────────────────────────────────────────────*/
function init () {
  // 1. Theme — must run first to avoid flash
  applyStoredTheme();

  // 2. Theme toggle
  const themeBtn = document.getElementById('themeToggle');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

  // 3. Video panel
  initVideo();

  // 4. Form submission
  const form = document.getElementById('forgotPasswordForm');
  if (form) form.addEventListener('submit', handleForgotSubmit);

  // 5. Clear field error on input
  const emailInput = document.getElementById('id_email');
  if (emailInput) emailInput.addEventListener('input', () => clearFieldError('email'));

  // 6. Resend button
  const resendBtn = document.getElementById('fpResendBtn');
  if (resendBtn) resendBtn.addEventListener('click', handleResend);

  // 7. Link hrefs
  initLinks();
}

// Run after DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}