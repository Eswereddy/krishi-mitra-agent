import { useCallback, useEffect, useRef, useState } from "react";
import { T, LANGS } from "./i18n";
import { startListening, speak, stopSpeaking, extFor, unlockAudio } from "./lib/audio";
import { Markdown, ToolCards, StepChips, LiveSteps, SourcesLine, I } from "./components";
import { ExtraSheet, ex, leafScan, adviceCard } from "./extras";

const DEFAULT_PROFILE = { state: "Andhra Pradesh", district: "", owns_land: false, main_crop: "" };
const uid = () => Math.random().toString(36).slice(2, 9);
const load = (k, fb) => {
  try {
    const v = localStorage.getItem(k);
    return v == null ? fb : JSON.parse(v);
  } catch {
    return fb;
  }
};
const save = (k, v) => {
  try {
    localStorage.setItem(k, JSON.stringify(v));
  } catch {
    /* storage unavailable */
  }
};

// Phone photos are huge; shrink before upload (faster, same diagnosis quality).
async function shrink(file, max = 1024) {
  try {
    const bmp = await createImageBitmap(file);
    const scale = Math.min(1, max / Math.max(bmp.width, bmp.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * scale);
    canvas.height = Math.round(bmp.height * scale);
    canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.85));
    return blob || file;
  } catch {
    return file;
  }
}

export default function App() {
  const [lang, setLang] = useState(() => load("km-lang", "auto"));
  const [theme, setTheme] = useState(() => load("km-theme", window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  const [autoSpeak, setAutoSpeak] = useState(() => load("km-autospeak", false));
  const [profile, setProfile] = useState(() => ({ ...DEFAULT_PROFILE, ...load("km-profile", {}) }));
  const [messages, setMessages] = useState(() => load("km-chat", []).filter((m) => !m.pending));
  const [text, setText] = useState("");
  const [photo, setPhoto] = useState(null); // { file, url }
  const [busy, setBusy] = useState(false);
  const [rec, setRec] = useState("idle"); // idle | recording
  const [speakingId, setSpeakingId] = useState(null);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [vstate, setVstate] = useState("idle"); // idle | listening | thinking | speaking
  const [vlive, setVlive] = useState("");
  const [showProfile, setShowProfile] = useState(false);
  const [showAttach, setShowAttach] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [toast, setToast] = useState("");
  const [extra, setExtra] = useState(null); // { kind: "scan" | "card", loading, data, error, run }
  const [big, setBig] = useState(() => load("km-big", false));
  const [online, setOnline] = useState(() => navigator.onLine !== false);
  const [installEvt, setInstallEvt] = useState(null);
  const [alerts, setAlerts] = useState(() => load("km-alerts", []));
  const [alertRes, setAlertRes] = useState({}); // id -> latest check result from the server
  const [showAlerts, setShowAlerts] = useState(false);
  const [dismissed, setDismissed] = useState([]);
  const [draft, setDraft] = useState({ crop: "", target: "", direction: "above" });

  const t = T[lang === "auto" ? "te" : lang];
  const tRef = useRef(t);
  tRef.current = t;
  const messagesRef = useRef(messages);
  const busyRef = useRef(false);
  const autoSpeakRef = useRef(autoSpeak);
  const voiceRef = useRef(false);
  const listenerRef = useRef(null);
  const cancelledRef = useRef(false);
  const orbRef = useRef(null);
  const meterRef = useRef(null);
  const endRef = useRef(null);
  const camRef = useRef(null);
  const galRef = useRef(null);
  const failRef = useRef(0);

  messagesRef.current = messages;
  autoSpeakRef.current = autoSpeak;

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    save("km-theme", theme);
  }, [theme]);
  useEffect(() => { document.documentElement.lang = t.code; }, [t.code]);
  useEffect(() => save("km-lang", lang), [lang]);
  useEffect(() => {
    document.documentElement.dataset.size = big ? "lg" : "";
    save("km-big", big);
  }, [big]);
  useEffect(() => {
    const on = () => setOnline(true), off = () => setOnline(false);
    const beforeInstall = (e) => { e.preventDefault(); setInstallEvt(e); };
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    window.addEventListener("beforeinstallprompt", beforeInstall);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
      window.removeEventListener("beforeinstallprompt", beforeInstall);
    };
  }, []);
  useEffect(() => save("km-autospeak", autoSpeak), [autoSpeak]);
  useEffect(() => save("km-profile", profile), [profile]);
  useEffect(() => {
    // keep the last 40 messages (photos are not stored, only the text)
    save("km-chat", messages.filter((m) => !m.pending).slice(-40).map((m) => ({ ...m, image: null })));
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);
  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 3200);
    return () => clearTimeout(id);
  }, [toast]);

  useEffect(() => save("km-alerts", alerts), [alerts]);

  // Price alerts live on the device. Ask the server for the latest live prices now, every 15 minutes,
  // and whenever the phone comes back online; notify once per alert per day when a target is reached.
  const alertsRef = useRef(alerts);
  alertsRef.current = alerts;
  const checkAlerts = useCallback(async (manual = false) => {
    const list = alertsRef.current;
    if (!list.length || !navigator.onLine) return;
    try {
      const r = await fetch("/api/alerts/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ alerts: list.map((a) => ({ ...a, state: profile.state })) }) });
      if (!r.ok) return;
      const { results } = await r.json();
      setAlertRes(Object.fromEntries(results.map((x) => [x.id, x])));
      const today = new Date().toISOString().slice(0, 10);
      const seen = load("km-alerts-seen", {});
      results.filter((x) => x.triggered && seen[x.id] !== today).forEach((x) => {
        seen[x.id] = today;
        const msg = `${tRef.current.al.banner}: ${x.crop} ₹${Number(x.current).toLocaleString("en-IN")} (${x.market || x.district})`;
        setToast(msg);
        try { if (window.Notification?.permission === "granted") new Notification(tRef.current.title, { body: msg, icon: "/icon.svg" }); } catch { /* notifications unavailable */ }
      });
      save("km-alerts-seen", seen);
      if (manual) setToast(tRef.current.al.check + " ✓");
    } catch { /* offline or server busy: try again at the next check */ }
  }, [profile.state]);
  useEffect(() => {
    checkAlerts();
    const id = setInterval(checkAlerts, 15 * 60 * 1000);
    window.addEventListener("online", checkAlerts);
    return () => { clearInterval(id); window.removeEventListener("online", checkAlerts); };
  }, [checkAlerts, alerts.length]);
  function addAlert() {
    const target = Number(draft.target);
    const crop = (draft.crop || profile.main_crop || "").trim();
    if (!profile.district) return setToast(t.al.needDistrict);
    if (!crop || !(target > 0)) return;
    setAlerts((l) => [...l, { id: uid(), crop, district: profile.district, target, direction: draft.direction }].slice(-5));
    setDraft({ crop: "", target: "", direction: "above" });
  }
  async function enableNotifications() {
    try { await window.Notification?.requestPermission(); } catch { /* not supported */ }
  }

  const onLevel = useCallback((lv) => {
    orbRef.current?.style.setProperty("--lvl", lv.toFixed(3));
    meterRef.current?.style.setProperty("--lvl", lv.toFixed(3));
  }, []);

  // ---------- speaking ----------
  async function speakMessage(id, answer) {
    setSpeakingId(id);
    const res = await speak(answer);
    setSpeakingId((s) => (s === id ? null : s));
    if (res === "novoice") setToast(tRef.current.noVoice);
    return res;
  }
  function toggleSpeak(m) {
    unlockAudio();
    if (speakingId === m.id) {
      stopSpeaking();
      setSpeakingId(null);
    } else speakMessage(m.id, m.text);
  }

  // ---------- sending ----------
  // Progress events from the streaming endpoints: each tool call shows up in the waiting bubble as it starts.
  function patchLive(bid, ev) {
    const tt = tRef.current;
    setMessages((list) =>
      list.map((x) => {
        if (x.id !== bid) return x;
        let live = [...(x.live || [])];
        if (ev.type === "status" && ev.key === "reading_photo") live.push({ key: "photo", label: tt.readingPhoto, done: false });
        else if (ev.type === "tool") {
          live = live.map((l) => (l.key === "photo" ? { ...l, done: true } : l));
          live.push({ key: ev.tool, label: tt.tools[ev.tool] || ev.tool, done: false });
        } else if (ev.type === "tool_done") {
          for (let k = live.length - 1; k >= 0; k--) {
            if (live[k].key === ev.tool && !live[k].done) { live[k] = { ...live[k], done: true }; break; }
          }
        } else if (ev.type === "verify") live.push({ key: "verify", label: tt.verifying, done: true });
        return { ...x, live };
      })
    );
  }

  async function readResult(r, bid) {
    if (!(r.headers.get("content-type") || "").includes("ndjson")) return r.json(); // older backend: plain JSON
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    let data = null;
    const handle = (ev) => {
      if (ev.type === "final") data = ev.data;
      else if (ev.type === "error") throw new Error(ev.detail);
      else patchLive(bid, ev);
    };
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, i).trim();
        buf = buf.slice(i + 1);
        if (line) handle(JSON.parse(line));
      }
    }
    if (buf.trim()) handle(JSON.parse(buf));
    if (!data) throw new Error("No answer received");
    return data;
  }

  async function send({ text: q0, file, speakReply = false, noSpeak = false }) {
    const q = (q0 || "").trim();
    if (busyRef.current || (!q && !file)) return null;
    if (!navigator.onLine) {
      setToast(tRef.current.offline);
      return null;
    }
    busyRef.current = true;
    setBusy(true);
    stopSpeaking();
    setSpeakingId(null);
    const bid = uid();
    let blob = null;
    let url = null;
    if (file) {
      blob = await shrink(file);
      url = URL.createObjectURL(blob);
    }
    const history = messagesRef.current
      .filter((m) => !m.pending && !m.error && m.text)
      .slice(-6)
      .map((m) => ({ role: m.role === "bot" ? "assistant" : "user", content: m.text }));
    setMessages((m) => [...m, { id: uid(), role: "user", text: q, image: url }, { id: bid, role: "bot", pending: true }]);
    try {
      let r;
      if (blob) {
        const form = new FormData();
        form.append("image", blob, "crop.jpg");
        form.append("question", q);
        form.append("lang", lang);
        form.append("profile", JSON.stringify(profile));
        r = await fetch("/api/diagnose/stream", { method: "POST", body: form });
      } else {
        r = await fetch("/api/agent/stream", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: q, lang, profile, history }),
        });
      }
      if (!r.ok) {
        let d = "";
        try { d = (await r.json()).detail; } catch { /* not json */ }
        throw new Error(d || `Error ${r.status}`);
      }
      const data = await readResult(r, bid);
      setMessages((m) => m.map((x) => (x.id === bid ? { id: bid, role: "bot", text: data.answer, steps: data.steps || [], verification: data.verification, mock: data.mock } : x)));
      if (!noSpeak && (speakReply || autoSpeakRef.current)) speakMessage(bid, data.answer);
      return { id: bid, answer: data.answer };
    } catch (e) {
      setMessages((m) => m.map((x) => (x.id === bid ? { id: bid, role: "bot", error: true, text: e.message, retry: { text: q, file } } : x)));
      return null;
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  // One-tap daily brief: weather, irrigation, spraying, price and sell/hold from the backend (no model call).
  async function dailyBrief() {
    unlockAudio();
    if (busyRef.current) return;
    if (!navigator.onLine) { setToast(tRef.current.offline); return; }
    busyRef.current = true;
    setBusy(true);
    stopSpeaking();
    setSpeakingId(null);
    const bid = uid();
    setMessages((m) => [...m, { id: uid(), role: "user", text: t.today }, { id: bid, role: "bot", pending: true }]);
    try {
      const r = await fetch("/api/brief", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile, lang: lang === "auto" ? "te" : lang }),
      });
      if (!r.ok) throw new Error(`Error ${r.status}`);
      const data = await r.json();
      setMessages((m) => m.map((x) => (x.id === bid ? { id: bid, role: "bot", text: data.answer, steps: data.steps || [], verification: data.verification } : x)));
      if (autoSpeakRef.current) speakMessage(bid, data.answer);
    } catch (e) {
      setMessages((m) => m.map((x) => (x.id === bid ? { id: bid, role: "bot", error: true, text: e.message } : x)));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function submit() {
    unlockAudio();
    const file = photo?.file;
    const q = text;
    if (!q.trim() && !file) return;
    setText("");
    clearPhoto();
    send({ text: q, file });
  }

  function retry(m) {
    setMessages((list) => list.filter((x) => x.id !== m.id));
    send({ text: m.retry.text, file: m.retry.file });
  }

  function newChat() {
    stopSpeaking();
    setSpeakingId(null);
    setMessages([]);
  }

  // ---------- photo ----------
  function pickPhoto(file) {
    if (!file || !file.type.startsWith("image/")) return;
    if (photo?.url) URL.revokeObjectURL(photo.url);
    setPhoto({ file, url: URL.createObjectURL(file) });
    setShowAttach(false);
  }
  function clearPhoto() {
    if (photo?.url) URL.revokeObjectURL(photo.url);
    setPhoto(null);
  }

  // ---------- voice ----------
  async function transcribe(blob) {
    const form = new FormData();
    form.append("audio", blob, `question.${extFor(blob.type)}`);
    const r = await fetch("/api/asr", { method: "POST", body: form }); // Muse Voice Transcribe when configured, else Spark Open
    if (r.status === 422) {
      const e = new Error(tRef.current.unclear);
      e.unclear = true;
      throw e;
    }
    if (!r.ok) {
      let d = "";
      try { d = (await r.json()).detail; } catch { /* not json */ }
      throw new Error(d || "transcribe failed");
    }
    return (await r.json()).text;
  }

  // Microphone button next to the text box: record, auto-stop on silence, transcribe, ask, read the reply aloud.
  async function micToggle() {
    if (rec === "recording") return listenerRef.current?.stop();
    unlockAudio();
    if (busyRef.current) return;
    stopSpeaking();
    setSpeakingId(null);
    cancelledRef.current = false;
    try {
      const l = startListening({ onLevel });
      listenerRef.current = l;
      setRec("recording");
      const blob = await l.promise;
      setRec("idle");
      if (cancelledRef.current) return;
      if (!blob) return setToast(t.unclear);
      const heard = await transcribe(blob);
      const file = photo?.file;
      clearPhoto();
      await send({ text: heard, file, speakReply: true });
    } catch (e) {
      setRec("idle");
      setToast(e.name === "NotAllowedError" ? t.mic + e.message : e.message);
    }
  }
  function cancelRec() {
    cancelledRef.current = true;
    listenerRef.current?.cancel();
  }

  // Hands-free conversation: listen -> answer -> speak -> listen again.
  async function voiceTurn() {
    if (!voiceRef.current) return;
    setVstate("listening");
    setVlive("");
    let blob;
    try {
      const l = startListening({ onLevel });
      listenerRef.current = l;
      blob = await l.promise;
    } catch (e) {
      setToast(t.mic + e.message);
      return setVstate("idle");
    }
    if (!voiceRef.current) return;
    if (!blob) {
      failRef.current++;
      return failRef.current >= 2 ? setVstate("idle") : voiceTurn();
    }
    setVstate("thinking");
    let heard;
    try {
      heard = await transcribe(blob);
    } catch (e) {
      if (!voiceRef.current) return;
      failRef.current++;
      setToast(e.message);
      return e.unclear && failRef.current < 3 ? voiceTurn() : setVstate("idle");
    }
    if (!voiceRef.current) return;
    failRef.current = 0;
    setVlive(heard);
    const res = await send({ text: heard, noSpeak: true });
    if (!voiceRef.current) return;
    if (!res) return setVstate("idle");
    setVstate("speaking");
    await speakMessage(res.id, res.answer);
    if (voiceRef.current) voiceTurn();
  }
  function openVoice() {
    unlockAudio();
    stopSpeaking();
    setSpeakingId(null);
    voiceRef.current = true;
    failRef.current = 0;
    setVoiceOpen(true);
    voiceTurn();
  }
  function closeVoice() {
    voiceRef.current = false;
    listenerRef.current?.cancel();
    stopSpeaking();
    setSpeakingId(null);
    setVoiceOpen(false);
    setVstate("idle");
  }
  function orbTap() {
    if (vstate === "listening") listenerRef.current?.stop();
    else if (vstate === "speaking") stopSpeaking(); // loop continues with listening
    else if (vstate === "idle") {
      failRef.current = 0;
      voiceTurn();
    }
  }

  // ---------- Meta extras: SAM 3.1 leaf measurement, Muse Image share card ----------
  async function runExtra(kind, run) {
    setExtra({ kind, loading: true, run });
    try {
      setExtra({ kind, data: await run(), run });
    } catch (e) {
      setExtra({ kind, error: e.message, run });
    }
  }
  const scanPhoto = () => photo?.file && runExtra("scan", () => leafScan(photo.file, ex(t.code).unavailable));
  const makeCard = (m) => runExtra("card", () => adviceCard(m.text, lang, profile.main_crop, ex(t.code).unavailable));

  // ---------- misc ----------
  function shareWhatsApp(m) {
    window.open("https://wa.me/?text=" + encodeURIComponent(`${t.title}\n\n${m.text}`), "_blank");
  }
  async function copyText(m) {
    try {
      await navigator.clipboard.writeText(m.text);
      setToast(t.copied);
    } catch { /* clipboard blocked */ }
  }
  function quick(q) {
    unlockAudio();
    if (q.text === "__photo__") return setShowAttach(true);
    send({ text: q.text });
  }
  async function installApp() {
    if (!installEvt) return;
    installEvt.prompt();
    try { await installEvt.userChoice; } catch { /* dismissed */ }
    setInstallEvt(null);
  }
  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    pickPhoto(e.dataTransfer.files?.[0]);
  }

  const lastBot = [...messages].reverse().find((m) => m.role === "bot" && m.text && !m.error);
  const vlabel = { listening: t.listening, thinking: t.thinking, speaking: t.speaking, idle: t.idle }[vstate];
  const canSend = !!(text.trim() || photo);

  return (
    <div
      className="app"
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={(e) => e.currentTarget === e.target && setDragging(false)}
      onDrop={onDrop}
    >
      {/* ---------- header ---------- */}
      <header className="top">
        <div className="brand">
          <span className="logo">🌾</span>
          <div>
            <h1>{t.title}</h1>
            <small>{t.tagline}</small>
          </div>
        </div>
        <div className="top-actions">
          <div className="seg" role="group" aria-label="Language">
            {LANGS.map((l) => (
              <button key={l.id} className={lang === l.id ? "on" : ""} onClick={() => setLang(l.id)}>{l.label}</button>
            ))}
          </div>
          <button className="icon-btn" aria-label={t.theme} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? <I.sun /> : <I.moon />}
          </button>
          <button className="icon-btn bell" aria-label={t.al.title} title={t.al.title} onClick={() => setShowAlerts(true)}>
            <I.bell />{Object.values(alertRes).some((x) => x.triggered) && <i className="dot" />}
          </button>
          <button className="icon-btn" aria-label={t.profile} onClick={() => setShowProfile(true)}><I.user /></button>
          {messages.length > 0 && <button className="icon-btn" aria-label={t.newChat} title={t.newChat} onClick={newChat}><I.plus /></button>}
        </div>
      </header>
      {!online && <div className="offline" role="status">📡 {t.offline}</div>}
      {Object.values(alertRes).filter((x) => x.triggered && !dismissed.includes(x.id)).map((x) => (
        <div className="alert-banner" role="status" key={x.id}>
          <span>{t.al.banner}: <b>{x.crop}</b> ₹{Number(x.current).toLocaleString("en-IN")} · {x.market || x.district} ({x.direction === "above" ? "≥" : "≤"} ₹{x.target.toLocaleString("en-IN")})</span>
          <button className="icon-btn sm" aria-label="Close" onClick={() => setDismissed((d) => [...d, x.id])}><I.x /></button>
        </div>
      ))}

      {/* ---------- conversation ---------- */}
      <main className="chat">
        {messages.length === 0 ? (
          <section className="welcome">
            <div className="hero-orb" aria-hidden="true">🌱</div>
            <h2>{t.hello}</h2>
            <p>{t.helloSub}</p>
            <button className="talk-cta" onClick={openVoice}>
              <span className="talk-ico"><I.wave /></span>
              <span><b>{t.talkBtn}</b><small>{t.talkSub}</small></span>
            </button>
            <button className="talk-cta today-cta" onClick={dailyBrief}>
              <span className="talk-ico">☀️</span>
              <span><b>{t.today}</b><small>{t.todaySub}</small></span>
            </button>
            {installEvt && <button className="pill" onClick={installApp}>{t.install}</button>}
            <h4>{t.tryAsk}</h4>
            <div className="quick">
              {t.quick.map((q) => (
                <button key={q.text} onClick={() => quick(q)}>
                  <span>{q.icon}</span>{q.label || q.text}
                </button>
              ))}
            </div>
          </section>
        ) : (
          <div className="thread">
            {messages.map((m) =>
              m.role === "user" ? (
                <div className="msg user" key={m.id}>
                  <div className="bubble">
                    {m.image && <img className="thumb" src={m.image} alt="" />}
                    {m.text && <p>{m.text}</p>}
                  </div>
                </div>
              ) : (
                <div className="msg bot" key={m.id}>
                  <span className="avatar">🌾</span>
                  <div className="bot-col">
                    {m.pending ? (
                      <LiveSteps live={m.live} t={t} />
                    ) : m.error ? (
                      <div className="bubble error">
                        <p>⚠️ {m.text}</p>
                        {m.retry && <button className="pill" onClick={() => retry(m)}>↻ {t.retry}</button>}
                      </div>
                    ) : (
                      <>
                        <div className="bubble"><Markdown text={m.text} /></div>
                        <ToolCards steps={m.steps} t={t} />
                        {m.verification && (
                          <p className={"verify " + (m.verification.passed ? "ok" : "warn")}>
                            {m.verification.passed ? "✓ " + t.verified : "⚠ " + t.unverified + (m.verification.unverified || []).join(", ")}
                          </p>
                        )}
                        <SourcesLine steps={m.steps} t={t} />
                        <StepChips steps={m.steps} t={t} />
                        <div className="actions">
                          <button className={"pill" + (speakingId === m.id ? " live" : "")} onClick={() => toggleSpeak(m)}>
                            {speakingId === m.id ? <I.stop width="16" height="16" /> : <I.speaker />}
                            {speakingId === m.id ? t.stopListen : t.listen}
                          </button>
                          <button className="pill" onClick={() => shareWhatsApp(m)}><I.whatsapp />{t.share}</button>
                          <button className="pill" onClick={() => copyText(m)}><I.copy />{t.copy}</button>
                          <button className="pill" onClick={() => makeCard(m)}>🖼️ {ex(t.code).cardBtn}</button>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )
            )}
            <div ref={endRef} />
          </div>
        )}
      </main>

      {/* ---------- composer ---------- */}
      <footer className="composer-wrap">
        {photo && (
          <div className="photo-prev">
            <img src={photo.url} alt="" />
            <span>{t.photo}</span>
            <button className="pill" onClick={scanPhoto}>🔬 {ex(t.code).scan}</button>
            <button className="icon-btn sm" aria-label={t.removePhoto} onClick={clearPhoto}><I.x /></button>
          </div>
        )}
        {showAttach && (
          <div className="attach-menu">
            <button onClick={() => camRef.current?.click()}><I.camera />{t.camera}</button>
            <button onClick={() => galRef.current?.click()}><I.image />{t.gallery}</button>
          </div>
        )}
        {rec === "recording" ? (
          <div className="composer recording">
            <button className="icon-btn" aria-label="Cancel" onClick={cancelRec}><I.x /></button>
            <div className="meter" ref={meterRef} aria-hidden="true">{Array.from({ length: 18 }).map((_, i) => <i key={i} style={{ "--k": (0.4 + 0.6 * Math.abs(Math.sin(i * 1.7))).toFixed(2) }} />)}</div>
            <span className="rec-label">{t.listening}</span>
            <button className="round stop" aria-label={t.tapStop} onClick={micToggle}><I.stop /></button>
          </div>
        ) : (
          <div className="composer">
            <button className={"icon-btn" + (showAttach ? " on" : "")} aria-label={t.photo} onClick={() => setShowAttach((s) => !s)}><I.camera /></button>
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), submit())}
              placeholder={photo ? t.photoPlaceholder : t.placeholder}
              disabled={busy}
              aria-label={t.placeholder}
            />
            {canSend ? (
              <button className="round" aria-label={t.send} onClick={submit} disabled={busy}><I.send /></button>
            ) : (
              <>
                <button className="icon-btn" aria-label={t.talkBtn} title={t.talkBtn} onClick={openVoice} disabled={busy}><I.wave /></button>
                <button className="round" aria-label={t.idle} onClick={micToggle} disabled={busy}><I.mic /></button>
              </>
            )}
          </div>
        )}
        <input ref={camRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { pickPhoto(e.target.files?.[0]); e.target.value = ""; }} />
        <input ref={galRef} type="file" accept="image/*" hidden onChange={(e) => { pickPhoto(e.target.files?.[0]); e.target.value = ""; }} />
      </footer>

      {/* ---------- hands-free voice conversation ---------- */}
      {voiceOpen && (
        <div className="voice" role="dialog" aria-modal="true">
          <button className="icon-btn voice-close" onClick={closeVoice} aria-label={t.closeVoice}><I.x /></button>
          <div className="voice-body">
            <button ref={orbRef} className={"orb " + vstate} onClick={orbTap} aria-label={vlabel}>
              <i className="ring r1" /><i className="ring r2" /><i className="ring r3" />
              <span className="core">{vstate === "speaking" ? <I.speaker width="44" height="44" /> : vstate === "thinking" ? <span className="spin" /> : <I.mic width="44" height="44" />}</span>
            </button>
            <h3>{vlabel}</h3>
            <p className="hint">
              {vstate === "listening" ? t.tapStop : vstate === "speaking" ? t.tapInterrupt : ""}
            </p>
            {vlive && <p className="live-text">“{vlive}”</p>}
            {lastBot && vstate !== "listening" && <div className="voice-answer"><Markdown text={lastBot.text} /></div>}
          </div>
          <button className="end-call" onClick={closeVoice}>{t.closeVoice}</button>
        </div>
      )}

      <ExtraSheet extra={extra} lang={t.code} onClose={() => setExtra(null)} onRetry={() => extra?.run && runExtra(extra.kind, extra.run)} />

      {/* ---------- price alerts sheet ---------- */}
      {showAlerts && (
        <div className="sheet-bg" onClick={() => setShowAlerts(false)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h3>🔔 {t.al.title}</h3>
            {alerts.length === 0 && <p className="hint">{t.al.empty}</p>}
            {alerts.map((a) => {
              const r = alertRes[a.id];
              const state = r?.triggered ? "reached" : r?.status === "waiting" ? "waiting" : r ? "off" : "";
              return (
                <div className={"alert-row " + state} key={a.id}>
                  <div>
                    <b>{a.crop}</b> · {a.district}
                    <small>{a.direction === "above" ? t.al.above : t.al.below} ₹{a.target.toLocaleString("en-IN")}
                      {r?.current != null && <> · {t.al.now} ₹{Number(r.current).toLocaleString("en-IN")}{r.live ? "" : ` (${t.al.notLive})`}</>}
                    </small>
                  </div>
                  <span className="alert-state">{r?.triggered ? "✅ " + t.al.reached : r?.status === "waiting" ? "⏳ " + t.al.waiting : ""}</span>
                  <button className="icon-btn sm" aria-label={t.al.remove} onClick={() => setAlerts((l) => l.filter((x) => x.id !== a.id))}><I.x /></button>
                </div>
              );
            })}
            {alerts.length < 5 && (
              <>
                <label>{t.al.crop}<input value={draft.crop} onChange={(e) => setDraft({ ...draft, crop: e.target.value })} placeholder={profile.main_crop || "Groundnut"} /></label>
                <div className="alert-form">
                  <select value={draft.direction} onChange={(e) => setDraft({ ...draft, direction: e.target.value })} aria-label="direction">
                    <option value="above">{t.al.above}</option>
                    <option value="below">{t.al.below}</option>
                  </select>
                  <input type="number" inputMode="numeric" min="1" value={draft.target} onChange={(e) => setDraft({ ...draft, target: e.target.value })} placeholder="₹ / quintal" aria-label={t.al.target} />
                </div>
                <button className="primary" onClick={addAlert}>＋ {t.al.add}</button>
              </>
            )}
            <p className="hint">{t.al.liveOnly}</p>
            <div className="alert-actions">
              {alerts.length > 0 && <button className="pill" onClick={() => checkAlerts(true)}>↻ {t.al.check}</button>}
              {"Notification" in window && window.Notification.permission === "default" && <button className="pill" onClick={enableNotifications}>🔔 {t.al.notifyOn}</button>}
            </div>
            <button className="primary" onClick={() => setShowAlerts(false)}>{t.save}</button>
          </div>
        </div>
      )}

      {/* ---------- profile sheet ---------- */}
      {showProfile && (
        <div className="sheet-bg" onClick={() => setShowProfile(false)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h3>{t.profile}</h3>
            <label>{t.state}<input value={profile.state} onChange={(e) => setProfile({ ...profile, state: e.target.value })} /></label>
            <label>{t.district}<input value={profile.district} onChange={(e) => setProfile({ ...profile, district: e.target.value })} placeholder="Kurnool" /></label>
            <label>{t.crop}<input value={profile.main_crop} onChange={(e) => setProfile({ ...profile, main_crop: e.target.value })} placeholder="Groundnut" /></label>
            <label className="check"><input type="checkbox" checked={profile.owns_land} onChange={(e) => setProfile({ ...profile, owns_land: e.target.checked })} />{t.land}</label>
            <label className="check"><input type="checkbox" checked={big} onChange={(e) => setBig(e.target.checked)} />{t.bigText}</label>
            <label className="check"><input type="checkbox" checked={autoSpeak} onChange={(e) => setAutoSpeak(e.target.checked)} />{t.autoSpeak}</label>
            <button className="primary" onClick={() => setShowProfile(false)}>{t.save}</button>
          </div>
        </div>
      )}

      {dragging && <div className="drop">📷 {t.dropHere}</div>}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}
