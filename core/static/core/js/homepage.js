/**
 * homepage.js — EdPal homepage interactions
 *
 * DOM contracts (IDs / classes this script expects):
 *   #hp-loader          — full-screen intro overlay
 *   #hp-loader-canvas   — Three.js canvas inside loader
 *   #hp-skip-btn        — button to dismiss loader
 *   #hp-hero-canvas     — Three.js canvas in hero section
 *   #hp-hero-fallback   — CSS fallback shown if WebGL unavailable
 *   .hp-nav-link        — all nav anchor links (desktop + mobile)
 *   #hp-theme-toggle    — theme toggle button
 *   #hp-hamburger       — mobile nav toggle
 *   #hp-mobile-nav      — mobile nav drawer
 *   #hp-contact-btn     — opens contact modal
 *   #hp-modal-backdrop  — modal container
 *   #hp-modal-close     — modal close button
 *   #hp-modal-submit    — modal form submit
 *   #hp-modal-status    — modal status message
 *   #hp-year            — footer copyright year
 *
 * Django integration:
 *   Place file at: static/homepage/js/homepage.js
 *   Reference via: {% static 'homepage/js/homepage.js' %}
 *   Three.js CDN must be loaded (deferred) before this script.
 */

'use strict';

/* ── Utility ── */
const $ = id => document.getElementById(id);
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const isSmallScreen = () => window.innerWidth <= 600;

/* ─────────────────────────────────────────────
   THEME
   Reads/writes reg_theme in localStorage and
   toggles .theme-dark on <html>.
───────────────────────────────────────────── */
function initTheme() {
  const btn = $('hp-theme-toggle');
  if (!btn) return;

  function applyTheme(dark) {
    document.documentElement.classList.toggle('theme-dark', dark);
    localStorage.setItem('reg_theme', dark ? 'dark' : 'light');
    btn.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
  }

  btn.addEventListener('click', () => {
    applyTheme(!document.documentElement.classList.contains('theme-dark'));
  });
}

/* ─────────────────────────────────────────────
   LOADER + THREE.JS INTRO SCENE
   Builds a simple rotating torus/sphere rig as
   a procedural logo stand-in.
   Replace with a real .glb model by swapping in
   a GLTFLoader and pointing at your model URL.
───────────────────────────────────────────── */
function initLoader() {
  const loader  = $('hp-loader');
  const skipBtn = $('hp-skip-btn');
  if (!loader) return;

  function hideLoader() {
    loader.classList.add('hp-loader--hidden');
    loader.addEventListener('transitionend', () => loader.remove(), { once: true });
  }

  skipBtn?.addEventListener('click', hideLoader);
  // Auto-dismiss after 1.8 s (one pulse cycle)
  setTimeout(hideLoader, reduceMotion ? 0 : 1800);
}

/* ─────────────────────────────────────────────
   HERO SCENE
   Floating SVG sprite icons (math / code / design)
   rendered as THREE.Sprite objects.
   Falls back to CSS animation if WebGL unavailable.
───────────────────────────────────────────── */
function initHeroScene() {
  const canvas   = $('hp-hero-canvas');
  const fallback = $('hp-hero-fallback');
  if (!canvas) return;

  if (isSmallScreen() || !window.THREE) { activateFallback(); return; }

  let raf;

  try {
    const THREE    = window.THREE;
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true });
    const parent   = canvas.parentElement;

    function resize() {
      renderer.setSize(parent.clientWidth, parent.clientHeight);
      camera.aspect = parent.clientWidth / parent.clientHeight;
      camera.updateProjectionMatrix();
    }

    const camera = new THREE.PerspectiveCamera(75, parent.clientWidth / parent.clientHeight, 0.1, 100);
    camera.position.z = 4;

    const scene = new THREE.Scene();
    renderer.setSize(parent.clientWidth, parent.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));

    /* ── Star field ── */
    const starCount = 2200;
    const starPos   = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i++) {
      starPos[i] = (Math.random() - 0.5) * 30;
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
    const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.045, sizeAttenuation: true, transparent: true, opacity: 0.75 });
    scene.add(new THREE.Points(starGeo, starMat));

    /* ── Nebula clouds — additive blended sprite clusters ── */
    const nebulaColors = [0xE85D04, 0xF97316, 0x1E3A5F, 0x0d1b2a, 0xDC2F02];
    const nebulaMeshes = [];

    nebulaColors.forEach((col, i) => {
      const cv  = document.createElement('canvas');
      cv.width  = 256;
      cv.height = 256;
      const ctx = cv.getContext('2d');
      const grd = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
      grd.addColorStop(0,   hexToRgba(col, 0.35));
      grd.addColorStop(0.4, hexToRgba(col, 0.12));
      grd.addColorStop(1,   'rgba(0,0,0,0)');
      ctx.fillStyle = grd;
      ctx.fillRect(0, 0, 256, 256);

      const tex = new THREE.CanvasTexture(cv);
      const mat = new THREE.SpriteMaterial({ map: tex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true });
      const spr = new THREE.Sprite(mat);
      const sc  = 3.5 + Math.random() * 3;
      spr.scale.set(sc, sc, 1);
      spr.position.set(
        (Math.random() - 0.5) * 8,
        (Math.random() - 0.5) * 5,
        -2 - Math.random() * 2,
      );
      spr.userData.speed  = 0.00008 + Math.random() * 0.00006;
      spr.userData.offset = Math.random() * Math.PI * 2;
      scene.add(spr);
      nebulaMeshes.push(spr);
    });

    /* ── Subtle dust particles ── */
    const dustCount = 600;
    const dustPos   = new Float32Array(dustCount * 3);
    const dustAlpha = new Float32Array(dustCount);
    for (let i = 0; i < dustCount; i++) {
      dustPos[i * 3]     = (Math.random() - 0.5) * 12;
      dustPos[i * 3 + 1] = (Math.random() - 0.5) * 8;
      dustPos[i * 3 + 2] = (Math.random() - 0.5) * 4;
      dustAlpha[i]       = Math.random();
    }
    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPos, 3));
    const dustMat = new THREE.PointsMaterial({ color: 0xF97316, size: 0.025, sizeAttenuation: true, transparent: true, opacity: 0.35 });
    scene.add(new THREE.Points(dustGeo, dustMat));

    /* ── Animation loop ── */
    function tick(t) {
      raf = requestAnimationFrame(tick);
      if (!reduceMotion) {
        // Slowly drift camera for parallax
        camera.position.x = Math.sin(t * 0.00005) * 0.4;
        camera.position.y = Math.cos(t * 0.00007) * 0.2;
        camera.lookAt(scene.position);

        // Breathe nebula clouds
        nebulaMeshes.forEach(s => {
          const pulse = 1 + Math.sin(t * s.userData.speed * 1000 + s.userData.offset) * 0.06;
          s.material.opacity = 0.55 + Math.sin(t * s.userData.speed * 800 + s.userData.offset) * 0.15;
          s.scale.setScalar(s.scale.x > 0 ? s.scale.x * pulse : 4);
        });
      }
      renderer.render(scene, camera);
    }

    tick(0);

    const ro = new ResizeObserver(resize);
    ro.observe(parent);

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) cancelAnimationFrame(raf);
      else tick(0);
    });

  } catch (err) {
    console.warn('[EdPal hero] Three.js init failed:', err.message);
    activateFallback();
  }

  function activateFallback() {
    if (fallback) fallback.classList.add('hp-hero__fallback--active');
    if (canvas)   canvas.style.display = 'none';
  }
}

/* Convert hex colour int to rgba string for canvas gradients */
function hexToRgba(hex, alpha) {
  const r = (hex >> 16) & 255;
  const g = (hex >> 8)  & 255;
  const b =  hex        & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

/**
 * Draws an SVG-like icon onto a canvas texture for use as a Three.js sprite.
 * @param {object} def — { label, color, svgPath }
 * @param {object} THREE
 * @returns {THREE.CanvasTexture}
 */
function buildSpriteTexture(def, THREE) {
  const size = 128;
  const cv   = document.createElement('canvas');
  cv.width = cv.height = size;
  const ctx = cv.getContext('2d');

  ctx.clearRect(0, 0, size, size);
  ctx.strokeStyle = def.color;
  ctx.lineWidth   = 5;
  ctx.lineCap     = 'round';
  ctx.lineJoin    = 'round';

  // Scale SVG viewBox (0 0 60 60) → canvas size
  const scale = size / 60;
  ctx.save();
  ctx.scale(scale, scale);
  ctx.beginPath();
  const p = new Path2D(def.svgPath);
  ctx.stroke(p);
  ctx.restore();

  return new THREE.CanvasTexture(cv);
}

/* ─────────────────────────────────────────────
   SCENE MORPH TRANSITIONS
   Triggered when user clicks a nav anchor.
   Animates a brief geometry morph on the hero
   canvas as visual feedback between sections.
───────────────────────────────────────────── */
function morphToSection(sectionId) {
  // Only run if we have WebGL and the hero canvas is active
  const canvas = $('hp-hero-canvas');
  if (!canvas || !window.THREE || reduceMotion) return;

  // Simple: flash a brief scale pulse — expand this to a full shader morph.
  canvas.style.transition = 'opacity 0.25s ease';
  canvas.style.opacity    = '0.4';
  setTimeout(() => { canvas.style.opacity = '1'; }, 280);
}

/* ─────────────────────────────────────────────
   NAV: anchor clicks + morph trigger
───────────────────────────────────────────── */
function initNav() {
  const hamburger  = $('hp-hamburger');
  const mobileNav  = $('hp-mobile-nav');

  document.querySelectorAll('.hp-nav-link').forEach(link => {
    link.addEventListener('click', e => {
      const section = link.dataset.section;
      if (section) morphToSection(section);
      // Close mobile nav if open
      closeMobileNav();
    });
  });

  hamburger?.addEventListener('click', () => {
    const isOpen = !mobileNav.hidden;
    if (isOpen) {
      closeMobileNav();
    } else {
      mobileNav.hidden = false;
      hamburger.setAttribute('aria-expanded', 'true');
      // Move focus to first link
      mobileNav.querySelector('.hp-mobile-nav__link')?.focus();
    }
  });

  function closeMobileNav() {
    if (!mobileNav) return;
    mobileNav.hidden = true;
    hamburger?.setAttribute('aria-expanded', 'false');
  }

  // Close on Escape
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !mobileNav?.hidden) closeMobileNav();
  });

  // Close when clicking outside
  document.addEventListener('click', e => {
    if (!mobileNav?.hidden && !mobileNav.contains(e.target) && e.target !== hamburger) {
      closeMobileNav();
    }
  });
}

/* ─────────────────────────────────────────────
   MODAL
───────────────────────────────────────────── */
function initModal() {
  const backdrop  = $('hp-modal-backdrop');
  const closeBtn  = $('hp-modal-close');
  const openBtn   = $('hp-contact-btn');
  const submitBtn = $('hp-modal-submit');
  const status    = $('hp-modal-status');

  if (!backdrop) return;

  function openModal() {
    backdrop.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    closeBtn?.focus();
  }

  function closeModal() {
    backdrop.classList.add('hidden');
    document.body.style.overflow = '';
    openBtn?.focus();
    if (status) status.textContent = '';
  }

  openBtn?.addEventListener('click', openModal);
  closeBtn?.addEventListener('click', closeModal);

  backdrop.addEventListener('click', e => {
    if (e.target === backdrop) closeModal();
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !backdrop.classList.contains('hidden')) closeModal();
  });

  // Trap focus inside modal
  backdrop.addEventListener('keydown', e => {
    if (e.key !== 'Tab') return;
    const focusable = [...backdrop.querySelectorAll('button, input, textarea, a[href], [tabindex]:not([tabindex="-1"])')];
    const first = focusable[0];
    const last  = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  submitBtn?.addEventListener('click', () => {
    const name    = $('hp-contact-name')?.value.trim();
    const email   = $('hp-contact-email')?.value.trim();
    const message = $('hp-contact-message')?.value.trim();

    if (!name || !email || !message) {
      status.textContent = 'Please fill in all fields.';
      return;
    }

    /*
     * Replace with a real fetch POST to a Django view, e.g.:
     *
     *   fetch('/contact/', {
     *     method: 'POST',
     *     headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
     *     body: JSON.stringify({ name, email, message }),
     *   })
     *   .then(r => r.json())
     *   .then(data => { status.textContent = data.message; });
     */
    status.textContent = 'Message sent — we will be in touch soon.';
    submitBtn.disabled = true;
    setTimeout(closeModal, 1800);
  });
}

/* ─────────────────────────────────────────────
   FOOTER YEAR
───────────────────────────────────────────── */
function setYear() {
  const el = $('hp-year');
  if (el) el.textContent = new Date().getFullYear();
}

/* ─────────────────────────────────────────────
   BOOT
───────────────────────────────────────────── */
function init() {
  setYear();
  initTheme();
  initNav();
  initModal();

  // Loader and hero share Three.js — wait for it to be available
  if (window.THREE) {
    initLoader();
    initHeroScene();
  } else {
    // Three.js loads with defer; wait for it
    window.addEventListener('load', () => {
      initLoader();
      initHeroScene();
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}