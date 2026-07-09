/**
 * assessments/static/assessments/js/questionnaire_parser.js
 *
 * Standalone parser module. No framework dependencies.
 * Requires SheetJS CDN loaded before this script:
 *   <script src="https://cdn.sheetjs.com/xlsx-latest/package/dist/xlsx.full.min.js"></script>
 *
 * Public API (called by questionnare.js):
 *   QuestionnaireParser.openModal()   — opens the upload modal
 *   QuestionnaireParser.onComplete    — assign a callback: fn(parsedPayload)
 *                                       parsedPayload matches buildFormData() expectations
 */

'use strict';

const QuestionnaireParser = (() => {

  /* ─────────────────────────────────────────────────────────────
     CONSTANTS
  ───────────────────────────────────────────────────────────────*/

  // Maps a detected column header → canonical field name
  // Fuzzy: normalise header (lowercase, strip spaces/underscores) then look up
  const FUZZY_MAP = {
    title:                    'title',
    questionnairetitle:       'title',
    name:                     'title',
    description:              'description',
    about:                    'description',
    instructions:             'instructions',
    settings:                 'instructions',
    questionnaireinstructions:'instructions',
    status:                   'status',
    questionnairestatus:      'status',
    score:                    'max_score',
    maxscore:                 'max_score',
    max_score:                'max_score',
    timelimit:                'time_limit_minutes',
    time_limit:               'time_limit_minutes',
    timelimitminutes:         'time_limit_minutes',
    randomised:               'is_randomised',
    israndomised:             'is_randomised',
    randomize:                'is_randomised',
    tag:                      'tags',
    tags:                     'tags',
    subjects:                 'tags',
    relations:                'tags',

    // Question sheet columns
    questiontext:             'question_text',
    question:                 'question_text',
    questiontype:             'question_type',
    type:                     'question_type',
    weight:                   'weight',
    maxpoints:                'max_points',
    max_points:               'max_points',
    order:                    'order',
    required:                 'is_required',
    isrequired:               'is_required',
    explanation:              'explanation',
    numericconfig:            'numeric_config_raw',
    numeric_config:           'numeric_config_raw',
    randomisationgroup:       'randomisation_group',
    randomization_group:      'randomisation_group',

    // Choice sheet columns
    choicekey:                'choice_key',
    key:                      'choice_key',
    choicetext:               'choice_text',
    choice:                   'choice_text',
    iscorrect:                'is_correct',
    correct:                  'is_correct',
    partialscore:             'partial_score',
    choiceorder:              'choice_order',
    choiceexplanation:        'choice_explanation',
    questionindex:            'choice_question_index',
    questionref:              'choice_question_index',
  };

  // Questionnaire-level fields shown in column mapper (Step A)
  const META_FIELDS = ['title','description','instructions','status','max_score','time_limit_minutes','is_randomised','tags'];
  // Question-level fields (Step A, question sheet)
  const QUESTION_FIELDS = ['question_text','question_type','weight','max_points','order','is_required','explanation','numeric_config_raw','randomisation_group'];
  // Choice-level fields
  const CHOICE_FIELDS = ['correct_answer','other_answers','choice_key_source','choice_order','choice_explanation','choice_question_index'];

  /* ─────────────────────────────────────────────────────────────
     STATE
  ───────────────────────────────────────────────────────────────*/
  let _file         = null;
  let _fileType     = null;
  let _sheets       = {};     // { sheetName: [ {col:val,...}, ... ] }
  let _sheetNames   = [];
  let _columnMap    = {};     // { canonical_field: { sheet, col } }
  let _onComplete   = null;   // callback(payload)
  let _modalStep    = 1;      // 1=upload, 2=sheet/column map, 3=review

  /* ─────────────────────────────────────────────────────────────
     PUBLIC
  ───────────────────────────────────────────────────────────────*/
  function openModal () {
    _resetState();
    _ensureModal();
    _showStep(1);
    document.getElementById('qpModal').classList.remove('hidden');
    document.getElementById('qpModalBackdrop').classList.remove('hidden');
    document.getElementById('qpFileInput').focus();
  }

  /* ─────────────────────────────────────────────────────────────
     RESET
  ───────────────────────────────────────────────────────────────*/
  function _resetState () {
    _file       = null;
    _fileType   = null;
    _sheets     = {};
    _sheetNames = [];
    _columnMap  = {};
    _modalStep  = 1;
  }

  /* ─────────────────────────────────────────────────────────────
     MODAL CREATION — injected into DOM once
  ───────────────────────────────────────────────────────────────*/
  function _ensureModal () {
    if (document.getElementById('qpModalBackdrop')) return;

    document.body.insertAdjacentHTML('beforeend', `
      <div class="qp-backdrop hidden" id="qpModalBackdrop" aria-hidden="true">
        <div class="qp-modal" id="qpModal" role="dialog" aria-modal="true" aria-labelledby="qpModalTitle">

          <button class="qp-modal__close" id="qpClose" aria-label="Close import">
            <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z"/></svg>
          </button>

          <!-- Step indicators -->
          <div class="qp-steps" aria-label="Import steps">
            <div class="qp-step qp-step--active" data-step="1">
              <span class="qp-step__dot">1</span><span class="qp-step__label">Upload</span>
            </div>
            <div class="qp-step" data-step="2">
              <span class="qp-step__dot">2</span><span class="qp-step__label">Map columns</span>
            </div>
            <div class="qp-step" data-step="3">
              <span class="qp-step__dot">3</span><span class="qp-step__label">Review</span>
            </div>
          </div>

          <h2 class="qp-modal__title" id="qpModalTitle">Import Questionnaire</h2>

          <!-- ── STEP 1: Upload ── -->
          <div class="qp-panel" id="qpStep1">
            <div class="qp-dropzone" id="qpDropzone" tabindex="0" role="button" aria-label="Upload file">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="40" height="40" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5"/>
              </svg>
              <p class="qp-dropzone__text">Drop your file here, or <span class="qp-dropzone__link">browse</span></p>
              <p class="qp-dropzone__hint">Supports .xlsx, .csv, .json</p>
              <input type="file" id="qpFileInput" class="qp-file-hidden" accept=".xlsx,.csv,.json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,application/json" aria-label="Choose file" />
            </div>
            <div class="qp-file-info hidden" id="qpFileInfo">
              <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16" aria-hidden="true" style="color:var(--color-success)"><path fill-rule="evenodd" d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.857-9.809a.75.75 0 0 0-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 1 0-1.06 1.061l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.5Z" clip-rule="evenodd"/></svg>
              <span id="qpFileName"></span>
              <button type="button" class="qp-btn-link" id="qpRemoveFile" aria-label="Remove file">Remove</button>
            </div>
            <div class="qp-error hidden" id="qpUploadError" role="alert"></div>
            <div class="qp-modal__footer">
              <button type="button" class="btn-ghost qp-btn" id="qpCancel">Cancel</button>
              <button type="button" class="btn-primary qp-btn" id="qpBtnParse" disabled>
                Next: Map columns →
              </button>
            </div>
          </div>

          <!-- ── STEP 2: Column Mapper ── -->
          <div class="qp-panel hidden" id="qpStep2">
            <p class="qp-hint">
              Columns were detected automatically. Adjust any mismatches below.
              Fields left as <em>— skip —</em> will not be imported.
            </p>

            <!-- Sheet selector (XLSX only, hidden for CSV/JSON) -->
            <div class="qp-sheet-selector hidden" id="qpSheetSelector">
              <div class="form-group">
                <label class="form-label" for="qpMetaSheet">Questionnaire meta sheet</label>
                <select class="form-input" id="qpMetaSheet"></select>
              </div>
              <div class="form-group">
                <label class="form-label" for="qpQuestionSheet">Questions sheet</label>
                <select class="form-input" id="qpQuestionSheet"></select>
              </div>
              <div class="form-group">
                <label class="form-label" for="qpChoiceSheet">Answer choices sheet</label>
                <select class="form-input" id="qpChoiceSheet"></select>
              </div>
            </div>

            <!-- Column mapping grid — populated by JS -->
            <div class="qp-mapper" id="qpMapper" aria-label="Column mapping"></div>

            <div class="qp-error hidden" id="qpMapError" role="alert"></div>
            <div class="qp-modal__footer">
              <button type="button" class="btn-ghost qp-btn" id="qpBtnBack2">← Back</button>
              <button type="button" class="btn-primary qp-btn" id="qpBtnBuild">
                Build questionnaire →
              </button>
            </div>
          </div>

          <!-- ── STEP 3: Review summary ── -->
          <div class="qp-panel hidden" id="qpStep3">
            <div class="qp-review" id="qpReview" aria-live="polite"></div>
            <div class="qp-error hidden" id="qpReviewError" role="alert"></div>
            <div class="qp-modal__footer">
              <button type="button" class="btn-ghost qp-btn" id="qpBtnBack3">← Back</button>
              <button type="button" class="btn-primary qp-btn" id="qpBtnApply">
                Load into form →
              </button>
            </div>
          </div>

        </div>
      </div>
    `);

    _bindModalEvents();
  }

  /* ─────────────────────────────────────────────────────────────
     MODAL EVENTS
  ───────────────────────────────────────────────────────────────*/
  function _bindModalEvents () {
    // Close
    document.getElementById('qpClose').addEventListener('click', _closeModal);
    document.getElementById('qpCancel').addEventListener('click', _closeModal);
    document.getElementById('qpModalBackdrop').addEventListener('click', e => {
      if (e.target === e.currentTarget) _closeModal();
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !document.getElementById('qpModalBackdrop').classList.contains('hidden'))
        _closeModal();
    });

    // Remove file
    document.getElementById('qpRemoveFile').addEventListener('click', _clearFile);

    // Step 1 — file input + dropzone
    const fileInput = document.getElementById('qpFileInput');
    const dropzone  = document.getElementById('qpDropzone');

    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); });

    dropzone.addEventListener('dragover',  e => { e.preventDefault(); dropzone.classList.add('qp-dropzone--over'); });
    dropzone.addEventListener('dragleave', ()  => dropzone.classList.remove('qp-dropzone--over'));
    dropzone.addEventListener('drop', e => {
      e.preventDefault();
      dropzone.classList.remove('qp-dropzone--over');
      if (e.dataTransfer.files.length) _handleFile(e.dataTransfer.files[0]);
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) _handleFile(fileInput.files[0]);
    });

    // Step 1 → Step 2
    document.getElementById('qpBtnParse').addEventListener('click', async () => {
      await _parseFile();
    });

    // Sheet selectors trigger remap
    ['qpMetaSheet','qpQuestionSheet','qpChoiceSheet'].forEach(id => {
      document.getElementById(id).addEventListener('change', _buildMapper);
    });

    // Step 2 → Step 3
    document.getElementById('qpBtnBuild').addEventListener('click', _buildReview);

    // Step 3 back / apply
    document.getElementById('qpBtnBack2').addEventListener('click', () => _showStep(1));
    document.getElementById('qpBtnBack3').addEventListener('click', () => _showStep(2));
    document.getElementById('qpBtnApply').addEventListener('click', _applyToForm);
  }

  function _closeModal () {
    document.getElementById('qpModalBackdrop').classList.add('hidden');
  }

  function _clearFile () {
    _file = null;
    _fileType = null;
    document.getElementById('qpFileInput').value = '';
    document.getElementById('qpFileInfo').classList.add('hidden');
    document.getElementById('qpDropzone').classList.remove('hidden');
    document.getElementById('qpBtnParse').disabled = true;
  }

  /* ─────────────────────────────────────────────────────────────
     STEP NAVIGATION
  ───────────────────────────────────────────────────────────────*/
  function _showStep (n) {
    _modalStep = n;
    [1,2,3].forEach(i => {
      document.getElementById(`qpStep${i}`).classList.toggle('hidden', i !== n);
      const dot = document.querySelector(`.qp-step[data-step="${i}"]`);
      if (dot) {
        dot.classList.toggle('qp-step--active', i === n);
        dot.classList.toggle('qp-step--done',   i < n);
      }
    });
  }

  /* ─────────────────────────────────────────────────────────────
     FILE HANDLING
  ───────────────────────────────────────────────────────────────*/
  function _handleFile (file) {
    const allowed = [
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'text/csv',
      'application/json',
    ];
    const extMap = { xlsx:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', csv:'text/csv', json:'application/json' };
    const ext    = file.name.split('.').pop().toLowerCase();
    const type   = file.type || extMap[ext] || null;

    if (!allowed.includes(type)) {
      _showError('qpUploadError', `Unsupported file type ".${ext}". Please upload .xlsx, .csv, or .json.`);
      return;
    }

    _hideError('qpUploadError');
    _file     = file;
    _fileType = type;

    document.getElementById('qpFileName').textContent = file.name;
    document.getElementById('qpFileInfo').classList.remove('hidden');
    document.getElementById('qpDropzone').classList.add('hidden');
    document.getElementById('qpBtnParse').disabled = false;
  }

  /* ─────────────────────────────────────────────────────────────
     PARSE DISPATCHER
  ───────────────────────────────────────────────────────────────*/
  async function _parseFile () {
    const btn = document.getElementById('qpBtnParse');
    btn.textContent = 'Parsing…';
    btn.disabled    = true;

    try {
      switch (_fileType) {
        case 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
          await _parseXLSX();
          break;
        case 'text/csv':
          await _parseCSV();
          break;
        case 'application/json':
          await _parseJSON();
          break;
      }
      _showStep(2);
    } catch (err) {
      _showError('qpUploadError', `Parse error: ${err.message || err}`);
      console.error('[Parser]', err);
    } finally {
      btn.textContent = 'Next: Map columns →';
      btn.disabled    = false;
    }
  }

  /* ── XLSX ── */
  async function _parseXLSX () {
    if (!window.XLSX) throw new Error('SheetJS not loaded. Add the CDN script tag.');
    const buffer   = await _file.arrayBuffer();
    const workbook = XLSX.read(buffer, { type: 'array' });

    _sheetNames = workbook.SheetNames;
    _sheets     = {};

    workbook.SheetNames.forEach(name => {
      const ws   = workbook.Sheets[name];
      const rows = XLSX.utils.sheet_to_json(ws, { defval: '' });
      _sheets[name] = rows;
    });

    // Populate sheet selectors
    _populateSheetSelectors();
    _buildMapper();
  }

  /* ── CSV (single sheet) ── */
  async function _parseCSV () {
    if (!window.XLSX) throw new Error('SheetJS not loaded.');
    const text     = await _file.text();
    const workbook = XLSX.read(text, { type: 'string' });
    _sheetNames    = ['Sheet1'];
    _sheets        = { Sheet1: XLSX.utils.sheet_to_json(workbook.Sheets[workbook.SheetNames[0]], { defval: '' }) };
    document.getElementById('qpSheetSelector').classList.add('hidden');
    _buildMapper();
  }

  /* ── JSON ── */
  async function _parseJSON () {
    const text = await _file.text();
    let data;
    try { data = JSON.parse(text); } catch { throw new Error('Invalid JSON file.'); }

    /* Support two shapes:
       A) Full questionnaire object: { title, description, questions: [...] }
       B) Array of question rows: [ { question_text, ... }, ... ]
    */
    if (Array.isArray(data)) {
      _sheets     = { Questions: data, Meta: [], Choices: [] };
      _sheetNames = ['Meta','Questions','Choices'];
    } else {
      // Extract meta, questions, choices from the object
      const meta = [{ ...data, questions: undefined, choices: undefined }];
      const qs   = data.questions || [];
      const cs   = qs.flatMap((q, qi) => (q.choices || []).map(c => ({ ...c, choice_question_index: qi })));
      _sheets     = { Meta: meta, Questions: qs, Choices: cs };
      _sheetNames = ['Meta','Questions','Choices'];
    }

    document.getElementById('qpSheetSelector').classList.add('hidden');
    _buildMapper();
  }

  /* ─────────────────────────────────────────────────────────────
     SHEET SELECTORS (XLSX only)
  ───────────────────────────────────────────────────────────────*/
  function _populateSheetSelectors () {
    const sel = document.getElementById('qpSheetSelector');
    sel.classList.remove('hidden');

    const noneOpt = '<option value="">— none —</option>';
    const opts    = _sheetNames.map(n => `<option value="${n}">${n}</option>`).join('');

    ['qpMetaSheet','qpQuestionSheet','qpChoiceSheet'].forEach((id, i) => {
      const el = document.getElementById(id);
      el.innerHTML = noneOpt + opts;
      // Auto-select by fuzzy sheet name matching
      const guesses = [
        ['meta','info','questionnaire','settings'],
        ['question','questions','q'],
        ['choice','choices','answer','answers','options'],
      ];
      const match = _sheetNames.find(n => guesses[i].some(g => n.toLowerCase().includes(g)));
      if (match) el.value = match;
    });
  }

  /* ─────────────────────────────────────────────────────────────
     COLUMN MAPPER — auto-detect + allow manual override
  ───────────────────────────────────────────────────────────────*/
function _buildMapper () {
  const mapperEl = document.getElementById('qpMapper');
  mapperEl.innerHTML = '';

  const sections = _getActiveSections();

  /* ── Meta section ── */
  const metaSection = sections[0];
  if (metaSection.sheet && _sheets[metaSection.sheet]?.length) {
    const detected  = _detectColumns(_sheets[metaSection.sheet]);
    const available = ['— skip —', ...detected];
    const sec = document.createElement('div');
    sec.className = 'qp-mapper-section';
    sec.innerHTML = `<h3 class="qp-mapper-section__title">Questionnaire Meta <span class="qp-mapper-section__sheet">(${metaSection.sheet})</span></h3>`;

    const grid = document.createElement('div');
    grid.className = 'qp-mapper-grid';

    META_FIELDS.forEach(field => {
      const autoMatch = _fuzzyMatchColumn(field, detected);
      const row = document.createElement('div');
      row.className = 'qp-mapper-row';
      row.innerHTML = `
        <label class="form-label qp-mapper-row__label" for="qp-map-meta-${field}">${field}</label>
        <div class="qp-mapper-row__combo">
          <select class="form-input qp-mapper-row__select" id="qp-map-meta-${field}" data-prefix="meta" data-field="${field}">
            ${available.map(col => `<option value="${col}" ${col === autoMatch ? 'selected' : ''}>${col}</option>`).join('')}
          </select>
          <!-- Manual override: shown when column not found or user selects "— skip —" -->
          <input
            type="text"
            class="form-input qp-mapper-row__manual"
            id="qp-manual-meta-${field}"
            placeholder="Or type value directly…"
            aria-label="Manual value for ${field}"
          />
        </div>`;
      grid.appendChild(row);
    });

    sec.appendChild(grid);
    mapperEl.appendChild(sec);
  }

  /* ── Questions section ── */
  const qSection = sections[1];
  if (qSection.sheet && _sheets[qSection.sheet]?.length) {
    const detected  = _detectColumns(_sheets[qSection.sheet]);
    const available = ['— skip —', ...detected];
    const sec = document.createElement('div');
    sec.className = 'qp-mapper-section';
    sec.innerHTML = `<h3 class="qp-mapper-section__title">Questions <span class="qp-mapper-section__sheet">(${qSection.sheet})</span></h3>`;

    const grid = document.createElement('div');
    grid.className = 'qp-mapper-grid';

    QUESTION_FIELDS.forEach(field => {
      const autoMatch = _fuzzyMatchColumn(field, detected);
      const row = document.createElement('div');
      row.className = 'qp-mapper-row';
      row.innerHTML = `
        <label class="form-label qp-mapper-row__label" for="qp-map-question-${field}">${field}</label>
        <select class="form-input qp-mapper-row__select" id="qp-map-question-${field}" data-prefix="question" data-field="${field}">
          ${available.map(col => `<option value="${col}" ${col === autoMatch ? 'selected' : ''}>${col}</option>`).join('')}
        </select>`;
      grid.appendChild(row);
    });

    sec.appendChild(grid);
    mapperEl.appendChild(sec);
  }

  /* ── Choices section — custom layout ── */
  const cSection = sections[2];
  if (cSection.sheet && _sheets[cSection.sheet]?.length) {
    const detected  = _detectColumns(_sheets[cSection.sheet]);
    const available = ['— skip —', ...detected];
    mapperEl.appendChild(_buildChoiceMapper(cSection.sheet, detected, available));
  }
}

function _buildChoiceMapper (sheet, detected, available) {
  const sec = document.createElement('div');
  sec.className = 'qp-mapper-section';
  sec.id = 'qpChoiceMapperSection';
  sec.innerHTML = `<h3 class="qp-mapper-section__title">Answer Choices <span class="qp-mapper-section__sheet">(${sheet})</span></h3>`;

  const body = document.createElement('div');
  body.className = 'qp-choice-mapper';

  /* ── Correct answer column ── */
  const correctAutoMatch = _fuzzyMatchColumn('correct_answer', detected)
    || _fuzzyMatchColumn('is_correct', detected)
    || _fuzzyMatchColumn('answer', detected);

  body.innerHTML = `
    <!-- Correct answer -->
    <div class="qp-choice-row-group">
      <label class="form-label">Correct answer column <span class="required-star">*</span></label>
      <select class="form-input" id="qp-map-choice-correct_answer">
        ${available.map(col => `<option value="${col}" ${col === correctAutoMatch ? 'selected' : ''}>${col}</option>`).join('')}
      </select>
      <p class="form-hint">Column whose value is the correct answer text or choice key.</p>
    </div>

    <!-- Other answers (repeatable) -->
    <div class="qp-choice-row-group">
      <label class="form-label">Other answer columns</label>
      <div id="qpOtherAnswersList" class="qp-other-answers-list">
        <!-- Seed one row -->
      </div>
      <button type="button" class="btn-outline qp-add-other-btn" id="qpAddOtherAnswer">
        + Add another answer column
      </button>
      <p class="form-hint">Each column you add becomes a separate wrong-answer choice.</p>
    </div>

    <!-- Key allocation -->
    <div class="qp-choice-row-group">
      <label class="form-label">Choice key column</label>
      <select class="form-input" id="qp-map-choice-choice_key_source">
        ${available.map(col => `<option value="${col}" ${_fuzzyMatchColumn('choice_key', detected) === col ? 'selected' : ''}>${col}</option>`).join('')}
      </select>
      <p class="form-hint">If your file has a key column (A, B, C…) select it here.
        Otherwise choose <em>— skip —</em> and enable auto-assign below.</p>
    </div>

    <!-- Manual key auto-assign toggle -->
    <div class="qp-choice-row-group qp-key-autoassign" id="qpKeyAutoassignWrap">
      <label class="form-label qm-toggle-row" for="qpAutoAssignKeys">
        <input type="checkbox" class="toggle-checkbox" id="qpAutoAssignKeys" checked />
        Auto-assign keys (A, B, C…) when key column is skipped
      </label>
    </div>

    <!-- choice_question_index -->
    <div class="qp-choice-row-group">
      <label class="form-label">Question reference column</label>
      <select class="form-input" id="qp-map-choice-choice_question_index">
        ${available.map(col => `<option value="${col}" ${_fuzzyMatchColumn('choice_question_index', detected) === col ? 'selected' : ''}>${col}</option>`).join('')}
      </select>
      <p class="form-hint">Column that says which question (0-based index) each choice belongs to.</p>
    </div>

    <!-- Partial score -->
    <div class="qp-choice-row-group">
      <label class="form-label">Partial score column</label>
      <select class="form-input" id="qp-map-choice-partial_score">
        ${available.map(col => `<option value="${col}" ${_fuzzyMatchColumn('partial_score', detected) === col ? 'selected' : ''}>${col}</option>`).join('')}
      </select>
    </div>

    <!-- Explanation -->
    <div class="qp-choice-row-group">
      <label class="form-label">Explanation column</label>
      <select class="form-input" id="qp-map-choice-choice_explanation">
        ${available.map(col => `<option value="${col}" ${_fuzzyMatchColumn('choice_explanation', detected) === col ? 'selected' : ''}>${col}</option>`).join('')}
      </select>
    </div>`;

  sec.appendChild(body);

  /* Seed first "other answer" row */
  const otherList = body.querySelector('#qpOtherAnswersList');
  _addOtherAnswerRow(otherList, available, detected);

  /* Add more other-answer columns */
  body.querySelector('#qpAddOtherAnswer').addEventListener('click', () => {
    _addOtherAnswerRow(otherList, available, detected);
  });

  /* Show/hide auto-assign toggle based on key column selection */
  body.querySelector('#qp-map-choice-choice_key_source').addEventListener('change', function () {
    const wrap = body.querySelector('#qpKeyAutoassignWrap');
    wrap.style.display = this.value === '— skip —' ? '' : 'none';
  });

  return sec;
}

function _addOtherAnswerRow (listEl, available, detected) {
  const idx  = listEl.children.length;
  const row  = document.createElement('div');
  row.className = 'qp-other-answer-row';

  /* Try to auto-match: look for columns named wrong_N, option_N, distractor_N etc */
  const guesses = [`wrong_${idx+1}`, `option_${idx+1}`, `distractor_${idx+1}`, `other_${idx+1}`];
  const auto    = available.find(col => guesses.some(g => col.toLowerCase().includes(g))) || '— skip —';

  row.innerHTML = `
    <select class="form-input qp-other-answer-select" aria-label="Other answer column ${idx + 1}">
      ${available.map(col => `<option value="${col}" ${col === auto ? 'selected' : ''}>${col}</option>`).join('')}
    </select>
    <button type="button" class="qp-other-answer-remove" aria-label="Remove this column">
      <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z"/></svg>
    </button>`;

  row.querySelector('.qp-other-answer-remove').addEventListener('click', () => row.remove());
  listEl.appendChild(row);
}

function _getActiveSections () {
    // For CSV/JSON the sheet selector is hidden — use auto-assigned sheet names
    const isXLSX = _fileType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

    const metaSheet     = isXLSX ? document.getElementById('qpMetaSheet').value     : 'Meta';
    const questionSheet = isXLSX ? document.getElementById('qpQuestionSheet').value : 'Questions';
    const choiceSheet   = isXLSX ? document.getElementById('qpChoiceSheet').value   : 'Choices';

    return [
      { label: 'Questionnaire Meta',  sheet: metaSheet,     fields: META_FIELDS,     prefix: 'meta'     },
      { label: 'Questions',           sheet: questionSheet, fields: QUESTION_FIELDS,  prefix: 'question' },
      { label: 'Answer Choices',      sheet: choiceSheet,   fields: CHOICE_FIELDS,    prefix: 'choice'   },
    ];
  }

  function _detectColumns (rows) {
    if (!rows.length) return [];
    return Object.keys(rows[0]);
  }

  function _fuzzyMatchColumn (field, available) {
    const norm = s => s.toLowerCase().replace(/[\s_\-]/g, '');
    for (const col of available) {
      const key = norm(col);
      if (FUZZY_MAP[key] === field || norm(field) === key) return col;
    }
    return '— skip —';
  }

  /* ─────────────────────────────────────────────────────────────
     BUILD REVIEW — reads mapper selects and constructs the payload
  ───────────────────────────────────────────────────────────────*/
  function _buildReview () {
    _hideError('qpMapError');

    try {
      const payload = _extractPayload();
      _renderReview(payload);
      // Cache for apply step
      document.getElementById('qpBtnApply').dataset.payload = JSON.stringify(payload);
      _showStep(3);
    } catch (err) {
      _showError('qpMapError', err.message || String(err));
    }
  }

  function _extractPayload () {
    // Read all mapper selects
    const colFor = (prefix, field) => {
      const el = document.getElementById(`qp-map-${prefix}-${field}`);
      return el ? el.value : '— skip —';
    };
    const val = (row, col) => col === '— skip —' ? '' : (row[col] ?? '');

    const sections = _getActiveSections();
    const metaSection     = sections[0];
    const questionSection = sections[1];
    const choiceSection   = sections[2];

    /* ── Meta (only first non-header row used) ── */
    const metaRows  = metaSection.sheet  ? (_sheets[metaSection.sheet]  || []) : [];
    const metaRow   = metaRows[0] || {};
    const meta = {};
    META_FIELDS.forEach(f => {
      // Use column-mapped value first; fall back to manual text input
      const colVal    = val(metaRow, colFor('meta', f));
      const manualEl  = document.getElementById(`qp-manual-meta-${f}`);
      const manualVal = manualEl ? manualEl.value.trim() : '';
      meta[f] = colVal || manualVal;
    });
    // Uploaded files frequently omit system fields like status; default it
    // so import doesn't fail validation on a field the sheet never had.
    if (!meta.status) meta.status = 'DRAFT';

    /* ── Questions ── */
    const qRows = questionSection.sheet ? (_sheets[questionSection.sheet] || []) : [];
    const questions = qRows.map((row, i) => {
      const q = {};
      QUESTION_FIELDS.forEach(f => { q[f] = val(row, colFor('question', f)); });
      if (!q.order) q.order = i + 1;
      return q;
    }).filter(q => q.question_text);   // skip empty rows

    /* ── Choices — built from correct + other-answer columns ── */
    const cRows       = choiceSection.sheet ? (_sheets[choiceSection.sheet] || []) : [];
    const correctCol  = (document.getElementById('qp-map-choice-correct_answer')        || {}).value || '— skip —';
    const keyCol      = (document.getElementById('qp-map-choice-choice_key_source')      || {}).value || '— skip —';
    const qIdxCol     = (document.getElementById('qp-map-choice-choice_question_index')  || {}).value || '— skip —';
    const partialCol  = (document.getElementById('qp-map-choice-partial_score')          || {}).value || '— skip —';
    const expCol      = (document.getElementById('qp-map-choice-choice_explanation')     || {}).value || '— skip —';
    const autoKeys    = (document.getElementById('qpAutoAssignKeys')                      || {}).checked !== false;

    const otherCols = Array.from(
      document.querySelectorAll('#qpOtherAnswersList .qp-other-answer-select')
    ).map(s => s.value).filter(v => v && v !== '— skip —');

    const KEY_SEQUENCE = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

    const choices = [];

    cRows.forEach(row => {
      const qIdx = qIdxCol !== '— skip —' ? (row[qIdxCol] ?? '') : '';

      // Correct answer
      if (correctCol !== '— skip —' && row[correctCol] !== '' && row[correctCol] !== undefined) {
        const assignedKey = keyCol !== '— skip —'
          ? (row[keyCol] || (autoKeys ? KEY_SEQUENCE[0] : ''))
          : (autoKeys ? KEY_SEQUENCE[0] : '');

        choices.push({
          choice_key:            assignedKey.toString().toUpperCase(),
          choice_text:           String(row[correctCol]),
          is_correct:            'on',
          partial_score:         partialCol !== '— skip —' ? (row[partialCol] ?? '') : '1',
          choice_order:          1,
          choice_explanation:    expCol !== '— skip —' ? (row[expCol] ?? '') : '',
          choice_question_index: qIdx,
        });
      }

      // Other (wrong) answers — each other column becomes one choice
      otherCols.forEach((col, ci) => {
        if (row[col] === '' || row[col] === undefined) return;
        const keyIdx = ci + 1; // offset by 1 because correct answer took index 0
        const assignedKey = autoKeys
          ? (KEY_SEQUENCE[keyIdx] || String(keyIdx + 1))
          : (ci + 2).toString();

        choices.push({
          choice_key:            assignedKey.toUpperCase(),
          choice_text:           String(row[col]),
          is_correct:            '',
          partial_score:         '0',
          choice_order:          keyIdx + 1,
          choice_explanation:    '',
          choice_question_index: qIdx,
        });
      });
    });

    if (!meta.title && !questions.length)
      throw new Error('No usable data found. Check your column mappings.');

    return { meta, questions, choices };
  }

  /* ─────────────────────────────────────────────────────────────
     RENDER REVIEW (Step 3)
  ───────────────────────────────────────────────────────────────*/
  function _renderReview (payload) {
    const { meta, questions, choices } = payload;
    const el = document.getElementById('qpReview');

    el.innerHTML = `
      <div class="qp-review-section">
        <div class="qp-review-section__title">Questionnaire</div>
        ${_reviewRow('Title',       meta.title       || '—')}
        ${_reviewRow('Status',      meta.status      || '—')}
        ${_reviewRow('Max score',   meta.max_score   || '—')}
        ${_reviewRow('Description', (meta.description || '').slice(0,80) || '—')}
      </div>
      <div class="qp-review-section">
        <div class="qp-review-section__title">Questions (${questions.length})</div>
        ${questions.slice(0,5).map((q,i) => _reviewRow(`Q${i+1} (${q.question_type || 'MCQ'})`, q.question_text.slice(0,60))).join('')}
        ${questions.length > 5 ? `<div class="qp-review-more">…and ${questions.length - 5} more</div>` : ''}
      </div>
      <div class="qp-review-section">
        <div class="qp-review-section__title">Choices (${choices.length})</div>
        ${choices.slice(0,4).map(c => _reviewRow(`[${c.choice_key}]`, c.choice_text.slice(0,60))).join('')}
        ${choices.length > 4 ? `<div class="qp-review-more">…and ${choices.length - 4} more</div>` : ''}
      </div>`;
  }

  function _reviewRow (key, val) {
    return `<div class="qp-review-row"><span class="qp-review-row__key">${key}</span><span class="qp-review-row__val">${val}</span></div>`;
  }

  /* ─────────────────────────────────────────────────────────────
     APPLY TO FORM — calls back into questionnare.js
  ───────────────────────────────────────────────────────────────*/
  function _applyToForm () {
    const raw = document.getElementById('qpBtnApply').dataset.payload;
    if (!raw) return;
    const payload = JSON.parse(raw);

    _closeModal();

    // Fire the registered callback (wired in questionnare.js)
    if (typeof _onComplete === 'function') {
      _onComplete(payload);
    }
  }

  /* ─────────────────────────────────────────────────────────────
     ERROR HELPERS
  ───────────────────────────────────────────────────────────────*/
  function _showError (id, msg) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.classList.remove('hidden');
  }

  function _hideError (id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('hidden');
  }

  /* ─────────────────────────────────────────────────────────────
     PUBLIC SURFACE
  ───────────────────────────────────────────────────────────────*/
  return {
    openModal,
    set onComplete (fn) { _onComplete = fn; },
    get onComplete ()   { return _onComplete; },
  };

})();