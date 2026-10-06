"""Hand-worked positions for each rule. Run: .venv/bin/python -m pytest -q"""

import random

from nchoro.engine import Rules, State, legal_moves, play

N = 6


def make(board, rules=Rules(), to_move=0):
    assert len(board) == 2 * rules.pits
    return State(rules=rules, board=list(board), to_move=to_move)


def test_turn_ends_when_last_seed_lands_in_empty_pit():
    s = make([1, 0, 0, 0, 0, 0, 5, 5, 5, 5, 5, 5])
    t = play(s, 0)
    assert t.board[:N] == [0, 1, 0, 0, 0, 0]
    assert t.scores == [0, 0]
    assert t.to_move == 1


def test_last_seed_making_opponent_pit_four_captures():
    s = make([0, 0, 0, 0, 0, 1, 3, 5, 5, 5, 5, 5])
    t = play(s, 5)
    assert t.board[6] == 0
    assert t.scores == [4, 0]


def test_last_seed_making_own_pit_four_captures():
    s = make([1, 3, 0, 0, 0, 0, 5, 5, 5, 5, 5, 5])
    t = play(s, 0)
    assert t.board[:N] == [0, 0, 0, 0, 0, 0]
    assert t.scores == [4, 0]


def test_own_side_four_relays_when_capture_side_is_opponent():
    s = make([1, 3, 0, 0, 0, 0, 5, 5, 5, 5, 5, 5], Rules(capture_side="opponent"))
    t = play(s, 0)
    assert t.board[:N] == [0, 0, 1, 1, 1, 1]
    assert t.scores == [0, 0]


def test_relay_picks_up_and_continues():
    # 0 -> sows 1,2; pit 2 now holds 2 -> pick up, sow 3,4; pit 4 was empty -> stop
    s = make([2, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 5])
    trace = []
    t = play(s, 0, trace)
    assert t.board == [0, 1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 5]
    assert [e["type"] for e in trace] == ["pickup", "sow", "sow", "pickup", "sow", "sow"]


def test_own_pit_reaching_four_mid_sowing_is_taken_at_once():
    # pit 1 goes 3 -> 4 mid-lap: taken immediately; the last seed lands in empty pit 2
    s = make([2, 3, 0, 0, 0, 0, 5, 5, 5, 5, 5, 5])
    trace = []
    t = play(s, 0, trace)
    assert t.board[:3] == [0, 0, 1]
    assert t.scores == [4, 0]
    assert [e["type"] for e in trace] == ["pickup", "sow", "capture", "sow"]


def test_untouched_own_four_is_not_swept():
    s = make([1, 0, 4, 0, 0, 0, 5, 5, 5, 5, 5, 5])
    t = play(s, 0)               # a -> b (empty), turn ends; pit c was never touched
    assert t.board[:3] == [0, 1, 4]
    assert t.scores == [0, 0]


def test_opponent_pit_reaching_four_mid_sowing_goes_to_the_opponent():
    s = make([0, 0, 0, 0, 0, 2, 3, 0, 5, 5, 5, 5])
    t = play(s, 5)               # f -> 6 (3 -> 4: player 2 takes it), 7 (empty): turn ends
    assert t.board[6:8] == [0, 1]
    assert t.scores == [0, 4]


def test_last_seed_four_on_opponent_side_goes_to_the_mover():
    s = make([0, 0, 0, 0, 0, 2, 0, 3, 5, 5, 5, 5])
    t = play(s, 5)               # f -> 6 (0 -> 1), 7 (3 -> 4, last seed): player 1 takes it
    assert t.board[6:8] == [1, 0]
    assert t.scores == [4, 0]


def test_seeds_landing_in_an_instantly_captured_pit_start_again_from_zero():
    s = make([5, 3, 0, 0, 0, 0, 5, 5, 0, 0, 0, 0])
    trace = []
    t = play(s, 0, trace)        # a -> b (taken), c, d, e, f: f was empty -> turn ends
    assert t.board[:6] == [0, 0, 1, 1, 1, 1]
    assert t.scores == [4, 0]


def test_mid_sowing_pass_through_without_instant_capture():
    s = make([0, 0, 0, 0, 0, 2, 3, 0, 5, 5, 5, 5], Rules(instant_capture=False))
    t = play(s, 5)
    assert t.board[6:8] == [4, 1]
    assert t.scores == [0, 0]


def test_sweep_option_comes_after_the_last_seed_capture():
    # a: 3 seeds -> b (3->4 passing), c, d (3->4 last seed: captured), then b is swept
    s = make([3, 3, 0, 3, 0, 0, 5, 5, 5, 5, 5, 5], Rules(instant_capture=False, sweep_own=True))
    trace = []
    t = play(s, 0, trace)
    caps = [(e["pit"], e["count"]) for e in trace if e["type"] == "capture"]
    assert caps == [(3, 4), (1, 4)]
    assert t.scores == [8, 0]


def test_untouched_by_sweep_or_instant_capture_when_both_are_off():
    s = make([2, 3, 0, 0, 0, 0, 5, 5, 5, 5, 5, 5], Rules(instant_capture=False))
    t = play(s, 0)
    assert t.board[:3] == [0, 4, 1]
    assert t.scores == [0, 0]


def test_full_lap_sows_into_the_starting_pit():
    s = make([12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], Rules(sowing="single"))
    t = play(s, 0)
    assert t.board == [1] * 12


def test_origin_skip_option():
    s = make([12, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], Rules(sowing="single", skip_origin=True))
    t = play(s, 0)
    assert t.board == [0, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]


def test_single_sowing_stops_after_one_lap():
    s = make([2, 0, 1, 0, 0, 0, 5, 5, 5, 5, 5, 5], Rules(sowing="single"))
    t = play(s, 0)
    assert t.board[:N] == [0, 1, 2, 0, 0, 0]


def test_feeding_rule_forces_a_move_into_opponents_row():
    s = make([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0], Rules(feeding=True))
    assert legal_moves(s) == [5]
    assert legal_moves(make(s.board)) == [0, 5]


def test_game_ends_when_four_or_fewer_seeds_are_left():
    # f captures 4 from pit 6, leaving 4 on the board; each player takes what is on their side
    s = make([0, 0, 0, 0, 0, 1, 3, 0, 0, 0, 0, 4])
    s.scores = [22, 18]
    trace = []
    t = play(s, 5, trace)
    assert t.over
    assert t.scores == [26, 22]
    assert t.winner == 0
    assert trace[-1]["type"] == "game_over"


def test_game_continues_with_more_than_four_seeds():
    s = make([1, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 3], to_move=1)
    t = play(s, 5)               # pit 11 -> sows 0,1,2: pit 2 was empty, turn ends
    assert not t.over
    assert t.board[:3] == [2, 1, 1]
    assert t.to_move == 0


def test_player_with_empty_side_passes_and_mover_plays_again():
    s = make([1, 0, 0, 0, 2, 3, 0, 0, 0, 0, 0, 0])
    trace = []
    t = play(s, 0, trace)        # a -> b; player 2's side is empty
    assert not t.over
    assert t.to_move == 0
    assert trace[-1] == {"type": "pass", "player": 1}
    assert t.move_count == 1


def test_end_at_threshold_is_configurable():
    s = make([0, 0, 0, 0, 0, 1, 3, 0, 0, 0, 0, 4], Rules(end_at=2))
    assert not play(s, 5).over


def test_oware_style_chain_capture():
    rules = Rules(sowing="single", capture_counts=(2, 3), capture_side="opponent", capture_chain=True,
                  instant_capture=False, skip_origin=True)
    s = make([0, 0, 0, 0, 0, 3, 1, 2, 1, 5, 5, 5], rules)
    t = play(s, 5)               # sows 6,7,8 -> 2,3,2: all three captured backwards
    assert t.board[6:9] == [0, 0, 0]
    assert t.scores == [7, 0]


def test_random_games_conserve_seeds_and_terminate():
    rng = random.Random(0)
    for rules in (Rules(), Rules(sowing="single"), Rules(feeding=True),
                  Rules(instant_capture=False, skip_origin=True, sweep_own=True),
                  Rules(capture_side="opponent", capture_chain=True)):
        for _ in range(200):
            s = State.initial(rules)
            while not s.over:
                s = play(s, rng.choice(legal_moves(s)))
                assert sum(s.board) + sum(s.scores) == rules.total_seeds
                assert s.over or legal_moves(s)
            assert s.move_count <= rules.max_moves


def test_endless_relay_is_cut_off():
    # reachable from the opening (P1 b, P2 e, P1 d, P2 c, P1 a, P2 f, P1 e); player 2's pit c loops forever
    s = make([1, 0, 1, 0, 1, 0, 2, 1, 3, 1, 0, 2], to_move=1)
    trace = []
    play(s, 2, trace)
    assert any(e["type"] == "lap_limit" for e in trace)
    assert sum(e["type"] == "pickup" for e in trace) == Rules().max_laps
