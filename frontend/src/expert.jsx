// Expert escalation: one structured case (symptoms + SAM scan + weather + crop profile) shared with a human expert.
// The case history and the photo stay on the phone; details are sent only after the farmer ticks consent.
import { useEffect, useState } from "react";
import { I } from "./components";
import { Sheet, shareText } from "./khata";
import { getLastScan } from "./extras";

const SYM = ["spots_on_leaves", "yellowing", "wilting", "holes_or_chewed", "spreading_fast", "whole_field", "after_rain", "insects_seen", "mould_or_powder", "stunted"];
const S = {
  en: { title: "Ask an expert", sub: "Send a clear case", what: "What do you see?", note: "Anything else? (optional)", c1: "Share my crop and growth stage", c2: "Share my place (for weather)", c3: "I will send the photo too",
        build: "Prepare case", rebuild: "Update case", urg: { high: "High urgency", medium: "Medium urgency", low: "Low urgency" }, send: "Send", copy: "Copy", copied: "Copied", share: "Share photo and case", close: "Close",
        configured: "Your experts", fallback: "No expert is set up. Show this case to your local agriculture extension office:", history: "Earlier cases", status: { open: "Open", answered: "Answered", closed: "Closed" }, reply: "Expert's reply (note)", scan: "Using your last leaf scan", noscan: "Tip: scan a leaf first to add the measurement.", fail: "Could not prepare the case. Check the connection.", consent: "Tick the first box to continue." },
  te: { title: "నిపుణుడిని అడగండి", sub: "స్పష్టమైన కేసు పంపండి", what: "మీకు ఏమి కనిపిస్తోంది?", note: "ఇంకేమైనా? (ఐచ్ఛికం)", c1: "నా పంట, ఎదుగుదల దశ పంచుకోండి", c2: "నా ప్రదేశం పంచుకోండి (వాతావరణం కోసం)", c3: "ఫోటో కూడా నేను పంపుతాను",
        build: "కేసు సిద్ధం చేయి", rebuild: "కేసు నవీకరించు", urg: { high: "ఎక్కువ అత్యవసరం", medium: "మధ్యస్థ అత్యవసరం", low: "తక్కువ అత్యవసరం" }, send: "పంపండి", copy: "కాపీ", copied: "కాపీ అయింది", share: "ఫోటో, కేసు పంచుకోండి", close: "మూసివేయి",
        configured: "మీ నిపుణులు", fallback: "నిపుణుడు సెట్ కాలేదు. ఈ కేసును మీ స్థానిక వ్యవసాయ అధికారికి చూపండి:", history: "గత కేసులు", status: { open: "తెరిచి ఉంది", answered: "సమాధానం వచ్చింది", closed: "ముగిసింది" }, reply: "నిపుణుడి సమాధానం (నోట్)", scan: "మీ చివరి ఆకు స్కాన్ వాడుతున్నాం", noscan: "సూచన: కొలత కోసం ముందు ఆకు స్కాన్ చేయండి.", fail: "కేసు సిద్ధం కాలేదు. కనెక్షన్ చూడండి.", consent: "కొనసాగడానికి మొదటి బాక్స్ టిక్ చేయండి." },
  hi: { title: "विशेषज्ञ से पूछें", sub: "साफ़ केस भेजें", what: "आपको क्या दिख रहा है?", note: "और कुछ? (वैकल्पिक)", c1: "मेरी फसल और बढ़वार का चरण साझा करें", c2: "मेरी जगह साझा करें (मौसम के लिए)", c3: "फ़ोटो भी मैं भेजूँगा",
        build: "केस तैयार करें", rebuild: "केस अपडेट करें", urg: { high: "ज़्यादा तात्कालिक", medium: "मध्यम तात्कालिक", low: "कम तात्कालिक" }, send: "भेजें", copy: "कॉपी", copied: "कॉपी हो गया", share: "फ़ोटो और केस साझा करें", close: "बंद करें",
        configured: "आपके विशेषज्ञ", fallback: "कोई विशेषज्ञ सेट नहीं है। यह केस अपने स्थानीय कृषि अधिकारी को दिखाएँ:", history: "पुराने केस", status: { open: "खुला", answered: "जवाब मिला", closed: "बंद" }, reply: "विशेषज्ञ का जवाब (नोट)", scan: "आपका पिछला पत्ती स्कैन इस्तेमाल हो रहा है", noscan: "सुझाव: माप जोड़ने के लिए पहले पत्ती स्कैन करें।", fail: "केस तैयार नहीं हो सका। कनेक्शन देखें।", consent: "आगे बढ़ने के लिए पहला बॉक्स टिक करें।" },
};
export const ax = (lang) => S[lang] || S.en;
const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };
const KEY = "km-cases";

export function CaseSheet({ lang, profile, onClose, toast }) {
  const t = ax(lang);
  const l = lang === "auto" ? "te" : lang;
  const scan = getLastScan();
  const [syms, setSyms] = useState([]);
  const [note, setNote] = useState("");
  const [cons, setCons] = useState({ share_details: true, share_location: false, share_photo: !!scan });
  const [cs, setCs] = useState(null);
  const [contacts, setContacts] = useState(null);
  const [hist, setHist] = useState(() => load(KEY, []));
  const [err, setErr] = useState("");
  useEffect(() => { fetch("/api/expert/contacts?" + new URLSearchParams({ lang: l, country: profile.country || "" })).then((r) => r.json()).then((j) => setContacts((c) => c || { labels: j.labels, experts: [] })).catch(() => {}); }, [l]);
  const toggle = (s) => setSyms((a) => (a.includes(s) ? a.filter((x) => x !== s) : [...a, s]));

  async function build() {
    setErr("");
    if (!cons.share_details) return setErr(t.consent);
    try {
      const r = await fetch("/api/case/build", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        lang: l, symptoms: syms, note, consent: cons, profile: { crop: profile.main_crop, country: profile.country, place: profile.district, sowing_date: profile.sowing_date },
        scan: scan ? { ...scan.data, severity_pct: scan.data.severity_pct } : {} }) });
      if (!r.ok) throw new Error();
      const c = await r.json();
      setCs(c);
      const q = new URLSearchParams({ lang: l, country: profile.country || "", text: c.summary_text });
      setContacts(await (await fetch("/api/expert/contacts?" + q)).json());
      const next = [{ id: c.id, at: c.created_at, urgency: c.urgency, crop: c.farmer.crop, text: c.summary_text, status: "open", reply: "" }, ...hist.filter((h) => h.id !== c.id)].slice(0, 20);
      setHist(next); save(KEY, next);
    } catch { setErr(t.fail); }
  }
  function sharePhoto() {
    const f = scan?.file;
    if (f && navigator.canShare?.({ files: [f] })) navigator.share({ files: [f], text: cs.summary_text }).catch(() => {});
    else shareText(cs.summary_text);
  }
  function upd(id, patch) { const n = hist.map((h) => (h.id === id ? { ...h, ...patch } : h)); setHist(n); save(KEY, n); }

  return (
    <Sheet title={"🧑‍🌾 " + t.title} onClose={onClose} close={t.close}>
      <p className="hint">{scan ? "📷 " + t.scan : t.noscan}</p>
      <h5>{t.what}</h5>
      <div className="chips">{SYM.map((s) => <label key={s} className="pill chip"><input type="checkbox" checked={syms.includes(s)} onChange={() => toggle(s)} /> {contacts?.labels?.symptoms?.[s] || s.replace(/_/g, " ")}</label>)}</div>
      <textarea value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} placeholder={t.note} aria-label={t.note} rows={2} />
      <label className="check"><input type="checkbox" checked={cons.share_details} onChange={(e) => setCons({ ...cons, share_details: e.target.checked })} /> {t.c1}</label>
      <label className="check"><input type="checkbox" checked={cons.share_location} onChange={(e) => setCons({ ...cons, share_location: e.target.checked })} /> {t.c2}</label>
      {scan && <label className="check"><input type="checkbox" checked={cons.share_photo} onChange={(e) => setCons({ ...cons, share_photo: e.target.checked })} /> {t.c3}</label>}
      <button className="primary" onClick={build}>{cs ? t.rebuild : t.build}</button>
      {err && <p className="warn-note">{err}</p>}
      {cs && (
        <div className="claim-out">
          <div className={"decision " + (cs.urgency === "high" ? "falling" : cs.urgency === "medium" ? "steady" : "rising")}><b>{t.urg[cs.urgency]}</b></div>
          <pre className="claim-msg">{cs.summary_text}</pre>
          {contacts?.configured ? <><h5>{t.configured}</h5><div className="alert-actions">{contacts.experts.map((e) => <a key={e.name} className="pill" href={e.link} target="_blank" rel="noreferrer">{e.type === "email" ? "✉️" : e.type === "phone" ? "📞" : <I.whatsapp />} {e.name}</a>)}</div></>
            : <p className="hint">{t.fallback} {contacts?.fallback?.local} {contacts?.fallback?.kisan_call_centre && <a href={"tel:" + contacts.fallback.kisan_call_centre.replace(/-/g, "")}>☎️ {contacts.fallback.kisan_call_centre}</a>}</p>}
          <div className="alert-actions">
            <button className="pill" onClick={sharePhoto}><I.whatsapp />{cons.share_photo && scan ? t.share : t.send}</button>
            <button className="pill" onClick={() => navigator.clipboard?.writeText(cs.summary_text).then(() => toast(t.copied))}><I.copy />{t.copy}</button>
          </div>
        </div>
      )}
      {hist.length > 0 && <><h5>{t.history}</h5>
        {hist.map((h) => (
          <div key={h.id} className="khata-row" style={{ display: "block" }}>
            <b>{h.id}</b> · {h.crop || "-"} · {t.urg[h.urgency]} · {new Date(h.at).toLocaleDateString()}
            <select value={h.status} onChange={(e) => upd(h.id, { status: e.target.value })}>{Object.keys(t.status).map((k) => <option key={k} value={k}>{t.status[k]}</option>)}</select>
            <input value={h.reply} onChange={(e) => upd(h.id, { reply: e.target.value })} placeholder={t.reply} aria-label={t.reply} />
          </div>
        ))}</>}
    </Sheet>
  );
}
