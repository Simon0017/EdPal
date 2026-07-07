/**
 * profile.js
 * Reads window.DATA from #attempt-data, manages read/edit toggle,
 * avatar drag-and-drop upload, debounced subject search, Quill rich text,
 * and AJAX save to /accounts/profile/update/.
 */

'use strict';

/* ── CSRF: cookie-based (cookie name "csrftoken") ── */
function getCookie (name) {
  const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return match ? decodeURIComponent(match[2]) : null;
}
const CSRF_TOKEN = getCookie('csrftoken');

/* ── Hydrate window.DATA ── */
window.DATA = JSON.parse(document.getElementById('user-data').textContent);

let quill = null;
let selectedSubjects = []; // [{id, name}]
let isEditing = false;
let pendingAvatarFile = null;

const els = {};

function cacheEls () {
  els.profileName     = document.getElementById('profileName');
  els.profileUsername = document.getElementById('profileUsername');
  els.profileEmail    = document.getElementById('profileEmail');

  els.firstName = document.getElementById('id_first_name');
  els.lastName  = document.getElementById('id_last_name');
  els.email     = document.getElementById('id_email');
  els.dob       = document.getElementById('id_date_of_birth');

  els.btnEdit   = document.getElementById('btnEdit');
  els.btnSave   = document.getElementById('btnSave');
  els.btnCancel = document.getElementById('btnCancel');

  els.errorBanner = document.getElementById('profileError');
  els.toast        = document.getElementById('profileToast');

  els.avatarDropzone   = document.getElementById('avatarDropzone');
  els.avatarInput      = document.getElementById('avatarInput');
  els.avatarPreview    = document.getElementById('avatarPreview');
  els.avatarPlaceholder= document.getElementById('avatarPlaceholder');

  els.chipList         = document.getElementById('subjectChips');
  els.subjectSearchWrap= document.getElementById('subjectSearchWrap');
  els.subjectSearch     = document.getElementById('subjectSearch');
  els.subjectDropdown   = document.getElementById('subjectDropdown');
  els.subjectIdsInput   = document.getElementById('subjectIdsInput');
}

/* ── Render read-only state from window.DATA ── */
function renderFromData () {
  const { user, profile } = window.DATA;

  els.profileName.textContent     = `${user.first_name} ${user.last_name}`.trim() || user.username;
  els.profileUsername.textContent = `@${user.username}`;
  els.profileEmail.textContent    = user.email;

  els.firstName.value = user.first_name || '';
  els.lastName.value  = user.last_name || '';
  els.email.value     = user.email || '';
  els.dob.value        = profile.date_of_birth || '';

  if (profile.avatar_url) {
    els.avatarPreview.src = profile.avatar_url;
    els.avatarPreview.classList.remove('hidden');
    els.avatarPlaceholder.classList.add('hidden');
  } else {
    els.avatarPreview.classList.add('hidden');
    els.avatarPlaceholder.classList.remove('hidden');
  }

  selectedSubjects = (profile.subjects || []).slice();
  renderChips();

  if (quill) {
    quill.root.innerHTML = profile.about_me || '';
  }
}

/* ── Edit / read toggle ── */
function setEditing (editing) {
  isEditing = editing;

  [els.firstName, els.lastName, els.email].forEach(i => i.disabled = !editing);
  els.dob.readOnly = !editing; // readOnly keeps the native date picker icon visible/functional

  els.btnEdit.classList.toggle('hidden', editing);
  els.btnSave.classList.toggle('hidden', !editing);
  els.btnCancel.classList.toggle('hidden', !editing);

  els.subjectSearchWrap.classList.toggle('hidden', !editing);
  els.avatarDropzone.setAttribute('tabindex', editing ? '0' : '-1');

  if (quill) {
    quill.enable(editing);
    quill.container.parentElement.classList.toggle('profile-quill--disabled', !editing);
  }

  renderChips(); // refresh remove-button disabled state
  hideError();
}

/* ── Subject chips ── */
function renderChips () {
  els.chipList.innerHTML = '';
  selectedSubjects.forEach(s => {
    const chip = document.createElement('span');
    chip.className = 'profile-chip';
    chip.innerHTML = `${escapeHtml(s.name)} <button type="button" class="profile-chip__remove" aria-label="Remove ${escapeHtml(s.name)}" ${isEditing ? '' : 'disabled'}>&times;</button>`;
    chip.querySelector('button').addEventListener('click', () => {
      if (!isEditing) return;
      selectedSubjects = selectedSubjects.filter(x => x.id !== s.id);
      renderChips();
      syncSubjectHidden();
    });
    els.chipList.appendChild(chip);
  });
  syncSubjectHidden();
}

function syncSubjectHidden () {
  els.subjectIdsInput.value = JSON.stringify(selectedSubjects.map(s => s.id));
}

function escapeHtml (str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/* ── Debounced subject search ── */
function debounce (fn, wait) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn.apply(null, args), wait);
  };
}

const doSubjectSearch = debounce(async (query) => {
  if (!query || query.length < 2) {
    closeDropdown();
    return;
  }
  try {
    const res = await fetch(`${window.SEARCH_SUBJECTS_URL}?query=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error('Search failed');
    const results = await res.json();
    renderDropdown(results.message || []);
  } catch (err) {
    renderDropdown([]);
  }
}, 300);

function renderDropdown (results) {
  const filtered = results.filter(r => !selectedSubjects.some(s => s.id === r.id));
  els.subjectDropdown.innerHTML = '';

  if (!filtered.length) {
    const empty = document.createElement('div');
    empty.className = 'profile-subject-option profile-subject-option--empty';
    empty.textContent = 'No matches found.';
    els.subjectDropdown.appendChild(empty);
  } else {
    filtered.forEach(r => {
      const opt = document.createElement('div');
      opt.className = 'profile-subject-option';
      opt.setAttribute('role', 'option');
      opt.textContent = r.name;
      opt.addEventListener('mousedown', (e) => {
        e.preventDefault();
        selectedSubjects.push({ id: r.id, name: r.name });
        renderChips();
        els.subjectSearch.value = '';
        closeDropdown();
      });
      els.subjectDropdown.appendChild(opt);
    });
  }

  openDropdown();
}

function openDropdown () {
  els.subjectDropdown.classList.add('open');
  els.subjectSearch.setAttribute('aria-expanded', 'true');
}

function closeDropdown () {
  els.subjectDropdown.classList.remove('open');
  els.subjectDropdown.innerHTML = '';
  els.subjectSearch.setAttribute('aria-expanded', 'false');
}

/* ── Avatar: drag/drop + click + validation + AJAX upload ── */
function validateAvatarFile (file) {
  const allowed = ['image/jpeg', 'image/png', 'image/jpg'];
  if (!allowed.includes(file.type)) {
    showError('Please upload a JPG or PNG image.');
    return false;
  }
  if (file.size > 5 * 1024 * 1024) {
    showError('Image must be 5MB or smaller.');
    return false;
  }
  return true;
}

function previewAvatar (file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    els.avatarPreview.src = e.target.result;
    els.avatarPreview.classList.remove('hidden');
    els.avatarPlaceholder.classList.add('hidden');
  };
  reader.readAsDataURL(file);
}

async function uploadAvatar (file) {
  const formData = new FormData();
  formData.append('avatar', file);

  try {
    const res = await fetch(window.UPLOAD_AVATAR_URL, {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF_TOKEN },
      body: formData,
    });
    if (!res.ok) throw new Error('Upload failed');
    const data = await res.json();
    window.DATA.profile.avatar_url = data.avatar_url;
    showToast('Profile picture updated.', 'success');
  } catch (err) {
    showError('Could not upload image. Please try again.');
  }
}

function initAvatar () {
  els.avatarDropzone.addEventListener('click', () => {
    if (isEditing) els.avatarInput.click();
  });

  els.avatarDropzone.addEventListener('keydown', (e) => {
    if (isEditing && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      els.avatarInput.click();
    }
  });

  els.avatarInput.addEventListener('change', () => {
    const file = els.avatarInput.files[0];
    if (!file || !validateAvatarFile(file)) return;
    pendingAvatarFile = file;
    previewAvatar(file);
    uploadAvatar(file);
  });

  ['dragenter', 'dragover'].forEach(evt =>
    els.avatarDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      if (isEditing) els.avatarDropzone.classList.add('profile-avatar--dragover');
    })
  );

  ['dragleave', 'drop'].forEach(evt =>
    els.avatarDropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      els.avatarDropzone.classList.remove('profile-avatar--dragover');
    })
  );

  els.avatarDropzone.addEventListener('drop', (e) => {
    if (!isEditing) return;
    const file = e.dataTransfer.files[0];
    if (!file || !validateAvatarFile(file)) return;
    pendingAvatarFile = file;
    previewAvatar(file);
    uploadAvatar(file);
  });
}

/* ── Quill init ── */
function initQuill () {
  quill = new Quill('#aboutMeEditor', {
    theme: 'snow',
    readOnly: true,
    modules: {
      toolbar: [['bold', 'italic', 'underline'], [{ list: 'ordered' }, { list: 'bullet' }], ['clean']],
    },
  });
  quill.root.innerHTML = window.DATA.profile.about_me || '';
}

/* ── Error / toast helpers ── */
function showError (msg) {
  els.errorBanner.textContent = msg;
  els.errorBanner.classList.remove('hidden');
}
function hideError () {
  els.errorBanner.classList.add('hidden');
}

function showToast (msg, type) {
  els.toast.textContent = msg;
  els.toast.className = `profile-toast profile-toast--${type}`;
  els.toast.classList.remove('hidden');
  setTimeout(() => els.toast.classList.add('hidden'), 3500);
}

/* ── Save ── */
async function saveProfile () {
  hideError();

  const email = els.email.value.trim();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    showError('Please enter a valid email address.');
    return;
  }

  const payload = {
    first_name: els.firstName.value.trim(),
    last_name: els.lastName.value.trim(),
    email: email,
    date_of_birth: els.dob.value || null,
    about_me: quill ? quill.root.innerHTML : '',
    subject_ids: selectedSubjects.map(s => s.id),
  };

  els.btnSave.disabled = true;
  els.btnSave.textContent = 'Saving…';

  
  try {
    const res = await fetch(window.location.pathname, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF_TOKEN,
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Failed to save profile.');
    }

    const updated = await res.json();

    // Sync local + server state
    window.DATA.user.first_name = payload.first_name;
    window.DATA.user.last_name  = payload.last_name;
    window.DATA.user.email      = payload.email;
    window.DATA.profile = updated.profile || {
      ...window.DATA.profile,
      date_of_birth: payload.date_of_birth,
      about_me: payload.about_me,
      subjects: selectedSubjects,
    };

    renderFromData();
    setEditing(false);
    showToast('Profile updated successfully.', 'success');

  } catch (err) {
    showError(err.message || 'Something went wrong while saving.');
  } finally {
    els.btnSave.disabled = false;
    els.btnSave.textContent = 'Save changes';
  }
}

/* ── Cancel ── */
function cancelEdit () {
  renderFromData();
  setEditing(false);
}

/* ── Keyboard support for dropdown ── */
function initSubjectSearch () {
  els.subjectSearch.addEventListener('input', () => doSubjectSearch(els.subjectSearch.value.trim()));
  els.subjectSearch.addEventListener('blur', () => setTimeout(closeDropdown, 150));
  els.subjectSearch.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDropdown();
  });
}

/* ── Boot ── */
document.addEventListener('DOMContentLoaded', () => {
  cacheEls();
  initQuill();
  initAvatar();
  initSubjectSearch();
  renderFromData();
  setEditing(false);

  els.btnEdit.addEventListener('click', () => setEditing(true));
  els.btnCancel.addEventListener('click', cancelEdit);
  els.btnSave.addEventListener('click', saveProfile);
});