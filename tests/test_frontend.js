"use strict";
const assert = require("assert");
const h = require("../web/helpers.js");

assert.strictEqual(h.detectAppBasePath("/"), "");
assert.strictEqual(h.detectAppBasePath("/renyyt/"), "/renyyt");
assert.strictEqual(h.detectAppBasePath("/renyyt/embed"), "/renyyt");
assert.strictEqual(h.isoWeek(new Date("2026-10-01T12:00:00")), 40);
assert.strictEqual(h.weekInRange(40, 18, 40), true);
assert.strictEqual(h.weekInRange(2, 41, 17), true);
assert.strictEqual(h.weekInRange(30, 41, 17), false);

assert.strictEqual(h.isSameIsoWeek("2026-10-04", new Date("2026-10-02T12:00:00")), true, "Sunday later in the same ISO week should be detected");
assert.strictEqual(h.isSameIsoWeek("2026-10-05", new Date("2026-10-02T12:00:00")), false, "Monday in the next ISO week must not be detected as this week");
assert.strictEqual(h.isSameIsoWeek("2027-01-03", new Date("2026-12-31T12:00:00")), true, "same ISO week across calendar year boundary should be detected");
let info = h.formatIntervalInfo({ASTVali:"2",ASTVali2:"4",ASTVoim1:"18",ASTVoim2:"40",ASTVoim21:"41",ASTVoim22:"17"}, new Date("2026-10-01T12:00:00"));
assert.strictEqual(info.current, "2 vk");
assert.ok(info.detail.includes("Kesä: 2 vk"));
info = h.formatIntervalInfo({ASTVali:"2",ASTVali2:"4",ASTVoim1:"18",ASTVoim2:"40",ASTVoim21:"41",ASTVoim22:"17"}, new Date("2026-12-01T12:00:00"));
assert.strictEqual(info.current, "4 vk");
assert.strictEqual(h.daysUntil("2026-10-02", new Date("2026-10-01T15:00:00")), 1);
assert.strictEqual(h.formatShare(33.3333), "33 %");
assert.strictEqual(h.formatShare(50), "50 %");
assert.strictEqual(h.serviceKey({ASTAsnro:"A",ASTTyyppi:2,ASTPos:1}), "A|2|1");
assert.strictEqual(h.serviceKey({tariff:{productgroup:"Bio",name:"240 l",size:"240"},ASTNimi:"Piha",ASTNextDate:"2026-10-10"}), "Bio|240 l|240|Piha||", "fallback service key must not depend on changing collection date");
const visService = {ASTAsnro:"A",ASTTyyppi:2,ASTPos:1};
assert.strictEqual(h.effectiveServiceVisibility({normal:{},embed:{},reminders:{}}, visService, "normal"), true);
assert.strictEqual(h.effectiveServiceVisibility({normal:{"A|2|1":false},embed:{},reminders:{}}, visService, "embed"), false, "embed must inherit normal visibility by default");
assert.strictEqual(h.effectiveServiceVisibility({normal:{"A|2|1":false},embed:{"A|2|1":true},reminders:{}}, visService, "embed"), true, "embed override must beat inherited normal visibility");
assert.strictEqual(h.effectiveServiceVisibility({normal:{},embed:{},reminders:{"A|2|1":false}}, visService, "reminders"), false);
assert.deepStrictEqual(h.applyManualOrder([{ASTAsnro:"A"},{ASTAsnro:"B"}], ["B||"] ).map(x=>x.ASTAsnro), ["B","A"]);
assert.deepStrictEqual(
  h.sortByCollectionDate(
    [{ASTAsnro:"past",ASTNextDate:"2026-10-01"},{ASTAsnro:"future",ASTNextDate:"2026-10-04"},{ASTAsnro:"today",ASTNextDate:"2026-10-02"}],
    new Date("2026-10-02T12:00:00")
  ).map(x => x.ASTAsnro),
  ["today","future","past"],
  "date ordering must move already-passed collections after current/upcoming ones without an API call"
);
let refreshAt = h.nextCollectionRefreshAt([{ASTNextDate:"2026-10-02"},{ASTNextDate:"2026-10-19"}], new Date("2026-10-02T12:00:00"));
assert.strictEqual(refreshAt.getFullYear(), 2026);
assert.strictEqual(refreshAt.getMonth(), 9);
assert.strictEqual(refreshAt.getDate(), 3);
assert.strictEqual(refreshAt.getHours(), 0);
assert.strictEqual(refreshAt.getMinutes(), 5);
refreshAt = h.nextCollectionRefreshAt([{ASTNextDate:"2026-10-01"},{ASTNextDate:"2026-10-19"}], new Date("2026-10-02T12:00:00"));
assert.strictEqual(Math.round((refreshAt.getTime() - new Date("2026-10-02T12:00:00").getTime()) / 60000), 30, "stale earliest date should trigger a retry soon instead of waiting for a later bin");
const secret = "pässwörd 🔐";
const obscured = h.obfuscateSecret(secret);
assert.ok(obscured.startsWith("b64:"));
assert.notStrictEqual(obscured, secret);
assert.strictEqual(h.deobfuscateSecret(obscured), secret);
assert.strictEqual(h.deobfuscateSecret("legacy-plain"), "legacy-plain");


const i18n = require("../web/i18n.js");
assert.deepStrictEqual(i18n.supported.sort(), ["en", "fi", "sv", "uk"]);
assert.strictEqual(i18n.t("fi", "app.title"), "Renyyt – seuraavat tyhjennykset");
assert.strictEqual(i18n.t("en", "status.ready"), "Ready");
assert.strictEqual(i18n.t("sv", "theme.dark"), "Mörkt");
assert.strictEqual(i18n.t("uk", "status.ready"), "Готово");
assert.strictEqual(i18n.locale("uk"), "uk-UA");
assert.strictEqual(i18n.direction("uk"), "ltr");
for (const lang of i18n.supported) {
  for (const key of Object.keys(i18n.translations.fi)) {
    assert.ok(i18n.translations[lang][key], `${lang} must translate ${key}`);
  }
}
assert.strictEqual(i18n.normalizeLanguage("de"), "fi");


console.log("frontend helper tests: OK");

// Regression: app.js must explicitly import isoWeek from RenyytHelpers. A syntax
// check alone does not catch an undefined identifier inside the seasonal card path.
const fs = require("fs");
const path = require("path");
const appSource = fs.readFileSync(path.join(__dirname, "..", "web", "app.js"), "utf8");
assert.ok(appSource.includes('t("due.thisWeek")'), "service cards must render the this-week due state");
for (const lang of ["fi", "en", "sv", "uk"]) {
  assert.ok(i18n.translations[lang]["due.thisWeek"], `due.thisWeek translation missing for ${lang}`);
}
assert.ok(/\{[^}]*\bisoWeek\b[^}]*\}\s*=\s*window\.RenyytHelpers/.test(appSource), "app.js must bind isoWeek from RenyytHelpers");
assert.ok(appSource.includes("renderServiceError"), "service rendering must isolate per-card failures");
assert.ok(appSource.includes("catch (error)"), "service rendering must catch per-card failures");

const cssSource = fs.readFileSync(path.join(__dirname, "..", "web", "styles.css"), "utf8");
const htmlSource = fs.readFileSync(path.join(__dirname, "..", "web", "index.html"), "utf8");
assert.ok(cssSource.includes("@media (forced-colors: active)"), "forced-colors support must remain present");
assert.ok(htmlSource.includes('class="skip-link"'), "keyboard skip link must remain present");
assert.ok(appSource.includes("version: 4"), "credential storage must use the versioned Web Crypto blob format");
assert.ok(appSource.includes("AES-GCM"), "credential storage must use AES-GCM obfuscation");
assert.ok(appSource.includes("credentials: blob"), "saved credentials must be stored as one opaque blob");
assert.ok(appSource.includes('params.set("credentials"'), "embedded-view URL must use a single credentials blob");
assert.ok(!appSource.includes('params.set("embed", "1")'), "embedded-view URL must not carry redundant embed=1");
assert.ok(!appSource.includes('params.set("username"'), "embedded-view URL must not expose username as a separate parameter");
assert.ok(!appSource.includes('params.set("password"'), "embedded-view URL must not expose password as a separate parameter");
assert.strictEqual(i18n.translations.fi["view.compact"], "Tiivis näkymä", "Finnish compact-view label must use Tiivis näkymä");
assert.strictEqual(i18n.translations.fi["login.rememberHelp"], "Kirjautumistiedot säilytetään selaimen paikallisessa muistissa. Älä tallenna tietoja, jos käytät jaettua tai muuten epäluotettavaa laitetta.", "Finnish save-help copy must match the approved wording");
assert.ok(!i18n.translations.fi["login.rememberHelp"].includes("localStorage"), "main save-help copy must not expose localStorage implementation details");

// Localized embedded-view terminology and security copy must not regress.
assert.strictEqual(i18n.translations.fi["embed.button"], "Upotusnäkymä");
assert.strictEqual(i18n.translations.en["embed.button"], "Embedded view");
assert.strictEqual(i18n.translations.sv["embed.button"], "Inbäddad vy");
assert.strictEqual(i18n.translations.uk["embed.button"], "Вбудований вигляд");
assert.ok(i18n.translations.fi["security.text"].includes("AES-GCM"), "Finnish security text must describe the current credential blob");
assert.ok(i18n.translations.fi["security.text"].includes("ei tarkoita turvallista salausta"), "Finnish security text must explain the obfuscation limitation");
assert.strictEqual(i18n.translations.fi["footnote"], "Huom! Kyseessä on epävirallinen asiakasrajapinnan käyttö. Renyy voi muuttaa palvelunsa sisältöä tai toimintaa ilman ennakkovaroitusta.");
for (const lang of i18n.supported) {
  assert.ok(i18n.translations[lang]["security.text"].includes("AES-GCM"), `security text must explain AES-GCM-based obfuscation for ${lang}`);
  assert.ok(i18n.translations[lang]["feedback.button"], `feedback.button translation missing for ${lang}`);
}
assert.ok(htmlSource.includes('id="embedBtn" class="secondary hidden" type="button" data-i18n="embed.button"'), "desktop embed button must be wired to i18n");
assert.ok(htmlSource.includes('id="compactEmbedBtn" class="secondary hidden" type="button" data-i18n="embed.button"'), "compact embed button must be wired to i18n");

assert.ok(appSource.includes('appPath("api/v1/renyyt")'), "frontend must use versioned v1 API route");
assert.ok(appSource.includes('appPath("api/v1/features")'), "frontend must discover optional server features");
assert.ok(appSource.includes('appPath("api/v1/feedback")'), "frontend feedback must use the local versioned endpoint");
assert.ok(appSource.includes('sendFeedbackBtn.dataset.state = "close"'), "successful feedback must turn the send button into a close button");
assert.ok(appSource.includes('sendFeedbackBtn.setAttribute("data-i18n", "feedback.close")'), "feedback close button must remain localized");
assert.ok(htmlSource.includes('data-i18n="app.provider"'), "page must visibly identify Pirkanmaan Jätehuolto context");
assert.ok(htmlSource.includes('name="description"'), "page must include an SEO description");
assert.ok(htmlSource.includes('id="feedbackBtn" class="secondary hidden"'), "feedback button must be hidden until server capability discovery enables it");
assert.ok(appSource.includes("formatPastStatusTime(lastSuccessfulFetchAt)"), "last successful fetch must include a date only when it is not today");
assert.ok(appSource.includes("formatPastStatusTime(cachedAt)"), "cached data timestamp must use the same relative-date rule");
assert.ok(htmlSource.includes('id="aboutBtn"'), "version/about UI button must exist");
assert.ok(appSource.includes("showAboutDialog"), "version/about dialog logic must exist");
assert.ok(cssSource.includes(".status.progress"), "only progress statuses should opt into right alignment");
assert.ok(cssSource.includes("text-align:left"), "ordinary status and notice messages must remain left-aligned");

assert.ok(htmlSource.includes('id="languageSelect"'), "language selector must exist");
assert.ok(htmlSource.includes('src="i18n.js"'), "i18n module must load before app.js");
assert.ok(appSource.includes('params.set("lang", currentLanguage)'), "embed URL must preserve UI language");

assert.ok(appSource.includes("rerenderStatusForLanguage"), "visible statuses must be retranslated when language changes");
assert.ok(appSource.includes('setStatusKey("status.ready"'), "ready status must use a translation key, not a frozen string");
assert.ok(htmlSource.includes('id="togglePasswordBtn"'), "password visibility control must exist");
assert.ok(appSource.includes("passwordUserEntered"), "password visibility must track whether the user entered the password");
assert.ok(appSource.indexOf("let savedCredentialsCache = null;") < appSource.indexOf("applyLanguage(currentLanguage, false);"), "saved credential cache must be initialized before language/UI startup uses it");
assert.ok(appSource.includes('password.addEventListener("beforeinput"'), "password visibility eligibility must be decided before user edits");
assert.ok(appSource.includes("startsFullSecretEntry"), "password visibility must require a fully user-originated field value");
assert.strictEqual(h.startsFullSecretEntry("", 0, 0, "insertText"), true, "typing into an empty password field starts a fully user-entered secret");
assert.strictEqual(h.startsFullSecretEntry("stored-secret", 13, 13, "insertText"), false, "appending to a restored password must not enable reveal");
assert.strictEqual(h.startsFullSecretEntry("stored-secret", 0, 13, "insertText"), true, "replacing the whole restored password is fully user-entered");
assert.strictEqual(h.startsFullSecretEntry("stored-secret", 0, 13, "deleteContentBackward"), false, "deleting a restored password does not itself enable reveal");
assert.ok(cssSource.includes(".header-row {\n  width:100%;"), "header must stay inside the same content column as the application panels");
assert.ok(!cssSource.includes("width: min(1180px"), "header must not break out wider than the main content column");
assert.ok(cssSource.includes("align-self:flex-end;"), "header controls must align to the right within the shared content column");
assert.ok(cssSource.includes("@media (max-width:700px)"), "narrow header must use its dedicated compact layout");
assert.ok(htmlSource.includes('class="password-icon password-icon-show"'), "password reveal must use an inline SVG icon");
assert.ok(cssSource.includes("position:absolute") && cssSource.includes("padding-right:48px"), "password reveal icon must live inside the password field area");
assert.ok(appSource.includes('togglePasswordBtn.setAttribute("aria-label", label)'), "icon-only password reveal must keep an accessible localized label");

assert.ok(htmlSource.includes('href="brand/favicon.svg"'), "adaptive SVG favicon must be linked");
assert.ok(htmlSource.includes('rel="manifest" href="brand/site.webmanifest"'), "web app manifest must be linked");
assert.ok(htmlSource.includes('class="brand-logo"'), "header must include the brand logo");
assert.ok(cssSource.includes(".brand-logo"), "brand logo must have compact layout styling");
assert.ok(appSource.includes('t("about.networkError")'), "About fetch network errors must be localized");
assert.ok(appSource.includes('t("document.networkError")'), "document fetch network errors must be localized");


// PWA install flow: opt-in only, direct installed launch to embed mode.
const manifestSource = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "web", "assets", "brand", "site.webmanifest"), "utf8"));
assert.strictEqual(manifestSource.start_url, "../embed", "installed app must launch directly into embed view");
assert.strictEqual(manifestSource.scope, "../", "manifest scope must remain base-path relative");
assert.ok(htmlSource.includes('id="installBtn"'), "opt-in install button must exist");
assert.ok(htmlSource.includes('id="installDialog"'), "iOS manual install instructions dialog must exist");
assert.ok(appSource.includes('window.addEventListener("beforeinstallprompt"'), "Chromium install prompt must be captured");
assert.ok(appSource.includes("event.preventDefault()"), "install prompt must not be shown automatically");
assert.ok(appSource.includes('window.addEventListener("appinstalled"'), "install UI must hide after installation");
assert.ok(appSource.includes('location.pathname.replace(/\\/+$/, "") === appPath("embed")'), "plain /embed path must activate embed mode for installed launches");
for (const lang of i18n.supported) {
  assert.ok(i18n.translations[lang]["install.button"], `install.button translation missing for ${lang}`);
  assert.ok(i18n.translations[lang]["install.iosHelp"], `install.iosHelp translation missing for ${lang}`);
}

assert.ok(htmlSource.includes('id="orderModeSelect"'), "results ordering selector must exist");
assert.ok(htmlSource.includes('id="icsBtn"'), "ICS export button must exist");
assert.ok(appSource.includes("saveDataCache"), "successful API data must be cached for stale fallback");
assert.ok(appSource.includes("renderCachedFallback"), "cached data fallback must exist");
assert.ok(appSource.includes("serviceWorker.register"), "PWA service worker must be registered when enabled");
assert.ok(appSource.includes("data?.pwa"), "frontend must gate PWA behavior through the server feature flag");
assert.ok(appSource.includes("navigator.serviceWorker.getRegistrations"), "disabling PWA must unregister an existing service worker");
assert.ok(appSource.includes("renyyt-shell-"), "disabling PWA must remove old Renyyt shell caches");
assert.ok(appSource.includes("exportIcs"), "ICS export logic must exist");
assert.ok(appSource.includes("dragstart"), "manual ordering must support drag and drop");

assert.ok(appSource.includes('orderMode === "manual" && !document.body.classList.contains("embed-mode")'), "embed mode must suppress reorder controls while retaining saved ordering");
assert.ok(appSource.includes('appPath(target)'), "Markdown relative links must resolve through the application base path");
assert.ok(appSource.includes('data-doc-path'), "local Markdown links must be marked for in-dialog navigation");
assert.ok(appSource.includes('showMarkdownDocument(link.dataset.docPath, event, false)'), "local Markdown links must stay inside the document dialog");
for (const lang of i18n.supported) {
  assert.ok(i18n.translations[lang]["document.loading"], `document.loading translation missing for ${lang}`);
  assert.ok(i18n.translations[lang]["document.error"], `document.error translation missing for ${lang}`);
  assert.ok(i18n.translations[lang]["document.networkError"], `document.networkError translation missing for ${lang}`);
}
const readmeSource = fs.readFileSync(path.join(__dirname, "..", "README.md"), "utf8");
assert.ok(readmeSource.includes('[Tekninen dokumentaatio](TECHNICAL.md)'), "README technical documentation link must remain relative");
assert.ok(readmeSource.includes('[MIT-lisenssillä](https://opensource.org/license/mit)'), "README license link must use the public OSI MIT page");
assert.ok(!/<https?:\/\//.test(readmeSource), "README should use labeled Markdown links instead of angle-bracket autolinks");
assert.ok(appSource.includes('nextCollectionRefreshAt'), "automatic API refresh must be tied to collection dates, not generic midnight reloads");
assert.ok(appSource.includes('if (currentData) render(currentData);'), "midnight handling must locally rerender current data");
assert.ok(appSource.includes('jsonImportFile'), "frontend must support importing saved JSON data");
assert.ok(appSource.includes('Array.isArray(parsed)'), "saved raw upstream arrays must be accepted for UI testing");
assert.ok(htmlSource.includes('id="jsonImportFile"'), "HTTP dialog must expose saved JSON import control");

assert.ok(htmlSource.includes('id="feedbackAttachData"'), "feedback dialog must offer an explicit collection-data attachment opt-in");
assert.ok(appSource.includes('{ collectionData: currentData }'), "feedback must attach current data only when explicitly selected");
assert.ok(appSource.includes('feedbackAttachData.disabled = !currentData'), "feedback attachment must be disabled when no UI data exists");

const serviceWorkerSource = fs.readFileSync(path.join(__dirname, "..", "web", "service-worker.js"), "utf8");
assert.ok(serviceWorkerSource.includes('const CACHE_NAME = "renyyt-shell-v3";'), "service worker cache version must advance after startup/cache regression fixes");
assert.ok(serviceWorkerSource.includes("const cacheCopy = response.clone();"), "service worker must clone cacheable network responses before asynchronous cache access");
assert.ok(serviceWorkerSource.includes("cache.put(request, cacheCopy)"), "service worker must cache the pre-cloned response body");
assert.ok(!serviceWorkerSource.includes("cache.put(request, response.clone())"), "service worker must not clone a response after asynchronous cache access");

assert.ok(serviceWorkerSource.includes('if (request.mode === "navigate")'), "service worker must handle navigations without runtime cloning/caching");
assert.ok(serviceWorkerSource.includes("event.waitUntil(caches.open(CACHE_NAME)"), "service worker cache writes must be bound to the fetch event lifetime");
assert.ok(appSource.includes('updateViaCache: "none"'), "service worker registration must bypass HTTP cache when checking for updates");
assert.ok(cssSource.includes(".technical-details > summary { cursor:pointer"), "technical details disclosure must use a pointer cursor");

assert.ok(htmlSource.includes('id="reminderBtn"'), "results toolbar must expose the reminder settings button");
assert.ok(htmlSource.includes('id="reminderDialog"'), "reminder dialog must exist");
assert.ok(appSource.includes('registration.pushManager.subscribe'), "frontend must create Web Push subscriptions only on user request");
assert.ok(appSource.includes('api/v1/reminders/sync'), "frontend must sync reminder snapshots to the local server");
assert.ok(serviceWorkerSource.includes('addEventListener("push"'), "service worker must handle Web Push messages");
assert.ok(serviceWorkerSource.includes('showNotification'), "service worker must display received reminder notifications");
for (const lang of i18n.supported) { assert.ok(i18n.translations[lang]["reminders.button"], `reminders.button translation missing for ${lang}`); }


// Per-bin visibility/filtering.
assert.ok(htmlSource.includes('id="serviceFilterBtn"'), "results toolbar must expose per-bin visibility settings");
assert.ok(htmlSource.includes('id="serviceFilterDialog"'), "per-bin visibility dialog must exist");
assert.ok(appSource.includes('SERVICE_FILTER_KEY = "renyyt.serviceVisibility"'), "bin visibility preferences must persist locally");
assert.ok(appSource.includes('serviceVisible(s, visibilityScope)'), "rendering must respect normal/embed visibility");
assert.ok(appSource.includes('serviceVisible(service, "reminders")'), "reminder snapshots must respect per-bin reminder visibility");
assert.ok(appSource.includes('params.set("view"'), "embedded-view URL must carry transferable view state independently of credentials");
assert.ok(appSource.includes('embedVisibleKeys'), "embedded-view state must carry the effective visible-bin selection");
for (const lang of i18n.supported) { assert.ok(i18n.translations[lang]["filters.title"], `filters.title translation missing for ${lang}`); }
