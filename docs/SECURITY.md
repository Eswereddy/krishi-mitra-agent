# Security and privacy report

Scope: what is implemented in this repository, tested offline, and what is **not**. No penetration test has been done.

## Data and privacy
- The only server database is the optional accounts table (email, name, password hash). Profile, field record, money notebook, outcomes, offers, expert cases and warnings live in the phone's `localStorage`. The server is stateless regarding farmers.
- Sent to the server and Meta models only to answer: the question, crop, district and (if chosen) a photo or voice clip. Not stored by the app.
- Location is never read from GPS: the farmer types the place; the expert case includes it only if ticked. Sharing a case or photo is opt-in each time (`consent.share_details` is enforced server-side, 400 otherwise).
- Consent notice on first run (te/hi/en). Logs hold method, path, status and milliseconds only: no bodies, query strings, headers or IPs.
- `localStorage` is not encrypted; anyone with the unlocked phone can read it.

## Controls (tests: `tests/test_security.py`, `test_hardening.py`, `test_whatsapp.py`)
| Area | Control |
|---|---|
| Secrets | Server-side env vars only; `.env` gitignored; no keys in frontend bundle |
| Input | Size caps (JSON 1 MB, uploads 12 MB, image 8 MB, audio 10 MB), validation and clamping in every module |
| Uploads | Real-image check by bytes (JPEG/PNG/WebP), full decode, 40 MP pixel cap, EXIF transposed copy re-encoded |
| Abuse | Per-IP rate limits on every compute endpoint; trusted-proxy aware client IP |
| Headers | nosniff, X-Frame-Options DENY, no-referrer, permissions policy |
| Webhook | WhatsApp HMAC-SHA256 signature verified in constant time |
| Sign-in | Email + password accounts in PostgreSQL (`app/accounts.py`): scrypt-salted hashes, constant-time check, same error for wrong email or password, 5-failure/10-minute lockout, account deletion. Optional Google sign-in (`app/auth.py`) verifies audience, issuer, expiry, verified email and links by email. Signed 30-day session tokens. No farmer data is stored server-side or synced. No password reset yet. Guest mode works without any of it. |
| Debug | `/api/debug/*` and `/api/models` off unless `DEBUG_ENDPOINTS=1` |
| Errors | Upstream failures become friendly 502/503; tool failures become error results, never stack traces |
| Monitoring | `/api/status`: per-model calls, errors (type only), median and p95 latency since restart |
| Safety | No pesticide names/doses (scanned in `EVAL_V2.md`), human escalation for severe or unreliable cases, verified buyers only from a registry |

## Not implemented (be honest in the submission)
User authentication and per-user authorisation (nothing server-side is per-user), a CSP header, a persistent or distributed rate limiter, encrypted on-device storage, backups (there is no server-side data to back up; `buyers.json` and settings live in git and Render env), a formal penetration test, and consent-based server-side memory.
