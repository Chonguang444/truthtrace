const CACHE = "truthtrace-v2";
const ASSETS = ["/", "/index.html", "/search", "/situational"];

// Install: pre-cache core assets
self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(CACHE).then(cache => cache.addAll(ASSETS).catch(() => {}))
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE).map(k => caches.delete(k))
    ))
  );
  self.clients.claim();
});

// Fetch: network-first with cache fallback
self.addEventListener("fetch", e => {
  // Skip API calls and non-GET
  if (e.request.url.includes("/api/") || e.request.method !== "GET") return;

  e.respondWith(
    fetch(e.request)
      .then(res => {
        // Cache successful responses
        if (res.ok && (e.request.destination === "script" || e.request.destination === "style" || e.request.destination === "image" || e.request.destination === "font")) {
          const clone = res.clone();
          caches.open(CACHE).then(cache => cache.put(e.request, clone));
        }
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});

// Push notification (future)
self.addEventListener("push", e => {
  const data = e.data?.json() || {};
  self.registration.showNotification(data.title || "TruthTrace", {
    body: data.body || "New rumor alert",
    icon: "/icons/icon-192.png",
    badge: "/icons/badge.png",
    tag: data.tag || "default",
    data: { url: data.url || "/" }
  });
});

self.addEventListener("notificationclick", e => {
  e.notification.close();
  e.waitUntil(
    clients.matchAll({type: "window"}).then(clist => {
      const url = e.notification.data?.url || "/";
      for (const c of clist) {
        if (c.url.includes(url) && "focus" in c) { c.focus(); return; }
      }
      if ("openWindow" in clients) clients.openWindow(url);
    })
  );
});
