// Agent controls on the phone: (1) confirm-before-action cards for anything the assistant offers to do, (2) "My farm memory":
// facts the farmer chooses to keep, sent with questions ONLY while memory is switched on. All stored on the device.
import { useState } from "react";
import { Sheet } from "./khata";

const S = {
  en: { yes: "Yes, do it", no: "No", saved: "Saved", skipped: "Skipped", mem: "My farm memory", memSub: "What I remember", on: "Remember my farm facts to personalise answers", off: "Memory is off: nothing is sent.",
        fill: "Fill from my profile and field", add: "Add a fact", ph: "For example: I use flood irrigation", forget: "Forget everything", close: "Close", note: "These notes are sent with your questions only while memory is on. They are never treated as instructions, and the server does not store them.", none: "No facts yet.", remove: "Remove", offered: "Offered, needs your OK", alertSet: "Alert set" },
  te: { yes: "అవును, చేయి", no: "వద్దు", saved: "సేవ్ అయింది", skipped: "వదిలేశాం", mem: "నా పొలం జ్ఞాపకం", memSub: "నేను గుర్తుంచుకునేవి", on: "జవాబులు మీకు తగ్గట్టు ఉండేందుకు నా పొలం వివరాలు గుర్తుంచుకో", off: "జ్ఞాపకం ఆఫ్: ఏమీ పంపబడదు.",
        fill: "నా ప్రొఫైల్, పొలం నుండి నింపు", add: "వివరం చేర్చు", ph: "ఉదా: నేను పారు నీటి తడి వాడతాను", forget: "అన్నీ మర్చిపో", close: "మూసివేయి", note: "ఈ గమనికలు జ్ఞాపకం ఆన్ లో ఉన్నప్పుడే మీ ప్రశ్నలతో వెళ్తాయి. వీటిని ఆదేశాలుగా తీసుకోరు, సర్వర్ వీటిని దాచదు.", none: "ఇంకా వివరాలు లేవు.", remove: "తొలగించు", offered: "ప్రతిపాదన, మీ అనుమతి కావాలి", alertSet: "అలర్ట్ సెట్ అయింది" },
  hi: { yes: "हाँ, करो", no: "नहीं", saved: "सेव हो गया", skipped: "छोड़ दिया", mem: "मेरे खेत की याद", memSub: "मैं क्या याद रखता हूँ", on: "जवाब आपके अनुसार बनाने के लिए मेरे खेत की बातें याद रखें", off: "याद बंद है: कुछ नहीं भेजा जाता।",
        fill: "मेरी प्रोफ़ाइल और खेत से भरें", add: "बात जोड़ें", ph: "जैसे: मैं बाढ़ सिंचाई करता हूँ", forget: "सब भूल जाओ", close: "बंद करें", note: "ये नोट केवल याद चालू रहने पर आपके सवालों के साथ जाते हैं। इन्हें आदेश नहीं माना जाता, और सर्वर इन्हें सहेजता नहीं।", none: "अभी कोई बात नहीं।", remove: "हटाएँ", offered: "सुझाव, आपकी मंज़ूरी चाहिए", alertSet: "अलर्ट लग गया" },
};
export const au = (lang) => S[lang] || S.en;
const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };

// Farm voice memory: while memory is ON, the last few questions and saved decisions go along as short quoted notes (never instructions).
export function rememberTurn(question) {
  if (!load("km-memory-on", false)) return;
  const q = String(question || "").trim().slice(0, 90);
  if (q) save("km-convo", [...load("km-convo", []), { date: new Date().toISOString().slice(0, 10), q }].slice(-10));
}

export function getMemoryPayload() {
  if (!load("km-memory-on", false)) return {};
  const facts = load("km-memory", []).slice(0, 6);
  const convo = load("km-convo", []).slice(-3).map((c) => `Asked on ${c.date}: ${c.q}`);
  const decisions = load("km-outcomes", []).slice(0, 3).map((o) => `Saved on ${o.date}: ${String(o.text || "").slice(0, 70)} (followed: ${o.done ? "yes" : "not yet"})${o.followup_note ? " - " + String(o.followup_note).slice(0, 40) : ""}`);
  const all = [...facts, ...decisions, ...convo].slice(0, 12);
  return all.length ? { memory_consent: true, memory: all } : {};
}

// Runs an accepted proposal on the device. Returns a short status key.
export function applyAction(a, setAlerts) {
  if (a.type === "log_recommendation") {
    const list = load("km-outcomes", []);
    save("km-outcomes", [{ id: Math.random().toString(36).slice(2, 9), date: new Date().toISOString().slice(0, 10), text: a.payload.text, kind: a.payload.kind, crop: a.payload.crop || "", done: false, useful: null, predicted: {}, actual: {} }, ...list].slice(0, 200));
    return "saved";
  }
  if (a.type === "set_price_alert") {
    setAlerts((l) => [...l, { id: Math.random().toString(36).slice(2, 9), crop: a.payload.crop, district: a.payload.district, target: a.payload.target, direction: a.payload.direction }].slice(-5));
    return "alertSet";
  }
  return "skipped";
}

export function ActionCards({ lang, actions, done, onChoose }) {
  const t = au(lang);
  if (!actions?.length) return null;
  return (
    <div className="actions-confirm">
      {actions.map((a) => (
        <div key={a.id} className="decision steady" style={{ display: "block" }}>
          <small className="hint">🔒 {t.offered}</small>
          <p>{a.label}</p>
          {done?.[a.id] ? <b>{t[done[a.id]] || t.saved}</b> : (
            <div className="alert-actions"><button className="pill" onClick={() => onChoose(a, true)}>{t.yes}</button><button className="pill" onClick={() => onChoose(a, false)}>{t.no}</button></div>
          )}
        </div>
      ))}
    </div>
  );
}

export function MemorySheet({ lang, profile, onClose }) {
  const t = au(lang);
  const [on, setOn] = useState(() => load("km-memory-on", false));
  const [facts, setFacts] = useState(() => load("km-memory", []));
  const [txt, setTxt] = useState("");
  const commit = (n) => { setFacts(n); save("km-memory", n); };
  const toggle = (v) => { setOn(v); save("km-memory-on", v); };

  function fill() {
    const tw = load("km-twin", {}) || {};
    const out = load("km-outcomes", []);
    const f = [];
    const crop = tw.crop || profile.main_crop;
    if (crop) f.push(`Main crop: ${crop}${tw.variety ? " (" + tw.variety + ")" : ""}`);
    if (tw.acres) f.push(`Field area: ${tw.acres} acres`);
    if (tw.soil) f.push(`Soil: ${tw.soil}`);
    if (tw.sowing_date || profile.sowing_date) f.push(`Sown on ${tw.sowing_date || profile.sowing_date}`);
    if (profile.district) f.push(`Place: ${profile.district}`);
    if (out.length) f.push(`Followed ${out.filter((o) => o.done).length} of ${out.length} saved recommendations`);
    commit([...new Set([...facts, ...f])].slice(0, 12));
  }
  return (
    <Sheet title={"🧠 " + t.mem} onClose={onClose} close={t.close}>
      <label className="check"><input type="checkbox" checked={on} onChange={(e) => toggle(e.target.checked)} /> {t.on}</label>
      {!on && <p className="hint">{t.off}</p>}
      <p className="hint">{t.note}</p>
      <button className="pill" onClick={fill}>{t.fill}</button>
      {!facts.length && <p className="hint">{t.none}</p>}
      <ul className="plain">{facts.map((f, i) => <li key={i}>{f} <button className="pill" onClick={() => commit(facts.filter((_, j) => j !== i))}>{t.remove}</button></li>)}</ul>
      <input value={txt} maxLength={120} onChange={(e) => setTxt(e.target.value)} placeholder={t.ph} aria-label={t.add} />
      <button className="pill" onClick={() => { if (txt.trim()) { commit([...facts, txt.trim()].slice(0, 12)); setTxt(""); } }}>{t.add}</button>
      <button className="pill" onClick={() => commit([])}>🗑️ {t.forget}</button>
    </Sheet>
  );
}
