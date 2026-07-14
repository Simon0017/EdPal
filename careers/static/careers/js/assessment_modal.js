/**
 * careers/assessment_modal.js
 *
 * Manages the career psychometric test selection modal.
 * Shared between dashboard.html and career_match.html.
 *
 * DOM contracts:
 * #caAssessmentModal      — modal backdrop
 * #caModalClose           — close button
 * #caTestGrid             — card grid container
 * #caTestEmpty            — empty-state element
 * #caModalCategoryChips   — chip filter bar
 * #crDashAssessmentBtn    — trigger on dashboard (if present)
 * #crMatchAssessmentBtn   — trigger on career match page (if present)
 * #caToastStack           — toast container (from toast.html partial)
 *
 * window.CA_TESTS         — array of test objects from the view context
 * { name, slug, description, category, estimated_duration, total_questions, is_premium }
 *
 * window.CA_URLS.assessmentPage — base URL for the assessment page (append slug)
 * Set this in the host template:
 * window.CA_URLS = { ..., assessmentPage: "{% url 'career-assessment' slug='__slug__' %}" }
 */

(() => {
  'use strict';

  /* ── Utilities ── */
  const $ = id => document.getElementById(id);

  function escHtml(str) {
    const d = document.createElement('div');
    d.textContent = str || '';
    return d.innerHTML;
  }

  function trapFocus(container) {
    const focusable = () => Array.from(
      container.querySelectorAll(
        'button:not(:disabled), input:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])'
      )
    );

    container.addEventListener('keydown', e => {
      if (e.key !== 'Tab') return;
      const els   = focusable();
      const first = els[0];
      const last  = els[els.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
    });
  }

  /* ── Toast ── */
  const CaToast = {
    show(message, type = 'success', duration = 4500) {
      const stack = $('caToastStack');
      if (!stack) return;

      const icons = {
        success: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                       stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22,4 12,14.01 9,11.01"/>
                  </svg>`,
        error:   `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                       stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                    <line x1="9"  y1="9" x2="15" y2="15"/>
                  </svg>`,
      };

      const el = document.createElement('div');
      el.className = `ca-toast ca-toast--${type}`;
      el.setAttribute('role', type === 'error' ? 'alert' : 'status');
      el.innerHTML = `
        <span class="ca-toast__icon" style="color:${type === 'success' ? '#a3e635' : '#f87171'}">
          ${icons[type] || ''}
        </span>
        <span class="ca-toast__text">${escHtml(message)}</span>`;

      stack.appendChild(el);
      setTimeout(() => el.remove(), duration);
    },
  };

  /* ── Modal ── */
  const CaModal = {
    _activeFilter: '',
    _backdrop: null,
    _previousFocus: null,

    init() {
      this._backdrop = $('caAssessmentModal');
      if (!this._backdrop) return;

      // Close controls
      $('caModalClose')?.addEventListener('click', () => this.close());
      this._backdrop.addEventListener('click', e => {
        if (e.target === this._backdrop) this.close();
      });
      document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && !this._backdrop.classList.contains('hidden')) this.close();
      });

      // Open triggers
      ['crDashAssessmentBtn', 'crMatchAssessmentBtn'].forEach(id => {
        $(id)?.addEventListener('click', () => this.open());
      });

      // Category filter chips
      $('caModalCategoryChips')?.addEventListener('click', e => {
        const chip = e.target.closest('.cr-chip');
        if (!chip) return;
        $('caModalCategoryChips').querySelectorAll('.cr-chip').forEach(c =>
          c.classList.remove('cr-chip--active')
        );
        chip.classList.add('cr-chip--active');
        this._activeFilter = chip.dataset.category || '';
        this._renderCards();
      });

      // Focus trap
      const modal = this._backdrop.querySelector('.ca-modal');
      if (modal) trapFocus(modal);

      // Initial render
      this._renderCards();
    },

    open() {
      if (!this._backdrop) return;
      this._previousFocus = document.activeElement;
      this._backdrop.classList.remove('hidden');
      document.body.style.overflow = 'hidden';
      $('caModalClose')?.focus();
    },

    close() {
      if (!this._backdrop) return;
      this._backdrop.classList.add('hidden');
      document.body.style.overflow = '';
      this._previousFocus?.focus();
    },

    _renderCards() {
      const grid     = $('caTestGrid');
      const emptyEl  = $('caTestEmpty');
      const tests    = window.CA_TESTS || [];
      if (!grid) return;

      const filtered = this._activeFilter
        ? tests.filter(t => t.category === this._activeFilter)
        : tests;

      // Clear skeletons + previous cards
      grid.innerHTML = '';

      if (!filtered.length) {
        emptyEl?.classList.remove('hidden');
        return;
      }

      emptyEl?.classList.add('hidden');

      filtered.forEach((test, i) => {
        const card = document.createElement('div');
        card.className = 'ca-test-card';
        card.setAttribute('tabindex', '0');
        card.setAttribute('role', 'button');
        card.setAttribute('data-test-slug', test.slug);
        card.setAttribute('data-test-category', test.category);
        card.setAttribute('data-premium', test.is_premium ? 'true' : 'false');
        card.setAttribute('aria-label', `Start ${test.name}${test.is_premium ? ' (Premium)' : ''}`);
        card.style.animationDelay = `${i * 0.05}s`;
        card.style.animation = 'cr-fade-up 0.3s ease both';

        const categoryBadge = this._categoryBadge(test.category);

        card.innerHTML = `
          <div class="ca-test-card__badges">
            ${categoryBadge}
          </div>
          <h3 class="ca-test-card__name">${escHtml(test.name)}</h3>
          <p class="ca-test-card__desc">${escHtml(test.description)}</p>
          <div class="ca-test-card__meta">
            <span class="ca-test-card__meta-item">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10"/><polyline points="12,6 12,12 16,14"/>
              </svg>
              ${escHtml(String(test.estimated_duration))} min
            </span>
            <span class="ca-test-card__meta-item">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <line x1="8" y1="6"  x2="21" y2="6"/>
                <line x1="8" y1="12" x2="21" y2="12"/>
                <line x1="8" y1="18" x2="21" y2="18"/>
                <line x1="3" y1="6"  x2="3.01" y2="6"/>
                <line x1="3" y1="12" x2="3.01" y2="12"/>
                <line x1="3" y1="18" x2="3.01" y2="18"/>
              </svg>
              ${escHtml(String(test.total_questions))} questions
            </span>
          </div>`;

        // Click + keyboard activation
        const activate = () => this._navigateToTest(test);
        card.addEventListener('click', activate);
        card.addEventListener('keydown', e => {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(); }
        });

        grid.appendChild(card);
      });
    },

    _categoryBadge(category) {
      const map = {
        basic:        ['ca-badge--basic',        'Basic'],
        intermediate: ['ca-badge--intermediate', 'Intermediate'],
        advanced:     ['ca-badge--advanced',     'Advanced'],
      };
      const [cls, label] = map[category] || ['cr-badge--muted', category];
      return `<span class="cr-badge ${cls}">${escHtml(label)}</span>`;
    },

    _navigateToTest(test) {
      const base = (window.CA_URLS?.assessmentPage || '/careers/assessment/__slug__/')
        .replace('__slug__', test.slug);
      window.location.href = base;
    },
  };

  /* ── Boot ── */
  function init() {
    CaModal.init();
    window.CaModal = CaModal;
    window.CaToast = CaToast;
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();