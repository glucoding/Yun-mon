const ACTIVE_PANEL_STORAGE_KEY = "yunmon.controlPlane.activePanel";

const form = document.getElementById("config-form");
const output = document.getElementById("action-output");
const serviceList = document.getElementById("service-list");
const runtimeStatus = document.getElementById("runtime-status");
const applicationsList = document.getElementById("applications-list");
const applicationsSummary = document.getElementById("applications-summary");
const metricSummary = document.getElementById("metric-summary");
const metricCategoryList = document.getElementById("metric-category-list");
const metricLiveList = document.getElementById("metric-live-list");
const metricCatalogList = document.getElementById("metric-catalog-list");
const metricVisualizationList = document.getElementById("metric-visualization-list");
const reloadConfigButton = document.getElementById("reload-config");
const saveConfigButton = document.getElementById("save-config");
const refreshStatusButton = document.getElementById("refresh-status");
const reloadPrometheusButton = document.getElementById("reload-prometheus");
const restartStackButton = document.getElementById("restart-stack");
const refreshApplicationsButton = document.getElementById("refresh-applications");
const refreshMetricsButton = document.getElementById("refresh-metrics");
const addMetricButton = document.getElementById("add-metric");
const treeItems = Array.from(document.querySelectorAll(".tree-item"));
const groupToggles = Array.from(document.querySelectorAll("[data-group-toggle]"));
const panels = Array.from(document.querySelectorAll(".content-panel"));
const badgeElements = new Map(
  Array.from(document.querySelectorAll("[data-badge-for]")).map((node) => [node.dataset.badgeFor, node]),
);

let currentConfig = null;
let currentApplications = [];
let currentMetricCatalog = {
  categories: [],
  items: [],
  liveMetrics: [],
  unmanagedLiveMetrics: [],
};
let metricPointerDrag = null;

function setOutput(value) {
  output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function parseCsv(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function getByPath(source, path) {
  return path.split(".").reduce((acc, key) => (acc == null ? undefined : acc[key]), source);
}

function setByPath(target, path, value) {
  const segments = path.split(".");
  let cursor = target;
  for (let index = 0; index < segments.length - 1; index += 1) {
    const segment = segments[index];
    if (typeof cursor[segment] !== "object" || cursor[segment] === null || Array.isArray(cursor[segment])) {
      cursor[segment] = {};
    }
    cursor = cursor[segment];
  }
  cursor[segments[segments.length - 1]] = value;
}

function setTreeBadge(panelId, text, state = "neutral") {
  const badge = badgeElements.get(panelId);
  if (!badge) {
    return;
  }
  const value = String(text || "").trim();
  badge.textContent = value;
  badge.dataset.state = state;
  badge.hidden = !value;
}

function setNodeText(selector, text, root = document) {
  const node = root.querySelector(selector);
  if (node) {
    node.textContent = text;
  }
}

function normalizeMetricSectionLabels() {
  const metricOverviewItem = document.querySelector('.tree-item[data-panel="metric-overview"]');
  const metricCatalogItem = document.querySelector('.tree-item[data-panel="metric-catalog"]');
  const metricVisualizationItem = document.querySelector('.tree-item[data-panel="metric-visualization"]');
  const metricGroup = metricOverviewItem?.closest("[data-group]");

  setNodeText(".tree-item-label", "指标总览", metricOverviewItem || document);
  setNodeText(".tree-item-label", "指标目录", metricCatalogItem || document);
  setNodeText(".tree-item-label", "可视化配置", metricVisualizationItem || document);
  setNodeText("[data-group-toggle] span", "指标治理", metricGroup || document);

  const overviewPanel = document.querySelector('.content-panel[data-panel="metric-overview"]');
  if (overviewPanel) {
    setNodeText("h2", "指标总览", overviewPanel);
    setNodeText(
      ".panel-note",
      "对监测指标进行分级分类管理，统一梳理基础指标、业务指标、组合指标和宏观指标，并查看当前实时已发现的指标资产。",
      overviewPanel,
    );
    const cards = overviewPanel.querySelectorAll(".card");
    if (cards[0]) {
      setNodeText("h2", "指标目录", cards[0]);
    }
    if (cards[1]) {
      setNodeText("h2", "已发现指标", cards[1]);
    }
  }

  const catalogPanel = document.querySelector('.content-panel[data-panel="metric-catalog"]');
  if (catalogPanel) {
    setNodeText("h2", "指标目录", catalogPanel);
    setNodeText(
      ".panel-note",
      "按“名称 + 作用”维护监测指标目录，可新增指标、调整分类，并把未纳管指标拖入指定目录变成纳管指标。",
      catalogPanel,
    );
  }

  const visualizationPanel = document.querySelector('.content-panel[data-panel="metric-visualization"]');
  if (visualizationPanel) {
    setNodeText("h2", "可视化配置", visualizationPanel);
    setNodeText(
      ".panel-note",
      "配置每个指标的默认可视化形式，包括图表类型、单位、精度和是否进入自动生成的指标治理仪表盘。",
      visualizationPanel,
    );
  }

  if (refreshMetricsButton) {
    refreshMetricsButton.textContent = "刷新指标目录";
  }
  if (addMetricButton) {
    addMetricButton.textContent = "新增指标";
  }
}

function updateConfigBadges(config) {
  setTreeBadge(
    "application-defaults",
    config?.applications?.autoDiscoveryEnabled ? "自动发现" : "手动",
    config?.applications?.autoDiscoveryEnabled ? "running" : "created",
  );
  setTreeBadge(
    "demo-app",
    config?.demoService?.monitoringEnabled ? "已监测" : "未监测",
    config?.demoService?.monitoringEnabled ? "running" : "created",
  );
}

function activatePanel(panelId) {
  const targetPanel = panels.find((panel) => panel.dataset.panel === panelId);
  if (!targetPanel) {
    return;
  }

  treeItems.forEach((item) => {
    item.classList.toggle("active", item.dataset.panel === panelId);
  });

  panels.forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.panel === panelId);
  });

  try {
    window.localStorage.setItem(ACTIVE_PANEL_STORAGE_KEY, panelId);
  } catch (error) {
    // Ignore local storage failures.
  }
  window.location.hash = panelId;
}

function initializeNavigation() {
  treeItems.forEach((item) => {
    item.addEventListener("click", () => {
      activatePanel(item.dataset.panel);
    });
  });

  groupToggles.forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const group = toggle.closest("[data-group]");
      const expanded = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!expanded));
      group.classList.toggle("collapsed", expanded);
    });
  });

  let storedPanel = "";
  try {
    storedPanel = window.localStorage.getItem(ACTIVE_PANEL_STORAGE_KEY) || "";
  } catch (error) {
    storedPanel = "";
  }
  const initialPanel = window.location.hash.replace("#", "") || storedPanel || "overview";
  activatePanel(initialPanel);
}

function fillForm(config) {
  currentConfig = clone(config);
  Array.from(form.elements).forEach((field) => {
    if (!field.name) {
      return;
    }
    if (field.name === "alertmanager.groupByCsv") {
      field.value = (config.alertmanager.groupBy || []).join(", ");
      return;
    }
    const value = getByPath(config, field.name);
    if (field.type === "checkbox") {
      field.checked = Boolean(value);
      return;
    }
    field.value = value ?? "";
  });
  updateConfigBadges(config);
}

function readForm() {
  const config = clone(currentConfig || {});
  Array.from(form.elements).forEach((field) => {
    if (!field.name) {
      return;
    }
    if (field.name === "alertmanager.groupByCsv") {
      setByPath(config, "alertmanager.groupBy", parseCsv(field.value));
      return;
    }
    let value;
    if (field.type === "checkbox") {
      value = field.checked;
    } else if (field.type === "number") {
      value = Number.parseInt(field.value, 10);
    } else {
      value = field.value;
    }
    setByPath(config, field.name, value);
  });
  return config;
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const text = await response.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : {};
  } catch (error) {
    payload = { ok: response.ok, raw: text };
  }

  if (!response.ok || payload.ok === false) {
    const message = payload.error || payload.message || response.statusText || "Request failed";
    throw new Error(message);
  }

  return payload;
}

function renderStatusChip(state) {
  const normalized = String(state || "unknown").toLowerCase();
  const chip = document.createElement("span");
  chip.className = `status-chip status-${normalized}`;
  chip.textContent = normalized;
  return chip;
}

function createField(labelText, inputElement, extraClass = "") {
  const label = document.createElement("label");
  if (extraClass) {
    label.className = extraClass;
  }
  label.textContent = labelText;
  label.appendChild(inputElement);
  return label;
}

function renderServices(services, project) {
  serviceList.innerHTML = "";
  setTreeBadge("overview", `${services.length} 服务`, services.length > 0 ? "running" : "created");

  const summary = document.createElement("div");
  summary.className = "status-summary";
  summary.innerHTML = `
    <span>项目：<strong>${project || "-"}</strong></span>
    <span>服务数：<strong>${services.length}</strong></span>
  `;
  serviceList.appendChild(summary);

  if (!services.length) {
    const empty = document.createElement("div");
    empty.className = "service-empty";
    empty.textContent = "暂未发现运行中的监测服务。";
    serviceList.appendChild(empty);
    return;
  }

  services.forEach((service) => {
    const card = document.createElement("article");
    card.className = "service-card";
    card.innerHTML = `
      <div class="service-top">
        <div class="service-title">
          <strong>${escapeHtml(service.service || service.name || "-")}</strong>
          <span>${escapeHtml(service.image || "-")}</span>
        </div>
      </div>
    `;
    card.querySelector(".service-top").appendChild(renderStatusChip(service.state));

    const meta = document.createElement("div");
    meta.className = "service-meta";
    meta.innerHTML = `
      <span>容器：${escapeHtml(service.name || "-")}</span>
      <span>状态：${escapeHtml(service.status || "-")}</span>
      <span>端口：${escapeHtml((service.ports || []).join(", ") || "-")}</span>
    `;
    card.appendChild(meta);
    serviceList.appendChild(card);
  });
}

function renderRuntime(runtime) {
  runtimeStatus.innerHTML = "";
  const stackAgent = runtime.stackAgent || {};
  const strategyState = runtime.restartStrategy === "host-agent" ? "running" : "created";
  setTreeBadge(
    "stack-agent",
    runtime.restartStrategy === "host-agent" ? "在线" : "回退",
    strategyState,
  );

  const strategyCard = document.createElement("article");
  strategyCard.className = "service-card";
  strategyCard.innerHTML = `
    <div class="service-top">
      <div class="service-title">
        <strong>重启策略</strong>
        <span>${runtime.restartStrategy === "host-agent" ? "使用宿主机 stack-agent 做真正重建" : "回退到容器级 Docker API 重启"}</span>
      </div>
    </div>
  `;
  strategyCard.querySelector(".service-top").appendChild(renderStatusChip(strategyState));
  runtimeStatus.appendChild(strategyCard);

  const agentCard = document.createElement("article");
  agentCard.className = "service-card";
  agentCard.innerHTML = `
    <div class="service-top">
      <div class="service-title">
        <strong>Host Stack Agent</strong>
        <span>${escapeHtml(stackAgent.baseUrl || "-")}</span>
      </div>
    </div>
    <div class="service-meta">
      <span>启用：${stackAgent.enabled ? "是" : "否"}</span>
      <span>已配置：${stackAgent.configured ? "是" : "否"}</span>
      <span>可达：${stackAgent.reachable ? "是" : "否"}</span>
      <span>说明：${escapeHtml(stackAgent.error || stackAgent.health?.lastAction?.summary || "等待探测结果")}</span>
    </div>
  `;
  agentCard.querySelector(".service-top").appendChild(
    renderStatusChip(stackAgent.reachable ? "running" : (stackAgent.enabled ? "restarting" : "exited")),
  );
  runtimeStatus.appendChild(agentCard);
}

function applicationState(application) {
  if (application.enabled && (application.targets || []).length > 0) {
    return "running";
  }
  if (application.enabled) {
    return "created";
  }
  return "exited";
}

function renderApplications(applications) {
  currentApplications = clone(applications);
  applicationsList.innerHTML = "";

  const total = applications.length;
  const enabledCount = applications.filter((item) => item.enabled).length;
  const autoDiscoveredCount = applications.filter((item) => item.autoDiscovered).length;
  const targetCount = applications.reduce((sum, item) => sum + (item.targets || []).length, 0);

  setTreeBadge("applications", `${total} 应用`, total > 0 ? "running" : "created");

  applicationsSummary.innerHTML = `
    <span>已发现应用：<strong>${total}</strong></span>
    <span>已启用监管：<strong>${enabledCount}</strong></span>
    <span>自动发现：<strong>${autoDiscoveredCount}</strong></span>
    <span>当前目标数：<strong>${targetCount}</strong></span>
  `;

  if (!applications.length) {
    const empty = document.createElement("div");
    empty.className = "service-empty";
    empty.textContent = "当前没有发现可接入监管的应用。";
    applicationsList.appendChild(empty);
    return;
  }

  applications.forEach((application) => {
    const card = document.createElement("article");
    card.className = "application-card";
    card.dataset.appId = application.appId;

    const top = document.createElement("div");
    top.className = "service-top";
    top.innerHTML = `
      <div class="service-title">
        <strong>${escapeHtml(application.displayName || application.serviceName || application.appId)}</strong>
        <span>${escapeHtml(application.serviceName || application.appId)}</span>
      </div>
    `;
    top.appendChild(renderStatusChip(applicationState(application)));

    const meta = document.createElement("div");
    meta.className = "application-meta";
    [
      application.autoDiscovered ? "Docker 自动发现" : "仅配置项",
      application.hasMonitoringLabels ? "带监测标签" : "无监测标签",
      `实例 ${(application.containers || []).length}`,
      `目标 ${(application.targets || []).length}`,
    ].forEach((label) => {
      const tag = document.createElement("span");
      tag.className = "application-tag";
      tag.textContent = label;
      meta.appendChild(tag);
    });

    const grid = document.createElement("div");
    grid.className = "application-grid";

    const enabledWrapper = document.createElement("label");
    enabledWrapper.className = "switch";
    enabledWrapper.innerHTML = `
      <input type="checkbox" data-field="enabled" ${application.enabled ? "checked" : ""}>
      <span>纳入监管</span>
    `;
    grid.appendChild(enabledWrapper);

    const displayNameInput = document.createElement("input");
    displayNameInput.type = "text";
    displayNameInput.value = application.displayName || "";
    displayNameInput.dataset.field = "displayName";
    grid.appendChild(createField("显示名称", displayNameInput));

    const serviceNameInput = document.createElement("input");
    serviceNameInput.type = "text";
    serviceNameInput.value = application.serviceName || "";
    serviceNameInput.dataset.field = "serviceName";
    grid.appendChild(createField("服务名称", serviceNameInput));

    const targetPortInput = document.createElement("input");
    targetPortInput.type = "number";
    targetPortInput.value = application.targetPort ?? "";
    targetPortInput.dataset.field = "targetPort";
    grid.appendChild(createField("采集端口", targetPortInput));

    const metricsPathInput = document.createElement("input");
    metricsPathInput.type = "text";
    metricsPathInput.value = application.metricsPath || "";
    metricsPathInput.dataset.field = "metricsPath";
    grid.appendChild(createField("指标路径", metricsPathInput));

    const environmentInput = document.createElement("input");
    environmentInput.type = "text";
    environmentInput.value = application.environment || "";
    environmentInput.dataset.field = "environment";
    grid.appendChild(createField("环境标签", environmentInput));

    const info = document.createElement("div");
    info.className = "service-meta";
    info.innerHTML = `
      <span>实例容器：${escapeHtml((application.containers || []).map((item) => item.name).join(", ") || "无")}</span>
      <span>当前目标：${escapeHtml((application.targets || []).join(", ") || "尚未形成可抓取目标，请补充采集端口或监测标签")}</span>
    `;

    card.appendChild(top);
    card.appendChild(meta);
    card.appendChild(grid);
    card.appendChild(info);
    applicationsList.appendChild(card);
  });
}

function readApplications() {
  return Array.from(applicationsList.querySelectorAll(".application-card")).map((card) => {
    const appId = card.dataset.appId;
    const source = currentApplications.find((item) => item.appId === appId) || {};
    const enabled = card.querySelector('[data-field="enabled"]').checked;
    const displayName = card.querySelector('[data-field="displayName"]').value.trim();
    const serviceName = card.querySelector('[data-field="serviceName"]').value.trim();
    const targetPortRaw = card.querySelector('[data-field="targetPort"]').value.trim();
    const metricsPath = card.querySelector('[data-field="metricsPath"]').value.trim();
    const environment = card.querySelector('[data-field="environment"]').value.trim();

    return {
      appId,
      enabled,
      displayName,
      serviceName: serviceName || source.serviceName || appId,
      targetPort: targetPortRaw ? Number.parseInt(targetPortRaw, 10) : null,
      metricsPath: metricsPath || source.metricsPath || "/actuator/prometheus",
      environment: environment || source.environment || "local",
    };
  });
}

function metricCategoriesById() {
  return new Map((currentMetricCatalog.categories || []).map((item) => [item.id, item]));
}

function metricCategoryName(categoryId) {
  return metricCategoriesById().get(categoryId)?.name || categoryId || "未分类";
}

function groupedMetricsByCategory(items) {
  const groups = new Map((currentMetricCatalog.categories || []).map((category) => [category.id, []]));
  (items || []).forEach((item) => {
    if (!groups.has(item.category)) {
      groups.set(item.category, []);
    }
    groups.get(item.category).push(item);
  });
  return groups;
}

function sortMetrics(items) {
  const categoryOrder = (currentMetricCatalog.categories || []).map((item) => item.id);
  return [...(items || [])].sort((left, right) => {
    const leftCategory = categoryOrder.indexOf(left.category);
    const rightCategory = categoryOrder.indexOf(right.category);
    if (leftCategory !== rightCategory) {
      return (leftCategory === -1 ? 999 : leftCategory) - (rightCategory === -1 ? 999 : rightCategory);
    }
    return String(left.displayName || left.metricName || left.metricId).localeCompare(
      String(right.displayName || right.metricName || right.metricId),
      "zh-CN",
    );
  });
}

function metricState(metric) {
  if (metric.enabled && metric.live) {
    return "running";
  }
  if (metric.enabled) {
    return "created";
  }
  return "exited";
}

function metricPurpose(metric) {
  return metric.purpose || metric.description || "未填写指标作用说明。";
}

function optionMarkup(options, value) {
  return options
    .map((item) => {
      const optionValue = typeof item === "string" ? item : item.value;
      const optionLabel = typeof item === "string" ? item : item.label;
      const selected = String(optionValue) === String(value) ? " selected" : "";
      return `<option value="${escapeHtml(optionValue)}"${selected}>${escapeHtml(optionLabel)}</option>`;
    })
    .join("");
}

function ensureUniqueMetricId(metricId) {
  const base = String(metricId || "managed_metric").trim() || "managed_metric";
  const existing = new Set((currentMetricCatalog.items || []).map((item) => item.metricId));
  if (!existing.has(base)) {
    return base;
  }
  let index = 2;
  let candidate = `${base}_${index}`;
  while (existing.has(candidate)) {
    index += 1;
    candidate = `${base}_${index}`;
  }
  return candidate;
}

function slugifyMetricName(metricName) {
  return String(metricName || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "") || "managed_metric";
}

function unmanagedMetricByName(metricName) {
  return (currentMetricCatalog.unmanagedLiveMetrics || []).find((item) => item.metricName === metricName) || null;
}

function promoteUnmanagedMetric(metricName, categoryId) {
  const source = unmanagedMetricByName(metricName);
  if (!source) {
    setOutput({ error: "未找到要纳管的实时指标。" });
    return;
  }

  const template = clone(source.suggestedItem || {});
  template.metricId = ensureUniqueMetricId(template.metricId || slugifyMetricName(metricName));
  template.metricName = source.metricName;
  template.displayName = source.displayName || source.metricName;
  template.description = source.purpose || template.description || "请补充该指标的业务作用说明。";
  template.category = categoryId || source.recommendedCategory || template.category || "basic";
  template.enabled = true;
  template.live = true;

  currentMetricCatalog.items = [...(currentMetricCatalog.items || []), template];
  currentMetricCatalog.unmanagedLiveMetrics = (currentMetricCatalog.unmanagedLiveMetrics || []).filter(
    (item) => item.metricName !== metricName,
  );
  renderMetricViews();
  activatePanel("metric-catalog");
  setOutput({
    message: "已将未纳管指标拖入目录并生成纳管条目，请按需补充名称、作用和可视化设置后保存。",
    metricId: template.metricId,
    metricName: template.metricName,
    category: metricCategoryName(template.category),
  });
}

function clearMetricDropHighlight() {
  document.querySelectorAll(".metric-drop-zone").forEach((node) => node.classList.remove("is-drop-target"));
}

function cleanupMetricPointerDrag() {
  if (!metricPointerDrag) {
    return;
  }
  metricPointerDrag.source?.classList.remove("dragging");
  metricPointerDrag.ghost?.remove();
  clearMetricDropHighlight();
  document.body.classList.remove("metric-dragging");
  window.removeEventListener("pointermove", handleMetricPointerMove, true);
  window.removeEventListener("mousemove", handleMetricPointerMove, true);
  window.removeEventListener("pointerup", finishMetricPointerDrag, true);
  window.removeEventListener("mouseup", finishMetricPointerDrag, true);
  window.removeEventListener("pointercancel", cancelMetricPointerDrag, true);
  window.removeEventListener("blur", cancelMetricPointerDrag, true);
  metricPointerDrag = null;
}

function updateMetricPointerTarget(clientX, clientY) {
  if (!metricPointerDrag) {
    return;
  }
  const hit = document.elementFromPoint(clientX, clientY);
  const nextZone = hit?.closest?.("[data-drop-category]") || null;
  if (metricPointerDrag.activeZone === nextZone) {
    return;
  }
  metricPointerDrag.activeZone?.classList.remove("is-drop-target");
  metricPointerDrag.activeZone = nextZone;
  metricPointerDrag.activeZone?.classList.add("is-drop-target");
}

function handleMetricPointerMove(event) {
  if (!metricPointerDrag) {
    return;
  }
  metricPointerDrag.ghost.style.transform = `translate(${event.clientX + 16}px, ${event.clientY + 16}px)`;
  updateMetricPointerTarget(event.clientX, event.clientY);
}

function finishMetricPointerDrag(event) {
  if (!metricPointerDrag) {
    return;
  }
  const metricName = metricPointerDrag.metricName;
  const categoryId = metricPointerDrag.activeZone?.dataset?.dropCategory || "";
  cleanupMetricPointerDrag();
  if (categoryId) {
    promoteUnmanagedMetric(metricName, categoryId);
  }
}

function cancelMetricPointerDrag() {
  cleanupMetricPointerDrag();
}

function beginMetricPointerDrag(card, event) {
  if (metricPointerDrag) {
    return;
  }
  if (event.button !== 0) {
    return;
  }
  event.preventDefault();

  const ghost = card.cloneNode(true);
  ghost.classList.add("metric-drag-ghost");
  ghost.style.width = `${Math.ceil(card.getBoundingClientRect().width)}px`;
  ghost.style.transform = `translate(${event.clientX + 16}px, ${event.clientY + 16}px)`;
  document.body.appendChild(ghost);

  metricPointerDrag = {
    metricName: card.dataset.draggableMetric || "",
    source: card,
    ghost,
    activeZone: null,
  };
  card.classList.add("dragging");
  document.body.classList.add("metric-dragging");
  window.addEventListener("pointermove", handleMetricPointerMove, true);
  window.addEventListener("mousemove", handleMetricPointerMove, true);
  window.addEventListener("pointerup", finishMetricPointerDrag, true);
  window.addEventListener("mouseup", finishMetricPointerDrag, true);
  window.addEventListener("pointercancel", cancelMetricPointerDrag, true);
  window.addEventListener("blur", cancelMetricPointerDrag, true);
  updateMetricPointerTarget(event.clientX, event.clientY);
}

function attachMetricDragHandlers() {
  Array.from(document.querySelectorAll("[data-draggable-metric]")).forEach((card) => {
    card.draggable = false;
    card.addEventListener("pointerdown", (event) => {
      beginMetricPointerDrag(card, event);
    });
    card.addEventListener("mousedown", (event) => {
      beginMetricPointerDrag(card, event);
    });
  });
}

function renderMetricBadges(items) {
  const enabledCount = items.filter((item) => item.enabled).length;
  const visibleCount = items.filter((item) => item.enabled && item.visualization?.showOnDashboard).length;
  setTreeBadge("metric-overview", `${items.length} 指标`, items.length > 0 ? "running" : "created");
  setTreeBadge("metric-catalog", `${enabledCount} 已启用`, enabledCount > 0 ? "running" : "created");
  setTreeBadge("metric-visualization", `${visibleCount} 展示`, visibleCount > 0 ? "running" : "created");
}

function renderMetricOverview() {
  const items = sortMetrics(currentMetricCatalog.items || []);
  const liveMetrics = currentMetricCatalog.liveMetrics || [];
  const unmanagedMetrics = currentMetricCatalog.unmanagedLiveMetrics || [];
  const categories = currentMetricCatalog.categories || [];

  renderMetricBadges(items);

  const enabledCount = items.filter((item) => item.enabled).length;
  const liveManagedCount = items.filter((item) => item.live).length;
  const derivedCount = items.filter((item) => item.sourceType === "recording_rule").length;
  const visibleCount = items.filter((item) => item.enabled && item.visualization?.showOnDashboard).length;

  metricSummary.innerHTML = `
    <span>目录指标：<strong>${items.length}</strong></span>
    <span>已启用：<strong>${enabledCount}</strong></span>
    <span>组合/宏观：<strong>${derivedCount}</strong></span>
    <span>已发现实时指标：<strong>${liveMetrics.length}</strong></span>
    <span>已纳管实时指标：<strong>${liveManagedCount}</strong></span>
    <span>未纳管实时指标：<strong>${unmanagedMetrics.length}</strong></span>
    <span>默认展示：<strong>${visibleCount}</strong></span>
  `;

  metricCategoryList.innerHTML = "";
  if (!categories.length) {
    const empty = document.createElement("div");
    empty.className = "service-empty";
    empty.textContent = "当前还没有定义指标分类。";
    metricCategoryList.appendChild(empty);
  } else {
    categories.forEach((category) => {
      const categoryItems = items.filter((item) => item.category === category.id);
      const preview = categoryItems.length
        ? categoryItems
          .slice(0, 3)
          .map((item) => `<span class="metric-pill" data-state="${metricState(item)}">${escapeHtml(item.displayName)}</span>`)
          .join("")
        : '<span class="service-empty compact-empty">当前目录还没有纳管指标。</span>';

      const card = document.createElement("article");
      card.className = "metric-category-card metric-drop-zone";
      card.dataset.dropCategory = category.id;
      card.innerHTML = `
        <div class="service-top">
          <div class="service-title">
            <strong>${escapeHtml(category.name)}</strong>
            <span>${escapeHtml(category.description || "未填写分类说明。")}</span>
          </div>
        </div>
      `;
      card.querySelector(".service-top").appendChild(renderStatusChip(categoryItems.length > 0 ? "running" : "created"));

      const summary = document.createElement("div");
      summary.className = "status-summary";
      summary.innerHTML = `
        <span>目录数：<strong>${categoryItems.length}</strong></span>
        <span>已启用：<strong>${categoryItems.filter((item) => item.enabled).length}</strong></span>
        <span>实时可见：<strong>${categoryItems.filter((item) => item.live).length}</strong></span>
      `;
      card.appendChild(summary);

      const hint = document.createElement("div");
      hint.className = "metric-drop-hint";
      hint.textContent = `将“未纳管指标”拖到这里，即可纳入“${category.name}”目录。`;
      card.appendChild(hint);

      const previewCloud = document.createElement("div");
      previewCloud.className = "metric-pill-cloud";
      previewCloud.innerHTML = preview;
      card.appendChild(previewCloud);
      metricCategoryList.appendChild(card);
    });
  }

  metricLiveList.innerHTML = "";
  const managedSection = document.createElement("section");
  managedSection.className = "metric-live-section";
  managedSection.innerHTML = `
    <div class="card-head metric-live-head">
      <div>
        <p class="section-kicker">Managed Metrics</p>
        <h2>已纳管指标</h2>
      </div>
    </div>
  `;

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "service-empty";
    empty.textContent = "当前还没有纳管任何指标定义。";
    managedSection.appendChild(empty);
  } else {
    const managedList = document.createElement("div");
    managedList.className = "managed-metric-list";
    items.forEach((metric) => {
      const card = document.createElement("article");
      card.className = "managed-metric-card";
      card.innerHTML = `
        <div class="metric-card-header">
          <div class="service-title">
            <strong>${escapeHtml(metric.displayName)}</strong>
            <span class="metric-code">${escapeHtml(metric.metricName)}</span>
          </div>
        </div>
      `;
      card.querySelector(".metric-card-header").appendChild(renderStatusChip(metricState(metric)));
      const meta = document.createElement("div");
      meta.className = "application-meta";
      meta.innerHTML = `
        <span class="application-tag">${escapeHtml(metricCategoryName(metric.category))}</span>
        <span class="application-tag">${metric.sourceType === "recording_rule" ? "组合/规则指标" : "基础/原始指标"}</span>
      `;
      card.appendChild(meta);
      const purpose = document.createElement("p");
      purpose.className = "metric-purpose-text";
      purpose.innerHTML = `<strong>作用：</strong>${escapeHtml(metricPurpose(metric))}`;
      card.appendChild(purpose);
      managedList.appendChild(card);
    });
    managedSection.appendChild(managedList);
  }
  metricLiveList.appendChild(managedSection);

  const unmanagedSection = document.createElement("section");
  unmanagedSection.className = "metric-live-section";
  unmanagedSection.innerHTML = `
    <div class="card-head metric-live-head">
      <div>
        <p class="section-kicker">Discovered Metrics</p>
        <h2>已发现但未纳管的实时指标</h2>
      </div>
    </div>
  `;

  if (!unmanagedMetrics.length) {
    const empty = document.createElement("div");
    empty.className = "service-empty";
    empty.textContent = "当前发现的实时指标已经全部纳入目录，或暂时没有新的可纳管指标。";
    unmanagedSection.appendChild(empty);
  } else {
    const list = document.createElement("div");
    list.className = "unmanaged-metric-list";
    unmanagedMetrics.forEach((metric) => {
      const card = document.createElement("article");
      card.className = "unmanaged-metric-card";
      card.draggable = true;
      card.dataset.draggableMetric = metric.metricName;
      card.innerHTML = `
        <div class="metric-card-header">
          <div class="service-title">
            <strong>${escapeHtml(metric.displayName || metric.metricName)}</strong>
            <span class="metric-code">${escapeHtml(metric.metricName)}</span>
          </div>
        </div>
      `;
      card.querySelector(".metric-card-header").appendChild(renderStatusChip("created"));
      const meta = document.createElement("div");
      meta.className = "application-meta";
      meta.innerHTML = `
        <span class="application-tag">建议目录：${escapeHtml(metric.recommendedCategoryName || metric.recommendedCategory || "基础指标")}</span>
        <span class="application-tag">拖动纳管</span>
      `;
      card.appendChild(meta);
      const purpose = document.createElement("p");
      purpose.className = "metric-purpose-text";
      purpose.innerHTML = `<strong>作用：</strong>${escapeHtml(metric.purpose || "这是 Prometheus 已发现但尚未纳管的实时指标。")}`;
      card.appendChild(purpose);
      list.appendChild(card);
    });
    unmanagedSection.appendChild(list);
  }
  metricLiveList.appendChild(unmanagedSection);

  attachMetricDragHandlers();
}

function renderMetricCatalog() {
  const categories = currentMetricCatalog.categories || [];
  const grouped = groupedMetricsByCategory(sortMetrics(currentMetricCatalog.items || []));
  const unmanagedMetrics = currentMetricCatalog.unmanagedLiveMetrics || [];
  metricCatalogList.innerHTML = "";

  const layout = document.createElement("div");
  layout.className = "metric-catalog-layout";

  const staging = document.createElement("section");
  staging.className = "metric-unmanaged-stage";
  staging.innerHTML = `
    <div class="metric-section-head">
      <div class="service-title">
        <strong>未纳管指标池</strong>
        <span>把左侧实时指标拖到右侧目录，即可生成新的纳管条目。</span>
      </div>
    </div>
  `;
  const stagingList = document.createElement("div");
  stagingList.className = "unmanaged-metric-list";
  if (!unmanagedMetrics.length) {
    const empty = document.createElement("div");
    empty.className = "service-empty";
    empty.textContent = "当前没有可拖入目录的未纳管指标。";
    stagingList.appendChild(empty);
  } else {
    unmanagedMetrics.forEach((metric) => {
      const card = document.createElement("article");
      card.className = "unmanaged-metric-card";
      card.draggable = false;
      card.dataset.draggableMetric = metric.metricName;
      card.innerHTML = `
        <div class="metric-card-header">
          <div class="service-title">
            <strong>${escapeHtml(metric.displayName || metric.metricName)}</strong>
            <span class="metric-code">${escapeHtml(metric.metricName)}</span>
          </div>
        </div>
      `;
      card.querySelector(".metric-card-header").appendChild(renderStatusChip("created"));
      const meta = document.createElement("div");
      meta.className = "application-meta";
      meta.innerHTML = `
        <span class="application-tag">建议目录：${escapeHtml(metric.recommendedCategoryName || metric.recommendedCategory || "基础指标")}</span>
        <span class="application-tag">拖到右侧目录</span>
      `;
      card.appendChild(meta);
      const purpose = document.createElement("p");
      purpose.className = "metric-purpose-text";
      purpose.innerHTML = `<strong>作用：</strong>${escapeHtml(metric.purpose || "这是 Prometheus 已发现但尚未纳管的实时指标。")}`;
      card.appendChild(purpose);
      stagingList.appendChild(card);
    });
  }
  staging.appendChild(stagingList);

  const sectionsPanel = document.createElement("div");
  sectionsPanel.className = "metric-catalog-sections";

  categories.forEach((category) => {
    const section = document.createElement("section");
    section.className = "metric-catalog-section metric-drop-zone";
    section.dataset.dropCategory = category.id;
    section.innerHTML = `
      <div class="metric-section-head">
        <div class="service-title">
          <strong>${escapeHtml(category.name)}</strong>
          <span>${escapeHtml(category.description || "未填写分类说明。")}</span>
        </div>
      </div>
    `;
    const head = section.querySelector(".metric-section-head");
    const count = document.createElement("div");
    count.className = "status-summary";
    count.innerHTML = `<span>目录数：<strong>${(grouped.get(category.id) || []).length}</strong></span>`;
    head.appendChild(count);

    const hint = document.createElement("div");
    hint.className = "metric-drop-hint";
    hint.textContent = "可将“已发现但未纳管”的指标拖到这个目录，直接生成纳管条目。";
    section.appendChild(hint);

    const list = document.createElement("div");
    list.className = "metric-category-list";
    const categoryItems = grouped.get(category.id) || [];
    if (!categoryItems.length) {
      const empty = document.createElement("div");
      empty.className = "service-empty";
      empty.textContent = `当前“${category.name}”目录还没有指标。`;
      list.appendChild(empty);
    } else {
      categoryItems.forEach((metric) => {
        const card = document.createElement("article");
        card.className = "metric-card";
        card.dataset.metricId = metric.metricId;
        card.innerHTML = `
          <div class="metric-card-header">
            <div class="service-title">
              <strong>${escapeHtml(metric.displayName)}</strong>
              <span class="metric-code">${escapeHtml(metric.metricName)}</span>
            </div>
          </div>
        `;
        const actions = document.createElement("div");
        actions.className = "metric-actions";
        actions.appendChild(renderStatusChip(metricState(metric)));
        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.className = "secondary metric-remove-button";
        removeButton.dataset.removeMetric = metric.metricId;
        removeButton.textContent = "删除";
        actions.appendChild(removeButton);
        card.querySelector(".metric-card-header").appendChild(actions);

        const identity = document.createElement("div");
        identity.className = "metric-identity-grid";
        identity.innerHTML = `
          <div>
            <span class="metric-meta-label">指标名称</span>
            <strong>${escapeHtml(metric.displayName)}</strong>
          </div>
          <div>
            <span class="metric-meta-label">Prometheus 名称</span>
            <span class="metric-code">${escapeHtml(metric.metricName)}</span>
          </div>
        `;
        card.appendChild(identity);

        const purpose = document.createElement("div");
        purpose.className = "metric-purpose-block";
        purpose.innerHTML = `
          <span class="metric-meta-label">指标作用</span>
          <p>${escapeHtml(metricPurpose(metric))}</p>
        `;
        card.appendChild(purpose);

        const meta = document.createElement("div");
        meta.className = "application-meta";
        meta.innerHTML = `
          <span class="application-tag">${escapeHtml(metricCategoryName(metric.category))}</span>
          <span class="application-tag">${metric.sourceType === "recording_rule" ? "组合/规则指标" : "基础/原始指标"}</span>
          <span class="application-tag">${metric.ruleMode === "managed" ? "平台生成" : "外部来源"}</span>
          <span class="application-tag">${metric.live ? "Prometheus 已发现" : "尚未发现"}</span>
        `;
        card.appendChild(meta);

        const grid = document.createElement("div");
        grid.className = "metric-editor-grid";
        grid.innerHTML = `
          <label class="switch">
            <input type="checkbox" data-field="enabled" ${metric.enabled ? "checked" : ""}>
            <span>启用该指标</span>
          </label>
          <label>指标显示名<input type="text" data-field="displayName" value="${escapeHtml(metric.displayName)}"></label>
          <label>指标标识 ID<input type="text" data-field="metricId" value="${escapeHtml(metric.metricId)}"></label>
          <label>Prometheus 名称<input type="text" data-field="metricName" value="${escapeHtml(metric.metricName)}"></label>
          <label>指标分类
            <select data-field="category">${optionMarkup(categories.map((item) => ({ value: item.id, label: item.name })), metric.category)}</select>
          </label>
          <label>来源类型
            <select data-field="sourceType">${optionMarkup([{ value: "raw", label: "基础指标 / 原始采集" }, { value: "recording_rule", label: "组合或宏观指标 / Recording Rule" }], metric.sourceType)}</select>
          </label>
          <label>规则归属
            <select data-field="ruleMode">${optionMarkup([{ value: "external", label: "外部已有规则" }, { value: "managed", label: "由平台生成规则" }], metric.ruleMode)}</select>
          </label>
          <label>单位<input type="text" data-field="unit" value="${escapeHtml(metric.unit || "short")}"></label>
          <label class="full-width">指标作用<textarea rows="3" data-field="description">${escapeHtml(metric.description || "")}</textarea></label>
          <label class="full-width">来源基础指标，逗号分隔<input type="text" data-field="derivedFromCsv" value="${escapeHtml((metric.derivedFrom || []).join(", "))}"></label>
          <label class="full-width">组合表达式 / Recording Rule
            <textarea rows="4" data-field="expression" ${metric.sourceType === "raw" ? "disabled" : ""}>${escapeHtml(metric.expression || "")}</textarea>
          </label>
        `;
        card.appendChild(grid);

        const note = document.createElement("p");
        note.className = "metric-hint";
        note.textContent = "指标目录要求明确记录“名称 + 作用”。基础指标可直接引用原始 metric name；组合指标和宏观指标可在这里把多个基础指标组合成新的纳管指标。";
        card.appendChild(note);
        list.appendChild(card);
      });
    }
    section.appendChild(list);
    sectionsPanel.appendChild(section);
  });

  layout.appendChild(staging);
  layout.appendChild(sectionsPanel);
  metricCatalogList.appendChild(layout);
  attachMetricDragHandlers();
}

function renderMetricVisualizations() {
  const items = sortMetrics(currentMetricCatalog.items || []);
  metricVisualizationList.innerHTML = "";

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "service-empty";
    empty.textContent = "当前还没有可配置可视化的指标。";
    metricVisualizationList.appendChild(empty);
    return;
  }

  items.forEach((metric) => {
    const card = document.createElement("article");
    card.className = "metric-card";
    card.dataset.metricId = metric.metricId;
    card.innerHTML = `
      <div class="metric-card-header">
        <div class="service-title">
          <strong>${escapeHtml(metric.displayName)}</strong>
          <span class="metric-code">${escapeHtml(metric.metricName)}</span>
        </div>
      </div>
    `;
    card.querySelector(".metric-card-header").appendChild(
      renderStatusChip(metric.visualization?.showOnDashboard ? "running" : "created"),
    );

    const meta = document.createElement("div");
    meta.className = "application-meta";
    meta.innerHTML = `
      <span class="application-tag">${escapeHtml(metricCategoryName(metric.category))}</span>
      <span class="application-tag">${escapeHtml(metricPurpose(metric))}</span>
    `;
    card.appendChild(meta);

    const grid = document.createElement("div");
    grid.className = "metric-editor-grid";
    grid.innerHTML = `
      <label>图表类型
        <select data-field="visualization.panelType">${optionMarkup([{ value: "timeseries", label: "时序图" }, { value: "stat", label: "统计卡片" }, { value: "gauge", label: "仪表盘" }], metric.visualization?.panelType || "stat")}</select>
      </label>
      <label>展示单位<input type="text" data-field="visualization.unit" value="${escapeHtml(metric.visualization?.unit || metric.unit || "short")}"></label>
      <label>小数位数<input type="number" min="0" data-field="visualization.decimals" value="${Number(metric.visualization?.decimals ?? 0)}"></label>
      <label>配色模式
        <select data-field="visualization.colorMode">${optionMarkup([{ value: "value", label: "按值着色" }, { value: "background", label: "背景着色" }, { value: "palette-classic", label: "经典色板" }, { value: "thresholds", label: "阈值色" }], metric.visualization?.colorMode || "value")}</select>
      </label>
      <label class="switch full-width">
        <input type="checkbox" data-field="visualization.showOnDashboard" ${metric.visualization?.showOnDashboard ? "checked" : ""}>
        <span>加入自动生成的指标治理仪表盘</span>
      </label>
    `;
    card.appendChild(grid);

    const note = document.createElement("p");
    note.className = "metric-hint";
    note.innerHTML = `当前将以 <strong>${escapeHtml(metric.visualization?.panelType || "stat")}</strong> 形式展示，单位为 <strong>${escapeHtml(metric.visualization?.unit || metric.unit || "short")}</strong>。`;
    card.appendChild(note);
    metricVisualizationList.appendChild(card);
  });
}

function renderMetricViews() {
  renderMetricOverview();
  renderMetricCatalog();
  renderMetricVisualizations();
}

function ensureMetric(metricId) {
  return (currentMetricCatalog.items || []).find((item) => item.metricId === metricId) || null;
}

function updateMetricField(metricId, field, rawValue) {
  const metric = ensureMetric(metricId);
  if (!metric) {
    return;
  }

  let value = rawValue;
  let targetField = field;
  if (field === "derivedFromCsv") {
    targetField = "derivedFrom";
    value = parseCsv(rawValue);
  }
  if (field === "visualization.decimals") {
    value = Number.isFinite(rawValue) ? rawValue : Number.parseInt(String(rawValue || "0"), 10) || 0;
  }
  if (typeof value === "string" && !field.startsWith("description") && !field.startsWith("expression")) {
    value = value.trim();
  }

  setByPath(metric, targetField, value);

  if (field === "sourceType") {
    if (value === "raw" && metric.ruleMode === "managed") {
      metric.ruleMode = "external";
      metric.expression = "";
      metric.derivedFrom = [];
    }
    if (value === "recording_rule" && !String(metric.expression || "").trim()) {
      metric.expression = metric.metricName.includes(":") ? "" : 'sum(up{job="applications"})';
      metric.derivedFrom = metric.derivedFrom?.length ? metric.derivedFrom : ["up"];
    }
  }

  if (field === "unit") {
    metric.visualization = metric.visualization || {};
    metric.visualization.unit = value || "short";
  }
}

function readFieldValue(element) {
  if (element.type === "checkbox") {
    return element.checked;
  }
  if (element.type === "number") {
    return Number.parseInt(element.value || "0", 10);
  }
  return element.value;
}

function syncMetricInput(element) {
  const metricCard = element.closest("[data-metric-id]");
  const field = element.dataset.field;
  if (!metricCard || !field) {
    return;
  }
  updateMetricField(metricCard.dataset.metricId, field, readFieldValue(element));
}

function buildMetricTemplate() {
  const existingIds = new Set((currentMetricCatalog.items || []).map((item) => item.metricId));
  let sequence = (currentMetricCatalog.items || []).length + 1;
  let metricId = `custom_metric_${sequence}`;
  while (existingIds.has(metricId)) {
    sequence += 1;
    metricId = `custom_metric_${sequence}`;
  }

  const categoryIds = (currentMetricCatalog.categories || []).map((item) => item.id);
  const preferredCategory = categoryIds.includes("business")
    ? "business"
    : (categoryIds.includes("composite") ? "composite" : (categoryIds[0] || "basic"));

  return {
    metricId,
    metricName: `custom:${metricId}`,
    displayName: `自定义指标 ${sequence}`,
    category: preferredCategory,
    sourceType: "recording_rule",
    ruleMode: "managed",
    description: "请补充该指标的业务作用、适用场景和阈值含义。",
    expression: 'sum(up{job="applications"})',
    derivedFrom: ["up"],
    unit: "short",
    enabled: true,
    live: false,
    visualization: {
      panelType: "stat",
      unit: "short",
      decimals: 0,
      colorMode: "value",
      showOnDashboard: true,
    },
  };
}

async function loadMetrics() {
  const payload = await request("/api/v1/metrics/catalog");
  currentMetricCatalog = clone({
    categories: payload.categories || [],
    items: payload.items || [],
    liveMetrics: payload.liveMetrics || [],
    unmanagedLiveMetrics: payload.unmanagedLiveMetrics || [],
  });
  renderMetricViews();
}

async function saveConfig() {
  const config = readForm();
  setByPath(config, "applications.items", readApplications());
  setByPath(config, "metricCatalog.categories", clone(currentMetricCatalog.categories || []));
  setByPath(
    config,
    "metricCatalog.items",
    sortMetrics(currentMetricCatalog.items || []).map((item) => ({
      metricId: String(item.metricId || "").trim(),
      metricName: String(item.metricName || "").trim(),
      displayName: String(item.displayName || "").trim(),
      category: String(item.category || "").trim(),
      sourceType: String(item.sourceType || "raw").trim(),
      ruleMode: String(item.ruleMode || "external").trim(),
      description: String(item.description || "").trim(),
      expression: String(item.expression || ""),
      derivedFrom: parseCsv((item.derivedFrom || []).join(",")),
      unit: String(item.unit || "short").trim(),
      enabled: Boolean(item.enabled),
      visualization: {
        panelType: String(item.visualization?.panelType || "stat").trim(),
        unit: String(item.visualization?.unit || item.unit || "short").trim(),
        decimals: Number.parseInt(String(item.visualization?.decimals ?? 0), 10) || 0,
        colorMode: String(item.visualization?.colorMode || "value").trim(),
        showOnDashboard: Boolean(item.visualization?.showOnDashboard),
      },
    })),
  );

  const payload = await request("/api/v1/config", {
    method: "PUT",
    body: JSON.stringify({ config }),
  });
  fillForm(payload.config);
  setOutput(payload);
  await loadMetrics();
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  if (label) {
    button.dataset.originalLabel = button.dataset.originalLabel || button.textContent;
    button.textContent = busy ? label : button.dataset.originalLabel;
  }
}

async function loadConfig() {
  const payload = await request("/api/v1/config");
  fillForm(payload.config);
  setOutput({
    message: "配置已加载",
    lastAppliedAt: payload.config.metadata.lastAppliedAt,
    project: payload.config.system.monitoringProject,
  });
}

async function loadServices() {
  const payload = await request("/api/v1/system/services");
  renderServices(payload.services || [], payload.project);
}

async function loadRuntime() {
  const payload = await request("/api/v1/system/runtime");
  renderRuntime(payload.runtime);
}

async function loadApplications() {
  const payload = await request("/api/v1/applications/discovery");
  renderApplications(payload.applications || []);
}

async function reloadPrometheus() {
  const payload = await request("/api/v1/system/prometheus/reload", {
    method: "POST",
    body: JSON.stringify({}),
  });
  setOutput(payload);
}

async function restartStack() {
  const payload = await request("/api/v1/system/restart", {
    method: "POST",
    body: JSON.stringify({ includeControlPlane: false }),
  });
  setOutput(payload);
}

function handleMetricInteraction(event) {
  const removeButton = event.target.closest("[data-remove-metric]");
  if (removeButton) {
    const metricId = removeButton.dataset.removeMetric;
    currentMetricCatalog.items = (currentMetricCatalog.items || []).filter((item) => item.metricId !== metricId);
    renderMetricViews();
    setOutput({
      message: "指标已从目录移除。",
      metricId,
    });
    return;
  }

  const target = event.target;
  if (!target || !target.dataset?.field) {
    return;
  }

  syncMetricInput(target);
  const field = target.dataset.field;
  if (field === "category" || field === "sourceType" || field.startsWith("visualization.")) {
    renderMetricViews();
    return;
  }
  renderMetricOverview();
}

async function runAction(
  button,
  pendingLabel,
  action,
  {
    refreshConfig = false,
    refreshServices = false,
    refreshRuntime = false,
    refreshApplications = false,
    refreshMetrics = false,
  } = {},
) {
  try {
    setBusy(button, true, pendingLabel);
    await action();
    if (refreshConfig) {
      await loadConfig();
    }
    if (refreshServices) {
      await loadServices();
    }
    if (refreshRuntime) {
      await loadRuntime();
    }
    if (refreshApplications) {
      await loadApplications();
    }
    if (refreshMetrics) {
      await loadMetrics();
    }
  } catch (error) {
    setOutput({ error: error.message });
  } finally {
    setBusy(button, false);
  }
}

reloadConfigButton.addEventListener("click", () => {
  runAction(reloadConfigButton, "加载中...", loadConfig, {
    refreshServices: true,
    refreshRuntime: true,
    refreshApplications: true,
    refreshMetrics: true,
  });
});

saveConfigButton.addEventListener("click", () => {
  runAction(saveConfigButton, "保存中...", saveConfig, {
    refreshServices: true,
    refreshRuntime: true,
    refreshApplications: true,
    refreshMetrics: true,
  });
});

refreshStatusButton.addEventListener("click", () => {
  runAction(refreshStatusButton, "刷新中...", async () => {
    await Promise.all([loadServices(), loadRuntime()]);
  });
});

if (refreshApplicationsButton) {
  refreshApplicationsButton.addEventListener("click", () => {
    runAction(refreshApplicationsButton, "发现中...", loadApplications);
  });
}

if (refreshMetricsButton) {
  refreshMetricsButton.addEventListener("click", () => {
    runAction(refreshMetricsButton, "刷新中...", loadMetrics);
  });
}

if (addMetricButton) {
  addMetricButton.addEventListener("click", () => {
    const metric = buildMetricTemplate();
    currentMetricCatalog.items = [...(currentMetricCatalog.items || []), metric];
    renderMetricViews();
    activatePanel("metric-catalog");
    setOutput({
      message: "已新增指标定义，请补充名称、作用、表达式和可视化配置后保存。",
      metricId: metric.metricId,
      metricName: metric.metricName,
    });
  });
}

reloadPrometheusButton.addEventListener("click", () => {
  runAction(reloadPrometheusButton, "重载中...", reloadPrometheus, {
    refreshServices: true,
    refreshRuntime: true,
    refreshApplications: true,
    refreshMetrics: true,
  });
});

restartStackButton.addEventListener("click", () => {
  runAction(restartStackButton, "重启中...", restartStack, {
    refreshServices: true,
    refreshRuntime: true,
    refreshApplications: true,
    refreshMetrics: true,
  });
});

metricCatalogList?.addEventListener("input", handleMetricInteraction);
metricCatalogList?.addEventListener("change", handleMetricInteraction);
metricCatalogList?.addEventListener("click", handleMetricInteraction);
metricVisualizationList?.addEventListener("input", handleMetricInteraction);
metricVisualizationList?.addEventListener("change", handleMetricInteraction);

normalizeMetricSectionLabels();
initializeNavigation();

(async function bootstrap() {
  try {
    await Promise.all([loadConfig(), loadServices(), loadRuntime(), loadApplications(), loadMetrics()]);
  } catch (error) {
    setOutput({ error: error.message });
  }
})();
