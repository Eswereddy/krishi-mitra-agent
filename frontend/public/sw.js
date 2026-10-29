// Offline shell: the app opens without internet and saved answers stay readable. API calls are never cached.
const V = "km-v2";
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(V).then((c) => c.addAll(["/", "/manifest.webmanifest", "/icon.svg"])).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== V).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/")) return;
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).then((r) => { const cp = r.clone(); caches.open(V).then((c) => c.put("/", cp)); return r; }).catch(() => caches.match("/")));
    return;
  }
  e.respondWith(caches.match(e.request).then((hit) => hit || fetch(e.request).then((r) => {
    if (r.ok) { const cp = r.clone(); caches.open(V).then((c) => c.put(e.request, cp)); }
    return r;
  })));
});
