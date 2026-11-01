// Outcome tracking: log a recommendation, mark it done, enter what really happened, see predicted vs actual.
// Records stay on the phone; the server only does the arithmetic for the report.
import { useState } from "react";
import { Sheet, shareText } from "./khata";

const KINDS = ["irrigate", "sow", "fertilise", "protect", "harvest", "sell", "store", "other"];
const S = {
  en: { title: "My results", sub: "Did advice help?", add: "Add recommendation", what: "What was advised?", kind: { irrigate: "Irrigate", sow: "Sow", fertilise: "Fertilise", protect: "Protect", harvest: "Harvest", sell: "Sell", store: "Store", other: "Other" },
        pe: "Expected cost", py: "Expected yield (kg)", pp: "Expected price/kg", save: "Save", done: "Mark done", ae: "Actual cost", ay: "Actual yield (kg)", ap: "Actual price/kg", useful: "Was it useful?", yes: "👍 Yes", no: "👎 No",
        report: "Season report", share: "Share", close: "Close", list: "Recommendations", empty: "Nothing logged yet.", del: "Remove", doneL: "Done", offline: "Report needs a connection." },
  te: { title: "నా ఫలితాలు", sub: "సలహా పనిచేసిందా?", add: "సూచన చేర్చండి", what: "ఏమి సూచించారు?", kind: { irrigate: "నీరు", sow: "విత్తనం", fertilise: "ఎరువు", protect: "పంట రక్షణ", harvest: "కోత", sell: "అమ్మకం", store: "నిల్వ", other: "ఇతరం" },
        pe: "అంచనా ఖర్చు", py: "అంచనా దిగుబడి (కిలో)", pp: "అంచనా ధర/కిలో", save: "సేవ్", done: "పూర్తయింది", ae: "వాస్తవ ఖర్చు", ay: "వాస్తవ దిగుబడి (కిలో)", ap: "వాస్తవ ధర/కిలో", useful: "ఉపయోగపడిందా?", yes: "👍 అవును", no: "👎 కాదు",
        report: "సీజన్ నివేదిక", share: "పంచుకో", close: "మూసివేయి", list: "సూచనలు", empty: "ఇంకా ఏమీ లేదు.", del: "తొలగించు", doneL: "పూర్తి", offline: "నివేదికకు ఇంటర్నెట్ కావాలి." },
  hi: { title: "मेरे नतीजे", sub: "क्या सलाह काम आई?", add: "सुझाव जोड़ें", what: "क्या सुझाव मिला?", kind: { irrigate: "सिंचाई", sow: "बुवाई", fertilise: "खाद", protect: "फसल सुरक्षा", harvest: "कटाई", sell: "बिक्री", store: "भंडारण", other: "अन्य" },
        pe: "अनुमानित खर्च", py: "अनुमानित उपज (किलो)", pp: "अनुमानित कीमत/किलो", save: "सेव", done: "हो गया", ae: "असली खर्च", ay: "असली उपज (किलो)", ap: "असली कीमत/किलो", useful: "क्या उपयोगी रहा?", yes: "👍 हाँ", no: "👎 नहीं",
        report: "सीज़न रिपोर्ट", share: "साझा करें", close: "बंद करें", list: "सुझाव", empty: "अभी कुछ नहीं।", del: "हटाएँ", doneL: "पूरा", offline: "रिपोर्ट के लिए इंटरनेट चाहिए।" },
};
export const ox = (lang) => S[lang] || S.en;
const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };
const KEY = "km-outcomes";
const nums = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== "" && v != null && !Number.isNaN(Number(v))).map(([k, v]) => [k, Number(v)]));

export function OutcomesSheet({ lang, profile, seed, onClose }) {
  const t = ox(lang);
  const l = lang === "auto" ? "te" : lang;
  const [recs, setRecs] = useState(() => load(KEY, []));
  const [form, setForm] = useState({ text: seed || "", kind: "other", expense: "", yield_kg: "", price_per_kg: "" });
  const [open, setOpen] = useState(null);
  const [act, setAct] = useState({});
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState("");
  const commit = (n) => { setRecs(n); save(KEY, n); };

  function add() {
    if (!form.text.trim()) return;
    const { expense, yield_kg, price_per_kg } = form;
    commit([{ id: Math.random().toString(36).slice(2, 9), date: new Date().toISOString().slice(0, 10), text: form.text.trim(), kind: form.kind, crop: profile.main_crop || "",
      done: false, useful: null, predicted: nums({ expense, yield_kg, price_per_kg }), actual: {} }, ...recs].slice(0, 200));
    setForm({ text: "", kind: "other", expense: "", yield_kg: "", price_per_kg: "" });
  }
  const upd = (id, p) => commit(recs.map((r) => (r.id === id ? { ...r, ...p } : r)));
  function finish(r, useful) {
    upd(r.id, { done: true, useful, actual: nums(act) });
    setOpen(null); setAct({});
  }
  async function makeReport() {
    setErr("");
    try {
      const r = await fetch("/api/outcomes/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ records: recs, lang: l, currency: profile.country === "IN" ? "₹" : "" }) });
      if (!r.ok) throw new Error();
      setRep(await r.json());
    } catch { setErr(t.offline); }
  }
  const field = (k, label, obj, set) => <input key={k} type="number" inputMode="decimal" value={obj[k] ?? ""} onChange={(e) => set({ ...obj, [k]: e.target.value })} placeholder={label} aria-label={label} />;

  return (
    <Sheet title={"📈 " + t.title} onClose={onClose} close={t.close}>
      <label>{t.what}<textarea rows={2} maxLength={300} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} /></label>
      <select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} aria-label="kind">{KINDS.map((k) => <option key={k} value={k}>{t.kind[k]}</option>)}</select>
      <div className="alert-form">{field("expense", t.pe, form, setForm)}{field("yield_kg", t.py, form, setForm)}{field("price_per_kg", t.pp, form, setForm)}</div>
      <button className="primary" onClick={add}>{t.add}</button>
      <h5>{t.list}</h5>
      {!recs.length && <p className="hint">{t.empty}</p>}
      {recs.map((r) => (
        <div key={r.id} className="khata-row" style={{ display: "block" }}>
          <b>{t.kind[r.kind] || r.kind}</b> · {r.date} {r.done && <span>✅ {t.doneL} {r.useful === true ? "👍" : r.useful === false ? "👎" : ""}</span>}
          <p>{r.text}</p>
          {!r.done && open !== r.id && <button className="pill" onClick={() => { setOpen(r.id); setAct({}); }}>{t.done}</button>}
          {open === r.id && <>
            <div className="alert-form">{field("expense", t.ae, act, setAct)}{field("yield_kg", t.ay, act, setAct)}{field("price_per_kg", t.ap, act, setAct)}</div>
            <p className="hint">{t.useful}</p>
            <div className="alert-actions"><button className="pill" onClick={() => finish(r, true)}>{t.yes}</button><button className="pill" onClick={() => finish(r, false)}>{t.no}</button></div>
          </>}
          <button className="pill" onClick={() => commit(recs.filter((x) => x.id !== r.id))}>{t.del}</button>
        </div>
      ))}
      <button className="primary" onClick={makeReport} disabled={!recs.length}>{t.report}</button>
      {err && <p className="warn-note">{err}</p>}
      {rep && <div className="claim-out"><pre className="claim-msg">{rep.text}</pre><button className="pill" onClick={() => shareText(rep.text)}>{t.share}</button></div>}
    </Sheet>
  );
}
