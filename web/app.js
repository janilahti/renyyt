(() => {
  const $ = (id) => document.getElementById(id);
  const username = $("username"), password = $("password"), suffixes = $("suffixes"), remember = $("remember");
  const togglePasswordBtn = $("togglePasswordBtn");
  const loadBtn = $("loadBtn"), forgetBtn = $("forgetBtn"), status = $("status");
  const loginPanel = $("loginPanel"), compactLoadBtn = $("compactLoadBtn"), expandLoginBtn = $("expandLoginBtn"), compactStatus = $("compactStatus");
  const httpHelpBtn = $("httpHelpBtn"), compactHttpHelpBtn = $("compactHttpHelpBtn"), embedBtn = $("embedBtn"), compactEmbedBtn = $("compactEmbedBtn"), httpDialog = $("httpDialog"), closeHttpDialog = $("closeHttpDialog");
  const httpExample = $("httpExample"), curlExample = $("curlExample"), embedUrlExample = $("embedUrlExample"), savedEmbedBlock = $("savedEmbedBlock"), savedEmbedUrlExample = $("savedEmbedUrlExample");
  const jsonImportFile = $("jsonImportFile"), jsonImportStatus = $("jsonImportStatus");
  const themeSelect = $("themeSelect"), languageSelect = $("languageSelect");
  const readmeBtn = $("readmeBtn"), readmeDialog = $("readmeDialog"), readmeDialogTitle = $("readmeDialogTitle"), closeReadmeDialog = $("closeReadmeDialog"), readmeStatus = $("readmeStatus"), readmeContent = $("readmeContent");
  const aboutBtn = $("aboutBtn"), aboutDialog = $("aboutDialog"), closeAboutDialog = $("closeAboutDialog"), aboutStatus = $("aboutStatus"), aboutContent = $("aboutContent"), aboutVersion = $("aboutVersion"), aboutBuildTime = $("aboutBuildTime"), aboutGitCommit = $("aboutGitCommit");
  const feedbackBtn = $("feedbackBtn"), feedbackDialog = $("feedbackDialog"), closeFeedbackDialog = $("closeFeedbackDialog"), feedbackMessage = $("feedbackMessage"), feedbackEmail = $("feedbackEmail"), feedbackAttachData = $("feedbackAttachData"), feedbackAttachRow = $("feedbackAttachRow"), sendFeedbackBtn = $("sendFeedbackBtn"), feedbackStatus = $("feedbackStatus");
  const installBtn = $("installBtn"), installDialog = $("installDialog"), closeInstallDialog = $("closeInstallDialog");
  const reminderDialog = $("reminderDialog"), closeReminderDialog = $("closeReminderDialog"), reminderDays = $("reminderDays"), reminderTime = $("reminderTime"), reminderSupportHelp = $("reminderSupportHelp"), enableRemindersBtn = $("enableRemindersBtn"), disableRemindersBtn = $("disableRemindersBtn"), reminderStatus = $("reminderStatus");
  const resultsPanel = $("resultsPanel"), cards = $("cards"), resultMeta = $("resultMeta"), nextSummary = $("nextSummary");
  const orderModeSelect = $("orderModeSelect"), compactViewBtn = $("compactViewBtn"), icsBtn = $("icsBtn"), serviceFilterBtn = $("serviceFilterBtn"), reminderBtn = $("reminderBtn"), resultsToolbar = $("resultsToolbar");
  const serviceFilterDialog = $("serviceFilterDialog"), closeServiceFilterDialog = $("closeServiceFilterDialog"), serviceFilterList = $("serviceFilterList"), resetServiceFiltersBtn = $("resetServiceFiltersBtn");
  const aboutBasePath = $("aboutBasePath"), aboutLastFetch = $("aboutLastFetch"), aboutCachedAt = $("aboutCachedAt"), aboutServiceWorker = $("aboutServiceWorker");
  let currentData = null;
  let dayChangeTimer = null;
  let autoReloadTimer = null;
  let autoReloadDueAt = null;
  let lastFetchConfig = null;
  let renderedDayKey = null;
  let lastSuccessfulFetchAt = null;
  let lastRenderedServiceCount = 0;
  let lastAutoRefreshError = "";
  let lastRenderErrorCount = 0;
  let lastApiWarningCount = 0;
  let lastStatusSpec = null;
  let passwordUserEntered = false;
  let deferredInstallPrompt = null;
  let currentDataIsStale = false;
  let draggedServiceKey = null;
  let cachedAt = null;
  let savedCredentialsCache = null;
  let savedCredentialsStorageValue = null;
  let reminderFeature = null;
  let embeddedVisibilityKeys = null;
  let embeddedViewState = null;

  const { detectAppBasePath, isoWeek, formatIntervalInfo, daysUntil, isSameIsoWeek, formatShare, serviceKey, effectiveServiceVisibility, applyManualOrder, sortByCollectionDate, nextCollectionRefreshAt, startsFullSecretEntry } = window.RenyytHelpers;

  const APP_BASE_PATH = detectAppBasePath(location.pathname);
  const appPath = (relative) => `${APP_BASE_PATH}/${String(relative).replace(/^\/+/, "")}`;
  const appUrl = (relative) => `${location.origin}${appPath(relative)}`;

  const I18N = window.RenyytI18n;
  let currentLanguage = I18N.normalizeLanguage(localStorage.getItem("renyyt.language") || "fi");
  const t = (key, vars) => I18N.t(currentLanguage, key, vars);
  const localeForLanguage = () => I18N.locale(currentLanguage);

  const CACHE_KEY = "renyyt.lastData";
  let orderMode = localStorage.getItem("renyyt.orderMode") === "manual" ? "manual" : "date";
  let compactView = localStorage.getItem("renyyt.compactView") === "1";
  let manualOrder = (() => { try { const v = JSON.parse(localStorage.getItem("renyyt.manualOrder") || "[]"); return Array.isArray(v) ? v : []; } catch (_) { return []; } })();
  const SERVICE_FILTER_KEY = "renyyt.serviceVisibility";
  let serviceVisibility = loadServiceVisibility();

  function loadServiceVisibility() {
    try {
      const value = JSON.parse(localStorage.getItem(SERVICE_FILTER_KEY) || "null");
      if (!value || value.version !== 1) return { version: 1, normal: {}, embed: {}, reminders: {} };
      return {
        version: 1,
        normal: value.normal && typeof value.normal === "object" ? value.normal : {},
        embed: value.embed && typeof value.embed === "object" ? value.embed : {},
        reminders: value.reminders && typeof value.reminders === "object" ? value.reminders : {}
      };
    } catch (_) { return { version: 1, normal: {}, embed: {}, reminders: {} }; }
  }

  function saveServiceVisibility() {
    localStorage.setItem(SERVICE_FILTER_KEY, JSON.stringify(serviceVisibility));
  }

  function serviceVisible(service, scope) {
    if (scope === "embed" && Array.isArray(embeddedVisibilityKeys)) return embeddedVisibilityKeys.includes(serviceKey(service));
    return effectiveServiceVisibility(serviceVisibility, service, scope);
  }

  function currentVisibilityScope() {
    return document.body.classList.contains("embed-mode") ? "embed" : "normal";
  }

  function serviceDisplayName(service) {
    const pg = service?.tariff?.productgroup || "";
    return productTitle(pg) || service?.ASTNimi || service?.tariff?.name || pg || t("waste.default");
  }

  function setScopedVisibility(scope, key, value) {
    if (scope === "normal") {
      if (value === true) delete serviceVisibility.normal[key];
      else serviceVisibility.normal[key] = false;
    } else if (value === null) {
      delete serviceVisibility[scope][key];
    } else {
      serviceVisibility[scope][key] = !!value;
    }
    saveServiceVisibility();
  }

  function scopedVisibilityValue(scope, key) {
    if (scope === "normal") return serviceVisibility.normal[key] === false ? "hide" : "show";
    if (!Object.prototype.hasOwnProperty.call(serviceVisibility[scope], key)) return "inherit";
    return serviceVisibility[scope][key] === false ? "hide" : "show";
  }

  function renderServiceFilterDialog() {
    serviceFilterList.innerHTML = "";
    const seen = new Set();
    const services = orderedServices((currentData?.services || []).filter(s => s && typeof s === "object"));
    services.forEach(service => {
      const key = serviceKey(service);
      if (!key || seen.has(key)) return;
      seen.add(key);
      const row = document.createElement("div");
      row.className = "service-filter-row";
      const normalChecked = serviceVisible(service, "normal");
      const makeSelect = (scope) => {
        const select = document.createElement("select");
        [["inherit", t("filters.inherit")], ["show", t("filters.show")], ["hide", t("filters.hide")]].forEach(([value,label]) => { const option=document.createElement("option"); option.value=value; option.textContent=label; select.appendChild(option); });
        select.value = scopedVisibilityValue(scope, key);
        select.addEventListener("change", () => {
          setScopedVisibility(scope, key, select.value === "inherit" ? null : select.value === "show");
          if (currentData) render(currentData);
          if (scope === "reminders" || scope === "normal") void syncReminderSnapshotIfSubscribed(currentData, false);
        });
        return select;
      };
      const name = document.createElement("strong"); name.className="service-filter-name"; name.dir="auto"; name.textContent=serviceDisplayName(service);
      const normalLabel=document.createElement("label"); const normal=document.createElement("input"); normal.type="checkbox"; normal.checked=normalChecked; normalLabel.append(t("filters.normal")+" ", normal);
      normal.addEventListener("change", () => { setScopedVisibility("normal", key, normal.checked); if (currentData) render(currentData); void syncReminderSnapshotIfSubscribed(currentData, false); });
      const embedLabel=document.createElement("label"); embedLabel.append(t("filters.embed")+" ", makeSelect("embed"));
      const remindersLabel=document.createElement("label"); remindersLabel.append(t("filters.reminders")+" ", makeSelect("reminders"));
      row.append(name, normalLabel, embedLabel, remindersLabel);
      serviceFilterList.appendChild(row);
    });
  }

  function openServiceFilterDialog(event) {
    lastDialogTrigger = event?.currentTarget || serviceFilterBtn;
    renderServiceFilterDialog();
    serviceFilterDialog.showModal();
  }

  function sanitizeServiceForCache(service) {
    const tariff = service?.tariff || {};
    const kimppa = service?.kimppa;
    return {
      ASTAsnro: service?.ASTAsnro ?? null, ASTTyyppi: service?.ASTTyyppi ?? null, ASTPos: service?.ASTPos ?? null,
      id: service?.id ? { ASTAsnro: service.id.ASTAsnro ?? null, ASTTyyppi: service.id.ASTTyyppi ?? null, ASTPos: service.id.ASTPos ?? null } : null,
      ASTNextDate: service?.ASTNextDate ?? null, ASTVali: service?.ASTVali ?? null, ASTVali2: service?.ASTVali2 ?? null,
      ASTVoim1: service?.ASTVoim1 ?? null, ASTVoim2: service?.ASTVoim2 ?? null, ASTVoim21: service?.ASTVoim21 ?? null, ASTVoim22: service?.ASTVoim22 ?? null,
      ASTNimi: service?.ASTNimi ?? null, ASTMaara: service?.ASTMaara ?? null, ASTHinta: service?.ASTHinta ?? null,
      ASTAlkPvm: service?.ASTAlkPvm ?? null, ASTKomm: service?.ASTKomm ?? null, KIRPros: service?.KIRPros ?? null,
      tariff: { productgroup: tariff.productgroup ?? null, name: tariff.name ?? null, size: tariff.size ?? null, unit: tariff.unit ?? null },
      kimppa: kimppa ? { KIMNimi1: kimppa.KIMNimi1 ?? null, KIMNimi4: kimppa.KIMNimi4 ?? null, KIMMaara: kimppa.KIMMaara ?? null,
        isanta: kimppa.isanta ? { nimi: kimppa.isanta.nimi ?? null, osoite: kimppa.isanta.osoite ?? null } : null } : null
    };
  }

  function saveDataCache(data, customer) {
    try {
      const payload = { version: 1, customer: String(customer || ""), savedAt: new Date().toISOString(), services: (data?.services || []).map(sanitizeServiceForCache) };
      localStorage.setItem(CACHE_KEY, JSON.stringify(payload));
      cachedAt = new Date(payload.savedAt);
    } catch (_) {}
  }

  function getDataCache(customer) {
    try {
      const value = JSON.parse(localStorage.getItem(CACHE_KEY) || "null");
      if (!value || value.version !== 1 || !Array.isArray(value.services)) return null;
      if (customer && value.customer && String(customer) !== String(value.customer)) return null;
      return { services: value.services, warnings: [], _cachedAt: value.savedAt };
    } catch (_) { return null; }
  }

  function renderCachedFallback(customer, error) {
    const cached = getDataCache(customer);
    if (!cached) return false;
    currentDataIsStale = true;
    cachedAt = cached._cachedAt ? new Date(cached._cachedAt) : null;
    render(cached);
    setStatus(t("cache.fallback", { error: error?.message || String(error) }), "error", { type: "key", key: "cache.fallback", vars: { error: error?.message || String(error) }, kind: "error" });
    return true;
  }

  function effectiveOrderMode() { return embeddedViewState?.orderMode || orderMode; }
  function effectiveManualOrder() { return embeddedViewState?.manualOrder || manualOrder; }
  function effectiveCompactView() { return embeddedViewState ? !!embeddedViewState.compactView : compactView; }

  function updateViewControls() {
    const activeOrderMode = effectiveOrderMode();
    const activeCompactView = effectiveCompactView();
    if (orderModeSelect) orderModeSelect.value = activeOrderMode;
    resultsPanel.classList.toggle("compact-view", activeCompactView);
    compactViewBtn.textContent = t(activeCompactView ? "view.normal" : "view.compact");
  }

  function applyLanguage(lang, persist = true) {
    currentLanguage = I18N.normalizeLanguage(lang);
    document.documentElement.lang = currentLanguage;
    document.documentElement.dir = I18N.direction(currentLanguage);
    languageSelect.value = currentLanguage;
    document.title = t("app.title");
    document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); });
    document.querySelectorAll("[data-i18n-aria-label]").forEach(el => { el.setAttribute("aria-label", t(el.dataset.i18nAriaLabel)); });
    if (persist) localStorage.setItem("renyyt.language", currentLanguage);
    updateSavedCredentialUi();
    updatePasswordToggleUi();
    rerenderStatusForLanguage();
    if (currentData) render(currentData);
    if (serviceFilterDialog?.open) renderServiceFilterDialog();
    buildHttpExamples();
    updateViewControls();
  }

  const savedTheme = localStorage.getItem("renyyt.theme") || "system";
  themeSelect.value = ["system", "light", "dark"].includes(savedTheme) ? savedTheme : "system";
  applyTheme(themeSelect.value);
  applyLanguage(currentLanguage, false);


  function base64UrlEncode(bytes) {
    let binary = "";
    bytes.forEach(byte => { binary += String.fromCharCode(byte); });
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
  }

  function base64UrlDecode(value) {
    const text = String(value || "");
    const padded = text.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (text.length % 4)) % 4);
    return Uint8Array.from(atob(padded), char => char.charCodeAt(0));
  }

  async function encodeOpaqueBlob(value) {
    if (!globalThis.crypto?.subtle || !globalThis.crypto?.getRandomValues) throw new Error("Web Crypto is not available.");
    const keyBytes = crypto.getRandomValues(new Uint8Array(32));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const key = await crypto.subtle.importKey("raw", keyBytes, "AES-GCM", false, ["encrypt"]);
    const plaintext = new TextEncoder().encode(JSON.stringify(value));
    const ciphertext = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plaintext));
    return `v1.${base64UrlEncode(keyBytes)}.${base64UrlEncode(iv)}.${base64UrlEncode(ciphertext)}`;
  }

  async function decodeOpaqueBlob(blob) {
    const parts = String(blob || "").split(".");
    if (parts.length !== 4 || parts[0] !== "v1" || !globalThis.crypto?.subtle) return null;
    try {
      const key = await crypto.subtle.importKey("raw", base64UrlDecode(parts[1]), "AES-GCM", false, ["decrypt"]);
      const plaintext = await crypto.subtle.decrypt({ name: "AES-GCM", iv: base64UrlDecode(parts[2]) }, key, base64UrlDecode(parts[3]));
      return JSON.parse(new TextDecoder().decode(plaintext));
    } catch (_) {
      return null;
    }
  }

  async function encodeCredentialBlob(credentials) {
    return encodeOpaqueBlob({
      username: String(credentials?.username || ""),
      password: String(credentials?.password || ""),
      suffixes: Array.isArray(credentials?.suffixes) ? credentials.suffixes.map(String) : []
    });
  }

  async function decodeCredentialBlob(blob) {
    const value = await decodeOpaqueBlob(blob);
    if (!value || typeof value.username !== "string" || typeof value.password !== "string" || !Array.isArray(value.suffixes)) return null;
    return { username: value.username, password: value.password, suffixes: value.suffixes.map(String) };
  }

  async function encodeEmbedViewState(state) {
    return encodeOpaqueBlob({
      embedVisibleKeys: Array.isArray(state?.embedVisibleKeys) ? state.embedVisibleKeys.map(String) : [],
      orderMode: state?.orderMode === "manual" ? "manual" : "date",
      manualOrder: Array.isArray(state?.manualOrder) ? state.manualOrder.map(String) : [],
      compactView: !!state?.compactView
    });
  }

  async function decodeEmbedViewState(blob) {
    const value = await decodeOpaqueBlob(blob);
    if (!value || !Array.isArray(value.embedVisibleKeys) || !Array.isArray(value.manualOrder)) return null;
    return {
      embedVisibleKeys: value.embedVisibleKeys.map(String),
      orderMode: value.orderMode === "manual" ? "manual" : "date",
      manualOrder: value.manualOrder.map(String),
      compactView: !!value.compactView
    };
  }

  function getSavedCredentials() {
    return savedCredentialsCache;
  }

  async function loadSavedCredentials() {
    try {
      const stored = localStorage.getItem("renyyt.credentials");
      const value = JSON.parse(stored || "null");
      if (!value || value.version !== 4 || typeof value.credentials !== "string") {
        savedCredentialsCache = null;
        return null;
      }
      savedCredentialsCache = await decodeCredentialBlob(value.credentials);
      savedCredentialsStorageValue = stored;
      return savedCredentialsCache;
    } catch (_) {
      savedCredentialsCache = null;
      return null;
    }
  }

  async function saveCredentials(credentials) {
    const normalized = {
      username: String(credentials?.username || ""),
      password: String(credentials?.password || ""),
      suffixes: Array.isArray(credentials?.suffixes) ? credentials.suffixes.map(String) : []
    };
    const blob = await encodeCredentialBlob(normalized);
    const stored = JSON.stringify({ version: 4, credentials: blob });
    localStorage.setItem("renyyt.credentials", stored);
    savedCredentialsStorageValue = stored;
    savedCredentialsCache = normalized;
  }

  function updateSavedCredentialUi() {
    const available = !!getSavedCredentials();
    embedBtn.classList.toggle("hidden", !available);
    compactEmbedBtn.classList.toggle("hidden", !available);
    forgetBtn.disabled = !available;
    forgetBtn.title = available ? "" : t("status.noSaved");
  }

  function updatePasswordToggleUi() {
    const enabled = passwordUserEntered && password.value.length > 0;
    togglePasswordBtn.disabled = !enabled;
    if (!enabled) password.type = "password";
    const visible = password.type === "text";
    const label = t(visible ? "login.hidePassword" : "login.showPassword");
    togglePasswordBtn.setAttribute("aria-label", label);
    togglePasswordBtn.title = label;
    togglePasswordBtn.dataset.visible = visible ? "true" : "false";
    togglePasswordBtn.setAttribute("aria-pressed", visible ? "true" : "false");
  }

  updatePasswordToggleUi();

  function applyTheme(theme) {
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  }

  function normalizeTheme(theme) {
    return ["system", "light", "dark"].includes(theme) ? theme : "system";
  }

  function applyEmbedTheme(theme) {
    const normalized = normalizeTheme(theme);
    themeSelect.value = normalized;
    applyTheme(normalized);
  }

  themeSelect.addEventListener("change", () => {
    const theme = themeSelect.value;
    applyTheme(theme);
    if (theme === "system") localStorage.removeItem("renyyt.theme");
    else localStorage.setItem("renyyt.theme", theme);
  });

  languageSelect.addEventListener("change", () => applyLanguage(languageSelect.value));

  function setLoginCompact(compact) {
    loginPanel.classList.toggle("compact", compact);
    document.body.classList.toggle("login-compact", compact);
    if (compact) {
      compactStatus.textContent = status.textContent;
      compactStatus.className = status.className;
    }
  }

  function setStatus(message, kind = "", spec = null) {
    const className = `status${kind ? ` ${kind}` : ""}`;
    status.className = className;
    compactStatus.className = className;
    status.textContent = message;
    compactStatus.textContent = message;
    lastStatusSpec = spec || { type: "literal", message, kind };
  }

  function setStatusKey(key, kind = "", vars = {}) {
    setStatus(t(key, vars), kind, { type: "key", key, vars, kind });
  }

  function setStatusError(error, kind = "error") {
    const code = error?.code || "";
    if (code && t(`error.${code}`) !== `error.${code}`) {
      setStatus(t(`error.${code}`), kind, { type: "error", code, kind });
      return;
    }
    setStatus(error?.message || String(error), kind, { type: "literal", message: error?.message || String(error), kind });
  }

  function rerenderStatusForLanguage() {
    if (!lastStatusSpec) return;
    if (lastStatusSpec.type === "key") {
      const { key, vars = {}, kind = "" } = lastStatusSpec;
      const message = t(key, vars);
      status.textContent = message;
      compactStatus.textContent = message;
      const className = `status${kind ? ` ${kind}` : ""}`;
      status.className = className;
      compactStatus.className = className;
    } else if (lastStatusSpec.type === "error") {
      const { code, kind = "error" } = lastStatusSpec;
      const message = t(`error.${code}`);
      status.textContent = message;
      compactStatus.textContent = message;
      const className = `status${kind ? ` ${kind}` : ""}`;
      status.className = className;
      compactStatus.className = className;
    } else if (lastStatusSpec.type === "autoError") {
      const { code, fallback, kind = "error" } = lastStatusSpec;
      const inner = code && t(`error.${code}`) !== `error.${code}` ? t(`error.${code}`) : fallback;
      const message = t("auto.failed", { error: inner });
      status.textContent = message;
      compactStatus.textContent = message;
      const className = `status${kind ? ` ${kind}` : ""}`;
      status.className = className;
      compactStatus.className = className;
    }
  }

  const productTitle = (pg) => pg && t(`waste.${pg}`) !== `waste.${pg}` ? t(`waste.${pg}`) : null;

  const localizedDate = (iso) => {
    if (!iso) return "–";
    const d = new Date(iso + "T12:00:00");
    return new Intl.DateTimeFormat(localeForLanguage(), { weekday:"short", day:"numeric", month:"numeric", year:"numeric" }).format(d);
  };

  const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));

  function syntaxHighlightJson(value) {
    const json = JSON.stringify(value, null, 2).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return json.replace(/("(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"\s*:|"(?:\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"|-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b|\btrue\b|\bfalse\b|\bnull\b)/g, token => {
      if (/^"/.test(token)) {
        const isKey = /:$/.test(token.trim());
        const suffixMatch = token.match(/(\s*:)?$/);
        const suffix = suffixMatch ? suffixMatch[0] : "";
        const quoted = suffix ? token.slice(0, -suffix.length) : token;
        const inner = quoted.slice(1, -1);
        const cls = isKey ? "json-key" : "json-string";
        return `<span class="json-quote">&quot;</span><span class="${cls}">${inner}</span><span class="json-quote">&quot;</span>${suffix}`;
      }
      if (/true|false/.test(token)) return `<span class="json-boolean">${token}</span>`;
      if (/null/.test(token)) return `<span class="json-null">${token}</span>`;
      return `<span class="json-number">${token}</span>`;
    });
  }

  function kimppaInfo(service) {
    // Renyyn vastauksessa tavallisella astialla `kimppa` on null ja
    // kimppa-astialla se on kimppatiedot sisältävä olio.
    if (!service?.kimppa || typeof service.kimppa !== "object") return null;

    const k = service.kimppa;
    const ownShare = service.KIRPros ?? null;
    return {
      name: k.KIMNimi1 || k?.isanta?.nimi || t("shared.defaultName"),
      address: k.KIMNimi4 || k?.isanta?.osoite || null,
      share: ownShare,
      memberCount: k.KIMMaara ?? (Array.isArray(k.osakkaat) ? k.osakkaat.length : null)
    };
  }

  const localDayKey = () => {
    const d = new Date();
    return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
  };

  function sameLocalDay(a, b = new Date()) {
    return !!a && a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  }

  function formatStatusTime(date, includeDate = false) {
    if (!date) return "";
    const opts = includeDate
      ? { day:"numeric", month:"numeric", hour:"2-digit", minute:"2-digit" }
      : { hour:"2-digit", minute:"2-digit" };
    return new Intl.DateTimeFormat(localeForLanguage(), opts).format(date).replace(/\s+klo\s+/i, " ");
  }

  function formatPastStatusTime(date) {
    return formatStatusTime(date, !sameLocalDay(date));
  }

  function updateResultMeta() {
    const parts = [t("results.services", { count: lastRenderedServiceCount })];
    if (lastSuccessfulFetchAt) parts.push(t("results.updated", { time: formatPastStatusTime(lastSuccessfulFetchAt) }));
    if (currentDataIsStale && cachedAt) parts.push(t("cache.stale", { time: formatPastStatusTime(cachedAt) }));
    if (lastAutoRefreshError) parts.push(t("results.autoError"));
    if (lastApiWarningCount) parts.push(t("results.apiWarnings", { count: lastApiWarningCount }));
    if (lastRenderErrorCount) parts.push(t("results.renderErrors", { count: lastRenderErrorCount }));
    if (autoReloadDueAt) {
      const now = new Date();
      const sameDay = now.toDateString() === autoReloadDueAt.toDateString();
      parts.push(t("results.nextUpdate", { time: formatStatusTime(autoReloadDueAt, !sameDay) }));
    }
    resultMeta.textContent = parts.join(" · ");
    const warnings = Array.isArray(currentData?.warnings) ? currentData.warnings : [];
    resultMeta.title = warnings.length ? warnings.map(w => w?.message || w?.code || t("results.apiWarnings", {count:1})).join("\n") : "";
  }

  function renderStateMessage(title, message, kind = "", role = "status") {
    cards.innerHTML = `<div class="state-message${kind ? ` ${kind}` : ""}" role="${role}"><strong>${escapeHtml(title)}</strong><div>${escapeHtml(message)}</div></div>`;
  }

  function scheduleDayRefresh() {
    if (dayChangeTimer) clearTimeout(dayChangeTimer);
    const now = new Date();
    const nextMidnight = new Date(now);
    nextMidnight.setHours(24, 0, 1, 0);
    dayChangeTimer = setTimeout(() => {
      if (currentData) render(currentData);
      scheduleDayRefresh();
    }, Math.max(1000, nextMidnight.getTime() - now.getTime()));
  }

  function nextAutoReloadTime(data) {
    return nextCollectionRefreshAt(data?.services || [], new Date());
  }

  function scheduleAutoReload(data) {
    if (autoReloadTimer) clearTimeout(autoReloadTimer);
    autoReloadTimer = null;
    autoReloadDueAt = nextAutoReloadTime(data);
    updateResultMeta();
    if (!autoReloadDueAt || !lastFetchConfig) return;

    const delay = Math.max(1000, autoReloadDueAt.getTime() - Date.now());
    autoReloadTimer = setTimeout(() => refreshFromLastConfig(true), delay);
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    if (!ok) throw new Error(t("status.copyFailLong"));
  }

  function markdownInline(text) {
    let out = escapeHtml(text);
    // Handle code and HTTP(S) autolinks together so URLs inside code stay literal.
    // Both captures are already HTML-escaped, including quotes in href values.
    out = out.replace(/`([^`]+)`|&lt;(https?:\/\/(?:(?!&(?:lt|gt);)[^\s<>])+)&gt;/gi, (match, code, href) =>
      code !== undefined ? `<code>${code}</code>` : `<a href="${href}" target="_blank" rel="noopener noreferrer">${href}</a>`);
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\[([^\]]+)\]\(([^\s)]+)\)/g, (match, label, href) => {
      const decoded = href.replace(/&amp;/g, "&");
      if (/^https?:\/\//i.test(decoded)) {
        return `<a href="${escapeHtml(decoded)}" target="_blank" rel="noopener noreferrer">${label}</a>`;
      }
      if (/^(?:\.\/)?[A-Za-z0-9_.\/-]+(?:#[A-Za-z0-9_.:-]+)?$/.test(decoded)) {
        const target = decoded.replace(/^\.\//, "");
        const docAttr = /^[A-Za-z0-9_.\/-]+\.md(?:#[A-Za-z0-9_.:-]+)?$/i.test(target)
          ? ` data-doc-path="${escapeHtml(target.split("#")[0])}"`
          : "";
        return `<a href="${escapeHtml(appPath(target))}"${docAttr}>${label}</a>`;
      }
      return match;
    });
    return out;
  }

  function renderMarkdown(markdown) {
    const lines = String(markdown || "").replace(/\r\n?/g, "\n").split("\n");
    const html = [];
    let inCode = false, codeLang = "", codeLines = [], listOpen = false, paragraph = [];
    const flushParagraph = () => {
      if (paragraph.length) {
        html.push(`<p>${markdownInline(paragraph.join(" ").trim())}</p>`);
        paragraph = [];
      }
    };
    const closeList = () => { if (listOpen) { html.push("</ul>"); listOpen = false; } };
    for (const line of lines) {
      const fence = line.match(/^```\s*([^\s]*)\s*$/);
      if (fence) {
        if (inCode) {
          html.push(`<pre><code${codeLang ? ` class="language-${escapeHtml(codeLang)}"` : ""}>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
          inCode = false; codeLang = ""; codeLines = [];
        } else {
          flushParagraph(); closeList(); inCode = true; codeLang = fence[1] || "";
        }
        continue;
      }
      if (inCode) { codeLines.push(line); continue; }
      if (!line.trim()) { flushParagraph(); closeList(); continue; }
      const heading = line.match(/^(#{1,3})\s+(.+)$/);
      if (heading) {
        flushParagraph(); closeList();
        const level = heading[1].length;
        html.push(`<h${level}>${markdownInline(heading[2])}</h${level}>`);
        continue;
      }
      const bullet = line.match(/^\s*-\s+(.+)$/);
      if (bullet) {
        flushParagraph();
        if (!listOpen) { html.push("<ul>"); listOpen = true; }
        html.push(`<li>${markdownInline(bullet[1])}</li>`);
        continue;
      }
      closeList();
      paragraph.push(line.trim());
    }
    if (inCode) html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    flushParagraph(); closeList();
    return html.join("\n");
  }

  async function showAboutDialog(event) {
    lastDialogTrigger = event?.currentTarget || document.activeElement;
    aboutStatus.textContent = t("about.loading");
    aboutStatus.className = "status";
    aboutContent.classList.add("hidden");
    if (typeof aboutDialog.showModal === "function") aboutDialog.showModal();
    else aboutDialog.setAttribute("open", "");
    try {
      const response = await fetch(appPath("version"), { cache: "no-store" });
      if (!response.ok) throw new Error(t("about.error", { status: response.status }));
      const data = await response.json();
      aboutVersion.textContent = data.version || "–";
      aboutBuildTime.textContent = data.buildTime || "–";
      aboutGitCommit.textContent = data.gitCommit || "–";
      aboutBasePath.textContent = APP_BASE_PATH || "/";
      aboutLastFetch.textContent = lastSuccessfulFetchAt ? formatPastStatusTime(lastSuccessfulFetchAt) : "–";
      const cache = getDataCache(username.value.trim());
      aboutCachedAt.textContent = cache?._cachedAt ? formatPastStatusTime(new Date(cache._cachedAt)) : "–";
      aboutServiceWorker.textContent = ("serviceWorker" in navigator) ? (navigator.serviceWorker.controller ? t("about.swActive") : t("about.swAvailable")) : t("about.swUnavailable");
      aboutStatus.textContent = "";
      aboutContent.classList.remove("hidden");
    } catch (error) {
      aboutStatus.textContent = error instanceof TypeError ? t("about.networkError") : (error?.message || t("about.networkError"));
      aboutStatus.className = "status error";
    }
  }

  async function showMarkdownDocument(path, event, openDialog = true) {
    const safePath = String(path || "README.md").replace(/^\.\//, "");
    if (!/^[A-Za-z0-9_.\/-]+\.md$/i.test(safePath)) return;
    if (openDialog) lastDialogTrigger = event?.currentTarget || document.activeElement;
    readmeDialogTitle.textContent = safePath.split("/").pop();
    readmeStatus.textContent = t("document.loading");
    readmeStatus.className = "status";
    readmeContent.classList.add("hidden");
    if (openDialog && !readmeDialog.open) {
      if (typeof readmeDialog.showModal === "function") readmeDialog.showModal();
      else readmeDialog.setAttribute("open", "");
    }
    try {
      const r = await fetch(appPath(safePath), { cache: "no-store" });
      if (!r.ok) throw new Error(t("document.error", { status: r.status }));
      const markdown = await r.text();
      const documentLanguage = safePath.match(/^README\.([A-Za-z-]+)\.md$/)?.[1];
      readmeContent.lang = documentLanguage || (["README.md", "TECHNICAL.md"].includes(safePath) ? "fi" : "en");
      readmeContent.dir = documentLanguage ? I18N.direction(documentLanguage) : "ltr";
      readmeContent.innerHTML = renderMarkdown(markdown);
      readmeStatus.textContent = "";
      readmeContent.classList.remove("hidden");
      readmeContent.scrollTop = 0;
      readmeDialog.scrollTop = 0;
    } catch (e) {
      readmeStatus.textContent = e instanceof TypeError ? t("document.networkError") : (e?.message || t("document.networkError"));
      readmeStatus.className = "status error";
    }
  }

  async function showReadmeDialog(event) {
    return showMarkdownDocument(`README.${currentLanguage}.md`, event, true);
  }

  function apiPayloadForExample() {
    const user = username.value.trim() || `<${t("example.customer")}>`;
    const pass = password.value || `<${t("example.password")}>`;
    const suffixList = suffixes.value.split(",").map(x => x.trim()).filter(Boolean);
    return { username: user, password: pass, suffixes: suffixList };
  }

  async function embedUrlFromPayload(payload, includeCredentials = true) {
    const params = new URLSearchParams();
    params.set("theme", normalizeTheme(themeSelect.value));
    params.set("lang", currentLanguage);
    const embedVisibleKeys = currentData ? (currentData.services || []).filter(service => serviceVisible(service, "embed")).map(serviceKey).filter(Boolean) : [];
    params.set("view", await encodeEmbedViewState({ embedVisibleKeys, orderMode, manualOrder, compactView }));
    if (includeCredentials) params.set("credentials", await encodeCredentialBlob(payload));
    return `${appUrl("embed")}#${params.toString()}`;
  }

  async function buildHttpExamples() {
    const payload = apiPayloadForExample();
    const body = JSON.stringify(payload, null, 2);
    const byteLength = new TextEncoder().encode(body).length;
    httpExample.textContent = `POST ${appPath("api/v1/renyyt")} HTTP/1.1\nHost: ${location.host}\nContent-Type: application/json\nContent-Length: ${byteLength}\n\n${body}`;
    curlExample.textContent = `curl --request POST '${appUrl("api/v1/renyyt")}' \\
  --header 'Content-Type: application/json' \\
  --data-binary @- <<'JSON'\n${body}\nJSON`;
    embedUrlExample.textContent = await embedUrlFromPayload(payload);
    const savedCreds = getSavedCredentials();
    savedEmbedBlock.classList.toggle("hidden", !savedCreds);
    if (savedCreds) savedEmbedUrlExample.textContent = await embedUrlFromPayload(savedCreds, false);
  }

  let lastDialogTrigger = null;


  async function importSavedJson(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    jsonImportStatus.textContent = t("http.importLoading");
    try {
      const parsed = JSON.parse(await file.text());
      const data = Array.isArray(parsed)
        ? { services: parsed, warnings: [] }
        : (parsed && Array.isArray(parsed.services) ? parsed : null);
      if (!data) throw new Error(t("http.importInvalid"));
      currentDataIsStale = false;
      cachedAt = null;
      lastSuccessfulFetchAt = data?.upstreamFetchedAt ? new Date(data.upstreamFetchedAt) : null;
      lastFetchConfig = null;
      render(data);
      scheduleDayRefresh();
      jsonImportStatus.textContent = t("http.importOk", { count: data.services.length });
      httpDialog.close();
    } catch (error) {
      jsonImportStatus.textContent = error?.message || t("http.importInvalid");
    } finally {
      event.target.value = "";
    }
  }

  function showHttpDialog(event) {
    lastDialogTrigger = event?.currentTarget || document.activeElement;
    buildHttpExamples();
    if (typeof httpDialog.showModal === "function") httpDialog.showModal();
    else httpDialog.setAttribute("open", "");
  }

  async function parseEmbedHash() {
    const embedPath = location.pathname.replace(/\/+$/, "") === appPath("embed");
    if (!embedPath) return null;
    const raw = location.hash.startsWith("#") ? location.hash.slice(1) : location.hash;
    const params = new URLSearchParams(raw);
    const credentials = params.get("credentials") ? await decodeCredentialBlob(params.get("credentials")) : null;
    const view = params.get("view") ? await decodeEmbedViewState(params.get("view")) : null;
    return {
      username: credentials?.username || "",
      password: credentials?.password || "",
      suffixes: credentials?.suffixes || [],
      view,
      theme: normalizeTheme(params.get("theme") || localStorage.getItem("renyyt.theme") || "system"),
      lang: I18N.normalizeLanguage(params.get("lang") || currentLanguage)
    };
  }

  function isStandaloneMode() {
    return window.matchMedia?.("(display-mode: standalone)")?.matches || window.navigator.standalone === true;
  }

  function isIosDevice() {
    const classicIos = /iPad|iPhone|iPod/.test(navigator.userAgent || "") && !window.MSStream;
    const ipadDesktopUa = navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
    return classicIos || ipadDesktopUa;
  }

  function updateInstallUi() {
    const available = !isStandaloneMode() && (!!deferredInstallPrompt || isIosDevice());
    installBtn.classList.toggle("hidden", !available);
  }

  function hasSavedInstallCredentials() {
    const saved = getSavedCredentials();
    if (!saved?.username.trim() || !saved?.password) return false;
    try {
      // Keep this check synchronous: the native prompt needs click activation.
      return localStorage.getItem("renyyt.credentials") === savedCredentialsStorageValue;
    } catch (_) {
      return false;
    }
  }

  async function requestInstall(event) {
    if (!hasSavedInstallCredentials()) {
      setStatusKey("install.needSavedCredentials", "error");
      return;
    }
    lastDialogTrigger = event?.currentTarget || document.activeElement;
    if (deferredInstallPrompt) {
      const promptEvent = deferredInstallPrompt;
      deferredInstallPrompt = null;
      updateInstallUi();
      try {
        await promptEvent.prompt();
      } catch (_) {
        // Browser-native install UI owns its own error/reporting behavior.
      }
      return;
    }
    if (isIosDevice()) {
      if (typeof installDialog.showModal === "function") installDialog.showModal();
      else installDialog.setAttribute("open", "");
    }
  }

  class RenyytRequestError extends Error {
    constructor(message, code = "REQUEST_FAILED", statusCode = 0) {
      super(message);
      this.name = "RenyytRequestError";
      this.code = code;
      this.statusCode = statusCode;
    }
  }

  async function fetchRenyy(payload) {
    let response;
    try {
      response = await fetch(appPath("api/v1/renyyt"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    } catch (_) {
      throw new RenyytRequestError(t("error.LOCAL_CONNECTION_ERROR"), "LOCAL_CONNECTION_ERROR");
    }

    const raw = await response.text();
    let data = {};
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch (_) {
        throw new RenyytRequestError(`${t("error.LOCAL_INVALID_RESPONSE")} (HTTP ${response.status})`, "LOCAL_INVALID_RESPONSE", response.status);
      }
    }
    if (!response.ok) {
      const code = data.code || "REQUEST_FAILED";
      const localized = t(`error.${code}`);
      throw new RenyytRequestError(localized !== `error.${code}` ? localized : (data.error || `HTTP ${response.status}`), code, response.status);
    }
    return data;
  }

  function enterEmbedMode(theme = "system", lang = currentLanguage) {
    document.body.classList.add("embed-mode");
    applyEmbedTheme(theme);
    applyLanguage(lang, false);
    resultsPanel.classList.remove("hidden");
  }

  function exitEmbedMode() {
    document.body.classList.remove("embed-mode");
    const normalTheme = localStorage.getItem("renyyt.theme") || "system";
    themeSelect.value = normalizeTheme(normalTheme);
    applyTheme(themeSelect.value);
    applyLanguage(localStorage.getItem("renyyt.language") || "fi", false);
    if (!currentData) resultsPanel.classList.add("hidden");
  }

  async function openEmbedView() {
    const savedCreds = getSavedCredentials();
    if (!savedCreds) return;
    const target = await embedUrlFromPayload(savedCreds, false);
    location.assign(target);
  }

  async function loadEmbedCredentials(config) {
    enterEmbedMode(config.theme || "system", config.lang || currentLanguage);
    lastFetchConfig = { username: config.username, password: config.password, suffixes: config.suffixes || [], theme: config.theme || "system", lang: config.lang || currentLanguage };
    resultsPanel.classList.add("embed-loading");
    renderStateMessage("", t("status.loading"));
    nextSummary.textContent = "";
    resultMeta.textContent = "";
    try {
      if (!config.username || !config.password || config.username.startsWith("<") || config.password.startsWith("<")) {
        throw new Error(t("embed.badUrl"));
      }
      const data = await fetchRenyy(config);
      lastSuccessfulFetchAt = data?.upstreamFetchedAt ? new Date(data.upstreamFetchedAt) : new Date();
      currentDataIsStale = false;
      saveDataCache(data, lastFetchConfig.username);
      resultsPanel.classList.remove("embed-loading");
      render(data);
      scheduleDayRefresh();
      scheduleAutoReload(data);
      void syncReminderSnapshotIfSubscribed(data);
    } catch (e) {
      resultsPanel.classList.remove("embed-loading");
      if (renderCachedFallback(config.username, e)) return;
      nextSummary.textContent = "";
      resultMeta.textContent = "";
      renderStateMessage(t("embed.failed"), e.message || String(e), "error", "alert");
    }
  }

  async function refreshFromLastConfig(isAutomatic = false) {
    if (!lastFetchConfig) return;
    if (isAutomatic && !document.body.classList.contains("embed-mode")) setStatusKey("status.updating", "progress");
    try {
      const data = await fetchRenyy({
        username: lastFetchConfig.username,
        password: lastFetchConfig.password,
        suffixes: lastFetchConfig.suffixes || []
      });
      lastSuccessfulFetchAt = data?.upstreamFetchedAt ? new Date(data.upstreamFetchedAt) : new Date();
      lastAutoRefreshError = "";
      currentDataIsStale = false;
      saveDataCache(data, lastFetchConfig.username);
      render(data);
      scheduleDayRefresh();
      scheduleAutoReload(data);
      void syncReminderSnapshotIfSubscribed(data);
      if (isAutomatic && !document.body.classList.contains("embed-mode")) setStatusKey("status.ready", "progress");
    } catch (e) {
      if (isAutomatic) {
        lastAutoRefreshError = e.message || String(e);
        if (!document.body.classList.contains("embed-mode")) {
          const inner = e?.code && t(`error.${e.code}`) !== `error.${e.code}` ? t(`error.${e.code}`) : (e.message || String(e));
          setStatus(t("auto.failed", { error: inner }), "error", { type: "autoError", code: e?.code || "", fallback: e.message || String(e), kind: "error" });
        }
        autoReloadDueAt = new Date(Date.now() + 30 * 60 * 1000);
        updateResultMeta();
        autoReloadTimer = setTimeout(() => refreshFromLastConfig(true), 30 * 60 * 1000);
      }
    }
  }

  function renderServiceError(service, error, index) {
    const el = document.createElement("article");
    el.className = "card service-error";
    el.setAttribute("role", "listitem");
    const fallbackName = service?.ASTNimi || service?.tariff?.name || `${t("waste.default")} ${index + 1}`;
    el.innerHTML = `
      <div class="card-top"><div><div class="type">${escapeHtml(fallbackName)}</div><div class="meta"><span class="pill">${escapeHtml(t("render.errorTitle"))}</span></div></div></div>
      <div class="state-message error" role="alert"><strong>${escapeHtml(t("render.errorTitle"))}</strong><div>${escapeHtml(t("render.error", { number: index + 1 }))}</div><details><summary>${escapeHtml(t("render.raw"))}</summary><pre>${escapeHtml(error?.message || String(error))}</pre></details></div>`;
    return el;
  }


  function localizedInterval(service) {
    const info = formatIntervalInfo(service);
    if (!info.currentValue) return { current: t("interval.unknown"), detail: null };
    const current = `${info.currentValue} ${t("interval.weeks")}`;
    if (!info.periods || info.periods.length < 2) return { current, detail: null };
    const parts = info.periods.map(period => {
      const season = period.season ? `${t(`interval.${period.season}`)}: ` : "";
      const range = Number.isFinite(period.start) && Number.isFinite(period.end) ? ` (${t("interval.week")} ${period.start}–${period.end})` : "";
      return `${season}${period.value} ${t("interval.weeks")}${range}`;
    });
    return { current, detail: parts.join(" · ") };
  }

  function orderedServices(services) {
    if (effectiveOrderMode() === "manual") return applyManualOrder(services, effectiveManualOrder());
    return sortByCollectionDate(services, new Date());
  }

  function formatMoney(value) {
    const n = Number(value);
    return Number.isFinite(n) ? new Intl.NumberFormat(localeForLanguage(), { style: "currency", currency: "EUR" }).format(n) : String(value ?? "");
  }

  function essentialDetails(service, interval, shared) {
    const rows = [];
    const add = (label, value) => { if (value !== null && value !== undefined && String(value).trim() !== "") rows.push(`<div><dt>${escapeHtml(label)}</dt><dd><bdi>${escapeHtml(String(value))}</bdi></dd></div>`); };
    add(t("details.size"), service?.tariff?.size || service?.tariff?.name);
    add(t("details.quantity"), service?.ASTMaara);
    add(t("details.interval"), interval.current);
    if (service?.ASTHinta !== null && service?.ASTHinta !== undefined) add(t("details.price"), formatMoney(service.ASTHinta));
    add(t("details.startDate"), service?.ASTAlkPvm ? localizedDate(service.ASTAlkPvm) : "");
    add(t("details.comment"), service?.ASTKomm);
    if (shared) add(t("details.shared"), [shared.name, shared.share != null ? formatShare(shared.share) : ""].filter(Boolean).join(" · "));
    return rows.length ? `<details class="essential-details"><summary>${escapeHtml(t("details.essential"))}</summary><dl class="essential-grid">${rows.join("")}</dl></details>` : "";
  }

  function moveManualService(key, delta) {
    const shown = orderedServices((currentData?.services || []).filter(s => s && typeof s === "object" && s.ASTNextDate && serviceVisible(s, "normal")));
    const keys = shown.map(serviceKey);
    const index = keys.indexOf(key);
    const target = index + delta;
    if (index < 0 || target < 0 || target >= keys.length) return;
    [keys[index], keys[target]] = [keys[target], keys[index]];
    manualOrder = keys;
    localStorage.setItem("renyyt.manualOrder", JSON.stringify(manualOrder));
    render(currentData);
  }

  function icsEscape(value) { return String(value || "").replace(/\\/g, "\\\\").replace(/\n/g, "\\n").replace(/,/g, "\\,").replace(/;/g, "\\;"); }
  function exportIcs() {
    if (!currentData) return;
    const services = orderedServices((currentData.services || []).filter(s => s?.ASTNextDate && serviceVisible(s, "normal")));
    const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Renyy//Collections//FI", "CALSCALE:GREGORIAN"];
    services.forEach(s => {
      const date = String(s.ASTNextDate).replace(/-/g, "");
      const pg = s?.tariff?.productgroup || "";
      const title = productTitle(pg) || s.ASTNimi || pg || t("waste.default");
      lines.push("BEGIN:VEVENT", `UID:${icsEscape(serviceKey(s))}-${date}@renyyt`, `DTSTART;VALUE=DATE:${date}`, `SUMMARY:${icsEscape(t("calendar.event", { name: title }))}`, "END:VEVENT");
    });
    lines.push("END:VCALENDAR");
    const blob = new Blob([lines.join("\r\n") + "\r\n"], {type:"text/calendar;charset=utf-8"});
    const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = "renyyt-tyhjennykset.ics"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function render(data) {
    currentData = data;
    renderedDayKey = localDayKey();
    const allServices = Array.isArray(data?.services) ? data.services : [];
    const visibilityScope = currentVisibilityScope();
    const services = orderedServices(allServices.filter(s => s && typeof s === "object" && s.ASTNextDate && serviceVisible(s, visibilityScope)));
    updateViewControls();
    resultsToolbar.classList.toggle("hidden", document.body.classList.contains("embed-mode"));
    serviceFilterBtn.classList.toggle("hidden", !allServices.length);
    cards.innerHTML = "";
    resultsPanel.classList.remove("hidden");
    lastRenderedServiceCount = services.length;
    lastRenderErrorCount = 0;
    lastApiWarningCount = Array.isArray(data?.warnings) ? data.warnings.length : 0;
    updateResultMeta();

    if (!services.length) {
      nextSummary.textContent = t("results.noDates");
      renderStateMessage(t("results.noneTitle"), t("results.noDateHelp"));
      return;
    }

    const soonest = sortByCollectionDate(
      allServices.filter(s => s && typeof s === "object" && s.ASTNextDate && serviceVisible(s, visibilityScope)),
      new Date()
    )[0];
    const n = daysUntil(soonest.ASTNextDate);
    nextSummary.textContent = n === 0 ? t("results.nextToday") : n === 1 ? t("results.nextTomorrow") : t("results.nextDays", { count: n });

    services.forEach((s, serviceIndex) => {
      try {
      const pg = s?.tariff?.productgroup || "";
      const title = productTitle(pg) || s.ASTNimi || pg || t("waste.default");
      const interval = localizedInterval(s);
      const d = daysUntil(s.ASTNextDate);
      const dueThisWeek = d > 1 && isSameIsoWeek(s.ASTNextDate);
      const when = d === 0 ? t("time.today") : d === 1 ? t("time.tomorrow") : d > 1 ? t("time.inDays", { count: d }) : t("time.daysAgo", { count: Math.abs(d) });
      const rawText = JSON.stringify(s, null, 2);
      const raw = syntaxHighlightJson(s);
      const shared = kimppaInfo(s);
      const el = document.createElement("article");
      el.className = `card${d === 0 ? " due-today" : d === 1 ? " due-tomorrow" : ""}`;
      const key = serviceKey(s);
      el.dataset.serviceKey = key;
      const allowReorder = orderMode === "manual" && !effectiveCompactView() && !document.body.classList.contains("embed-mode");
      el.draggable = allowReorder;
      el.setAttribute("role", "listitem");
      el.innerHTML = `
        <div class="card-top">
          <div class="card-main">
            <div class="type"><bdi>${escapeHtml(title)}</bdi></div>
            <div class="meta">
              ${interval.detail ? `<details class="interval-details"><summary class="pill">${escapeHtml(t("interval.label", { value: interval.current }))}</summary><div class="interval-popover"><strong>${escapeHtml(t("interval.variable"))}</strong><div>${escapeHtml(interval.detail)}</div><div>${escapeHtml(t("interval.currentWeek", { week: isoWeek() }))}</div><div>${escapeHtml(t("interval.tapClose"))}</div></div></details>` : `<span class="pill">${escapeHtml(t("interval.label", { value: interval.current }))}</span>`}
              ${pg ? `<span class="pill"><bdi>${escapeHtml(pg)}</bdi></span>` : ""}
              ${s.ASTNimi && s.ASTNimi !== title ? `<span><bdi>${escapeHtml(s.ASTNimi)}</bdi></span>` : ""}
              ${shared ? `<details class="shared-details"><summary class="pill shared">${escapeHtml(shared.share != null ? t("shared.share", { share: formatShare(shared.share) }) : t("shared.label"))}</summary><div class="shared-popover"><strong><bdi>${escapeHtml(shared.name)}</bdi></strong>${shared.address ? `<div><bdi>${escapeHtml(shared.address)}</bdi></div>` : ""}${shared.memberCount != null ? `<div>${escapeHtml(t("shared.members", { count: shared.memberCount }))}</div>` : ""}<div>${escapeHtml(t("interval.tapClose"))}</div></div></details>` : ""}
            </div>
          </div>
          <div class="card-date-block">
            <div class="date">${escapeHtml(localizedDate(s.ASTNextDate))}</div>
            ${d === 0 ? `<div class="due-label">${escapeHtml(t("due.today"))}</div>` : d === 1 ? `<div class="due-label">${escapeHtml(t("due.tomorrow"))}</div>` : dueThisWeek ? `<div class="due-label due-week">${escapeHtml(t("due.thisWeek"))}</div>` : `<div class="help">${escapeHtml(when)}</div>`}
          </div>
        </div>
        ${allowReorder ? `<div class="reorder-controls"><span class="drag-handle" title="${escapeHtml(t("order.drag"))}" aria-hidden="true">↕</span><button type="button" class="secondary move-up" aria-label="${escapeHtml(t("order.up"))}">↑</button><button type="button" class="secondary move-down" aria-label="${escapeHtml(t("order.down"))}">↓</button></div>` : ""}
        ${essentialDetails(s, interval, shared)}
        <details class="raw-details">
          <summary>${escapeHtml(t("details.raw"))}</summary>
          <div class="json-wrap"><button type="button" class="secondary copy-json">${escapeHtml(t("details.copyJson"))}</button><pre>${raw}</pre></div>
        </details>`;
      const copyBtn = el.querySelector(".copy-json");
      copyBtn.addEventListener("click", async () => {
        const original = copyBtn.textContent;
        try {
          await copyText(rawText);
          copyBtn.textContent = t("status.copyOk");
        } catch (e) {
          copyBtn.textContent = t("status.copyFail");
        }
        setTimeout(() => { copyBtn.textContent = original; }, 1600);
      });
      if (allowReorder) {
        el.addEventListener("dragstart", () => { draggedServiceKey = key; el.classList.add("dragging"); });
        el.addEventListener("dragend", () => { draggedServiceKey = null; el.classList.remove("dragging"); });
        el.addEventListener("dragover", e => { e.preventDefault(); });
        el.addEventListener("drop", e => {
          e.preventDefault();
          if (!draggedServiceKey || draggedServiceKey === key) return;
          const keys = orderedServices(services).map(serviceKey);
          const from = keys.indexOf(draggedServiceKey), to = keys.indexOf(key);
          if (from < 0 || to < 0) return;
          const [moved] = keys.splice(from, 1); keys.splice(to, 0, moved);
          manualOrder = keys; localStorage.setItem("renyyt.manualOrder", JSON.stringify(manualOrder)); render(currentData);
        });
        el.querySelector(".move-up")?.addEventListener("click", () => moveManualService(key, -1));
        el.querySelector(".move-down")?.addEventListener("click", () => moveManualService(key, 1));
      }
      cards.appendChild(el);
      } catch (error) {
        lastRenderErrorCount += 1;
        console.error("Renyy service render error", { serviceIndex, error });
        cards.appendChild(renderServiceError(s, error, serviceIndex));
      }
    });
    updateResultMeta();
  }

  async function load() {
    setStatusKey("status.loading", "progress");
    resultsPanel.setAttribute("aria-busy", "true");
    loadBtn.disabled = true;
    compactLoadBtn.disabled = true;
    loadBtn.setAttribute("aria-busy", "true");
    compactLoadBtn.setAttribute("aria-busy", "true");
    resultsPanel.classList.add("hidden");
    try {
      if (!username.value.trim() || !password.value) throw new RenyytRequestError(t("error.MISSING_CREDENTIALS"), "MISSING_CREDENTIALS");

      if (remember.checked) {
        await saveCredentials({
          username: username.value.trim(),
          password: password.value,
          suffixes: suffixes.value.split(",").map(x => x.trim()).filter(Boolean)
        });
      } else {
        savedCredentialsCache = null;
        localStorage.removeItem("renyyt.credentials");
      }
      updateSavedCredentialUi();

      lastFetchConfig = {
        username: username.value.trim(),
        password: password.value,
        suffixes: suffixes.value.split(",").map(x => x.trim()).filter(Boolean),
        theme: themeSelect.value
      };

      const data = await fetchRenyy({
        username: lastFetchConfig.username,
        password: lastFetchConfig.password,
        suffixes: lastFetchConfig.suffixes
      });
      lastSuccessfulFetchAt = data?.upstreamFetchedAt ? new Date(data.upstreamFetchedAt) : new Date();
      lastAutoRefreshError = "";
      currentDataIsStale = false;
      saveDataCache(data, lastFetchConfig.username);
      render(data);
      scheduleDayRefresh();
      scheduleAutoReload(data);
      void syncReminderSnapshotIfSubscribed(data);
      setStatusKey("status.ready", "progress");
      setLoginCompact(true);
    } catch (e) {
      if (!["AUTH_FAILED", "MISSING_CREDENTIALS", "RATE_LIMITED"].includes(e?.code) && renderCachedFallback(username.value.trim(), e)) {
        setLoginCompact(true);
        return;
      }
      setStatusError(e, "error");
      if (e?.code === "AUTH_FAILED" || e?.code === "MISSING_CREDENTIALS") {
        setLoginCompact(false);
        (username.value.trim() ? password : username).focus();
      }
    } finally {
      resultsPanel.setAttribute("aria-busy", "false");
      loadBtn.disabled = false;
      compactLoadBtn.disabled = false;
      loadBtn.removeAttribute("aria-busy");
      compactLoadBtn.removeAttribute("aria-busy");
    }
  }

  function remindersSupported() {
    return !!(reminderFeature?.enabled && reminderFeature?.vapidPublicKey && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window);
  }

  function reminderSettings() {
    return {
      daysBefore: Math.max(0, Math.min(2, Number(reminderDays.value || 1))),
      time: /^\d{2}:\d{2}$/.test(reminderTime.value || "") ? reminderTime.value : "18:00"
    };
  }

  function saveReminderSettings() {
    localStorage.setItem("renyyt.reminderSettings", JSON.stringify(reminderSettings()));
  }

  function loadReminderSettings() {
    try {
      const value = JSON.parse(localStorage.getItem("renyyt.reminderSettings") || "null");
      if (value) {
        reminderDays.value = String([0,1,2].includes(Number(value.daysBefore)) ? Number(value.daysBefore) : 1);
        if (/^\d{2}:\d{2}$/.test(value.time || "")) reminderTime.value = value.time;
      }
    } catch (_) {}
  }

  function buildReminderItems(data) {
    const settings = reminderSettings();
    const seen = new Set();
    const out = [];
    for (const service of (data?.services || [])) {
      if (!service?.ASTNextDate || !serviceVisible(service, "reminders")) continue;
      const pg = service?.tariff?.productgroup || "";
      const label = productTitle(pg) || service.ASTNimi || pg || t("waste.default");
      const local = new Date(`${service.ASTNextDate}T${settings.time}:00`);
      if (Number.isNaN(local.getTime())) continue;
      local.setDate(local.getDate() - settings.daysBefore);
      const key = `${service.ASTNextDate}|${label}|${local.toISOString()}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ collectionDate: service.ASTNextDate, label, triggerAt: local.toISOString() });
    }
    return out;
  }

  async function currentPushSubscription() {
    if (!remindersSupported()) return null;
    try {
      const registration = await navigator.serviceWorker.ready;
      return await registration.pushManager.getSubscription();
    } catch (_) { return null; }
  }

  async function postReminderState(path, subscription, reminders = []) {
    const response = await fetch(appPath(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ subscription: subscription.toJSON(), reminders, locale: currentLanguage })
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async function syncReminderSnapshotIfSubscribed(data = currentData, showStatus = false) {
    if (!data || !remindersSupported()) return false;
    const subscription = await currentPushSubscription();
    if (!subscription) return false;
    try {
      saveReminderSettings();
      await postReminderState("api/v1/reminders/sync", subscription, buildReminderItems(data));
      if (showStatus) reminderStatus.textContent = t("reminders.saved");
      return true;
    } catch (_) {
      if (showStatus) reminderStatus.textContent = t("reminders.error");
      return false;
    }
  }

  async function updateReminderDialogState() {
    loadReminderSettings();
    if (!remindersSupported()) {
      reminderSupportHelp.textContent = t("reminders.unsupported");
      enableRemindersBtn.disabled = true;
      disableRemindersBtn.classList.add("hidden");
      return;
    }
    const subscription = await currentPushSubscription();
    reminderSupportHelp.textContent = subscription ? t("reminders.enabled") : t("reminders.disabled");
    enableRemindersBtn.disabled = !currentData;
    disableRemindersBtn.classList.toggle("hidden", !subscription);
  }

  async function openReminderDialog(event) {
    lastDialogTrigger = event?.currentTarget || reminderBtn;
    reminderStatus.textContent = "";
    await updateReminderDialogState();
    reminderDialog.showModal();
  }

  async function enableReminders() {
    reminderStatus.textContent = "";
    if (!currentData) { reminderStatus.textContent = t("reminders.needData"); return; }
    if (!remindersSupported()) { reminderStatus.textContent = t("reminders.unsupported"); return; }
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") { reminderStatus.textContent = t("reminders.permissionDenied"); return; }
      const registration = await navigator.serviceWorker.ready;
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: base64UrlDecode(reminderFeature.vapidPublicKey)
        });
      }
      saveReminderSettings();
      await postReminderState("api/v1/reminders/sync", subscription, buildReminderItems(currentData));
      reminderStatus.textContent = t("reminders.saved");
      await updateReminderDialogState();
    } catch (_) {
      reminderStatus.textContent = t("reminders.error");
    }
  }

  async function disableReminders() {
    const subscription = await currentPushSubscription();
    if (!subscription) { await updateReminderDialogState(); return; }
    try { await postReminderState("api/v1/reminders/unsubscribe", subscription, []); } catch (_) {}
    try { await subscription.unsubscribe(); } catch (_) {}
    reminderStatus.textContent = t("reminders.disabled");
    await updateReminderDialogState();
  }

  async function loadFeatures() {
    try {
      const response = await fetch(appPath("api/v1/features"), { cache: "no-store", credentials: "same-origin" });
      if (!response.ok) throw new Error("features unavailable");
      const data = await response.json();
      feedbackBtn.classList.toggle("hidden", !data?.feedback);
      reminderFeature = data?.reminders || null;
      reminderBtn.classList.toggle("hidden", !reminderFeature?.enabled);
      if (currentData) void syncReminderSnapshotIfSubscribed(currentData);
      if (data?.pwa) enablePwaFeatures();
      else disablePwaFeatures();
    } catch (_) {
      feedbackBtn.classList.add("hidden");
      reminderBtn.classList.add("hidden");
      installBtn.classList.add("hidden");
    }
  }

  async function disablePwaFeatures() {
    deferredInstallPrompt = null;
    installBtn.classList.add("hidden");
    if ("serviceWorker" in navigator) {
      try {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.filter(reg => reg.scope.startsWith(`${location.origin}${APP_BASE_PATH || ""}/`)).map(reg => reg.unregister()));
      } catch (_) {}
    }
    if ("caches" in window) {
      try {
        const keys = await caches.keys();
        await Promise.all(keys.filter(key => key.startsWith("renyyt-shell-")).map(key => caches.delete(key)));
      } catch (_) {}
    }
  }

  function enablePwaFeatures() {
    window.addEventListener("beforeinstallprompt", (event) => {
      event.preventDefault();
      deferredInstallPrompt = event;
      updateInstallUi();
    });
    window.addEventListener("appinstalled", () => {
      deferredInstallPrompt = null;
      updateInstallUi();
    });
    updateInstallUi();
    if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
      const registerWorker = () => navigator.serviceWorker.register(`${appPath("service-worker.js")}?v=0.8.0`, { scope: `${APP_BASE_PATH || ""}/`, updateViaCache: "none" }).catch(() => {});
      if (document.readyState === "complete") registerWorker();
      else window.addEventListener("load", registerWorker, { once: true });
    }
  }

  function resetFeedbackSubmitButton() {
    sendFeedbackBtn.dataset.state = "send";
    sendFeedbackBtn.setAttribute("data-i18n", "feedback.send");
    sendFeedbackBtn.textContent = t("feedback.send");
    sendFeedbackBtn.disabled = false;
  }

  function openFeedbackDialog(event) {
    lastDialogTrigger = event?.currentTarget || feedbackBtn;
    feedbackStatus.textContent = "";
    resetFeedbackSubmitButton();
    feedbackAttachData.checked = false;
    feedbackAttachData.disabled = !currentData;
    feedbackAttachRow.classList.toggle("disabled", !currentData);
    feedbackDialog.showModal();
    feedbackMessage.focus();
  }

  async function submitFeedback() {
    if (sendFeedbackBtn.dataset.state === "close") {
      feedbackDialog.close();
      return;
    }
    const message = feedbackMessage.value.trim();
    if (!message) {
      feedbackMessage.focus();
      return;
    }
    sendFeedbackBtn.disabled = true;
    feedbackStatus.textContent = t("feedback.sending");
    try {
      const response = await fetch(appPath("api/v1/feedback"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ message, email: feedbackEmail.value.trim(), ...(feedbackAttachData.checked && currentData ? { collectionData: currentData } : {}) })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      feedbackMessage.value = "";
      feedbackEmail.value = "";
      feedbackAttachData.checked = false;
      feedbackStatus.textContent = t("feedback.sent");
      sendFeedbackBtn.dataset.state = "close";
      sendFeedbackBtn.setAttribute("data-i18n", "feedback.close");
      sendFeedbackBtn.textContent = t("feedback.close");
    } catch (_) {
      feedbackStatus.textContent = t("feedback.error");
    } finally {
      sendFeedbackBtn.disabled = false;
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;
    if (currentData && renderedDayKey !== localDayKey()) {
      render(currentData);
      scheduleDayRefresh();
    }
    if (lastFetchConfig && autoReloadDueAt && Date.now() >= autoReloadDueAt.getTime()) {
      refreshFromLastConfig(true);
    }
  });

  httpHelpBtn.addEventListener("click", showHttpDialog);
  compactHttpHelpBtn.addEventListener("click", showHttpDialog);
  if (jsonImportFile) jsonImportFile.addEventListener("change", importSavedJson);
  readmeBtn.addEventListener("click", showReadmeDialog);

  readmeContent.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-doc-path]");
    if (!link || !readmeContent.contains(link)) return;
    event.preventDefault();
    showMarkdownDocument(link.dataset.docPath, event, false);
  });
  aboutBtn.addEventListener("click", showAboutDialog);
  feedbackBtn.addEventListener("click", openFeedbackDialog);
  sendFeedbackBtn.addEventListener("click", submitFeedback);
  closeFeedbackDialog.addEventListener("click", () => feedbackDialog.close());
  feedbackDialog.addEventListener("click", (e) => { if (e.target === feedbackDialog) feedbackDialog.close(); });
  feedbackDialog.addEventListener("close", () => { if (lastDialogTrigger?.isConnected) lastDialogTrigger.focus(); });
  serviceFilterBtn.addEventListener("click", openServiceFilterDialog);
  closeServiceFilterDialog.addEventListener("click", () => serviceFilterDialog.close());
  serviceFilterDialog.addEventListener("click", (e) => { if (e.target === serviceFilterDialog) serviceFilterDialog.close(); });
  serviceFilterDialog.addEventListener("close", () => { if (lastDialogTrigger?.isConnected) lastDialogTrigger.focus(); });
  resetServiceFiltersBtn.addEventListener("click", () => { serviceVisibility = { version: 1, normal: {}, embed: {}, reminders: {} }; saveServiceVisibility(); renderServiceFilterDialog(); if (currentData) render(currentData); void syncReminderSnapshotIfSubscribed(currentData, false); });
  reminderBtn.addEventListener("click", openReminderDialog);
  enableRemindersBtn.addEventListener("click", enableReminders);
  disableRemindersBtn.addEventListener("click", disableReminders);
  reminderDays.addEventListener("change", () => { saveReminderSettings(); void syncReminderSnapshotIfSubscribed(currentData, true); });
  reminderTime.addEventListener("change", () => { saveReminderSettings(); void syncReminderSnapshotIfSubscribed(currentData, true); });
  closeReminderDialog.addEventListener("click", () => reminderDialog.close());
  reminderDialog.addEventListener("click", (e) => { if (e.target === reminderDialog) reminderDialog.close(); });
  reminderDialog.addEventListener("close", () => { if (lastDialogTrigger?.isConnected) lastDialogTrigger.focus(); });
  installBtn.addEventListener("click", requestInstall);
  closeInstallDialog.addEventListener("click", () => installDialog.close());
  installDialog.addEventListener("click", (e) => { if (e.target === installDialog) installDialog.close(); });
  installDialog.addEventListener("close", () => { if (lastDialogTrigger?.isConnected) lastDialogTrigger.focus(); });
  closeAboutDialog.addEventListener("click", () => aboutDialog.close());
  aboutDialog.addEventListener("click", (e) => { if (e.target === aboutDialog) aboutDialog.close(); });
  aboutDialog.addEventListener("close", () => { if (lastDialogTrigger?.isConnected) lastDialogTrigger.focus(); });
  closeReadmeDialog.addEventListener("click", () => readmeDialog.close());
  readmeDialog.addEventListener("click", (e) => { if (e.target === readmeDialog) readmeDialog.close(); });
  readmeDialog.addEventListener("close", () => { if (lastDialogTrigger?.isConnected) lastDialogTrigger.focus(); });
  embedBtn.addEventListener("click", openEmbedView);
  compactEmbedBtn.addEventListener("click", openEmbedView);
  closeHttpDialog.addEventListener("click", () => httpDialog.close());
  httpDialog.addEventListener("click", (e) => {
    if (e.target === httpDialog) httpDialog.close();
  });
  httpDialog.addEventListener("close", () => { if (lastDialogTrigger?.isConnected) lastDialogTrigger.focus(); });
  httpDialog.querySelectorAll("[data-copy-target]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const original = btn.textContent;
      try {
        await copyText($(btn.dataset.copyTarget).textContent);
        btn.textContent = t("status.copyOk");
      } catch (_) {
        btn.textContent = t("status.copyFail");
      }
      setTimeout(() => { btn.textContent = original; }, 1600);
    });
  });

  orderModeSelect.addEventListener("change", () => { orderMode = orderModeSelect.value === "manual" ? "manual" : "date"; localStorage.setItem("renyyt.orderMode", orderMode); if (currentData) render(currentData); });
  compactViewBtn.addEventListener("click", () => { compactView = !compactView; localStorage.setItem("renyyt.compactView", compactView ? "1" : "0"); if (currentData) render(currentData); else updateViewControls(); });
  icsBtn.addEventListener("click", exportIcs);

  loadBtn.addEventListener("click", load);
  compactLoadBtn.addEventListener("click", load);
  expandLoginBtn.addEventListener("click", () => setLoginCompact(false));
  password.addEventListener("keydown", e => {
    // Enter can confirm an IME candidate instead of submitting the credentials.
    if (e.key === "Enter" && !e.isComposing && e.keyCode !== 229) load();
  });
  password.addEventListener("beforeinput", (e) => {
    if (!e.isTrusted) return;
    if (startsFullSecretEntry(password.value, password.selectionStart, password.selectionEnd, e.inputType)) {
      passwordUserEntered = true;
    }
  });
  password.addEventListener("input", () => {
    if (!password.value) passwordUserEntered = false;
    updatePasswordToggleUi();
  });
  togglePasswordBtn.addEventListener("click", () => {
    if (togglePasswordBtn.disabled) return;
    password.type = password.type === "password" ? "text" : "password";
    updatePasswordToggleUi();
    password.focus();
  });
  forgetBtn.addEventListener("click", () => {
    localStorage.removeItem("renyyt.credentials");
    savedCredentialsCache = null;
    username.value = ""; password.value = ""; suffixes.value = ""; remember.checked = false;
    passwordUserEntered = false;
    updateSavedCredentialUi();
    updatePasswordToggleUi();
    setStatusKey("status.deleted");
  });

  async function syncModeFromLocation(forceReload = false) {
    const embedConfig = await parseEmbedHash();
    if (!embedConfig) {
      embeddedVisibilityKeys = null;
      embeddedViewState = null;
      exitEmbedMode();
      updateViewControls();
      return;
    }

    embeddedViewState = embedConfig.view;
    embeddedVisibilityKeys = Array.isArray(embedConfig.view?.embedVisibleKeys) ? embedConfig.view.embedVisibleKeys : null;
    enterEmbedMode(embedConfig.theme, embedConfig.lang);
    updateViewControls();
    const effective = (embedConfig.username && embedConfig.password)
      ? embedConfig
      : getSavedCredentials();

    if (!effective) {
      nextSummary.textContent = "";
      resultMeta.textContent = "";
      renderStateMessage(t("embed.missingTitle"), t("embed.missing"), "error", "alert");
      currentData = null;
      lastFetchConfig = null;
      return;
    }

    effective.theme = embedConfig.theme;
    effective.lang = embedConfig.lang;
    const changed = !lastFetchConfig
      || lastFetchConfig.username !== effective.username
      || lastFetchConfig.password !== effective.password
      || JSON.stringify(lastFetchConfig.suffixes || []) !== JSON.stringify(effective.suffixes || []);
    if (forceReload || changed || !currentData) loadEmbedCredentials(effective);
  }

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || httpDialog.open || readmeDialog.open || aboutDialog.open || feedbackDialog.open || serviceFilterDialog.open || reminderDialog.open || installDialog.open) return;
    document.querySelectorAll(".shared-details[open], .interval-details[open]").forEach(el => { el.open = false; });
  });
  document.addEventListener("click", (e) => {
    document.querySelectorAll(".shared-details[open], .interval-details[open]").forEach(el => {
      if (!el.contains(e.target)) el.open = false;
    });
  });

  loadFeatures();

  window.addEventListener("popstate", () => { void syncModeFromLocation(false); });
  window.addEventListener("hashchange", () => { void syncModeFromLocation(false); });
  window.addEventListener("pageshow", () => { void syncModeFromLocation(false); });

  (async () => {
    const saved = await loadSavedCredentials();
    if (saved) {
      username.value = saved.username;
      password.value = saved.password;
      suffixes.value = saved.suffixes.join(",");
      remember.checked = true;
      passwordUserEntered = false;
    }
    updateSavedCredentialUi();
    updatePasswordToggleUi();
    await buildHttpExamples();
    await syncModeFromLocation(false);
  })();
})();
