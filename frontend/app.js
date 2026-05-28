const state = {
  alerts: [],
  selected: null,
  settings: {
    apiBaseUrl: localStorage.getItem("iot.apiBaseUrl") || "http://100.118.101.103:32080",
    apiKey: localStorage.getItem("iot.apiKey") || "SeiLa",
  },
};

const el = {
  apiBaseUrl: document.querySelector("#apiBaseUrl"),
  apiKey: document.querySelector("#apiKey"),
  saveSettings: document.querySelector("#saveSettings"),
  minutesFilter: document.querySelector("#minutesFilter"),
  cameraFilter: document.querySelector("#cameraFilter"),
  eventFilter: document.querySelector("#eventFilter"),
  refreshButton: document.querySelector("#refreshButton"),
  totalAlerts: document.querySelector("#totalAlerts"),
  activeCameras: document.querySelector("#activeCameras"),
  avgConfidence: document.querySelector("#avgConfidence"),
  criticalAlerts: document.querySelector("#criticalAlerts"),
  alertList: document.querySelector("#alertList"),
  mediaViewer: document.querySelector("#mediaViewer"),
  alertDetails: document.querySelector("#alertDetails"),
  template: document.querySelector("#alertItemTemplate"),
};

function headers() {
  return { "X-API-Key": state.settings.apiKey };
}

function apiUrl(path, params = {}) {
  const url = new URL(path, state.settings.apiBaseUrl);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  });
  return url;
}

async function fetchJson(path, params) {
  const response = await fetch(apiUrl(path, params), { headers: headers() });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function formatEvent(evento) {
  return String(evento || "desconhecido").replaceAll("_", " ");
}

function formatDate(value) {
  if (!value) return "--";
  return new Intl.DateTimeFormat("pt-PT", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

function confidencePercent(value) {
  if (typeof value !== "number") return "--";
  return `${Math.round(value * 100)}%`;
}

function classifyAlert(alert) {
  if (alert.evento === "intruso_detectado" || alert.evento === "som_suspeito") return "critical";
  if ((alert.confianca || 0) < 0.65) return "warning";
  return "";
}

function filteredAlerts() {
  const camera = el.cameraFilter.value.trim().toLowerCase();
  const event = el.eventFilter.value;
  return state.alerts.filter((alert) => {
    const matchesCamera = !camera || String(alert.camera_id || "").toLowerCase().includes(camera);
    const matchesEvent = !event || alert.evento === event;
    return matchesCamera && matchesEvent;
  });
}

function renderMetrics(summary) {
  const alerts = state.alerts;
  const critical = alerts.filter((alert) =>
    ["intruso_detectado", "som_suspeito"].includes(alert.evento)
  ).length;

  el.totalAlerts.textContent = summary?.total_alertas ?? alerts.length;
  el.activeCameras.textContent = summary?.cameras_ativas ?? new Set(alerts.map((item) => item.camera_id)).size;
  el.avgConfidence.textContent = confidencePercent(summary?.confianca_media);
  el.criticalAlerts.textContent = critical;
}

function renderAlerts() {
  const alerts = filteredAlerts();
  el.alertList.replaceChildren();

  if (!alerts.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>Sem incidentes</strong><span>Nao ha alertas para estes filtros.</span>";
    el.alertList.append(empty);
    return;
  }

  alerts.forEach((alert) => {
    const item = el.template.content.firstElementChild.cloneNode(true);
    item.dataset.filename = alert.media_filename || "";
    item.classList.toggle("selected", state.selected === alert);
    const severity = classifyAlert(alert);
    if (severity) {
      item.querySelector(".severity-dot").classList.add(severity);
    }
    item.querySelector(".alert-title").textContent = `${formatEvent(alert.evento)} · ${alert.camera_id}`;
    item.querySelector(".alert-meta").textContent = `${alert.localizacao || "--"} · ${formatDate(alert.timestamp)}`;
    item.querySelector(".confidence").textContent = confidencePercent(alert.confianca);
    item.addEventListener("click", () => selectAlert(alert));
    el.alertList.append(item);
  });
}

async function selectAlert(alert) {
  state.selected = alert;
  renderAlerts();
  renderDetails(alert);

  if (!alert.media_filename) {
    renderNoMedia("Este alerta nao tem ficheiro associado.");
    return;
  }

  const streamUrl = apiUrl("/api/v1/media/stream", {
    filename: alert.media_filename,
    api_key: state.settings.apiKey,
  });
  renderMedia(alert, streamUrl.toString());
}

function renderMedia(alert, url) {
  el.mediaViewer.replaceChildren();
  const filename = alert.media_filename || "";
  const isImage = /\.(png|jpg|jpeg)$/i.test(filename);

  if (isImage) {
    const image = document.createElement("img");
    image.src = url;
    image.alt = `Media do alerta ${alert.evento}`;
    el.mediaViewer.append(image);
    return;
  }

  const video = document.createElement("video");
  video.src = url;
  video.controls = true;
  video.playsInline = true;
  el.mediaViewer.append(video);
}

function renderNoMedia(message) {
  el.mediaViewer.innerHTML = `<div class="empty-state"><strong>Sem preview</strong><span class="error">${message}</span></div>`;
}

function renderDetails(alert) {
  const rows = [
    ["Hora", formatDate(alert.timestamp)],
    ["Camara", alert.camera_id],
    ["Evento", formatEvent(alert.evento)],
    ["Localizacao", alert.localizacao],
    ["Confianca", confidencePercent(alert.confianca)],
    ["Ficheiro", alert.media_filename || "--"],
  ];

  el.alertDetails.replaceChildren(
    ...rows.flatMap(([label, value]) => {
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = label;
      dd.textContent = value || "--";
      return [dt, dd];
    })
  );
}

async function loadDashboard() {
  el.refreshButton.disabled = true;
  const minutes = el.minutesFilter.value;
  const [alertsResponse, summaryResponse] = await Promise.all([
    fetchJson("/api/v1/alerts", { minutos: minutes, limit: 200 }),
    fetchJson("/api/v1/dashboard/summary", { minutos: minutes }),
  ]);

  state.alerts = alertsResponse.dados || [];
  renderMetrics(summaryResponse.dados);
  renderAlerts();

  if (!state.selected && state.alerts.length) {
    await selectAlert(state.alerts[0]);
  }
  el.refreshButton.disabled = false;
}

function saveSettings() {
  state.settings.apiBaseUrl = el.apiBaseUrl.value.trim().replace(/\/$/, "");
  state.settings.apiKey = el.apiKey.value.trim();
  localStorage.setItem("iot.apiBaseUrl", state.settings.apiBaseUrl);
  localStorage.setItem("iot.apiKey", state.settings.apiKey);
  loadDashboard().catch(showFatalError);
}

function showFatalError(error) {
  el.alertList.innerHTML = `<div class="empty-state"><strong>Erro ao carregar dados</strong><span class="error">${error.message}</span></div>`;
  el.refreshButton.disabled = false;
}

function init() {
  el.apiBaseUrl.value = state.settings.apiBaseUrl;
  el.apiKey.value = state.settings.apiKey;

  el.saveSettings.addEventListener("click", saveSettings);
  el.refreshButton.addEventListener("click", () => loadDashboard().catch(showFatalError));
  el.minutesFilter.addEventListener("change", () => loadDashboard().catch(showFatalError));
  el.cameraFilter.addEventListener("input", renderAlerts);
  el.eventFilter.addEventListener("change", renderAlerts);

  loadDashboard().catch(showFatalError);
}

init();
