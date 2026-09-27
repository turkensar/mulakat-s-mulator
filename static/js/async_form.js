/*
 * Sayfayı yenilemeden gönderilen formlar (sunucu sözleşmesi: config/async_forms.py).
 *
 * <form data-async data-network-error="..." data-error-target="ID" data-progress-target="ID">
 *   <button type="submit" data-busy="Hazırlanıyor…">…</button>
 * İlerleme kutusu (templates/_async_progress.html): data-elapsed="{s} sn",
 *   içinde adımlar listesi [data-steps] li, [data-step] ve [data-elapsed-text].
 * Hata kutusu: içinde bir <p>.
 *
 * Yapay zeka yanıtı bir dakikayı bulabildiği için: bekleme boyunca adım adım
 * ilerleyen bir durum gösterilir; hata ya da bağlantı kopmasında sayfa beyaz
 * kalmaz, form (yapıştırılan CV/ilan dahil) olduğu gibi durur ve tekrar denenir.
 */
(function () {
    var CLIENT_TIMEOUT_MS = 150000;
    var STEP_EVERY_MS = 8000;

    function setup(form) {
        var button = form.querySelector('button[type="submit"][data-busy]');
        var errorBox = document.getElementById(form.dataset.errorTarget);
        var progress = document.getElementById(form.dataset.progressTarget);
        var label = button ? button.textContent : '';
        var ticker = null;

        function showError(message) {
            if (!errorBox) {
                window.alert(message);
                return;
            }
            errorBox.querySelector('p').textContent = message;
            errorBox.hidden = false;
            errorBox.scrollIntoView({block: 'center', behavior: 'smooth'});
        }

        function startProgress() {
            if (!progress) {
                return;
            }
            var steps = Array.prototype.map.call(
                progress.querySelectorAll('[data-steps] li'),
                function (li) { return li.textContent; }
            );
            var stepEl = progress.querySelector('[data-step]');
            var elapsedEl = progress.querySelector('[data-elapsed-text]');
            var started = Date.now();
            var index = 0;
            if (stepEl && steps.length) {
                stepEl.textContent = steps[0];
            }
            progress.hidden = false;
            progress.scrollIntoView({block: 'center', behavior: 'smooth'});
            ticker = window.setInterval(function () {
                var seconds = Math.round((Date.now() - started) / 1000);
                if (elapsedEl) {
                    elapsedEl.textContent = progress.dataset.elapsed.replace('{s}', seconds);
                }
                // Son adımda durur: döngüye girmesi "takıldı" izlenimi verir.
                var next = Math.min(Math.floor(seconds * 1000 / STEP_EVERY_MS), steps.length - 1);
                if (stepEl && next !== index && next >= 0) {
                    index = next;
                    stepEl.textContent = steps[index];
                }
            }, 1000);
        }

        function reset() {
            window.clearInterval(ticker);
            if (progress) {
                progress.hidden = true;
            }
            if (button) {
                button.disabled = false;
                button.textContent = label;
            }
            form.dispatchEvent(new CustomEvent('async-form:reset'));
        }

        form.addEventListener('submit', function (event) {
            if (form.dataset.native === '1') {
                return;
            }
            event.preventDefault();
            if (button && button.disabled) {
                return;
            }
            if (errorBox) {
                errorBox.hidden = true;
            }
            if (button) {
                button.disabled = true;
                button.textContent = button.dataset.busy;
            }
            startProgress();

            var controller = window.AbortController ? new AbortController() : null;
            var timer = window.setTimeout(function () {
                if (controller) {
                    controller.abort();
                }
            }, CLIENT_TIMEOUT_MS);

            fetch(form.action || window.location.href, {
                method: 'POST',
                body: new FormData(form),
                headers: {'X-Requested-With': 'fetch'},
                credentials: 'same-origin',
                signal: controller ? controller.signal : undefined
            }).then(function (response) {
                // Vercel zaman aşımı gibi durumlarda yanıt JSON değil HTML olur.
                return response.json().catch(function () { return null; });
            }).then(function (data) {
                window.clearTimeout(timer);
                if (data && data.redirect) {
                    window.location.href = data.redirect;
                    return;
                }
                if (data && data.invalid) {
                    // Alan hataları: normal gönderim, sunucu hataları sayfada gösterir.
                    form.dataset.native = '1';
                    form.submit();
                    return;
                }
                reset();
                showError((data && data.error) || form.dataset.networkError);
            }).catch(function () {
                window.clearTimeout(timer);
                reset();
                showError(form.dataset.networkError);
            });
        });

        // Geri tuşuyla dönüldüğünde sayfa önbellekten gelir; kilitli kalmasın.
        window.addEventListener('pageshow', function (event) {
            if (event.persisted) {
                delete form.dataset.native;
                reset();
            }
        });
    }

    Array.prototype.forEach.call(document.querySelectorAll('form[data-async]'), setup);
})();
