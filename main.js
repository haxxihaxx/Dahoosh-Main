const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const http = require('http');
const fs = require('fs');

let mainWindow = null;
let flaskProcess = null;
const FLASK_PORT = 5000;
const FLASK_URL = `http://localhost:${FLASK_PORT}`;

// ── Python / Flask bootstrap ──────────────────────────────────────────────

function getPythonPath() {
  // 1. Prefer a local virtualenv (works on all platforms)
  const venvPaths = [
    path.join(__dirname, 'venv', 'bin', 'python3'),
    path.join(__dirname, 'venv', 'bin', 'python'),
    path.join(__dirname, 'venv', 'Scripts', 'python.exe'), // Windows venv
  ];
  for (const p of venvPaths) {
    if (fs.existsSync(p)) return p;
  }

  // 2. On Windows, try the Python Launcher (`py`) first — it is immune to
  //    the Microsoft Store stub that intercepts bare `python` / `python3`
  //    commands and redirects to the Store instead of running Python.
  if (process.platform === 'win32') {
    try {
      execSync('py --version', { stdio: 'pipe' });
      return 'py';
    } catch (_) {}

    // 3. Also probe the default CPython install path directly, bypassing
    //    the Store alias entirely.
    const localAppData = process.env.LOCALAPPDATA || '';
    const programFiles  = process.env.PROGRAMFILES  || 'C:\\Program Files';
    const directPaths = [
      path.join(localAppData, 'Programs', 'Python', 'Python313', 'python.exe'),
      path.join(localAppData, 'Programs', 'Python', 'Python312', 'python.exe'),
      path.join(localAppData, 'Programs', 'Python', 'Python311', 'python.exe'),
      path.join(localAppData, 'Programs', 'Python', 'Python310', 'python.exe'),
      path.join(programFiles, 'Python313', 'python.exe'),
      path.join(programFiles, 'Python312', 'python.exe'),
    ];
    for (const p of directPaths) {
      if (fs.existsSync(p)) return p;
    }
  }

  // 4. Last resort: try python3 / python on PATH.
  try { execSync('python3 --version', { stdio: 'pipe' }); return 'python3'; } catch (_) {}
  try { execSync('python --version',  { stdio: 'pipe' }); return 'python';  } catch (_) {}
  return 'python3';
}

function installDependencies(python) {
  const req = path.join(__dirname, 'requirements.txt');
  if (!fs.existsSync(req)) return;
  try {
    execSync(`"${python}" -m pip install -r "${req}" --quiet`, {
      cwd: __dirname,
      stdio: 'pipe',
    });
  } catch (e) {
    console.error('pip install warning:', e.message);
  }
}

function startFlask() {
  const python = getPythonPath();
  const script = path.join(__dirname, 'app.py');

  if (!fs.existsSync(script)) {
    console.error('app.py not found at', script);
    return;
  }

  // Ensure storage dirs exist
  ['uploads', 'storage/answer_keys', 'storage/results', 'storage/podcasts'].forEach(d => {
    fs.mkdirSync(path.join(__dirname, d), { recursive: true });
  });

  flaskProcess = spawn(python, [script], {
    cwd: __dirname,
    env: { ...process.env, FLASK_PORT: String(FLASK_PORT), FLASK_DEBUG: 'False', PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  flaskProcess.stdout.on('data', d => console.log('[Flask]', d.toString().trim()));
  flaskProcess.stderr.on('data', d => console.error('[Flask ERR]', d.toString().trim()));
  flaskProcess.on('close', code => console.log('[Flask] exited', code));
}

function waitForFlask(retries = 40, delay = 500) {
  return new Promise((resolve, reject) => {
    const attempt = () => {
      http.get(`${FLASK_URL}/health`, res => {
        if (res.statusCode === 200) return resolve();
        retry();
      }).on('error', retry);
    };
    const retry = () => {
      if (--retries <= 0) return reject(new Error('Flask did not start in time'));
      setTimeout(attempt, delay);
    };
    attempt();
  });
}

// ── Window ────────────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1080,
    height: 780,
    minWidth: 760,
    minHeight: 600,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: '#09090B',
    icon: path.join(__dirname, 'renderer', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.focus();
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

// ── IPC handlers ──────────────────────────────────────────────────────────

ipcMain.handle('get-flask-url', () => FLASK_URL);

ipcMain.handle('show-save-dialog', async (_, opts) => {
  const result = await dialog.showSaveDialog(mainWindow, opts);
  return result;
});

ipcMain.handle('save-file', async (_, { filePath, buffer }) => {
  fs.writeFileSync(filePath, Buffer.from(buffer));
  return true;
});

ipcMain.handle('check-backend', async () => {
  try {
    await waitForFlask(1, 100);
    return { ok: true };
  } catch (_) {
    return { ok: false };
  }
});

// ── Pull-based handshake ──────────────────────────────────────────────────
// The renderer calls 'get-backend-status' once its JS is running and
// ready to handle the result.  This avoids the race where 'backend-ready'
// was pushed via IPC *before* app.js had registered its ipcRenderer
// listener (did-finish-load fires when the DOM is ready, not when the
// renderer's JavaScript has fully executed and attached listeners).
let _backendResult = null; // cached once Flask is confirmed up/down

ipcMain.handle('get-backend-status', async () => {
  // If we already know the answer, return it immediately.
  if (_backendResult) return { ..._backendResult, url: FLASK_URL };

  // Otherwise wait for Flask now (renderer will poll if needed).
  try {
    await waitForFlask(40, 500);
    _backendResult = { ok: true };
  } catch (e) {
    _backendResult = { ok: false, message: e.message };
  }
  return { ..._backendResult, url: FLASK_URL };
});

// ── App lifecycle ─────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  createWindow();

  startFlask();

  // Warm up the backend check in the background so the result is already
  // cached by the time the renderer calls 'get-backend-status'.
  waitForFlask()
    .then(() => { _backendResult = { ok: true }; })
    .catch(e => { _backendResult = { ok: false, message: e.message }; });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (flaskProcess) {
    flaskProcess.kill('SIGTERM');
    setTimeout(() => flaskProcess && flaskProcess.kill('SIGKILL'), 3000);
  }
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  if (flaskProcess) flaskProcess.kill('SIGTERM');
});
