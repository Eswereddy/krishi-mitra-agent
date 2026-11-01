// Farm digital twin: one living record of the field (area, soil, crop, variety, sowing, irrigation, cost, yield) kept on the
// phone, turned into an explainable progress report with the weather the field has actually lived through.
import { useState } from "react";
import { Sheet, shareText } from "./khata";

const SOILS = ["sandy", "loam", "clay", "black", "red", "alluvial", "other"];
const S = {
  en: { title: "My field", sub: "Digital twin", crop: "Crop", variety: "Variety (optional)", place: "Village / district", acres: "Area (acres)", soil: { sandy: "Sandy", loam: "Loam", clay: "Clay", black: "Black", red: "Red", alluvial: "Alluvial", other: "Other" },
        sow: "Sowing date", exp: "Spent so far", yld: "Yield so far (kg)", khata: "Use my Khata expenses", irr: "Irrigation log", mm: "mm given", addIrr: "Add", report: "Field report", share: "Share", close: "Close", fail: "Report needs a connection and the crop, area filled in.", basis: "Basis" },
  te: { title: "నా పొలం", sub: "డిజిటల్ ట్విన్", crop: "పంట", variety: "రకం (ఐచ్ఛికం)", place: "ఊరు / జిల్లా", acres: "విస్తీర్ణం (ఎకరాలు)", soil: { sandy: "ఇసుక", loam: "ఒండ్రు", clay: "బంక", black: "నల్ల", red: "ఎర్ర", alluvial: "ఒండ్రుమట్టి", other: "ఇతరం" },
        sow: "విత్తిన తేదీ", exp: "ఇప్పటివరకు ఖర్చు", yld: "ఇప్పటివరకు దిగుబడి (కిలో)", khata: "నా ఖాతా ఖర్చులు వాడు", irr: "తడుల నమోదు", mm: "మి.మీ ఇచ్చారు", addIrr: "చేర్చు", report: "పొలం నివేదిక", share: "పంచుకో", close: "మూసివేయి", fail: "నివేదికకు ఇంటర్నెట్, పంట, విస్తీర్ణం కావాలి.", basis: "ఆధారం" },
  hi: { title: "मेरा खेत", sub: "डिजिटल ट्विन", crop: "फसल", variety: "किस्म (वैकल्पिक)", place: "गाँव / ज़िला", acres: "क्षेत्र (एकड़)", soil: { sandy: "रेतीली", loam: "दोमट", clay: "चिकनी", black: "काली", red: "लाल", alluvial: "जलोढ़", other: "अन्य" },
        sow: "बुवाई की तारीख़", exp: "अब तक खर्च", yld: "अब तक उपज (किलो)", khata: "मेरे खाते का खर्च लें", irr: "सिंचाई का रिकॉर्ड", mm: "मिमी दिया", addIrr: "जोड़ें", report: "खेत रिपोर्ट", share: "साझा करें", close: "बंद करें", fail: "रिपोर्ट के लिए इंटरनेट, फसल और क्षेत्र चाहिए।", basis: "आधार" },
};
export const wx = (lang) => S[lang] || S.en;
const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };
const KEY = "km-twin";

export function TwinSheet({ lang, profile, onClose }) {
  const t = wx(lang);
  const l = lang === "auto" ? "te" : lang;
  const today = new Date().toISOString().slice(0, 10);
  const [tw, setTw] = useState(() => load(KEY, null) || { crop: profile.main_crop || "", variety: "", place: profile.district || "", acres: "", soil: "loam", sowing_date: profile.sowing_date || "", expenses: "", yield_kg: "", irrigation: [] });
  const [irr, setIrr] = useState({ date: today, mm: "" });
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState("");
  const set = (p) => { const n = { ...tw, ...p }; setTw(n); save(KEY, n); };

  function fromKhata() {
    const rows = load("km-khata", []).filter((e) => e.type === "expense" && (!tw.crop || !e.crop || e.crop.toLowerCase() === tw.crop.toLowerCase()));
    set({ expenses: String(rows.reduce((a, e) => a + (Number(e.amount_rs) || 0), 0)) });
  }
  function addIrr() {
    const mm = Number(irr.mm);
    if (!(mm > 0) || !irr.date) return;
    set({ irrigation: [...tw.irrigation, { date: irr.date, mm }].slice(-200) });
    setIrr({ date: today, mm: "" });
  }
  async function run() {
    setErr("");
    try {
      const r = await fetch("/api/twin/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lang: l, twin: { ...tw, country: profile.country } }) });
      if (!r.ok) throw new Error();
      setRep(await r.json());
    } catch { setErr(t.fail); }
  }
  const inp = (k, label, type = "text") => <input type={type} inputMode={type === "number" ? "decimal" : undefined} value={tw[k] ?? ""} onChange={(e) => set({ [k]: e.target.value })} placeholder={label} aria-label={label} />;

  return (
    <Sheet title={"🌾 " + t.title} onClose={onClose} close={t.close}>
      <div className="alert-form">{inp("crop", t.crop)}{inp("variety", t.variety)}</div>
      <div className="alert-form">{inp("place", t.place)}{inp("acres", t.acres, "number")}</div>
      <select value={tw.soil} onChange={(e) => set({ soil: e.target.value })} aria-label="soil">{SOILS.map((s) => <option key={s} value={s}>{t.soil[s]}</option>)}</select>
      <label>{t.sow}<input type="date" value={tw.sowing_date} max={today} onChange={(e) => set({ sowing_date: e.target.value })} /></label>
      <div className="alert-form">{inp("expenses", t.exp, "number")}{inp("yield_kg", t.yld, "number")}</div>
      <button className="pill" onClick={fromKhata}>📒 {t.khata}</button>
      <h5>{t.irr}</h5>
      <div className="alert-form">
        <input type="date" value={irr.date} max={today} onChange={(e) => setIrr({ ...irr, date: e.target.value })} aria-label="date" />
        <input type="number" inputMode="decimal" value={irr.mm} onChange={(e) => setIrr({ ...irr, mm: e.target.value })} placeholder={t.mm} aria-label={t.mm} />
        <button className="pill" onClick={addIrr}>{t.addIrr}</button>
      </div>
      {tw.irrigation.length > 0 && <ul className="plain">{tw.irrigation.slice(-5).map((x, i) => <li key={i}>{x.date}: {x.mm} mm</li>)}</ul>}
      <button className="primary" onClick={run}>{t.report}</button>
      {err && <p className="warn-note">{err}</p>}
      {rep && (
        <div className="claim-out">
          <ul className="plain">{rep.facts.map((f) => <li key={f.code} className={f.code === "warning" ? "warn-note" : ""}>{f.text}<small className="hint" style={{ display: "block" }}>{t.basis}: {f.basis}</small></li>)}</ul>
          <p className="hint">{rep.note}</p>
          <button className="pill" onClick={() => shareText(rep.text)}>{t.share}</button>
        </div>
      )}
    </Sheet>
  );
}
