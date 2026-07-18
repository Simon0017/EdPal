/**
 * settings.js
 *
 * DOM contracts:
 *   #attempt-data            — json_script block with server data (falls back to #attempt-data-fallback)
 *   #stpTabList / #stp-tab-* — sidebar tab buttons (role="tab")
 *   #stp-panel-*             — tab panels (role="tabpanel")
 *   #stpExtraTabList / #stpExtraPanelList — extension points, see Settings.registerTab()
 *
 * Extending with new tabs (no edits to this file required):
 *
 *   Settings.registerTab({
 *     id: 'billing',
 *     title: 'Billing',
 *     icon: '<svg ...></svg>',      // optional, raw SVG string
 *     render: () => '<p>Billing content…</p>',
 *     init: (panelEl) => { ... }    // optional, runs once after render
 *   });
 */

'use strict';

/* ── CSRF helper ── */
function getCookie(name) {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
  return match ? decodeURIComponent(match[2]) : null;
}

function csrfToken() {
  return (
    getCookie('csrftoken') ||
    (document.querySelector('#settingsCsrfForm input[name="csrfmiddlewaretoken"]') || {}).value ||
    ''
  );
}

let settingsCommands = {
  rememberMe: "remember-me",
  deleteSession:"delete-session",
  changePassword: "change-password",
  notifications: "notifications",
  logout: "logout",
  deleteAccount: "delete-account",
}

async function apiFetch(url, options = {}) {
  const headers = Object.assign(
    { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' },
    options.headers || {},
  );
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(url, Object.assign({}, options, { headers }));
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch (_) { /* empty body */ }
  if (!res.ok) {
    const err = new Error((data && data.error) || `Request failed (${res.status})`);
    err.data = data;
    err.status = res.status;
    throw err;
  }
  return data;
}

/* ── Toasts ── */
function showToast(message, type = 'success') {
  const stack = document.getElementById('stpToastStack');
  if (!stack) return;
  const el = document.createElement('div');
  el.className = `stp-toast stp-toast--${type}`;
  el.setAttribute('role', type === 'error' ? 'alert' : 'status');
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

/* ── Hydrate window.DATA ── */
function loadData() {
  const primary  = document.getElementById('attempt-data');
  const fallback = document.getElementById('attempt-data-fallback');
  const source   = (primary && primary.textContent.trim()) ? primary : fallback;

  try {
    window.DATA = JSON.parse(source.textContent);
  } catch (_) {
    window.DATA = { user: {}, settings: { sessions: [], notifications: {} } };
  }
  return window.DATA;
}

/* ── Tabs / panels (extensible registry) ── */
const Settings = {
  _tabs: [],

  registerTab(tab) {
    this._tabs.push(tab);
    this._renderExtraTab(tab);
  },

  _renderExtraTab(tab) {
    const tabList   = document.getElementById('stpExtraTabList');
    const panelList = document.getElementById('stpExtraPanelList');
    if (!tabList || !panelList) return;

    const li = document.createElement('li');
    li.setAttribute('role', 'none');
    li.innerHTML = `
      <button class="stp-tab" id="stp-tab-${tab.id}" role="tab"
              aria-selected="false" aria-controls="stp-panel-${tab.id}" data-tab="${tab.id}" type="button">
        ${tab.icon ? `<span class="stp-tab__icon" aria-hidden="true">${tab.icon}</span>` : ''}
        <span>${tab.title}</span>
      </button>
    `;
    tabList.appendChild(li);

    const panel = document.createElement('section');
    panel.className = 'stp-panel';
    panel.id = `stp-panel-${tab.id}`;
    panel.setAttribute('role', 'tabpanel');
    panel.setAttribute('aria-labelledby', `stp-tab-${tab.id}`);
    panel.setAttribute('tabindex', '0');
    panel.hidden = true;
    panel.innerHTML = tab.render ? tab.render() : '';
    panelList.appendChild(panel);

    li.querySelector('.stp-tab').addEventListener('click', () => activateTab(tab.id));

    if (tab.init) tab.init(panel);
  },
};
window.Settings = Settings;

/* ── Tab activation ── */
function activateTab(id) {
  document.querySelectorAll('.stp-tab').forEach(btn => {
    const active = btn.dataset.tab === id;
    btn.classList.toggle('stp-tab--active', active);
    btn.setAttribute('aria-selected', String(active));
  });

  document.querySelectorAll('.stp-panel').forEach(panel => {
    const active = panel.id === `stp-panel-${id}`;
    panel.hidden = !active;
    if (active) panel.focus({ preventScroll: true });
  });

  if (history.replaceState) history.replaceState(null, '', `#${id}`);
}

function initTabs() {
  document.querySelectorAll('.stp-tab').forEach(btn => {
    btn.addEventListener('click', () => activateTab(btn.dataset.tab));
  });

  // Keyboard navigation: arrow keys move focus between tabs
  const tabList = document.getElementById('stpTabList');
  tabList?.addEventListener('keydown', e => {
    const tabs = Array.from(document.querySelectorAll('.stp-tab'));
    const idx  = tabs.indexOf(document.activeElement);
    if (idx === -1) return;

    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') {
      e.preventDefault();
      tabs[(idx + 1) % tabs.length].focus();
    } else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
      e.preventDefault();
      tabs[(idx - 1 + tabs.length) % tabs.length].focus();
    }
  });

  // Hash-based deep link on load
  const hash = window.location.hash.replace('#', '');
  if (hash && document.getElementById(`stp-panel-${hash}`)) {
    activateTab(hash);
  }
}

/* ── General: theme ── */
function initTheme(data) {
  const lightBtn = document.getElementById('stpThemeLight');
  const darkBtn  = document.getElementById('stpThemeDark');
  if (!lightBtn || !darkBtn) return;

  function reflect() {
    const isDark = document.documentElement.classList.contains('theme-dark');
    lightBtn.setAttribute('aria-checked', String(!isDark));
    darkBtn.setAttribute('aria-checked', String(isDark));
  }

  function setTheme(theme) {
    const isDark = theme === 'dark';
    document.documentElement.classList.toggle('theme-dark', isDark);
    localStorage.setItem('reg_theme', isDark ? 'dark' : 'light');
    data.settings.theme = theme;
    reflect();
  }

  lightBtn.addEventListener('click', () => setTheme('light'));
  darkBtn.addEventListener('click', () => setTheme('dark'));

  reflect();
}

/* ── General: remember me ── */
function initRememberMe(data) {
  const input = document.getElementById('stpRememberMe');
  if (!input) return;

  input.checked = !!data.settings.remember_me;

  input.addEventListener('change', async () => {
    const value = input.checked;
    try {
      await apiFetch(window.location.pathname, {
        method: 'POST',
        body: JSON.stringify({ remember_me: value,command:settingsCommands.rememberMe }),
      });
      data.settings.remember_me = value;
      showToast('Preference saved.');
    } catch (err) {
      input.checked = !value; // revert on failure
      showToast(err.message || 'Could not save preference.', 'error');
    }
  });
}

/* ── Security: change password ── */
function initPasswordForm() {
  const form = document.getElementById('stpPasswordForm');
  if (!form) return;

  const fields = {
    current: document.getElementById('stpCurrentPassword'),
    next:    document.getElementById('stpNewPassword'),
    confirm: document.getElementById('stpConfirmPassword'),
  };
  const errors = {
    current: document.getElementById('stpCurrentPasswordError'),
    next:    document.getElementById('stpNewPasswordError'),
    confirm: document.getElementById('stpConfirmPasswordError'),
  };
  const status = document.getElementById('stpPasswordStatus');
  const submitBtn = document.getElementById('stpPasswordSubmit');

  function clearErrors() {
    Object.values(errors).forEach(el => { el.textContent = ''; });
    status.textContent = '';
    status.className = 'stp-form__status';
  }

  form.addEventListener('submit', async e => {
    e.preventDefault(); // AJAX path; form still works without JS via normal submit
    clearErrors();

    if (fields.next.value !== fields.confirm.value) {
      errors.confirm.textContent = 'Passwords do not match.';
      return;
    }

    submitBtn.disabled = true;
    try {
      await apiFetch(window.location.pathname, {
        method: 'POST',
        body: JSON.stringify({
          current_password: fields.current.value,
          new_password: fields.next.value,
          command:settingsCommands.changePassword,
        }),
      });
      status.textContent = 'Password updated successfully.';
      status.className = 'stp-form__status stp-form__status--success';
      form.reset();
      showToast('Password updated.');
    } catch (err) {
      const fieldErrors = (err.data && err.data.errors) || {};
      if (fieldErrors.current_password) errors.current.textContent = fieldErrors.current_password;
      if (fieldErrors.new_password)     errors.next.textContent = fieldErrors.new_password;
      if (!Object.keys(fieldErrors).length) {
        status.textContent = err.message || 'Could not update password.';
        status.className = 'stp-form__status stp-form__status--error';
      }
    } finally {
      submitBtn.disabled = false;
    }
  });
}

/* ── Sessions ── */
function renderSessions(data) {
  const list = document.getElementById('stpSessionList');
  if (!list) return;

  list.innerHTML = '';
  const sessions = data.settings.sessions || [];

  if (!sessions.length) {
    list.innerHTML = '<li style="font-size:0.85rem;opacity:0.5;">No active sessions found.</li>';
    return;
  }

  sessions.forEach(s => {
    const li = document.createElement('li');
    li.className = 'stp-session-item';
    li.dataset.sessionId = s.id;

    const expires = s.expires
      ? new Date(s.expires).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
      : '';

    li.innerHTML = `
      <div>
        <div class="stp-session-item__device">
          ${escHtml(s.device)} ${s.current ? '<span class="stp-chip">This device</span>' : ''}
        </div>
        <div class="stp-session-item__meta">${expires ? `Expires ${expires}` : ''}</div>
      </div>
      ${s.current ? '' : `<button class="stp-session-item__end" data-session-id="${s.id}" type="button">End session</button>`}
    `;
    list.appendChild(li);
  });

  list.querySelectorAll('.stp-session-item__end').forEach(btn => {
    btn.addEventListener('click', () => endSession(btn.dataset.sessionId, data));
  });
}

async function endSession(id, data) {
  try {
    await apiFetch(
      window.location.pathname, {
        method: 'DELETE',
        body: JSON.stringify({
          sessionId:id,
          command:settingsCommands.deleteSession
        }),
      }
    );
    data.settings.sessions = data.settings.sessions.filter(s => s.id !== id);
    renderSessions(data);
    showToast('Session ended.');
  } catch (err) {
    showToast(err.message || 'Could not end session.', 'error');
  }
}

/* ── Notifications ── */
function initNotifications(data) {
  const map = {
    email: document.getElementById('stpNotifyEmail'),
    sms:   document.getElementById('stpNotifySms'),
    push:  document.getElementById('stpNotifyPush'),
  };

  Object.entries(map).forEach(([key, input]) => {
    if (!input) return;
    input.checked = !!data.settings.notifications[key];

    input.addEventListener('change', async () => {
      const updated = Object.assign({}, data.settings.notifications, { [key]: input.checked });
      try {
        await apiFetch(window.location.pathname, {
          method: 'POST',
          body: JSON.stringify({ notifications: updated,command:settingsCommands.notifications }),
        });
        data.settings.notifications = updated;
        showToast('Notification preference saved.');
      } catch (err) {
        input.checked = !input.checked; // revert
        showToast(err.message || 'Could not save preference.', 'error');
      }
    });
  });
}

/* ── Logout ── */
function initLogout() {
  const form = document.getElementById('stpLogoutForm');
  if (!form) return;

  form.addEventListener('submit', async e => {
    e.preventDefault(); // AJAX path; falls back to real submit without JS
    try {
      await apiFetch(
        window.location.pathname, {
        method: 'POST',
        body: JSON.stringify({
          command:settingsCommands.logout,
        }),
      }
      );
      window.location.href = '/';
    } catch (err) {
      showToast(err.message || 'Could not log out.', 'error');
    }
  });
}

/* ── Delete account (focus-trapped modal) ── */
function initDeleteAccount(data) {
  const trigger     = document.getElementById('stpDeleteTrigger');
  const backdrop     = document.getElementById('stpDeleteBackdrop');
  const closeBtn      = document.getElementById('stpDeleteClose');
  const cancelBtn     = document.getElementById('stpDeleteCancel');
  const confirmInput  = document.getElementById('stpDeleteConfirmInput');
  const confirmBtn    = document.getElementById('stpDeleteConfirm');
  const usernameLabel = document.getElementById('stpDeleteUsername');
  const form          = document.getElementById('stpDeleteForm');
  const status        = document.getElementById('stpDeleteStatus');

  if (!trigger || !backdrop) return;

  const username = (data.user && data.user.username) || '';
  usernameLabel.textContent = username;

  function openModal() {
    backdrop.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    confirmInput.value = '';
    confirmBtn.disabled = true;
    status.textContent = '';
    requestAnimationFrame(() => confirmInput.focus());
  }

  function closeModal() {
    backdrop.classList.add('hidden');
    document.body.style.overflow = '';
    trigger.focus();
  }

  trigger.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  cancelBtn.addEventListener('click', closeModal);

  backdrop.addEventListener('click', e => { if (e.target === backdrop) closeModal(); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !backdrop.classList.contains('hidden')) closeModal();
  });

  confirmInput.addEventListener('input', () => {
    confirmBtn.disabled = confirmInput.value.trim() !== username;
  });

  // Focus trap inside modal
  backdrop.addEventListener('keydown', e => {
    if (e.key !== 'Tab') return;
    const focusable = Array.from(backdrop.querySelectorAll('button, input, [tabindex]:not([tabindex="-1"])'))
      .filter(el => !el.disabled);
    const first = focusable[0];
    const last  = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  form.addEventListener('submit', async e => {
    e.preventDefault(); // AJAX path; falls back to real submit without JS
    if (confirmInput.value.trim() !== username) return;

    confirmBtn.disabled = true;
    try {
      await apiFetch(window.location.pathname, {
        method: 'POST',
        body: JSON.stringify({ confirm_username: confirmInput.value.trim(),command:settingsCommands.deleteAccount }),
      });
      window.location.href = '/';
    } catch (err) {
      status.textContent = err.message || 'Could not delete account.';
      confirmBtn.disabled = false;
    }
  });
}

/* ── Helpers ── */
function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

/* ── Boot ── */
function init() {
  const data = loadData();

  initTabs();
  initTheme(data);
  initRememberMe(data);
  initPasswordForm();
  renderSessions(data);
  initNotifications(data);
  initLogout();
  initDeleteAccount(data);

  // Example of registering an additional tab from elsewhere in the codebase:
  // Settings.registerTab({
  //   id: 'integrations',
  //   title: 'Integrations',
  //   render: () => '<h2 class="stp-panel__title">Integrations</h2><p class="stp-panel__sub">Coming soon.</p>',
  // });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}