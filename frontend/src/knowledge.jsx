// Knowledge tools: why-this-answer, crop rotation, knowledge graph, learning coach, research assistant, field report, follow-ups.
// Everything the farmer saves (documents, notes, quiz history, decisions) stays on the phone; the server only computes.
import { useEffect, useRef, useState } from "react";
import { Sheet, shareText } from "./khata";
import { getLastScan } from "./extras";
import { startListening, extFor, unlockAudio } from "./lib/audio";

const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch { return false; } };
const post = async (url, body) => {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) { let d = ""; try { d = (await r.json()).detail; } catch { /* not json */ } throw new Error(d || String(r.status)); }
  return r.json();
};

const K = {
  en: {
    close: "Close", fail: "Could not load. Check the network and try again.", loading: "Working…",
    why: "Why this answer?", whyT: "Why this answer", ev: "What it is based on", trace: "Where each number came from", checks: "Checks run", change: "What would change it", inputs: "Used", figs: "figures checked",
    passed: "All figures match the tool results", notPassed: "Some figures did NOT match: treat with care", notool: "No data was used.",
    rot: "Crop rotation", rotSub: "What to grow next", last: "Last crop", before: "Crop before that", soil: "Soil", season: "Season", any: "Any / not sure", best: "Best next crop", planA: "Plan A (2 seasons)", planB: "Plan B (2 seasons)", compare: "Compare plans", pts: "points", none: "none", pick: "choose",
    kg: "Knowledge graph", kgSub: "Crops, problems, soils", search: "Crop or problem (e.g. cotton, tikka)", go: "Show", tapNode: "Tap a circle to explore it", links: "Links (with source)", unrev: "From the project's own tables, not yet reviewed by an agronomist.",
    coach: "Learning coach", coachSub: "Short lessons and quiz", topic: "Ask about a crop or a problem", make: "Make lesson", next: "Next lesson", score: "You scored {s} of {t}", level: "Level", answered: "Check answer",
    res: "Research assistant", resSub: "Answers from your documents", upload: "Add a document (PDF or text)", docs: "Your documents", ask: "Ask your documents", askPh: "For example: row spacing for groundnut", remove: "Remove", passages: "Passages used", model: "answered by the model, checked against the passages", extract: "closest passage, no model used", noDoc: "No documents yet. Add an ICAR or agriculture university PDF.", full: "Storage is full: remove a document.",
    fr: "Field report", frSub: "From voice notes + photo", note: "Add a note (type or speak)", add: "Add", speak: "Speak", stop: "Stop", notes: "Today's notes", useScan: "Include my latest leaf scan", build: "Build report", share: "Share", clear: "Clear notes", urgency: "Urgency", sym: "Symptoms", act: "Work done", match: "Possible matches (first guess)", steps: "Safe steps", ask2: "Questions for the expert", by: "Extracted by", noNotes: "Add a note or a leaf scan first.",
    fu: "Follow up", didIt: "Did it", notYet: "Not yet", skip: "Skip", say: "Tell me how it went", saved: "Saved. Thank you.",
  },
  te: {
    close: "మూసివేయి", fail: "లోడ్ కాలేదు. నెట్‌వర్క్ చూసి మళ్ళీ ప్రయత్నించండి.", loading: "పని జరుగుతోంది…",
    why: "ఈ జవాబు ఎందుకు?", whyT: "ఈ జవాబు ఎందుకు", ev: "దేని ఆధారంగా", trace: "ప్రతి సంఖ్య ఎక్కడి నుండి", checks: "జరిగిన తనిఖీలు", change: "ఏది మారిస్తే సలహా మారుతుంది", inputs: "వాడినవి", figs: "సంఖ్యలు తనిఖీ",
    passed: "అన్ని సంఖ్యలు టూల్ ఫలితాలతో సరిపోయాయి", notPassed: "కొన్ని సంఖ్యలు సరిపోలేదు: జాగ్రత్తగా చూడండి", notool: "ఏ డేటా వాడలేదు.",
    rot: "పంట మార్పిడి", rotSub: "తర్వాత ఏ పంట వేయాలి", last: "చివరి పంట", before: "దానికి ముందు పంట", soil: "నేల", season: "సీజన్", any: "ఏదైనా / తెలియదు", best: "తర్వాత వేయదగిన పంటలు", planA: "ప్లాన్ A (2 సీజన్లు)", planB: "ప్లాన్ B (2 సీజన్లు)", compare: "ప్లాన్లు పోల్చు", pts: "పాయింట్లు", none: "లేదు", pick: "ఎంచుకోండి",
    kg: "జ్ఞాన గ్రాఫ్", kgSub: "పంటలు, సమస్యలు, నేలలు", search: "పంట లేదా సమస్య (ఉదా: పత్తి, tikka)", go: "చూపు", tapNode: "చూడడానికి ఒక వృత్తాన్ని తాకండి", links: "సంబంధాలు (మూలంతో)", unrev: "ప్రాజెక్ట్ సొంత పట్టికల నుండి, వ్యవసాయ నిపుణుడు ఇంకా సమీక్షించలేదు.",
    coach: "నేర్చుకునే కోచ్", coachSub: "చిన్న పాఠాలు, క్విజ్", topic: "పంట లేదా సమస్య గురించి అడగండి", make: "పాఠం చేయి", next: "తర్వాతి పాఠం", score: "మీకు {t} లో {s} వచ్చాయి", level: "స్థాయి", answered: "జవాబు చూడు",
    res: "పరిశోధన సహాయకుడు", resSub: "మీ పత్రాల నుండి జవాబులు", upload: "పత్రం చేర్చండి (PDF లేదా టెక్స్ట్)", docs: "మీ పత్రాలు", ask: "మీ పత్రాలను అడగండి", askPh: "ఉదా: వేరుశనగ వరుసల దూరం", remove: "తొలగించు", passages: "వాడిన భాగాలు", model: "మోడల్ జవాబు, భాగాలతో సరిచూసింది", extract: "దగ్గరి భాగం, మోడల్ వాడలేదు", noDoc: "ఇంకా పత్రాలు లేవు. ICAR లేదా వ్యవసాయ విశ్వవిద్యాలయ PDF చేర్చండి.", full: "నిల్వ నిండింది: ఒక పత్రం తొలగించండి.",
    fr: "పొలం నివేదిక", frSub: "వాయిస్ గమనికలు + ఫోటో", note: "గమనిక చేర్చండి (టైప్ లేదా మాట్లాడండి)", add: "చేర్చు", speak: "మాట్లాడండి", stop: "ఆపు", notes: "ఈ రోజు గమనికలు", useScan: "నా తాజా ఆకు స్కాన్ చేర్చు", build: "నివేదిక తయారుచేయి", share: "షేర్", clear: "గమనికలు తొలగించు", urgency: "అత్యవసరం", sym: "లక్షణాలు", act: "చేసిన పనులు", match: "సాధ్యమైన సరిపోలికలు (మొదటి అంచనా)", steps: "సురక్షిత చర్యలు", ask2: "నిపుణుడిని అడగాల్సినవి", by: "తీసినది", noNotes: "ముందు గమనిక లేదా ఆకు స్కాన్ చేర్చండి.",
    fu: "ఫాలో-అప్", didIt: "చేశాను", notYet: "ఇంకా లేదు", skip: "వదిలేయి", say: "ఎలా జరిగిందో చెప్పండి", saved: "సేవ్ అయింది. ధన్యవాదాలు.",
  },
  hi: {
    close: "बंद करें", fail: "लोड नहीं हुआ। नेटवर्क जाँचकर फिर कोशिश करें।", loading: "काम चल रहा है…",
    why: "यह जवाब क्यों?", whyT: "यह जवाब क्यों", ev: "किस आधार पर", trace: "हर संख्या कहाँ से आई", checks: "की गई जाँच", change: "क्या बदलने पर सलाह बदलेगी", inputs: "इस्तेमाल", figs: "संख्याएँ जाँची गईं",
    passed: "सभी संख्याएँ टूल परिणामों से मेल खाती हैं", notPassed: "कुछ संख्याएँ मेल नहीं खाईं: सावधानी रखें", notool: "कोई डेटा इस्तेमाल नहीं हुआ।",
    rot: "फसल चक्र", rotSub: "अगली फसल क्या लगाएँ", last: "पिछली फसल", before: "उससे पहले की फसल", soil: "मिट्टी", season: "मौसम", any: "कोई भी / पता नहीं", best: "अगली सबसे अच्छी फसलें", planA: "योजना A (2 मौसम)", planB: "योजना B (2 मौसम)", compare: "योजनाओं की तुलना", pts: "अंक", none: "कोई नहीं", pick: "चुनें",
    kg: "ज्ञान ग्राफ़", kgSub: "फसलें, समस्याएँ, मिट्टी", search: "फसल या समस्या (जैसे कपास, tikka)", go: "दिखाएँ", tapNode: "देखने के लिए किसी गोले को छुएँ", links: "संबंध (स्रोत सहित)", unrev: "प्रोजेक्ट की अपनी तालिकाओं से, कृषि विशेषज्ञ ने अभी समीक्षा नहीं की।",
    coach: "सीखने का कोच", coachSub: "छोटे पाठ और क्विज़", topic: "किसी फसल या समस्या के बारे में पूछें", make: "पाठ बनाएँ", next: "अगला पाठ", score: "आपको {t} में से {s} मिले", level: "स्तर", answered: "जवाब देखें",
    res: "शोध सहायक", resSub: "आपके दस्तावेज़ों से जवाब", upload: "दस्तावेज़ जोड़ें (PDF या टेक्स्ट)", docs: "आपके दस्तावेज़", ask: "अपने दस्तावेज़ों से पूछें", askPh: "जैसे: मूँगफली में कतार की दूरी", remove: "हटाएँ", passages: "इस्तेमाल हुए अंश", model: "मॉडल का जवाब, अंशों से जाँचा गया", extract: "सबसे करीबी अंश, मॉडल नहीं चला", noDoc: "अभी कोई दस्तावेज़ नहीं। ICAR या कृषि विश्वविद्यालय का PDF जोड़ें।", full: "भंडारण भर गया: एक दस्तावेज़ हटाएँ।",
    fr: "खेत रिपोर्ट", frSub: "आवाज़ नोट + फ़ोटो से", note: "नोट जोड़ें (लिखें या बोलें)", add: "जोड़ें", speak: "बोलें", stop: "रोकें", notes: "आज के नोट", useScan: "मेरा ताज़ा पत्ती स्कैन जोड़ें", build: "रिपोर्ट बनाएँ", share: "शेयर", clear: "नोट हटाएँ", urgency: "तात्कालिकता", sym: "लक्षण", act: "किया गया काम", match: "संभावित मिलान (पहला अनुमान)", steps: "सुरक्षित कदम", ask2: "विशेषज्ञ से सवाल", by: "निकाला गया", noNotes: "पहले नोट या पत्ती स्कैन जोड़ें।",
    fu: "फ़ॉलो-अप", didIt: "कर लिया", notYet: "अभी नहीं", skip: "छोड़ें", say: "बताइए कैसा रहा", saved: "सेव हो गया। धन्यवाद।",
  },
};
export const kn = (lang) => K[lang] || K.en;
const SOILS = { en: ["sandy", "loam", "clay", "black", "red", "alluvial", "other"] };
const SOIL_L = { en: { sandy: "Sandy", loam: "Loam", clay: "Clay", black: "Black", red: "Red", alluvial: "Alluvial", other: "Other / not sure" },
  te: { sandy: "ఇసుక", loam: "లోమ్", clay: "బంకమట్టి", black: "నల్ల రేగడి", red: "ఎర్ర నేల", alluvial: "ఒండ్రు", other: "ఇతర / తెలియదు" },
  hi: { sandy: "रेतीली", loam: "दोमट", clay: "चिकनी", black: "काली", red: "लाल", alluvial: "जलोढ़", other: "अन्य / पता नहीं" } };

// Voice note: record, transcribe with Muse Voice Transcribe via /api/asr, hand the text back.
function useVoice(lang, onText, toast) {
  const [rec, setRec] = useState(false);
  const ref = useRef(null);
  async function toggle() {
    if (rec) return ref.current?.stop();
    try {
      unlockAudio();
      const l = startListening({});
      ref.current = l;
      setRec(true);
      const blob = await l.promise;
      setRec(false);
      if (!blob) return;
      const form = new FormData();
      form.append("audio", blob, `note.${extFor(blob.type)}`);
      form.append("lang", lang);
      const r = await fetch("/api/asr", { method: "POST", body: form });
      if (!r.ok) throw new Error(String(r.status));
      onText((await r.json()).text);
    } catch (e) { setRec(false); toast?.(e.name === "NotAllowedError" ? "Microphone: " + e.message : e.message); }
  }
  return { rec, toggle };
}
const Badge = ({ kind, children }) => <span className={"badge b-" + kind}>{children}</span>;

// ------------------------------------------------------------------ 1. why this answer
export function ExplainSheet({ lang, answer, steps, onClose }) {
  const t = kn(lang);
  const [d, setD] = useState(null);
  const [err, setErr] = useState(false);
  useEffect(() => { post("/api/explain", { answer, steps: (steps || []).slice(0, 12), lang }).then(setD).catch(() => setErr(true)); }, []); // eslint-disable-line
  return (
    <Sheet title={"🔎 " + t.whyT} onClose={onClose} close={t.close}>
      {err && <p className="hint">{t.fail}</p>}
      {!d && !err && <p className="hint">{t.loading}</p>}
      {d && <>
        {d.no_tool_note && <p className="hint">{d.no_tool_note}</p>}
        {d.evidence.length > 0 && <h5>{t.ev}</h5>}
        {d.evidence.map((e, i) => (
          <div key={i} className="decision steady" style={{ display: "block" }}>
            <b>{e.title}</b> <Badge kind={e.kind}>{e.label}</Badge>
            {e.source && <small className="hint" style={{ display: "block" }}>{e.source}{e.as_of ? " · " + e.as_of : ""}</small>}
            {Object.keys(e.inputs || {}).length > 0 && <small className="hint" style={{ display: "block" }}>{t.inputs}: {Object.entries(e.inputs).map(([k, v]) => `${k}=${v}`).join(", ")}</small>}
            {e.note && <small className="hint" style={{ display: "block" }}>{e.note}</small>}
          </div>
        ))}
        {d.figure_trace.length > 0 && <><h5>{t.trace}</h5><ul className="plain">{d.figure_trace.map((f, i) => <li key={i}><b>{f.figure}</b>: {f.label}{f.field ? <small className="hint"> ({f.field})</small> : null}</li>)}</ul></>}
        <h5>{t.checks}</h5>
        <p>{d.checks.passed ? "✅ " + t.passed : "⚠️ " + t.notPassed}{d.checks.unverified.length ? ": " + d.checks.unverified.join(", ") : ""} <small className="hint">({d.checks.figures_checked} {t.figs})</small></p>
        {d.could_change.length > 0 && <><h5>{t.change}</h5><ul className="plain">{d.could_change.map((c, i) => <li key={i}>{c}</li>)}</ul></>}
      </>}
    </Sheet>
  );
}

// ------------------------------------------------------------------ 2. crop rotation simulator
export function RotationSheet({ lang, profile, onClose }) {
  const t = kn(lang);
  const [crops, setCrops] = useState([]);
  const [last, setLast] = useState("");
  const [before, setBefore] = useState("");
  const [soil, setSoil] = useState((load("km-twin", null) || {}).soil || "other");
  const [season, setSeason] = useState("");
  const [A, setA] = useState(["", ""]);
  const [B, setB] = useState(["", ""]);
  const [res, setRes] = useState(null);
  const [cmp, setCmp] = useState(null);
  const [open, setOpen] = useState(null);
  const [err, setErr] = useState(false);
  useEffect(() => { fetch(`/api/kg/crops?lang=${lang}`).then((r) => r.json()).then((j) => setCrops(j.crops.map((c) => ({ id: c.id.split(":")[1], name: c.display })))).catch(() => setErr(true)); }, [lang]);
  const history = [last, before].filter(Boolean);
  useEffect(() => {
    if (!history.length) return setRes(null);
    post("/api/rotation/simulate", { history, soil, season, lang }).then((r) => { setRes(r); setErr(false); }).catch(() => setErr(true));
  }, [last, before, soil, season, lang]); // eslint-disable-line
  function compare() {
    const sc = [A, B].map((p) => p.filter(Boolean)).filter((p) => p.length);
    if (!sc.length) return;
    post("/api/rotation/simulate", { history, soil, season, scenarios: sc, lang }).then(setCmp).catch(() => setErr(true));
  }
  const sel = (v, set, label) => <label>{label}<select value={v} onChange={(e) => set(e.target.value)}><option value="">{t.pick}</option>{crops.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>;
  const mark = (n) => (n > 0 ? "+" + n : String(n));
  return (
    <Sheet title={"🔄 " + t.rot} onClose={onClose} close={t.close}>
      {err && <p className="hint">{t.fail}</p>}
      <div className="alert-form">{sel(last, setLast, t.last)}{sel(before, setBefore, t.before)}</div>
      <div className="alert-form">
        <label>{t.soil}<select value={soil} onChange={(e) => setSoil(e.target.value)}>{SOILS.en.map((s) => <option key={s} value={s}>{(SOIL_L[lang] || SOIL_L.en)[s]}</option>)}</select></label>
        <label>{t.season}<select value={season} onChange={(e) => setSeason(e.target.value)}><option value="">{t.any}</option><option value="kharif">Kharif</option><option value="rabi">Rabi</option></select></label>
      </div>
      {res && <>
        <h5>{t.best}</h5>
        {res.scenarios.slice(0, 5).map((s) => (
          <div key={s.ids[0]} className="decision steady" style={{ display: "block" }} onClick={() => setOpen(open === s.ids[0] ? null : s.ids[0])}>
            <b>{s.sequence[0]}</b> <Badge kind={s.total_points > 0 ? "live" : s.total_points < 0 ? "sample" : "indicative"}>{mark(s.total_points)} {t.pts}</Badge>
            {open === s.ids[0] && <ul className="plain">{s.steps[0].reasons.map((r, i) => <li key={i}>{mark(r.points)} · {r.reason}</li>)}{s.steps[0].water_note && <li>{s.steps[0].water_note}</li>}</ul>}
          </div>
        ))}
        <p className="hint">{res.basis}</p>
        {res.unrecognised.length > 0 && <p className="hint">{res.unrecognised.join(", ")}</p>}
      </>}
      {history.length > 0 && <>
        <h5>{t.compare}</h5>
        <p className="hint">{t.planA}</p><div className="alert-form">{sel(A[0], (v) => setA([v, A[1]]), "1")}{sel(A[1], (v) => setA([A[0], v]), "2")}</div>
        <p className="hint">{t.planB}</p><div className="alert-form">{sel(B[0], (v) => setB([v, B[1]]), "1")}{sel(B[1], (v) => setB([B[0], v]), "2")}</div>
        <button className="pill" onClick={compare}>⚖️ {t.compare}</button>
        {cmp?.scenarios.map((s, i) => (
          <div key={i} className="decision steady" style={{ display: "block" }}>
            <b>{s.sequence.join(" → ")}</b> <Badge kind={s.total_points > 0 ? "live" : s.total_points < 0 ? "sample" : "indicative"}>{mark(s.total_points)} {t.pts}</Badge>
            <ul className="plain">{s.steps.map((st) => st.reasons.map((r, j) => <li key={st.crop + j}>{st.name}: {mark(r.points)} · {r.reason}</li>))}</ul>
          </div>
        ))}
      </>}
    </Sheet>
  );
}

// ------------------------------------------------------------------ 3. knowledge graph
const KIND_COLOR = { crop: "#2e7d32", problem: "#c62828", condition: "#ef6c00", practice: "#1565c0", soil: "#6d4c41" };
export function GraphSheet({ lang, profile, onClose }) {
  const t = kn(lang);
  const [q, setQ] = useState(profile.main_crop || "");
  const [g, setG] = useState(null);
  const [err, setErr] = useState("");
  async function show(params) {
    setErr("");
    try {
      const r = await fetch(`/api/kg/node?lang=${lang}&` + new URLSearchParams(params));
      if (!r.ok) throw new Error(String(r.status));
      setG(await r.json());
    } catch { setErr(t.fail); }
  }
  useEffect(() => { if (q) show({ q }); }, []); // eslint-disable-line
  const others = g ? g.nodes.filter((n) => n.id !== g.center).slice(0, 14) : [];
  const center = g?.nodes.find((n) => n.id === g.center);
  const R = 118, cx = 160, cy = 150;
  const short = (s) => (s.length > 16 ? s.slice(0, 15) + "…" : s);
  return (
    <Sheet title={"🕸️ " + t.kg} onClose={onClose} close={t.close}>
      <div className="alert-form"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t.search} aria-label={t.search} onKeyDown={(e) => e.key === "Enter" && q && show({ q })} /><button className="pill" onClick={() => q && show({ q })}>{t.go}</button></div>
      {err && <p className="hint">{err}</p>}
      {g && <>
        <svg viewBox="0 0 320 300" width="100%" role="img" aria-label={center?.display} style={{ maxHeight: 340 }}>
          {others.map((n, i) => { const a = (2 * Math.PI * i) / others.length - Math.PI / 2; return <line key={n.id} x1={cx} y1={cy} x2={cx + R * Math.cos(a)} y2={cy + R * Math.sin(a)} stroke="#bbb" strokeWidth="1" />; })}
          {others.map((n, i) => { const a = (2 * Math.PI * i) / others.length - Math.PI / 2; const x = cx + R * Math.cos(a), y = cy + R * Math.sin(a);
            return <g key={n.id} onClick={() => show({ node: n.id })} style={{ cursor: "pointer" }}><circle cx={x} cy={y} r="15" fill={KIND_COLOR[n.kind]} opacity="0.9" /><text x={x} y={y + 28} fontSize="9" textAnchor="middle" fill="currentColor">{short(n.display)}</text></g>; })}
          <circle cx={cx} cy={cy} r="28" fill={KIND_COLOR[center?.kind]} /><text x={cx} y={cy + 4} fontSize="10" textAnchor="middle" fill="#fff">{short(center?.display || "")}</text>
        </svg>
        <p className="hint">{t.tapNode} · {Object.entries(KIND_COLOR).filter(([k]) => g.nodes.some((n) => n.kind === k)).map(([k, c]) => <span key={k} style={{ color: c }}>● {g.nodes.find((n) => n.kind === k)?.kind_label || k} </span>)}</p>
        <h5>{t.links}</h5>
        <ul className="plain">{g.edges.slice(0, 24).map((e, i) => <li key={i}>{e.text} <small className="hint">[{e.source}]</small></li>)}</ul>
        <p className="hint">{t.unrev}</p>
      </>}
    </Sheet>
  );
}

// ------------------------------------------------------------------ 4. learning coach
export function CoachSheet({ lang, profile, seed, onClose }) {
  const t = kn(lang);
  const [q, setQ] = useState(seed || "");
  const [les, setLes] = useState(null);
  const [picked, setPicked] = useState({});
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState("");
  async function make(question) {
    setErr(""); setPicked({}); setSaved(false);
    try { setLes(await post("/api/lessons/build", { question, profile: { main_crop: profile.main_crop }, history: load("km-lessons", []).slice(-8), lang })); }
    catch (e) { setLes(null); setErr(e.message || t.fail); }
  }
  useEffect(() => { make(q); }, []); // eslint-disable-line
  const total = les?.quiz.length || 0;
  const done = les && Object.keys(picked).length === total;
  const score = les ? les.quiz.filter((z) => picked[z.id] === z.answer_index).length : 0;
  useEffect(() => {
    if (done && !saved) { save("km-lessons", [...load("km-lessons", []), { topic: les.topic.id, score, total, at: new Date().toISOString().slice(0, 10) }].slice(-30)); setSaved(true); }
  }, [done]); // eslint-disable-line
  return (
    <Sheet title={"🎓 " + t.coach} onClose={onClose} close={t.close}>
      <div className="alert-form"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t.topic} aria-label={t.topic} onKeyDown={(e) => e.key === "Enter" && make(q)} /><button className="pill" onClick={() => make(q)}>{t.make}</button></div>
      {err && <p className="hint">{err}</p>}
      {les && <>
        <h4>{les.topic.name}</h4>
        <p className="hint">{les.level_why}</p>
        {les.sections.map((s, i) => <div key={i}><h5>{s.title}</h5><ul className="plain">{s.items.map((x, j) => <li key={j}>{x}</li>)}</ul></div>)}
        {les.quiz.map((z, qi) => (
          <div key={z.id} className="decision steady" style={{ display: "block" }}>
            <b>{qi + 1}. {z.q}</b>
            {z.options.map((o, oi) => {
              const chosen = picked[z.id] !== undefined, right = oi === z.answer_index;
              return <button key={oi} className="pill quiz-opt" disabled={chosen} style={{ display: "block", width: "100%", textAlign: "left", margin: "6px 0", background: chosen ? (right ? "#c8e6c9" : picked[z.id] === oi ? "#ffcdd2" : undefined) : undefined, color: chosen ? "#222" : undefined }} onClick={() => setPicked({ ...picked, [z.id]: oi })}>{o}</button>;
            })}
            {picked[z.id] !== undefined && <small className="hint">{picked[z.id] === z.answer_index ? "✅ " + les.right : "❌ " + z.explain}</small>}
          </div>
        ))}
        {done && <><p><b>{t.score.replace("{s}", score).replace("{t}", total)}</b></p><button className="pill" onClick={() => make(q)}>➡️ {t.next}</button></>}
        <p className="hint">{les.basis}</p>
      </>}
    </Sheet>
  );
}

// ------------------------------------------------------------------ 5. research assistant (documents stay on the phone)
const MAX_CHUNKS = 300;
export function ResearchSheet({ lang, onClose, toast }) {
  const t = kn(lang);
  const [docs, setDocs] = useState(() => load("km-research", []));
  const [q, setQ] = useState("");
  const [ans, setAns] = useState(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const commit = (d) => { if (save("km-research", d)) { setDocs(d); setErr(""); } else setErr(t.full); };
  const voice = useVoice(lang, (x) => setQ(x), toast);
  async function upload(e) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setBusy(t.loading); setErr("");
    try {
      const form = new FormData(); form.append("document", f, f.name);
      const r = await fetch("/api/research/ingest", { method: "POST", body: form });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || String(r.status));
      const used = docs.reduce((a, d) => a + d.chunks.length, 0);
      commit([...docs.filter((d) => d.title !== j.title), { title: j.title, chunks: j.chunks.slice(0, Math.max(0, MAX_CHUNKS - used)), at: new Date().toISOString().slice(0, 10) }]);
    } catch (x) { setErr(x.message); }
    setBusy("");
  }
  async function ask() {
    if (!q.trim()) return;
    setBusy(t.loading); setAns(null); setErr("");
    try { setAns(await post("/api/research/ask", { question: q, lang, chunks: docs.flatMap((d) => d.chunks).slice(0, MAX_CHUNKS) })); }
    catch (x) { setErr(x.message || t.fail); }
    setBusy("");
  }
  return (
    <Sheet title={"📚 " + t.res} onClose={onClose} close={t.close}>
      <label className="pill" style={{ display: "inline-block" }}>📎 {t.upload}<input type="file" accept=".pdf,.txt,.md,.html,.htm,application/pdf,text/plain" onChange={upload} style={{ display: "none" }} /></label>
      {busy && <p className="hint">{busy}</p>}
      {err && <p className="hint">{err}</p>}
      <h5>{t.docs}</h5>
      {!docs.length && <p className="hint">{t.noDoc}</p>}
      <ul className="plain">{docs.map((d) => <li key={d.title}>{d.title} <small className="hint">({d.chunks.length})</small> <button className="pill" onClick={() => commit(docs.filter((x) => x.title !== d.title))}>{t.remove}</button></li>)}</ul>
      <h5>{t.ask}</h5>
      <div className="alert-form"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t.askPh} aria-label={t.ask} onKeyDown={(e) => e.key === "Enter" && ask()} />
        <button className={"pill" + (voice.rec ? " live" : "")} onClick={voice.toggle} aria-label={t.speak}>{voice.rec ? "⏹" : "🎙️"}</button><button className="pill" onClick={ask} disabled={!docs.length}>{t.go || "Go"}</button></div>
      {ans && <div className="decision steady" style={{ display: "block" }}>
        <p style={{ whiteSpace: "pre-wrap" }}>{ans.answer}</p>
        {ans.mode && ans.mode !== "no-match" && ans.mode !== "no-documents" && <small className="hint">{ans.mode === "model" ? t.model : t.extract}</small>}
        {ans.passages?.length > 0 && <><h5>{t.passages}</h5>{ans.passages.map((p) => <blockquote key={p.n} style={{ margin: "6px 0", fontSize: 13 }}><b>[{p.n}]</b> {p.text}<br /><small className="hint">{p.title}{p.page ? `, p.${p.page}` : ""}</small></blockquote>)}</>}
      </div>}
    </Sheet>
  );
}

// ------------------------------------------------------------------ 6. field report from voice notes + photo
export function FieldReportSheet({ lang, profile, onClose, toast }) {
  const t = kn(lang);
  const [notes, setNotes] = useState(() => load("km-fnotes", []));
  const [txt, setTxt] = useState("");
  const [useScan, setUseScan] = useState(true);
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState("");
  const scan = getLastScan();
  const commit = (n) => { setNotes(n); save("km-fnotes", n); };
  const addNote = (text, source) => {                       // functional update: a voice note finishes seconds later, `notes` may have changed
    const s = String(text || "").trim();
    if (!s) return;
    setNotes((prev) => { const n = [...prev, { text: s.slice(0, 400), at: new Date().toISOString().slice(0, 16).replace("T", " "), source }].slice(-20); save("km-fnotes", n); return n; });
  };
  const voice = useVoice(lang, (x) => addNote(x, "voice"), toast);
  async function build() {
    setErr("");
    if (!notes.length && !(useScan && scan)) return setErr(t.noNotes);
    try {
      const tw = load("km-twin", null);
      setRep(await post("/api/fieldreport/build", { lang, notes, scan: useScan && scan ? scan : undefined, profile: { crop: profile.main_crop, place: profile.district, country: profile.country, sowing_date: profile.sowing_date }, twin: tw && tw.crop && tw.acres ? { ...tw, country: profile.country } : undefined }));
    } catch (e) { setErr(e.message || t.fail); }
  }
  const UR = { high: "#c62828", medium: "#ef6c00", low: "#2e7d32" };
  return (
    <Sheet title={"📋 " + t.fr} onClose={onClose} close={t.close}>
      <h5>{t.notes}</h5>
      <ul className="plain">{notes.map((n, i) => <li key={i}>{n.source === "voice" ? "🎙️" : "✍️"} {n.text} <button className="pill" onClick={() => commit(notes.filter((_, j) => j !== i))}>✕</button></li>)}</ul>
      <div className="alert-form"><input value={txt} onChange={(e) => setTxt(e.target.value)} maxLength={400} placeholder={t.note} aria-label={t.note} onKeyDown={(e) => { if (e.key === "Enter") { addNote(txt, "typed"); setTxt(""); } }} />
        <button className="pill" onClick={() => { addNote(txt, "typed"); setTxt(""); }}>{t.add}</button>
        <button className={"pill" + (voice.rec ? " live" : "")} onClick={voice.toggle}>{voice.rec ? "⏹ " + t.stop : "🎙️ " + t.speak}</button></div>
      {scan && <label className="check"><input type="checkbox" checked={useScan} onChange={(e) => setUseScan(e.target.checked)} /> {t.useScan} ({scan.severity_pct}%)</label>}
      <button className="pill primary" onClick={build}>{t.build}</button>
      {notes.length > 0 && <button className="pill" onClick={() => commit([])}>🗑️ {t.clear}</button>}
      {err && <p className="hint">{err}</p>}
      {rep && <div className="decision steady" style={{ display: "block" }}>
        <b>{rep.id}</b> · {rep.crop || "-"} · <span style={{ color: UR[rep.urgency], fontWeight: 700 }}>{t.urgency}: {rep.urgency.toUpperCase()}</span>
        {rep.symptoms.length > 0 && <p>{t.sym}: {rep.symptoms.map((s) => s.replace(/_/g, " ")).join(", ")}</p>}
        {rep.activities.length > 0 && <p>{t.act}: {rep.activities.join(", ")}</p>}
        {rep.possible_matches.length > 0 && <><h5>{t.match}</h5>{rep.possible_matches.map((m) => <div key={m.name}><b>{m.name}</b><ul className="plain">{m.what_to_do.map((x, i) => <li key={i}>{x}</li>)}</ul></div>)}</>}
        <h5>{t.steps}</h5><ul className="plain">{rep.safe_steps.map((x, i) => <li key={i}>{x}</li>)}</ul>
        <h5>{t.ask2}</h5><ul className="plain">{rep.questions_for_expert.map((x, i) => <li key={i}>{x}</li>)}</ul>
        <small className="hint">{t.by}: {rep.extraction}</small>
        <div className="alert-actions"><button className="pill" onClick={() => shareText(rep.summary_text)}>📤 {t.share}</button></div>
      </div>}
    </Sheet>
  );
}

// ------------------------------------------------------------------ 7. follow-ups on saved decisions (voice or tap)
export function FollowUps({ lang, toast }) {
  const t = kn(lang);
  const [list, setList] = useState([]);
  const target = useRef(null);                              // which follow-up the voice answer belongs to (a ref: the recording outlives this render)
  useEffect(() => {
    const recs = load("km-outcomes", []);
    if (!recs.length) return;
    post("/api/memory/followups", { records: recs, lang }).then((j) => setList(j.followups)).catch(() => {});
  }, [lang]);
  const patch = (id, change) => {
    save("km-outcomes", load("km-outcomes", []).map((r) => (r.id === id ? { ...r, ...change } : r)));
    setList((l) => l.filter((x) => x.id !== id));
  };
  const day = (n) => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10);
  const voice = useVoice(lang, (x) => { if (target.current) { patch(target.current, { done: true, followup_note: x.slice(0, 300) }); toast?.(t.saved); target.current = null; } }, toast);
  if (!list.length) return null;
  const f = list[0];
  return (
    <div className="decision steady" style={{ display: "block", margin: "10px 0" }}>
      <small className="hint">🔁 {t.fu}</small>
      <p>{f.question}</p>
      <div className="alert-actions">
        <button className="pill" onClick={() => { patch(f.id, { done: true }); toast?.(t.saved); }}>✅ {t.didIt}</button>
        <button className="pill" onClick={() => patch(f.id, { snoozed_until: day(3) })}>⏳ {t.notYet}</button>
        <button className={"pill" + (voice.rec ? " live" : "")} onClick={() => { target.current = f.id; voice.toggle(); }}>{voice.rec ? "⏹" : "🎙️ " + t.say}</button>
        <button className="pill" onClick={() => patch(f.id, { snoozed_until: day(45) })}>{t.skip}</button>
      </div>
    </div>
  );
}
