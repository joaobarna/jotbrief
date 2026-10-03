// Janela do ícone: mostra se o app JB está conectado e deixa esconder o selo no Meet.
const t = (k) => chrome.i18n.getMessage(k);
const $ = (id) => document.getElementById(id);

document.documentElement.lang = chrome.i18n.getUILanguage();
$("title").textContent = t("popupTitle");
$("lead").textContent = t("popupLead");
$("downloadLink").textContent = t("downloadApp");
$("badgeLabel").textContent = t("showBadge");
$("badgeHint").textContent = t("badgeHint");
$("how").textContent = t("howItWorks");
$("statusText").textContent = t("statusChecking");
if (chrome.i18n.getUILanguage().toLowerCase().startsWith("en")) {  // links em inglês para quem usa o Chrome em inglês
  $("downloadLink").href = "https://joao-barnabe.com/en/jot-brief/";
  $("how").href = "https://joao-barnabe.com/en/jot-brief/privacy/";
}

chrome.runtime.sendMessage({ type: "status" }, (r) => {
  void chrome.runtime.lastError;
  const ok = r && r.ok;
  $("statusText").textContent = !ok ? t("statusNoApp") : (r.recording ? t("statusRecording") : t("statusIdle"));
  $("dot").className = "dot" + (ok ? (r.recording ? " rec" : " ok") : "");
  $("download").hidden = !!ok;
});

chrome.storage.local.get({ badge: true }, (v) => { $("badge").checked = v.badge !== false; });
$("badge").addEventListener("change", () => chrome.storage.local.set({ badge: $("badge").checked }));
