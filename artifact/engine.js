// Nchoro Amarachi style: rules engine + AlphaZero player, a line-for-line port of
// nchoro/engine.py, nchoro/net.py and nchoro/mcts.py. tests/test_js_parity.py checks
// that both versions produce identical games and network outputs.
(function (root) {
  "use strict";

  // ------------------------------------------------------------------ rules
  function makeRules(d) {
    const r = Object.assign({ pits: 6, seeds: 4, sowing: "relay", capture_counts: [4],
      capture_side: "both", capture_chain: false, instant_capture: true, skip_origin: false,
      sweep_own: false, feeding: false, end_at: 4,
      max_laps: 200, max_moves: 300 }, d || {});
    r.total = 2 * r.pits * r.seeds;
    r.captureSet = new Set(r.capture_counts);
    return r;
  }

  function initial(rules) {
    return { rules, board: new Array(2 * rules.pits).fill(rules.seeds), scores: [0, 0],
             toMove: 0, moveCount: 0, winner: null, endReason: null };
  }

  function copy(s) {
    return { rules: s.rules, board: s.board.slice(), scores: s.scores.slice(), toMove: s.toMove,
             moveCount: s.moveCount, winner: s.winner, endReason: s.endReason };
  }

  const owner = (s, pit) => Math.floor(pit / s.rules.pits);

  function sideOk(s, pit, player) {
    const side = s.rules.capture_side;
    if (side === "both") return true;
    const mine = owner(s, pit) === player;
    return side === "own" ? mine : !mine;
  }

  function capture(s, pit, player, trace) {
    const count = s.board[pit];
    s.board[pit] = 0;
    s.scores[player] += count;
    if (trace) trace.push({ type: "capture", pit, count, player });
  }

  function sow(s, pit, trace, touched) {
    const r = s.rules, board = s.board, n2 = 2 * r.pits, player = s.toMove;
    let origin = pit, hand = board[pit], pos = pit, laps = 1;
    board[pit] = 0;
    if (touched) touched.add(pit);
    if (trace) trace.push({ type: "pickup", pit, count: hand });
    for (;;) {
      while (hand) {
        pos = (pos + 1) % n2;
        if (r.skip_origin && pos === origin) continue;
        board[pos] += 1;
        hand -= 1;
        if (touched) touched.add(pos);
        if (trace) trace.push({ type: "sow", pit: pos });
        if (hand && r.instant_capture && r.captureSet.has(board[pos])) capture(s, pos, owner(s, pos), trace);
      }
      const count = board[pos];
      if (r.captureSet.has(count) && sideOk(s, pos, player)) {
        capture(s, pos, player, trace);
        if (r.capture_chain) {
          let p = (pos - 1 + n2) % n2;
          for (let k = 0; k < n2 - 1; k++) {
            if (r.captureSet.has(board[p]) && sideOk(s, p, player)) {
              capture(s, p, player, trace);
              p = (p - 1 + n2) % n2;
            } else break;
          }
        }
        return;
      }
      if (r.sowing === "single" || count === 1) return;
      if (laps >= r.max_laps) {
        if (trace) trace.push({ type: "lap_limit" });
        return;
      }
      hand = count;
      board[pos] = 0;
      if (touched) touched.add(pos);
      origin = pos;
      laps += 1;
      if (trace) trace.push({ type: "pickup", pit: pos, count: hand });
    }
  }

  function rowEmpty(s, player) {
    const n = s.rules.pits;
    for (let i = player * n; i < player * n + n; i++) if (s.board[i]) return false;
    return true;
  }

  function legalMoves(s) {
    if (s.winner !== null) return [];
    const n = s.rules.pits, me = s.toMove, base = me * n;
    let moves = [];
    for (let i = 0; i < n; i++) if (s.board[base + i]) moves.push(i);
    if (s.rules.feeding && rowEmpty(s, 1 - me) && moves.length) {
      const feeding = moves.filter(m => {
        const t = copy(s);
        sow(t, base + m, null);
        return !rowEmpty(t, 1 - me);
      });
      if (feeding.length) moves = feeding;
    }
    return moves;
  }

  function checkEnd(s, trace) {
    const r = s.rules;
    const left = s.board.reduce((a, b) => a + b, 0);
    let reason;
    if (left <= r.end_at) reason = `${left} seed${left === 1 ? "" : "s"} left on the board`;
    else if (s.moveCount >= r.max_moves) reason = "move limit reached";
    else return false;
    const n = r.pits;
    for (let p = 0; p < 2; p++)
      for (let i = p * n; i < p * n + n; i++) { s.scores[p] += s.board[i]; s.board[i] = 0; }
    const [a, b] = s.scores;
    s.winner = a > b ? 0 : b > a ? 1 : -1;
    s.endReason = reason;
    if (trace) trace.push({ type: "game_over", winner: s.winner, scores: s.scores.slice(), reason });
    return true;
  }

  function play(state, move, trace) {
    if (!legalMoves(state).includes(move)) throw new Error(`illegal move ${move}`);
    const s = copy(state), mover = s.toMove;
    const touched = new Set();
    sow(s, mover * s.rules.pits + move, trace, touched);
    if (s.rules.sweep_own) {
      const n = s.rules.pits;
      for (let pit = mover * n; pit < mover * n + n; pit++)
        if (touched.has(pit) && s.rules.captureSet.has(s.board[pit])) capture(s, pit, mover, trace);
    }
    s.moveCount += 1;
    s.toMove = 1 - mover;
    if (checkEnd(s, trace)) return s;
    if (rowEmpty(s, s.toMove)) {
      if (trace) trace.push({ type: "pass", player: s.toMove });
      s.toMove = mover;
    }
    return s;
  }

  const resultFor = (s, player) => s.winner === -1 ? 0 : s.winner === player ? 1 : -1;

  // ------------------------------------------------------------------ network
  const BUCKETS = 16;

  function encode(s) {
    const r = s.rules, n = r.pits, me = s.toMove;
    const x = new Float32Array(2 * n * (BUCKETS + 1) + 3);
    for (let k = 0; k < 2 * n; k++) {
      const i = k < n ? me * n + k : (1 - me) * n + (k - n);
      const c = s.board[i];
      x[k * BUCKETS + Math.min(c, BUCKETS - 1)] = 1;
      x[2 * n * BUCKETS + k] = c / r.seeds / 4;
    }
    const tail = 2 * n * (BUCKETS + 1);
    x[tail] = s.scores[me] / r.total;
    x[tail + 1] = s.scores[1 - me] / r.total;
    x[tail + 2] = s.moveCount / r.max_moves;
    return x;
  }

  // weights: {layers: [{w: Float32Array(in*out), b, in, out}], policy: {...}, value: {...}}
  function dense(x, L, relu) {
    const out = new Float32Array(L.out);
    for (let j = 0; j < L.out; j++) out[j] = L.b[j];
    for (let i = 0; i < L.in; i++) {
      const xi = x[i];
      if (xi === 0) continue;
      const row = i * L.out;
      for (let j = 0; j < L.out; j++) out[j] += xi * L.w[row + j];
    }
    if (relu) for (let j = 0; j < L.out; j++) if (out[j] < 0) out[j] = 0;
    return out;
  }

  function makeNet(weights) {
    return function (x) {
      let h = x;
      for (const L of weights.layers) h = dense(h, L, true);
      const logits = dense(h, weights.policy, false);
      const value = Math.tanh(dense(h, weights.value, false)[0]);
      return { logits, value };
    };
  }

  // ------------------------------------------------------------------ MCTS
  function Node(state, prior, mover) {
    this.state = state; this.prior = prior; this.mover = mover;
    this.children = null; this.n = 0; this.w = 0; this.terminal = null;
  }
  Node.prototype.q = function () { return this.n ? this.w / this.n : 0; };

  function MCTS(net, cPuct) {
    this.net = net;
    this.c = cPuct || 1.5;
  }

  MCTS.prototype.evaluate = function (node) {
    const s = node.state;
    if (s.winner !== null) { node.terminal = resultFor(s, s.toMove); return node.terminal; }
    const moves = legalMoves(s);
    const { logits, value } = this.net(encode(s));
    let mx = -Infinity;
    for (const m of moves) mx = Math.max(mx, logits[m]);
    let sum = 0;
    const p = moves.map(m => { const e = Math.exp(logits[m] - mx); sum += e; return e; });
    node.children = new Map();
    moves.forEach((m, k) => node.children.set(m, new Node(null, p[k] / sum, s.toMove)));
    return value;
  };

  MCTS.prototype.root = function (state) {
    const root = new Node(state, 1, -1);
    this.evaluate(root);
    return root;
  };

  MCTS.prototype.simulate = function (root, sims) {
    for (let k = 0; k < sims; k++) {
      let node = root;
      const path = [root], moves = [];
      while (node.children) {
        const sq = Math.sqrt(node.n + 1);
        let best = null, bestMove = -1, bestScore = -1e9;
        for (const [m, ch] of node.children) {
          const sc = ch.q() + this.c * ch.prior * sq / (1 + ch.n);
          if (sc > bestScore) { best = ch; bestMove = m; bestScore = sc; }
        }
        if (!best.state) best.state = play(node.state, bestMove);
        node = best;
        path.push(node);
        moves.push([node.mover, bestMove]);
        if (node.terminal !== null) break;
      }
      const v = node.terminal !== null ? node.terminal : this.evaluate(node);
      const leaf = node.state.toMove;
      for (const nd of path) { nd.n += 1; nd.w += nd.mover === leaf ? v : -v; }
      // what the last simulation did, for explaining the search
      this.last = { moves, value: v, player: leaf, terminal: node.terminal !== null, nodes: path };
    }
  };

  MCTS.prototype.best = function (root) {
    let best = -1, bestN = -1;
    const ties = [];
    for (const [m, ch] of root.children) {
      if (ch.n > bestN) { bestN = ch.n; ties.length = 0; ties.push(m); }
      else if (ch.n === bestN) ties.push(m);
    }
    best = ties[Math.floor(Math.random() * ties.length)];
    return best;
  };

  const api = { makeRules, initial, legalMoves, play, resultFor, encode, makeNet, MCTS, BUCKETS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Nchoro = api;
})(this);
