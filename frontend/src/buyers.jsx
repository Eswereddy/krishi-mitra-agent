// Buyer offers: enter what buyers offered, see the NET income of each (after commission, transport, other costs), with
// honest verified/unverified labels and risk flags. Offers stay on the phone; the server only does the arithmetic.
import { useEffect, useState } from "react";
import { Sheet, shareText } from "./khata";

const S = {
  en: { title: "Compare buyers", sub: "Net income per offer", qty: "Quantity", unit: { quintal: "quintal", kg: "kg", tonne: "tonne" }, ref: "Your reference price (optional)", buyer: "Buyer name", price: "Offered price per unit", comm: "Commission %", trans: "Transport cost (total)", other: "Other costs", days: "Payment after (days)",
        adv: "Asks for advance / deposit", reg: "Verified buyer (registry)", none: "Not in registry (unverified)", add: "Add offer", compare: "Compare", remove: "Remove", share: "Share", close: "Close", fail: "Enter quantity and at least one offer with a price. Needs a connection.", ver: "✅ Verified", unver: "⚠️ Unverified", best: "Best net", offers: "Offers" },
  te: { title: "కొనుగోలుదారులను పోల్చండి", sub: "ప్రతి ఆఫర్ నికర ఆదాయం", qty: "పరిమాణం", unit: { quintal: "క్వింటాల్", kg: "కిలో", tonne: "టన్ను" }, ref: "మీ రిఫరెన్స్ ధర (ఐచ్ఛికం)", buyer: "కొనుగోలుదారు పేరు", price: "యూనిట్‌కు ఇచ్చిన ధర", comm: "కమీషన్ %", trans: "రవాణా ఖర్చు (మొత్తం)", other: "ఇతర ఖర్చులు", days: "చెల్లింపు (రోజుల తర్వాత)",
        adv: "అడ్వాన్స్ / డిపాజిట్ అడుగుతున్నారు", reg: "ధృవీకరించిన కొనుగోలుదారు (రిజిస్ట్రీ)", none: "రిజిస్ట్రీలో లేరు (ధృవీకరించలేదు)", add: "ఆఫర్ చేర్చు", compare: "పోల్చు", remove: "తొలగించు", share: "పంచుకో", close: "మూసివేయి", fail: "పరిమాణం, ధరతో కనీసం ఒక ఆఫర్ ఇవ్వండి. ఇంటర్నెట్ కావాలి.", ver: "✅ ధృవీకరించబడింది", unver: "⚠️ ధృవీకరించలేదు", best: "ఉత్తమ నికరం", offers: "ఆఫర్లు" },
  hi: { title: "खरीदारों की तुलना", sub: "हर ऑफ़र की शुद्ध आय", qty: "मात्रा", unit: { quintal: "क्विंटल", kg: "किलो", tonne: "टन" }, ref: "आपका संदर्भ भाव (वैकल्पिक)", buyer: "खरीदार का नाम", price: "प्रति इकाई ऑफ़र कीमत", comm: "कमीशन %", trans: "ढुलाई खर्च (कुल)", other: "अन्य खर्च", days: "भुगतान (कितने दिन बाद)",
        adv: "अग्रिम / जमा माँग रहा है", reg: "सत्यापित खरीदार (रजिस्ट्री)", none: "रजिस्ट्री में नहीं (असत्यापित)", add: "ऑफ़र जोड़ें", compare: "तुलना करें", remove: "हटाएँ", share: "साझा करें", close: "बंद करें", fail: "मात्रा और कीमत वाला कम से कम एक ऑफ़र डालें। इंटरनेट चाहिए।", ver: "✅ सत्यापित", unver: "⚠️ असत्यापित", best: "सबसे अच्छा शुद्ध", offers: "ऑफ़र" },
};
export const bx = (lang) => S[lang] || S.en;
const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };
const KEY = "km-offers";
const EMPTY = { buyer: "", buyer_id: "", price: "", commission_pct: "", transport_cost: "", other_costs: "", payment_days: "", asks_advance: false };

export function BuyersSheet({ lang, profile, onClose }) {
  const t = bx(lang);
  const l = lang === "auto" ? "te" : lang;
  const saved = load(KEY, {});
  const [offers, setOffers] = useState(saved.offers || []);
  const [form, setForm] = useState(EMPTY);
  const [qty, setQty] = useState(saved.qty || "");
  const [unit, setUnit] = useState(saved.unit || "quintal");
  const [ref, setRef] = useState(saved.ref || "");
  const [reg, setReg] = useState([]);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { fetch("/api/buyers/registry").then((r) => r.json()).then((j) => setReg(j.verified || [])).catch(() => {}); }, []);
  useEffect(() => save(KEY, { offers, qty, unit, ref }), [offers, qty, unit, ref]);
  const f = (k, label, type = "number") => <input type={type} inputMode={type === "number" ? "decimal" : undefined} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} placeholder={label} aria-label={label} />;

  function add() {
    if (!(Number(form.price) > 0)) return;
    const name = form.buyer || reg.find((b) => b.id === form.buyer_id)?.name || "";
    setOffers([...offers, { ...form, buyer: name, id: Math.random().toString(36).slice(2, 7) }].slice(-10));
    setForm(EMPTY);
  }
  async function run() {
    setErr("");
    try {
      const r = await fetch("/api/buyers/compare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ offers, quantity: Number(qty), unit, reference_price: ref ? Number(ref) : null, lang: l, currency: profile.country === "IN" ? "₹" : "" }) });
      if (!r.ok) throw new Error();
      setRes(await r.json());
    } catch { setErr(t.fail); }
  }

  return (
    <Sheet title={"🤝 " + t.title} onClose={onClose} close={t.close}>
      <div className="alert-form">
        <input type="number" inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} placeholder={t.qty} aria-label={t.qty} />
        <select value={unit} onChange={(e) => setUnit(e.target.value)} aria-label="unit">{Object.keys(t.unit).map((u) => <option key={u} value={u}>{t.unit[u]}</option>)}</select>
      </div>
      <input type="number" inputMode="decimal" value={ref} onChange={(e) => setRef(e.target.value)} placeholder={t.ref} aria-label={t.ref} />
      <h5>{t.offers}</h5>
      {f("buyer", t.buyer, "text")}
      {reg.length > 0 && <select value={form.buyer_id} onChange={(e) => setForm({ ...form, buyer_id: e.target.value })} aria-label={t.reg}><option value="">{t.none}</option>{reg.map((b) => <option key={b.id} value={b.id}>✅ {b.name}</option>)}</select>}
      <div className="alert-form">{f("price", t.price)}{f("commission_pct", t.comm)}</div>
      <div className="alert-form">{f("transport_cost", t.trans)}{f("other_costs", t.other)}</div>
      {f("payment_days", t.days)}
      <label className="check"><input type="checkbox" checked={form.asks_advance} onChange={(e) => setForm({ ...form, asks_advance: e.target.checked })} /> {t.adv}</label>
      <button className="pill" onClick={add}>{t.add}</button>
      {offers.length > 0 && <ul className="plain">{offers.map((o) => <li key={o.id}>{o.buyer || "?"}: {o.price} <button className="pill" onClick={() => setOffers(offers.filter((x) => x.id !== o.id))}>{t.remove}</button></li>)}</ul>}
      <button className="primary" onClick={run} disabled={!offers.length}>{t.compare}</button>
      {err && <p className="warn-note">{err}</p>}
      {res && (
        <div className="claim-out">
          {res.offers.map((o, i) => (
            <div key={i} className={"decision " + (o.status === "verified" ? "rising" : "steady")} style={{ display: "block" }}>
              <b>{i === 0 ? "🏆 " : ""}{o.buyer} · {o.status === "verified" ? t.ver : t.unver}</b>
              <p>{o.net_text}</p>
              <ul className="plain">{o.notes.map((n, j) => <li key={j} className={o.flags.length && j > 0 ? "warn-note" : ""}>{n}</li>)}</ul>
            </div>
          ))}
          <p className="hint">{res.note}</p>
          <button className="pill" onClick={() => shareText(res.text)}>{t.share}</button>
        </div>
      )}
    </Sheet>
  );
}
