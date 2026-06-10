/* dashboard.js */

const CHART_DEFAULTS = {
  color: {
    primary: '#E85D04',
    accent:  '#F97316',
    grid:    'rgba(255,255,255,0.06)',
    text:    'rgba(250,250,250,0.5)',
  },
};

function isDark() {
  return document.documentElement.classList.contains('theme-dark');
}

function gridColor() {
  return isDark() ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.07)';
}

function textColor() {
  return isDark() ? 'rgba(250,250,250,0.5)' : 'rgba(20,20,20,0.5)';
}

/* ── Stat cards ── */
function fillStats(data) {
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  if (data.latest_score != null) {
    set('dbLatestScore', data.latest_score + '%');
    set('dbLatestScoreSub', data.latest_title || '');
  }
  set('dbAvgPct',    data.avg_pct != null ? data.avg_pct + '%' : '—');
  set('dbCompleted', data.completed ?? '—');
  set('dbInProgress', data.in_progress ?? '—');
}

/* ── Score trend chart ── */
function initScoreChart(labels, scores) {
  const ctx = document.getElementById('dbScoreChart');
  if (!ctx) return;

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: scores,
        borderColor: CHART_DEFAULTS.color.primary,
        backgroundColor: 'rgba(232,93,4,0.12)',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: CHART_DEFAULTS.color.primary,
        tension: 0.4,
        fill: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
      scales: {
        x: {
          grid: { color: gridColor() },
          ticks: { color: textColor(), font: { size: 11, family: "'DM Sans'" } },
        },
        y: {
          min: 0, max: 100,
          grid: { color: gridColor() },
          ticks: {
            color: textColor(),
            font: { size: 11, family: "'DM Sans'" },
            callback: v => v + '%',
          },
        },
      },
    },
  });
}

/* ── Category donut chart ── */
function initCategoryChart(labels, values) {
  const ctx = document.getElementById('dbCategoryChart');
  if (!ctx) return;

  const palette = ['#E85D04','#21c5e2','#12ac6b','#38bdf8','#a3e635','#f472b6','#818cf8'];

  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: palette.slice(0, labels.length),
        borderWidth: 0,
        hoverOffset: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: textColor(),
            font: { size: 11, family: "'DM Sans'" },
            padding: 10,
            boxWidth: 10,
            boxHeight: 10,
          },
        },
      },
    },
  });
}

/* ── Career list ── */
function renderCareers(careers) {
  const list = document.getElementById('dbCareerList');
  if (!list) return;
  list.innerHTML = '';

  if (!careers || !careers.length) {
    list.innerHTML = '<li style="font-size:0.8rem;opacity:0.45;padding:8px 4px">No career recommendations yet. Complete your profile to get personalised suggestions.</li>';
    return;
  }

  careers.forEach(c => {
    const li = document.createElement('li');
    li.className = 'db-career-item';
    li.innerHTML = `
      <div>
        <div class="db-career-item__title">${escHtml(c.title)}</div>
        <div class="db-career-item__sector">${escHtml(c.sector || '')}</div>
      </div>
      <span class="db-career-item__rank">#${c.rank}</span>
    `;
    list.appendChild(li);
  });
}

/* ── Tag trending ── */
function renderTags(tags) {
  const list = document.getElementById('dbTagList');
  if (!list) return;
  list.innerHTML = '';

  if (!tags || !tags.length) {
    list.innerHTML = '<li style="font-size:0.8rem;opacity:0.45">No trending topics available.</li>';
    return;
  }

  const max = Math.max(...tags.map(t => t.count || 1));
  tags.forEach(t => {
    const pct = Math.round(((t.count || 0) / max) * 100);
    const li = document.createElement('li');
    li.className = 'db-tag-item';
    li.innerHTML = `
      <span class="db-tag-item__name">${escHtml(t.title)}</span>
      <div class="db-tag-item__bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100" aria-label="${escHtml(t.title)} activity">
        <div class="db-tag-item__fill" style="width:0%" data-target="${pct}%"></div>
      </div>
      <span class="db-tag-item__count">${t.count || 0}</span>
    `;
    list.appendChild(li);
  });

  // Animate bars after paint
  requestAnimationFrame(() => {
    list.querySelectorAll('.db-tag-item__fill').forEach(bar => {
      bar.style.width = bar.dataset.target;
    });
  });
}

/* ── Latest questionnaires ── */
function renderLatestQ(questionnaires) {
  const list = document.getElementById('dbLatestQ');
  if (!list) return;
  list.innerHTML = '';

  if (!questionnaires || !questionnaires.length) {
    list.innerHTML = '<li style="font-size:0.8rem;opacity:0.45">No questionnaires found.</li>';
    return;
  }

  questionnaires.forEach(q => {
    const li = document.createElement('li');
    li.className = 'db-q-item';
    const date = q.created_at ? new Date(q.created_at).toLocaleDateString() : '';
    li.innerHTML = `
      <span class="db-q-item__title">${escHtml(q.title)}</span>
      <div class="db-q-item__meta">
        <span>${date}</span>
        ${q.status ? `<span>&middot;</span><span>${escHtml(q.status)}</span>` : ''}
      </div>
    `;
    list.appendChild(li);
  });
}

/* ── Three.js decorative scene ── */
function init3D() {
  const canvas = document.getElementById('db3dCanvas');
  if (!canvas || !window.THREE) return;

  const THREE = window.THREE;
  const W = canvas.parentElement.clientWidth || 200;
  const H = canvas.parentElement.clientHeight || 200;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setSize(W, H);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, W / H, 0.1, 100);
  camera.position.set(0, 0, 4);

  // Floating spheres
  const geo  = new THREE.SphereGeometry(0.22, 16, 16);
  const mat  = new THREE.MeshBasicMaterial({ color: 0xE85D04, wireframe: true });
  const spheres = [];
  for (let i = 0; i < 8; i++) {
    const m = new THREE.Mesh(geo, mat.clone());
    m.position.set(
      (Math.random() - 0.5) * 3,
      (Math.random() - 0.5) * 3,
      (Math.random() - 0.5) * 2,
    );
    m.userData.speed = 0.004 + Math.random() * 0.006;
    m.userData.offset = Math.random() * Math.PI * 2;
    scene.add(m);
    spheres.push(m);
  }

  // Central torus
  const torusGeo = new THREE.TorusGeometry(0.8, 0.08, 8, 40);
  const torusMat = new THREE.MeshBasicMaterial({ color: 0xF97316, wireframe: false });
  const torus = new THREE.Mesh(torusGeo, torusMat);
  scene.add(torus);

  let frame;
  function animate(t) {
    frame = requestAnimationFrame(animate);
    torus.rotation.x = t * 0.0005;
    torus.rotation.y = t * 0.0008;
    spheres.forEach((s, i) => {
      s.position.y += Math.sin(t * s.userData.speed + s.userData.offset) * 0.003;
      s.rotation.x += 0.01;
    });
    renderer.render(scene, camera);
  }

  animate(0);

  // Cleanup on page navigation
  window.addEventListener('beforeunload', () => cancelAnimationFrame(frame));
}

/* ── Fetch dashboard data ── */
async function loadDashboardData() {
  try {
    const data = window.DB_DATA;
    fillStats(data);

    const labels = (data.score_trend || []).map(p => p.label);
    const scores = (data.score_trend || []).map(p => p.score);
    initScoreChart(labels.length ? labels : placeholderLabels(), scores.length ? scores : []);

    const catLabels = (data.categories || []).map(c => c.label);
    const catVals   = (data.categories || []).map(c => c.value);
    initCategoryChart(catLabels.length ? catLabels : ['No data'], catVals.length ? catVals : [1]);

    renderCareers(data.careers || []);
    renderTags(data.trending_tags || []);
    renderLatestQ(data.latest_questionnaires || []);

  } catch (_) {
    // Render empty states gracefully
    initScoreChart(placeholderLabels(), []);
    initCategoryChart(['No data'], [1]);
    renderCareers([]);
    renderTags([]);
    renderLatestQ([]);
  }
}

function placeholderLabels() {
  const months = ['Jan','Feb','Mar','Apr','May','Jun'];
  return months.slice(-6);
}

function escHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

/* ── Boot ── */
function init() {
  loadDashboardData();
  init3D();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}