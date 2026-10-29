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

let token = 0;
const synth = typeof window !== "undefined" ? window.speechSynthesis : null;

export function scriptOf(text) {
  return /[\u0C00-\u0C7F]/.test(text) ? "te" : /[\u0900-\u097F]/.test(text) ? "hi" : "en";
}

function pickVoice(code) {
  const voices = synth?.getVoices?.() || [];
  const norm = (v) => v.lang.replace("_", "-").toLowerCase();
  return (
    voices.find((v) => norm(v) === `${code}-in`) ||
    voices.find((v) => norm(v).startsWith(code)) ||
    null
  );
}

export function hasVoice(code) {
  return !!pickVoice(code);
}

// Make the answer sound natural: drop markdown, emoji and links; say "rupees" after amounts.
export function cleanForSpeech(text, code) {
  const rupee = { te: "రూపాయలు", hi: "रुपये", en: "rupees" }[code];
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
}

/** Speak text; resolves when finished or stopped. Resolves "novoice" if no matching voice is installed. */
export function speak(text, { onStart } = {}) {
  return new Promise((resolve) => {
    if (!synth) return resolve("unsupported");
    stopSpeaking();
    const my = token;
    const code = scriptOf(text);
    const voice = pickVoice(code);
    const parts = chunk(cleanForSpeech(text, code));
    if (!parts.length) return resolve("empty");
    let i = 0;
    const next = () => {
      if (my !== token) return resolve("stopped");
      if (i >= parts.length) return resolve(voice ? "done" : "novoice");
      const u = new SpeechSynthesisUtterance(parts[i++]);
      u.lang = { te: "te-IN", hi: "hi-IN", en: "en-IN" }[code];
      if (voice) u.voice = voice;
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
