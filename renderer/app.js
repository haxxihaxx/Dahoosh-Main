/* ─── State ───────────────────────────────────────────────────────────── */
let API_BASE = 'http://localhost:5000';
let backendReady = false;

const state = {
  activeTab: 'grader',
  step: 'idle',           // idle | key_uploaded | student_uploaded | grading | graded
  testId: `T-${Date.now()}`,
  studentId: '',
  answerKeyFile: null,
  studentFile: null,
  gradingResult: null,
  error: null,
  loading: false,
  loadingProgress: 0,
  loadingMsg: '',
  // chatbot
  chatMessages: [],
  chatDocName: null,
  chatDocId: null,
  chatSessionId: `s-${Date.now()}`,
  chatIsLoading: false,
  chatIsIndexing: false,
  // podcast
  podFile: null,
  podLanguage: 'fa',
  podExchanges: 8,
  podMode: 'full',
  podIsLoading: false,
  podGenerated: false,
  podScript: [],
  podTitle: '',
  podDownloadUrl: null,
  podcastId: null,
  // math
  mathMode: 'text',
  mathProblem: '',
  mathHint: '',
  mathImageFile: null,
  mathImagePreview: null,
  mathIsLoading: false,
  mathResult: null,
  mathExpandedSteps: new Set(),
};

/* ─── Utilities ───────────────────────────────────────────────────────── */
const fmt = n => {
  if (n < 1024)         return `${n} B`;
  if (n < 1024 * 1024)  return `${(n/1024).toFixed(1)} KB`;
  return `${(n/1024/1024).toFixed(1)} MB`;
};

function dots(dark = false) {
  return `<span class="dots${dark ? ' dark' : ''}"><span></span><span></span><span></span></span>`;
}

let progTimer = null;
function startProgress(msg, slow = false) {
  state.loadingProgress = 0; state.loadingMsg = msg; state.loading = true;
  renderLoadBar();
  let current = 0;
  if (progTimer) clearInterval(progTimer);
  progTimer = setInterval(() => {
    const rem = 95 - current;
    const s = slow ? Math.max(rem * 0.025, 0.08) : Math.max(rem * 0.07, 0.15);
    current = Math.min(current + s, 95);
    state.loadingProgress = parseFloat(current.toFixed(1));
    renderLoadBar();
  }, 80);
}
function finishProgress() {
  if (progTimer) clearInterval(progTimer);
  state.loadingProgress = 100;
  renderLoadBar();
  setTimeout(() => {
    state.loadingProgress = 0; state.loading = false; state.loadingMsg = '';
    renderLoadBar();
  }, 300);
}
function renderLoadBar() {
  const bar = document.getElementById('loadBar');
  const msg = document.getElementById('loadMsg');
  if (!bar) return;
  bar.style.width = state.loadingProgress + '%';
  if (state.loadingMsg && state.loading) {
    msg.style.display = ''; msg.textContent = state.loadingMsg;
  } else {
    msg.style.display = 'none';
  }
}

function setStatus(ok, text) {
  const dot = document.getElementById('statusDot');
  const txt = document.getElementById('statusTxt');
  if (!dot) return;
  dot.className = 'status-dot' + (ok ? '' : ' err');
  txt.className = 'status-txt' + (ok ? '' : ' err');
  txt.textContent = text;
}

/* ─── API helpers ─────────────────────────────────────────────────────── */
async function apiFetch(path, opts = {}) {
  const res = await fetch(API_BASE + path, opts);
  const data = await res.json();
  return data;
}

/* ─── Grader Tab ──────────────────────────────────────────────────────── */
function updateProgress() {
  const idx = { idle:0, key_uploaded:1, student_uploaded:2, grading:2, graded:3 }[state.step];
  const pct = (idx / 3) * 100;
  document.getElementById('progFill').style.width = pct + '%';
  ['pst0','pst1','pst2','pst3'].forEach((id, i) => {
    document.getElementById(id).className = 'prog-st' + (i <= idx ? ' done' : '');
  });
}

async function uploadAnswerKey(file) {
  startProgress('در حال بارگذاري كليد پاسخ...');
  const form = new FormData();
  form.append('file', file); form.append('exam_type', 'descriptive');
  try {
    const data = await apiFetch(`/api/upload-answer-key/${state.testId}`, { method:'POST', body:form });
    if (!data.success) throw new Error(data.error);
    state.answerKeyFile = { name: file.name, size: file.size };
    state.step = 'key_uploaded';
    renderGraderPanel();
  } catch(e) {
    state.error = e.message;
    renderGraderPanel();
  } finally { finishProgress(); }
}

async function uploadStudentAnswers(file) {
  if (!state.studentId.trim()) { state.error = 'شناسه دانش‌آموز الزامي است'; renderGraderPanel(); return; }
  startProgress('در حال بارگذاري پاسخ‌نامه...');
  const form = new FormData();
  form.append('file', file); form.append('student_id', state.studentId);
  try {
    const data = await apiFetch(`/api/upload-student-answers/${state.testId}`, { method:'POST', body:form });
    if (!data.success) throw new Error(data.error);
    state.studentFile = { name: file.name, size: file.size, filepath: data.filepath };
    state.step = 'student_uploaded';
    renderGraderPanel();
  } catch(e) {
    state.error = e.message;
    renderGraderPanel();
  } finally { finishProgress(); }
}

async function gradeTest() {
  if (!state.studentFile?.filepath) return;
  startProgress('هوش مصنوعي در حال تصحيح...', true);
  state.step = 'grading'; state.error = null;
  renderGraderPanel();
  try {
    const data = await apiFetch(`/api/grade-test/${state.testId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_id: state.studentId, student_answer_file: state.studentFile.filepath }),
    });
    if (!data.success) throw new Error(data.error);
    state.gradingResult = data.grading_result;
    state.step = 'graded';
    renderGraderPanel();
  } catch(e) {
    state.error = e.message;
    state.step = 'student_uploaded';
    renderGraderPanel();
  } finally { finishProgress(); }
}

async function downloadReport() {
  startProgress('در حال آماده‌سازي گزارش PDF...');
  try {
    const res = await fetch(`${API_BASE}/api/download-report/${state.testId}/${state.studentId}`);
    if (!res.ok) throw new Error('خطا در دريافت گزارش');
    const blob = await res.blob();
    // Use Electron save dialog
    if (window.electron) {
      const { filePath } = await window.electron.showSaveDialog({
        defaultPath: `dahoosh_${state.testId}_${state.studentId}.pdf`,
        filters: [{ name: 'PDF', extensions: ['pdf'] }],
      });
      if (filePath) {
        const buf = await blob.arrayBuffer();
        await window.electron.saveFile({ filePath, buffer: Array.from(new Uint8Array(buf)) });
      }
    } else {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `dahoosh_${state.testId}_${state.studentId}.pdf`;
      a.click(); URL.revokeObjectURL(url);
    }
  } catch(e) {
    state.error = e.message; renderGraderPanel();
  } finally { finishProgress(); }
}

function scoreRingSVG(score) {
  const score20 = Math.round((score / 100) * 20 * 10) / 10;
  const r = 44, circ = 2 * Math.PI * r;
  const pct = Math.min(Math.max(score, 0), 100) / 100;
  const color = score >= 85 ? '#4ade80' : score >= 60 ? '#C9A84C' : '#f87171';
  return `<svg width="120" height="120" viewBox="0 0 120 120" class="score-ring">
    <circle cx="60" cy="60" r="${r}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="8"/>
    <circle cx="60" cy="60" r="${r}" fill="none" stroke="${color}" stroke-width="8"
      stroke-dasharray="${circ * pct} ${circ}" stroke-linecap="round"
      transform="rotate(-90 60 60)"
      style="transition:stroke-dasharray 1s cubic-bezier(0.16,1,0.3,1);filter:drop-shadow(0 0 6px ${color}80)"/>
    <text x="60" y="52" text-anchor="middle" dominant-baseline="middle" fill="${color}" font-size="22" font-weight="700" font-family="Vazirmatn,sans-serif">${score20.toFixed(1)}</text>
    <text x="60" y="70" text-anchor="middle" dominant-baseline="middle" fill="rgba(255,255,255,0.35)" font-size="10" font-family="Vazirmatn,sans-serif">از ۲۰</text>
  </svg>`;
}

function errorHtml() {
  if (!state.error) return '';
  return `<div class="err-wrap">
    <p class="err-msg">${state.error}</p>
    <button class="err-close" onclick="state.error=null;renderGraderPanel()">×</button>
  </div>`;
}

function renderGraderPanel() {
  updateProgress();
  const body = document.getElementById('cardBody');
  let html = '';
  if (state.error) html += errorHtml();

  if (state.step === 'idle') {
    html += `<div class="panel">
      <div class="eyebrow">مرحله ۱ از ۴</div>
      <h2 class="heading">كليد پاسخ را بارگذاري كنيد</h2>
      <p class="subtext">فايل PDF يا تصويري حاوي پاسخ‌هاي صحيح آزمون را انتخاب كنيد.</p>
      <div class="dropzone" id="dzKey">
        <div class="dz-icon"><div class="dz-icon-shape"></div></div>
        <p class="dz-title"><span>انتخاب فايل</span> يا رها كردن اينجا</p>
        <p class="dz-hint">PDF, PNG, JPG — حداكثر ۱۶ مگابايت</p>
      </div>
      <input type="file" id="fileKey" accept=".pdf,.png,.jpg,.jpeg" style="display:none">
      ${state.loading ? `<div class="dots-center">${dots()}</div>` : ''}
    </div>`;
  } else if (state.step === 'key_uploaded') {
    html += `<div class="panel">
      <div class="eyebrow">مرحله ۲ از ۴</div>
      <h2 class="heading">پاسخ‌نامه دانش‌آموز</h2>
      <p class="subtext">شناسه دانش‌آموز را وارد كرده و فايل پاسخ‌هايش را بارگذاري كنيد.</p>
      ${state.answerKeyFile ? `<div class="file-tag"><div class="file-tag-dot"></div><div class="file-tag-info"><div class="file-tag-name">${state.answerKeyFile.name}</div><div class="file-tag-size">${fmt(state.answerKeyFile.size)}</div></div><span class="file-tag-badge">كليد تاييد شد</span></div>` : ''}
      <div class="field-wrap">
        <label class="field-label">شناسه دانش‌آموز <span class="field-req">*</span></label>
        <input class="field-input" id="studentIdInput" type="text" placeholder="student001" value="${state.studentId}">
      </div>
      <div class="dropzone" id="dzStudent">
        <div class="dz-icon"><div class="dz-icon-shape"></div></div>
        <p class="dz-title"><span>انتخاب پاسخ‌نامه</span> يا رها كردن اينجا</p>
        <p class="dz-hint">PDF, PNG, JPG</p>
      </div>
      <input type="file" id="fileStudent" accept=".pdf,.png,.jpg,.jpeg" style="display:none">
      ${state.loading ? `<div class="dots-center">${dots()}</div>` : ''}
    </div>`;
  } else if (state.step === 'student_uploaded') {
    html += `<div class="panel">
      <div class="eyebrow">مرحله ۳ از ۴</div>
      <h2 class="heading">آماده براي تصحيح</h2>
      <p class="subtext">هر دو فايل بارگذاري شدند. تصحيح هوشمند آماده شروع است.</p>
      <div class="review-item"><div class="review-sq a"><div class="review-sq-inner"></div></div><div class="review-info"><div class="review-label">كليد پاسخ</div><div class="review-val">${state.answerKeyFile?.name}</div><div class="review-sz">${fmt(state.answerKeyFile?.size||0)}</div></div></div>
      <div class="review-item"><div class="review-sq b"><div class="review-sq-inner ok"></div></div><div class="review-info"><div class="review-label">پاسخ‌نامه — ${state.studentId}</div><div class="review-val">${state.studentFile?.name}</div><div class="review-sz">${fmt(state.studentFile?.size||0)}</div></div></div>
      <div class="actions">
        <button class="btn btn-gold" id="btnGrade" ${state.loading ? 'disabled' : ''}>
          ${state.loading ? `${dots(true)} شروع...` : 'شروع تصحيح هوشمند'}
        </button>
      </div>
    </div>`;
  } else if (state.step === 'grading') {
    html += `<div class="panel"><div class="grading-center">
      <div class="orb"><div class="orb-inner"><div class="orb-cross"></div></div></div>
      <div><div class="grading-title">در حال تصحيح...</div><p class="grading-sub">مدل هوش مصنوعي در حال بررسي دقيق پاسخ‌هاست</p></div>
      ${dots()}
    </div></div>`;
  } else if (state.step === 'graded' && state.gradingResult) {
    const r = state.gradingResult;
    html += `<div class="panel">
      <div class="done-tag"><div class="done-tag-dot"></div><span class="done-tag-text">تصحيح كامل شد</span></div>
      <div class="result-header">
        ${scoreRingSVG(r.score)}
        <div class="result-text">
          <div class="result-label">نتيجه ارزيابي</div>
          <div class="result-grade">${r.grade}</div>
          <div class="result-sub">نمره ${((r.score/100)*20).toFixed(1)} از ۲۰</div>
        </div>
      </div>
      <div class="meta-row">
        <div class="meta-box"><div class="meta-box-label">شناسه آزمون</div><div class="meta-box-val">${state.testId}</div></div>
        <div class="meta-box"><div class="meta-box-label">دانش‌آموز</div><div class="meta-box-val">${state.studentId}</div></div>
      </div>
      <div class="actions">
        <button class="btn btn-ok" id="btnDownload">دانلود گزارش PDF</button>
        <button class="btn btn-ghost" id="btnNewTest">آزمون جديد</button>
      </div>
    </div>`;
  }

  body.innerHTML = html;
  bindGraderEvents();
}

function bindGraderEvents() {
  const dzKey = document.getElementById('dzKey');
  const fileKey = document.getElementById('fileKey');
  if (dzKey) {
    dzKey.addEventListener('click', () => !state.loading && fileKey.click());
    dzKey.addEventListener('dragover', e => { e.preventDefault(); dzKey.classList.add('over'); });
    dzKey.addEventListener('dragleave', () => dzKey.classList.remove('over'));
    dzKey.addEventListener('drop', e => { e.preventDefault(); dzKey.classList.remove('over'); const f=e.dataTransfer.files[0]; if(f) uploadAnswerKey(f); });
    fileKey.addEventListener('change', e => { const f=e.target.files[0]; if(f) uploadAnswerKey(f); e.target.value=''; });
  }
  const dzStu = document.getElementById('dzStudent');
  const fileStu = document.getElementById('fileStudent');
  const stuInput = document.getElementById('studentIdInput');
  if (stuInput) stuInput.addEventListener('input', e => state.studentId = e.target.value);
  if (dzStu) {
    dzStu.addEventListener('click', () => !state.loading && fileStu.click());
    dzStu.addEventListener('dragover', e => { e.preventDefault(); dzStu.classList.add('over'); });
    dzStu.addEventListener('dragleave', () => dzStu.classList.remove('over'));
    dzStu.addEventListener('drop', e => { e.preventDefault(); dzStu.classList.remove('over'); const f=e.dataTransfer.files[0]; if(f) uploadStudentAnswers(f); });
    fileStu.addEventListener('change', e => { const f=e.target.files[0]; if(f) uploadStudentAnswers(f); e.target.value=''; });
  }
  const btnGrade = document.getElementById('btnGrade');
  if (btnGrade) btnGrade.addEventListener('click', gradeTest);
  const btnDL = document.getElementById('btnDownload');
  if (btnDL) btnDL.addEventListener('click', downloadReport);
  const btnNew = document.getElementById('btnNewTest');
  if (btnNew) btnNew.addEventListener('click', () => {
    state.step='idle'; state.answerKeyFile=null; state.studentFile=null;
    state.gradingResult=null; state.studentId=''; state.error=null;
    state.testId=`T-${Date.now()}`;
    document.getElementById('footTestId').textContent = state.testId;
    renderGraderPanel();
  });
}

/* ─── Chatbot Tab ─────────────────────────────────────────────────────── */
function renderChatbotTab() {
  const body = document.getElementById('cardBody');
  const dotStatus = state.chatDocId
    ? `<span class="chat-doc-dot active"></span><span class="chat-doc-name">${state.chatDocName}</span><span class="chat-doc-badge">RAG فعال</span>`
    : state.chatIsIndexing
    ? `<span class="chat-doc-dot" style="background:#C9A84C;animation:pulse 1s infinite"></span><span class="chat-doc-name">در حال فهرست‌بندي...</span>`
    : `<span class="chat-doc-dot"></span><span class="chat-doc-empty">هيچ سندي بارگذاري نشده — مي‌توانيد بدون سند هم چت كنيد</span>`;

  const messagesHtml = state.chatMessages.length === 0
    ? `<div class="chat-empty"><div class="chat-empty-icon">◉</div><p>يك سند PDF يا TXT بارگذاري كنيد يا مستقيماً سوال بپرسيد.</p></div>`
    : state.chatMessages.map(m => `<div class="chat-bubble ${m.role}"><div class="chat-bubble-inner">${escHtml(m.content)}</div></div>`).join('')
      + (state.chatIsLoading ? `<div class="chat-bubble assistant"><div class="chat-bubble-inner">${dots()}</div></div>` : '');

  body.innerHTML = `
    <div class="tab-panel" style="display:flex;flex-direction:column;height:100%">
      <div class="chat-doc-bar">
        <div class="chat-doc-info">${dotStatus}</div>
        <button class="chat-doc-btn" id="chatDocBtn" ${state.chatIsIndexing?'disabled':''}>
          ${state.chatDocId ? 'تغيير سند' : 'بارگذاري PDF/TXT'}
        </button>
        <input type="file" id="chatFileInput" accept=".pdf,.txt" style="display:none">
      </div>
      <div class="chat-messages" id="chatMessages">${messagesHtml}</div>
      <div class="chat-input-row">
        <input class="chat-input" id="chatInput" placeholder="سوال خود را بنويسيد..." value="" ${state.chatIsLoading?'disabled':''}>
        <button class="chat-send-btn" id="chatSendBtn" ${state.chatIsLoading?'disabled':''}>ارسال</button>
      </div>
    </div>`;

  // scroll to bottom
  const msgs = document.getElementById('chatMessages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;

  document.getElementById('chatDocBtn').addEventListener('click', () => {
    document.getElementById('chatFileInput').click();
  });
  document.getElementById('chatFileInput').addEventListener('change', async e => {
    const file = e.target.files[0]; if (!file) return;
    e.target.value = '';
    state.chatIsIndexing = true; renderChatbotTab();
    const form = new FormData();
    form.append('file', file); form.append('doc_id', `doc-${Date.now()}`);
    try {
      const data = await apiFetch('/api/rag/index', { method:'POST', body:form });
      if (!data.success) throw new Error(data.error);
      state.chatDocName = file.name; state.chatDocId = data.doc_id;
      state.chatMessages = [{ role:'assistant', content:`✅ سند «${file.name}» با موفقيت فهرست‌بندي شد (${data.chunks_created} بخش). اكنون مي‌توانيد سوال بپرسيد.` }];
    } catch(e) {
      state.chatMessages.push({ role:'assistant', content:'خطا: ' + e.message });
    } finally { state.chatIsIndexing = false; renderChatbotTab(); }
  });

  const chatInput = document.getElementById('chatInput');
  const sendMsg = async () => {
    const msg = chatInput.value.trim(); if (!msg || state.chatIsLoading) return;
    chatInput.value = '';
    state.chatMessages.push({ role:'user', content:msg });
    state.chatIsLoading = true; renderChatbotTab();
    try {
      let reply = '';
      if (state.chatDocId) {
        const data = await apiFetch('/api/rag/query', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ question:msg, doc_id:state.chatDocId, top_k:5 }) });
        if (!data.success) throw new Error(data.error);
        reply = data.answer;
      } else {
        const data = await apiFetch('/api/chatbot/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ session_id:state.chatSessionId, message:msg }) });
        if (!data.success) throw new Error(data.error);
        reply = data.reply;
      }
      state.chatMessages.push({ role:'assistant', content:reply });
    } catch(e) {
      state.chatMessages.push({ role:'assistant', content:'خطا: ' + e.message });
    } finally { state.chatIsLoading = false; renderChatbotTab(); }
  };
  document.getElementById('chatSendBtn').addEventListener('click', sendMsg);
  chatInput.addEventListener('keydown', e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(); } });
}

/* ─── Podcast Tab ─────────────────────────────────────────────────────── */
function renderPodcastTab() {
  const body = document.getElementById('cardBody');

  const dropzoneContent = state.podFile
    ? `<div class="pod-file-info">
        <div class="pod-file-icon">📄</div>
        <div><div class="pod-file-name">${state.podFile.name}</div><div class="pod-file-size">${fmt(state.podFile.size)}</div></div>
        <button class="pod-file-remove" id="podRemoveFile">×</button>
      </div>`
    : `<div class="pod-dz-icon">🎙️</div>
       <div class="pod-dz-text"><span>انتخاب فايل</span> يا رها كردن اينجا</div>
       <div class="pod-dz-hint">PDF يا TXT — محتواي سند به پادكست تبديل مي‌شود</div>`;

  const resultHtml = state.podGenerated ? `
    <div class="pod-result" style="animation:slideUp .4s cubic-bezier(.16,1,.3,1)">
      <div class="pod-result-head">
        <div>
          <div class="done-tag" style="margin-bottom:.5rem"><div class="done-tag-dot"></div><span class="done-tag-text">${state.podMode==='full'?'پادكست آماده شد':'اسكريپت آماده شد'}</span></div>
          <div class="pod-title">${state.podTitle}</div>
        </div>
        ${state.podDownloadUrl ? `<button class="btn btn-gold" id="btnPodDownload">⬇ دانلود MP3</button>` : ''}
      </div>
      <div class="pod-script-viewer">
        ${state.podScript.map(l => `<div class="pod-script-line ${l.speaker==='Alex'?'alex':'sara'}">
          <div class="pod-speaker-badge">${l.speaker}</div>
          <div class="pod-line-text">${escHtml(l.line)}</div>
        </div>`).join('')}
      </div>
    </div>` : '';

  body.innerHTML = `
    <div class="tab-panel">
      <div class="pod-dropzone${state.podFile?' has-file':''}" id="podDz">${dropzoneContent}</div>
      <input type="file" id="podFileInput" accept=".pdf,.txt" style="display:none">
      <div class="pod-settings">
        <div class="pod-field">
          <label class="pod-label">زبان پادكست</label>
          <div class="pod-options">
            <button class="pod-opt${state.podLanguage==='fa'?' active':''}" data-lang="fa">فارسي</button>
            <button class="pod-opt${state.podLanguage==='en'?' active':''}" data-lang="en">English</button>
          </div>
        </div>
        <div class="pod-field">
          <label class="pod-label">تعداد تبادل گفتگو</label>
          <div class="pod-options">
            ${[4,6,8,12].map(n=>`<button class="pod-opt${state.podExchanges===n?' active':''}" data-ex="${n}">${n}</button>`).join('')}
          </div>
        </div>
        <div class="pod-field">
          <label class="pod-label">حالت خروجي</label>
          <div class="pod-options">
            <button class="pod-opt${state.podMode==='full'?' active':''}" data-mode="full">🎵 پادكست صوتي كامل</button>
            <button class="pod-opt${state.podMode==='script'?' active':''}" data-mode="script">📝 اسكريپت فقط</button>
          </div>
        </div>
      </div>
      <button class="btn btn-gold" id="btnGenPod" ${state.podIsLoading||!state.podFile?'disabled':''} style="width:100%;margin-bottom:1.5rem">
        ${state.podIsLoading ? `${dots(true)} ${state.podMode==='full'?' در حال توليد پادكست...':' در حال نوشتن اسكريپت...'}` : (state.podMode==='full'?'🎙️ توليد پادكست با صدا':'📝 توليد اسكريپت')}
      </button>
      ${state.podIsLoading ? `<div class="pod-loading"><div class="pod-loading-bars">${[0,1,2,3,4,5,6,7].map(i=>`<div class="pod-bar" style="animation-delay:${i*.1}s"></div>`).join('')}</div><p class="pod-loading-txt">${state.podMode==='full'?'هوش مصنوعي در حال نوشتن اسكريپت و توليد صدا...':'هوش مصنوعي در حال نوشتن اسكريپت...'}</p></div>` : ''}
      ${resultHtml}
    </div>`;

  const podDz = document.getElementById('podDz');
  const podFileInput = document.getElementById('podFileInput');

  if (!state.podFile) {
    podDz.addEventListener('click', () => !state.podIsLoading && podFileInput.click());
    podDz.addEventListener('dragover', e => { e.preventDefault(); podDz.classList.add('over'); });
    podDz.addEventListener('dragleave', () => podDz.classList.remove('over'));
    podDz.addEventListener('drop', e => { e.preventDefault(); podDz.classList.remove('over'); const f=e.dataTransfer.files[0]; if(f) { state.podFile=f; state.podGenerated=false; renderPodcastTab(); } });
  }
  podFileInput.addEventListener('change', e => { const f=e.target.files[0]; if(f){ state.podFile=f; state.podGenerated=false; renderPodcastTab(); } e.target.value=''; });

  const removeBtn = document.getElementById('podRemoveFile');
  if (removeBtn) removeBtn.addEventListener('click', e => { e.stopPropagation(); state.podFile=null; state.podGenerated=false; renderPodcastTab(); });

  document.querySelectorAll('[data-lang]').forEach(b => b.addEventListener('click', () => { state.podLanguage=b.dataset.lang; renderPodcastTab(); }));
  document.querySelectorAll('[data-ex]').forEach(b => b.addEventListener('click', () => { state.podExchanges=+b.dataset.ex; renderPodcastTab(); }));
  document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => { state.podMode=b.dataset.mode; renderPodcastTab(); }));

  const btnGen = document.getElementById('btnGenPod');
  if (btnGen) btnGen.addEventListener('click', async () => {
    if (!state.podFile || state.podIsLoading) return;
    state.podIsLoading=true; state.podGenerated=false; state.podScript=[]; state.podDownloadUrl=null; renderPodcastTab();
    const form = new FormData();
    form.append('file', state.podFile); form.append('language', state.podLanguage); form.append('num_exchanges', String(state.podExchanges));
    try {
      const endpoint = state.podMode==='full' ? '/api/podcast/generate' : '/api/podcast/script';
      const data = await apiFetch(endpoint, { method:'POST', body:form });
      if (!data.success) throw new Error(data.error);
      state.podTitle = data.title || 'پادكست هوش مصنوعي';
      state.podScript = data.script || [];
      if (data.podcast_id) { state.podcastId=data.podcast_id; state.podDownloadUrl=`${API_BASE}/api/podcast/download/${data.podcast_id}`; }
      state.podGenerated = true;
    } catch(e) {
      alert('خطا: ' + e.message);
    } finally { state.podIsLoading=false; renderPodcastTab(); }
  });

  const btnPodDL = document.getElementById('btnPodDownload');
  if (btnPodDL) btnPodDL.addEventListener('click', async () => {
    if (!state.podDownloadUrl) return;
    try {
      const res = await fetch(state.podDownloadUrl);
      if (!res.ok) throw new Error('دانلود ناموفق');
      const blob = await res.blob();
      if (window.electron) {
        const { filePath } = await window.electron.showSaveDialog({ defaultPath:`podcast_${state.podcastId}.mp3`, filters:[{name:'MP3',extensions:['mp3']}] });
        if (filePath) { const buf=await blob.arrayBuffer(); await window.electron.saveFile({ filePath, buffer:Array.from(new Uint8Array(buf)) }); }
      } else {
        const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`podcast_${state.podcastId}.mp3`; a.click(); URL.revokeObjectURL(url);
      }
    } catch(e) { alert('خطا: ' + e.message); }
  });
}

/* ─── Math Solver Tab ─────────────────────────────────────────────────── */
function renderMathTab() {
  const body = document.getElementById('cardBody');
  const diffColor = { easy:'#4ade80', medium:'#C9A84C', hard:'#f87171', unknown:'#888' };

  const resultHtml = state.mathResult ? (() => {
    const r = state.mathResult;
    const stepsHtml = (r.steps||[]).map((step, i) => `
      <div class="math-step${state.mathExpandedSteps.has(i)?' expanded':''}" data-stepidx="${i}">
        <button class="math-step-header">
          <div class="math-step-num">گام ${step.step_number}</div>
          <div class="math-step-title">${escHtml(step.title)}</div>
          <div class="math-step-chevron">${state.mathExpandedSteps.has(i)?'▲':'▼'}</div>
        </button>
        ${state.mathExpandedSteps.has(i) ? `<div class="math-step-body">
          ${step.explanation ? `<p class="math-step-explanation">${escHtml(step.explanation)}</p>` : ''}
          ${step.math ? `<div class="math-formula">${escHtml(step.math)}</div>` : ''}
        </div>` : ''}
      </div>`).join('');
    return `<div class="math-result" style="animation:slideUp .4s cubic-bezier(.16,1,.3,1)">
      <div class="math-result-header">
        <div class="done-tag" style="margin-bottom:0"><div class="done-tag-dot"></div><span class="done-tag-text">مسئله حل شد</span></div>
        <div class="math-meta">
          ${r.problem_type?`<span class="math-tag">${escHtml(r.problem_type)}</span>`:''}
          ${r.difficulty?`<span class="math-difficulty" style="color:${diffColor[r.difficulty]||'#888'}">● ${r.difficulty==='easy'?'آسان':r.difficulty==='medium'?'متوسط':r.difficulty==='hard'?'دشوار':r.difficulty}</span>`:''}
        </div>
      </div>
      ${r.identified_problem?`<div class="math-identified"><div class="math-section-label">مسئله شناسايي شده</div><div class="math-identified-text">${escHtml(r.identified_problem)}</div></div>`:''}
      ${(r.steps||[]).length>0?`<div class="math-steps"><div class="math-section-label">حل گام‌به‌گام</div>${stepsHtml}</div>`:''}
      ${r.answer_summary?`<div class="math-answer-box"><div class="math-answer-label">📌 پاسخ نهايي</div><div class="math-answer-text">${escHtml(r.final_answer||r.answer_summary)}</div></div>`:''}
      ${(r.topics||[]).length>0?`<div class="math-topics">${r.topics.map(t=>`<span class="math-topic-chip">${escHtml(t)}</span>`).join('')}</div>`:''}
    </div>`;
  })() : '';

  const inputSection = state.mathMode === 'text'
    ? `<div class="field-wrap"><label class="field-label">مسئله رياضي <span class="field-req">*</span></label>
       <textarea class="field-input math-textarea" id="mathProblem" placeholder="مسئله رياضي خود را اينجا بنويسيد..." rows="5">${state.mathProblem}</textarea></div>`
    : `<div class="math-dropzone${state.mathImageFile?' has-file':''}" id="mathDz">
        ${state.mathImageFile && state.mathImagePreview
          ? `<div class="math-img-preview-wrap"><img src="${state.mathImagePreview}" class="math-img-preview" alt="math"><button class="math-img-remove" id="mathImgRemove">×</button></div>`
          : `<div class="math-dz-icon">∑</div><div class="math-dz-text"><span>انتخاب تصوير</span> يا رها كردن اينجا</div><div class="math-dz-hint">PNG, JPG, JPEG, WEBP</div>`}
       </div>
       <input type="file" id="mathImgInput" accept="image/*" style="display:none">
       <div class="field-wrap" style="margin-top:1rem;margin-bottom:0"><label class="field-label">راهنمايي اضافي (اختياري)</label>
       <input class="field-input" id="mathHint" placeholder="مثال: اين مسئله مربوط به هندسه مثلثاتي است" value="${escHtml(state.mathHint)}"></div>`;

  const solveDisabled = state.mathIsLoading || (state.mathMode==='text'?!state.mathProblem.trim():!state.mathImageFile);

  body.innerHTML = `
    <div class="tab-panel">
      <div class="math-mode-switch">
        <button class="math-mode-btn${state.mathMode==='text'?' active':''}" data-mathmode="text">✏️ متن مسئله</button>
        <button class="math-mode-btn${state.mathMode==='image'?' active':''}" data-mathmode="image">📷 تصوير مسئله</button>
      </div>
      ${inputSection}
      <button class="btn btn-gold" id="btnSolveMath" ${solveDisabled?'disabled':''} style="width:100%;margin-top:1.25rem;margin-bottom:1.5rem">
        ${state.mathIsLoading ? `${dots(true)} هوش مصنوعي در حال حل مسئله...` : '🔍 حل مسئله'}
      </button>
      ${state.mathIsLoading?`<div class="pod-loading"><div class="pod-loading-bars">${[0,1,2,3,4,5,6,7].map(i=>`<div class="pod-bar" style="animation-delay:${i*.1}s"></div>`).join('')}</div><p class="pod-loading-txt">مدل رياضي در حال تحليل و حل گام‌به‌گام مسئله...</p></div>`:''}
      ${resultHtml}
    </div>`;

  document.querySelectorAll('[data-mathmode]').forEach(b => b.addEventListener('click', () => { state.mathMode=b.dataset.mathmode; state.mathResult=null; renderMathTab(); }));

  const mathProblem = document.getElementById('mathProblem');
  if (mathProblem) mathProblem.addEventListener('input', e => { state.mathProblem=e.target.value; });

  const mathHint = document.getElementById('mathHint');
  if (mathHint) mathHint.addEventListener('input', e => state.mathHint=e.target.value);

  const mathDz = document.getElementById('mathDz');
  const mathImgInput = document.getElementById('mathImgInput');
  if (mathDz && !state.mathImageFile) {
    mathDz.addEventListener('click', () => !state.mathIsLoading && mathImgInput.click());
    mathDz.addEventListener('dragover', e => { e.preventDefault(); mathDz.classList.add('over'); });
    mathDz.addEventListener('dragleave', () => mathDz.classList.remove('over'));
    mathDz.addEventListener('drop', e => { e.preventDefault(); mathDz.classList.remove('over'); handleMathImage(e.dataTransfer.files[0]); });
  }
  if (mathImgInput) mathImgInput.addEventListener('change', e => { handleMathImage(e.target.files[0]); e.target.value=''; });
  const removeBtn = document.getElementById('mathImgRemove');
  if (removeBtn) removeBtn.addEventListener('click', e => { e.stopPropagation(); state.mathImageFile=null; state.mathImagePreview=null; state.mathResult=null; renderMathTab(); });

  // Step toggle
  document.querySelectorAll('.math-step').forEach(el => {
    el.querySelector('.math-step-header')?.addEventListener('click', () => {
      const idx = +el.dataset.stepidx;
      if (state.mathExpandedSteps.has(idx)) state.mathExpandedSteps.delete(idx);
      else state.mathExpandedSteps.add(idx);
      renderMathTab();
    });
  });

  const btnSolve = document.getElementById('btnSolveMath');
  if (btnSolve) btnSolve.addEventListener('click', async () => {
    if (state.mathIsLoading) return;
    state.mathIsLoading=true; state.mathResult=null; state.mathExpandedSteps=new Set(); renderMathTab();
    try {
      let data;
      if (state.mathMode==='text') {
        data = await apiFetch('/api/math/solve-text', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ problem:state.mathProblem.trim() }) });
      } else {
        const form = new FormData();
        form.append('file', state.mathImageFile);
        if (state.mathHint.trim()) form.append('hint', state.mathHint.trim());
        data = await apiFetch('/api/math/solve-image', { method:'POST', body:form });
      }
      if (!data.success) throw new Error(data.error);
      state.mathResult = data;
      state.mathExpandedSteps = new Set((data.steps||[]).map((_,i)=>i));
    } catch(e) {
      alert('خطا: ' + e.message);
    } finally { state.mathIsLoading=false; renderMathTab(); }
  });
}

function handleMathImage(file) {
  if (!file || !file.type.startsWith('image/')) return;
  state.mathImageFile = file;
  const reader = new FileReader();
  reader.onload = ev => { state.mathImagePreview = ev.target.result; renderMathTab(); };
  reader.readAsDataURL(file);
}

/* ─── Tab Routing ─────────────────────────────────────────────────────── */
function renderCurrentTab() {
  const progress = document.getElementById('graderProgress');
  if (progress) progress.style.display = state.activeTab === 'grader' ? '' : 'none';
  switch(state.activeTab) {
    case 'grader':  renderGraderPanel(); break;
    case 'chatbot': renderChatbotTab();  break;
    case 'podcast': renderPodcastTab();  break;
    case 'math':    renderMathTab();     break;
  }
}

document.getElementById('tabNav').addEventListener('click', e => {
  const btn = e.target.closest('[data-tab]');
  if (!btn) return;
  state.activeTab = btn.dataset.tab;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === state.activeTab));
  renderCurrentTab();
});

/* ─── Welcome & Splash ────────────────────────────────────────────────── */
function showApp() {
  document.getElementById('welcome').classList.add('hidden');
  document.getElementById('appMain').style.display = '';
  document.getElementById('footTestId').textContent = state.testId;
  renderCurrentTab();
}

document.getElementById('enterBtn').addEventListener('click', showApp);

function hideSplash() {
  const splash = document.getElementById('splash');
  splash.classList.add('hidden');
  setTimeout(() => splash.remove(), 700);
  document.getElementById('welcome').classList.remove('hidden');
  setStatus(true, 'آنلاين');
}

function showSplashError(msg) {
  document.getElementById('splashMsg').style.display = 'none';
  const err = document.getElementById('splashErr');
  err.style.display = '';
  err.textContent = '⚠️ ' + msg + ' — بررسي كنيد Python نصب است.';
  // Still allow entry after a few seconds
  setTimeout(hideSplash, 4000);
  setStatus(false, 'خطا در اتصال');
}

/* ─── Bootstrap ───────────────────────────────────────────────────────── */
function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

if (window.electron) {
  // Pull-based handshake: we call into main.js *after* this script is
  // fully parsed and running, so the IPC invoke can never arrive before
  // we are ready to handle it. The old push approach (onBackendReady)
  // had a race: main.js sent 'backend-ready' on did-finish-load, which
  // fires when the DOM is ready — but *before* app.js had executed and
  // attached the ipcRenderer listener, so the event was silently dropped.
  window.electron.getBackendStatus().then(({ ok, url, message }) => {
    if (ok) {
      API_BASE = url;
      backendReady = true;
      hideSplash();
    } else {
      showSplashError(message || 'سرور در دسترس نيست');
    }
  }).catch(() => {
    showSplashError('خطا در اتصال به سرور');
  });
} else {
  // Running in browser (dev mode) - try to connect directly
  fetch(API_BASE + '/health')
    .then(r => r.json())
    .then(() => hideSplash())
    .catch(() => showSplashError('سرور در دسترس نيست'));
}
