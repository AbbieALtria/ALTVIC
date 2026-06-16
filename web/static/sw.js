// Altria Ops — minimal app-shell service worker
// Caches static assets only; all API calls and HTML pages always hit the network
// (this is a live data dashboard — we never want to serve stale numbers).

const CACHE_NAME = 'altria-ops-shell-v1';
const SHELL_ASSETS = [
    '/static/css/style.css',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS)).catch(() => {})
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((names) =>
            Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Never cache API calls, login, or HTML pages — always live data
    if (url.pathname.startsWith('/api/') || url.pathname === '/login' || url.pathname === '/logout' || url.pathname === '/') {
        return; // let the browser handle it normally (network)
    }

    // Static assets: cache-first, falling back to network
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(event.request).then((cached) => {
                if (cached) return cached;
                return fetch(event.request).then((resp) => {
                    const copy = resp.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)).catch(() => {});
                    return resp;
                });
            })
        );
    }
});
