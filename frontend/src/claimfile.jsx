// Insurance evidence file and claim tracker. Evidence (photos, notes), checklist ticks and claim progress are kept on the phone;
// the server only renders a printable report. The app never promises approval: the insurer decides.
import { useState } from "react";
import { Sheet, shareText } from "./khata";

const STAGES = ["reported", "documents_submitted", "survey_done", "decision_waiting", "paid", "rejected"];
const S = {
  en: { btn: "Evidence file and claim tracker", title: "Claim file", needLoss: "First fill in the loss details in the crop-loss kit and tap Get kit.", policy: "Policy / application no.", complaint: "Complaint / reference no.", check: "Documents", ev: "Evidence",
        photo: "Add photo", note: "Add note", noteLabel: "What does this show?", save: "Save note", track: "Claim progress", stageSel: "Stage", date: "Date", noteP: "Note (who, what they said)", addStage: "Add to progress", download: "Download report (open and print as PDF)", share: "Share summary", close: "Close", remove: "Remove",
        stage: { reported: "Loss reported", documents_submitted: "Documents submitted", survey_done: "Field survey done", decision_waiting: "Waiting for decision", paid: "Claim paid", rejected: "Claim rejected" }, warn: "This organises your evidence. It does not guarantee approval: the insurer decides.", fail: "Could not make the report. Check the connection.", full: "Storage is full: remove a photo.", photos: "Photos in report" },
  te: { btn: "ఆధారాల ఫైల్, క్లెయిమ్ ట్రాకర్", title: "క్లెయిమ్ ఫైల్", needLoss: "ముందు పంట నష్టం కిట్‌లో వివరాలు నింపి Get kit నొక్కండి.", policy: "పాలసీ / దరఖాస్తు నం.", complaint: "ఫిర్యాదు / రిఫరెన్స్ నం.", check: "పత్రాలు", ev: "ఆధారాలు",
        photo: "ఫోటో చేర్చు", note: "గమనిక చేర్చు", noteLabel: "ఇది ఏమి చూపిస్తుంది?", save: "గమనిక సేవ్", track: "క్లెయిమ్ పురోగతి", stageSel: "దశ", date: "తేదీ", noteP: "గమనిక (ఎవరు, ఏమన్నారు)", addStage: "పురోగతికి చేర్చు", download: "రిపోర్ట్ డౌన్‌లోడ్ (తెరిచి PDF గా ప్రింట్ చేయండి)", share: "సారాంశం పంచుకో", close: "మూసివేయి", remove: "తొలగించు",
        stage: { reported: "నష్టం తెలియజేశారు", documents_submitted: "పత్రాలు సమర్పించారు", survey_done: "పొలం సర్వే అయింది", decision_waiting: "నిర్ణయం కోసం వేచి ఉన్నారు", paid: "క్లెయిమ్ చెల్లించారు", rejected: "క్లెయిమ్ తిరస్కరించారు" }, warn: "ఇది మీ ఆధారాలను క్రమబద్ధీకరిస్తుంది. ఆమోదానికి హామీ కాదు: బీమా సంస్థ నిర్ణయిస్తుంది.", fail: "రిపోర్ట్ రాలేదు. ఇంటర్నెట్ చూడండి.", full: "స్టోరేజ్ నిండింది: ఒక ఫోటో తొలగించండి.", photos: "రిపోర్ట్‌లో ఫోటోలు" },
  hi: { btn: "साक्ष्य फ़ाइल और क्लेम ट्रैकर", title: "क्लेम फ़ाइल", needLoss: "पहले फसल-नुकसान किट में विवरण भरें और Get kit दबाएँ।", policy: "पॉलिसी / आवेदन नं.", complaint: "शिकायत / संदर्भ नं.", check: "दस्तावेज़", ev: "साक्ष्य",
        photo: "फ़ोटो जोड़ें", note: "नोट जोड़ें", noteLabel: "यह क्या दिखाता है?", save: "नोट सेव", track: "क्लेम की प्रगति", stageSel: "चरण", date: "तारीख़", noteP: "नोट (किसने, क्या कहा)", addStage: "प्रगति में जोड़ें", download: "रिपोर्ट डाउनलोड (खोलकर PDF के रूप में प्रिंट करें)", share: "सारांश साझा करें", close: "बंद करें", remove: "हटाएँ",
        stage: { reported: "नुकसान की सूचना दी", documents_submitted: "दस्तावेज़ जमा किए", survey_done: "खेत का सर्वे हुआ", decision_waiting: "फ़ैसले का इंतज़ार", paid: "क्लेम मिला", rejected: "क्लेम अस्वीकृत" }, warn: "यह आपके साक्ष्य व्यवस्थित करता है। मंज़ूरी की गारंटी नहीं: फ़ैसला बीमा कंपनी करती है।", fail: "रिपोर्ट नहीं बनी। इंटरनेट देखें।", full: "स्टोरेज भर गया: एक फ़ोटो हटाएँ।", photos: "रिपोर्ट में फ़ोटो" },
};
export const cf = (lang) => S[lang] || S.en;
const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const KEY = "km-claimfile";

async function smallPhoto(file) {
  const bmp = await createImageBitmap(file);
  for (const [side, q] of [[640, 0.6], [480, 0.5], [360, 0.45]]) {
    const k = Math.min(1, side / Math.max(bmp.width, bmp.height));
    const c = document.createElement("canvas");
    c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    const url = c.toDataURL("image/jpeg", q);
    if (url.length <= 140000) return url;
  }
  return null;
}

export function ClaimFileSheet({ lang, profile, onClose }) {
  const t = cf(lang);
  const l = lang === "auto" ? "te" : lang;
  const claim = load("km-claim", null);
  const [d, setD] = useState(() => load(KEY, { policy_no: "", complaint_no: "", checks: {}, evidence: [], timeline: [] }));
  const [note, setNote] = useState("");
  const [st, setSt] = useState({ stage: "reported", date: new Date().toISOString().slice(0, 16), note: "" });
  const [err, setErr] = useState("");
  const put = (p) => {
    const n = { ...d, ...p };
    setD(n);
    try { localStorage.setItem(KEY, JSON.stringify(n)); setErr(""); } catch { setErr(t.full); }
  };
  if (!claim?.res || !claim?.form) return <Sheet title={"📁 " + t.title} onClose={onClose} close={t.close}><p className="warn-note">{t.needLoss}</p></Sheet>;
  const checklist = claim.res.checklist || [];

  async function addPhoto(ev) {
    const f = ev.target.files?.[0];
    if (!f) return;
    const url = await smallPhoto(f).catch(() => null);
    if (url) put({ evidence: [...d.evidence, { id: Math.random().toString(36).slice(2, 8), kind: "photo", label: f.name.slice(0, 60), taken_at: new Date().toISOString(), data_url: url }].slice(-12) });
    ev.target.value = "";
  }
  const body = () => ({ lang: l, profile, loss: { cause: claim.form.cause, occurred_at: new Date(claim.form.when).toISOString(), crop: claim.form.crop, acres: Number(claim.form.acres) || null },
    policy_no: d.policy_no, complaint_no: d.complaint_no, checklist: checklist.map((text, i) => ({ text, done: !!d.checks[i] })),
    evidence: d.evidence, timeline: d.timeline.map((x) => ({ ...x, date: new Date(x.date).toISOString() })), include_photos: true });
  async function post() {
    const r = await fetch("/api/claim/evidence", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body()) });
    if (!r.ok) throw new Error();
    return r.json();
  }
  async function download() {
    try {
      const j = await post();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([j.html], { type: "text/html" }));
      a.download = j.filename; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    } catch { setErr(t.fail); }
  }
  const last = d.timeline[d.timeline.length - 1];
  const summary = () => `${t.title}: ${claim.form.crop || ""}\n${checklist.filter((_, i) => d.checks[i]).length}/${checklist.length} ${t.check}\n${t.ev}: ${d.evidence.length}\n${last ? t.stage[last.stage] : ""}\n${d.complaint_no ? t.complaint + ": " + d.complaint_no : ""}`;

  return (
    <Sheet title={"📁 " + t.title} onClose={onClose} close={t.close}>
      <p className="warn-note">{t.warn}</p>
      <div className="alert-form">
        <input value={d.policy_no} onChange={(e) => put({ policy_no: e.target.value.slice(0, 40) })} placeholder={t.policy} aria-label={t.policy} />
        <input value={d.complaint_no} onChange={(e) => put({ complaint_no: e.target.value.slice(0, 40) })} placeholder={t.complaint} aria-label={t.complaint} />
      </div>
      <h5>{t.check}</h5>
      {checklist.map((c, i) => <label key={i} className="check"><input type="checkbox" checked={!!d.checks[i]} onChange={(e) => put({ checks: { ...d.checks, [i]: e.target.checked } })} /> {c}</label>)}
      <h5>{t.ev} ({d.evidence.length})</h5>
      <label className="pill">📷 {t.photo}<input type="file" accept="image/*" capture="environment" onChange={addPhoto} hidden /></label>
      <input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t.noteLabel} aria-label={t.noteLabel} maxLength={200} />
      <button className="pill" onClick={() => { if (note.trim()) { put({ evidence: [...d.evidence, { id: Math.random().toString(36).slice(2, 8), kind: "note", label: note.trim(), taken_at: new Date().toISOString() }].slice(-30) }); setNote(""); } }}>{t.save}</button>
      <ul className="plain">{d.evidence.map((e) => <li key={e.id}>{e.kind === "photo" ? <img src={e.data_url} alt="" style={{ height: 48, borderRadius: 6, verticalAlign: "middle", marginRight: 8 }} /> : "📝 "}{e.label} <button className="pill" onClick={() => put({ evidence: d.evidence.filter((x) => x.id !== e.id) })}>{t.remove}</button></li>)}</ul>
      <h5>{t.track}</h5>
      <select value={st.stage} onChange={(e) => setSt({ ...st, stage: e.target.value })} aria-label={t.stageSel}>{STAGES.map((s) => <option key={s} value={s}>{t.stage[s]}</option>)}</select>
      <input type="datetime-local" value={st.date} onChange={(e) => setSt({ ...st, date: e.target.value })} aria-label={t.date} />
      <input value={st.note} onChange={(e) => setSt({ ...st, note: e.target.value })} placeholder={t.noteP} aria-label={t.noteP} maxLength={300} />
      <button className="pill" onClick={() => { put({ timeline: [...d.timeline, st].sort((a, b) => a.date.localeCompare(b.date)).slice(-30) }); setSt({ ...st, note: "" }); }}>{t.addStage}</button>
      <ol className="plain">{d.timeline.map((x, i) => <li key={i}><b>{t.stage[x.stage]}</b> · {new Date(x.date).toLocaleString()}{x.note ? ` · ${x.note}` : ""}</li>)}</ol>
      {err && <p className="warn-note">{err}</p>}
      <button className="primary" onClick={download}>⬇️ {t.download}</button>
      <button className="pill" onClick={() => shareText(summary())}>{t.share}</button>
    </Sheet>
  );
}
