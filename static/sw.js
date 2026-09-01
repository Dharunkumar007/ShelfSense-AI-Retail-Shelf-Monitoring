self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open("shelfsense-v1").then((cache) =>
      cache.addAll(["/", "/static/styles.css", "/static/app.js", "/static/manifest.json"])
    )
  );
});

self.addEventListener("fetch", (event) => {
  event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
});
