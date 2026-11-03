// Minimal sign-in: Continue with Google, or use the app as a guest. Signing in only identifies the farmer; farm data stays on the phone.
import { useEffect, useRef, useState } from "react";

const S = {
  en: { title: "Krishi Mitra", sub: "Sign in to continue", google: "Continue with Google", guest: "Continue without signing in", or: "or",
        note: "Signing in only shows your name. Your farm data stays on this phone.", off: "Google sign-in is not set up yet. You can continue as a guest.", fail: "Sign-in failed", wait: "Signing in…", out: "Sign out", as: "Signed in as", signin: "Sign in", guestLbl: "Guest" },
  te: { title: "కృషి మిత్ర", sub: "కొనసాగడానికి సైన్ ఇన్ చేయండి", google: "Google తో కొనసాగండి", guest: "సైన్ ఇన్ లేకుండా కొనసాగండి", or: "లేదా",
        note: "సైన్ ఇన్ మీ పేరు చూపిస్తుంది అంతే. మీ పొలం డేటా ఈ ఫోన్‌లోనే ఉంటుంది.", off: "Google సైన్ ఇన్ ఇంకా సిద్ధం కాలేదు. అతిథిగా కొనసాగవచ్చు.", fail: "సైన్ ఇన్ విఫలమైంది", wait: "సైన్ ఇన్ అవుతోంది…", out: "సైన్ అవుట్", as: "సైన్ ఇన్ అయినవారు", signin: "సైన్ ఇన్", guestLbl: "అతిథి" },
  hi: { title: "कृषि मित्र", sub: "जारी रखने के लिए साइन इन करें", google: "Google से जारी रखें", guest: "बिना साइन इन जारी रखें", or: "या",
        note: "साइन इन से सिर्फ़ आपका नाम दिखता है। आपके खेत का डेटा इसी फ़ोन में रहता है।", off: "Google साइन इन अभी सेट नहीं है। आप अतिथि के रूप में जारी रख सकते हैं।", fail: "साइन इन नहीं हुआ", wait: "साइन इन हो रहा है…", out: "साइन आउट", as: "साइन इन:", signin: "साइन इन", guestLbl: "अतिथि" },
};
const X = {
  en: { email: "Email", pw: "Password (8+ characters)", name: "Your name", login: "Sign in", create: "Create account", toCreate: "New here? Create an account", toLogin: "Have an account? Sign in", show: "Show", hide: "Hide",
        pwNote: "No password reset yet, so remember it.", del: "Delete my account", delAsk: "Delete your account permanently? Farm data on this phone stays.", note2: "Your account stores only your email, name and a scrambled password. Farm data stays on this phone." },
  te: { email: "ఇమెయిల్", pw: "పాస్‌వర్డ్ (8+ అక్షరాలు)", name: "మీ పేరు", login: "సైన్ ఇన్", create: "ఖాతా సృష్టించండి", toCreate: "కొత్తవారా? ఖాతా సృష్టించండి", toLogin: "ఖాతా ఉందా? సైన్ ఇన్", show: "చూపు", hide: "దాచు",
        pwNote: "పాస్‌వర్డ్ రీసెట్ ఇంకా లేదు, గుర్తుంచుకోండి.", del: "నా ఖాతాను తొలగించు", delAsk: "ఖాతాను శాశ్వతంగా తొలగించాలా? ఫోన్‌లోని పొలం డేటా అలాగే ఉంటుంది.", note2: "ఖాతాలో మీ ఇమెయిల్, పేరు, గుప్తీకరించిన పాస్‌వర్డ్ మాత్రమే ఉంటాయి. పొలం డేటా ఫోన్‌లోనే ఉంటుంది." },
  hi: { email: "ईमेल", pw: "पासवर्ड (8+ अक्षर)", name: "आपका नाम", login: "साइन इन", create: "खाता बनाएँ", toCreate: "नए हैं? खाता बनाएँ", toLogin: "खाता है? साइन इन", show: "दिखाएँ", hide: "छिपाएँ",
        pwNote: "पासवर्ड रीसेट अभी नहीं है, याद रखें।", del: "मेरा खाता हटाएँ", delAsk: "खाता हमेशा के लिए हटाएँ? फ़ोन का खेत डेटा रहेगा।", note2: "खाते में सिर्फ़ ईमेल, नाम और एन्क्रिप्टेड पासवर्ड रहता है। खेत का डेटा फ़ोन में रहता है।" },
};
export const lg = (lang) => ({ ...(S[lang] || S.en), ...(X[lang] || X.en) });
const get = (k) => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } };
const set = (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };
export const getUser = () => get("km-user");
export const isGuest = () => get("km-guest") === true;
export const needsLogin = () => !getUser() && !isGuest();
export async function deleteAccount() {
  const u = getUser();
  const r = await fetch("/api/auth/account", { method: "DELETE", headers: { Authorization: "Bearer " + u.token } });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "failed");
  signOut();
}
export function signOut() { set("km-user", null); set("km-guest", null); try { window.google?.accounts?.id?.disableAutoSelect(); } catch { /* not loaded */ } }

// A stored session is checked with the server once per start; an expired or invalid one is dropped so the login page returns.
export async function validateSession() {
  const u = getUser();
  if (!u) return;
  try {
    const r = await fetch("/api/auth/me", { headers: { Authorization: "Bearer " + u.token } });
    if (r.status === 401) set("km-user", null);
  } catch { /* offline: keep the session */ }
}

export function LoginScreen({ lang, onDone }) {
  const t = lg(lang);
  const box = useRef(null);
  const [cfg, setCfg] = useState(undefined); // undefined = loading
  const [msg, setMsg] = useState("");
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const cid = cfg?.google_client_id || null;

  const finish = (j) => { set("km-user", { ...j.user, token: j.token }); set("km-guest", null); onDone(); };
  const post = async (url, body) => {
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : t.fail);
    return j;
  };
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setMsg("");
    try { finish(await post(mode === "login" ? "/api/auth/login" : "/api/auth/register", f)); }
    catch (er) { setMsg(er.message || t.fail); }
    setBusy(false);
  };

  useEffect(() => { fetch("/api/auth/config").then((r) => r.json()).then(setCfg).catch(() => setCfg({})); }, []);
  useEffect(() => {
    if (!cid) return;
    const init = () => {
      if (!window.google?.accounts?.id || !box.current) return;
      window.google.accounts.id.initialize({ client_id: cid, callback: async (resp) => {
        setMsg(t.wait);
        try { finish(await post("/api/auth/google", { credential: resp.credential })); } catch (e) { setMsg(e.message || t.fail); }
      } });
      window.google.accounts.id.renderButton(box.current, { theme: "outline", size: "large", text: "continue_with", shape: "pill", width: 280 });
    };
    if (window.google?.accounts?.id) return init();
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.onload = init;
    s.onerror = () => setMsg(t.fail);
    document.head.appendChild(s);
  }, [cid]); // eslint-disable-line

  const up = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="login-screen" role="dialog" aria-label={t.title}>
      <div className="login-card">
        <div className="login-logo">🌾</div>
        <h2>{t.title}</h2>
        <p className="hint">{t.sub}</p>
        {cfg === undefined && <p className="hint">…</p>}
        {cfg?.accounts && (
          <form className="login-form" onSubmit={submit}>
            {mode === "create" && <input aria-label={t.name} placeholder={t.name} autoComplete="name" maxLength={80} value={f.name} onChange={up("name")} />}
            <input aria-label={t.email} placeholder={t.email} type="email" autoComplete="email" required value={f.email} onChange={up("email")} />
            <div className="login-pw">
              <input aria-label={t.pw} placeholder={t.pw} type={showPw ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"} required minLength={8} maxLength={128} value={f.password} onChange={up("password")} />
              <button type="button" className="pill" onClick={() => setShowPw(!showPw)}>{showPw ? t.hide : t.show}</button>
            </div>
            <button className="pill primary login-guest" disabled={busy}>{busy ? "…" : mode === "login" ? t.login : t.create}</button>
            <button type="button" className="login-link" onClick={() => { setMode(mode === "login" ? "create" : "login"); setMsg(""); }}>{mode === "login" ? t.toCreate : t.toLogin}</button>
            {mode === "create" && <p className="hint">{t.pwNote}</p>}
          </form>
        )}
        {msg && <p className="hint login-msg" role="alert">{msg}</p>}
        {cid && <>{cfg?.accounts && <div className="login-or"><span>{t.or}</span></div>}<div ref={box} className="login-google" /></>}
        {cfg && !cid && !cfg.accounts && <p className="hint">{t.off}</p>}
        <div className="login-or"><span>{t.or}</span></div>
        <button className="pill login-guest" onClick={() => { set("km-guest", true); onDone(); }}>{t.guest}</button>
        <p className="hint">{cfg?.accounts ? t.note2 : t.note}</p>
      </div>
    </div>
  );
}
