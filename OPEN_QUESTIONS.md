# Things to check

Rules that are provisional until confirmed. Current behaviour in brackets.

1. ~~When does the game end?~~ **Answered:** when 4 or fewer seeds are left at the end of a turn;
   each player takes their own side. A player with an empty side passes and the other plays again.

2. **Feeding:** must you give seeds to an opponent whose side is empty, if you can? [No.]

3. **Endless relays — what happens?** [Turn is cut off after 200 laps and simply ends.]
   Still proven to occur under the instant-capture rules, though rarer (22 of ~4 million moves
   checked in random games). From the opening, the legal sequence
   `P1 b, P2 e, P1 d, P2 c, P1 a, P2 f, P1 e` reaches this position with P2 to move:

   ```
      P2 captured: 24
       2  0  1  3  1  2
       1  0  1  0  1  0
       a  b  c  d  e  f
      P1 captured: 12
   ```

   P2 playing **c** relays forever: the board and the pit being picked up repeat exactly.
   Options: (a) the move is not allowed, (b) cut off after N laps (current), (c) something traditional.

4. **Can you choose an empty pit?** [No — assumed, since there is nothing to sow.]

5. ~~Lap skip~~ **Answered:** there is no skip; a full lap sows into the starting pit too.

6. ~~Sweep edge case~~ **No longer applies:** the end-of-turn sweep was replaced by instant capture.
