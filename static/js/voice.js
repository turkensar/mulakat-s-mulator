/* Sesli mülakat (docs/mulakat2.md §2.2): soruları sesli okuma ve mikrofonla cevap yazma.
   Tarayıcının Web Speech API'sini kullanır; ek bir kütüphane ya da sunucu tarafı yoktur.
   Özellik desteklenmiyorsa arayüz hiç görünmez (has-tts / has-stt sınıfları eklenmez). */
(function () {
    'use strict';

    var root = document.querySelector('.session');
    var textarea = document.getElementById('answer-text');
    var form = document.getElementById('answer-form');
    if (!root || !textarea || !form) return;

    // Arayüz metinleri sayfaya gömülü JSON'dan gelir (interviews/views.py _detail_js_strings).
    var T = JSON.parse((document.getElementById('js-strings') || {}).textContent || '{}');

    function fmt(text, values) {
        return String(text).replace(/%\((\w+)\)s/g, function (match, key) { return values[key]; });
    }

    var speechLang = root.dataset.speechLang || 'tr-TR';
    var langPrefix = speechLang.slice(0, 2).toLowerCase();
    var langName = root.dataset.speechName || speechLang;
    var html = document.documentElement;
    var synth = window.speechSynthesis;
    var canSpeak = !!synth && typeof window.SpeechSynthesisUtterance !== 'undefined';
    var note = document.getElementById('voice-note');
    var mic = document.getElementById('mic');
    var autoreadButton = document.getElementById('autoread');
    var STORAGE_KEY = 'mulakat.autoread';

    var voice = null;
    var speakToken = 0;        // eski konuşmanın geç gelen olayları yenisini bozmasın
    var speakingButton = null;
    var recognition = null;
    var recognitionStarted = false;
    var autoread = false;

    // ---- Yardımcılar -------------------------------------------------------

    function recognitionClass() {
        return window.SpeechRecognition || window.webkitSpeechRecognition || null;
    }

    function showNote(message) {
        if (!note) return;
        note.textContent = message;
        note.hidden = !message;
    }

    function readPreference() {
        try { return window.localStorage.getItem(STORAGE_KEY) === '1'; } catch (e) { return false; }
    }

    function savePreference(value) {
        try { window.localStorage.setItem(STORAGE_KEY, value ? '1' : '0'); } catch (e) { /* önemli değil */ }
    }

    // Konuşma motoru `kod`, **kalın** işaretlerini okumasın.
    function cleanForSpeech(text) {
        return String(text).replace(/[`*_#]/g, '').replace(/\s+/g, ' ').trim();
    }

    // Chrome uzun tek konuşmayı ~15 sn sonra kesebiliyor; cümle sınırlarında parçalara böleriz.
    function splitIntoChunks(text) {
        var sentences = text.match(/[^.!?…]+[.!?…]*\s*/g) || [text];
        var chunks = [];
        var current = '';
        sentences.forEach(function (sentence) {
            if (current && (current + sentence).length > 180) {
                chunks.push(current.trim());
                current = sentence;
            } else {
                current += sentence;
            }
        });
        if (current.trim()) chunks.push(current.trim());
        return chunks;
    }

    // ---- Sesli okuma -------------------------------------------------------

    function pickVoice() {
        var voices = synth.getVoices();
        var exact = voices.filter(function (v) {
            return v.lang.replace('_', '-').toLowerCase() === speechLang.toLowerCase();
        });
        var sameLanguage = voices.filter(function (v) {
            return v.lang.toLowerCase().indexOf(langPrefix) === 0;
        });
        var candidates = exact.length ? exact : sameLanguage;
        // Yerel sesler çevrimdışı çalışır ve daha hızlı başlar.
        return candidates.filter(function (v) { return v.localService; })[0] || candidates[0] || null;
    }

    function refreshVoice() {
        voice = pickVoice();
        var available = canSpeak && !!voice;
        html.classList.toggle('has-tts', available);
        if (canSpeak && !voice && synth.getVoices().length) {
            showNote(fmt(T.noVoice, {lang: langName}));
        }
    }

    function setListenButton(button, active) {
        if (!button) return;
        button.classList.toggle('is-active', active);
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
        button.textContent = active ? T.listenStop : T.listen;
    }

    function stopSpeaking() {
        speakToken += 1;
        if (canSpeak) synth.cancel();
        setListenButton(speakingButton, false);
        speakingButton = null;
    }

    function speak(text, button) {
        if (!canSpeak || !voice) return;
        stopSpeaking();
        stopListening(true);
        showNote('');
        var chunks = splitIntoChunks(cleanForSpeech(text));
        if (!chunks.length) return;

        var token = speakToken;
        speakingButton = button || null;
        setListenButton(speakingButton, true);

        function finish() {
            if (token !== speakToken) return;
            setListenButton(speakingButton, false);
            speakingButton = null;
        }

        chunks.forEach(function (chunk, index) {
            var utterance = new window.SpeechSynthesisUtterance(chunk);
            utterance.lang = speechLang;
            utterance.voice = voice;
            if (index === chunks.length - 1) utterance.onend = finish;
            utterance.onerror = finish;
            synth.speak(utterance);
        });
    }

    // ---- Mikrofonla yazma --------------------------------------------------

    var ERROR_MESSAGES = {};
    Object.keys(T.speechErrors || {}).forEach(function (key) {
        ERROR_MESSAGES[key] = fmt(T.speechErrors[key], {lang: langName});
    });

    // 'starting': tıklama alındı, tarayıcı izin/hizmet bekliyor; true: dinliyor; false: boşta.
    function setListening(state) {
        if (!mic) return;
        mic.classList.toggle('is-listening', state === true);
        mic.setAttribute('aria-pressed', state ? 'true' : 'false');
        mic.textContent = state === 'starting' ? T.micStarting : state ? T.micStop : T.micStart;
    }

    function stopListening(discard) {
        if (!recognition) return;
        var current = recognition;
        recognition = null;
        if (discard || !recognitionStarted) {
            // Gönderim ya da başka bir eylem sırasında: geç gelen sonuç alanı bozmasın.
            // Henüz başlamamış (izin/hizmet bekleyen) tanıma da hemen iptal edilir; onend gelmeyebilir.
            current.onresult = null;
            current.onerror = null;
            current.onend = null;
            try { current.abort(); } catch (e) { /* zaten durmuş */ }
            if (!recognitionStarted) showNote('');
            setListening(false);
        } else {
            try { current.stop(); } catch (e) { setListening(false); }
        }
    }

    function startListening() {
        var Recognition = recognitionClass();
        if (!Recognition) return;
        if (textarea.readOnly) {
            showNote(T.micBusy);
            return;
        }
        stopSpeaking();
        showNote('');

        var base = textarea.value;
        if (base && !/\s$/.test(base)) base += ' ';

        var rec = new Recognition();
        rec.lang = speechLang;
        rec.continuous = true;
        rec.interimResults = true;
        rec.maxAlternatives = 1;

        var started = false;
        var errored = false;
        var watchdog = window.setTimeout(function () {
            // Ne başladı ne hata verdi: izin penceresi bekleniyor ya da tarayıcı hizmeti yanıt vermiyor.
            if (recognition !== rec || started || errored) return;
            showNote(T.micSlow);
        }, 4000);

        rec.onstart = function () {
            started = true;
            recognitionStarted = true;
            window.clearTimeout(watchdog);
            showNote('');
            setListening(true);
        };
        rec.onresult = function (event) {
            var finals = [];
            var interim = '';
            for (var i = 0; i < event.results.length; i++) {
                var result = event.results[i];
                var transcript = result[0].transcript.trim();
                if (result.isFinal) finals.push(transcript); else interim += ' ' + transcript;
            }
            textarea.value = base + finals.join(' ') + (finals.length && interim ? ' ' : '') + interim.trim();
        };
        rec.onerror = function (event) {
            if (event.error === 'aborted') return;
            errored = true;
            showNote(ERROR_MESSAGES[event.error] || fmt(T.micGeneric, {error: event.error}));
        };
        rec.onend = function () {
            window.clearTimeout(watchdog);
            if (recognition === rec) recognition = null;
            setListening(false);
            // Hiç başlamadan ve hata vermeden kapandıysa kullanıcı sessizlikte kalmasın.
            if (!started && !errored) showNote(T.micClosed);
        };

        recognition = rec;
        recognitionStarted = false;
        setListening('starting');
        try {
            rec.start();
        } catch (e) {
            window.clearTimeout(watchdog);
            recognition = null;
            setListening(false);
            showNote(fmt(T.micFailed, {error: e && e.name ? e.name : T.unknownError}));
        }
    }

    // ---- Arayüz bağlantıları -----------------------------------------------

    // Soru balonlarındaki "Dinle" düğmeleri (sonradan eklenenler dahil) için olay yetkilendirme.
    document.addEventListener('click', function (event) {
        var button = event.target.closest('.listen');
        if (!button) return;
        if (button === speakingButton) {
            stopSpeaking();
            return;
        }
        var bubble = button.closest('.msg').querySelector('.bubble');
        speak(bubble.textContent, button);
    });

    if (mic) {
        mic.addEventListener('click', function () {
            if (recognition) stopListening(false); else startListening();
        });
    }

    if (autoreadButton) {
        autoread = readPreference();
        var syncToggle = function () {
            autoreadButton.setAttribute('aria-pressed', autoread ? 'true' : 'false');
            autoreadButton.classList.toggle('is-on', autoread);
        };
        syncToggle();
        autoreadButton.addEventListener('click', function () {
            autoread = !autoread;
            savePreference(autoread);
            syncToggle();
            if (autoread) {
                var current = document.getElementById('current-question');
                if (current) speak(current.querySelector('.bubble').textContent, current.querySelector('.listen'));
            } else {
                stopSpeaking();
            }
        });
    }

    // Mülakat ekranı yeni bir soru eklediğinde (cevap gönderildikten sonra).
    document.addEventListener('interview:question', function (event) {
        if (!autoread) return;
        var detail = event.detail || {};
        var button = detail.element ? detail.element.querySelector('.listen') : null;
        speak(detail.text || '', button);
    });

    // Gönderimde dinlemeyi iptal et (geç sonuç, temizlenen alanı yeniden doldurmasın).
    form.addEventListener('submit', function () {
        stopListening(true);
        stopSpeaking();
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') return;
        stopSpeaking();
        stopListening(false);
    });

    window.addEventListener('pagehide', function () {
        stopSpeaking();
        stopListening(true);
    });

    // ---- Başlangıç ---------------------------------------------------------

    if (canSpeak) {
        refreshVoice();
        // Sesler birçok tarayıcıda eşzamansız yüklenir.
        if (typeof synth.addEventListener === 'function') {
            synth.addEventListener('voiceschanged', refreshVoice);
        } else {
            synth.onvoiceschanged = refreshVoice;
        }
    }
    if (recognitionClass()) html.classList.add('has-stt');
})();
