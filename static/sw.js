/* Service worker: makes the UI installable and available offline.
   API calls are never cached, media downloads always go to the network. */

const CACHE_VERSION = 'ytd-shell-v4';
const SHELL_ASSETS = [
  '/',
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/manifest.webmanifest',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/favicon.ico',
  '/static/icons/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_VERSION);
      await Promise.all(
        SHELL_ASSETS.map(async (asset) => {
          try {
            const response = await fetch(asset, { cache: 'reload' });
            if (response.ok) {
              const url = new URL(asset, self.location.origin);
              await cache.put(url.pathname, response.clone());
            }
          } catch (_) {
            /* offline installs are fine: assets get cached on first use */
          }
        })
      );
      await self.skipWaiting();
    })()
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key)));
      await self.clients.claim();
    })()
  );
});

function isCacheableAsset(url) {
  return (
    url.pathname.startsWith('/static/') ||
    url.pathname === '/manifest.webmanifest' ||
    url.pathname === '/sw.js'
  );
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_VERSION);
  const url = new URL(request.url);
  // Ignore cache-busting query strings so versioned assets still resolve offline.
  const key = url.pathname;
  const cached = await cache.match(key);
  const network = fetch(request)
    .then(async (response) => {
      if (response && response.ok) {
        try {
          await cache.put(key, response.clone());
        } catch (_) {}
      }
      return response;
    })
    .catch(() => cached);
  return cached || network;
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE_VERSION);
  try {
    const response = await fetch(request);
    if (response && response.ok) {
      try {
        await cache.put('/', response.clone());
      } catch (_) {}
    }
    return response;
  } catch (error) {
    const cached = (await cache.match('/')) || (await cache.match(new URL('/', self.location.origin).pathname));
    if (cached) return cached;
    throw error;
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return; // live data only
  if (url.pathname.startsWith('/downloads/')) return; // media files: no caching

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }
  if (isCacheableAsset(url)) {
    event.respondWith(staleWhileRevalidate(request));
  }
});
