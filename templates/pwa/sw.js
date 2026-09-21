/* Service worker (docs §2.2 PWA). Amaç yalnızca uygulamanın "yüklenebilir" olması ve
   internet yokken tarayıcının hata sayfası yerine çevrimdışı sayfayı göstermesidir.
   Uygulama AI'ya bağlı olduğu için çevrimdışı çalışmaz; sayfalar, cevaplar ve kullanıcıya
   ait hiçbir veri önbelleğe alınmaz (ortak cihazda başka kullanıcının verisi sızmasın).
   Çevrimdışı sayfa ya da stilleri değişirse CACHE adındaki sürümü artır. */
var CACHE = 'mulakat-offline-v4';
var OFFLINE_URL = '/cevrimdisi/';
var OFFLINE_ASSETS = [OFFLINE_URL, '/static/css/tokens.css', '/static/css/theme.css', '/static/img/icon-192.png'];

self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(CACHE)
            .then(function (cache) {
                // cache: 'reload' → tarayıcı HTTP önbelleğindeki eski kopyayı almasın.
                return cache.addAll(OFFLINE_ASSETS.map(function (url) {
                    return new Request(url, {cache: 'reload'});
                }));
            })
            .then(function () { return self.skipWaiting(); })
    );
});

self.addEventListener('activate', function (event) {
    event.waitUntil(
        caches.keys()
            .then(function (keys) {
                return Promise.all(keys.filter(function (key) { return key !== CACHE; })
                    .map(function (key) { return caches.delete(key); }));
            })
            .then(function () { return self.clients.claim(); })
    );
});

self.addEventListener('fetch', function (event) {
    var request = event.request;
    if (request.method !== 'GET') return;

    // Sayfa gezintisi: önce ağ; ağ hiç yoksa çevrimdışı sayfa. (Sunucu 4xx/5xx dönerse
    // o yanıt olduğu gibi gösterilir; yalnızca bağlantı hatasında yedek devreye girer.)
    // Anlık kopmalarda (zayıf mobil bağlantı) boşuna hata sayfası görünmesin diye bir kez daha denenir.
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request.clone())
                .catch(function () {
                    return new Promise(function (resolve) { setTimeout(resolve, 600); })
                        .then(function () { return fetch(request.clone()); });
                })
                .catch(function () {
                    return caches.match(OFFLINE_URL, {ignoreVary: true});
                })
        );
        return;
    }

    // Çevrimdışı sayfanın stilleri ve simgesi: önce ağ (güncel kalsın), ağ yoksa önbellek.
    var path = new URL(request.url).pathname;
    if (request.url.indexOf(self.location.origin) === 0 && OFFLINE_ASSETS.indexOf(path) > 0) {
        event.respondWith(
            fetch(request).catch(function () {
                return caches.match(request, {ignoreVary: true});
            })
        );
    }
});
