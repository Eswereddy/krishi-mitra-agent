import { useState } from "react";

// ---------- tiny markdown: **bold**, bullets, numbered lists, paragraphs ----------
function inline(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : p
  );
}

export function Markdown({ text }) {
  const lines = (text || "").split("\n");
  const blocks = [];
  let list = null;
  lines.forEach((raw) => {
    const line = raw.trimEnd();
    const m = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (m) {
      const ordered = /^\s*\d/.test(line);
      if (!list || list.ordered !== ordered) {
        list = { ordered, items: [] };
        blocks.push(list);
      }
      list.items.push(m[1]);
    } else {
      list = null;
      if (line.trim()) blocks.push({ p: line.replace(/^#+\s*/, "") });
    }
  });
  return (
    <div className="md">
      {blocks.map((b, i) =>
        b.items ? (
          b.ordered ? (
            <ol key={i}>{b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}</ol>
          ) : (
            <ul key={i}>{b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}</ul>
          )
        ) : (
          <p key={i}>{inline(b.p)}</p>
        )
      )}
    </div>
  );
}

// ---------- rich cards for tool results ----------
const rupee = (n) => (n == null ? "–" : "₹" + Number(n).toLocaleString("en-IN"));
const WX = (mm, pct) => (mm >= 10 || pct >= 80 ? "🌧️" : mm >= 1 || pct >= 50 ? "🌦️" : pct >= 25 ? "⛅" : "☀️");

function SourceBadge({ source, t }) {
  if (!source) return null;
  const sample = /sample/i.test(source);
  const saved = /snapshot/i.test(source);
  const cls = sample || saved ? "badge-warn" : "badge-ok";
  return <span className={"badge " + cls} title={source}>{sample ? t.sample : saved ? t.snapshot : t.live}</span>;
}

function PriceCard({ step, t }) {
  const rows = step.result?.results || step.result?.highest_first || [];
  if (!rows.length) return null;
  const best = step.tool === "best_markets";
  const top = Math.max(...rows.map((r) => r.modal_price_per_quintal || 0), 1);
  return (
    <div className="card">
      <div className="card-head">
        <span>{best ? "📈" : "🌾"} {t.tools[step.tool]}{rows[0].commodity ? ` · ${rows[0].commodity}` : ""}</span>
        <SourceBadge source={step.result?.source} t={t} />
      </div>
      <div className="rows">
        {rows.slice(0, 5).map((r, i) => (
          <div className="row" key={i}>
            <div className="row-main">
              <b>{r.market || r.district || "–"}</b>
              <small>{[r.district && r.district !== r.market ? r.district : "", r.date].filter(Boolean).join(" · ")}</small>
            </div>
            <div className="row-price">
              <b>{rupee(r.modal_price_per_quintal)}</b>
              {(r.min_price_per_quintal || r.max_price_per_quintal) && (
                <small>{rupee(r.min_price_per_quintal)} – {rupee(r.max_price_per_quintal)}</small>
              )}
            </div>
            {best && <div className="bar"><i style={{ width: `${((r.modal_price_per_quintal || 0) / top) * 100}%` }} /></div>}
          </div>
        ))}
      </div>
      <div className="card-foot">{t.perQ}</div>
    </div>
  );
}


function TrendCard({ step, t }) {
  const r = step.result;
  const pts = r?.series || [];
  if (pts.length < 2) return null;
  const vals = pts.map((p) => p.modal_price_per_quintal);
  const lo = Math.min(...vals), hi = Math.max(...vals), span = Math.max(hi - lo, 1);
  const W = 260, H = 70, pad = 6;
  const xy = vals.map((v, i) => [pad + (i / (vals.length - 1)) * (W - 2 * pad), H - pad - ((v - lo) / span) * (H - 2 * pad)]);
  const line = xy.map((p) => p.join(",")).join(" ");
  const label = { rising: t.trendRising, falling: t.trendFalling, steady: t.trendSteady }[r.trend];
  const arrow = { rising: "▲", falling: "▼", steady: "▬" }[r.trend];
  return (
    <div className="card">
      <div className="card-head"><span>📊 {t.trendTool} · {r.commodity}</span><SourceBadge source={r.source} t={t} /></div>
      <div className="trend">
        <svg viewBox={`0 0 ${W} ${H}`} className={"spark " + r.trend} role="img" aria-label={label}>
          <polyline points={`${pad},${H - pad} ${line} ${W - pad},${H - pad}`} className="spark-fill" />
          <polyline points={line} className="spark-line" />
          <circle cx={xy[xy.length - 1][0]} cy={xy[xy.length - 1][1]} r="4.5" className="spark-dot" />
        </svg>
        <div className={"trend-badge " + r.trend}>
          <b>{arrow} {r.change_pct > 0 ? "+" : ""}{r.change_pct}%</b>
          <small>{label}</small>
        </div>
      </div>
      <div className="trend-meta">
        <span>{r.market}</span>
        <span>{rupee(vals[0])} → <b>{rupee(vals[vals.length - 1])}</b></span>
        <span>{pts.length} {t.trendLast}</span>
      </div>
      <div className="card-foot">{t.perQ}</div>
    </div>
  );
}

function WeatherCard({ step, t }) {
  const f = step.result?.forecast;
  if (!f?.length) return null;
  return (
    <div className="card">
      <div className="card-head"><span>🌦️ {step.result.place}</span><SourceBadge source={step.result.source} t={t} /></div>
      <div className="wx">
        {f.map((d) => (
          <div className="wx-day" key={d.date}>
            <small>{new Date(d.date).toLocaleDateString(undefined, { weekday: "short", day: "numeric" })}</small>
            <span className="wx-ico">{WX(d.rain_mm, d.rain_chance_pct)}</span>
            <b>{Math.round(d.max_c)}°</b><small>{Math.round(d.min_c)}°</small>
            <small className="wx-rain">💧 {d.rain_chance_pct ?? 0}%</small>
          </div>
        ))}
      </div>
    </div>
  );
}

function SchemeCard({ step, t }) {
  const list = step.result?.matched || [];
  if (!list.length) return null;
  return (
    <div className="card">
      <div className="card-head"><span>🏛️ {t.tools.check_schemes}</span></div>
      {list.map((s) => (
        <details className="scheme" key={s.name}>
          <summary><b>{s.name}</b><small>{s.benefit}</small></summary>
          <div className="scheme-body">
            <h5>{t.docs}</h5>
            <ul>{(s.documents || []).map((d) => <li key={d}>{d}</li>)}</ul>
            <h5>{t.apply}</h5>
            <p>{s.how_to_apply}</p>
            {s.verify_at && <a href={s.verify_at} target="_blank" rel="noreferrer">{s.verify_at.replace(/^https?:\/\//, "")} ↗</a>}
          </div>
        </details>
      ))}
    </div>
  );
}

function RevenueCard({ step, t }) {
  const r = step.result;
  if (!r || r.revenue_rs == null) return null;
  return (
    <div className="card">
      <div className="card-head"><span>🧮 {t.tools.calculate_revenue}</span></div>
      <div className="stats">
        <div><small>{t.revenue}</small><b>{rupee(r.revenue_rs)}</b></div>
        {r.expenses_rs > 0 && <div><small>{t.expenses}</small><b>{rupee(r.expenses_rs)}</b></div>}
        {r.expenses_rs > 0 && <div className="stat-profit"><small>{t.profit}</small><b>{rupee(r.profit_rs)}</b></div>}
      </div>
      <div className="card-foot">{r.quintals} q × {rupee(r.price_per_quintal)}</div>
    </div>
  );
}

function ExpertCard({ step, t }) {
  const r = step.result;
  if (!r?.kisan_call_centre) return null;
  return (
    <div className="card card-expert">
      <div className="card-head"><span>☎️ {t.tools.get_expert_help}</span></div>
      <p>{r.local}</p>
      <a className="call-btn" href={`tel:${r.kisan_call_centre.replace(/[^\d]/g, "")}`}>📞 {t.callNow} · {r.kisan_call_centre}</a>
    </div>
  );
}


// ---------- advisor cards: MSP, take-home value, spray window, crop problem, sell-or-hold ----------
function MspCard({ step, t }) {
  const r = step.result, cur = r?.current;
  if (!cur) return null;
  return (
    <div className="card">
      <div className="card-head"><span>🏷️ {t.tools.get_msp} · {r.commodity}</span><span className="badge badge-ok">{cur.season}</span></div>
      <div className="stats">
        <div className="stat-profit"><small>{t.adv.msp}</small><b>{rupee(cur.msp_price_per_quintal)}</b></div>
        {(r.other_seasons || []).slice(0, 2).map((o) => <div key={o.season}><small>{o.season}</small><b>{rupee(o.msp_price_per_quintal)}</b></div>)}
      </div>
      <div className="card-foot">{t.perQ} · {t.adv.mspNote}</div>
    </div>
  );
}

function NetValueCard({ step, t }) {
  const r = step.result;
  if (!r || r.net_revenue_rs == null) return null;
  const gap = r.net_vs_msp_rs_per_quintal;
  return (
    <div className="card">
      <div className="card-head"><span>💰 {t.adv.netTitle} · {r.commodity}</span></div>
      <div className="stats">
        <div><small>{t.adv.gross}</small><b>{rupee(r.gross_revenue_rs)}</b></div>
        <div><small>{t.adv.fees}</small><b>−{rupee((r.commission_rs || 0) + (r.loading_rs || 0))}</b></div>
        {r.transport_rs > 0 && <div><small>{t.adv.transport}</small><b>−{rupee(r.transport_rs)}</b></div>}
        <div className="stat-profit"><small>{t.adv.net}</small><b>{rupee(r.net_revenue_rs)}</b></div>
      </div>
      <div className="card-foot">
        {rupee(r.net_price_per_quintal)} {t.perQ.toLowerCase?.() || ""}
        {gap != null && <> · <b className={gap >= 0 ? "pos" : "neg"}>{gap >= 0 ? "+" : "−"}{rupee(Math.abs(gap))}</b> {t.adv.vsMsp}</>}
      </div>
      <div className="card-foot warn-note">⚠️ {t.adv.assumed}</div>
    </div>
  );
}

function SprayCard({ step, t }) {
  const days = step.result?.days;
  if (!days?.length) return null;
  return (
    <div className="card">
      <div className="card-head"><span>🧴 {t.tools.spray_window} · {step.result.place}</span><SourceBadge source={step.result.source} t={t} /></div>
      <div className="wx">
        {days.map((d) => (
          <div className={"wx-day spray " + (d.suitable ? "go" : "stop")} key={d.date} title={d.advice}>
            <small>{new Date(d.date).toLocaleDateString(undefined, { weekday: "short", day: "numeric" })}</small>
            <span className="wx-ico">{d.suitable ? "✅" : "⛔"}</span>
            <small className="wx-rain">💧 {d.rain_chance_pct ?? 0}%</small>
            {d.wind_kmh != null && <small>🌬 {Math.round(d.wind_kmh)}</small>}
          </div>
        ))}
      </div>
      {step.result.best_day && <div className="card-foot">✅ {t.adv.sprayGood}: <b>{new Date(step.result.best_day).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" })}</b></div>}
    </div>
  );
}

function ProblemCard({ step, t }) {
  const ms = step.result?.matches;
  if (!ms?.length) return null;
  const urg = { high: t.adv.urgencyHigh, medium: t.adv.urgencyMedium, low: t.adv.urgencyLow };
  return (
    <div className="card">
      <div className="card-head"><span>🔍 {t.tools.lookup_problem}</span></div>
      {ms.map((m, i) => (
        <details className="scheme" key={m.name} open={i === 0}>
          <summary><b>{m.name}</b><small className={"urg " + m.urgency}>{urg[m.urgency]}</small></summary>
          <div className="scheme-body">
            <p>{m.looks_like}</p>
            <h5>{t.adv.checks}</h5>
            <ul>{m.what_to_do.map((w) => <li key={w}>{w}</li>)}</ul>
            <p className="card-foot">👨‍🌾 {m.expert_note}</p>
          </div>
        </details>
      ))}
      <div className="card-foot">{t.adv.askOfficer}</div>
    </div>
  );
}

function DecisionCard({ step, t }) {
  const r = step.result;
  if (!r?.recommendation) return null;
  const label = { sell_now: t.adv.sellNow, hold_short: t.adv.holdShort, use_procurement_or_wait: t.adv.procure,
    sell_now_or_hold_if_stored: t.adv.sellOrHold, not_enough_data: t.adv.noData }[r.recommendation] || r.recommendation;
  const tone = r.recommendation === "hold_short" ? "rising" : r.recommendation === "sell_now" ? "falling" : "steady";
  return (
    <div className="card">
      <div className="card-head"><span>⚖️ {t.tools.hold_or_sell} · {r.commodity}</span><SourceBadge source={r.trend?.source} t={t} /></div>
      <div className={"decision " + tone}><b>{label}</b></div>
      <div className="stats">
        {r.current_price_per_quintal != null && <div><small>{t.adv.now}</small><b>{rupee(r.current_price_per_quintal)}</b></div>}
        {r.msp_price_per_quintal != null && <div><small>{t.adv.msp}</small><b>{rupee(r.msp_price_per_quintal)}</b></div>}
        {r.best_market?.modal_price_per_quintal != null && <div><small>{t.adv.best} · {r.best_market.market}</small><b>{rupee(r.best_market.modal_price_per_quintal)}</b></div>}
      </div>
      <div className="card-foot">{t.adv.guidance}</div>
    </div>
  );
}

export function ToolCards({ steps, t }) {
  // show the latest result per tool (the agent may call a tool twice)
  const seen = new Map();
  (steps || []).forEach((s) => s.result && !s.result.error && seen.set(s.tool + JSON.stringify(s.args), s));
  const cards = [...seen.values()];
  const render = (s) => {
    switch (s.tool) {
      case "get_mandi_price":
      case "best_markets": return <PriceCard step={s} t={t} />;
      case "get_price_trend": return <TrendCard step={s} t={t} />;
      case "get_weather": return <WeatherCard step={s} t={t} />;
      case "check_schemes": return <SchemeCard step={s} t={t} />;
      case "calculate_revenue": return <RevenueCard step={s} t={t} />;
      case "get_expert_help": return <ExpertCard step={s} t={t} />;
      case "get_msp": return <MspCard step={s} t={t} />;
      case "net_market_value": return <NetValueCard step={s} t={t} />;
      case "spray_window": return <SprayCard step={s} t={t} />;
      case "lookup_problem": return <ProblemCard step={s} t={t} />;
      case "hold_or_sell": return <DecisionCard step={s} t={t} />;
      default: return null;
    }
  };
  return <>{cards.map((s, i) => <div key={i}>{render(s)}</div>)}</>;
}

export function StepChips({ steps, t }) {
  const [open, setOpen] = useState(false);
  if (!steps?.length) return null;
  return (
    <div className="steps">
      <button className="steps-toggle" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span>⚙️ {t.steps}</span>
        {steps.map((s, i) => <em key={i} className="chip-sm">{t.tools[s.tool] || s.tool}</em>)}
      </button>
      {open && (
        <ul className="steps-list">
          {steps.map((s, i) => (
            <li key={i}><code>{s.tool}</code> {JSON.stringify(s.args)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}


// Live progress shown inside the pending bubble while the agent works (each tool call appears as it starts).
export function LiveSteps({ live, t }) {
  return (
    <div className="bubble typing live">
      <div className="live-head"><i /><i /><i /><span>{t.thinking}</span></div>
      {live?.length > 0 && (
        <ul className="live-list">
          {live.map((l, i) => (
            <li key={i} className={l.done ? "done" : "run"}>
              <span className="live-ico">{l.done ? "✓" : <b className="mini-spin" />}</span>
              {l.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const SRC = [
  [/agmarknet/i, "Agmarknet (data.gov.in)"], [/open-meteo/i, "Open-Meteo"], [/sample/i, null],
];
export function SourcesLine({ steps, t }) {
  const names = new Set();
  (steps || []).forEach((s) => {
    const src = s.result?.source;
    if (!src) return;
    const hit = SRC.find(([re]) => re.test(src));
    if (hit?.[1]) names.add(hit[1]);
  });
  if ((steps || []).some((s) => s.tool === "check_schemes" && s.result?.matched?.length)) names.add("pmkisan.gov.in · pmfby.gov.in");
  if ((steps || []).some((s) => s.tool === "get_expert_help")) names.add("Kisan Call Centre");
  if ((steps || []).some((s) => s.tool === "get_msp" && s.result?.current) || (steps || []).some((s) => s.tool === "hold_or_sell" && s.result?.msp_price_per_quintal != null)) names.add("CCEA / agriculture.gov.in (MSP)");
  if (!names.size) return null;
  return <p className="sources">📚 {t.sources}: {[...names].join(" · ")}</p>;
}

// ---------- icons ----------
export const I = {
  mic: (p) => <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v4" /></svg>,
  stop: (p) => <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" {...p}><rect x="6" y="6" width="12" height="12" rx="2.5" /></svg>,
  send: (p) => <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>,
  camera: (p) => <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" /></svg>,
  image: (p) => <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8.5" cy="8.5" r="1.5" /><path d="m21 15-5-5L5 21" /></svg>,
  speaker: (p) => <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M11 5 6 9H2v6h4l5 4zM15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14" /></svg>,
  whatsapp: (p) => <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" {...p}><path d="M12 2a10 10 0 0 0-8.6 15L2 22l5.2-1.4A10 10 0 1 0 12 2zm5.2 14.2c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.2-4.6-4-4.7-4.2-.1-.2-1.1-1.5-1.1-2.8s.7-2 1-2.3c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .5l-.4.6-.3.4c-.1.2-.3.3-.1.6.2.3.8 1.3 1.7 2.1 1.2 1 2.1 1.3 2.4 1.5.3.1.5.1.6-.1l.8-1c.2-.3.4-.2.6-.1l1.9.9c.3.1.5.2.5.3.1.2.1.8-.1 1.4z" /></svg>,
  copy: (p) => <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>,
  plus: (p) => <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" {...p}><path d="M12 5v14M5 12h14" /></svg>,
  x: (p) => <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" {...p}><path d="M18 6 6 18M6 6l12 12" /></svg>,
  user: (p) => <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>,
  moon: (p) => <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>,
  sun: (p) => <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>,
  wave: (p) => <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" {...p}><path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4" /></svg>,
};
