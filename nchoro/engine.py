"""Nchoro Amarachi style rules engine.

Pure game logic: no UI, no AI, no third-party dependencies.

Board layout (n = pits per side):

    index:   2n-1 ... n+1  n        <- player 1's row (top, runs right-to-left)
             0    1  ...   n-1      <- player 0's row (bottom, runs left-to-right)

Sowing goes to increasing indices (mod 2n), which is counter-clockwise when
drawn as above. Player 0 owns pits 0..n-1, player 1 owns pits n..2n-1.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class Rules:
    pits: int = 6                          # pits per side
    seeds: int = 4                         # seeds per pit at start
    sowing: str = "relay"                  # "relay" | "single"
    capture_counts: tuple = (4,)           # last seed making a pit exactly one of these captures it
    capture_side: str = "both"             # "both" | "opponent" | "own" (for the last seed)
    capture_chain: bool = False            # also capture preceding pits with a capture count
    instant_capture: bool = True           # a pit reaching a capture count mid-sowing goes to its owner at once
    skip_origin: bool = False              # on a full lap, skip the pit the lap started from
    sweep_own: bool = False                # at turn end, also capture own pits that changed and hold a capture count
    feeding: bool = False                  # must give seeds to an opponent with an empty row, if possible
    end_at: int = 4                        # game ends when this many seeds or fewer are left after a turn
    max_laps: int = 200                    # safety: cut off a relay turn after this many laps
    max_moves: int = 300                   # safety: end the game after this many moves

    def __post_init__(self):
        if self.sowing not in ("relay", "single"):
            raise ValueError(f"sowing must be 'relay' or 'single', not {self.sowing!r}")
        if self.capture_side not in ("both", "opponent", "own"):
            raise ValueError(f"capture_side must be 'both', 'opponent' or 'own', not {self.capture_side!r}")
        if self.end_at < 0:
            raise ValueError("end_at must be 0 or more")
        if self.pits < 2 or self.seeds < 1:
            raise ValueError("need at least 2 pits per side and 1 seed per pit")
        object.__setattr__(self, "capture_counts", tuple(sorted(set(self.capture_counts))))

    @property
    def total_seeds(self) -> int:
        return 2 * self.pits * self.seeds

    def to_dict(self) -> dict:
        d = asdict(self)
        d["capture_counts"] = list(self.capture_counts)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Rules":
        d = dict(d)
        if "capture_counts" in d:
            d["capture_counts"] = tuple(d["capture_counts"])
        return cls(**d)

    def describe(self) -> str:
        counts = "/".join(str(c) for c in self.capture_counts)
        return (f"{self.pits} pits x {self.seeds} seeds, {self.sowing} sowing, "
                f"capture exactly {counts} on {self.capture_side} side(s)"
                f"{', chained' if self.capture_chain else ''}"
                f"{', owner takes mid-sowing 4s' if self.instant_capture else ''}"
                f"{', origin skipped' if self.skip_origin else ''}"
                f"{', own changed 4s swept' if self.sweep_own else ''}"
                f"{', feeding' if self.feeding else ', no feeding'}, "
                f"ends at {self.end_at} or fewer seeds")


@dataclass
class State:
    rules: Rules
    board: list
    scores: list = field(default_factory=lambda: [0, 0])
    to_move: int = 0
    move_count: int = 0
    winner: Optional[int] = None           # 0, 1, or -1 for a draw; None while the game is running
    end_reason: Optional[str] = None

    @classmethod
    def initial(cls, rules: Rules = Rules(), first: int = 0) -> "State":
        return cls(rules=rules, board=[rules.seeds] * (2 * rules.pits), to_move=first)

    def copy(self) -> "State":
        return State(self.rules, self.board[:], self.scores[:], self.to_move,
                     self.move_count, self.winner, self.end_reason)

    @property
    def over(self) -> bool:
        return self.winner is not None

    def row(self, player: int) -> range:
        n = self.rules.pits
        return range(player * n, player * n + n)

    def owner(self, pit: int) -> int:
        return pit // self.rules.pits

    def to_dict(self) -> dict:
        return {"rules": self.rules.to_dict(), "board": self.board, "scores": self.scores,
                "to_move": self.to_move, "move_count": self.move_count,
                "winner": self.winner, "end_reason": self.end_reason,
                "legal_moves": legal_moves(self)}


# --------------------------------------------------------------------------- moves

def _sow(state: State, pit: int, trace: Optional[list], touched: Optional[set] = None) -> None:
    """Sow from absolute pit index `pit` in place, including relays and captures.

    If `touched` is a set, every pit that gains or loses seeds is added to it.
    """
    r = state.rules
    board = state.board
    n2 = 2 * r.pits
    player = state.to_move

    origin = pit
    hand = board[pit]
    board[pit] = 0
    if touched is not None:
        touched.add(pit)
    if trace is not None:
        trace.append({"type": "pickup", "pit": pit, "count": hand})
    pos = pit
    laps = 1

    while True:
        while hand:
            pos = (pos + 1) % n2
            if r.skip_origin and pos == origin:
                continue
            board[pos] += 1
            hand -= 1
            if touched is not None:
                touched.add(pos)
            if trace is not None:
                trace.append({"type": "sow", "pit": pos})
            if hand and r.instant_capture and board[pos] in r.capture_counts:
                _capture(state, pos, state.owner(pos), trace)   # not the last seed: the pit's owner takes it

        count = board[pos]
        if count in r.capture_counts and _side_ok(state, pos, player):
            _capture(state, pos, player, trace)
            if r.capture_chain:
                p = (pos - 1) % n2
                for _ in range(n2 - 1):
                    if board[p] in r.capture_counts and _side_ok(state, p, player):
                        _capture(state, p, player, trace)
                        p = (p - 1) % n2
                    else:
                        break
            return
        if r.sowing == "single" or count == 1:
            return
        if laps >= r.max_laps:
            if trace is not None:
                trace.append({"type": "lap_limit"})
            return
        # relay: pick up the pit the last seed landed in and keep going
        hand = count
        board[pos] = 0
        origin = pos
        laps += 1
        if trace is not None:
            trace.append({"type": "pickup", "pit": pos, "count": hand})


def _side_ok(state: State, pit: int, player: int) -> bool:
    side = state.rules.capture_side
    if side == "both":
        return True
    mine = state.owner(pit) == player
    return mine if side == "own" else not mine


def _capture(state: State, pit: int, player: int, trace: Optional[list]) -> None:
    count = state.board[pit]
    state.board[pit] = 0
    state.scores[player] += count
    if trace is not None:
        trace.append({"type": "capture", "pit": pit, "count": count, "player": player})


def _row_empty(state: State, player: int) -> bool:
    return not any(state.board[i] for i in state.row(player))


def legal_moves(state: State) -> list:
    """Legal moves for the player to move, as local pit indices 0..pits-1."""
    if state.over:
        return []
    me = state.to_move
    base = me * state.rules.pits
    moves = [i for i in range(state.rules.pits) if state.board[base + i]]
    if state.rules.feeding and _row_empty(state, 1 - me) and moves:
        feeding = []
        for m in moves:
            s = state.copy()
            _sow(s, base + m, None)
            if not _row_empty(s, 1 - me):
                feeding.append(m)
        if feeding:
            moves = feeding
    return moves


def play(state: State, move: int, trace: Optional[list] = None) -> State:
    """Return the state after the player to move plays local pit `move`.

    If `trace` is a list, animation events are appended to it:
    pickup / sow / capture / lap_limit / pass / game_over.
    Captures from the end-of-turn sweep come after the turn's own capture.
    """
    if move not in legal_moves(state):
        raise ValueError(f"illegal move {move} (legal: {legal_moves(state)})")
    s = state.copy()
    mover = s.to_move
    touched = set()
    _sow(s, mover * s.rules.pits + move, trace, touched)
    if s.rules.sweep_own:                  # own pits that changed this turn and now hold a capture count
        for pit in s.row(mover):
            if pit in touched and s.board[pit] in s.rules.capture_counts:
                _capture(s, pit, mover, trace)
    s.move_count += 1
    s.to_move = 1 - mover
    if _check_end(s, trace):
        return s
    if _row_empty(s, s.to_move):           # opponent has nothing to play: the mover plays again
        if trace is not None:
            trace.append({"type": "pass", "player": s.to_move})
        s.to_move = mover
    return s


def _check_end(s: State, trace: Optional[list]) -> bool:
    r = s.rules
    left = sum(s.board)
    if left <= r.end_at:
        reason = f"{left} seed{'' if left == 1 else 's'} left on the board"
    elif s.move_count >= r.max_moves:
        reason = "move limit reached"
    else:
        return False
    for p in (0, 1):                       # seeds left on the board belong to whoever's side they're on
        for i in s.row(p):
            s.scores[p] += s.board[i]
            s.board[i] = 0
    a, b = s.scores
    s.winner = 0 if a > b else 1 if b > a else -1
    s.end_reason = reason
    if trace is not None:
        trace.append({"type": "game_over", "winner": s.winner, "scores": s.scores[:], "reason": reason})
    return True


def result_for(state: State, player: int) -> float:
    """+1 win, -1 loss, 0 draw from `player`'s point of view (game must be over)."""
    if state.winner == -1:
        return 0.0
    return 1.0 if state.winner == player else -1.0


def render(state: State) -> str:
    """Plain-text board, for terminals and debugging."""
    n = state.rules.pits
    top = " ".join(f"{state.board[i]:>2}" for i in reversed(range(n, 2 * n)))
    bot = " ".join(f"{state.board[i]:>2}" for i in range(n))
    letters = " ".join(f"{chr(ord('a') + i):>2}" for i in range(n))
    return (f"   P2 captured: {state.scores[1]}\n"
            f"   {top}\n   {bot}\n   {letters}\n"
            f"   P1 captured: {state.scores[0]}")
