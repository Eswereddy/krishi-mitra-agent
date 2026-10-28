import { useRef, useState } from "react";

export default function App() {
  const [recording, setRecording] = useState(false);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [steps, setSteps] = useState([]);
  const [verification, setVerification] = useState(null);
  const recorder = useRef(null);
  const chunks = useRef([]);

  async function ask(text) {
    setSteps([]);
    setVerification(null);
    const r = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text }),
    });
    if (!r.ok) throw new Error((await r.json()).detail || "ask failed");
    const data = await r.json();
    setAnswer(data.answer);
    setSteps(data.steps || []);
    setVerification(data.verification || null);
  }

  async function start() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunks.current = [];
      mr.ondataavailable = (e) => chunks.current.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks.current, { type: "audio/webm" });
        const form = new FormData();
        form.append("audio", blob, "question.webm");
        try {
          const r = await fetch("/api/transcribe", { method: "POST", body: form });
          if (!r.ok) throw new Error((await r.json()).detail || "transcribe failed");
          const { text } = await r.json();
          setQuestion(text);
          await ask(text);
        } catch (e) {
          setError(e.message);
        }
      };
      mr.start();
      recorder.current = mr;
      setRecording(true);
    } catch (e) {
      setError("Mic access ivvandi: " + e.message);
    }
  }

  async function uploadPhoto(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    setAnswer("Photo chuduthunnanu...");
    const form = new FormData();
    form.append("image", file);
    form.append("question", question);
    try {
      const r = await fetch("/api/diagnose", { method: "POST", body: form });
      if (!r.ok) throw new Error((await r.json()).detail || "diagnose failed");
      setAnswer((await r.json()).answer);
    } catch (err) {
      setAnswer("");
      setError(err.message);
    }
  }

  function stop() {
    recorder.current?.stop();
    setRecording(false);
  }

  return (
    <main style={{ maxWidth: 560, margin: "40px auto", padding: 16, fontFamily: "system-ui" }}>
      <h1>🌾 Krishi Mitra</h1>
      <p>Mee prashna Telugu lo cheppandi.</p>
      <button onClick={recording ? stop : start} style={{ fontSize: 18, padding: "12px 20px" }}>
        {recording ? "⏹ Aapandi" : "🎤 Matladandi"}
      </button>
      <div style={{ marginTop: 12 }}>
        <label>
          📷 Pant photo pampandi:{" "}
          <input type="file" accept="image/*" capture="environment" onChange={uploadPhoto} />
        </label>
      </div>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      {question && (
        <p>
          <b>Meeru:</b> {question}
        </p>
      )}
      {steps.length > 0 && (
        <details open>
          <summary>Agent steps ({steps.length})</summary>
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
        <p>
          <b>Krishi Mitra:</b> {answer}
        </p>
      )}
      {verification && (
        <p style={{ fontSize: 14, color: verification.passed ? "green" : "darkorange" }}>
          {verification.passed
            ? "✅ Figures verified against tool results"
            : "⚠️ Some figures could not be verified: " + (verification.unverified || []).join(", ")}
        </p>
      )}
    </main>
  );
}
