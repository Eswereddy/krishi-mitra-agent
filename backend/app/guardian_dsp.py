"""Sound features for Krishi Machine Guardian (numpy only, no model, no network).

All numbers are computed from the recording itself. Level (loudness) is NOT used because phone microphone gain varies; only the shape of the
sound is: how steady the engine rate is, how regular the pulses are, where energy sits, whether a new steady tone has appeared, how many
sharp impulses there are. The thresholds in guardian.py were tuned on SYNTHETIC engine-like signals only and are not validated on real machines.
"""
import numpy as np

SR = 8000
N, HOP, NFFT = 4096, 2048, 16384
MIN_S, MAX_S = 4.0, 20.0
F_LO, F_HI = 25.0, 250.0


def _frames(x):
    w = np.hanning(N)
    return np.array([x[i:i + N] * w for i in range(0, len(x) - N + 1, HOP)])


def _f0_per_frame(F):
    """Harmonic product spectrum on zero-padded frames. Returns Hz per frame (nan if flat)."""
    binhz = SR / NFFT
    spec = np.abs(np.fft.rfft(F, n=NFFT, axis=1))
    lo, hi = int(F_LO / binhz), int(F_HI / binhz)
    out = []
    for s in spec:
        hps = s[lo:hi].copy()
        for k in (2, 3, 4, 5):
            hps = hps * s[lo * k:hi * k:k][:hi - lo]
        i = int(np.argmax(hps))
        out.append((lo + i) * binhz if hps[i] > 0 else np.nan)
    return np.array(out)


def _band(P, f, lo, hi):
    m = (f >= lo) & (f < hi)
    return float(P[m].sum())


def quality(x, sr_in):
    """Reasons the recording cannot be used (empty list means usable)."""
    bad = []
    d = len(x) / SR
    if d < MIN_S:
        bad.append("short")
    if not len(x) or float(np.sqrt(np.mean(x ** 2))) < 0.002:
        bad.append("quiet")
    if len(x) and float(np.mean(np.abs(x) >= 0.98)) > 0.02:
        bad.append("clipped")
    return bad


def features(x):
    """x: float array in [-1, 1] at 8 kHz. Returns a dict of plain numbers (JSON-safe)."""
    x = np.asarray(x, dtype=float)[: int(MAX_S * SR)]
    x = x - x.mean()
    F = _frames(x)
    if len(F) < 3:
        return None
    f0s = _f0_per_frame(F)
    good = f0s[~np.isnan(f0s)]
    if len(good) < 3:
        return None
    f0 = float(np.median(good))
    keep = good[np.abs(good - f0) <= 0.5 * f0]
    f0_cv = float(np.std(keep) / np.median(keep)) if len(keep) >= 3 else 0.0
    P = (np.abs(np.fft.rfft(F, axis=1)) ** 2)
    Pm = P.mean(axis=0)
    f = np.fft.rfftfreq(N, 1 / SR)
    total = _band(Pm, f, 40, 3800) + 1e-18
    hf = _band(Pm, f, 1500, 3800) / total
    cen = float((Pm[(f >= 40) & (f < 3800)] * f[(f >= 40) & (f < 3800)]).sum() / (Pm[(f >= 40) & (f < 3800)].sum() + 1e-18))
    harm = sub = 0.0
    eh = es = 0.0
    for k in range(0, 21):
        if (k + 0.5) * f0 * 1.03 > 2000:
            break
        if k >= 1:
            eh += _band(Pm, f, k * f0 * 0.97, k * f0 * 1.03)
        if (k + 0.5) * f0 >= 28:
            es += _band(Pm, f, (k + 0.5) * f0 * 0.97, (k + 0.5) * f0 * 1.03)
    harm = float(eh / (_band(Pm, f, 40, 2000) + 1e-18))
    sub = float(es / (eh + 1e-18))
    # steady narrow tones away from the engine harmonics
    L = 10 * np.log10(P + 1e-18)
    Lm = L.mean(axis=0)
    k200 = int(200 / (SR / N))
    med = np.array([np.median(Lm[max(0, i - k200):i + k200]) for i in range(len(Lm))])
    tones = []
    for i in range(int(600 / (SR / N)), int(3800 / (SR / N))):
        if Lm[i] - med[i] >= 8 and Lm[i] >= Lm[i - 1] and Lm[i] >= Lm[i + 1]:
            fr = float(f[i])
            pers = float(np.mean(L[:, max(0, i - 1):i + 2].max(axis=1) - med[i] >= 6))
            if pers >= 0.7:
                tones.append({"hz": round(fr), "db": round(float(Lm[i] - med[i]), 1), "persist": round(pers, 2)})
    tones.sort(key=lambda t: -t["db"])
    # sharp impulses in 200-2000 Hz
    X = np.fft.rfft(x)
    ff = np.fft.rfftfreq(len(x), 1 / SR)
    Xb = np.where((ff >= 200) & (ff <= 2000), X, 0)
    an = np.fft.irfft(np.concatenate([Xb[:1], 2 * Xb[1:-1], Xb[-1:]]) if len(Xb) % 2 == 0 else Xb, n=len(x))
    env = np.abs(an)
    k = max(1, int(0.005 * SR))
    env = np.convolve(env, np.ones(k) / k, mode="same")
    med_e = float(np.median(env))
    mad = float(np.median(np.abs(env - med_e))) * 1.4826 + 1e-12
    thr = med_e + 6 * mad
    peaks, last = 0, -10 ** 9
    for i in range(1, len(env) - 1):
        if env[i] > thr and env[i] >= env[i - 1] and env[i] >= env[i + 1] and i - last > 0.02 * SR:
            peaks += 1
            last = i
    secs = len(x) / SR
    rms_fr = np.sqrt((F ** 2).mean(axis=1))
    level_cv = float(np.std(rms_fr) / (np.mean(rms_fr) + 1e-12))
    return {"f0_hz": round(f0, 1), "f0_cv": round(f0_cv, 4), "harmonic_ratio": round(harm, 3), "subharmonic_ratio": round(sub, 3), "hf_ratio": round(hf, 4),
            "centroid_hz": round(cen), "tones": tones[:8], "impulses_per_s": round(peaks / secs, 2), "level_cv": round(level_cv, 3), "seconds": round(secs, 1)}
