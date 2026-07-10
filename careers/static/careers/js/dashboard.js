/**
 * careers/dashboard.js
 * Handles: search, recommendation card animations, skeleton loading, match bar animation.
 * Expects window.CR_URLS to be set by the template.
 */

'use strict';

/* ── Utilities ── */
function debounce(fn, wait = 350) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), wait); };
}

function escHtml(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}

function $(id) { return document.getElementById(id); }

/* ── Animate recommendation match bars ── */
function animateMatchBars() {
  document.querySelectorAll('.cr-rec-card__match-fill[data-pct]').forEach(bar => {
    requestAnimationFrame(() => {
      bar.style.width = bar.dataset.pct + '%';
    });
  });
}

/* ── Remove skeletons once real content is present ── */
function clearSkeletons(containerId) {
  const container = $(containerId);
  if (!container) return;
  container.querySelectorAll('.cr-skeleton-card').forEach(el => el.remove());
}

/* ── Dashboard search (debounced, hits careers search API) ── */
function initSearch() {
  const input      = $('crDashSearch');
  const results    = $('crDashSearchResults');
  if (!input || !results) return;

  const doSearch = debounce(async () => {
    const q = input.value.trim();
    results.innerHTML = '';
    if (!q) return;

    try {
      const res  = await fetch(`${window.CR_URLS.searchAPI}?query=${encodeURIComponent(q)}`, {
        headers: { 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (!res.ok) throw new Error('search failed');
      const data = await res.json();

      // API returns { success, message: [{id, title}, ...] } or {id: name} object
      const items = Array.isArray(data.message)
        ? data.message
        : Object.entries(data.message || {}).map(([id, title]) => ({ id, title }));

      if (!items.length) {
        results.innerHTML = '<span style="font-size:0.8rem;opacity:0.5;">No results found.</span>';
        return;
      }

      items.slice(0, 8).forEach(item => {
        const chip = document.createElement('a');
        chip.href = `${window.CR_URLS.explore}?q=${encodeURIComponent(item.title || item.id)}`;
        chip.className = 'cr-chip';
        chip.textContent = item.title || item.id;
        results.appendChild(chip);
      });
    } catch (_) {
      results.innerHTML = '<span style="font-size:0.8rem;opacity:0.4;">Search unavailable.</span>';
    }
  }, 350);

  input.addEventListener('input', doSearch);

  input.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      input.value = '';
      results.innerHTML = '';
    }
  });
}

/* ── Stagger-animate cards as they enter viewport ── */
function initCardAnimations() {
  if (!window.IntersectionObserver) return;

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animationPlayState = 'running';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.cr-rec-card, .cr-card, .cr-course-card').forEach(card => {
    card.style.animationPlayState = 'paused';
    observer.observe(card);
  });
}

/* ── Boot ── */
function init() {
  initSearch();
  initCardAnimations();

  // Animate match bars after a short delay so the transition is visible
  setTimeout(animateMatchBars, 200);

  // Once JS has run, clear any remaining skeleton placeholders
  clearSkeletons('crRecCareers');
  clearSkeletons('crRecCourses');
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
