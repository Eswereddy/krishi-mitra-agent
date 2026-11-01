// Irrigation costs: log each irrigation (mm, pump hours), set pump and price once, see water used, pumping cost, savings against
// the farmer's own usual practice, and this week's recommended water priced at their cost per mm. Data stays on the phone.
import { useState } from "react";
import { Sheet, shareText } from "./khata";

const S = {
  en: { title: "Water and pump cost", sub: "Save water and money", pump: "Pump", electric: "Electric (kW)", diesel: "Diesel (litres/hour)", power: "Pump power", price: "Price (per kWh or per litre)", flow: "Pump flow m3/hour (optional)", base: "My usual water per week (mm)",
        date: "Date", mm: "Water given (mm)", hours: "Pump hours", add: "Add irrigation", report: "Cost report", share: "Share", close: "Close", acres: "Set your area in My field first.", fail: "Could not make the report. Check the connection and numbers.", list: "Irrigations", remove: "Remove", help: "1 mm over 1 acre is about 4,047 litres." },
  te: { title: "నీరు, పంపు ఖర్చు", sub: "నీరు, డబ్బు ఆదా", pump: "పంపు", electric: "విద్యుత్ (kW)", diesel: "డీజిల్ (లీటర్లు/గంట)", power: "పంపు శక్తి", price: "ధర (kWh లేదా లీటరుకు)", flow: "పంపు ప్రవాహం ఘ.మీ/గంట (ఐచ్ఛికం)", base: "నా సాధారణ వారపు నీరు (మి.మీ)",
        date: "తేదీ", mm: "ఇచ్చిన నీరు (మి.మీ)", hours: "పంపు గంటలు", add: "తడి చేర్చు", report: "ఖర్చు నివేదిక", share: "పంచుకో", close: "మూసివేయి", acres: "ముందు నా పొలంలో విస్తీర్ణం నమోదు చేయండి.", fail: "నివేదిక రాలేదు. ఇంటర్నెట్, సంఖ్యలు చూడండి.", list: "తడులు", remove: "తొలగించు", help: "1 ఎకరాపై 1 మి.మీ సుమారు 4,047 లీటర్లు." },
  hi: { title: "पानी और पंप खर्च", sub: "पानी और पैसे की बचत", pump: "पंप", electric: "बिजली (kW)", diesel: "डीज़ल (लीटर/घंटा)", power: "पंप शक्ति", price: "कीमत (प्रति kWh या लीटर)", flow: "पंप प्रवाह घन मी/घंटा (वैकल्पिक)", base: "मेरा सामान्य साप्ताहिक पानी (मिमी)",
        date: "तारीख़", mm: "दिया पानी (मिमी)", hours: "पंप के घंटे", add: "सिंचाई जोड़ें", report: "खर्च रिपोर्ट", share: "साझा करें", close: "बंद करें", acres: "पहले मेरा खेत में क्षेत्र डालें।", fail: "रिपोर्ट नहीं बनी। इंटरनेट और संख्याएँ देखें।", list: "सिंचाई", remove: "हटाएँ", help: "1 एकड़ पर 1 मिमी लगभग 4,047 लीटर है।" },
};
export const ix = (lang) => S[lang] || S.en;
const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };

export function IrrigationSheet({ lang, profile, onClose }) {
  const t = ix(lang);
  const l = lang === "auto" ? "te" : lang;
  const today = new Date().toISOString().slice(0, 10);
  const [twin, setTwinState] = useState(() => load("km-twin", null) || { irrigation: [] });
  const [cfg, setCfg] = useState(() => load("km-irrig", { type: "electric", power: "", price: "", flow: "", base: "" }));
  const [e, setE] = useState({ date: today, mm: "", hours: "" });
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState("");
  const log = twin.irrigation || [];
  const setCfgP = (p) => { const n = { ...cfg, ...p }; setCfg(n); save("km-irrig", n); };
  const setLog = (irrigation) => { const n = { ...twin, irrigation }; setTwinState(n); save("km-twin", n); };

  function add() {
    if (!(Number(e.mm) > 0) || !e.date) return;
    setLog([...log, { date: e.date, mm: Number(e.mm), ...(Number(e.hours) > 0 ? { hours: Number(e.hours) } : {}) }].slice(-200));
    setE({ date: today, mm: "", hours: "" });
  }
  async function run() {
    setErr("");
    const pump = { type: cfg.type, price: Number(cfg.price) || null, flow_m3_per_h: Number(cfg.flow) || null, ...(cfg.type === "diesel" ? { diesel_l_per_h: Number(cfg.power) || null } : { kw: Number(cfg.power) || null }) };
    try {
      const r = await fetch("/api/irrigation/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        lang: l, acres: Number(twin.acres), entries: log, pump, baseline_mm_per_week: Number(cfg.base) || null, currency: profile.country === "IN" ? "₹" : "",
        crop: twin.crop || profile.main_crop, place: twin.place || profile.district, sowing_date: twin.sowing_date || profile.sowing_date, country: profile.country }) });
      if (!r.ok) throw new Error();
      setRep(await r.json());
    } catch { setErr(t.fail); }
  }
  const num = (v, set, label) => <input type="number" inputMode="decimal" value={v} onChange={(x) => set(x.target.value)} placeholder={label} aria-label={label} />;

  return (
    <Sheet title={"💧 " + t.title} onClose={onClose} close={t.close}>
      {!Number(twin.acres) && <p className="warn-note">{t.acres}</p>}
      <select value={cfg.type} onChange={(x) => setCfgP({ type: x.target.value })} aria-label={t.pump}><option value="electric">{t.electric}</option><option value="diesel">{t.diesel}</option></select>
      <div className="alert-form">{num(cfg.power, (v) => setCfgP({ power: v }), t.power)}{num(cfg.price, (v) => setCfgP({ price: v }), t.price)}</div>
      {num(cfg.flow, (v) => setCfgP({ flow: v }), t.flow)}
      {num(cfg.base, (v) => setCfgP({ base: v }), t.base)}
      <p className="hint">{t.help}</p>
      <div className="alert-form">
        <input type="date" value={e.date} max={today} onChange={(x) => setE({ ...e, date: x.target.value })} aria-label={t.date} />
        {num(e.mm, (v) => setE({ ...e, mm: v }), t.mm)}{num(e.hours, (v) => setE({ ...e, hours: v }), t.hours)}
      </div>
      <button className="pill" onClick={add}>{t.add}</button>
      {log.length > 0 && <><h5>{t.list}</h5><ul className="plain">{log.slice(-6).map((x, i) => <li key={i}>{x.date}: {x.mm} mm{x.hours ? `, ${x.hours} h` : ""}</li>)}</ul></>}
      <button className="primary" onClick={run} disabled={!log.length}>{t.report}</button>
      {err && <p className="warn-note">{err}</p>}
      {rep && <div className="claim-out"><pre className="claim-msg">{rep.text}</pre><button className="pill" onClick={() => shareText(rep.text)}>{t.share}</button></div>}
    </Sheet>
  );
}
