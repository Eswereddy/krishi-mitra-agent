"""Synthetic engine-like sounds for testing the Guardian features. These are NOT recordings of real machines."""
import numpy as np

SR = 8000


def engine(seed=0, secs=10, f0=60.0, jitter=0.01, wobble=0.0, misfire_every=0, knock=0.0, whine=0.0, rattle=0.0, noise=0.02, gain=1.0):
    r = np.random.default_rng(seed)
    n = int(secs * SR)
    x = np.zeros(n)
    t, k = 0.0, 0
    res = [(150, 40), (420, 70), (900, 110)]            # (resonance Hz, decay 1/s) of one firing event
    L = int(0.05 * SR)
    tt = np.arange(L) / SR
    ph = r.uniform(0, 6.28, len(res))
    ev = sum(np.exp(-d * tt) * np.sin(2 * np.pi * f * tt + p) * (1.0 if i == 0 else 0.6) for i, ((f, d), p) in enumerate(zip(res, ph)))
    while t < secs:
        rate = f0 * (1 + wobble * np.sin(2 * np.pi * 0.7 * t))
        i = int(t * SR)
        a = (0.2 if (misfire_every and k % misfire_every == misfire_every - 1) else 1.0) * (1 + r.normal(0, 0.03))
        m = min(L, n - i)
        if m > 0:
            x[i:i + m] += a * ev[:m]
        t += (1.0 / rate) * (1 + r.normal(0, jitter))
        k += 1
    x = x / np.abs(x).max() * 0.5
    x = x + r.normal(0, noise, n)
    tn = np.arange(n) / SR
    if knock:
        for tk in r.uniform(0.2, secs - 0.2, int(knock * secs)):
            i = int(tk * SR)
            m = min(400, n - i)
            x[i:i + m] += 0.9 * np.exp(-np.arange(m) / 60) * np.sin(2 * np.pi * 900 * np.arange(m) / SR)
    if whine:
        x = x + whine * np.sin(2 * np.pi * 1800 * tn)
    if rattle:
        z = np.fft.rfft(r.normal(0, 1, n))
        f = np.fft.rfftfreq(n, 1 / SR)
        z[(f < 1500) | (f > 3500)] = 0
        b = np.fft.irfft(z, n=n)
        x = x + rattle * b / np.std(b)
    return np.clip(x * gain, -1, 1)
