/**
 * careers/explore.js
 * Handles: tab switching, search, filter chips, drawer, modal,
 *          client-side pagination, card animations.
 * Expects: window.CR_URLS, window.CR_DATA set by template.
 */

'use strict';

/* ── Utilities ── */
const $ = id => document.getElementById(id);

function debounce(fn, wait = 350) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

function trapFocus(el) {
  const focusable = Array.from(
    el.querySelectorAll('button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])')
  ).filter(e => !e.disabled);
  const first = focusable[0];
  const last  = focusable[focusable.length - 1];

  el.addEventListener('keydown', function handler(e) {
    if (e.key !== 'Tab') return;
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
  });
}

/* ── State ── */
const state = {
  activeTab:  'careers',
  search:     '',
  sector:     '',
  qual:       '',
  country:    '',
  pages: { careers: 1, courses: 1, institutions: 1 },
};

const PAGE_SIZE = { careers: 9, courses: 12, institutions: 9 };

/* ─────────────────────────────────────────────
   TABS
───────────────────────────────────────────── */
function initTabs() {
  const tabs = document.querySelectorAll('.cr-tab[data-tab]');

  tabs.forEach(btn => {
    btn.addEventListener('click', () => activateTab(btn.dataset.tab));
  });

  // Arrow-key navigation
  $('crExploreTabs')?.addEventListener('keydown', e => {
    const all = Array.from(tabs);
    const idx = all.indexOf(document.activeElement);
    if (idx === -1) return;
    if (e.key === 'ArrowRight') { e.preventDefault(); all[(idx + 1) % all.length].focus(); }
    if (e.key === 'ArrowLeft')  { e.preventDefault(); all[(idx - 1 + all.length) % all.length].focus(); }
  });

  // Hash deep-link
  const hash = location.hash.replace('#', '');
  if (['careers', 'courses', 'institutions'].includes(hash)) activateTab(hash);
}

function activateTab(tab) {
  state.activeTab = tab;
  state.pages[tab] = 1;

  document.querySelectorAll('.cr-tab[data-tab]').forEach(btn => {
    const active = btn.dataset.tab === tab;
    btn.classList.toggle('cr-tab--active', active);
    btn.setAttribute('aria-selected', String(active));
  });

  ['careers', 'courses', 'institutions'].forEach(id => {
    const panel = $(`cr-panel-${id}`);
    if (!panel) return;
    panel.hidden = id !== tab;
  });

  history.replaceState(null, '', `#${tab}`);
  renderActiveTab();
}

/* ─────────────────────────────────────────────
   RENDERING — client-side filter + paginate
───────────────────────────────────────────── */
function renderActiveTab() {
  switch (state.activeTab) {
    case 'careers':      renderCareers(); break;
    case 'courses':      renderCourses(); break;
    case 'institutions': renderInstitutions(); break;
  }
}

/* Careers */
function renderCareers() {
  const data = filterCareers();
  paginate('crCareersGrid', 'crCareersPagination', 'crCareersEmpty', data,
    PAGE_SIZE.careers, state.pages.careers, career => careerCardHtml(career));
}

function filterCareers() {
  const q  = state.search.toLowerCase();
  const sec = state.sector;
  return (window.CR_DATA.careers || []).filter(c =>
    (!q   || c.title.toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q)) &&
    (!sec || c.sector === sec)
  );
}

function careerCardHtml(c) {
  return `
    <a href="${window.CR_URLS.careerDetail}${escHtml(c.slug)}/"
       class="cr-card"
       aria-label="${escHtml(c.title)}">
      <div class="cr-card__sector-bar" aria-hidden="true"></div>
      <div class="cr-card__icon" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="2" y="7" width="20" height="14" rx="2"/>
          <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
        </svg>
      </div>
      <h3 class="cr-card__title">${escHtml(c.title)}</h3>
      ${c.description ? `<p class="cr-card__desc">${escHtml(c.description)}</p>` : ''}
      <div class="cr-card__meta">
        <span class="cr-badge cr-badge--muted">${escHtml(c.sector || '')}</span>
        ${c.course_count ? `<span class="cr-badge cr-badge--info">${c.course_count} course${c.course_count !== 1 ? 's' : ''}</span>` : ''}
      </div>
    </a>`;
}

/* Courses */
function renderCourses() {
  const data = filterCourses();
  paginate('crCoursesGrid', 'crCoursesPagination', 'crCoursesEmpty', data,
    PAGE_SIZE.courses, state.pages.courses, course => courseCardHtml(course));
}

function filterCourses() {
  const q   = state.search.toLowerCase();
  const qual = state.qual;
  return (window.CR_DATA.courses || []).filter(c =>
    (!q    || c.title.toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q)) &&
    (!qual || c.qualification === qual)
  );
}

function courseCardHtml(c) {
  return `
    <a href="/careers/courses/${escHtml(c.slug)}/"
       class="cr-course-card"
       aria-label="${escHtml(c.title)}">
      <span class="cr-course-card__qual">${escHtml(c.qualification || '')}</span>
      <h3 class="cr-course-card__title">${escHtml(c.title)}</h3>
      <div class="cr-course-card__meta">
        ${c.duration_years ? `<span>${c.duration_years} yr${c.duration_years !== 1 ? 's' : ''}</span>` : ''}
        ${c.institution ? `<span>${escHtml(c.institution.name || '')}</span>` : ''}
      </div>
    </a>`;
}

/* Institutions */
function renderInstitutions() {
  const data = filterInstitutions();
  paginate('crInstitutionsGrid', 'crInstitutionsPagination', 'crInstitutionsEmpty', data,
    PAGE_SIZE.institutions, state.pages.institutions, inst => instCardHtml(inst));
}

function filterInstitutions() {
  const q       = state.search.toLowerCase();
  const country = state.country;
  return (window.CR_DATA.institutions || []).filter(i =>
    (!q       || i.name.toLowerCase().includes(q)) &&
    (!country || i.country === country)
  );
}

function instCardHtml(i) {
  return `
    <a href="/careers/institutions/${escHtml(i.slug)}/"
       class="cr-inst-card"
       aria-label="${escHtml(i.name)}">
      <div class="cr-inst-card__logo" aria-hidden="true">${escHtml((i.code || '').slice(0, 2).toUpperCase())}</div>
      <div>
        <p class="cr-inst-card__name">${escHtml(i.name)}</p>
        <p class="cr-inst-card__meta">
          ${escHtml(i.type || '')}
          ${i.country ? ` &middot; ${escHtml(i.country)}` : ''}
          ${i.course_count ? ` &middot; ${i.course_count} course${i.course_count !== 1 ? 's' : ''}` : ''}
        </p>
      </div>
    </a>`;
}

/* Generic paginator */
function paginate(gridId, paginationId, emptyId, data, pageSize, page, renderFn) {
  const grid       = $(gridId);
  const paginEl    = $(paginationId);
  const emptyEl    = $(emptyId);
  if (!grid) return;

  // Remove skeletons
  grid.querySelectorAll('.cr-skeleton-card').forEach(el => el.remove());

  const total     = data.length;
  const totalPages = Math.ceil(total / pageSize);
  const slice     = data.slice((page - 1) * pageSize, page * pageSize);

  if (!slice.length) {
    grid.innerHTML = '';
    if (emptyEl) emptyEl.style.display = 'flex';
    if (paginEl) paginEl.innerHTML = '';
    return;
  }

  if (emptyEl) emptyEl.style.display = 'none';
  grid.innerHTML = slice.map(renderFn).join('');

  // Stagger fade-up animation
  grid.querySelectorAll('.cr-card, .cr-course-card, .cr-inst-card').forEach((el, i) => {
    el.style.animationDelay = `${i * 0.04}s`;
    el.style.animation = 'cr-fade-up 0.35s ease both';
  });

  // Pagination controls
  if (paginEl) renderPagination(paginEl, page, totalPages, gridId);
}

function renderPagination(container, current, total, gridId) {
  if (total <= 1) { container.innerHTML = ''; return; }

  const tab = state.activeTab;
  let html  = '';

  // Prev
  html += `<button class="cr-page-btn" data-page="${current - 1}" data-grid="${gridId}"
             ${current === 1 ? 'disabled' : ''} aria-label="Previous page" type="button">
             <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
               <polyline points="15,18 9,12 15,6"/>
             </svg>
           </button>`;

  // Page buttons — show window of 5
  const start = Math.max(1, current - 2);
  const end   = Math.min(total, start + 4);
  for (let p = start; p <= end; p++) {
    html += `<button class="cr-page-btn ${p === current ? 'cr-page-btn--active' : ''}"
               data-page="${p}" data-grid="${gridId}" aria-label="Page ${p}"
               aria-current="${p === current ? 'page' : 'false'}" type="button">
               ${p}
             </button>`;
  }

  // Next
  html += `<button class="cr-page-btn" data-page="${current + 1}" data-grid="${gridId}"
             ${current === total ? 'disabled' : ''} aria-label="Next page" type="button">
             <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
               <polyline points="9,18 15,12 9,6"/>
             </svg>
           </button>`;

  container.innerHTML = html;

  container.querySelectorAll('.cr-page-btn:not(:disabled)').forEach(btn => {
    btn.addEventListener('click', () => {
      state.pages[tab] = parseInt(btn.dataset.page, 10);
      renderActiveTab();
      $(`cr-panel-${tab}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

/* ─────────────────────────────────────────────
   SEARCH
───────────────────────────────────────────── */
function initSearch() {
  const input = $('crExploreSearch');
  if (!input) return;

  input.addEventListener('input', debounce(() => {
    state.search = input.value.trim();
    state.pages[state.activeTab] = 1;
    renderActiveTab();
    updateActiveChips();
  }));

  input.addEventListener('keydown', e => {
    if (e.key === 'Escape') { input.value = ''; state.search = ''; renderActiveTab(); }
  });
}

/* ─────────────────────────────────────────────
   FILTER CHIPS (sector / qual / country)
───────────────────────────────────────────── */
function initFilterChips() {
  // Sector chips (in careers panel)
  delegateChips($('crSectorChips'), 'sector', val => {
    state.sector = val;
    state.pages.careers = 1;
    syncDrawerChip('crDrawerSector', 'sector', val);
    renderCareers();
    updateActiveChips();
  });

  // Qual chips (in courses panel)
  delegateChips($('crQualChips'), 'qual', val => {
    state.qual = val;
    state.pages.courses = 1;
    syncDrawerChip('crDrawerQual', 'qual', val);
    renderCourses();
    updateActiveChips();
  });

  // Country chips (in institutions panel)
  delegateChips($('crCountryChips'), 'country', val => {
    state.country = val;
    state.pages.institutions = 1;
    syncDrawerChip('crDrawerCountry', 'country', val);
    renderInstitutions();
    updateActiveChips();
  });

  // Clear careers filter button (empty state)
  document.addEventListener('click', e => {
    if (e.target.id === 'crClearCareerFilters') resetFilters();
  });
}

function delegateChips(container, key, onChange) {
  if (!container) return;
  container.addEventListener('click', e => {
    const btn = e.target.closest('.cr-chip');
    if (!btn) return;
    container.querySelectorAll('.cr-chip').forEach(c => c.classList.remove('cr-chip--active'));
    btn.classList.add('cr-chip--active');
    onChange(btn.dataset[key] || '');
  });
}

function syncDrawerChip(drawerId, key, value) {
  const container = $(drawerId);
  if (!container) return;
  container.querySelectorAll('.cr-chip').forEach(c => {
    c.classList.toggle('cr-chip--active', (c.dataset[key] || '') === value);
  });
}

/* Active filter chips bar */
function updateActiveChips() {
  const bar = $('crActiveChips');
  const countBadge = $('crActiveFilterCount');
  if (!bar) return;

  const active = [];
  if (state.search)  active.push({ label: `"${state.search}"`,  key: 'search' });
  if (state.sector)  active.push({ label: state.sector,          key: 'sector' });
  if (state.qual)    active.push({ label: state.qual,            key: 'qual' });
  if (state.country) active.push({ label: state.country,         key: 'country' });

  bar.innerHTML = active.map(f =>
    `<button class="cr-chip cr-chip--active" data-filter-key="${f.key}" type="button">
       ${escHtml(f.label)}
       <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="3" stroke-linecap="round" style="margin-left:4px;" aria-hidden="true">
         <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
       </svg>
     </button>`
  ).join('');

  if (countBadge) {
    countBadge.textContent = active.length;
    countBadge.style.display = active.length ? 'inline-flex' : 'none';
  }

  bar.querySelectorAll('.cr-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      clearFilter(btn.dataset.filterKey);
      renderActiveTab();
      updateActiveChips();
    });
  });
}

function clearFilter(key) {
  if (key === 'search')  { state.search = ''; const i = $('crExploreSearch'); if (i) i.value = ''; }
  if (key === 'sector')  { state.sector = '';  resetChips('crSectorChips',  'sector'); }
  if (key === 'qual')    { state.qual = '';    resetChips('crQualChips',    'qual'); }
  if (key === 'country') { state.country = ''; resetChips('crCountryChips', 'country'); }
}

function resetChips(containerId, key) {
  const c = $(containerId);
  if (!c) return;
  c.querySelectorAll('.cr-chip').forEach(ch => {
    ch.classList.toggle('cr-chip--active', (ch.dataset[key] || '') === '');
  });
}

function resetFilters() {
  ['search', 'sector', 'qual', 'country'].forEach(k => clearFilter(k));
  state.pages = { careers: 1, courses: 1, institutions: 1 };
  renderActiveTab();
  updateActiveChips();
}

/* ─────────────────────────────────────────────
   DRAWER
───────────────────────────────────────────── */
function initDrawer() {
  const filterBtn  = $('crFilterBtn');
  const backdrop   = $('crFilterDrawer-backdrop');
  const drawer     = $('crFilterDrawer');
  if (!drawer) return;

  function openDrawer() {
    backdrop?.classList.remove('hidden');
    backdrop?.removeAttribute('aria-hidden');
    drawer.classList.add('cr-drawer--open');
    drawer.removeAttribute('aria-hidden');
    filterBtn?.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
    drawer.querySelector('button, input')?.focus();
    trapFocus(drawer);
  }

  function closeDrawer() {
    backdrop?.classList.add('hidden');
    backdrop?.setAttribute('aria-hidden', 'true');
    drawer.classList.remove('cr-drawer--open');
    drawer.setAttribute('aria-hidden', 'true');
    filterBtn?.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
    filterBtn?.focus();
  }

  filterBtn?.addEventListener('click', openDrawer);
  backdrop?.addEventListener('click', closeDrawer);

  document.querySelectorAll('[data-cr-drawer-close="crFilterDrawer"]').forEach(btn => {
    btn.addEventListener('click', closeDrawer);
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && drawer.classList.contains('cr-drawer--open')) closeDrawer();
  });

  // Drawer chip interactions (populated by inline script in template)
  document.addEventListener('click', e => {
    const applyBtn = e.target.closest('#crDrawerApply');
    const resetBtn = e.target.closest('#crDrawerReset');

    if (applyBtn) {
      // Read active chips from drawer and apply
      const sectorChip  = $('crDrawerSector')?.querySelector('.cr-chip--active');
      const qualChip    = $('crDrawerQual')?.querySelector('.cr-chip--active');
      const countryChip = $('crDrawerCountry')?.querySelector('.cr-chip--active');

      state.sector  = sectorChip?.dataset.sector   || '';
      state.qual    = qualChip?.dataset.qual        || '';
      state.country = countryChip?.dataset.country  || '';

      // Sync inline chips
      syncDrawerChip('crSectorChips',  'sector',  state.sector);
      syncDrawerChip('crQualChips',    'qual',    state.qual);
      syncDrawerChip('crCountryChips', 'country', state.country);

      state.pages = { careers: 1, courses: 1, institutions: 1 };
      renderActiveTab();
      updateActiveChips();
      closeDrawer();
    }

    if (resetBtn) {
      resetFilters();
      // Reset drawer chips to "All"
      ['crDrawerSector', 'crDrawerQual', 'crDrawerCountry'].forEach(id => {
        const c = $(id);
        if (!c) return;
        c.querySelectorAll('.cr-chip').forEach((ch, i) => {
          ch.classList.toggle('cr-chip--active', i === 0);
        });
      });
    }
  });
}

/* ─────────────────────────────────────────────
   MODAL (career detail)
───────────────────────────────────────────── */
function initModal() {
  const backdrop = $('crCareerModal');
  if (!backdrop) return;

  function openModal(career) {
    $('crCareerModal-title').textContent = career.title || '';
    $('crCareerModal-sub').textContent   = career.sector || '';
    $('crCareerModal-body').innerHTML    = `
      <p style="font-size:0.87rem;opacity:0.65;line-height:1.7;margin:0 0 16px;">
        ${escHtml(career.description || 'No description available.')}
      </p>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <a href="${window.CR_URLS.careerDetail}${escHtml(career.slug)}/"
           class="btn-primary" style="font-size:0.82rem;padding:9px 18px;text-decoration:none;">
          View Full Career
        </a>
        <a href="${window.CR_URLS.careerMatch}?career=${escHtml(career.slug)}"
           class="btn-outline" style="font-size:0.82rem;padding:9px 18px;text-decoration:none;">
          Check My Match
        </a>
      </div>`;

    backdrop.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    backdrop.querySelector('.cr-modal__close')?.focus();
    trapFocus(backdrop.querySelector('.cr-modal'));
  }

  function closeModal() {
    backdrop.classList.add('hidden');
    document.body.style.overflow = '';
  }

  backdrop.addEventListener('click', e => { if (e.target === backdrop) closeModal(); });

  backdrop.querySelectorAll('[data-cr-modal-close]').forEach(btn => {
    btn.addEventListener('click', closeModal);
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !backdrop.classList.contains('hidden')) closeModal();
  });

  // Open modal on career card click
  document.addEventListener('click', e => {
    const card = e.target.closest('#crCareersGrid .cr-card');
    if (!card) return;
    const slug   = card.href?.split('/').filter(Boolean).pop();
    const career = (window.CR_DATA.careers || []).find(c => c.slug === slug);
    if (career) { e.preventDefault(); openModal(career); }
  });
}

/* ─────────────────────────────────────────────
   BOOT
───────────────────────────────────────────── */
function init() {
  initTabs();
  initSearch();
  initFilterChips();
  initDrawer();
  initModal();

  // Initial render from CR_DATA
  renderActiveTab();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
