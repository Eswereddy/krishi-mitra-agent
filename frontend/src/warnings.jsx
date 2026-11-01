// Early warning: crop-specific heat / cold / rain / wind / disease-weather alerts for the farmer's place, checked on the
// phone every few hours while the app is open. The last result is kept so it still shows offline. No account, no server storage.
import { useCallback, useEffect, useState } from "react";
import { Sheet } from "./khata";

const S = {
  en: { title: "Early warning", sub: "Weather risks for my crop", check: "Check now", notify: "Notify me on this phone", notified: "Notifications on", banner: "Crop warning", need: "Add your village and crop in your profile first.", fail: "Could not check. Showing the last result if any.", last: "Last checked", close: "Close", actions: "What to do", basis: "Indicative crop limits, live forecast", none: "All clear" },
  te: { title: "ముందస్తు హెచ్చరిక", sub: "నా పంటకు వాతావరణ ప్రమాదాలు", check: "ఇప్పుడు చూడు", notify: "ఈ ఫోన్‌లో నోటిఫికేషన్లు", notified: "నోటిఫికేషన్లు ఆన్", banner: "పంట హెచ్చరిక", need: "ముందు ప్రొఫైల్‌లో ఊరు, పంట నమోదు చేయండి.", fail: "చూడలేకపోయాం. చివరి ఫలితం చూపిస్తున్నాం.", last: "చివరిసారి", close: "మూసివేయి", actions: "ఏమి చేయాలి", basis: "సూచనాత్మక పంట పరిమితులు, ప్రత్యక్ష అంచనా", none: "అంతా సరిగ్గా ఉంది" },
  hi: { title: "पूर्व चेतावनी", sub: "मेरी फसल के मौसम जोखिम", check: "अभी जाँचें", notify: "इस फ़ोन पर सूचना", notified: "सूचनाएँ चालू", banner: "फसल चेतावनी", need: "पहले प्रोफ़ाइल में गाँव और फसल डालें।", fail: "जाँच नहीं हो सकी। पिछला नतीजा दिखा रहे हैं।", last: "आख़िरी जाँच", close: "बंद करें", actions: "क्या करें", basis: "सांकेतिक फसल सीमाएँ, लाइव पूर्वानुमान", none: "सब ठीक है" },
};
export const wn = (lang) => S[lang] || S.en;
const load = (k, fb) => { try { const v = localStorage.getItem(k); return v == null ? fb : JSON.parse(v); } catch { return fb; } };
const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };
const KEY = "km-warn";

export function useWarnings(profile, lang) {
  const l = lang === "auto" ? "te" : lang;
  const [data, setData] = useState(() => load(KEY, null));
  const [error, setError] = useState(false);
  const ready = !!(profile.district && profile.main_crop);
  const check = useCallback(async () => {
    if (!ready) return null;
    try {
      const r = await fetch("/api/warnings/check", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ crop: profile.main_crop, place: profile.district, country: profile.country, sowing_date: profile.sowing_date, lang: l }) });
      if (!r.ok) throw new Error();
      const j = { ...(await r.json()), at: new Date().toISOString() };
      if (j.error) throw new Error();
      setData(j); setError(false); save(KEY, j);
      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        const seen = load("km-warn-seen", []);
        const fresh = j.alerts.filter((a) => a.severity === "warning" && !seen.includes(a.key));
        fresh.slice(0, 2).forEach((a) => { try { new Notification(wn(lang).banner, { body: a.text }); } catch { /* not allowed here */ } });
        save("km-warn-seen", [...seen, ...fresh.map((a) => a.key)].slice(-50));
      }
      return j;
    } catch { setError(true); return null; }
  }, [ready, profile.main_crop, profile.district, profile.country, profile.sowing_date, l, lang]);
  useEffect(() => {
    check();
    const id = setInterval(check, 3 * 3600 * 1000);
    window.addEventListener("online", check);
    return () => { clearInterval(id); window.removeEventListener("online", check); };
  }, [check]);
  return { data, error, check, ready };
}

export function WarningsSheet({ lang, ready, data, error, check, onClose }) {
  const t = wn(lang);
  const [busy, setBusy] = useState(false);
  const [perm, setPerm] = useState(() => (typeof Notification !== "undefined" ? Notification.permission : "denied"));
  const run = async () => { setBusy(true); await check(); setBusy(false); };
  return (
    <Sheet title={"⚠️ " + t.title} onClose={onClose} close={t.close}>
      {!ready && <p className="warn-note">{t.need}</p>}
      <button className="primary" onClick={run} disabled={!ready || busy}>{t.check}</button>
      {typeof Notification !== "undefined" && perm !== "denied" && (
        <button className="pill" disabled={perm === "granted"} onClick={() => Notification.requestPermission().then(setPerm)}>🔔 {perm === "granted" ? t.notified : t.notify}</button>
      )}
      {error && <p className="warn-note">{t.fail}</p>}
      {data && (
        <div className="claim-out">
          <p className="hint">{data.place} · {data.crop || ""} · {t.last}: {new Date(data.at).toLocaleString()}</p>
          {data.all_clear && <div className="decision rising"><b>✅ {data.clear_text || t.none}</b></div>}
          {data.alerts.map((a) => (
            <div key={a.key} className={"decision " + (a.severity === "warning" ? "falling" : "steady")} style={{ display: "block" }}>
              <b>{a.severity === "warning" ? "🔴" : "🟡"} {a.label}</b>
              <p>{a.text}</p>
              <small className="hint">{t.actions}</small>
              <ul className="plain">{a.actions.map((x) => <li key={x.code}>{x.text}</li>)}</ul>
            </div>
          ))}
          <p className="hint">{t.basis}. {data.note}</p>
        </div>
      )}
    </Sheet>
  );
}
