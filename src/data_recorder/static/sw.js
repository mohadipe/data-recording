/**
 * Data-Recording PWA Service Worker
 * Enables PWA installability on mobile devices and supports Web Share Target.
 */

const CACHE_NAME = 'data-recorder-v1';
const PRECACHE_ASSETS = [
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/icons/apple-touch-icon.png',
    '/manifest.json'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(PRECACHE_ASSETS);
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => name !== CACHE_NAME)
                    .map((name) => caches.delete(name))
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    // Only handle GET requests in Cache API.
    // Non-GET requests (e.g. POST /wizard/share) pass directly to the server.
    if (event.request.method !== 'GET') {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then((networkResponse) => {
                // If network succeeds, optionally cache static assets
                if (networkResponse && networkResponse.status === 200 && event.request.url.includes('/static/')) {
                    const responseClone = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return networkResponse;
            })
            .catch(() => {
                // Fallback to cache if network is unavailable
                return caches.match(event.request);
            })
    );
});
