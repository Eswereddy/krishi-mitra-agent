// Krishi Machine Guardian: record ~10 s of an engine, compare with this machine's own saved healthy recording, see what changed.
// Audio is turned into 8 kHz mono on the phone and sent only for analysis; the server keeps nothing. Only measured features are saved here as the baseline.
import { useRef, useState } from "react";
import { Sheet } from "./khata";

const MACHINES = ["tractor", "harvester", "pump", "other"];
const SYMS = ["smoke_black", "smoke_white_blue", "overheating", "oil_light", "loss_of_power", "hard_start", "vibration", "burning_smell", "leak", "grinding"];
const S = {
  en: { title: "Machine Guardian", sub: "Listen to the engine", tip: "Stand safely at arm's length from the engine, never near belts or shafts. Hold the phone steady, same spot and same engine speed each time, 10 seconds.",
        machine: { tractor: "Tractor", harvester: "Harvester", pump: "Pump engine", other: "Other engine" }, sym: "Anything else you notice? (tick)",
        symt: { smoke_black: "Black smoke", smoke_white_blue: "White or blue smoke", overheating: "Overheating", oil_light: "Oil pressure warning", loss_of_power: "Loss of power", hard_start: "Hard to start", vibration: "Strong vibration", burning_smell: "Burning smell", leak: "Leak", grinding: "Grinding noise" },
        rec: "Record 10 s", stop: "Recording…", file: "Or choose an audio file", base: "Healthy baseline for this machine", none: "None saved yet. Record while the machine runs well, then save it.", saved: "Saved", save: "Save this as healthy baseline", del: "Delete baseline",
        poss: "Possible causes (not a diagnosis)", chk: "Safe checks (engine off, cool)", meas: "Measurements", fail: "Could not analyse. Try again.", mic: "Microphone not available. Choose an audio file instead.", close: "Close", rate: "engine rate", unv: "Not validated on real machines" },
  te: { title: "మెషిన్ గార్డియన్", sub: "ఇంజిన్ శబ్దం వినండి", tip: "ఇంజిన్ నుంచి చేయి దూరంలో సురక్షితంగా నిలబడండి, బెల్టులు/షాఫ్ట్‌ల దగ్గర కాదు. ఫోన్‌ను స్థిరంగా పట్టండి, ప్రతిసారీ అదే చోటు, అదే ఇంజిన్ వేగం, 10 సెకన్లు.",
        machine: { tractor: "ట్రాక్టర్", harvester: "హార్వెస్టర్", pump: "పంపు ఇంజిన్", other: "ఇతర ఇంజిన్" }, sym: "ఇంకేమైనా గమనించారా? (టిక్ చేయండి)",
        symt: { smoke_black: "నల్లని పొగ", smoke_white_blue: "తెల్లని/నీలి పొగ", overheating: "వేడెక్కడం", oil_light: "ఆయిల్ ప్రెషర్ హెచ్చరిక", loss_of_power: "శక్తి తగ్గడం", hard_start: "స్టార్ట్ కష్టం", vibration: "ఎక్కువ కంపనం", burning_smell: "కాలిన వాసన", leak: "లీకేజ్", grinding: "రాపిడి శబ్దం" },
        rec: "10 సెకన్లు రికార్డ్", stop: "రికార్డ్ అవుతోంది…", file: "లేదా ఆడియో ఫైల్ ఎంచుకోండి", base: "ఈ యంత్రం యొక్క ఆరోగ్యకర బేస్‌లైన్", none: "ఇంకా సేవ్ చేయలేదు. యంత్రం బాగా నడుస్తున్నప్పుడు రికార్డ్ చేసి సేవ్ చేయండి.", saved: "సేవ్ అయింది", save: "దీన్ని ఆరోగ్యకర బేస్‌లైన్‌గా సేవ్ చేయి", del: "బేస్‌లైన్ తొలగించు",
        poss: "సాధ్యమైన కారణాలు (నిర్ధారణ కాదు)", chk: "సురక్షిత తనిఖీలు (ఇంజిన్ ఆపి, చల్లారాక)", meas: "కొలతలు", fail: "విశ్లేషణ కాలేదు. మళ్లీ ప్రయత్నించండి.", mic: "మైక్రోఫోన్ అందుబాటులో లేదు. ఆడియో ఫైల్ ఎంచుకోండి.", close: "మూసివేయి", rate: "ఇంజిన్ రేటు", unv: "నిజమైన యంత్రాలపై ధృవీకరించలేదు" },
  hi: { title: "मशीन गार्डियन", sub: "इंजन की आवाज़ सुनें", tip: "इंजन से हाथ भर दूर सुरक्षित खड़े हों, बेल्ट या शाफ्ट के पास नहीं। फ़ोन स्थिर पकड़ें, हर बार वही जगह और वही इंजन गति, 10 सेकंड।",
        machine: { tractor: "ट्रैक्टर", harvester: "हार्वेस्टर", pump: "पंप इंजन", other: "अन्य इंजन" }, sym: "कुछ और दिखा? (टिक करें)",
        symt: { smoke_black: "काला धुआँ", smoke_white_blue: "सफ़ेद/नीला धुआँ", overheating: "गरम होना", oil_light: "ऑयल प्रेशर चेतावनी", loss_of_power: "ताक़त घटना", hard_start: "स्टार्ट में दिक्कत", vibration: "तेज़ कंपन", burning_smell: "जलने की गंध", leak: "रिसाव", grinding: "घिसने की आवाज़" },
        rec: "10 सेकंड रिकॉर्ड", stop: "रिकॉर्ड हो रहा है…", file: "या ऑडियो फ़ाइल चुनें", base: "इस मशीन की स्वस्थ बेसलाइन", none: "अभी कोई सहेजी नहीं। मशीन ठीक चलते समय रिकॉर्ड करके सहेजें।", saved: "सहेजा गया", save: "इसे स्वस्थ बेसलाइन के रूप में सहेजें", del: "बेसलाइन हटाएँ",
        poss: "संभावित कारण (निदान नहीं)", chk: "सुरक्षित जाँच (इंजन बंद, ठंडा)", meas: "माप", fail: "विश्लेषण नहीं हो सका। फिर कोशिश करें।", mic: "माइक्रोफ़ोन उपलब्ध नहीं। ऑडियो फ़ाइल चुनें।", close: "बंद करें", rate: "इंजन दर", unv: "असली मशीनों पर परखा नहीं गया" },
};
export const gd = (lang) => S[lang] || S.en;
const KEY = "km-guardian";
const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } };
const store = (v) => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch { /* storage unavailable */ } };
const COLOR = { stop_now: "#c62828", soon: "#e65100", monitor: "#a86f00", ok: "#2e7d32", bad: "#616161" };

// any browser-decodable audio -> raw little-endian int16, 8 kHz, mono
async function toPcm(buf) {
  const AC = window.AudioContext || window.webkitAudioContext;
  const ctx = new AC();
  const a = await ctx.decodeAudioData(buf.slice(0));
  ctx.close && ctx.close();
  const secs = Math.min(a.duration, 20);
  const off = new OfflineAudioContext(1, Math.max(1, Math.floor(secs * 8000)), 8000);
  const src = off.createBufferSource(); src.buffer = a; src.connect(off.destination); src.start();
  const r = (await off.startRendering()).getChannelData(0);
  const out = new Int16Array(r.length);
  for (let i = 0; i < r.length; i++) out[i] = Math.max(-1, Math.min(1, r[i])) * 32767;
  return new Blob([out.buffer]);
}

export function GuardianSheet({ lang, onClose }) {
  const t = gd(lang);
  const [machine, setMachine] = useState("tractor");
  const [syms, setSyms] = useState([]);
  const [saved, setSaved] = useState(load);
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [rec, setRec] = useState(false);
  const [err, setErr] = useState("");
  const fileRef = useRef(null);
  const base = saved[machine] || null;

  async function analyse(blob) {
    setBusy(true); setErr("");
    try {
      const pcm = await toPcm(await blob.arrayBuffer());
      const fd = new FormData();
      fd.append("pcm", pcm, "a.pcm"); fd.append("machine", machine); fd.append("symptoms", JSON.stringify(syms)); fd.append("lang", lang);
      if (base) fd.append("baseline", JSON.stringify(base.features));
      const r = await fetch("/api/guardian/analyze", { method: "POST", body: fd });
      if (!r.ok) throw new Error();
      setRes(await r.json());
    } catch { setErr(t.fail); }
    setBusy(false);
  }
  async function record() {
    setErr("");
    try {
      const st = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
      const mr = new MediaRecorder(st), chunks = [];
      mr.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      mr.onstop = () => { st.getTracks().forEach((x) => x.stop()); setRec(false); analyse(new Blob(chunks, { type: mr.mimeType })); };
      mr.start(); setRec(true); setTimeout(() => mr.state !== "inactive" && mr.stop(), 10000);
    } catch { setErr(t.mic); }
  }
  const tick = (c) => setSyms((s) => (s.includes(c) ? s.filter((x) => x !== c) : [...s, c]));
  const saveBase = () => { const n = { ...saved, [machine]: { features: res.features, date: new Date().toISOString().slice(0, 10) } }; setSaved(n); store(n); };
  const delBase = () => { const n = { ...saved }; delete n[machine]; setSaved(n); store(n); };

  return (
    <Sheet title={"🔊 " + t.title} onClose={onClose} close={t.close}>
      <p className="hint">{t.tip}</p>
      <label>{t.title}<select value={machine} onChange={(e) => { setMachine(e.target.value); setRes(null); }}>{MACHINES.map((m) => <option key={m} value={m}>{t.machine[m]}</option>)}</select></label>
      <h5>{t.base}</h5>
      <p className="hint">{base ? "✅ " + base.date + (base.features.f0_hz ? " · " + t.rate + " " + base.features.f0_hz + " Hz" : "") : t.none}</p>
      {base && <button className="pill" onClick={delBase}>{t.del}</button>}
      <h5>{t.sym}</h5>
      {SYMS.map((c) => <label key={c} className="check"><input type="checkbox" checked={syms.includes(c)} onChange={() => tick(c)} />{t.symt[c]}</label>)}
      <div className="alert-form">
        <button className="primary" onClick={record} disabled={busy || rec}>{rec ? t.stop : busy ? "…" : "🎙️ " + t.rec}</button>
        <button className="pill" onClick={() => fileRef.current.click()} disabled={busy || rec}>{t.file}</button>
        <input ref={fileRef} type="file" accept="audio/*" hidden data-testid="guardian-file" onChange={(e) => { const f = e.target.files[0]; e.target.value = ""; f && analyse(f); }} />
      </div>
      {err && <p className="hint">{err}</p>}
      {res && (
        <div id="guardian-result">
          <div className="decision" style={{ textAlign: "left", borderLeft: "6px solid " + (COLOR[res.level] || "#616161") }}><b>{res.title}</b><small style={{ display: "block", marginTop: 4 }}>{res.advice}</small></div>
          {res.state_note && <p className="hint">{res.state_note}</p>}
          {res.recording_notes.map((n, i) => <p key={i} className="hint">⚠️ {n}</p>)}
          {res.symptoms.length > 0 && <p className="hint">{res.symptoms.map((s) => s.text).join(" · ")}</p>}
          {res.patterns.map((p) => (
            <div key={p.code} className="decision" style={{ textAlign: "left", borderLeft: "6px solid #a86f00" }}>
              <b>{p.title}</b>
              <small style={{ display: "block", marginTop: 4 }}>{t.poss}</small>
              <ul className="plain">{p.possible_causes.map((x, i) => <li key={i}>{x}</li>)}</ul>
              <small>{t.chk}</small>
              <ul className="plain">{p.checks.map((x, i) => <li key={i}>{x}</li>)}</ul>
            </div>
          ))}
          <p className="hint">{res.mechanic}</p>
          {res.measurements && <small className="hint">{t.meas}: {t.rate} {res.measurements.f0_hz ?? "—"} Hz · {res.measurements.seconds}s</small>}
          {res.features && !res.recording_notes.length && res.state !== "bad" && <div><button className="pill" onClick={saveBase}>{t.save}</button></div>}
          <p className="hint">{res.note}</p><p className="hint"><b>{t.unv}</b></p>
        </div>
      )}
    </Sheet>
  );
}
