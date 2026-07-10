/**
 * careers/career_match.js
 * Handles: match score ring animation, accordion expansion, eligibility checker,
 *          recommendation interactions, dynamic tables, smooth scrolling, loading states.
 * Expects: window.CR_MATCH set by template.
 */

'use strict';

const $ = id => document.getElementById(id);

/* ─────────────────────────────────────────────
   MATCH SCORE RING ANIMATION
   SVG circle circumference: 2π × 54 ≈ 339.29
───────────────────────────────────────────── */
function initRing() {
  const fill   = $('crRingFill');
  const label  = $('crRingValue');
  const pct    = window.CR_MATCH?.match_pct || 0;
  const CIRCUM = 339.29;

  if (!fill || !label) return;

  // Animate on load
  requestAnimationFrame(() => {
    const offset = CIRCUM - (pct / 100) * CIRCUM;
    fill.style.strokeDashoffset = String(offset);
  });

  // Count-up number
  const duration = 1200;
  const start    = performance.now();

  function step(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased    = 1 - Math.pow(1 - progress, 3); // ease-out cubic
    label.textContent = Math.round(eased * pct) + '%';
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

/* ─────────────────────────────────────────────
   ACCORDION (insights)
───────────────────────────────────────────── */
function initAccordion() {
  const list = $('crInsightsList');
  if (!list) return;

  list.addEventListener('click', e => {
    const trigger = e.target.closest('.cr-accordion-item__trigger');
    if (!trigger) return;

    const item     = trigger.closest('.cr-accordion-item');
    const isOpen   = item.classList.contains('cr-accordion-item--open');
    const expanded = !isOpen;

    // Close all, then open clicked (single-open accordion)
    list.querySelectorAll('.cr-accordion-item').forEach(i => {
      i.classList.remove('cr-accordion-item--open');
      i.querySelector('.cr-accordion-item__trigger')?.setAttribute('aria-expanded', 'false');
    });

    if (expanded) {
      item.classList.add('cr-accordion-item--open');
      trigger.setAttribute('aria-expanded', 'true');

      // Animate any match bars inside the opened panel
      item.querySelectorAll('.cr-rec-card__match-fill[data-pct]').forEach(bar => {
        requestAnimationFrame(() => { bar.style.width = bar.dataset.pct + '%'; });
      });
    }
  });

  // Keyboard: Space/Enter already handled by button; arrow keys between items
  list.addEventListener('keydown', e => {
    if (!['ArrowDown', 'ArrowUp'].includes(e.key)) return;
    const triggers = Array.from(list.querySelectorAll('.cr-accordion-item__trigger'));
    const idx      = triggers.indexOf(document.activeElement);
    if (idx === -1) return;
    e.preventDefault();
    const next = e.key === 'ArrowDown'
      ? triggers[(idx + 1) % triggers.length]
      : triggers[(idx - 1 + triggers.length) % triggers.length];
    next.focus();
  });
}

/* ─────────────────────────────────────────────
   ELIGIBILITY CHECKER
───────────────────────────────────────────── */
function initEligibilityChecker() {
  const grid      = $('crEligibilityGrid');
  const checkBtn  = $('crCheckEligibility');
  const result    = $('crEligibilityResult');
  const pointsInput = $('crUserPoints');

  if (!grid || !checkBtn) return;

  const subjectReqs = window.CR_MATCH?.subject_reqs || [];
  const userGrades  = window.CR_MATCH?.user_grades   || {};
  const userPoints  = window.CR_MATCH?.user_points;

  // Pre-fill points if available from server
  if (pointsInput && userPoints != null) pointsInput.value = userPoints;

  // Build grade inputs for mandatory subjects
  const mandatory = subjectReqs.filter(r => r.requirement_type === 'MANDATORY');

  if (mandatory.length) {
    mandatory.forEach(req => {
      const field = document.createElement('div');
      field.className = 'cr-eligibility__field';

      const label = document.createElement('label');
      label.className = 'cr-eligibility__label';
      label.textContent = req.subject;
      label.htmlFor = `cr-grade-${req.subject.replace(/\s+/g, '-').toLowerCase()}`;

      const select = document.createElement('select');
      select.className = 'form-input';
      select.id  = label.htmlFor;
      select.name = req.subject;
      select.setAttribute('aria-label', `Grade for ${req.subject}`);

      const grades = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'E'];
      select.innerHTML = `<option value="">Select grade</option>` +
        grades.map(g => {
          const selected = userGrades[req.subject] === g ? ' selected' : '';
          return `<option value="${g}"${selected}>${g}</option>`;
        }).join('');

      field.appendChild(label);
      field.appendChild(select);
      grid.appendChild(field);
    });
  } else {
    grid.innerHTML = '<p style="font-size:0.82rem;opacity:0.5;margin:0 0 12px;">No specific subject requirements found for this career.</p>';
  }

  checkBtn.addEventListener('click', () => {
    if (!result) return;

    const totalPoints  = parseInt(pointsInput?.value || '0', 10);
    const latestCutoff = getLatestCutoff();

    // Grade check
    let gradeOk   = true;
    let missingGrades = [];

    mandatory.forEach(req => {
      const select = grid.querySelector(`[name="${req.subject}"]`);
      if (!select || !select.value) { gradeOk = false; missingGrades.push(req.subject); return; }
      if (req.minimum_grade && !gradeAtLeast(select.value, req.minimum_grade)) {
        gradeOk = false;
        missingGrades.push(`${req.subject} (need ${req.minimum_grade}, got ${select.value})`);
      }
    });

    const pointsOk = latestCutoff == null || totalPoints >= latestCutoff;

    result.classList.add('cr-eligibility__result--show');

    if (gradeOk && pointsOk) {
      result.className = 'cr-eligibility__result cr-eligibility__result--show cr-eligibility__result--pass';
      result.innerHTML = `
        <strong>You appear eligible!</strong>
        ${latestCutoff ? ` Your ${totalPoints} pts meet the ${latestCutoff} pt cutoff.` : ''}
        Check with the institution for final confirmation.
      `;
    } else {
      const reasons = [];
      if (!pointsOk) reasons.push(`Your points (${totalPoints}) are below the cutoff (${latestCutoff}).`);
      if (!gradeOk)  reasons.push(`Grade requirements not met: ${missingGrades.join(', ')}.`);
      result.className = 'cr-eligibility__result cr-eligibility__result--show cr-eligibility__result--fail';
      result.innerHTML = `<strong>Not yet eligible.</strong> ${reasons.join(' ')}`;
    }

    result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  });
}

/* Get most recent cutoff points from CR_MATCH data */
function getLatestCutoff() {
  const cutoffs = window.CR_MATCH?.cutoffs || [];
  if (!cutoffs.length) return null;
  const sorted = [...cutoffs].sort((a, b) => b.year - a.year);
  return sorted[0]?.cutoff_points ?? null;
}

/* Ordinal grade comparison (KCSE-style) */
const GRADE_ORDER = ['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'E'];
function gradeAtLeast(got, required) {
  return GRADE_ORDER.indexOf(got) <= GRADE_ORDER.indexOf(required);
}

/* ─────────────────────────────────────────────
   CUTOFF TABLE TREND INDICATORS
   Adds up/down/flat arrows to .cr-cutoff-trend spans
───────────────────────────────────────────── */
function initCutoffTrends() {
  const cutoffs = window.CR_MATCH?.cutoffs || [];
  if (cutoffs.length < 2) return;

  const sorted = [...cutoffs].sort((a, b) => b.year - a.year);
  const spans  = document.querySelectorAll('.cr-cutoff-trend');

  spans.forEach((span, i) => {
    const current  = sorted[i];
    const previous = sorted[i + 1];
    if (!current || !previous) return;

    const diff = current.cutoff_points - previous.cutoff_points;
    if (diff > 0)      { span.textContent = '↑'; span.style.color = '#a3e635'; span.title = `+${diff} from previous year`; }
    else if (diff < 0) { span.textContent = '↓'; span.style.color = '#f87171'; span.title = `${diff} from previous year`; }
    else               { span.textContent = '→'; span.style.color = 'var(--color-foreground)'; span.title = 'Unchanged'; }
  });
}

/* ─────────────────────────────────────────────
   INSTITUTIONS — show more toggle
───────────────────────────────────────────── */
function initShowMoreInstitutions() {
  const btn  = $('crShowMoreInst');
  const list = $('crMatchInstList');
  if (!btn || !list) return;

  const items = Array.from(list.querySelectorAll('.cr-inst-card'));
  const SHOW  = 4;

  // Initially hide extras
  items.forEach((item, i) => { if (i >= SHOW) item.hidden = true; });

  let expanded = false;
  btn.addEventListener('click', () => {
    expanded = !expanded;
    items.forEach((item, i) => { if (i >= SHOW) item.hidden = !expanded; });
    btn.textContent = expanded ? 'Show less' : 'Show more';
  });
}

/* ─────────────────────────────────────────────
   SMOOTH SCROLL — hash nav links within page
───────────────────────────────────────────── */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', e => {
      const target = document.querySelector(link.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      target.focus({ preventScroll: true });
    });
  });
}

/* ─────────────────────────────────────────────
   SIMILAR CAREERS — animate on scroll
───────────────────────────────────────────── */
function initSimilarCareersAnimation() {
  if (!window.IntersectionObserver) return;

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animationPlayState = 'running';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('#crSimilarGrid .cr-card').forEach(card => {
    card.style.animationPlayState = 'paused';
    observer.observe(card);
  });
}

/* ─────────────────────────────────────────────
   RESPONSIVE GRID COLLAPSE
───────────────────────────────────────────── */
function initResponsiveGrid() {
  const grid = $('crMatchGrid');
  if (!grid) return;

  function adjust() {
    if (window.innerWidth <= 900) {
      grid.style.gridTemplateColumns = '1fr';
    } else {
      grid.style.gridTemplateColumns = '1fr 320px';
    }
  }

  adjust();
  window.addEventListener('resize', adjust, { passive: true });
}

/* ─────────────────────────────────────────────
   BOOT
───────────────────────────────────────────── */
function init() {
  initRing();
  initAccordion();
  initEligibilityChecker();
  initCutoffTrends();
  initShowMoreInstitutions();
  initSmoothScroll();
  initSimilarCareersAnimation();
  initResponsiveGrid();

  // Animate any visible match bars (recommendation card partial)
  setTimeout(() => {
    document.querySelectorAll('.cr-rec-card__match-fill[data-pct]').forEach(bar => {
      bar.style.width = bar.dataset.pct + '%';
    });
  }, 200);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
