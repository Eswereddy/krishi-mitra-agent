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
export const lg = (lang) => S[lang] || S.en;
const get = (k) => { try { return JSON.parse(localStorage.getItem(k)); } catch { return null; } };
const set = (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } };
export const getUser = () => get("km-user");
export const isGuest = () => get("km-guest") === true;
export const needsLogin = () => !getUser() && !isGuest();
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
  const [cid, setCid] = useState(undefined); // undefined = loading, null = not configured
  const [msg, setMsg] = useState("");

  useEffect(() => { fetch("/api/auth/config").then((r) => r.json()).then((j) => setCid(j.google_client_id || null)).catch(() => setCid(null)); }, []);
  useEffect(() => {
    if (!cid) return;
    const init = () => {
      if (!window.google?.accounts?.id || !box.current) return;
      window.google.accounts.id.initialize({ client_id: cid, callback: async (resp) => {
        setMsg(t.wait);
        try {
          const r = await fetch("/api/auth/google", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ credential: resp.credential }) });
          const j = await r.json();
          if (!r.ok) throw new Error(j.detail || t.fail);
          set("km-user", { ...j.user, token: j.token });
          set("km-guest", null);
          onDone();
        } catch (e) { setMsg(e.message || t.fail); }
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

  return (
    <div className="login-screen" role="dialog" aria-label={t.title}>
      <div className="login-card">
        <div className="login-logo">🌾</div>
        <h2>{t.title}</h2>
        <p className="hint">{t.sub}</p>
        {cid === undefined && <p className="hint">…</p>}
        {cid && <div ref={box} className="login-google" />}
        {cid === null && <p className="hint">{t.off}</p>}
        {msg && <p className="hint" role="status">{msg}</p>}
        <div className="login-or"><span>{t.or}</span></div>
        <button className="pill login-guest" onClick={() => { set("km-guest", true); onDone(); }}>{t.guest}</button>
        <p className="hint">{t.note}</p>
      </div>
    </div>
  );
}
