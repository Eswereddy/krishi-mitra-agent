// Extras that use more of Meta's model family (all optional; the server answers 503 until MODEL_API_KEY is set):
//  - Leaf damage measurement with SAM 3.1 (the percentage is computed on the server from the masks)
//  - Shareable advice card with Muse Image
import { I } from "./components";

const S = {
  te: {
    week: "ఈ వారం", weekSub: "7 రోజుల ప్లాన్: ముందు ఏం చేయాలి",
    scan: "నష్టం కొలవండి", scanTitle: "ఆకు నష్టం కొలత", scanning: "SAM 3.1 ఆకును చూస్తోంది...", cardBtn: "కార్డ్", cardTitle: "షేర్ కార్డ్",
    making: "Muse Image కార్డ్ తయారుచేస్తోంది...", pct: "ఆకులో నష్టం", spots: "మచ్చల ప్రాంతాలు", photoBasis: "(ఫోటోలో శాతం)",
    bands: { none: "మచ్చలు కనిపించలేదు", mild: "తక్కువ", moderate: "మధ్యస్థం", severe: "ఎక్కువ" },
    expert: "నష్టం ఎక్కువ: వెంటనే వ్యవసాయ అధికారిని లేదా కిసాన్ కాల్ సెంటర్ 1800-180-1551 ను సంప్రదించండి.",
    note: "ఇది ఫోటో కొలత మాత్రమే, వ్యాధి నిర్ధారణ కాదు. మందు, మోతాదు కోసం వ్యవసాయ అధికారిని అడగండి.",
    unavailable: "ఈ సదుపాయం ఇప్పుడు అందుబాటులో లేదు.", download: "డౌన్‌లోడ్", share: "షేర్", close: "మూసివేయి", again: "మళ్లీ ప్రయత్నించు",
  },
  en: {
    week: "This week", weekSub: "7-day plan: what to do first",
    scan: "Measure damage", scanTitle: "Leaf damage measurement", scanning: "SAM 3.1 is looking at the leaf...", cardBtn: "Card", cardTitle: "Share card",
    making: "Muse Image is making the card...", pct: "of the leaf is marked", spots: "marked areas", photoBasis: "(of the whole photo)",
    bands: { none: "No lesions found", mild: "Mild", moderate: "Moderate", severe: "Severe" },
    expert: "Heavy damage: contact the agriculture officer or the Kisan Call Centre 1800-180-1551 now.",
    note: "This measures the photo only. It is not a diagnosis. Ask the agriculture officer for the product and dose.",
    unavailable: "This feature is not available right now.", download: "Download", share: "Share", close: "Close", again: "Try again",
  },
  hi: {
    week: "इस हफ़्ते", weekSub: "7 दिन की योजना: पहले क्या करें",
    scan: "नुकसान मापें", scanTitle: "पत्ती के नुकसान की माप", scanning: "SAM 3.1 पत्ती देख रहा है...", cardBtn: "कार्ड", cardTitle: "शेयर कार्ड",
    making: "Muse Image कार्ड बना रहा है...", pct: "पत्ती पर निशान", spots: "निशान वाले हिस्से", photoBasis: "(पूरी फ़ोटो का हिस्सा)",
    bands: { none: "कोई धब्बा नहीं मिला", mild: "हल्का", moderate: "मध्यम", severe: "ज़्यादा" },
    expert: "नुकसान ज़्यादा है: अभी कृषि अधिकारी या किसान कॉल सेंटर 1800-180-1551 से संपर्क करें।",
    note: "यह सिर्फ़ फ़ोटो की माप है, बीमारी की पहचान नहीं। दवा और मात्रा के लिए कृषि अधिकारी से पूछें।",
    unavailable: "यह सुविधा अभी उपलब्ध नहीं है।", download: "डाउनलोड", share: "शेयर", close: "बंद करें", again: "फिर कोशिश करें",
  },
};
export const ex = (lang) => S[lang] || S.en;

async function shrink(file, max = 1024) {
  try {
    const bmp = await createImageBitmap(file);
    const k = Math.min(1, max / Math.max(bmp.width, bmp.height));
    const c = document.createElement("canvas");
    c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
    c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
    return (await new Promise((res) => c.toBlob(res, "image/jpeg", 0.88))) || file;
  } catch { return file; }
}

async function fail(r, fallback) {
  let d = "";
  try { d = (await r.json()).detail; } catch { /* not json */ }
  throw new Error(r.status === 503 ? fallback : d || `Error ${r.status}`);
}

export async function leafScan(file, unavailable) {
  const form = new FormData();
  form.append("image", await shrink(file), "leaf.jpg");
  const r = await fetch("/api/leaf-scan", { method: "POST", body: form });
  if (!r.ok) await fail(r, unavailable);
  return r.json();
}

export async function adviceCard(text, lang, crop, unavailable) {
  const r = await fetch("/api/advice-card", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, lang: lang === "auto" ? "te" : lang, crop }) });
  if (!r.ok) await fail(r, unavailable);
  return r.json();
}

function Sheet({ title, onClose, close, children }) {
  return (
    <div className="sheet-bg" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        {children}
        <button className="primary" onClick={onClose}>{close}</button>
      </div>
    </div>
  );
}

export function ExtraSheet({ extra, lang, onClose, onRetry }) {
  const t = ex(lang);
  if (!extra) return null;
  const { kind, loading, data, error } = extra;
  const isScan = kind === "scan";
  return (
    <Sheet title={(isScan ? "🔬 " + t.scanTitle : "🖼️ " + t.cardTitle)} onClose={onClose} close={t.close}>
      {loading && <p className="hint"><b className="mini-spin" /> {isScan ? t.scanning : t.making}</p>}
      {error && <><p className="hint">⚠️ {error}</p><button className="pill" onClick={onRetry}>↻ {t.again}</button></>}
      {data && isScan && (
        <>
          <img className="extra-img" src={data.overlay} alt="" />
          <div className={"decision " + (data.band === "severe" ? "falling" : data.band === "none" || data.band === "mild" ? "rising" : "steady")}>
            <b>{t.bands[data.band]}{data.found ? ` · ${data.severity_pct}% ${t.pct}` : ""}</b>
            {data.found && data.basis === "photo" && <small> {t.photoBasis}</small>}
          </div>
          {data.found && <p className="hint">{data.spot_count} {t.spots}</p>}
          {data.needs_expert && <p className="warn-note">☎️ {t.expert}</p>}
          <p className="hint">{t.note}</p>
        </>
      )}
      {data && !isScan && (
        <>
          <img className="extra-img" src={data.image} alt={data.text} />
          <div className="alert-actions">
            <a className="pill" href={data.image} download="krishi-mitra-card.png">⬇️ {t.download}</a>
            <button className="pill" onClick={() => shareImage(data)}><I.whatsapp />{t.share}</button>
          </div>
        </>
      )}
    </Sheet>
  );
}

async function shareImage(data) {
  try {
    const blob = await (await fetch(data.image)).blob();
    const file = new File([blob], "krishi-mitra-card.png", { type: "image/png" });
    if (navigator.canShare?.({ files: [file] })) return await navigator.share({ files: [file], text: data.text });
  } catch { /* user cancelled or unsupported: fall through to text share */ }
  window.open("https://wa.me/?text=" + encodeURIComponent(data.text), "_blank");
}
