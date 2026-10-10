// Klubbhusets service worker: gör att appen startar snabbt och fungerar offline.
// Nyheterna hämtas färskt när det finns nät; annars visas det som hämtades senast.

const VERSION = "klubbhuset-v6";
const SHELL = [
  "./",
  "index.html",
  "styles.css",
  "app.js",
  "api.js",
  "local.js",
  "demo.js",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  // cache: "reload" – hämta direkt från servern, aldrig en gammal kopia ur webbläsarens cache
  event.waitUntil(caches.open(VERSION).then((cache) =>
    cache.addAll(SHELL.map((path) => new Request(path, { cache: "reload" })))));
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

  // Nyheterna (api/): hämta färskt, men visa senast hämtade om nätet saknas.
  if (url.origin === location.origin && url.pathname.includes("/api/")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(VERSION).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Appens egna filer: alltid senaste versionen när det finns nät, sparad kopia offline.
  const isShell = url.origin === location.origin;
  if (isShell) {
    event.respondWith(
      fetch(event.request, { cache: "no-cache" })
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(VERSION).then((cache) => cache.put(event.request, copy));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Typsnitt: ändras aldrig, så visa sparad kopia direkt.
  const isFont = url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com";
  if (!isFont) return;

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
