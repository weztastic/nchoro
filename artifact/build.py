"""Build the self-contained web page: page.html + engine.js + trained weights -> nchoro.html

    .venv/bin/python artifact/build.py [models/nchoro/latest.pt]
"""

import base64
import csv
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from nchoro.engine import Rules  # noqa: E402
from nchoro.net import load_checkpoint, torch_to_numpy  # noqa: E402


def rules_id(rules: Rules) -> str:
    """Short fingerprint of a rule set, stored with every game record."""
    return hashlib.sha1(json.dumps(rules.to_dict(), sort_keys=True).encode()).hexdigest()[:8]


def _layer(w, b):
    w = np.ascontiguousarray(w.T, dtype="<f4")          # (in, out), row-major, like NumpyNet
    return {"in": int(w.shape[0]), "out": int(w.shape[1]),
            "w": base64.b64encode(w.tobytes()).decode(),
            "b": base64.b64encode(np.asarray(b, dtype="<f4").tobytes()).decode()}


def export_weights(checkpoint: str) -> dict:
    net, rules, meta = load_checkpoint(checkpoint)
    w = torch_to_numpy(net)
    return {
        "rules": rules.to_dict(),
        "rules_id": rules_id(rules),
        "iteration": meta.get("iteration"),
        "layers": [_layer(w[f"body.{i}.weight"], w[f"body.{i}.bias"]) for i in range(0, 2 * w["_depth"], 2)],
        "policy": _layer(w["policy.weight"], w["policy.bias"]),
        "value": _layer(w["value.weight"], w["value.bias"]),
    }


def main():
    checkpoint = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), "models/nchoro/latest.pt")
    weights = export_weights(checkpoint)
    with open(os.path.join(HERE, "engine.js")) as f:
        engine = f.read()
    with open(os.path.join(os.path.dirname(checkpoint), "log.csv")) as f:
        log = [dict(zip(("iteration", "p1", "p2", "vs_minimax3"), (int(r["iteration"]), float(r["p1_win"]),
                float(r["p2_win"]), float(r["vs_minimax3"] or 0)))) for r in csv.DictReader(f)]
    for template, target in (("page.html", "nchoro.html"), ("inside.html", "inside_ai.html")):
        with open(os.path.join(HERE, template)) as f:
            page = f.read()
        page = page.replace("/*__ENGINE__*/", engine)
        page = page.replace("/*__WEIGHTS__*/null", json.dumps(weights, separators=(",", ":")))
        page = page.replace("/*__LOG__*/null", json.dumps(log, separators=(",", ":")))
        out = os.path.join(HERE, target)
        with open(out, "w") as f:
            f.write(page)
        print(f"wrote {out} ({os.path.getsize(out) / 1e6:.2f} MB, model iteration {weights['iteration']})")


if __name__ == "__main__":
    main()
