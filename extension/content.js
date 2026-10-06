// Detecta quem está falando no Google Meet e avisa o app SaidKeep, que roda no seu computador (via background.js).
//
// O Meet não expõe "quem fala" de forma estável (as classes mudam). Por isso a detecção é por ATIVIDADE:
// cada "bloco de participante" ([data-participant-id]) que tem animação/mutações recorrentes fora do vídeo
// (o indicador de áudio mexe só para quem fala) é considerado "falando". O nome vem do próprio bloco.
// Nada sai do computador: os avisos vão só para http://127.0.0.1 (o app). O selo no canto da tela é opcional.
(() => {
  const WINDOW_MS = 700;      // janela para contar mutações
  const MIN_MUTATIONS = 3;    // mutações na janela para considerar "falando"
  const HOLD_MS = 900;        // quanto tempo depois da última atividade ainda vale como falando
  const t = (k) => chrome.i18n.getMessage(k);

  const activity = new Map(); // tile -> [timestamps]
  const speaking = new Map(); // nome -> último instante de atividade
  const announced = new Set();

  // ---- selo opcional no canto da tela (escolha no popup do ícone) ----
  let showBadge = true;
  let link = "…";             // estado da ligação com o app (atualizado a cada 2 s)
  let lastText = t("badgeWaiting");
  const badge = document.createElement("div");
  badge.style.cssText = "position:fixed;left:8px;bottom:8px;z-index:99999;background:#1f2937;color:#fff;" +
    "font:12px system-ui;padding:4px 8px;border-radius:8px;opacity:.85;pointer-events:none";
  const paint = () => {
    if (showBadge) {
      badge.textContent = "[SaidKeep] " + lastText + "  ·  " + link;
      if (!badge.isConnected) document.documentElement.appendChild(badge);
    } else if (badge.isConnected) {
      badge.remove();
    }
  };
  const show = (text) => { lastText = text; paint(); };
  chrome.storage.local.get({ badge: true }, (v) => { showBadge = v.badge !== false; paint(); });
  chrome.storage.onChanged.addListener((c) => {
    if (c.badge) { showBadge = c.badge.newValue !== false; paint(); }
  });
  setInterval(() => {
    chrome.runtime.sendMessage({ type: "status" }, (r) => {
      if (chrome.runtime.lastError || !r) link = t("badgeNoExt");
      else if (!r.ok) link = t("badgeAppClosed");
      else link = r.recording ? t("badgeAppRecording") : t("badgeAppIdle");
      paint();
    });
  }, 2000);

  const SELF = /^(você|voce|you)$/i;

  // textos que NÃO são nome de gente: ícones (frame_person), estados ("Your microphone is off.") e botões
  const NOT_NAME = /microphone|microfone|camera|câmera|\bpin\b|fixar|mute|silenciar|presentation|apresent|more options|mais opç|remove|remover|is off|está desat|turned off|captions|legendas|raised|mão|host|anfitri|reframe|enquadr|whiteboard|jamboard|layout|spotlight|participants|participantes|meeting details|detalhes da reuni/i;
  const looksLikeName = (s) =>
    s.length >= 2 && s.length <= 40 && !/^[a-z0-9]+(_[a-z0-9]+)+$/.test(s) && !/[.!?:]$/.test(s) &&
    s.split(" ").length <= 5 && !NOT_NAME.test(s);

  function nameOf(tile) {
    const cands = [];
    const self = tile.querySelector("[data-self-name]");
    if (self) cands.push(self.getAttribute("data-self-name"));
    const walker = document.createTreeWalker(tile, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (!n.parentElement.closest("video, canvas, button")) cands.push(n.textContent);
    }
    tile.querySelectorAll("[aria-label]").forEach((e) => cands.push(e.getAttribute("aria-label")));
    for (const c of cands) {
      const s = (c || "").replace(/\s+/g, " ").trim();
      if (looksLikeName(s)) return s;
    }
    return "";
  }

  const tileOf = (node) => {
    const el = node.nodeType === 1 ? node : node.parentElement;
    return el && el.closest ? el.closest("[data-participant-id]") : null;
  };

  const inVideo = (node) => {
    const el = node.nodeType === 1 ? node : node.parentElement;
    return !el || !!el.closest("video, canvas");
  };

  new MutationObserver((muts) => {
    const now = performance.now();
    for (const m of muts) {
      if (inVideo(m.target)) continue;
      if (m.type === "characterData") continue; // texto (legendas, relógio) não é indicador de áudio
      const tile = tileOf(m.target);
      if (!tile) continue;
      const arr = activity.get(tile) || [];
      arr.push(now);
      activity.set(tile, arr);
    }
  }).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["class", "style"] });

  function tick() {
    const now = performance.now();
    const current = new Set();
    for (const [tile, arr] of activity) {
      if (!tile.isConnected) { activity.delete(tile); continue; }
      while (arr.length && now - arr[0] > WINDOW_MS) arr.shift();
      const name = nameOf(tile);
      if (!name || SELF.test(name)) continue;
      if (arr.length >= MIN_MUTATIONS) speaking.set(name, now);
    }
    for (const [name, last] of speaking) {
      if (now - last <= HOLD_MS) current.add(name);
    }
    for (const name of current) {
      if (!announced.has(name)) {
        announced.add(name);
        chrome.runtime.sendMessage({ type: "event", name, on: true }, () => void chrome.runtime.lastError);
      }
    }
    for (const name of [...announced]) {
      if (!current.has(name)) {
        announced.delete(name);
        chrome.runtime.sendMessage({ type: "event", name, on: false }, () => void chrome.runtime.lastError);
      }
    }
    show(current.size ? [...current].join(", ") : t("badgeNobody"));
  }
  setInterval(tick, 250);
  // repete "está falando" a cada 2 s: se a gravação começou DEPOIS do aviso inicial, o app ainda fica sabendo
  setInterval(() => {
    for (const name of announced) {
      chrome.runtime.sendMessage({ type: "event", name, on: true }, () => void chrome.runtime.lastError);
    }
  }, 2000);
  paint();
})();
