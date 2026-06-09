// TruthTrace Service Worker
// 缓存策略: Network First (API) + Cache First (静态资源)

const CACHE_VERSION = "truthtrace-v1";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;
const IMAGE_CACHE = `${CACHE_VERSION}-images`;

// 静态资源预缓存列表
const PRECACHE_URLS = [
  "/",
  "/index.html",
  "/manifest.json",
];

// --- Install: 预缓存关键资源 ---
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(STATIC_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// --- Activate: 清理旧缓存 ---
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== STATIC_CACHE && key !== API_CACHE && key !== IMAGE_CACHE)
            .map((key) => caches.delete(key))
        )
      )
      .then(() => self.clients.claim())
  );
});

// --- Fetch: 智能缓存策略 ---
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 跳过非 GET 请求和非 http/https
  if (request.method !== "GET" || !url.protocol.startsWith("http")) {
    return;
  }

  // API 请求: Network First, 失败时用缓存
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request, API_CACHE));
    return;
  }

  // 图片/字体: Cache First
  if (
    request.destination === "image" ||
    request.destination === "font" ||
    url.pathname.match(/\.(png|jpg|jpeg|gif|svg|ico|woff2?)$/i)
  ) {
    event.respondWith(cacheFirst(request, IMAGE_CACHE));
    return;
  }

  // 静态资源 (JS/CSS): Cache First, 后台更新
  if (
    request.destination === "script" ||
    request.destination === "style" ||
    url.pathname.match(/\.(js|css)$/i)
  ) {
    event.respondWith(staleWhileRevalidate(request, STATIC_CACHE));
    return;
  }

  // 默认: Network First
  event.respondWith(networkFirst(request, STATIC_CACHE));
});

// --- 缓存策略 ---

async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    // 只缓存成功的响应
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    // 离线 fallback
    if (request.destination === "document") {
      return caches.match("/index.html");
    }
    return new Response("离线状态下不可用", { status: 503 });
  }
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response("离线状态下不可用", { status: 503 });
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const fetchPromise = fetch(request)
    .then((response) => {
      if (response.ok) {
        cache.put(request, response.clone());
      }
      return response;
    })
    .catch(() => cached);
  return cached || fetchPromise;
}

// --- 推送通知 (可选) ---
self.addEventListener("push", (event) => {
  if (!event.data) return;
  const data = event.data.json();
  const options = {
    body: data.body || "",
    icon: "/icons/icon-192.png",
    badge: "/icons/icon-192.png",
    data: { url: data.url || "/" },
    vibrate: [200, 100, 200],
    tag: data.tag || "truthtrace",
  };
  event.waitUntil(self.registration.showNotification(data.title || "TruthTrace", options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/";
  event.waitUntil(
    clients.matchAll({ type: "window" }).then((clientList) => {
      for (const client of clientList) {
        if (client.url === url && "focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});
