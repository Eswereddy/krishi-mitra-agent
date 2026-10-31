// Cards for the everyday farm-problem tools: grain storage, livestock heat, loan cost, fertiliser value, break-even.
const F = {
  en: {
    storage: "Grain storage", dry: "Dry enough to store", wet: "Too wet to store", moisture: "Moisture", safe: "Safe up to", dryMore: "Dry by another", pts: "points",
    dryDays: "Good drying days", noDry: "No good drying day in the next 5 days", damp: "Damp air: use clean, airtight bags or drums and keep them off the floor.",
    heat: "Livestock heat", stress: { none: "No heat stress", mild: "Mild stress", moderate: "Moderate stress", severe: "Severe stress", emergency: "Emergency" },
    worst: "Worst day", acts: { shade_and_air: "Give shade and airflow", clean_cool_water: "Clean, cool water always available", feed_in_cool_hours: "Feed in the cool hours", no_midday_work_or_walking: "No midday work or long walking" },
    loan: "Loan comparison", cheapest: "Cheapest", real: "Real yearly rate", total: "You repay", interest: "Interest", fees: "Fees", month: "per month",
    inputs: "Fertiliser value", perKgN: "per kg N", perKgP: "per kg P₂O₅", perKgK: "per kg K₂O", bestFor: "Best value",
    be: "Break-even price", need: "Needed per", margin: "With margin of", cost: "Total cost", qty: "Expected quantity",
    foot: "Guide only. Ask your local extension officer.",
  },
  te: {
    storage: "ధాన్యం నిల్వ", dry: "నిల్వకు సరిపడా ఆరింది", wet: "నిల్వకు ఇంకా తడిగా ఉంది", moisture: "తేమ", safe: "సురక్షిత పరిమితి", dryMore: "ఇంకా ఆరబెట్టాలి", pts: "పాయింట్లు",
    dryDays: "ఆరబెట్టడానికి మంచి రోజులు", noDry: "రాబోయే 5 రోజుల్లో ఆరబెట్టడానికి మంచి రోజు లేదు", damp: "గాలిలో తేమ ఎక్కువ: శుభ్రమైన, గాలి చొరని సంచులు లేదా డ్రమ్ములు వాడండి, నేలపై పెట్టవద్దు.",
    heat: "పశువులకు వేడి", stress: { none: "వేడి ఒత్తిడి లేదు", mild: "కొద్ది ఒత్తిడి", moderate: "మధ్యస్థ ఒత్తిడి", severe: "తీవ్ర ఒత్తిడి", emergency: "అత్యవసరం" },
    worst: "అత్యంత కష్టమైన రోజు", acts: { shade_and_air: "నీడ, గాలి ఉండేలా చూడండి", clean_cool_water: "శుభ్రమైన, చల్లని నీరు ఎప్పుడూ ఉంచండి", feed_in_cool_hours: "చల్లని వేళల్లో మేత పెట్టండి", no_midday_work_or_walking: "మధ్యాహ్నం పని, దూర నడక వద్దు" },
    loan: "రుణాల పోలిక", cheapest: "అతి తక్కువ ఖర్చు", real: "అసలు వార్షిక వడ్డీ", total: "మీరు చెల్లించేది", interest: "వడ్డీ", fees: "ఫీజులు", month: "నెలకు",
    inputs: "ఎరువు విలువ", perKgN: "కిలో N కు", perKgP: "కిలో P₂O₅ కు", perKgK: "కిలో K₂O కు", bestFor: "ఉత్తమ విలువ",
    be: "నష్టం లేని ధర", need: "ఒక్కొక్కదానికి కావాల్సింది", margin: "మార్జిన్ తో", cost: "మొత్తం ఖర్చు", qty: "ఆశించే పరిమాణం",
    foot: "మార్గదర్శకం మాత్రమే. స్థానిక వ్యవసాయ అధికారిని అడగండి.",
  },
  hi: {
    storage: "अनाज भंडारण", dry: "भंडारण के लिए सूखा है", wet: "भंडारण के लिए अभी गीला है", moisture: "नमी", safe: "सुरक्षित सीमा", dryMore: "और सुखाएँ", pts: "अंक",
    dryDays: "सुखाने के अच्छे दिन", noDry: "अगले 5 दिन सुखाने के लिए अच्छे नहीं", damp: "हवा में नमी है: साफ़, हवा-बंद बोरे या ड्रम इस्तेमाल करें, ज़मीन से ऊपर रखें।",
    heat: "पशुओं की गर्मी", stress: { none: "गर्मी का तनाव नहीं", mild: "हल्का तनाव", moderate: "मध्यम तनाव", severe: "गंभीर तनाव", emergency: "आपातकाल" },
    worst: "सबसे मुश्किल दिन", acts: { shade_and_air: "छाया और हवा दें", clean_cool_water: "साफ़, ठंडा पानी हमेशा रखें", feed_in_cool_hours: "ठंडे समय में चारा दें", no_midday_work_or_walking: "दोपहर में काम या लंबी पैदल दूरी नहीं" },
    loan: "कर्ज़ की तुलना", cheapest: "सबसे सस्ता", real: "असली सालाना दर", total: "आप चुकाएँगे", interest: "ब्याज", fees: "शुल्क", month: "प्रति माह",
    inputs: "खाद का मूल्य", perKgN: "प्रति किलो N", perKgP: "प्रति किलो P₂O₅", perKgK: "प्रति किलो K₂O", bestFor: "सबसे बढ़िया मूल्य",
    be: "बराबरी का भाव", need: "प्रति इकाई चाहिए", margin: "मुनाफ़े के साथ", cost: "कुल लागत", qty: "अपेक्षित मात्रा",
    foot: "सिर्फ़ मार्गदर्शन। स्थानीय कृषि अधिकारी से पूछें।",
  },
};
F.en.disease = { title: "Disease weather watch", risk: { low: "Low risk", moderate: "Watch the crop", high: "High risk" }, wet: "humid hours", blight: "Late-blight conditions: look at leaves every day and ask your officer.", acts: { scout_leaves: "Walk the field and check leaves (also the underside)", avoid_overhead_irrigation_evening: "Avoid watering leaves late in the evening", improve_airflow: "Keep rows open and remove dense weeds for airflow", ask_officer_if_spots: "If you see spots or mould, send a photo or ask your officer" } };
F.te.disease = { title: "తెగులు వాతావరణ హెచ్చరిక", risk: { low: "తక్కువ ప్రమాదం", moderate: "పంటను గమనించండి", high: "ఎక్కువ ప్రమాదం" }, wet: "తేమ గంటలు", blight: "ఆకుమాడు తెగులుకు అనుకూల వాతావరణం: ప్రతిరోజూ ఆకులు చూడండి, అధికారిని అడగండి.", acts: { scout_leaves: "పొలం తిరిగి ఆకులను (అడుగు భాగం కూడా) చూడండి", avoid_overhead_irrigation_evening: "సాయంత్రం ఆలస్యంగా ఆకులపై నీరు పోయవద్దు", improve_airflow: "వరుసల మధ్య గాలి తగిలేలా కలుపు తీయండి", ask_officer_if_spots: "మచ్చలు లేదా బూజు కనిపిస్తే ఫోటో పంపండి లేదా అధికారిని అడగండి" } };
F.hi.disease = { title: "रोग मौसम चेतावनी", risk: { low: "कम जोखिम", moderate: "फसल पर नज़र रखें", high: "ज़्यादा जोखिम" }, wet: "नम घंटे", blight: "झुलसा रोग के अनुकूल मौसम: रोज़ पत्तियाँ देखें, अधिकारी से पूछें।", acts: { scout_leaves: "खेत में घूमकर पत्तियाँ (नीचे की तरफ़ भी) देखें", avoid_overhead_irrigation_evening: "शाम को देर से पत्तियों पर पानी न डालें", improve_airflow: "कतारों में हवा के लिए खरपतवार हटाएँ", ask_officer_if_spots: "धब्बे या फफूँद दिखे तो फोटो भेजें या अधिकारी से पूछें" } };
const num = (n) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
const lg = (t) => F[t.code] || F.en;

export function StorageCard({ step, t }) {
  const r = step.result || {}, L = lg(t);
  if (r.safe_to_store == null) return null;
  return (
    <div className="card">
      <div className="card-head"><span>🌾 {L.storage} · {r.crop}</span>{r.place && <span className="badge badge-ok">{r.place}</span>}</div>
      <div className={"decision " + (r.safe_to_store ? "rising" : "falling")}><b>{r.safe_to_store ? "✅ " + L.dry : "⚠️ " + L.wet}</b></div>
      <div className="stats">
        <div><small>{L.moisture}</small><b>{r.moisture_pct}%</b></div>
        <div><small>{L.safe}</small><b>{r.safe_max_moisture_pct}%</b></div>
        {!r.safe_to_store && <div><small>{L.dryMore}</small><b>{r.points_to_dry} {L.pts}</b></div>}
      </div>
      {r.good_drying_days && <p className="hint">☀️ {r.good_drying_days.length ? `${L.dryDays}: ${r.good_drying_days.join(", ")}` : L.noDry}</p>}
      {r.damp_air && <p className="hint">💧 {L.damp}</p>}
      {r.warning && <p className="warn-note">⚠️ {r.warning}</p>}
      <div className="card-foot">{L.foot}</div>
    </div>
  );
}

export function HeatCard({ step, t }) {
  const r = step.result || {}, L = lg(t);
  if (!r.days) return null;
  const cls = (s) => (s === "none" ? "rising" : s === "mild" || s === "moderate" ? "steady" : "falling");
  return (
    <div className="card">
      <div className="card-head"><span>🐄 {L.heat} · {r.animal}</span><span className="badge badge-ok">{r.place}</span></div>
      <div className={"decision " + cls(r.worst_stress)}><b>{L.stress[r.worst_stress]}</b> <small>· {L.worst}: {r.worst_day}</small></div>
      <div className="rows">
        {r.days.map((d) => (
          <div className="row" key={d.date}>
            <div className="row-main"><b>{d.date}</b><small>{d.max_c}°C{d.thi != null ? ` · THI ${d.thi}` : ""}</small></div>
            <div className="row-price"><small>{L.stress[d.stress]}</small></div>
          </div>
        ))}
      </div>
      {r.actions?.length > 0 && <ul className="plain">{r.actions.map((a) => <li key={a}>{L.acts[a]}</li>)}</ul>}
      <div className="card-foot">{r.note}</div>
    </div>
  );
}

export function LoanCard({ step, t }) {
  const r = step.result || {}, L = lg(t);
  if (!r.offers) return null;
  return (
    <div className="card">
      <div className="card-head"><span>🏦 {L.loan}</span><span className="badge badge-ok">{L.cheapest}: {r.cheapest}</span></div>
      <div className="rows">
        {r.offers.map((o, i) => (
          <div className="row" key={i}>
            <div className="row-main"><b>{o.name}</b><small>{L.total} {num(o.total_repay)} · {L.interest} {num(o.total_interest)}{o.fees ? ` · ${L.fees} ${num(o.fees)}` : ""} · {num(o.monthly_payment)} {L.month}</small></div>
            <div className="row-price"><b className={i === 0 ? "pos" : o.effective_annual_rate_pct > 60 ? "neg" : ""}>{o.effective_annual_rate_pct}%</b><small>{L.real}</small></div>
          </div>
        ))}
      </div>
      <div className="card-foot">{r.note}</div>
    </div>
  );
}

export function InputsCard({ step, t }) {
  const r = step.result || {}, L = lg(t);
  if (!r.products) return null;
  const parts = [["n", L.perKgN], ["p2o5", L.perKgP], ["k2o", L.perKgK]];
  return (
    <div className="card">
      <div className="card-head"><span>🧪 {L.inputs}</span></div>
      <div className="rows">
        {r.products.map((p, i) => (
          <div className="row" key={i}>
            <div className="row-main"><b>{p.name}</b><small>{num(p.price_per_bag)} / {p.bag_kg} kg</small></div>
            <div className="row-price">{parts.filter(([k]) => p[`cost_per_kg_${k}`] != null).map(([k, lab]) => <small key={k}>{num(p[`cost_per_kg_${k}`])} {lab}{r.cheapest_per_nutrient?.[k] === p.name ? " ✅" : ""}</small>)}</div>
          </div>
        ))}
      </div>
      <div className="card-foot">{r.note}</div>
    </div>
  );
}

export function BreakevenCard({ step, t }) {
  const r = step.result || {}, L = lg(t);
  if (r.breakeven_price_per_unit == null) return null;
  return (
    <div className="card">
      <div className="card-head"><span>⚖️ {L.be}</span></div>
      <div className="stats">
        <div><small>{L.cost}</small><b>{num(r.total_cost)}</b></div>
        <div><small>{L.qty}</small><b>{num(r.expected_quantity)} {r.unit}</b></div>
        <div className="stat-profit"><small>{L.need} {r.unit}</small><b>{num(r.breakeven_price_per_unit)}</b></div>
        <div><small>{L.margin} {r.target_margin_pct}%</small><b>{num(r.price_for_margin_per_unit)}</b></div>
      </div>
      <div className="card-foot">{r.note}</div>
    </div>
  );
}

export function DiseaseCard({ step, t }) {
  const r = step.result || {}, L = lg(t).disease || F.en.disease;
  if (!r.days) return null;
  const cls = (k) => (k === "low" ? "rising" : k === "moderate" ? "steady" : "falling");
  return (
    <div className="card">
      <div className="card-head"><span>🍄 {L.title} · {r.crop}</span><span className="badge badge-ok">{r.place}</span></div>
      <div className={"decision " + cls(r.worst_risk)}><b>{L.risk[r.worst_risk]}</b> <small>· {r.worst_day}</small></div>
      <div className="rows">
        {r.days.map((d) => (
          <div className="row" key={d.date}>
            <div className="row-main"><b>{d.date}</b><small>{d.wet_hours} {L.wet}</small></div>
            <div className="row-price"><small>{L.risk[d.risk]}</small></div>
          </div>
        ))}
      </div>
      {r.late_blight_period && <p className="warn-note">⚠️ {L.blight}</p>}
      {r.actions?.length > 0 && <ul className="plain">{r.actions.map((a) => <li key={a}>{L.acts[a]}</li>)}</ul>}
      <div className="card-foot">{r.note}</div>
    </div>
  );
}

const MONTHS = {
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  te: ["జన", "ఫిబ్ర", "మార్చి", "ఏప్రి", "మే", "జూన్", "జూలై", "ఆగ", "సెప్టెం", "అక్టో", "నవం", "డిసెం"],
  hi: ["जन", "फ़र", "मार्च", "अप्रै", "मई", "जून", "जुला", "अग", "सित", "अक्टू", "नव", "दिस"],
};
const SZ = {
  en: { title: "Best months to sell", high: "Usually highest", low: "Usually lowest", gap: "Gap between best and worst month", note: "Past pattern at one market, not a forecast. Storing pays only if the gap is bigger than your storage cost, losses and interest.", idx: "100 = yearly average" },
  te: { title: "అమ్మడానికి మంచి నెలలు", high: "సాధారణంగా ఎక్కువ ధర", low: "సాధారణంగా తక్కువ ధర", gap: "మంచి, చెడ్డ నెల మధ్య తేడా", note: "ఒక మార్కెట్ లో గత ధోరణి మాత్రమే, ఫోర్కాస్ట్ కాదు. నిల్వ ఖర్చు, నష్టం, వడ్డీ కంటే తేడా ఎక్కువైతేనే నిల్వ లాభం.", idx: "100 = ఏడాది సగటు" },
  hi: { title: "बेचने के अच्छे महीने", high: "आमतौर पर सबसे ऊँचा", low: "आमतौर पर सबसे नीचा", gap: "सबसे अच्छे और बुरे महीने का अंतर", note: "एक मंडी का पिछला रुझान, पूर्वानुमान नहीं। भंडारण तभी फ़ायदेमंद जब अंतर भंडारण खर्च, नुकसान और ब्याज से ज़्यादा हो।", idx: "100 = सालाना औसत" },
};

export function SeasonalityCard({ step, t }) {
  const r = step.result || {}, L = SZ[t.code] || SZ.en, M = MONTHS[t.code] || MONTHS.en;
  if (!r.index_by_month) return null;
  const hi = Math.max(...r.index_by_month.map((x) => x.index));
  return (
    <div className="card">
      <div className="card-head"><span>📅 {L.title} · {r.commodity}</span><span className="badge snap">{r.country}</span></div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: 3, alignItems: "end", height: 70, margin: "8px 0 4px" }}>
        {r.index_by_month.map((x) => {
          const top = r.highest_months.includes(x.month), low = r.lowest_months.includes(x.month);
          return <div key={x.month} title={`${M[x.month - 1]} ${x.index}`} style={{ height: `${(x.index / hi) * 100}%`, borderRadius: 3, background: top ? "var(--green)" : low ? "var(--gold)" : "var(--surface2)" }} />;
        })}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: 3, fontSize: 9, textAlign: "center", color: "var(--muted)" }}>
        {r.index_by_month.map((x) => <span key={x.month}>{M[x.month - 1]}</span>)}
      </div>
      <div className="stats">
        <div className="stat-profit"><small>{L.high}</small><b>{r.highest_months.map((m) => M[m - 1]).join(", ")}</b></div>
        <div><small>{L.low}</small><b>{r.lowest_months.map((m) => M[m - 1]).join(", ")}</b></div>
        <div><small>{L.gap}</small><b>{r.peak_vs_trough_pct}%</b></div>
      </div>
      <div className="card-foot">{L.idx} · {r.market}, {r.years_used.length} · {L.note}</div>
    </div>
  );
}
