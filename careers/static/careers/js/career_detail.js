/**
 * careers/career_detail.js
 *
 * Shared behaviour for career_detail, course_detail, and institution_detail pages.
 *
 * Responsibilities:
 *   - Animate score rings (career_detail, course_detail)
 *   - Cutoff trend indicators (reuses logic from career_match.js)
 *   - "Show more" toggle for institution sidebar lists
 *   - Institution detail: client-side course search and chip filtering
 *   - Course detail: quick eligibility check
 *   - Smooth scroll for in-page anchor links
 */

'use strict';

const $ = id => document.getElementById(id);

function debounce(fn, wait = 300) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

/* ─────────────────────────────────────────────
   SCORE RING ANIMATION
   Shared between career_detail and course_detail.
   Looks for crDetailRingFill or crCourseRingFill.
───────────────────────────────────────────── */
function initRing() {
  const cfg = window.CR_DETAIL || {};
  const pct = cfg.matchPct;
  if (pct == null) return;

  const CIRCUM  = 339.29;
  const fillIds = ['crDetailRingFill', 'crCourseRingFill'];
  const valIds  = ['crDetailRingValue', 'crCourseRingValue'];

  fillIds.forEach((fillId, i) => {
    const fill  = $(fillId);
    const label = $(valIds[i]);
    if (!fill) return;

    requestAnimationFrame(() => {
      fill.style.strokeDashoffset = String(CIRCUM - (pct / 100) * CIRCUM);
    });

    if (!label) return;
    const start    = performance.now();
    const duration = 1100;
    function count(now) {
      const p = Math.min((now - start) / duration, 1);
      label.textContent = Math.round((1 - Math.pow(1 - p, 3)) * pct) + '%';
      if (p < 1) requestAnimationFrame(count);
    }
    requestAnimationFrame(count);
  });
}

/* ─────────────────────────────────────────────
   CUTOFF TREND INDICATORS
   Adds ↑ / ↓ / → to .cr-cutoff-trend spans.
   Works on any detail page that includes the cutoff_table partial.
───────────────────────────────────────────── */
function initCutoffTrends() {
  const rows = document.querySelectorAll('table .cr-cutoff-trend');
  if (rows.length < 2) return;

  // Read points from the sibling <strong> in the same row
  const points = Array.from(rows).map(span => {
    const cell = span.closest('td');
    const prev = cell?.previousElementSibling;
    return parseInt(prev?.querySelector('strong')?.textContent || '0', 10);
  });

  rows.forEach((span, i) => {
    if (i === rows.length - 1) return; // no previous for last row
    const diff = points[i] - points[i + 1];
    if (diff > 0)      { span.textContent = '↑'; span.style.color = '#a3e635'; span.title = `+${diff}`; }
    else if (diff < 0) { span.textContent = '↓'; span.style.color = '#f87171'; span.title = String(diff); }
    else               { span.textContent = '→'; span.title = 'Unchanged'; }
  });
}

/* ─────────────────────────────────────────────
   SHOW MORE INSTITUTIONS (career_detail sidebar)
───────────────────────────────────────────── */
function initShowMoreInst() {
  const btn      = $('crShowMoreInst');
  const extraDiv = $('crExtraInst');
  if (!btn || !extraDiv) return;

  btn.addEventListener('click', () => {
    const hidden = extraDiv.hidden;
    extraDiv.hidden = !hidden;
    btn.textContent = hidden ? 'Show less' : btn.dataset.originalLabel || 'Show more';
    if (hidden) btn.dataset.originalLabel = btn.textContent;
  });
}

/* ─────────────────────────────────────────────
   COURSE DETAIL — quick eligibility check
───────────────────────────────────────────── */
function initCourseEligibility() {
  const checkBtn = $('crCheckCourseElig');
  const input    = $('crCoursePoints');
  const result   = $('crCourseEligResult');
  if (!checkBtn || !input || !result) return;

  const latestCutoff = window.CR_DETAIL?.latestCutoff ?? null;

  checkBtn.addEventListener('click', () => {
    const pts = parseInt(input.value || '0', 10);
    result.classList.add('cr-eligibility__result--show');

    if (latestCutoff == null) {
      result.className = 'cr-eligibility__result cr-eligibility__result--show cr-eligibility__result--pass';
      result.textContent = 'No cutoff data available for this course. Contact the institution directly.';
      return;
    }

    if (pts >= latestCutoff) {
      result.className = 'cr-eligibility__result cr-eligibility__result--show cr-eligibility__result--pass';
      result.textContent = `Your ${pts} pts meet the ${latestCutoff} pt cutoff. You appear eligible.`;
    } else {
      result.className = 'cr-eligibility__result cr-eligibility__result--show cr-eligibility__result--fail';
      result.textContent = `Your ${pts} pts are below the ${latestCutoff} pt cutoff.`;
    }
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') checkBtn.click();
  });
}

/* ─────────────────────────────────────────────
   INSTITUTION DETAIL — client-side course filtering
   Reads from window.CR_INST.courses (JSON from view).
───────────────────────────────────────────── */
function initInstCourseFilter() {
  const grid     = $('crInstCoursesGrid');
  const empty    = $('crInstCoursesEmpty');
  const clearBtn = $('crInstClearFilters');
  if (!grid) return;

  const allCourses = window.CR_INST?.courses || [];
  if (!allCourses.length) return; // server-rendered content — don't interfere

  const state = { search: '', qual: '', sector: '' };

  function render() {
    const q      = state.search.toLowerCase();
    const qual   = state.qual;
    const sector = state.sector;

    const filtered = allCourses.filter(c =>
      (!q      || c.title.toLowerCase().includes(q)) &&
      (!qual   || c.qualification === qual) &&
      (!sector || (c.career_sector || '') === sector)
    );

    grid.innerHTML = filtered.length
      ? filtered.map(c => courseCardHtml(c)).join('')
      : '';

    if (empty) empty.classList.toggle('hidden', filtered.length > 0);
  }

  function courseCardHtml(c) {
    return `
      <a href="/careers/courses/${escHtml(c.slug)}/" class="cr-course-card"
         aria-label="${escHtml(c.title)}">
        <span class="cr-course-card__qual">${escHtml(c.qualification || '')}</span>
        <h3 class="cr-course-card__title">${escHtml(c.title)}</h3>
        <div class="cr-course-card__meta">
          ${c.duration_years ? `<span>${c.duration_years} yr${c.duration_years !== 1 ? 's' : ''}</span>` : ''}
          ${c.career_title   ? `<span>${escHtml(c.career_title)}</span>` : ''}
        </div>
      </a>`;
  }

  // Search
  $('crInstCourseSearch')?.addEventListener('input', debounce(e => {
    state.search = e.target.value.trim();
    render();
  }));

  // Qual chips
  $('crInstQualChips')?.addEventListener('click', e => {
    const chip = e.target.closest('.cr-chip');
    if (!chip) return;
    $('crInstQualChips').querySelectorAll('.cr-chip').forEach(c =>
      c.classList.remove('cr-chip--active')
    );
    chip.classList.add('cr-chip--active');
    state.qual = chip.dataset.qual || '';
    render();
  });

  // Sector chips
  $('crInstSectorChips')?.addEventListener('click', e => {
    const chip = e.target.closest('.cr-chip');
    if (!chip) return;
    $('crInstSectorChips').querySelectorAll('.cr-chip').forEach(c =>
      c.classList.remove('cr-chip--active')
    );
    chip.classList.add('cr-chip--active');
    state.sector = chip.dataset.sector || '';
    render();
  });

  // Clear
  clearBtn?.addEventListener('click', () => {
    state.search = ''; state.qual = ''; state.sector = '';
    const searchInput = $('crInstCourseSearch');
    if (searchInput) searchInput.value = '';
    document.querySelectorAll('#crInstQualChips .cr-chip, #crInstSectorChips .cr-chip')
      .forEach((c, i) => c.classList.toggle('cr-chip--active', i === 0 || c.dataset.qual === '' || c.dataset.sector === ''));
    render();
  });
}

/* ─────────────────────────────────────────────
   SMOOTH SCROLL for in-page anchors
───────────────────────────────────────────── */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', e => {
      const target = document.querySelector(link.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

/* ─────────────────────────────────────────────
   RESPONSIVE DETAIL GRID
   Collapses to single column on narrow screens.
───────────────────────────────────────────── */
function initResponsiveGrid() {
  const grids = ['crDetailGrid', 'crCourseGrid'];
  function adjust() {
    grids.forEach(id => {
      const el = $(id);
      if (!el) return;
      el.style.gridTemplateColumns = window.innerWidth <= 900 ? '1fr' : '1fr 300px';
    });
  }
  adjust();
  window.addEventListener('resize', adjust, { passive: true });
}

/* ─────────────────────────────────────────────
   ASSESSMENT BUTTON — opens modal (from assessment_modal.js)
   Registers any detail-page assessment buttons as modal triggers.
───────────────────────────────────────────── */
function initAssessmentButtons() {
  ['crDetailAssessmentBtn', 'crCourseAssessmentBtn'].forEach(id => {
    $(id)?.addEventListener('click', () => {
      window.CaModal?.open();
    });
  });
}

/* ─────────────────────────────────────────────
   BOOT
───────────────────────────────────────────── */
function init() {
  initRing();
  initCutoffTrends();
  initShowMoreInst();
  initCourseEligibility();
  initInstCourseFilter();
  initSmoothScroll();
  initResponsiveGrid();
  // Assessment modal buttons wired after assessment_modal.js may have already run
  if (window.CaModal) {
    initAssessmentButtons();
  } else {
    // assessment_modal.js loads after this file; wait for it
    window.addEventListener('load', initAssessmentButtons);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
