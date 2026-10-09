// Klubbhusets service worker: gör att appen startar snabbt och fungerar offline.
// Nyheterna hämtas alltid färskt från databasen; bara själva appen sparas.

const VERSION = "klubbhuset-v1";
const SHELL = [
  "./",
  "index.html",
  "styles.css",
  "app.js",
  "api.js",
  "config.js",
  "demo.js",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;

  // Appens egna filer och typsnitt: visa sparad version direkt, uppdatera i bakgrunden.
  const isShell = url.origin === location.origin;
  const isFont = url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com";
  const isLibrary = url.hostname === "cdn.jsdelivr.net";
  if (!isShell && !isFont && !isLibrary) return;

  event.respondWith(
    caches.open(VERSION).then(async (cache) => {
      const cached = await cache.match(event.request);
      const network = fetch(event.request)
        .then((response) => {
          if (response.ok) cache.put(event.request, response.clone());
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
