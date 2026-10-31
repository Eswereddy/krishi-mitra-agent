// Khata (voice farm ledger) and Crop-loss kit (PMFBY 72-hour rule). Both keep their data on the phone.
import { useEffect, useRef, useState } from "react";
import { startListening, extFor, unlockAudio } from "./lib/audio";
import { I } from "./components";

const CATS = ["seed", "fertilizer", "pesticide", "labour", "irrigation", "machinery", "transport", "rent", "other"];
const INCOME = ["sale", "subsidy", "other_income"];
const CAUSES = ["hailstorm", "flood_local", "landslide", "cloudburst", "fire", "post_harvest_rain", "other"];

const S = {
  te: {
    khata: "ఖాతా", khataSub: "మాట్లాడి ఖర్చులు, ఆదాయం రాసుకోండి", claim: "పంట నష్టం", claimSub: "72 గంటల గడువు, బీమా క్లెయిమ్ కిట్",
    say: "ఉదా: ₹1500 కు యూరియా కొన్నాను", add: "చేర్చు", income: "ఆదాయం", cost: "ఖర్చు", net: "నికరం", acres: "ఎకరాలు", report: "సీజన్ నివేదిక",
    confirm: "సరిచూసి సేవ్ చేయండి", check: "మొత్తం సరిచూడండి: మీ మాటల్లో ఆ సంఖ్య స్పష్టంగా లేదు.", save: "సేవ్", cancel: "రద్దు", amount: "మొత్తం ₹", crop: "పంట",
    empty: "ఇంకా ఏ ఎంట్రీ లేదు. 'యూరియా ₹1500' లేదా 'వేరుశనగ 8 క్వింటాళ్లు ₹7000 కు అమ్మాను' అని చెప్పండి.", noAmount: "మొత్తం అర్థం కాలేదు. మొత్తంతో మళ్లీ చెప్పండి.",
    share: "WhatsApp", copy: "కాపీ", csv: "CSV", copied: "కాపీ అయింది", close: "మూసివేయి", listening: "వింటున్నాను...", private: "ఈ రికార్డులు మీ ఫోన్‌లోనే ఉంటాయి.",
    cat: { seed: "విత్తనాలు", fertilizer: "ఎరువులు", pesticide: "మందులు", labour: "కూలీలు", irrigation: "నీటి తడి/ఇంధనం", machinery: "యంత్రాలు", transport: "రవాణా", rent: "కౌలు", other: "ఇతరం", sale: "అమ్మకం", subsidy: "సబ్సిడీ", other_income: "ఇతర ఆదాయం" },
    cause: { hailstorm: "వడగళ్ల వాన", flood_local: "స్థానిక వరద / నీరు నిలవడం", landslide: "కొండచరియలు", cloudburst: "మేఘ విస్ఫోటనం", fire: "అగ్నిప్రమాదం", post_harvest_rain: "కోసిన పంటకు తుఫాను/అకాల వర్షం", other: "కరువు, చీడపీడలు, ఇతరం" },
    whatHappened: "ఏమైంది?", when: "ఎప్పుడు జరిగింది?", getKit: "గడువు, సందేశం పొందండి", left: "గంటలు మిగిలాయి", expired: "72 గంటల గడువు ముగిసింది: అయినా వెంటనే బీమా కంపెనీకి/వ్యవసాయ అధికారికి తెలియజేసి అడగండి.",
    checklist: "సిద్ధం చేసుకోండి", how: "ఎలా తెలియజేయాలి", message: "సిద్ధమైన సందేశం", call: "కాల్ చేయండి", photosNote: "ఫోటోలను WhatsApp లో సందేశంతో పాటు జతచేయండి.", redo: "మళ్లీ లెక్కించు",
  },
  en: {
    khata: "Khata", khataSub: "Speak your costs and income", claim: "Crop loss", claimSub: "72-hour deadline and insurance claim kit",
    say: "e.g. bought urea for ₹1500", add: "Add", income: "Income", cost: "Cost", net: "Net", acres: "Acres", report: "Season report",
    confirm: "Check and save", check: "Please check the amount: that number was not clearly in your words.", save: "Save", cancel: "Cancel", amount: "Amount ₹", crop: "Crop",
    empty: "No entries yet. Say \"urea ₹1500\" or \"sold 8 quintals groundnut at 7000\".", noAmount: "I could not find an amount. Please say it again with the amount.",
    share: "WhatsApp", copy: "Copy", csv: "CSV", copied: "Copied", close: "Close", listening: "Listening...", private: "These records stay on your phone.",
    cat: { seed: "Seed", fertilizer: "Fertiliser", pesticide: "Spray", labour: "Labour", irrigation: "Irrigation/fuel", machinery: "Machinery", transport: "Transport", rent: "Land rent", other: "Other", sale: "Sale", subsidy: "Subsidy", other_income: "Other income" },
    cause: { hailstorm: "Hailstorm", flood_local: "Local flooding / water-logging", landslide: "Landslide", cloudburst: "Cloudburst", fire: "Fire", post_harvest_rain: "Cyclone/unseasonal rain on harvested crop", other: "Drought, pest, other" },
    whatHappened: "What happened?", when: "When did it happen?", getKit: "Get deadline and message", left: "hours left", expired: "The 72-hour window has passed: still report to the insurer or agriculture officer now and ask.",
    checklist: "Get ready", how: "How to report", message: "Ready message", call: "Call", photosNote: "Attach your photos with this message on WhatsApp.", redo: "Recalculate",
  },
  hi: {
    khata: "खाता", khataSub: "बोलकर खर्च और आमदनी लिखें", claim: "फसल नुकसान", claimSub: "72 घंटे की समय सीमा, बीमा क्लेम किट",
    say: "जैसे: ₹1500 की यूरिया खरीदी", add: "जोड़ें", income: "आमदनी", cost: "खर्च", net: "शुद्ध", acres: "एकड़", report: "सीज़न रिपोर्ट",
    confirm: "जाँचकर सेव करें", check: "रकम जाँच लें: यह संख्या आपके शब्दों में साफ़ नहीं थी।", save: "सेव", cancel: "रद्द", amount: "रकम ₹", crop: "फसल",
    empty: "अभी कोई एंट्री नहीं। बोलें \"यूरिया ₹1500\" या \"8 क्विंटल मूंगफली 7000 पर बेची\"।", noAmount: "रकम समझ नहीं आई। रकम के साथ फिर बोलें।",
    share: "WhatsApp", copy: "कॉपी", csv: "CSV", copied: "कॉपी हुआ", close: "बंद करें", listening: "सुन रहा हूँ...", private: "ये रिकॉर्ड आपके फ़ोन में ही रहते हैं।",
    cat: { seed: "बीज", fertilizer: "खाद", pesticide: "दवा", labour: "मज़दूरी", irrigation: "सिंचाई/ईंधन", machinery: "मशीन", transport: "ढुलाई", rent: "किराया", other: "अन्य", sale: "बिक्री", subsidy: "सब्सिडी", other_income: "अन्य आमदनी" },
    cause: { hailstorm: "ओलावृष्टि", flood_local: "स्थानीय बाढ़ / जलभराव", landslide: "भूस्खलन", cloudburst: "बादल फटना", fire: "आग", post_harvest_rain: "कटी फसल पर चक्रवात/बेमौसम बारिश", other: "सूखा, कीट, अन्य" },
    whatHappened: "क्या हुआ?", when: "कब हुआ?", getKit: "समय सीमा और संदेश पाएँ", left: "घंटे बचे", expired: "72 घंटे की सीमा निकल गई: फिर भी अभी बीमा कंपनी या कृषि अधिकारी को बताएँ और पूछें।",
    checklist: "तैयार रखें", how: "कैसे बताएँ", message: "तैयार संदेश", call: "कॉल करें", photosNote: "फ़ोटो को WhatsApp पर इस संदेश के साथ भेजें।", redo: "फिर से गिनें",
  },
};
export const kx = (lang) => S[lang] || S.en;
const rupee = (n) => (n < 0 ? "−₹" : "₹") + Math.abs(Math.round(n)).toLocaleString("en-IN");
const uid = () => Math.random().toString(36).slice(2, 9);
const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };
const post = (url, body) => fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

async function hearOnce() {
  unlockAudio();
  const l = startListening({ onLevel: () => {} });
  const blob = await l.promise;
  if (!blob) return "";
  const form = new FormData();
  form.append("audio", blob, `q.${extFor(blob.type)}`);
  const r = await fetch("/api/asr", { method: "POST", body: form });
  return r.ok ? (await r.json()).text : "";
}

function Sheet({ title, onClose, close, children }) {
  return (
    <div className="sheet-bg" onClick={onClose}>
      <div className="sheet tall" onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        {children}
        <button className="primary" onClick={onClose}>{close}</button>
      </div>
    </div>
  );
}

function shareText(text) { window.open("https://wa.me/?text=" + encodeURIComponent(text), "_blank"); }

export function KhataSheet({ lang, profile, onClose, toast }) {
  const t = kx(lang);
  const [entries, setEntries] = useState(() => load("km-khata", []));
  const [acres, setAcres] = useState(() => load("km-acres", ""));
  const [text, setText] = useState("");
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [hearing, setHearing] = useState(false);
  const [rep, setRep] = useState(null);
  const listener = useRef(null);
  useEffect(() => save("km-khata", entries), [entries]);
  useEffect(() => save("km-acres", acres), [acres]);

  const income = entries.filter((e) => e.type === "income").reduce((a, e) => a + e.amount_rs, 0);
  const cost = entries.filter((e) => e.type === "expense").reduce((a, e) => a + e.amount_rs, 0);

  async function parse(sentence) {
    if (!sentence.trim()) return;
    setBusy(true);
    try {
      const r = await post("/api/ledger/parse", { text: sentence, crop: profile.main_crop });
      const j = await r.json();
      if (j.error) toast(t.noAmount); else { setDraft(j); setText(""); }
    } catch { toast(t.noAmount); } finally { setBusy(false); }
  }
  async function speak() {
    if (hearing) return listener.current?.stop?.();
    setHearing(true);
    try { const said = await hearOnce(); if (said) await parse(said); } catch { /* mic denied */ } finally { setHearing(false); }
  }
  function saveDraft() {
    const amount = Number(draft.amount_rs);
    if (!(amount > 0)) return;
    setEntries((l) => [{ ...draft, amount_rs: Math.round(amount), id: uid() }, ...l].slice(0, 500));
    setDraft(null); setRep(null);
  }
  async function makeReport() {
    const r = await post("/api/ledger/report", { entries, acres: Number(acres) || null, lang });
    setRep(await r.json());
  }
  function csv() {
    const rows = [["date", "type", "category", "amount_rs", "quantity_q", "crop", "note"], ...entries.map((e) => [e.date, e.type, e.category, e.amount_rs, e.quantity_q ?? "", e.crop, `"${(e.note || "").replace(/"/g, "'")}"`])];
    const url = URL.createObjectURL(new Blob([rows.map((r) => r.join(",")).join("\n")], { type: "text/csv" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "krishi-mitra-khata.csv" });
    a.click(); URL.revokeObjectURL(url);
  }

  return (
    <Sheet title={"📒 " + t.khata} onClose={onClose} close={t.close}>
      <div className="stats">
        <div><small>{t.income}</small><b className="pos">{rupee(income)}</b></div>
        <div><small>{t.cost}</small><b>{rupee(cost)}</b></div>
        <div className="stat-profit"><small>{t.net}</small><b className={income - cost >= 0 ? "pos" : "neg"}>{rupee(income - cost)}</b></div>
      </div>
      {draft ? (
        <div className="khata-draft">
          <b>{t.confirm}</b>
          {!draft.amount_in_words && <p className="warn-note">⚠️ {t.check}</p>}
          <div className="alert-form">
            <select value={draft.type} onChange={(e) => setDraft({ ...draft, type: e.target.value, category: e.target.value === "income" ? "sale" : "other" })}>
              <option value="expense">{t.cost}</option><option value="income">{t.income}</option>
            </select>
            <select value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })}>
              {(draft.type === "income" ? INCOME : CATS).map((c) => <option key={c} value={c}>{t.cat[c]}</option>)}
            </select>
          </div>
          <div className="alert-form">
            <input type="number" inputMode="numeric" value={draft.amount_rs} onChange={(e) => setDraft({ ...draft, amount_rs: e.target.value })} placeholder={t.amount} aria-label={t.amount} />
            <input value={draft.crop || ""} onChange={(e) => setDraft({ ...draft, crop: e.target.value })} placeholder={t.crop} aria-label={t.crop} />
          </div>
          <div className="alert-actions"><button className="pill" onClick={() => setDraft(null)}>{t.cancel}</button><button className="pill live" onClick={saveDraft}>✓ {t.save}</button></div>
        </div>
      ) : (
        <div className="khata-add">
          <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && parse(text)} placeholder={hearing ? t.listening : t.say} aria-label={t.say} disabled={busy} />
          <button className="round" aria-label={t.add} onClick={() => parse(text)} disabled={busy || !text.trim()}><I.send /></button>
          <button className={"round" + (hearing ? " stop" : "")} aria-label="mic" onClick={speak} disabled={busy}>{hearing ? <I.stop /> : <I.mic />}</button>
        </div>
      )}
      <label>{t.acres}<input type="number" inputMode="decimal" min="0" value={acres} onChange={(e) => setAcres(e.target.value)} placeholder="2" /></label>
      {entries.length === 0 && !draft && <p className="hint">{t.empty}</p>}
      <div className="khata-list">
        {entries.slice(0, 30).map((e) => (
          <div className="alert-row" key={e.id}>
            <div><b className={e.type === "income" ? "pos" : ""}>{e.type === "income" ? "+" : "−"}{rupee(e.amount_rs).replace("−", "")}</b> · {t.cat[e.category]}
              <small>{[e.date, e.crop, e.quantity_q ? `${e.quantity_q} q` : ""].filter(Boolean).join(" · ")}</small></div>
            <span />
            <button className="icon-btn sm" aria-label="delete" onClick={() => setEntries((l) => l.filter((x) => x.id !== e.id))}><I.x /></button>
          </div>
        ))}
      </div>
      {entries.length > 0 && <button className="pill" onClick={makeReport}>📄 {t.report}</button>}
      {rep && (
        <div className="khata-report">
          <pre>{rep.text}</pre>
          <div className="alert-actions">
            <button className="pill" onClick={() => shareText(rep.text)}><I.whatsapp />{t.share}</button>
            <button className="pill" onClick={() => navigator.clipboard?.writeText(rep.text).then(() => toast(t.copied))}><I.copy />{t.copy}</button>
            <button className="pill" onClick={csv}>⬇️ {t.csv}</button>
          </div>
        </div>
      )}
      <p className="hint">🔒 {t.private}</p>
    </Sheet>
  );
}

export function ClaimSheet({ lang, profile, onClose, toast }) {
  const t = kx(lang);
  const saved = load("km-claim", null);
  const nowLocal = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  const [form, setForm] = useState(saved?.form || { cause: "hailstorm", when: nowLocal(), crop: profile.main_crop || "", acres: "" });
  const [res, setRes] = useState(saved?.res || null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(id); }, []);

  async function run() {
    const body = { profile, lang, loss: { cause: form.cause, occurred_at: new Date(form.when).toISOString(), crop: form.crop, acres: Number(form.acres) || null } };
    try {
      const r = await post("/api/claim/draft", body);
      const j = await r.json();
      setRes(j); save("km-claim", { form, res: j });
    } catch { /* offline: keep the old result */ }
  }
  const hoursLeft = res?.deadline ? Math.max(0, (new Date(res.deadline).getTime() - now) / 3600000) : null;
  const status = res?.status === "area_level" ? "area_level" : hoursLeft === 0 ? "expired" : hoursLeft != null && hoursLeft <= 24 ? "urgent" : "open";

  return (
    <Sheet title={"🌧️ " + t.claim} onClose={onClose} close={t.close}>
      <label>{t.whatHappened}
        <select value={form.cause} onChange={(e) => setForm({ ...form, cause: e.target.value })}>{CAUSES.map((c) => <option key={c} value={c}>{t.cause[c]}</option>)}</select>
      </label>
      <label>{t.when}<input type="datetime-local" value={form.when} max={nowLocal()} onChange={(e) => setForm({ ...form, when: e.target.value })} /></label>
      <div className="alert-form">
        <input value={form.crop} onChange={(e) => setForm({ ...form, crop: e.target.value })} placeholder={t.crop} aria-label={t.crop} />
        <input type="number" inputMode="decimal" value={form.acres} onChange={(e) => setForm({ ...form, acres: e.target.value })} placeholder={t.acres} aria-label={t.acres} />
      </div>
      <button className="primary" onClick={run}>{res ? t.redo : t.getKit}</button>
      {res && (
        <div className="claim-out">
          {hoursLeft != null && (
            <div className={"decision " + (status === "expired" || status === "urgent" ? "falling" : "rising")}>
              <b>{status === "expired" ? "⛔ " + t.expired : `⏱️ ${Math.floor(hoursLeft)} ${t.left}`}</b>
            </div>
          )}
          <p className={status === "area_level" ? "hint" : "warn-note"}>{res.guidance}</p>
          <h5>{t.checklist}</h5>
          <ul>{res.checklist.map((c) => <li key={c}>{c}</li>)}</ul>
          {res.individual_claim && <><h5>{t.how}</h5><p className="hint">{res.how}</p></>}
          <div className="alert-actions">
            <a className="pill" href={`tel:${res.helplines.pmfby}`}>📞 {t.call} {res.helplines.pmfby}</a>
            <a className="pill" href={`tel:${res.helplines.kisan_call_centre.replace(/-/g, "")}`}>☎️ {res.helplines.kisan_call_centre}</a>
          </div>
          <h5>{t.message}</h5>
          <pre className="claim-msg">{res.message}</pre>
          <p className="hint">📷 {t.photosNote}</p>
          <div className="alert-actions">
            <button className="pill" onClick={() => shareText(res.message)}><I.whatsapp />{t.share}</button>
            <button className="pill" onClick={() => navigator.clipboard?.writeText(res.message).then(() => toast(t.copied))}><I.copy />{t.copy}</button>
          </div>
        </div>
      )}
    </Sheet>
  );
}
