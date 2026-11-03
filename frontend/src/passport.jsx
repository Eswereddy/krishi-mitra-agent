// Farm Sustainability Passport: a plain report of what the farmer's own records support. Records stay on the phone; the server only calculates the report
// from what is sent and stores nothing. A practice counts only with a dated photo, receipt or record note, and an absence ("no synthetic pesticide") cannot count.
import { useState } from "react";
import { Sheet, shareText } from "./khata";

const PRACTICES = ["residue_not_burned", "mulching", "drip_or_sprinkler", "rainwater_harvest", "compost_or_manure", "legume_or_cover", "solar_pump", "no_synthetic_pesticide"];
const S = {
  en: { title: "Sustainability Passport", sub: "What my records can show", pr: "Practices I follow", hint: "Tick what you do. A practice counts only if you attach a dated photo, receipt or record note.", kind: "Evidence", date: "Date", note: "Short note (what the evidence shows)",
        k: { photo: "Photo", receipt: "Receipt", record: "Record" }, complete: "I logged every irrigation in the period (needed to claim a water saving)", make: "Make my passport", share: "Share", copy: "Copy", copied: "Copied", print: "Print", close: "Close", fail: "Could not make the passport. Try again.",
        p: { residue_not_burned: "Crop residue not burned", mulching: "Mulching", drip_or_sprinkler: "Drip or sprinkler irrigation", rainwater_harvest: "Rainwater harvesting", compost_or_manure: "Compost or farmyard manure", legume_or_cover: "Legume or cover crop", solar_pump: "Solar pump", no_synthetic_pesticide: "No synthetic pesticide used" },
        absence: "This cannot be proven from phone records. It will be listed as not claimed." },
  te: { title: "సుస్థిరత పాస్‌పోర్ట్", sub: "నా రికార్డులు ఏమి చూపగలవు", pr: "నేను పాటించే పద్ధతులు", hint: "మీరు చేసేవి టిక్ చేయండి. తేదీతో ఫోటో, రసీదు లేదా రికార్డు నోట్ జతచేస్తేనే పద్ధతి లెక్కలోకి వస్తుంది.", kind: "ఆధారం", date: "తేదీ", note: "చిన్న నోట్ (ఆధారం ఏమి చూపుతుంది)",
        k: { photo: "ఫోటో", receipt: "రసీదు", record: "రికార్డు" }, complete: "ఆ కాలంలో ప్రతి నీటి పారుదలను నమోదు చేశాను (నీటి ఆదా క్లెయిమ్‌కు అవసరం)", make: "నా పాస్‌పోర్ట్ తయారు చేయి", share: "షేర్", copy: "కాపీ", copied: "కాపీ అయింది", print: "ప్రింట్", close: "మూసివేయి", fail: "పాస్‌పోర్ట్ తయారు కాలేదు. మళ్లీ ప్రయత్నించండి.",
        p: { residue_not_burned: "పంట అవశేషాలు కాల్చలేదు", mulching: "మల్చింగ్", drip_or_sprinkler: "డ్రిప్ లేదా స్ప్రింక్లర్", rainwater_harvest: "వర్షపు నీటి సేకరణ", compost_or_manure: "కంపోస్ట్ లేదా పశువుల ఎరువు", legume_or_cover: "పప్పు జాతి లేదా కవర్ పంట", solar_pump: "సోలార్ పంపు", no_synthetic_pesticide: "రసాయన పురుగుమందు వాడలేదు" },
        absence: "ఫోన్ రికార్డులతో దీన్ని నిరూపించలేం. 'క్లెయిమ్ చేయలేదు' జాబితాలో ఉంటుంది." },
  hi: { title: "स्थिरता पासपोर्ट", sub: "मेरे रिकॉर्ड क्या दिखा सकते हैं", pr: "मैं जो तरीके अपनाता हूँ", hint: "जो करते हैं टिक करें। तारीख वाला फ़ोटो, रसीद या रिकॉर्ड नोट जोड़ने पर ही तरीका गिना जाएगा।", kind: "सबूत", date: "तारीख", note: "छोटा नोट (सबूत क्या दिखाता है)",
        k: { photo: "फ़ोटो", receipt: "रसीद", record: "रिकॉर्ड" }, complete: "उस अवधि की हर सिंचाई मैंने दर्ज की (पानी की बचत के दावे के लिए ज़रूरी)", make: "मेरा पासपोर्ट बनाएँ", share: "शेयर", copy: "कॉपी", copied: "कॉपी हुआ", print: "प्रिंट", close: "बंद करें", fail: "पासपोर्ट नहीं बन सका। फिर कोशिश करें।",
        p: { residue_not_burned: "फसल अवशेष नहीं जलाए", mulching: "मल्चिंग", drip_or_sprinkler: "ड्रिप या स्प्रिंकलर", rainwater_harvest: "वर्षा जल संचयन", compost_or_manure: "कम्पोस्ट या गोबर खाद", legume_or_cover: "दलहन या कवर फसल", solar_pump: "सोलर पंप", no_synthetic_pesticide: "रासायनिक कीटनाशक नहीं डाला" },
        absence: "फ़ोन रिकॉर्ड से इसे साबित नहीं किया जा सकता। यह 'दावा नहीं' सूची में आएगा।" },
};
export const pp = (lang) => S[lang] || S.en;
const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };
const KEY = "km-passport";
const today = () => new Date().toISOString().slice(0, 10);

export function PassportSheet({ lang, profile, onClose }) {
  const t = pp(lang);
  const [st, setSt] = useState(() => load(KEY, { practices: {}, complete: false }));
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState(false);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const put = (n) => { setSt(n); save(KEY, n); };
  const setP = (code, patch) => put({ ...st, practices: { ...st.practices, [code]: { ...(st.practices[code] || { on: false, kind: "photo", date: today(), note: "" }), ...patch } } });

  async function make() {
    setBusy(true); setErr(false);
    const tw = load("km-twin", null) || {};
    const practices = PRACTICES.filter((c) => st.practices[c]?.on).map((c) => { const p = st.practices[c]; return { code: c, evidence: p.note ? { kind: p.kind, date: p.date, note: p.note } : null }; });
    try {
      const r = await fetch("/api/passport/build", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        lang, farm: { crop: tw.crop || profile.main_crop, place: tw.place || profile.district, acres: tw.acres || load("km-acres", "") },
        irrigation: tw.irrigation || [], irrigation_baseline_mm_per_week: (load("km-irrig", {}) || {}).base || null, irrigation_log_complete: st.complete === true,
        khata: load("km-khata", []), notes: load("km-fnotes", []), cases: load("km-cases", []), safety: load("km-safety-log", []), outcomes: load("km-outcomes", []), practices }) });
      if (!r.ok) throw new Error();
      setRep(await r.json());
    } catch { setErr(true); }
    setBusy(false);
  }
  const copy = async () => { try { await navigator.clipboard.writeText(rep.text); setCopied(true); } catch { /* clipboard blocked */ } };
  return (
    <Sheet title={"🌱 " + t.title} onClose={onClose} close={t.close}>
      <h5>{t.pr}</h5>
      <p className="hint">{t.hint}</p>
      {PRACTICES.map((c) => {
        const p = st.practices[c] || {};
        return (
          <div key={c}>
            <label className="check"><input type="checkbox" checked={!!p.on} onChange={(e) => setP(c, { on: e.target.checked })} />{t.p[c]}</label>
            {p.on && c === "no_synthetic_pesticide" && <small className="hint">{t.absence}</small>}
            {p.on && c !== "no_synthetic_pesticide" && (
              <div className="alert-form" style={{ marginLeft: 30 }}>
                <label>{t.kind}<select value={p.kind || "photo"} onChange={(e) => setP(c, { kind: e.target.value })}>{Object.keys(t.k).map((k) => <option key={k} value={k}>{t.k[k]}</option>)}</select></label>
                <label>{t.date}<input type="date" max={today()} value={p.date || today()} onChange={(e) => setP(c, { date: e.target.value })} /></label>
                <input aria-label={t.note} placeholder={t.note} maxLength={120} value={p.note || ""} onChange={(e) => setP(c, { note: e.target.value })} />
              </div>
            )}
          </div>
        );
      })}
      <label className="check"><input type="checkbox" checked={!!st.complete} onChange={(e) => put({ ...st, complete: e.target.checked })} />{t.complete}</label>
      <button className="primary" onClick={make} disabled={busy}>{busy ? "…" : t.make}</button>
      {err && <p className="hint">{t.fail}</p>}
      {rep && (
        <div id="passport-report">
          <h4>{rep.title}</h4>
          <p className="hint">{rep.generated}{rep.farm ? " · " + rep.farm : ""}</p>
          <h5>{rep.headings.ok}</h5>
          {rep.supported.length === 0 && <p className="hint">—</p>}
          {rep.supported.map((c) => (
            <div key={c.code} className="decision" style={{ textAlign: "left", borderLeft: "6px solid " + (c.status === "recorded" ? "#2e7d32" : "#a86f00") }}>
              {c.text}<small style={{ display: "block", marginTop: 4 }}><span className={"badge " + (c.status === "recorded" ? "badge-ok" : "badge-warn")}>{c.status_text}</span></small>
            </div>
          ))}
          <h5>{rep.headings.no}</h5>
          {rep.not_claimed.map((c, i) => (
            <div key={c.code + i} className="decision" style={{ textAlign: "left", borderLeft: "6px solid #9e9e9e" }}>
              <b>{c.text}</b><small style={{ display: "block" }}>{c.why}</small><small style={{ display: "block" }}>→ {c.next}</small>
            </div>
          ))}
          <h5>{rep.headings.never}</h5>
          <ul className="plain">{rep.never.map((x, i) => <li key={i}>{x}</li>)}</ul>
          <p className="hint">{rep.basis}</p><p className="hint">{rep.disclaimer}</p>
          <div className="alert-form">
            <button className="pill" onClick={() => shareText(rep.text)}>{t.share}</button>
            <button className="pill" onClick={copy}>{copied ? "✅ " + t.copied : t.copy}</button>
            <button className="pill" onClick={() => window.print()}>{t.print}</button>
          </div>
        </div>
      )}
    </Sheet>
  );
}
