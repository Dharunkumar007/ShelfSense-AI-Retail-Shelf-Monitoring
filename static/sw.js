const CACHE_NAME = "shelfsense-v6";
const VERSION = "20261001-6";
const APP_SHELL = ["/", ...["styles.css", "app.js", "appearance.js", "manifest.json"].map((name) => `/static/${name}?v=${VERSION}`), "/static/shelfsense-logo.jpeg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL.map((url) => new Request(url, {cache:"reload"})))).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key.startsWith("shelfsense-") && key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin || !APP_SHELL.includes(url.pathname + url.search)) return;

  event.respondWith(
    fetch(event.request, {cache:"no-store"})
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)));
        }
        return response;
      })
      .catch(() =>
        caches.match(event.request).then((cached) => {
          if (cached) return cached;
          if (event.request.mode === "navigate") return caches.match("/");
          return Response.error();
        })
      )
  );
});
