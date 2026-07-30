const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("parrot", {
  getState: () => ipcRenderer.invoke("parrot:get-state"),
  saveSettings: (settings) =>
    ipcRenderer.invoke("parrot:save-settings", settings),
  restart: () => ipcRenderer.invoke("parrot:restart"),
  setupModel: () => ipcRenderer.invoke("parrot:setup-model"),
  copyTranscript: (text) => ipcRenderer.invoke("parrot:copy-transcript", text),
  openOllama: () => ipcRenderer.invoke("parrot:open-ollama"),
  hide: () => ipcRenderer.invoke("parrot:hide"),
  quit: () => ipcRenderer.invoke("parrot:quit"),
  onState: (listener) => {
    const wrapped = (_event, value) => listener(value);
    ipcRenderer.on("parrot:state", wrapped);
    return () => ipcRenderer.removeListener("parrot:state", wrapped);
  },
});
