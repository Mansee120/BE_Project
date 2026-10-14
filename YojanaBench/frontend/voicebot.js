/* =====================================================================
   YojanaBench Voice Assistant widget
   A floating, screen-reader-friendly voice chat for the dashboard.
   - Press-and-hold the mic (or tap) to speak.
   - Speech is recognised with the Web Speech API in the selected language
     and answered by the /api/assistant endpoint.
   - Answers are read back with SpeechSynthesis using a matching voice, so
     a blind user can run a full scheme audit by voice alone.
   ===================================================================== */
(function () {
  "use strict";

  const $ = (s) => document.querySelector(s);

  const LANGS = [
    { code: "en-IN", label: "English (India)" },
    { code: "hi-IN", label: "Hindi (हिन्दी)" },
    { code: "mr-IN", label: "Marathi (मराठी)" },
    { code: "ta-IN", label: "Tamil (தமிழ்)" },
    { code: "te-IN", label: "Telugu (తెలుగు)" },
    { code: "kn-IN", label: "Kannada (ಕನ್ನಡ)" },
    { code: "ml-IN", label: "Malayalam (മലയാളം)" },
    { code: "bn-IN", label: "Bengali (বাংলা)" },
    { code: "gu-IN", label: "Gujarati (ગુજરાતી)" },
    { code: "pa-IN", label: "Punjabi (ਪੰਜਾਬੀ)" },
    { code: "or-IN", label: "Odia (ଓଡ଼ିଆ)" },
    { code: "as-IN", label: "Assamese (অসমীয়া)" },
    { code: "ur-PK", label: "Urdu (اردو)" },
    { code: "ne-NP", label: "Nepali (नेपाली)" },
    { code: "en-US", label: "English (US)" },
    { code: "en-GB", label: "English (UK)" },
    { code: "fr-FR", label: "French (Français)" },
    { code: "es-ES", label: "Spanish (Español)" },
    { code: "de-DE", label: "German (Deutsch)" },
    { code: "ar-SA", label: "Arabic (العربية)" },
  ];

  const CHIPS = [
    "How many schemes are there?",
    "How much amount under PM Kisan?",
    "What documents are needed for ration card?",
    "Check if I am eligible for old age pension",
    "Write the audit case for old age pension",
  ];

  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const supportsSpeech = !!SR;
  const isTouch = "ontouchstart" in window;

  let panel = null;
  let messages = null;
  let statusEl = null;
  let micBtn = null;
  let micLabel = null;
  let launcher = null;
  let langSel = null;
  let muteBtn = null;
  let inputEl = null;

  let recognition = null;
  let listening = false;
  let thinking = false;
  let muted = false;
  let open = false;
  let welcomed = false;
  let userEngaged = false;
  let pendingSpeech = null;

  const AUTO_START_MS = 5000;
  const WELCOME_HI =
    "नमस्ते! योजना बेंच में आपका स्वागत है। मैं आपकी आज मदद करूँगी। " +
    "बोलने के लिए नीचे माइक्रोफ़ोन का बटन दबाकर रखें और फिर छोड़ दें, " +
    "या अपना सवाल टाइप करें। मैं किसी भी योजना, ज़रूरी दस्तावेज़, मिलने वाली " +
    "राशि और पूरी पात्रता की जाँच के बारे में बता सकती हूँ।";
  const WELCOME_EN =
    "Namaste! Welcome to YojanaBench. I am here to help you today. " +
    "To speak, press and hold the microphone button at the bottom, then release. " +
    "You can also type your question. I can explain any scheme, the documents " +
    "you need, the money you will get, and run a full voice audit for you.";

  const sessionId = "vb-" + (Date.now().toString(36)) + "-" +
    Math.random().toString(36).slice(2, 8);
  const savedLang = localStorage.getItem("vb_lang") || "hi-IN";

  function welcomeText() {
    return currentLang().toLowerCase().startsWith("hi") ? WELCOME_HI : WELCOME_EN;
  }

  function currentLang() {
    return langSel ? langSel.value : savedLang;
  }

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function buildLangOptions() {
    const opts = LANGS.map((l) =>
      `<option value="${l.code}"${l.code === savedLang ? " selected" : ""}>${esc(l.label)}</option>`
    ).join("");
    langSel.innerHTML = opts;
  }

  // ------------------------------------------------------------------ TTS
  function allVoices() {
    return window.speechSynthesis && speechSynthesis.getVoices()
      ? speechSynthesis.getVoices() : [];
  }

  // getVoices() is empty until the browser has loaded its voice list, which
  // happens asynchronously. Wait for it (briefly) before speaking.
  function ensureVoices(timeoutMs) {
    return new Promise((resolve) => {
      if (!window.speechSynthesis) return resolve([]);
      const have = allVoices();
      if (have.length) return resolve(have);
      let settled = false;
      const onch = () => done();
      const done = () => {
        if (settled) return;
        settled = true;
        try { speechSynthesis.removeEventListener("voiceschanged", onch); } catch (err) { /* ignore */ }
        resolve(allVoices());
      };
      try { speechSynthesis.addEventListener("voiceschanged", onch); } catch (err) { /* ignore */ }
      setTimeout(done, timeoutMs || 1500);
    });
  }

  function matchingVoice(voices, lang) {
    const target = String(lang || "en").toLowerCase();
    const base = target.split("-")[0];
    if (!voices.length) return null;
    return voices.find((v) => v.lang && v.lang.toLowerCase() === target)
      || voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(base) &&
        /(Microsoft|Google|iOS|Natural|Swara|Heera|Priya|Kalpana|Neerja|Rishi|Lekha)/i.test(v.name))
      || voices.find((v) => v.lang && v.lang.toLowerCase().startsWith(base))
      || null;
  }

  function fallbackVoice(voices) {
    return voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("en-in"))
      || voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("en"))
      || voices.find((v) => v.default)
      || voices[0] || null;
  }

  function hasVoiceFor(lang) {
    return !!matchingVoice(allVoices(), lang);
  }

  function speak(text) {
    if (muted || !text || !window.speechSynthesis) return;
    ensureVoices().then((voices) => {
      if (muted || !text) return;
      speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text.replace(/\s+/g, " ").trim());
      const voice = matchingVoice(voices, currentLang()) || fallbackVoice(voices);
      if (voice) {
        utter.voice = voice;
        utter.lang = voice.lang;
      } else {
        utter.lang = currentLang() || "en-US";
      }
      utter.rate = 0.98;
      utter.volume = 1;

      // Chrome blocks the first utterance until the page has had a user
      // gesture. If that happens (error 'not-allowed' or nothing starts),
      // remember the text so we can replay it on the first key press or tap.
      let started = false;
      utter.onstart = () => { started = true; pendingSpeech = null; };
      utter.onerror = (e) => {
        if (!e || e.error === "not-allowed") pendingSpeech = text;
      };
      try { speechSynthesis.speak(utter); } catch (err) { pendingSpeech = text; }
      setTimeout(() => {
        if (!started && !muted) {
          pendingSpeech = text;
          setStatus("Press any key or tap once to hear the voice", "");
        }
      }, 1200);
    });
  }

  function flushPending() {
    if (pendingSpeech && !muted) {
      const text = pendingSpeech;
      pendingSpeech = null;
      speak(text);
      return true;
    }
    return false;
  }

  // ------------------------------------------------------------ messages
  function addBubble(kind, text) {
    const div = document.createElement("div");
    div.className = "vb-bubble vb-" + kind;
    const paras = String(text || "").split(/\n{2,}/);
    div.innerHTML = paras.map((p) => `<p>${esc(p)}</p>`).join("");
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  function setStatus(text, cls) {
    statusEl.textContent = text || "";
    statusEl.className = "vb-status" + (cls ? " " + cls : "");
  }

  // -------------------------------------------------------------- backend
  async function sendMessage(text) {
    text = String(text || "").trim();
    if (!text || thinking) return;
    userEngaged = true;
    addBubble("user", text);
    inputEl.value = "";
    setStatus("Thinking…", "work");
    thinking = true;
    micBtn.classList.add("vb-busy");
    try {
      const resp = await fetch("/api/assistant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, lang: currentLang(), session_id: sessionId }),
      });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      const data = await resp.json();
      addBubble("bot", data.reply || "Sorry, I could not answer that.");
      speak(data.reply);
    } catch (err) {
      const msg = "Could not reach the assistant. Is the backend running? (" +
        (err && err.message) + ")";
      addBubble("bot", msg);
      setStatus("Error", "err");
    } finally {
      thinking = false;
      micBtn.classList.remove("vb-busy");
      setStatus(listening ? "Listening…" : "", listening ? "live" : "");
    }
  }

  // ---------------------------------------------------------------- mic
  function startListening() {
    if (!supportsSpeech) {
      setStatus("Speech input is not supported in this browser. Use Chrome or Edge.", "err");
      return;
    }
    if (listening || thinking) return;
    speechSynthesis.cancel();
    try {
      recognition = new SR();
    } catch (err) {
      setStatus("Could not start speech recognition.", "err");
      return;
    }
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.lang = currentLang();

    recognition.onresult = (e) => {
      const text = e.results[0] && e.results[0][0] && e.results[0][0].transcript;
      setStatus("", "");
      stopListeningUI();
      if (text && text.trim()) sendMessage(text);
    };
    recognition.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        setStatus("Microphone permission denied. Enable it for this site.", "err");
      } else if (e.error === "no-speech") {
        setStatus("No speech heard. Press and hold the mic and try again.", "");
      } else if (e.error !== "aborted") {
        setStatus("Speech error: " + e.error, "err");
      }
      stopListeningUI();
    };
    recognition.onend = () => stopListeningUI();

    listening = true;
    micBtn.classList.add("vb-live");
    micLabel.innerHTML = "Listening…";
    setStatus("Listening… speak now", "live");
    try {
      recognition.start();
    } catch (err) {
      listening = false;
      micBtn.classList.remove("vb-live");
      micLabel.innerHTML = "Hold<br/>to talk";
      setStatus("Speech engine not ready. Try again.", "err");
    }
  }

  function stopListeningUI() {
    listening = false;
    micBtn.classList.remove("vb-live");
    micLabel.innerHTML = "Hold<br/>to talk";
    setStatus(thinking ? "Thinking…" : "", thinking ? "work" : "");
  }

  // ---------------------------------------------------------------- UI
  function setOpen(value) {
    open = value;
    panel.classList.toggle("vb-open", value);
    panel.setAttribute("aria-hidden", String(!value));
    launcher.setAttribute("aria-expanded", String(value));
    if (value) {
      micBtn.focus();
      if (!welcomed) {
        welcomed = true;
        const greet = welcomeText();
        addBubble("bot", greet);
        ensureVoices().then((voices) => {
          const needsNative = !currentLang().toLowerCase().startsWith("en");
          if (needsNative && !matchingVoice(voices, currentLang())) {
            const note =
              "Heads up: this browser has no voice installed for the selected " +
              "language, so you may not hear replies. Please open YojanaBench in " +
              "Google Chrome or Microsoft Edge, or pick another language above.";
            addBubble("bot", note);
            speak(note);
          } else {
            speak(greet);
          }
        });
      }
    } else {
      speechSynthesis.cancel();
      stopListeningUI();
    }
  }

  function onMicHold() {
    if (isTouch) {
      if (listening) stopListenNow();
      else startListening();
    } else {
      startListening();
    }
  }

  function onMicRelease() {
    if (!isTouch && listening) {
      stopListenNow();
    }
  }

  function stopListenNow() {
    if (recognition) {
      try { recognition.stop(); } catch (err) { /* ignore */ }
    }
    stopListeningUI();
  }

  function init() {
    launcher = $("#vb-launcher");
    panel = $("#vb-panel");
    messages = $("#vb-messages");
    statusEl = $("#vb-status");
    micBtn = $("#vb-mic");
    micLabel = $("#vb-mic-label");
    langSel = $("#vb-lang");
    muteBtn = $("#vb-mute");
    inputEl = $("#vb-input");

    buildLangOptions();

    launcher.addEventListener("click", () => { userEngaged = true; setOpen(!open); });
    $("#vb-close").addEventListener("click", () => { userEngaged = true; setOpen(false); });

    micBtn.addEventListener("pointerdown", (e) => {
      e.preventDefault(); userEngaged = true;
      if (flushPending()) return;
      onMicHold();
    });
    micBtn.addEventListener("pointerup", onMicRelease);
    micBtn.addEventListener("pointerleave", onMicRelease);
    micBtn.addEventListener("keydown", (e) => {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault(); userEngaged = true;
        if (flushPending()) return;
        startListening();
      }
    });
    micBtn.addEventListener("keyup", (e) => {
      if ((e.key === " " || e.key === "Enter") && listening) stopListenNow();
    });

    $("#vb-send").addEventListener("click", () => sendMessage(inputEl.value));
    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendMessage(inputEl.value);
    });

    langSel.addEventListener("change", () => {
      localStorage.setItem("vb_lang", langSel.value);
      if (listening) stopListenNow();
      updateMuteLabel();
    });

    muteBtn.addEventListener("click", () => {
      muted = !muted;
      if (muted) speechSynthesis.cancel();
      updateMuteLabel();
    });

    // Warm the voice list once the browser reports it is ready.
    if (window.speechSynthesis) {
      ensureVoices();
    }

    // Welcome chips
    const chips = $("#vb-chips");
    chips.innerHTML = CHIPS.map((c) =>
      `<button class="vb-chip" type="button">${esc(c)}</button>`).join("");
    chips.addEventListener("click", (e) => {
      if (e.target.classList.contains("vb-chip")) sendMessage(e.target.textContent);
    });

    updateMuteLabel();

    if (!supportsSpeech) {
      micBtn.disabled = true;
      micLabel.innerHTML = "Speech<br/>not supported";
      micBtn.title = "Speech recognition needs Chrome or Edge";
    }

    // First user gesture both unlocks speech playback and replays any greeting
    // that the browser blocked while the page was still "cold".
    const unlock = () => { flushPending(); };
    document.addEventListener("pointerdown", unlock, { once: true });
    document.addEventListener("keydown", unlock, { once: true });

    // Accessibility: a blind visitor cannot see where to click. So, a few
    // seconds after landing, open the assistant and greet them out loud by
    // itself -- unless they already started using it.
    setTimeout(() => {
      if (!userEngaged && !open) {
        setOpen(true);
      }
    }, AUTO_START_MS);
  }

  function updateMuteLabel() {
    muteBtn.textContent = muted ? "Audio Off" : "Audio On";
    muteBtn.setAttribute("aria-label", muted ? "Turn spoken replies on" : "Turn spoken replies off");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();