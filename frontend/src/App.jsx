import { useRef, useState } from "react";

// UI text for each language. "auto" answers in the farmer's own language (UI shows Telugu).
const T = {
  te: {
    title: "కృషి మిత్ర", hint: "మీ ప్రశ్న చెప్పండి లేదా పంట ఫోటో పంపండి.",
    speak: "🎤 మాట్లాడండి", stop: "⏹ ఆపండి", photo: "📷 పంట ఫోటో పంపండి:",
    you: "మీరు", bot: "కృషి మిత్ర", steps: "ఏజెంట్ దశలు", looking: "ఫోటో చూస్తున్నాను...",
    ok: "✅ సంఖ్యలు టూల్ ఫలితాలతో సరిపోలాయి", warn: "⚠️ ఈ సంఖ్యలు ధృవీకరించలేదు: ",
    mic: "మైక్ అనుమతి ఇవ్వండి: ", unclear: "నాకు స్పష్టంగా వినిపించలేదు. మళ్లీ మాట్లాడండి లేదా టైప్ చేయండి.", listen: "🔊 వినండి", profile: "నా వివరాలు", state: "రాష్ట్రం", district: "జిల్లా", land: "నాకు సొంత భూమి ఉంది", crop: "ప్రధాన పంట", type: "లేదా ఇక్కడ టైప్ చేయండి...", send: "పంపండి",
  },
  en: {
    title: "Krishi Mitra", hint: "Speak your question or send a photo of your crop.",
    speak: "🎤 Speak", stop: "⏹ Stop", photo: "📷 Send crop photo:",
    you: "You", bot: "Krishi Mitra", steps: "Agent steps", looking: "Looking at the photo...",
    ok: "✅ Figures verified against tool results", warn: "⚠️ Some figures could not be verified: ",
    mic: "Please allow microphone access: ", unclear: "I could not hear that clearly. Please speak again or type your question.", listen: "🔊 Listen", profile: "My details", state: "State", district: "District", land: "I own farmland", crop: "Main crop", type: "Or type here...", send: "Send",
  },
  hi: {
    title: "कृषि मित्र", hint: "अपना सवाल बोलें या फसल की फोटो भेजें।",
    speak: "🎤 बोलिए", stop: "⏹ रोकिए", photo: "📷 फसल की फोटो भेजें:",
    you: "आप", bot: "कृषि मित्र", steps: "एजेंट के कदम", looking: "फोटो देख रहा हूँ...",
    ok: "✅ आंकड़े टूल के नतीजों से मेल खाते हैं", warn: "⚠️ इन आंकड़ों की पुष्टि नहीं हुई: ",
    mic: "कृपया माइक की अनुमति दें: ", unclear: "मैं साफ़ सुन नहीं पाया। कृपया फिर से बोलें या टाइप करें।", listen: "🔊 सुनिए", profile: "मेरी जानकारी", state: "राज्य", district: "ज़िला", land: "मेरे पास अपनी ज़मीन है", crop: "मुख्य फसल", type: "या यहाँ टाइप करें...", send: "भेजें",
  },
};

export default function App() {
  const [lang, setLang] = useState("auto"); // auto | te | en | hi
  const t = T[lang === "auto" ? "te" : lang];
  const [recording, setRecording] = useState(false);
  const [question, setQuestion] = useState("");
  const [typed, setTyped] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [steps, setSteps] = useState([]);
  const [verification, setVerification] = useState(null);
  const [profile, setProfile] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("km-profile")) || { state: "Andhra Pradesh", district: "", owns_land: false, main_crop: "" };
    } catch {
      return { state: "Andhra Pradesh", district: "", owns_land: false, main_crop: "" };
    }
  });
  function updateProfile(patch) {
    const next = { ...profile, ...patch };
    setProfile(next);
    try { localStorage.setItem("km-profile", JSON.stringify(next)); } catch { /* storage unavailable */ }
  }
  function speak(text) {
    try {
      const synth = window.speechSynthesis;
      if (!synth) return;
      synth.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = /[\u0C00-\u0C7F]/.test(text) ? "te-IN" : /[\u0900-\u097F]/.test(text) ? "hi-IN" : "en-IN";
      synth.speak(u);
    } catch { /* speech not supported */ }
  }
  const recorder = useRef(null);
  const chunks = useRef([]);

  async function ask(text) {
    setSteps([]);
    setVerification(null);
    setAnswer("…");
    const r = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text, lang, profile }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "ask failed");
    const data = await r.json();
    setAnswer(data.answer);
    setSteps(data.steps || []);
    setVerification(data.verification || null);
  }

  async function sendTyped() {
    const text = typed.trim();
    if (!text) return;
    setError("");
    setQuestion(text);
    try {
      await ask(text);
    } catch (e) {
      setAnswer("");
      setError(e.message);
    }
  }

  async function start() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (e) => chunks.current.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        const blob = new Blob(chunks.current, { type: mr.mimeType || "audio/webm" });
        if (blob.size < 4000) {
          setError(t.unclear); // recording too short
          return;
        }
        const form = new FormData();
        form.append("audio", blob, "question.webm");
        try {
          const r = await fetch("/api/transcribe", { method: "POST", body: form });
          if (r.status === 422) throw new Error(t.unclear);
          if (!r.ok) throw new Error((await r.json()).detail || "transcribe failed");
          const { text } = await r.json();
          setQuestion(text);
          await ask(text);
        } catch (e) {
          setAnswer("");
          setError(e.message);
        }
      };
      mr.start();
      recorder.current = mr;
      setRecording(true);
    } catch (e) {
      setError(t.mic + e.message);
    }
  }

  function stop() {
    recorder.current?.stop();
    setRecording(false);
  }

  async function uploadPhoto(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    setSteps([]);
    setVerification(null);
    setAnswer(t.looking);
    const form = new FormData();
    form.append("image", file);
    form.append("question", question);
    form.append("lang", lang);
    try {
      const r = await fetch("/api/diagnose", { method: "POST", body: form });
      if (!r.ok) throw new Error((await r.json()).detail || "diagnose failed");
      setAnswer((await r.json()).answer);
    } catch (err) {
      setAnswer("");
      setError(err.message);
    }
  }

  return (
    <main style={{ maxWidth: 560, margin: "40px auto", padding: 16, fontFamily: "system-ui" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>🌾 {t.title}</h1>
        <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language">
          <option value="auto">Auto</option>
          <option value="te">తెలుగు</option>
          <option value="en">English</option>
          <option value="hi">हिन्दी</option>
        </select>
      </div>
      <p>{t.hint}</p>
      <details style={{ marginBottom: 12 }}>
        <summary>{t.profile}</summary>
        <div style={{ display: "grid", gap: 6, marginTop: 8 }}>
          <input value={profile.state} onChange={(e) => updateProfile({ state: e.target.value })} placeholder={t.state} />
          <input value={profile.district} onChange={(e) => updateProfile({ district: e.target.value })} placeholder={t.district} />
          <input value={profile.main_crop} onChange={(e) => updateProfile({ main_crop: e.target.value })} placeholder={t.crop} />
          <label>
            <input type="checkbox" checked={profile.owns_land} onChange={(e) => updateProfile({ owns_land: e.target.checked })} /> {t.land}
          </label>
        </div>
      </details>
      <button onClick={recording ? stop : start} style={{ fontSize: 18, padding: "12px 20px" }}>
        {recording ? t.stop : t.speak}
      </button>
      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
        <input
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && sendTyped()}
          placeholder={t.type}
          style={{ flex: 1, padding: 8 }}
        />
        <button onClick={sendTyped}>{t.send}</button>
      </div>
      <div style={{ marginTop: 12 }}>
        <label>
          {t.photo}{" "}
          <input type="file" accept="image/*" capture="environment" onChange={uploadPhoto} />
        </label>
      </div>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {question && (
        <p>
          <b>{t.you}:</b> {question}
        </p>
      )}
      {steps.length > 0 && (
        <details open>
          <summary>
            {t.steps} ({steps.length})
          </summary>
          <ul>
            {steps.map((st, i) => (
              <li key={i}>
                <code>{st.tool}</code> {JSON.stringify(st.args)}
              </li>
            ))}
          </ul>
        </details>
      )}
      {answer && (
        <p style={{ whiteSpace: "pre-wrap" }}>
          <b>{t.bot}:</b> {answer}{" "}
          <button onClick={() => speak(answer)} aria-label="Listen">{t.listen}</button>
        </p>
      )}
      {verification && (
        <p style={{ fontSize: 14, color: verification.passed ? "green" : "darkorange" }}>
          {verification.passed ? t.ok : t.warn + (verification.unverified || []).join(", ")}
        </p>
      )}
    </main>
  );
}
