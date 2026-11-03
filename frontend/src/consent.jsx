// First-run privacy and consent notice. Plain words, shown once, reopenable from the profile. Nothing is collected before "OK".
import { useState } from "react";
import { Sheet } from "./khata";

const S = {
  en: { title: "Your data stays with you", pts: [
    "Your profile, field record, money notebook, results, offers and expert cases are saved only on this phone. Signing in with Google is optional and only shows your name; the server keeps no farmer data.",
    "To answer, the app sends your question, crop and place (district) to our server and the Meta AI models. A photo you choose is sent for analysis and is not stored by the app.",
    "Sharing with an expert, or sending your place and photo, happens only when you tick it yourself each time.",
    "Answers are help, not a diagnosis or a promise. Prices and weather come from public sources and may be late; the app says when data is a sample or not live. For serious crop problems talk to an agriculture officer.",
  ], ok: "OK, I understand", close: "Close" },
  te: { title: "మీ డేటా మీ దగ్గరే ఉంటుంది", pts: [
    "మీ ప్రొఫైల్, పొలం రికార్డు, ఖాతా, ఫలితాలు, ఆఫర్లు, నిపుణుల కేసులు ఈ ఫోన్‌లోనే సేవ్ అవుతాయి. Google సైన్ ఇన్ ఐచ్ఛికం, అది మీ పేరు మాత్రమే చూపిస్తుంది; సర్వర్‌లో రైతు డేటా ఉండదు.",
    "జవాబు ఇవ్వడానికి మీ ప్రశ్న, పంట, ప్రదేశం (జిల్లా) మా సర్వర్‌కు, Meta AI మోడళ్లకు వెళ్తాయి. మీరు ఎంచుకున్న ఫోటో విశ్లేషణకు పంపబడుతుంది, యాప్ దాన్ని దాచదు.",
    "నిపుణుడితో పంచుకోవడం, ప్రదేశం, ఫోటో పంపడం ప్రతిసారీ మీరే టిక్ చేసినప్పుడే జరుగుతుంది.",
    "జవాబులు సహాయం మాత్రమే, నిర్ధారణ లేదా హామీ కాదు. ధరలు, వాతావరణం పబ్లిక్ వనరుల నుండి వస్తాయి, ఆలస్యం కావచ్చు; డేటా నమూనా అయితే లేదా ప్రత్యక్షం కాకపోతే యాప్ చెబుతుంది. తీవ్ర పంట సమస్యలకు వ్యవసాయ అధికారిని కలవండి.",
  ], ok: "సరే, అర్థమైంది", close: "మూసివేయి" },
  hi: { title: "आपका डेटा आपके पास रहता है", pts: [
    "आपकी प्रोफ़ाइल, खेत का रिकॉर्ड, खाता, नतीजे, ऑफ़र और विशेषज्ञ केस सिर्फ़ इसी फ़ोन में सेव होते हैं। Google साइन इन वैकल्पिक है और सिर्फ़ आपका नाम दिखाता है; सर्वर पर किसान का डेटा नहीं रहता।",
    "जवाब के लिए आपका सवाल, फसल और जगह (ज़िला) हमारे सर्वर और Meta AI मॉडल को भेजी जाती है। आपकी चुनी फ़ोटो विश्लेषण के लिए भेजी जाती है, ऐप उसे सहेजता नहीं।",
    "विशेषज्ञ से साझा करना, जगह या फ़ोटो भेजना तभी होता है जब आप हर बार खुद टिक करें।",
    "जवाब मदद हैं, निदान या वादा नहीं। भाव और मौसम सार्वजनिक स्रोतों से आते हैं और देर से हो सकते हैं; डेटा नमूना या लाइव न हो तो ऐप बताता है। गंभीर फसल समस्या में कृषि अधिकारी से मिलें।",
  ], ok: "ठीक है, समझ गया", close: "बंद करें" },
};
const KEY = "km-consent";
export const consentGiven = () => { try { return localStorage.getItem(KEY) === "1"; } catch { return true; } };

export function ConsentSheet({ lang, onDone }) {
  const t = S[lang] || S.en;
  const [open, setOpen] = useState(true);
  if (!open) return null;
  const done = () => { try { localStorage.setItem(KEY, "1"); } catch { /* storage unavailable */ } setOpen(false); onDone?.(); };
  return (
    <Sheet title={"🔒 " + t.title} onClose={done} close={t.close}>
      <ul className="plain">{t.pts.map((p, i) => <li key={i}>{p}</li>)}</ul>
      <button className="primary" onClick={done}>{t.ok}</button>
    </Sheet>
  );
}
