import { useRef, useState } from "react";

// UI text per language. "auto" answers in the farmer's own language (UI shows Telugu).
const T = {
  te: {
    title: "కృషి మిత్ర", hint: "మీ ప్రశ్న చెప్పండి, టైప్ చేయండి లేదా పంట ఫోటో పంపండి.",
    speak: "🎤 మాట్లాడండి", stop: "⏹ ఆపండి", photo: "📷 పంట ఫోటో పంపండి:",
    you: "మీరు", bot: "కృషి మిత్ర", steps: "ఏజెంట్ దశలు", looking: "ఆలోచిస్తున్నాను...",
    ok: "✅ సంఖ్యలు టూల్ ఫలితాలతో సరిపోలాయి", warn: "⚠️ ఈ సంఖ్యలు ధృవీకరించలేదు: ",
    mic: "మైక్ అనుమతి ఇవ్వండి: ", unclear: "నాకు స్పష్టంగా వినిపించలేదు. మళ్లీ మాట్లాడండి లేదా టైప్ చేయండి.",
    listen: "🔊 వినండి", share: "WhatsApp లో పంపండి", clear: "కొత్త సంభాషణ",
    profile: "నా వివరాలు", state: "రాష్ట్రం", district: "జిల్లా", land: "నాకు సొంత భూమి ఉంది", crop: "ప్రధాన పంట",
    type: "లేదా ఇక్కడ టైప్ చేయండి...", send: "పంపండి", try: "ఇవి అడిగి చూడండి:",
    chips: ["నా జిల్లాలో వరి ధర ఎంత?", "నాకు ఏ పథకాలు వస్తాయి?", "ఈ వారం వర్షం పడుతుందా?", "వేరుశనగ ఎక్కడ అమ్మితే ఎక్కువ ధర వస్తుంది?"],
  },
  en: {
    title: "Krishi Mitra", hint: "Speak, type, or send a photo of your crop.",
    speak: "🎤 Speak", stop: "⏹ Stop", photo: "📷 Send crop photo:",
    you: "You", bot: "Krishi Mitra", steps: "Agent steps", looking: "Thinking...",
    ok: "✅ Figures verified against tool results", warn: "⚠️ Some figures could not be verified: ",
    mic: "Please allow microphone access: ", unclear: "I could not hear that clearly. Please speak again or type your question.",
    listen: "🔊 Listen", share: "Share on WhatsApp", clear: "New conversation",
    profile: "My details", state: "State", district: "District", land: "I own farmland", crop: "Main crop",
    type: "Or type here...", send: "Send", try: "Try asking:",
    chips: ["What is the paddy price in my district?", "Which schemes can I get?", "Will it rain this week?", "Where should I sell groundnut for the best price?"],
  },
  hi: {
    title: "कृषि मित्र", hint: "बोलें, टाइप करें या फसल की फोटो भेजें।",
    speak: "🎤 बोलिए", stop: "⏹ रोकिए", photo: "📷 फसल की फोटो भेजें:",
    you: "आप", bot: "कृषि मित्र", steps: "एजेंट के कदम", looking: "सोच रहा हूँ...",
    ok: "✅ आंकड़े टूल के नतीजों से मेल खाते हैं", warn: "⚠️ इन आंकड़ों की पुष्टि नहीं हुई: ",
    mic: "कृपया माइक की अनुमति दें: ", unclear: "मैं साफ़ सुन नहीं पाया। कृपया फिर से बोलें या टाइप करें।",
    listen: "🔊 सुनिए", share: "WhatsApp पर भेजें", clear: "नई बातचीत",
    profile: "मेरी जानकारी", state: "राज्य", district: "ज़िला", land: "मेरे पास अपनी ज़मीन है", crop: "मुख्य फसल",
    type: "या यहाँ टाइप करें...", send: "भेजें", try: "ये पूछकर देखें:",
    chips: ["मेरे ज़िले में धान का भाव क्या है?", "मुझे कौन सी योजनाएँ मिल सकती हैं?", "क्या इस हफ़्ते बारिश होगी?", "मूँगफली कहाँ बेचूँ ताकि अच्छा भाव मिले?"],
  },
};

const DEFAULT_PROFILE = { state: "Andhra Pradesh", district: "", owns_land: false, main_crop: "" };

// Phone photos are huge; shrink before upload (faster, cheaper, same diagnosis quality).
async function shrink(file, max = 1024) {
  try {
    const bmp = await createImageBitmap(file);
    const scale = Math.min(1, max / Math.max(bmp.width, bmp.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * scale);
    canvas.height = Math.round(bmp.height * scale);
    canvas.getContext("2d").drawImage(bmp, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.85));
    return blob || file;
  } catch {
    return file;
  }
}

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
      return JSON.parse(localStorage.getItem("km-profile")) || DEFAULT_PROFILE;
    } catch {
      return DEFAULT_PROFILE;
    }
  });
  const recorder = useRef(null);
  const chunks = useRef([]);
  const history = useRef([]); // last turns, sent to the agent so follow-ups work

  function updateProfile(patch) {
    const next = { ...profile, ...patch };
    setProfile(next);
    try {
      localStorage.setItem("km-profile", JSON.stringify(next));
    } catch {
      /* storage unavailable */
    }
  }

  function speak(text) {
    try {
      const synth = window.speechSynthesis;
      if (!synth) return;
      synth.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = /[ఀ-౿]/.test(text) ? "te-IN" : /[ऀ-ॿ]/.test(text) ? "hi-IN" : "en-IN";
      synth.speak(u);
    } catch {
      /* speech not supported */
    }
  }

  function shareWhatsApp() {
    window.open("https://wa.me/?text=" + encodeURIComponent(`${t.title}\n\n${answer}`), "_blank");
  }

  function newConversation() {
    history.current = [];
    setQuestion("");
    setAnswer("");
    setSteps([]);
    setVerification(null);
    setError("");
  }

  function showResult(userText, data) {
    setAnswer(data.answer);
    setSteps(data.steps || []);
    setVerification(data.verification || null);
    history.current = [
      ...history.current,
      { role: "user", content: userText },
      { role: "assistant", content: data.answer },
    ].slice(-6);
  }

  function begin() {
    setError("");
    setSteps([]);
    setVerification(null);
    setAnswer(t.looking);
  }

  async function ask(text) {
    begin();
    setQuestion(text);
    try {
      const r = await fetch("/api/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, lang, profile, history: history.current }),
      });
      if (!r.ok) throw new Error((await r.json()).detail || "ask failed");
      showResult(text, await r.json());
    } catch (e) {
      setAnswer("");
      setError(e.message);
    }
  }

  function sendTyped() {
    const text = typed.trim();
    if (!text) return;
    setTyped("");
    ask(text);
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
        begin();
        try {
          const r = await fetch("/api/transcribe", { method: "POST", body: form });
          if (r.status === 422) throw new Error(t.unclear);
          if (!r.ok) throw new Error((await r.json()).detail || "transcribe failed");
          const { text } = await r.json();
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
    e.target.value = "";
    if (!file) return;
    begin();
    const form = new FormData();
    form.append("image", await shrink(file), "crop.jpg");
    form.append("question", typed.trim());
    form.append("lang", lang);
    form.append("profile", JSON.stringify(profile));
    try {
      const r = await fetch("/api/diagnose", { method: "POST", body: form });
      if (!r.ok) throw new Error((await r.json()).detail || "diagnose failed");
      const label = "📷 " + (typed.trim() || "crop photo");
      setQuestion(label);
      showResult(label, await r.json());
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
          {t.photo} <input type="file" accept="image/*" capture="environment" onChange={uploadPhoto} />
        </label>
      </div>
      <div style={{ marginTop: 12 }}>
        <small>{t.try}</small>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
          {t.chips.map((c) => (
            <button key={c} onClick={() => ask(c)} style={{ fontSize: 13, borderRadius: 14, padding: "4px 10px" }}>
              {c}
            </button>
          ))}
        </div>
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
        <div>
          <p style={{ whiteSpace: "pre-wrap" }}>
            <b>{t.bot}:</b> {answer}
          </p>
          {answer !== t.looking && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button onClick={() => speak(answer)}>{t.listen}</button>
              <button onClick={shareWhatsApp}>{t.share}</button>
              <button onClick={newConversation}>{t.clear}</button>
            </div>
          )}
        </div>
      )}
      {verification && (
        <p style={{ fontSize: 14, color: verification.passed ? "green" : "darkorange" }}>
          {verification.passed ? t.ok : t.warn + (verification.unverified || []).join(", ")}
        </p>
      )}
    </main>
  );
}
