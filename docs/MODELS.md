# How each Meta model is used

Krishi Mitra uses six Meta models, each for a job it is suited to. Where a number matters, the model finds things and **code computes the number**. Status column = what is verified by automated tests (stubbed) vs what must be confirmed live on the deployed app.

| Model | Job in the app | Code | Fallback / guard | Verified |
|---|---|---|---|---|
| **Muse Spark Open** (`meta-models/muse-spark-open-1026`, open weights, Baseten) | The agent: reads the question in Telugu / Hindi / English (and more), decides which of 28 tools to call, writes the answer. Also reads crop photos (vision) and is the speech fallback. | `agent.py`, `meta_client.py`, `config.py` | Every figure in the answer is checked against tool results (`verify.py`); unverified figures trigger a rewrite then a visible warning. If the call fails, Muse Glimmer takes over. | Tool loop and verification: tests. Live behaviour: `eval/suite_v2.py --live` |
| **Muse Voice Transcribe** | Speech to text for voice questions (`PCM_16KHZ`, push to talk, `languageBias` Telugu / Hindi / English). Also used for WhatsApp voice notes. | `meta_models.asr_transcribe`, `/api/transcribe`, `/api/asr`, `whatsapp.py` | If it is not configured or fails, Spark Open audio transcribes instead. | Fallback path: tests. Real Telugu accuracy: test live |
| **SAM 3.1** | Farm Doctor: finds the leaf and the damaged spots in the photo (text prompts "diseased leaf spot" and "leaf") with per-region confidence. | `meta_models.segment`, `measure`, `doctor.py`, `/api/leaf-scan` | The damage **percentage is pixel arithmetic**, not a model guess. A photo-quality gate (dark, blurry, tiny) and a confidence check mark the result clear / uncertain / retake. Severe or unreliable results escalate to a human expert. | Gate and arithmetic: tests on synthetic images. SAM output on real leaves: test live; thresholds need real photos |
| **Muse Wonder** (`muse-wonder-1.0`, reasoning) | Independent second opinion: audits an answer against the tool results the agent saw, as a different model from the one that wrote it. | `audit.py`, `/api/second-opinion` | The code-based figure check is shown next to Wonder's view and works even if Wonder is unavailable. | Parsing and fallback: tests. Live audit quality: test live |
| **Muse Image** | Turns an answer into a clean, shareable advice card for WhatsApp groups. | `meta_models.generate_image`, `/api/advice-card` | Optional extra; the text answer is always available. | Test live |
| **Muse Glimmer** (`meta-models/Muse-Glimmer-30B`, Apache 2.0, about 30B, open weights) | Open-weight fallback so the farmer still gets an answer when the main model call times out, returns 5xx or is rate limited. Can run on one GPU behind any OpenAI-compatible server. | `meta_client.chat_message`, `GLIMMER_BASE_URL`, `GLIMMER_API_KEY`, `GLIMMER_MODEL` | Used only on retryable errors; our own 4xx bad requests are not retried. | Fallback logic: tests. Needs your own Glimmer server to try live |

## Why this split
- **Spark Open does language and judgment** (what the farmer means, which tool answers it). It never does the arithmetic: prices, percentages, costs, water and net income are computed in code from tool data.
- **SAM does perception** (where is the leaf, where is the damage). The percentage and the reliability decision are ours, so they are explainable and testable.
- **A second model audits the first** (Wonder), and code audits both: three independent checks before a figure reaches a farmer.
- **Open weights matter for farmers**: Spark Open and Glimmer can be self-hosted by a cooperative or an extension office, so the service is not tied to one provider.

## What to say honestly
- Nothing here has been verified against the live Meta APIs from the build sandbox; the offline tests stub the network. Run the live checks on the deployed app and quote only what you see.
- SAM percentages are an automated measurement from a phone photo, not a diagnosis; the app says so on screen and in the expert case.
