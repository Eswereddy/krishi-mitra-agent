// Machine safety: the operator ticks what is true right now and gets ranked warnings (rollover, collision, entanglement, power lines, fitness).
// Rules run on the server in code. The app cannot see hazards that are not ticked and cannot detect a collision; the sheet says so.
// A check can be logged on this phone (date, machine, level) so it can count as evidence in the Sustainability Passport.
import { useEffect, useState } from "react";
import { Sheet } from "./khata";

const GROUPS = { ground: ["slope_steep", "ground_wet", "ditch_edge", "narrow_path", "heavy_rain", "strong_wind"], light: ["night", "low_vis", "hot_midday"],
  around: ["children_near", "people_near", "animals_near", "power_lines", "road_crossing", "other_vehicles", "blind_corner"],
  operator: ["unwell_or_drowsy", "tired", "hours_4plus", "working_alone", "loose_clothing", "first_time"],
  machine: ["riders", "no_rops_belt", "pto_guard_missing", "overloaded", "brakes_unchecked", "implement_raised", "reversing"] };
const MACHINES = ["tractor", "tiller", "thresher", "harvester", "sprayer", "trailer", "pump"];
const S = {
  en: { title: "Machine safety", sub: "Warnings before you start", machine: "Machine", intro: "Tick what is true right now", log: "Log this check on my phone", logged: "Logged", fail: "Could not check. Try again.", close: "Close", none: "Tick what applies and the warnings appear here.", why: "Do",
        g: { ground: "Ground and weather", light: "Light and heat", around: "Around me", operator: "Operator", machine: "Machine" },
        m: { tractor: "Tractor", tiller: "Power tiller", thresher: "Thresher", harvester: "Harvester", sprayer: "Sprayer", trailer: "Trailer", pump: "Engine pump" },
        c: { slope_steep: "Steep slope", ground_wet: "Wet or muddy ground", ditch_edge: "Near a ditch, canal, pond or bund edge", narrow_path: "Narrow path or bund", heavy_rain: "Heavy rain", strong_wind: "Strong wind", night: "Dark or dusk", low_vis: "Fog, dust or rain: poor view", hot_midday: "Very hot",
          children_near: "Children nearby", people_near: "People nearby", animals_near: "Animals nearby", power_lines: "Overhead power lines", road_crossing: "Using or crossing a road", other_vehicles: "Other vehicles around", blind_corner: "Blind corner or crest ahead",
          unwell_or_drowsy: "I am drowsy or unwell, or had drink or medicine", tired: "Very tired or slept little", hours_4plus: "Driving 4+ hours without a break", working_alone: "Working alone", loose_clothing: "Loose clothes, scarf or long hair", first_time: "New to this machine",
          riders: "People are riding on it", no_rops_belt: "No roll-over frame or seat belt", pto_guard_missing: "Shaft or belt guard missing", overloaded: "Overloaded", brakes_unchecked: "Brakes not checked today", implement_raised: "Implement, loader or load raised", reversing: "I am reversing" } },
  te: { title: "యంత్ర భద్రత", sub: "మొదలుపెట్టే ముందు హెచ్చరికలు", machine: "యంత్రం", intro: "ఇప్పుడు నిజమైనవి టిక్ చేయండి", log: "ఈ తనిఖీని ఫోన్‌లో నమోదు చేయి", logged: "నమోదైంది", fail: "తనిఖీ కాలేదు. మళ్లీ ప్రయత్నించండి.", close: "మూసివేయి", none: "వర్తించేవి టిక్ చేస్తే హెచ్చరికలు ఇక్కడ వస్తాయి.", why: "చేయాల్సింది",
        g: { ground: "నేల, వాతావరణం", light: "వెలుతురు, వేడి", around: "నా చుట్టూ", operator: "ఆపరేటర్", machine: "యంత్రం" },
        m: { tractor: "ట్రాక్టర్", tiller: "పవర్ టిల్లర్", thresher: "నూర్పిడి యంత్రం", harvester: "కోత యంత్రం", sprayer: "స్ప్రేయర్", trailer: "ట్రైలర్", pump: "ఇంజిన్ పంపు" },
        c: { slope_steep: "నిటారు వాలు", ground_wet: "తడి లేదా బురద నేల", ditch_edge: "గుంత, కాలువ, చెరువు, గట్టు అంచు దగ్గర", narrow_path: "ఇరుకైన దారి లేదా గట్టు", heavy_rain: "భారీ వర్షం", strong_wind: "బలమైన గాలి", night: "చీకటి లేదా సంధ్య", low_vis: "పొగమంచు, దుమ్ము, వర్షం: సరిగా కనిపించదు", hot_midday: "చాలా వేడి",
          children_near: "దగ్గర పిల్లలు", people_near: "దగ్గర మనుషులు", animals_near: "దగ్గర పశువులు", power_lines: "పైన విద్యుత్ తీగలు", road_crossing: "రోడ్డు దాటడం లేదా రోడ్డుపై", other_vehicles: "చుట్టూ ఇతర వాహనాలు", blind_corner: "ముందు కనిపించని మలుపు లేదా ఎత్తు",
          unwell_or_drowsy: "నాకు నిద్రమత్తు/అనారోగ్యం, లేదా మద్యం/మందు వేసుకున్నాను", tired: "చాలా అలసట, నిద్ర తక్కువ", hours_4plus: "విరామం లేకుండా 4+ గంటలు నడుపుతున్నాను", working_alone: "ఒంటరిగా పని", loose_clothing: "వదులు బట్టలు, కండువా, పొడవైన జుట్టు", first_time: "ఈ యంత్రం కొత్త",
          riders: "మనుషులు ఎక్కి ఉన్నారు", no_rops_belt: "రోల్-ఓవర్ ఫ్రేమ్ లేదా సీటు బెల్ట్ లేదు", pto_guard_missing: "షాఫ్ట్/బెల్ట్ గార్డ్ లేదు", overloaded: "ఎక్కువ బరువు", brakes_unchecked: "ఈరోజు బ్రేకులు పరీక్షించలేదు", implement_raised: "పనిముట్టు/లోడర్/లోడ్ పైకి ఉంది", reversing: "వెనక్కి నడుపుతున్నాను" } },
  hi: { title: "मशीन सुरक्षा", sub: "शुरू करने से पहले चेतावनी", machine: "मशीन", intro: "जो अभी सच है उसे टिक करें", log: "यह जाँच फ़ोन में दर्ज करें", logged: "दर्ज हुआ", fail: "जाँच नहीं हो सकी। फिर कोशिश करें।", close: "बंद करें", none: "जो लागू हो टिक करें, चेतावनी यहाँ दिखेगी।", why: "क्या करें",
        g: { ground: "ज़मीन और मौसम", light: "रोशनी और गर्मी", around: "मेरे आसपास", operator: "ऑपरेटर", machine: "मशीन" },
        m: { tractor: "ट्रैक्टर", tiller: "पावर टिलर", thresher: "थ्रेशर", harvester: "हार्वेस्टर", sprayer: "स्प्रेयर", trailer: "ट्रेलर", pump: "इंजन पंप" },
        c: { slope_steep: "तेज़ ढलान", ground_wet: "गीली या कीचड़ वाली ज़मीन", ditch_edge: "गड्ढे, नहर, तालाब, मेड़ के किनारे के पास", narrow_path: "संकरा रास्ता या मेड़", heavy_rain: "भारी बारिश", strong_wind: "तेज़ हवा", night: "अँधेरा या शाम", low_vis: "कोहरा, धूल, बारिश: कम दिखता है", hot_midday: "बहुत गर्मी",
          children_near: "पास में बच्चे", people_near: "पास में लोग", animals_near: "पास में पशु", power_lines: "ऊपर बिजली की तारें", road_crossing: "सड़क पर या पार करना", other_vehicles: "आसपास दूसरे वाहन", blind_corner: "आगे न दिखने वाला मोड़ या ऊँचाई",
          unwell_or_drowsy: "मुझे नींद/बीमारी है, या शराब/दवा ली है", tired: "बहुत थका हूँ या कम सोया", hours_4plus: "बिना रुके 4+ घंटे चला रहा हूँ", working_alone: "अकेले काम", loose_clothing: "ढीले कपड़े, गमछा, लंबे बाल", first_time: "इस मशीन पर नया हूँ",
          riders: "लोग सवार हैं", no_rops_belt: "रोल-ओवर फ्रेम या सीट बेल्ट नहीं", pto_guard_missing: "शाफ्ट/बेल्ट गार्ड नहीं", overloaded: "ज़्यादा वज़न", brakes_unchecked: "आज ब्रेक नहीं जाँचे", implement_raised: "औज़ार/लोडर/लोड ऊपर है", reversing: "पीछे ले रहा हूँ" } },
};
export const sf = (lang) => S[lang] || S.en;
const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };
export const SAFETY_LOG = "km-safety-log";
const COLORS = { stop: "#c62828", high: "#e65100", caution: "#a86f00", ok: "#2e7d32" };

export function SafetySheet({ lang, onClose }) {
  const t = sf(lang);
  const [machine, setMachine] = useState("tractor");
  const [on, setOn] = useState({});
  const [res, setRes] = useState(null);
  const [err, setErr] = useState(false);
  const [done, setDone] = useState(false);
  const conditions = Object.keys(on).filter((k) => on[k]);
  useEffect(() => {
    setDone(false);
    if (!conditions.length) return setRes(null);
    let live = true;
    fetch("/api/safety/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ machine, conditions, lang }) })
      .then((r) => (r.ok ? r.json() : Promise.reject())).then((j) => { if (live) { setRes(j); setErr(false); } }).catch(() => live && setErr(true));
    return () => { live = false; };
  }, [machine, on, lang]); // eslint-disable-line
  function logIt() {
    if (!res) return;
    save(SAFETY_LOG, [{ date: new Date().toISOString().slice(0, 10), machine, level: res.level, stop: res.counts.stop, high: res.counts.high, caution: res.counts.caution }, ...load(SAFETY_LOG, [])].slice(0, 60));
    setDone(true);
  }
  return (
    <Sheet title={"🚜 " + t.title} onClose={onClose} close={t.close}>
      <label>{t.machine}<select value={machine} onChange={(e) => setMachine(e.target.value)}>{MACHINES.map((m) => <option key={m} value={m}>{t.m[m]}</option>)}</select></label>
      <p className="hint">{t.intro}</p>
      {res && (
        <div className="decision" style={{ background: COLORS[res.level], color: "#fff", fontWeight: 800 }} role="status">{res.level_text}</div>
      )}
      {err && <p className="hint">{t.fail}</p>}
      {res && res.warnings.map((w) => (
        <div key={w.code} className="decision" style={{ textAlign: "left", borderLeft: "6px solid " + COLORS[w.level] }}>
          <b>{w.icon} {w.text}</b> <span className="badge" style={{ background: COLORS[w.level], color: "#fff" }}>{w.kind_text}</span>
          <small style={{ display: "block", marginTop: 4 }}><b>{t.why}:</b> {w.do}</small>
        </div>
      ))}
      {!res && !err && <p className="hint">{t.none}</p>}
      {res && <p className="hint">{res.note}</p>}
      {res && <button className="pill" onClick={logIt} disabled={done}>{done ? "✅ " + t.logged : t.log}</button>}
      {Object.entries(GROUPS).map(([g, items]) => (
        <div key={g}><h5>{t.g[g]}</h5>
          {items.map((c) => <label key={c} className="check"><input type="checkbox" checked={!!on[c]} onChange={(e) => setOn({ ...on, [c]: e.target.checked })} />{t.c[c]}</label>)}
        </div>
      ))}
    </Sheet>
  );
}
