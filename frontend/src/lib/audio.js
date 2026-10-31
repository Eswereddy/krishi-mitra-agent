// Voice helpers: microphone recording with automatic end-of-speech detection, and text-to-speech.

function pickMime() {
  const list = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
  return list.find((m) => window.MediaRecorder?.isTypeSupported?.(m)) || "";
}

export function extFor(mime = "") {
  if (mime.includes("mp4")) return "mp4";
  if (mime.includes("ogg")) return "ogg";
  return "webm";
}

/**
 * Start listening. Stops by itself when the person finishes speaking.
 * Returns { promise, stop, cancel }. promise resolves to a Blob, or null (nothing heard / cancelled).
 */
export function startListening({ onLevel, silenceMs = 1400, waitMs = 9000, maxMs = 40000 } = {}) {
  let finish = () => {};
  const promise = (async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
    const mime = pickMime();
    const mr = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const chunks = [];
    mr.ondataavailable = (e) => e.data?.size && chunks.push(e.data);

    const AC = window.AudioContext || window.webkitAudioContext;
    const ctx = new AC();
    ctx.resume?.();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const buf = new Uint8Array(analyser.fftSize);

    return new Promise((resolve) => {
      const t0 = performance.now();
      let heard = false, lastVoice = 0, floor = 0, raf = 0, reason = "";
      finish = (why) => {
        if (reason) return;
        reason = why;
        cancelAnimationFrame(raf);
        if (mr.state !== "inactive") mr.stop();
        else cleanup();
      };
      const cleanup = () => {
        stream.getTracks().forEach((tr) => tr.stop());
        ctx.close?.();
        onLevel?.(0);
        const blob = new Blob(chunks, { type: mr.mimeType || mime || "audio/webm" });
        const usable =
          reason === "manual" ? blob.size > 3000 : reason === "silence" && heard ? blob.size > 3000 : false;
        resolve(usable ? blob : null);
      };
      mr.onstop = cleanup;

      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / buf.length);
        const now = performance.now();
        onLevel?.(Math.min(1, rms * 7));
        if (now - t0 < 400) floor = Math.max(floor, rms); // measure background noise first
        else {
          if (rms > Math.max(0.022, floor * 2.4)) {
            heard = true;
            lastVoice = now;
          }
          if (heard && now - lastVoice > silenceMs) return finish("silence");
          if (!heard && now - t0 > waitMs) return finish("timeout");
        }
        if (now - t0 > maxMs) return finish(heard ? "silence" : "timeout");
        raf = requestAnimationFrame(tick);
      };
      mr.start(250);
      raf = requestAnimationFrame(tick);
    });
  })();
  return { promise, stop: () => finish("manual"), cancel: () => finish("cancel") };
}

// ---------- Text to speech ----------
// 1) browser voice if the device has one for the language, 2) otherwise an MP3 from the server (/api/tts),
// so Telugu/Hindi answers can be heard even on laptops without those voices.

let token = 0;
const synth = typeof window !== "undefined" ? window.speechSynthesis : null;
let player = null; // one shared <audio> element: unlocked once by a tap, then reusable for hands-free mode
const SILENCE = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";

/** Call from a tap/click handler so later automatic playback is allowed (Safari/Chrome autoplay rules). */
export function unlockAudio() {
  try {
    if (!player) player = new Audio();
    player.src = SILENCE;
    player.play().catch(() => {});
  } catch {
    /* audio unsupported */
  }
}

export function scriptOf(text) {
  return /[\u0C00-\u0C7F]/.test(text) ? "te" : /[\u0900-\u097F]/.test(text) ? "hi" : /[\u0980-\u09FF]/.test(text) ? "bn" : "en";
}

function pickVoice(code) {
  const voices = synth?.getVoices?.() || [];
  const norm = (v) => v.lang.replace("_", "-").toLowerCase();
  return voices.find((v) => norm(v) === `${code}-in`) || voices.find((v) => norm(v).startsWith(code)) || null;
}

export function hasVoice(code) {
  return !!pickVoice(code);
}

// Make the answer sound natural: drop markdown, emoji and links; say "rupees" after amounts.
export function cleanForSpeech(text, code) {
  const rupee = { te: "రూపాయలు", hi: "रुपये", en: "rupees", bn: "টাকা" }[code] || "rupees";
  return text
    .replace(/https?:\/\/\S+/g, "")
    .replace(/₹\s?([\d,]+(?:\.\d+)?)/g, `$1 ${rupee}`)
    .replace(/Rs\.?\s?([\d,]+)/gi, `$1 ${rupee}`)
    .replace(/[*_`#>|]/g, "")
    .replace(/\p{Extended_Pictographic}/gu, "")
    .replace(/\s*\n+\s*/g, ". ")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function chunk(text, max = 170) {
  const parts = text.match(/[^.!?।]+[.!?।]*/g) || [text];
  const out = [];
  let cur = "";
  for (const p of parts) {
    if ((cur + p).length > max && cur) {
      out.push(cur.trim());
      cur = p;
    } else cur += p;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}

export function stopSpeaking() {
  token++;
  try {
    synth?.cancel();
  } catch {
    /* unsupported */
  }
  if (player && !player.paused) {
    player.pause();
    player.dispatchEvent(new Event("ended")); // lets a waiting speak() promise finish
  }
}

async function serverSpeak(text, code, my, onStart) {
  try {
    const r = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, lang: code }),
    });
    if (!r.ok) return "novoice";
    const blob = await r.blob();
    if (my !== token) return "stopped";
    if (!player) player = new Audio();
    const url = URL.createObjectURL(blob);
    return await new Promise((resolve) => {
      const done = (res) => {
        player.onended = player.onerror = null;
        URL.revokeObjectURL(url);
        resolve(res);
      };
      player.onplay = () => onStart?.();
      player.onended = () => done("done");
      player.onerror = () => done("novoice");
      player.src = url;
      player.play().catch(() => done("novoice"));
    });
  } catch {
    return "novoice";
  }
}

/** Speak text; resolves "done", "stopped", or "novoice" if neither a browser voice nor the server could speak. */
const VOICE_LOCALE = { te: "te-IN", hi: "hi-IN", en: "en-IN", bn: "bn-IN", es: "es-ES", fr: "fr-FR", pt: "pt-BR", sw: "sw-KE", id: "id-ID" };

/** `lang` (optional) is the app language: it picks the voice for Latin-script languages (Spanish, French, Swahili...). */
export function speak(text, { onStart, lang } = {}) {
  return new Promise((resolve) => {
    stopSpeaking();
    const my = token;
    const sc = scriptOf(text);
    const code = sc === "en" && VOICE_LOCALE[lang] ? lang : sc;
    const clean = cleanForSpeech(text, code);
    if (!clean) return resolve("empty");
    const voice = synth ? pickVoice(code) : null;
    if (!voice) {
      serverSpeak(clean, code, my, onStart).then((res) => resolve(my !== token ? "stopped" : res));
      return;
    }
    const parts = chunk(clean);
    let i = 0;
    const next = () => {
      if (my !== token) return resolve("stopped");
      if (i >= parts.length) return resolve("done");
      const u = new SpeechSynthesisUtterance(parts[i++]);
      u.lang = VOICE_LOCALE[code] || "en-IN";
      u.voice = voice;
      u.rate = code === "en" ? 1 : 0.95;
      if (i === 1) u.onstart = () => onStart?.();
      u.onend = next;
      u.onerror = () => resolve("error");
      synth.speak(u);
    };
    next();
  });
}

if (synth) synth.getVoices(); // warm up the voice list (loads asynchronously in Chrome)
