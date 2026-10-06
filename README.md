# Nchoro Amarachi style — AlphaZero self-play

A relay-sowing mancala (see `RULES.md`), an AlphaZero-style AI that learns it from the rules alone,
a browser UI to watch or play, and tools to measure game balance.

Things still to confirm about the rules: `OPEN_QUESTIONS.md`.

## Setup (already done)

    python3 -m venv .venv && .venv/bin/pip install torch numpy pytest

## Play / watch

    .venv/bin/python server.py          # open http://localhost:8000

Pick Human or any AI for each side. With two AIs, use Play / Step to watch; the speed slider
controls the sowing animation. Yellow bars show how much the AI considered each pit.

## Train

    .venv/bin/python train.py                                   # default rules -> models/nchoro/
    .venv/bin/python train.py --run nchoro --resume --iterations 40   # keep improving it
    .venv/bin/python train.py --run single --sowing single      # a rule variant
    .venv/bin/python train.py --help                            # all rule and training options

Each iteration prints self-play results and scores against two fixed baselines (greedy, minimax-3).
`models/<run>/log.csv` has the same numbers. New runs show up in the UI's player list.

## Analyse a rule set

    .venv/bin/python analyze.py models/nchoro/latest.pt
    .venv/bin/python analyze.py models/nchoro/latest.pt models/single/latest.pt   # compare variants

Reports first-player advantage, draws, length, relay laps, captures and how games end.

## Published test page

https://claude.ai/artifact/LeqsTvpEST1m4QEGHtBTKC — runs entirely in the browser (JS port in
`artifact/engine.js`, checked against Python by `tests/test_js_parity.py`). Finished games against the
AI are saved to the page's shared `games` record.

After retraining, rebuild with `.venv/bin/python artifact/build.py` and ask Claude to republish.

## Layout

| File | What |
|---|---|
| `nchoro/engine.py` | the rules — no UI or AI code; every option in `Rules` |
| `nchoro/net.py` | neural network (PyTorch for training, NumPy for fast play) |
| `nchoro/mcts.py` | Monte Carlo Tree Search |
| `nchoro/players.py` | random / greedy / minimax / AlphaZero players |
| `nchoro/selfplay.py` | self-play and evaluation workers |
| `train.py`, `analyze.py`, `server.py`, `web/index.html` | entry points and UI |
| `tests/test_engine.py` | hand-worked positions for every rule (`.venv/bin/python -m pytest -q`) |
