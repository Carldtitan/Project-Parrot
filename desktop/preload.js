const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("parrot", {
  getState: () => ipcRenderer.invoke("parrot:get-state"),
  saveSettings: (settings) =>
    ipcRenderer.invoke("parrot:save-settings", settings),
  savePersonalization: (data) =>
    ipcRenderer.invoke("parrot:save-personalization", data),
  restart: () => ipcRenderer.invoke("parrot:restart"),
  setupModel: () => ipcRenderer.invoke("parrot:setup-model"),
  toggleHandsFree: () => ipcRenderer.invoke("parrot:toggle-hands-free"),
  cancel: () => ipcRenderer.invoke("parrot:cancel"),
  pasteLast: () => ipcRenderer.invoke("parrot:paste-last"),
  pasteText: (text) => ipcRenderer.invoke("parrot:paste-text", text),
  deleteHistory: (id) => ipcRenderer.invoke("parrot:delete-history", id),
  clearHistory: () => ipcRenderer.invoke("parrot:clear-history"),
  copyTranscript: (text) => ipcRenderer.invoke("parrot:copy-transcript", text),
  openOllama: () => ipcRenderer.invoke("parrot:open-ollama"),
  hide: () => ipcRenderer.invoke("parrot:hide"),
  quit: () => ipcRenderer.invoke("parrot:quit"),
  e2eSeed: (data) => ipcRenderer.invoke("parrot:e2e-seed", data),
  onState: (listener) => {
    const wrapped = (_event, value) => listener(value);
    ipcRenderer.on("parrot:state", wrapped);
    return () => ipcRenderer.removeListener("parrot:state", wrapped);
  },
});
