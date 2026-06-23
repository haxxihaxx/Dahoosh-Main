const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electron', {
  getFlaskUrl:       ()        => ipcRenderer.invoke('get-flask-url'),
  checkBackend:      ()        => ipcRenderer.invoke('check-backend'),
  // Pull-based handshake: renderer calls this once its JS is running.
  // Returns { ok, url } or { ok: false, message } — no listener race possible.
  getBackendStatus:  ()        => ipcRenderer.invoke('get-backend-status'),
  showSaveDialog:    (opts)    => ipcRenderer.invoke('show-save-dialog', opts),
  saveFile:          (payload) => ipcRenderer.invoke('save-file', payload),
  onBackendReady:    (cb)      => ipcRenderer.on('backend-ready',  (_, d) => cb(d)),
  onBackendError:    (cb)      => ipcRenderer.on('backend-error',  (_, d) => cb(d)),
});
