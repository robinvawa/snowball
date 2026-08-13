"""Predict P(a Quantum Makers video on this creator is an outlier).

Trained on QM's own catalogue — the only real labels available. The headline
finding is that the strongest predictor is not anything the distributors do, it
is the creator's own channel size.

Why we trust that rather than dismissing it as reverse causality (QM has 18.7M
subs, so featuring someone inflates them):

  - The obvious "clean subset" test — dropping creators where QM's views dominate
    their channel — is invalid. That filter preferentially removes cases where QM
    hit big on a *small* creator, which are exactly the counterexamples to the
    rule. Collider selection; it inflates the result to 0.77 for free.
  - The valid test is temporal. If inflation drove the signal, it would be
    strongest where QM's video has had the most time to inflate the creator.
    Measured the other way round:

        QM video < 120 days old   AUC 0.828  (n=43)
        120-400 days              AUC 0.576  (n=105)
        > 400 days                AUC 0.576  (n=208)

    Current creator size is the best proxy for their size *at publication* when
    the video is recent, and drifts as it ages. That is the signature of a real
    effect, not of contamination.
  - Control: creator video count, which QM cannot inflate, predicts nothing at
    any horizon (0.48/0.45/0.53).

The recent regime is also the one that matters: when ranking an unexplored
creator today, their size is measured at decision time.
"""
import collections
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
QM_HIT = 2.0

FEATURES = ["log_subs", "log_vpv", "dist_strength", "log_dist_reach"]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l]
    neg = [s for s, l in zip(scores, labels) if not l]
    if not pos or not neg:
        return None
    w = sum((1 if p > n else 0.5 if p == n else 0) for p in pos for n in neg)
    return w / (len(pos) * len(neg))


def featurize(key, cc, prio):
    c = cc.get(key) or {}
    p = prio.get(key) or {}
    if not c.get("found"):
        return None
    vpv = c["views"] / max(1, c["videos"])
    return {
        "log_subs": math.log10(c["subs"] + 10),
        "log_vpv": math.log10(vpv + 10),
        "dist_strength": p.get("dist_strength") or 0.0,
        "log_dist_reach": math.log10((p.get("dist_best_reach") or 0) + 10),
    }


def fit(X, y, iters=6000, lr=0.25, l2=0.01):
    n = len(FEATURES)
    mu = [sum(x[f] for x in X) / len(X) for f in FEATURES]
    sd = [max(1e-6, (sum((x[f] - mu[i]) ** 2 for x in X) / len(X)) ** .5)
          for i, f in enumerate(FEATURES)]
    Z = [[(x[f] - mu[i]) / sd[i] for i, f in enumerate(FEATURES)] for x in X]
    b = [0.0] * n
    b0 = 0.0
    for _ in range(iters):
        g = [0.0] * n
        g0 = 0.0
        for z, yy in zip(Z, y):
            p = 1 / (1 + math.exp(-max(-30, min(30, b0 + sum(bi * zi for bi, zi in zip(b, z))))))
            e = yy - p
            g0 += e
            for i in range(n):
                g[i] += e * z[i]
        b0 += lr * g0 / len(Z)
        for i in range(n):
            b[i] += lr * (g[i] / len(Z) - l2 * b[i])
    return {"b0": b0, "b": b, "mu": mu, "sd": sd}


def predict(m, x):
    z = [(x[f] - m["mu"][i]) / m["sd"][i] for i, f in enumerate(FEATURES)]
    t = m["b0"] + sum(bi * zi for bi, zi in zip(m["b"], z))
    return 1 / (1 + math.exp(-max(-30, min(30, t))))


def cross_val(X, y, folds=5):
    idx = list(range(len(X)))
    preds = [0.0] * len(X)
    for f in range(folds):
        te = [i for i in idx if i % folds == f]
        tr = [i for i in idx if i % folds != f]
        if not te or len({y[i] for i in tr}) < 2:
            continue
        m = fit([X[i] for i in tr], [y[i] for i in tr])
        for i in te:
            preds[i] = predict(m, X[i])
    return preds


def build():
    cc = json.load(open(os.path.join(DATA, "creator_channels.json")))
    prio = {r["key"]: r for r in
            json.load(open(os.path.join(DATA, "creator_priority.json")))["creators"]}
    qm = json.load(open(os.path.join(DATA, "qm_videos.json")))
    qmc = collections.defaultdict(list)
    for v in qm:
        for h in v["source_handles_title"]:
            k = norm(h)
            if k:
                qmc[k].append(v)

    keys, X, y, age = [], [], [], []
    for k, vs in qmc.items():
        x = featurize(k, cc, prio)
        if not x:
            continue
        keys.append(k)
        X.append(x)
        y.append(1 if max(v["perp_outlier"] for v in vs) >= QM_HIT else 0)
        age.append(min(v["age_days"] for v in vs))

    cv = cross_val(X, y)
    overall = auc(cv, y)
    recent = [i for i, a in enumerate(age) if a < 120]
    rec_auc = auc([cv[i] for i in recent], [y[i] for i in recent])

    model = fit(X, y)

    # Score every creator we have a channel for, labelled or not.
    scored = {}
    for k in set(cc):
        x = featurize(k, cc, prio)
        if x:
            scored[k] = round(predict(model, x), 4)

    json.dump({"features": FEATURES,
               "coef": dict(zip(FEATURES, [round(v, 3) for v in model["b"]])),
               "intercept": round(model["b0"], 3),
               "cv_auc": overall, "cv_auc_recent": rec_auc,
               "n_train": len(y), "n_pos": sum(y),
               "scores": scored},
              open(os.path.join(DATA, "creator_model.json"), "w"), indent=1)
    return model, overall, rec_auc, scored, (keys, X, y, cv, age)


if __name__ == "__main__":
    m, a, ra, scored, (keys, X, y, cv, age) = build()
    print("Entrenado con %d creadores etiquetados (%d aciertos, %.0f%%)"
          % (len(y), sum(y), 100 * sum(y) / len(y)))
    print()
    print("AUC validado cruzado (5 folds), honesto:")
    print("  todos los creadores          %.3f" % a)
    print("  solo vídeos recientes <120d  %.3f   <- el régimen de decisión real"
          % ra)
    print()
    print("Coeficientes (estandarizados, + = sube la probabilidad):")
    for f, b in zip(FEATURES, m["b"]):
        print("  %-16s %+.3f" % (f, b))
    print()
    base = sum(y) / len(y)
    print("Comparación de señales, mismo test:")
    print("  %-34s %.3f" % ("modelo completo (CV)", a))
    print("  %-34s %.3f" % ("solo subs del creador",
                            auc([x["log_subs"] for x in X], y)))
    print("  %-34s %.3f" % ("solo señal de distribuidores",
                            auc([x["dist_strength"] for x in X], y)))
    print("  %-34s %.3f" % ("azar", 0.5))
    print()
    print("Tasa base de acierto: %.0f%%" % (100 * base))
