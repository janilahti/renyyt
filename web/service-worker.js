"use strict";
const CACHE_NAME = "renyyt-shell-v3";
const scopeUrl = () => new URL(self.registration.scope);

self.addEventListener("install", event => {
  self.skipWaiting();
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.add(new URL("./", scopeUrl()).href)));
});

self.addEventListener("activate", event => {
  event.waitUntil(Promise.all([
    self.clients.claim(),
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
  ]));
});

function cacheable(request) {
  if (request.method !== "GET") return false;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return false;
  if (/\/(api|metrics)(\/|$)/.test(url.pathname) || /\/(health|ready|version)$/.test(url.pathname)) return false;
  return ["script", "style", "image", "manifest", "font"].includes(request.destination) || url.pathname.endsWith(".md");
}

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(async () => {
      const cachedShell = await caches.match(new URL("./", scopeUrl()).href);
      if (cachedShell) return cachedShell;
      throw new Error("offline");
    }));
    return;
  }
  if (!cacheable(request)) return;
  event.respondWith(fetch(request).then(response => {
    if (response.ok && !response.bodyUsed) {
      const cacheCopy = response.clone();
      event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.put(request, cacheCopy)).catch(() => {}));
    }
    return response;
  }).catch(async () => {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw new Error("offline");
  }));
});

self.addEventListener("push", event => {
  let payload = {};
  try { payload = event.data ? event.data.json() : {}; } catch (_) {}
  const title = payload.title || "Renyyt";
  const options = {
    body: payload.body || "",
    tag: payload.tag || "renyyt-reminder",
    icon: new URL("brand/icon-192.png", scopeUrl()).href,
    badge: new URL("brand/icon-192.png", scopeUrl()).href,
    data: { url: payload.url || "./" }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", event => {
  event.notification.close();
  const target = new URL(event.notification?.data?.url || "./", scopeUrl()).href;
  event.waitUntil((async () => {
    const clientsList = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of clientsList) {
      if (client.url.startsWith(scopeUrl().origin) && "focus" in client) {
        if ("navigate" in client) await client.navigate(target);
        return client.focus();
      }
    }
    return self.clients.openWindow ? self.clients.openWindow(target) : undefined;
  })());
});
