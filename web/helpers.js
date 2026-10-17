(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.RenyytHelpers = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function detectAppBasePath(pathname) {
    const path = pathname || "/";
    for (const suffix of ["/embed", "/index.html"]) {
      if (path.endsWith(suffix)) return path.slice(0, -suffix.length);
    }
    if (path === "/") return "";
    if (path.endsWith("/")) return path.slice(0, -1);
    return path;
  }

  function isoWeek(date) {
    const src = date || new Date();
    const d = new Date(Date.UTC(src.getFullYear(), src.getMonth(), src.getDate()));
    const day = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - day);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  }

  function weekInRange(week, start, end) {
    if (!Number.isFinite(start) || !Number.isFinite(end)) return false;
    return start <= end ? week >= start && week <= end : week >= start || week <= end;
  }

  function formatIntervalInfo(service, now) {
    const primary = String(service.ASTVali ?? "").trim();
    const secondary = String(service.ASTVali2 ?? "").trim();
    if (!primary) return { current: "ei tiedossa", detail: null, currentValue: null, periods: [] };
    if (!secondary || secondary === "0") return { current: `${primary} vk`, detail: null, currentValue: primary, periods: [{ value: primary, start: null, end: null, season: null }] };
    const p1Start = Number(service.ASTVoim1), p1End = Number(service.ASTVoim2);
    const p2Start = Number(service.ASTVoim21), p2End = Number(service.ASTVoim22);
    const valid1 = [p1Start, p1End].every(Number.isFinite), valid2 = [p2Start, p2End].every(Number.isFinite);
    if (!valid1 || !valid2) return { current: `${primary} vk`, detail: `${primary} vk · ${secondary} vk`, currentValue: primary, periods: [{ value: primary, start: null, end: null, season: null }, { value: secondary, start: null, end: null, season: null }] };
    const week = isoWeek(now || new Date());
    const current = weekInRange(week, p1Start, p1End) ? primary : weekInRange(week, p2Start, p2End) ? secondary : primary;
    const p1CrossesYear = p1Start > p1End, p2CrossesYear = p2Start > p2End;
    let detail;
    let periods;
    if (!p1CrossesYear && p2CrossesYear) {
      detail = `Kesä: ${primary} vk (vko ${p1Start}–${p1End}) · Talvi: ${secondary} vk (vko ${p2Start}–${p2End})`;
      periods = [{ value: primary, start: p1Start, end: p1End, season: "summer" }, { value: secondary, start: p2Start, end: p2End, season: "winter" }];
    } else if (p1CrossesYear && !p2CrossesYear) {
      detail = `Kesä: ${secondary} vk (vko ${p2Start}–${p2End}) · Talvi: ${primary} vk (vko ${p1Start}–${p1End})`;
      periods = [{ value: secondary, start: p2Start, end: p2End, season: "summer" }, { value: primary, start: p1Start, end: p1End, season: "winter" }];
    } else {
      detail = `${primary} vk (vko ${p1Start}–${p1End}) · ${secondary} vk (vko ${p2Start}–${p2End})`;
      periods = [{ value: primary, start: p1Start, end: p1End, season: null }, { value: secondary, start: p2Start, end: p2End, season: null }];
    }
    return { current: `${current} vk`, detail, currentValue: current, periods };
  }

  function daysUntil(iso, now) {
    const today = new Date(now || new Date()); today.setHours(0,0,0,0);
    const d = new Date(iso + "T00:00:00");
    return Math.round((d - today) / 86400000);
  }

  function isoWeekYear(date) {
    const src = date || new Date();
    const d = new Date(Date.UTC(src.getFullYear(), src.getMonth(), src.getDate()));
    const day = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - day);
    return d.getUTCFullYear();
  }

  function isSameIsoWeek(iso, now) {
    const target = new Date(String(iso) + "T00:00:00");
    if (Number.isNaN(target.getTime())) return false;
    const current = new Date(now || new Date());
    return isoWeek(target) === isoWeek(current) && isoWeekYear(target) === isoWeekYear(current);
  }


  function serviceKey(service) {
    if (!service || typeof service !== "object") return "";
    const id = service.id || {};
    const parts = [service.ASTAsnro ?? id.ASTAsnro, service.ASTTyyppi ?? id.ASTTyyppi, service.ASTPos ?? id.ASTPos];
    if (parts.some(v => v !== null && v !== undefined && String(v) !== "")) return parts.map(v => String(v ?? "")).join("|");
    return [service?.tariff?.productgroup || "", service?.tariff?.name || "", service?.tariff?.size || "", service.ASTNimi || "", service.ASTTyyppi || "", service.ASTPos || ""].join("|");
  }

  function effectiveServiceVisibility(preferences, service, scope) {
    const prefs = preferences && typeof preferences === "object" ? preferences : {};
    const key = serviceKey(service);
    const normal = !(prefs.normal && Object.prototype.hasOwnProperty.call(prefs.normal, key)) || prefs.normal[key] !== false;
    if (scope === "normal") return normal;
    const scoped = prefs[scope];
    if (scoped && Object.prototype.hasOwnProperty.call(scoped, key)) return scoped[key] !== false;
    return normal;
  }

  function applyManualOrder(services, order) {
    const items = Array.isArray(services) ? services.slice() : [];
    const wanted = Array.isArray(order) ? order : [];
    const rank = new Map(wanted.map((key, index) => [String(key), index]));
    return items.map((service, index) => ({service, index, rank: rank.has(serviceKey(service)) ? rank.get(serviceKey(service)) : Number.MAX_SAFE_INTEGER}))
      .sort((a,b) => a.rank - b.rank || a.index - b.index).map(item => item.service);
  }

  function sortByCollectionDate(services, now = new Date()) {
    return (services || []).slice().sort((a, b) => {
      const da = daysUntil(a && a.ASTNextDate, now);
      const db = daysUntil(b && b.ASTNextDate, now);
      const aPast = Number.isFinite(da) && da < 0 ? 1 : 0;
      const bPast = Number.isFinite(db) && db < 0 ? 1 : 0;
      if (aPast !== bPast) return aPast - bPast;
      return String(a && a.ASTNextDate || "").localeCompare(String(b && b.ASTNextDate || ""));
    });
  }

  function nextCollectionRefreshAt(services, now = new Date()) {
    const dates = (services || []).map(s => s && s.ASTNextDate).filter(Boolean).sort();
    if (!dates.length) return null;
    const target = new Date(`${dates[0]}T00:05:00`);
    target.setDate(target.getDate() + 1);
    if (target > now) return target;
    return new Date(now.getTime() + 30 * 60 * 1000);
  }

  function obfuscateSecret(value) {
    const text = String(value ?? "");
    if (typeof TextEncoder !== "undefined" && typeof btoa === "function") {
      const bytes = new TextEncoder().encode(text);
      let binary = "";
      bytes.forEach(b => { binary += String.fromCharCode(b); });
      return "b64:" + btoa(binary);
    }
    if (typeof Buffer !== "undefined") return "b64:" + Buffer.from(text, "utf8").toString("base64");
    throw new Error("Base64-koodaus ei ole käytettävissä.");
  }

  function deobfuscateSecret(value) {
    const raw = String(value ?? "");
    if (!raw.startsWith("b64:")) return raw;
    const encoded = raw.slice(4);
    if (typeof atob === "function" && typeof TextDecoder !== "undefined") {
      const binary = atob(encoded);
      const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
      return new TextDecoder().decode(bytes);
    }
    if (typeof Buffer !== "undefined") return Buffer.from(encoded, "base64").toString("utf8");
    throw new Error("Base64-purku ei ole käytettävissä.");
  }

  function startsFullSecretEntry(value, selectionStart, selectionEnd, inputType) {
    const current = String(value ?? "");
    const type = String(inputType || "");
    if (!type.startsWith("insert")) return false;
    if (current.length === 0) return true;
    const start = Number(selectionStart);
    const end = Number(selectionEnd);
    return Number.isFinite(start) && Number.isFinite(end) && start === 0 && end === current.length;
  }

  function formatShare(value) {
    if (value === null || value === undefined || value === "") return null;
    const n = Number(value);
    return Number.isFinite(n) ? `${Math.round(n)} %` : `${value} %`;
  }

  return { detectAppBasePath, isoWeek, weekInRange, formatIntervalInfo, daysUntil, isSameIsoWeek, formatShare, serviceKey, effectiveServiceVisibility, applyManualOrder, sortByCollectionDate, nextCollectionRefreshAt, obfuscateSecret, deobfuscateSecret, startsFullSecretEntry };
});
