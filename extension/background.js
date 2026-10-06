// Repassa os eventos da página do Meet para o app local (127.0.0.1) e mostra no ícone quando o app está gravando.
const BASE = "http://127.0.0.1:47821";
const HEADERS = { "Content-Type": "application/json", "X-SaidKeep": "1" };
const SIZES = [16, 32, 48, 128];

let shown = null; // estado do ícone: null (desconhecido) | false (normal) | true (gravando)

// Ícone do app (SaidKeep com microfone, verde); quando gravando, ganha um círculo vermelho no canto.
async function paintIcon(recording) {
  const bmp = await createImageBitmap(await (await fetch(chrome.runtime.getURL("icons/icon128.png"))).blob());
  const imageData = {};
  for (const s of SIZES) {
    const c = new OffscreenCanvas(s, s);
    const g = c.getContext("2d");
    g.drawImage(bmp, 0, 0, s, s);
    if (recording) {
      const r = s * 0.27;
      const x = s - r - s * 0.01, y = s - r - s * 0.01;
      g.beginPath();
      g.arc(x, y, r, 0, 2 * Math.PI);
      g.fillStyle = "#E5302E";
      g.fill();
      g.lineWidth = Math.max(1, s * 0.07);
      g.strokeStyle = "#FFFFFF";
      g.stroke();
    }
    imageData[s] = g.getImageData(0, 0, s, s);
  }
  await chrome.action.setIcon({ imageData });
  await chrome.action.setTitle({ title: recording ? chrome.i18n.getMessage("iconRecording") : chrome.i18n.getMessage("actionTitle") });
}

function setRecording(recording) {
  if (shown === recording) return;
  shown = recording;
  paintIcon(recording).catch(() => { shown = null; });
}

async function pollStatus() {
  try {
    const r = await fetch(BASE + "/", { headers: HEADERS });
    const j = await r.json();
    setRecording(!!j.recording);
    return { ok: true, recording: !!j.recording };
  } catch (e) {
    setRecording(false); // app fechado: ícone normal
    return { ok: false };
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.type === "event") {
    fetch(BASE + "/event", { method: "POST", headers: HEADERS, body: JSON.stringify({ name: msg.name, on: msg.on }) })
      .then((r) => r.json()).then((j) => reply({ ok: true, stored: j.stored }))
      .catch(() => reply({ ok: false }));
    return true; // resposta assíncrona
  }
  if (msg.type === "status") {
    pollStatus().then(reply);
    return true;
  }
});

// Mesmo sem uma aba do Meet aberta, confere o app a cada 30 s (o mínimo permitido para alarmes).
chrome.alarms.create("jb-poll", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((a) => { if (a.name === "jb-poll") pollStatus(); });
chrome.runtime.onStartup.addListener(pollStatus);
chrome.runtime.onInstalled.addListener(pollStatus);
pollStatus();
