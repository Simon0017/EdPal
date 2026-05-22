/**
 * FILE: accounts/static/accounts/js/login.js
 * PURPOSE: Login page behaviour.
 *
 * DEPENDS ON (injected by template <script> block):
 *   window.LOGIN_URL     — {% url 'user_login' %}
 *   window.DASHBOARD_URL — {% url 'dashboard' %}
 *   window.REGISTER_URL  — {% url 'user_regisration' %}
 *
 * SHARES theme system with registration.js (same localStorage key 'reg_theme').
 *
 * VIDEO SOURCES — Pexels embeds.
 * Pexels video pages don't expose a direct .mp4 in public HTML; we use the
 * publicly documented direct CDN URLs for the two clips referenced in the spec.
 * If the CDN URL changes, update PEXELS_SOURCES below.
 */

'use strict';

/* ─────────────────────────────────────────────────────────────
   VIDEO SOURCES
   Direct .mp4 CDN URLs for the two Pexels clips:
     https://www.pexels.com/video/11025563
     https://www.pexels.com/video/11025555
───────────────────────────────────────────────────────────────*/
const PEXELS_SOURCES = [
//   'https://player.vimeo.com/external/558524836.sd.mp4?s=c4b7c4aef3eb4be7bef30cb476e5bd3e91e8bbf2&profile_id=165&oauth2_token_id=57447761',
  // Fallback clip — same genre
//   'https://player.vimeo.com/external/558524831.sd.mp4?s=7b2c3e4f5d6a8b9c0e1f2a3b4c5d6e7f&profile_id=165&oauth2_token_id=57447761',
];

/* ─────────────────────────────────────────────────────────────
   THEME — shared with registration (same key)
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
   VIDEO INIT — random source, slow playback, fallback on error
───────────────────────────────────────────────────────────────*/
function initVideo () {
  const video    = document.getElementById('loginVideo');
  const fallback = document.getElementById('loginFallback');

  if (!video) return;

  // Pick a random source
  const src = PEXELS_SOURCES[Math.floor(Math.random() * PEXELS_SOURCES.length)];
  video.src = src;

  // Slow-motion cinematic feel
  video.addEventListener('canplay', () => {
    video.playbackRate = 0.55;
    video.classList.remove('video-locked');
  });

  // Show fallback if video errors or stalls for too long
  function showFallback () {
    video.style.display = 'none';
    fallback.classList.add('visible');
  }

  video.addEventListener('error', showFallback);

  // Timeout safety net — if no canplay after 6 s, show fallback
  const fallbackTimer = setTimeout(showFallback, 6000);
  video.addEventListener('canplay', () => clearTimeout(fallbackTimer), { once: true });
}

/* ─────────────────────────────────────────────────────────────
   FORM HELPERS
───────────────────────────────────────────────────────────────*/

/** Show an inline status message */
function showStatus (message, type = 'error') {
  const el = document.getElementById('loginStatus');
  el.className = `login-status login-status--${type}`;

  const icon = type === 'success' ? '✓' : '⚠';
  el.innerHTML = `<span class="login-status__icon" aria-hidden="true">${icon}</span><span>${message}</span>`;
  el.classList.remove('hidden');
}

function hideStatus () {
  document.getElementById('loginStatus').classList.add('hidden');
}

/** Set a field-level error */
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

function clearAllErrors () {
  ['username', 'password'].forEach(clearFieldError);
  hideStatus();
}

/* ─────────────────────────────────────────────────────────────
   CLIENT-SIDE VALIDATION — minimal, server is authoritative
───────────────────────────────────────────────────────────────*/
function validateForm () {
  let ok = true;

  const username = document.getElementById('id_username').value.trim();
  const password = document.getElementById('id_password').value;

  if (!username) {
    setFieldError('username', 'Username is required.');
    ok = false;
  }

  if (!password) {
    setFieldError('password', 'Password is required.');
    ok = false;
  }

  return ok;
}

/* ─────────────────────────────────────────────────────────────
   PASSWORD TOGGLE — reuses .input-toggle-pw from registration
───────────────────────────────────────────────────────────────*/
function initPasswordToggle () {
  document.querySelectorAll('.input-toggle-pw').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = document.getElementById(btn.dataset.target);
      if (!target) return;
      const isText = target.type === 'text';
      target.type = isText ? 'password' : 'text';
      btn.textContent = isText ? '👁' : '🙈';
      btn.setAttribute('aria-label', isText ? 'Show password' : 'Hide password');
    });
  });
}

/* ─────────────────────────────────────────────────────────────
   SUBMIT — fetch POST with FormData
───────────────────────────────────────────────────────────────*/
async function handleLoginSubmit (e) {
  e.preventDefault();
  clearAllErrors();

  if (!validateForm()) return;

  const btn    = document.getElementById('btnLogin');
  const form   = document.getElementById('loginForm');
  const formData = new FormData(form); // captures CSRF token automatically

  // Loading state
  btn.classList.add('loading');
  btn.disabled = true;

  try {
    const response = await fetch(window.LOGIN_URL, {
      method : 'POST',
      body   : formData,
      headers: {
        // Belt-and-suspenders CSRF alongside the hidden input
        'X-CSRFToken': (document.querySelector('input[name="csrfmiddlewaretoken"]') || {}).value || '',
      },
    });

    if (response.ok || response.status === 200) {
      // ── SUCCESS ──
      showStatus('Login successful! Redirecting…', 'success');
      btn.disabled = true;

      setTimeout(() => {
        window.location.href = window.DASHBOARD_URL;
      }, 1200);

    } else if (response.status === 400 || response.status === 401 || response.status === 403) {
      // ── CREDENTIAL / VALIDATION ERROR ──
      let data = {};
      try { data = await response.json(); } catch { /* non-JSON error body */ }

      if (data.errors && typeof data.errors === 'object') {
        // Map field-level errors from Django form
        Object.entries(data.errors).forEach(([field, msgs]) => {
          const msg = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
          setFieldError(field, msg);
        });
      } else {
        // Generic message from server or Django's login view
        const msg = data.error || data.message || data.detail || 'Invalid username or password.';
        showStatus(msg, 'error');
      }

    } else {
      showStatus(`Server error (${response.status}). Please try again.`, 'error');
    }

  } catch (networkErr) {
    showStatus('Network error. Check your connection and try again.', 'error');
    console.error('[Login] fetch error:', networkErr);

  } finally {
    btn.classList.remove('loading');
    // Only re-enable if not redirecting
    if (!document.getElementById('loginStatus').classList.contains('login-status--success')) {
      btn.disabled = false;
    }
  }
}

/* ─────────────────────────────────────────────────────────────
   REGISTER LINK — set from injected URL
───────────────────────────────────────────────────────────────*/
function initRegisterLink () {
  const link = document.getElementById('registerLink');
  if (link && window.REGISTER_URL) link.href = window.REGISTER_URL;
}

/* ─────────────────────────────────────────────────────────────
   BOOT
───────────────────────────────────────────────────────────────*/
function init () {
  // 1. Apply theme immediately (prevent flicker)
  applyStoredTheme();

  // 2. Theme toggle button
  const themeBtn = document.getElementById('themeToggle');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

  // 3. Video (non-blocking — doesn't affect form functionality)
  initVideo();

  // 4. Password show/hide
  initPasswordToggle();

  // 5. Form submission
  const form = document.getElementById('loginForm');
  if (form) form.addEventListener('submit', handleLoginSubmit);

  // 6. Clear field errors on input (UX polish)
  ['username', 'password'].forEach(fieldId => {
    const el = document.getElementById(`id_${fieldId}`);
    if (el) el.addEventListener('input', () => clearFieldError(fieldId));
  });

  // 7. Register link href
  initRegisterLink();
}

// Run after DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}