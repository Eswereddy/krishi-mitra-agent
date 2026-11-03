"""Machine safety check: the operator ticks what is true right now (machine, ground, light, who is nearby, how they feel, what is fitted) and gets
ranked warnings for rollover, collision, entanglement, power lines and operator fitness, each with one clear action.

What this is: rules written in code from common farm-machinery safety practice, applied to what the operator reports.
What this is NOT: the app has no sensor or camera on the machine, so it cannot see a hazard that was not ticked, cannot detect a
collision and does not replace training or the machine manual. The answer says so every time. No numbers are invented: slope and
weather come from the operator's own choice, never from a guessed threshold. Computed in code, never by a model.
"""

MACHINES = ("tractor", "tiller", "thresher", "harvester", "sprayer", "trailer", "pump")
PTO = {"tractor", "tiller", "thresher", "pump"}
ROLL = {"tractor", "harvester", "trailer", "tiller"}
MOVING = {"tractor", "tiller", "harvester", "sprayer", "trailer"}
RAISE = {"tractor", "harvester", "trailer"}

GROUPS = {
    "ground": ["slope_steep", "ground_wet", "ditch_edge", "narrow_path", "heavy_rain", "strong_wind"],
    "light": ["night", "low_vis", "hot_midday"],
    "around": ["children_near", "people_near", "animals_near", "power_lines", "road_crossing", "other_vehicles", "blind_corner"],
    "operator": ["unwell_or_drowsy", "tired", "hours_4plus", "working_alone", "loose_clothing", "first_time"],
    "machine": ["riders", "no_rops_belt", "pto_guard_missing", "overloaded", "brakes_unchecked", "implement_raised", "reversing"],
}
CODES = [c for g in GROUPS.values() for c in g]
LEVELS = {"stop": 3, "high": 2, "caution": 1, "ok": 0}
KIND_ICON = {"rollover": "⛰️", "collision": "💥", "entanglement": "⚙️", "power": "⚡", "operator": "🧍", "environment": "🌧️"}

# text per code: {"t": what is wrong, "do": what to do}
W = {
    "unwell_or_drowsy": {"en": ("Drowsy, unwell or affected by drink or medicine", "Do not operate the machine. Let someone else do the work or wait until you are fully fit."),
                         "te": ("నిద్రమత్తు, అనారోగ్యం, లేదా మద్యం/మందుల ప్రభావం", "యంత్రం నడపకండి. వేరొకరు చేయనివ్వండి, లేదా పూర్తిగా కోలుకునే వరకు ఆగండి."),
                         "hi": ("नींद, बीमारी या शराब/दवा का असर", "मशीन न चलाएँ। किसी और से करवाएँ या पूरी तरह ठीक होने तक रुकें।")},
    "riders": {"en": ("People are riding on the machine", "Nobody may ride on mudguards, drawbar or trailer hitch. Get everyone off before moving."),
               "te": ("యంత్రం మీద మనుషులు ఎక్కి ఉన్నారు", "మడ్‌గార్డ్, డ్రాబార్ లేదా ట్రైలర్ హిచ్ మీద ఎవరూ ఎక్కకూడదు. కదలక ముందు అందరినీ దించండి."),
               "hi": ("मशीन पर लोग सवार हैं", "मडगार्ड, ड्रॉबार या ट्रेलर हिच पर कोई न बैठे। चलने से पहले सबको उतारें।")},
    "pto_guard_missing": {"en": ("A guard on the spinning shaft or belt is missing", "Stop the engine and fit the guard before any work. Never step over a turning shaft."),
                          "te": ("తిరిగే షాఫ్ట్ లేదా బెల్ట్ గార్డ్ లేదు", "ఇంజిన్ ఆపి గార్డ్ బిగించిన తర్వాతే పని చేయండి. తిరిగే షాఫ్ట్ మీద నుంచి దాటకండి."),
                          "hi": ("घूमते शाफ्ट या बेल्ट का गार्ड नहीं लगा", "इंजन बंद करें और गार्ड लगाकर ही काम करें। घूमते शाफ्ट के ऊपर से न लाँघें।")},
    "children_near": {"en": ("Children are near the machine", "Stop. Do not move until every child is far away and an adult is watching them. Keep children out of the work area."),
                      "te": ("యంత్రం దగ్గర పిల్లలు ఉన్నారు", "ఆగండి. పిల్లలందరూ దూరంగా వెళ్లి, పెద్దవారు చూసుకునే వరకు కదలకండి. పని ప్రాంతంలోకి పిల్లలను రానివ్వకండి."),
                      "hi": ("मशीन के पास बच्चे हैं", "रुकें। सब बच्चे दूर जाकर कोई बड़ा उन्हें संभाल न ले तब तक न चलें। बच्चों को काम की जगह से दूर रखें।")},
    "power_raised": {"en": ("Raised part or tall load near overhead power lines", "Lower it now and keep well away from the lines. Treat every line as live and never touch a machine that touches a line."),
                     "te": ("విద్యుత్ తీగల దగ్గర ఎత్తిన భాగం లేదా ఎత్తైన లోడ్", "వెంటనే దించండి, తీగలకు దూరంగా ఉండండి. ప్రతి తీగను కరెంటు ఉన్నదిగా భావించండి; తీగ తగిలిన యంత్రాన్ని ముట్టుకోకండి."),
                     "hi": ("बिजली की तारों के पास ऊँचा हिस्सा या ऊँचा लोड", "अभी नीचे करें और तारों से दूर रहें। हर तार को चालू मानें; तार से छूती मशीन को न छुएँ।")},
    "loose_thresher": {"en": ("Loose clothing near a feeding or spinning part", "Stop. Tie or remove loose cloth, scarf and long hair ends before feeding or going near moving parts."),
                       "te": ("కదిలే భాగాల దగ్గర వదులు బట్టలు", "ఆగండి. వదులు బట్టలు, కండువా, పొడవైన జుట్టు కట్టి లేదా తీసి వేసిన తర్వాతే పని చేయండి."),
                       "hi": ("चलते हिस्सों के पास ढीले कपड़े", "रुकें। ढीले कपड़े, गमछा और लंबे बाल बाँधें या हटाएँ, फिर ही काम करें।")},
    "reverse_people": {"en": ("Reversing with people nearby", "Stop. Ask someone to stand clear in your view and guide you, or get down and check behind first."),
                       "te": ("దగ్గర మనుషులు ఉండగా వెనక్కి నడపడం", "ఆగండి. ఎవరినైనా మీకు కనిపించేలా దూరంగా నిలబడి సైగ చేయమనండి, లేదా దిగి వెనుక చూడండి."),
                       "hi": ("आसपास लोग हैं और मशीन पीछे ले रहे हैं", "रुकें। किसी को आपको दिखने वाली जगह पर खड़ा करें, या उतरकर पीछे देख लें।")},
    "steep_wet_roll": {"en": ("Steep slope on wet ground: high risk of sliding or rolling over", "Do not work this slope now. Wait for the ground to dry or use another route."),
                       "te": ("తడి నేలపై నిటారు వాలు: జారడం లేదా బోల్తా పడే ప్రమాదం ఎక్కువ", "ఇప్పుడు ఈ వాలుపై పని చేయకండి. నేల ఆరే వరకు ఆగండి లేదా వేరే దారి చూడండి."),
                       "hi": ("गीली ज़मीन पर तेज़ ढलान: फिसलने या पलटने का ज़्यादा खतरा", "अभी इस ढलान पर काम न करें। ज़मीन सूखने तक रुकें या दूसरा रास्ता लें।")},
    "slope_steep": {"en": ("Steep slope", "Go straight up or down, never across. Use a low gear, no sudden turns, no sudden braking."),
                    "te": ("నిటారు వాలు", "నేరుగా పైకి లేదా కిందికి వెళ్లండి, అడ్డంగా కాదు. తక్కువ గేర్ వాడండి, ఆకస్మిక మలుపులు, ఆకస్మిక బ్రేకులు వద్దు."),
                    "hi": ("तेज़ ढलान", "सीधे ऊपर या नीचे जाएँ, आड़े नहीं। निचला गियर लगाएँ, अचानक मोड़ या ब्रेक न लगाएँ।")},
    "no_rops_belt": {"en": ("No roll-over frame or seat belt", "Do not work on slopes, near ditches or on wet ground. Fit a roll-over frame, and wear the belt if the frame is fitted."),
                     "te": ("రోల్-ఓవర్ ఫ్రేమ్ లేదా సీటు బెల్ట్ లేదు", "వాలులు, గుంతల అంచులు, తడి నేలలో పని చేయకండి. రోల్-ఓవర్ ఫ్రేమ్ బిగించండి; ఫ్రేమ్ ఉంటే బెల్ట్ పెట్టుకోండి."),
                     "hi": ("रोल-ओवर फ्रेम या सीट बेल्ट नहीं है", "ढलान, गड्ढे के किनारे या गीली ज़मीन पर काम न करें। रोल-ओवर फ्रेम लगवाएँ; फ्रेम हो तो बेल्ट बाँधें।")},
    "ditch_wet": {"en": ("Wet edge of a ditch, canal, pond or bund can collapse", "Stay well back from the edge and mark a safe line. Do not drive close to it."),
                  "te": ("తడి గుంత, కాలువ, చెరువు లేదా గట్టు అంచు కూలిపోవచ్చు", "అంచు నుంచి దూరంగా ఉండండి, సురక్షిత గీత గుర్తు పెట్టండి. దగ్గరగా నడపకండి."),
                  "hi": ("गीले गड्ढे, नहर, तालाब या मेड़ का किनारा धँस सकता है", "किनारे से दूर रहें और सुरक्षित रेखा चिह्नित करें। उसके पास गाड़ी न चलाएँ।")},
    "ditch_edge": {"en": ("Work near a ditch, canal, pond or bund edge", "Keep a safe distance from the edge, and go slowly near it."),
                   "te": ("గుంత, కాలువ, చెరువు లేదా గట్టు అంచు దగ్గర పని", "అంచు నుంచి సురక్షిత దూరం ఉంచండి, దగ్గర నెమ్మదిగా వెళ్లండి."),
                   "hi": ("गड्ढे, नहर, तालाब या मेड़ के किनारे के पास काम", "किनारे से सुरक्षित दूरी रखें और पास धीरे चलें।")},
    "overloaded": {"en": ("Trailer or machine is overloaded", "Unload part of it. An overloaded trailer cannot stop or turn safely and can tip."),
                   "te": ("ట్రైలర్ లేదా యంత్రంపై ఎక్కువ బరువు", "కొంత దించండి. ఎక్కువ బరువుతో ఆగడం, మలుపు తిరగడం కష్టం, బోల్తా పడవచ్చు."),
                   "hi": ("ट्रेलर या मशीन पर ज़्यादा वज़न", "कुछ माल उतारें। ज़्यादा वज़न से रुकना और मुड़ना मुश्किल होता है, पलट सकता है।")},
    "brakes_unchecked": {"en": ("Brakes not checked today", "Test the brakes at walking speed in an empty place before the real work."),
                         "te": ("ఈరోజు బ్రేకులు పరీక్షించలేదు", "అసలు పనికి ముందు ఖాళీ చోట నెమ్మదిగా బ్రేకులు పరీక్షించండి."),
                         "hi": ("आज ब्रेक जाँचे नहीं", "असली काम से पहले खाली जगह धीमी रफ़्तार पर ब्रेक जाँच लें।")},
    "tired": {"en": ("Very tired or short of sleep", "Rest before you operate. Tiredness slows reaction like drink does."),
              "te": ("చాలా అలసట లేదా నిద్ర తక్కువ", "యంత్రం నడపక ముందు విశ్రాంతి తీసుకోండి. అలసట వల్ల స్పందన నెమ్మదిస్తుంది."),
              "hi": ("बहुत थकान या कम नींद", "मशीन चलाने से पहले आराम करें। थकान से प्रतिक्रिया धीमी हो जाती है।")},
    "hours_4plus": {"en": ("Driving for four hours or more without a break", "Stop for a break, drink water and stretch before you continue."),
                    "te": ("విరామం లేకుండా నాలుగు గంటలకు పైగా నడపడం", "ఆగి విరామం తీసుకోండి, నీరు తాగండి, శరీరం సాగదీసి తర్వాత కొనసాగండి."),
                    "hi": ("बिना रुके चार घंटे या ज़्यादा चलाना", "रुककर आराम करें, पानी पिएँ और शरीर खींचकर ही आगे बढ़ें।")},
    "night_road": {"en": ("Low light or poor view on a road or near other vehicles", "Switch on all lights and reflectors, go slowly, and do not take the road unless you must."),
                   "te": ("రోడ్డు మీద లేదా ఇతర వాహనాల దగ్గర తక్కువ వెలుతురు, సరిగా కనిపించదు", "అన్ని లైట్లు, రిఫ్లెక్టర్లు వేయండి, నెమ్మదిగా వెళ్లండి; తప్పనిసరి అయితేనే రోడ్డు ఎక్కండి."),
                   "hi": ("सड़क या दूसरे वाहनों के पास कम रोशनी, कम दिखना", "सारी लाइट और रिफ्लेक्टर चालू करें, धीरे चलें; ज़रूरी न हो तो सड़क पर न जाएँ।")},
    "night": {"en": ("Working in the dark or at dusk", "Use working lights, keep the area clear of people and animals, and take extra care at edges and ditches."),
              "te": ("చీకటిలో లేదా సంధ్య వేళ పని", "వర్కింగ్ లైట్లు వాడండి, మనుషులు, పశువులు లేకుండా చూడండి, అంచులు, గుంతల దగ్గర మరింత జాగ్రత్త."),
              "hi": ("अँधेरे या शाम के समय काम", "वर्किंग लाइट चलाएँ, लोगों और पशुओं को दूर रखें, किनारों और गड्ढों के पास ज़्यादा सावधान रहें।")},
    "low_vis": {"en": ("Fog, dust or heavy rain: poor view", "Slow down, use lights, and stop if you cannot see the edge of the field or people nearby."),
                "te": ("పొగమంచు, దుమ్ము లేదా భారీ వర్షం: సరిగా కనిపించదు", "నెమ్మదిగా వెళ్లండి, లైట్లు వేయండి; పొలం అంచు లేదా దగ్గరి మనుషులు కనిపించకపోతే ఆగండి."),
                "hi": ("कोहरा, धूल या भारी बारिश: कम दिखता है", "धीरे चलें, लाइट चालू करें; खेत का किनारा या पास के लोग न दिखें तो रुक जाएँ।")},
    "blind_people": {"en": ("A blind corner with people or vehicles about", "Slow right down, sound the horn before the corner and be ready to stop."),
                     "te": ("మనుషులు లేదా వాహనాలు ఉన్న కనిపించని మలుపు", "చాలా నెమ్మదిగా వెళ్లండి, మలుపు ముందు హారన్ కొట్టండి, ఆపడానికి సిద్ధంగా ఉండండి."),
                     "hi": ("ऐसा मोड़ जहाँ लोग या वाहन हो सकते हैं और कुछ दिखता नहीं", "बहुत धीरे चलें, मोड़ से पहले हॉर्न दें और रुकने को तैयार रहें।")},
    "blind_corner": {"en": ("A blind corner or crest", "Slow down and sound the horn before you reach it."),
                     "te": ("కనిపించని మలుపు లేదా ఎత్తు", "నెమ్మదిగా వెళ్లండి, అక్కడికి చేరే ముందు హారన్ కొట్టండి."),
                     "hi": ("दिखाई न देने वाला मोड़ या ऊँचाई", "धीरे चलें और वहाँ पहुँचने से पहले हॉर्न दें।")},
    "loose_clothing": {"en": ("Loose clothing, scarf or long hair near moving parts", "Tie or remove them. Cloth caught in a turning shaft pulls the body in within a moment."),
                       "te": ("కదిలే భాగాల దగ్గర వదులు బట్టలు, కండువా లేదా పొడవైన జుట్టు", "కట్టండి లేదా తీసేయండి. తిరిగే షాఫ్ట్‌లో బట్ట చిక్కితే క్షణంలో శరీరాన్ని లాగేస్తుంది."),
                       "hi": ("चलते हिस्सों के पास ढीले कपड़े, गमछा या लंबे बाल", "उन्हें बाँधें या हटाएँ। घूमते शाफ्ट में कपड़ा फँसे तो पल भर में शरीर खिंच जाता है।")},
    "heavy_rain_slope": {"en": ("Heavy rain with a slope: slippery ground", "Stop working on the slope until the rain passes and the ground firms up."),
                         "te": ("భారీ వర్షం, వాలు కూడా: నేల జారుడు", "వర్షం ఆగి నేల గట్టిపడే వరకు వాలుపై పని ఆపండి."),
                         "hi": ("भारी बारिश और ढलान: ज़मीन फिसलन भरी", "बारिश रुकने और ज़मीन जमने तक ढलान पर काम बंद रखें।")},
    "heavy_rain": {"en": ("Heavy rain", "Wet ground makes the machine slide and lengthens braking. Slow down, or wait."),
                   "te": ("భారీ వర్షం", "తడి నేలలో యంత్రం జారుతుంది, ఆగడానికి ఎక్కువ దూరం పడుతుంది. నెమ్మదిగా వెళ్లండి లేదా ఆగండి."),
                   "hi": ("भारी बारिश", "गीली ज़मीन पर मशीन फिसलती है और रुकने में ज़्यादा दूरी लगती है। धीरे चलें या रुकें।")},
    "ground_wet": {"en": ("Wet or muddy ground", "Go slowly, avoid sharp turns, keep away from edges, and do not overload."),
                   "te": ("తడి లేదా బురద నేల", "నెమ్మదిగా వెళ్లండి, ఆకస్మిక మలుపులు వద్దు, అంచులకు దూరంగా ఉండండి, ఎక్కువ బరువు వేయకండి."),
                   "hi": ("गीली या कीचड़ वाली ज़मीन", "धीरे चलें, तेज़ मोड़ न लें, किनारों से दूर रहें और ज़्यादा वज़न न डालें।")},
    "spray_wind": {"en": ("Strong wind while spraying", "Do not spray now. The wind carries spray onto you, people and neighbouring crops."),
                   "te": ("స్ప్రే చేసేటప్పుడు బలమైన గాలి", "ఇప్పుడు స్ప్రే చేయకండి. గాలి స్ప్రేను మీ మీదకు, ఇతరుల మీదకు, పక్క పంటల మీదకు తీసుకెళ్తుంది."),
                   "hi": ("छिड़काव के समय तेज़ हवा", "अभी छिड़काव न करें। हवा दवा को आप, लोगों और पड़ोसी फसलों पर उड़ा देती है।")},
    "strong_wind": {"en": ("Strong wind", "Take care with raised parts and loads, and with dust that hides your view."),
                    "te": ("బలమైన గాలి", "ఎత్తిన భాగాలు, లోడ్లు, చూపు కప్పే దుమ్ము విషయంలో జాగ్రత్త."),
                    "hi": ("तेज़ हवा", "ऊँचे हिस्सों, लोड और नज़र रोकने वाली धूल से सावधान रहें।")},
    "people_near": {"en": ("People are close to the machine", "Slow down, keep them in view, and agree where they will stand. Never let anyone stand behind or beside a moving implement."),
                    "te": ("యంత్రం దగ్గర మనుషులు ఉన్నారు", "నెమ్మదిగా వెళ్లండి, వారు కనిపించేలా ఉంచండి, ఎక్కడ నిలబడాలో చెప్పండి. కదిలే పనిముట్టు వెనుక లేదా పక్కన ఎవరూ నిలబడకూడదు."),
                    "hi": ("मशीन के पास लोग हैं", "धीरे चलें, उन्हें नज़र में रखें और बताएँ कहाँ खड़े रहें। चलते औज़ार के पीछे या बगल में कोई न खड़ा हो।")},
    "animals_near": {"en": ("Animals near the machine", "Go slowly and sound the horn. Animals can bolt into your path."),
                     "te": ("యంత్రం దగ్గర పశువులు", "నెమ్మదిగా వెళ్లండి, హారన్ కొట్టండి. పశువులు అకస్మాత్తుగా అడ్డం రావచ్చు."),
                     "hi": ("मशीन के पास पशु", "धीरे चलें और हॉर्न दें। पशु अचानक रास्ते में आ सकते हैं।")},
    "power_lines": {"en": ("Overhead power lines in the work area", "Note where they are before you start. Keep every raised part and tall load well below and away from them."),
                    "te": ("పని ప్రాంతంలో పైన విద్యుత్ తీగలు", "మొదలుపెట్టే ముందు అవి ఎక్కడ ఉన్నాయో గమనించండి. ఎత్తిన భాగాలు, ఎత్తైన లోడ్లను వాటికి దూరంగా, కిందే ఉంచండి."),
                    "hi": ("काम की जगह पर ऊपर बिजली की तारें", "शुरू करने से पहले देख लें कहाँ हैं। ऊँचे हिस्से और ऊँचा लोड तारों से दूर और नीचे रखें।")},
    "road_crossing": {"en": ("Crossing or using a road", "Stop and look both ways, give way to faster vehicles, and check the trailer and lights first."),
                      "te": ("రోడ్డు దాటడం లేదా రోడ్డుపై నడపడం", "ఆగి రెండు వైపులా చూడండి, వేగవంతమైన వాహనాలకు దారి ఇవ్వండి, ముందు ట్రైలర్, లైట్లు చూసుకోండి."),
                      "hi": ("सड़क पार करना या सड़क पर चलना", "रुककर दोनों ओर देखें, तेज़ वाहनों को रास्ता दें और पहले ट्रेलर व लाइट जाँच लें।")},
    "other_vehicles": {"en": ("Other vehicles in the work area or on the path", "Keep a safe gap, agree who goes first, and do not overtake on a bend or a slope."),
                       "te": ("పని ప్రాంతంలో లేదా దారిలో ఇతర వాహనాలు", "సురక్షిత దూరం ఉంచండి, ఎవరు ముందు వెళ్లాలో నిర్ణయించుకోండి, మలుపు లేదా వాలుపై ఓవర్‌టేక్ చేయకండి."),
                       "hi": ("काम की जगह या रास्ते में दूसरे वाहन", "सुरक्षित दूरी रखें, तय करें कि पहले कौन जाएगा, और मोड़ या ढलान पर ओवरटेक न करें।")},
    "narrow_path": {"en": ("Narrow path or bund", "Go slowly in a straight line, and do not meet other vehicles on it."),
                    "te": ("ఇరుకైన దారి లేదా గట్టు", "నేరుగా నెమ్మదిగా వెళ్లండి; అక్కడ ఇతర వాహనాలను ఎదుర్కోకండి."),
                    "hi": ("संकरा रास्ता या मेड़", "सीधी रेखा में धीरे चलें और वहाँ दूसरे वाहन से आमना-सामना न करें।")},
    "hot_midday": {"en": ("Very hot hours", "Drink water, take shade breaks, and avoid the hottest hours of the day. Heat makes you slow and careless."),
                   "te": ("చాలా వేడి గంటలు", "నీరు తాగండి, నీడలో విరామాలు తీసుకోండి, ఎండ ఎక్కువగా ఉండే సమయం తప్పించండి. వేడి వల్ల నెమ్మదిగా, అజాగ్రత్తగా అవుతారు."),
                   "hi": ("बहुत गर्म घंटे", "पानी पिएँ, छाँव में आराम करें और दिन के सबसे गर्म समय से बचें। गर्मी में आदमी सुस्त और लापरवाह हो जाता है।")},
    "working_alone": {"en": ("Working alone", "Tell someone where you are and when you will be back. Keep your phone charged and within reach."),
                      "te": ("ఒంటరిగా పని", "మీరు ఎక్కడ ఉన్నారో, ఎప్పుడు తిరిగి వస్తారో ఎవరికైనా చెప్పండి. ఫోన్ ఛార్జ్ చేసి దగ్గర ఉంచండి."),
                      "hi": ("अकेले काम", "किसी को बताएँ कि आप कहाँ हैं और कब लौटेंगे। फ़ोन चार्ज रखें और पास रखें।")},
    "first_time": {"en": ("New to this machine", "Practise on flat open ground with an experienced person, and read the manual's safety page first."),
                   "te": ("ఈ యంత్రం కొత్త", "అనుభవం ఉన్నవారితో సమతల ఖాళీ నేలపై ప్రాక్టీస్ చేయండి; ముందు మాన్యువల్‌లో భద్రత పేజీ చదవండి."),
                   "hi": ("इस मशीन पर नए हैं", "अनुभवी व्यक्ति के साथ समतल खुली ज़मीन पर अभ्यास करें और पहले मैनुअल का सुरक्षा पन्ना पढ़ें।")},
    "implement_raised": {"en": ("Implement, loader or load is raised", "Keep it as low as possible while moving. A raised weight makes the machine tip more easily."),
                         "te": ("పనిముట్టు, లోడర్ లేదా లోడ్ పైకి ఎత్తి ఉంది", "కదిలేటప్పుడు వీలైనంత కిందే ఉంచండి. పైకి ఎత్తిన బరువు వల్ల యంత్రం సులభంగా బోల్తా పడుతుంది."),
                         "hi": ("औज़ार, लोडर या लोड ऊपर उठा है", "चलते समय जितना हो सके नीचे रखें। ऊपर उठा वज़न मशीन को आसानी से पलटा देता है।")},
    "reversing": {"en": ("Reversing", "Look behind before and while you reverse. Go slowly."),
                  "te": ("వెనక్కి నడపడం", "వెనక్కి నడిపే ముందు, నడిపేటప్పుడు వెనుక చూడండి. నెమ్మదిగా వెళ్లండి."),
                  "hi": ("पीछे ले रहे हैं", "पीछे लेने से पहले और लेते समय पीछे देखें। धीरे चलें।")},
}
LV = {"en": {"stop": "STOP: do not operate", "high": "HIGH RISK: fix these first", "caution": "Take care", "ok": "No risk reported"},
      "te": {"stop": "ఆపండి: యంత్రం నడపవద్దు", "high": "ఎక్కువ ప్రమాదం: ముందు వీటిని సరిచేయండి", "caution": "జాగ్రత్త", "ok": "ప్రమాదం ఏదీ చెప్పలేదు"},
      "hi": {"stop": "रुकें: मशीन न चलाएँ", "high": "ज़्यादा खतरा: पहले इन्हें ठीक करें", "caution": "सावधान रहें", "ok": "कोई खतरा नहीं बताया"}}
NOTE = {"en": "This uses only what you tick. The app has no sensor or camera on the machine, so it cannot see a hazard you did not report, and it cannot detect a collision. It does not replace training or the machine manual.",
        "te": "మీరు టిక్ చేసినవే ఇది లెక్కలోకి తీసుకుంటుంది. యంత్రంపై సెన్సార్ లేదా కెమెరా లేదు, కాబట్టి మీరు చెప్పని ప్రమాదాన్ని చూడలేదు, ఢీకొనడాన్ని గుర్తించలేదు. శిక్షణ లేదా యంత్ర మాన్యువల్‌కు ప్రత్యామ్నాయం కాదు.",
        "hi": "यह सिर्फ़ वही देखता है जो आप टिक करते हैं। मशीन पर कोई सेंसर या कैमरा नहीं है, इसलिए यह बिना बताया खतरा नहीं देख सकता और टक्कर नहीं पकड़ सकता। यह प्रशिक्षण या मशीन मैनुअल की जगह नहीं लेता।"}
KIND_T = {"en": {"rollover": "Rollover", "collision": "Collision", "entanglement": "Entanglement", "power": "Power line", "operator": "Operator", "environment": "Conditions"},
          "te": {"rollover": "బోల్తా", "collision": "ఢీకొనడం", "entanglement": "చిక్కుకోవడం", "power": "విద్యుత్ తీగ", "operator": "ఆపరేటర్", "environment": "పరిస్థితులు"},
          "hi": {"rollover": "पलटना", "collision": "टक्कर", "entanglement": "फँसना", "power": "बिजली की तार", "operator": "ऑपरेटर", "environment": "हालात"}}


def _rules(machine: str, c: set) -> list:
    """[(code, level, kind)] in no particular order."""
    r = []
    add = lambda code, level, kind: r.append((code, level, kind))
    moving = machine in MOVING
    pto_machine = machine in PTO
    if "unwell_or_drowsy" in c: add("unwell_or_drowsy", "stop", "operator")
    if "riders" in c and machine in {"tractor", "trailer", "tiller", "harvester"}: add("riders", "stop", "collision")
    if "pto_guard_missing" in c and pto_machine: add("pto_guard_missing", "stop", "entanglement")
    if "children_near" in c: add("children_near", "stop", "collision")
    if "power_lines" in c and "implement_raised" in c and machine in RAISE: add("power_raised", "stop", "power")
    elif "power_lines" in c: add("power_lines", "caution", "power")
    if "loose_clothing" in c and machine in {"thresher", "harvester"}: add("loose_thresher", "stop", "entanglement")
    elif "loose_clothing" in c and pto_machine: add("loose_clothing", "high", "entanglement")
    elif "loose_clothing" in c: add("loose_clothing", "caution", "entanglement")
    if "reversing" in c and "people_near" in c and moving: add("reverse_people", "stop", "collision")
    elif "reversing" in c and moving: add("reversing", "caution", "collision")
    steep, wet = "slope_steep" in c, "ground_wet" in c or "heavy_rain" in c
    if steep and wet and machine in ROLL: add("steep_wet_roll", "stop", "rollover")
    elif steep and machine in ROLL: add("slope_steep", "caution", "rollover")
    if "no_rops_belt" in c and machine == "tractor": add("no_rops_belt", "high" if (steep or "ditch_edge" in c or wet) else "caution", "rollover")
    if "ditch_edge" in c and wet and machine in ROLL: add("ditch_wet", "high", "rollover")
    elif "ditch_edge" in c and machine in ROLL: add("ditch_edge", "caution", "rollover")
    if "overloaded" in c and machine in {"trailer", "tractor", "harvester"}: add("overloaded", "high", "rollover")
    if "brakes_unchecked" in c and machine in {"tractor", "trailer", "harvester"}: add("brakes_unchecked", "high", "collision")
    if "implement_raised" in c and machine in RAISE and "power_lines" not in c: add("implement_raised", "caution", "rollover")
    if "tired" in c: add("tired", "high", "operator")
    if "hours_4plus" in c: add("hours_4plus", "caution", "operator")
    dark = bool(c & {"night", "low_vis"})
    if dark and (c & {"road_crossing", "other_vehicles"}) and moving: add("night_road", "high", "collision")
    elif "night" in c and moving: add("night", "caution", "environment")
    elif "low_vis" in c and moving: add("low_vis", "caution", "environment")
    if "blind_corner" in c and (c & {"people_near", "children_near", "other_vehicles"}) and moving: add("blind_people", "high", "collision")
    elif "blind_corner" in c and moving: add("blind_corner", "caution", "collision")
    if "heavy_rain" in c and steep and machine in ROLL: add("heavy_rain_slope", "high", "rollover")
    elif "heavy_rain" in c and moving: add("heavy_rain", "caution", "environment")
    elif "ground_wet" in c and not steep and machine in ROLL: add("ground_wet", "caution", "rollover")
    if "strong_wind" in c and machine == "sprayer": add("spray_wind", "high", "environment")
    elif "strong_wind" in c and (c & {"implement_raised"}): add("strong_wind", "caution", "environment")
    if "people_near" in c and "reversing" not in c and moving: add("people_near", "caution", "collision")
    if "animals_near" in c and moving: add("animals_near", "caution", "collision")
    if "road_crossing" in c and not dark and moving: add("road_crossing", "caution", "collision")
    if "other_vehicles" in c and not dark and moving: add("other_vehicles", "caution", "collision")
    if "narrow_path" in c and moving: add("narrow_path", "caution", "collision")
    if "hot_midday" in c: add("hot_midday", "caution", "operator")
    if "working_alone" in c: add("working_alone", "caution", "operator")
    if "first_time" in c: add("first_time", "caution", "operator")
    return r


def check(payload: dict, lang: str = "en") -> dict:
    """Ranked warnings for the machine and conditions the operator reports. Raises ValueError for an unknown machine."""
    lang = lang if lang in NOTE else "en"
    machine = str((payload or {}).get("machine") or "").lower()
    if machine not in MACHINES:
        raise ValueError("machine must be one of: " + ", ".join(MACHINES))
    raw = (payload or {}).get("conditions") or []
    raw = [str(x) for x in raw][:60] if isinstance(raw, list) else []
    known = [x for x in dict.fromkeys(raw) if x in CODES]
    ignored = [x for x in dict.fromkeys(raw) if x not in CODES]
    rows = _rules(machine, set(known))
    rows.sort(key=lambda x: (-LEVELS[x[1]], x[2]))
    out = [{"code": code, "level": lv, "kind": kind, "icon": KIND_ICON[kind], "kind_text": KIND_T[lang][kind], "text": W[code][lang][0], "do": W[code][lang][1]} for code, lv, kind in rows]
    top = max([LEVELS[w["level"]] for w in out], default=0)
    level = next(k for k, v in LEVELS.items() if v == top)
    return {"machine": machine, "level": level, "level_text": LV[lang][level], "warnings": out, "reported": len(known), "ignored": ignored,
            "counts": {k: sum(1 for w in out if w["level"] == k) for k in ("stop", "high", "caution")},
            "collision_warnings": sum(1 for w in out if w["kind"] == "collision"), "note": NOTE[lang], "basis": "operator-reported conditions + safety rules in code"}
