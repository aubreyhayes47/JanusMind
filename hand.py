# hand.py
from dataclasses import dataclass, field
from typing import List, Callable

from deck import Deck
from hand_evaluator import evaluate_hand


@dataclass
class PlayerState:
    seat: int
    stack: int
    hole_cards: List = field(default_factory=list)
    current_bet: int = 0
    total_contributed: int = 0
    has_folded: bool = False

    def reset_for_new_hand(self):
        self.hole_cards = []
        self.current_bet = 0
        self.total_contributed = 0
        self.has_folded = False


class HoldemHand:
    def __init__(self, players: List[PlayerState]):
        self.players = players
        self.deck = Deck()
        self.board = []
        self.pot = 0
        self.side_pots = []

    # ----------------------------------------------------------------------
    # Utilities
    # ----------------------------------------------------------------------

    def reset_for_new_deck(self):
        self.deck = Deck()
        self.board = []
        for p in self.players:
            p.reset_for_new_hand()

    def living_players(self):
        return [p for p in self.players if not p.has_folded and p.stack > 0]

    # ----------------------------------------------------------------------
    # Dealing
    # ----------------------------------------------------------------------

    def deal_hole_cards(self):
        for _ in range(2):
            for p in self.players:
                p.hole_cards.append(self.deck.deal(1))  # returns Card

    def deal_flop(self):
        self.deck.deal(1)  # burn
        flop = self.deck.deal(3)
        self.board.extend(flop)

    def deal_turn(self):
        self.deck.deal(1)  # burn
        self.board.append(self.deck.deal(1))

    def deal_river(self):
        self.deck.deal(1)  # burn
        self.board.append(self.deck.deal(1))

    # ----------------------------------------------------------------------
    # Blinds
    # ----------------------------------------------------------------------

    def post_blinds(self, sb, bb):
        sb_player = self.players[0]
        bb_player = self.players[1]

        sb_amt = min(sb_player.stack, sb)
        bb_amt = min(bb_player.stack, bb)

        sb_player.stack -= sb_amt
        bb_player.stack -= bb_amt

        sb_player.current_bet = sb_amt
        bb_player.current_bet = bb_amt

        self.pot = sb_amt + bb_amt

    # ----------------------------------------------------------------------
    # Betting Logic
    # ----------------------------------------------------------------------

    def collect_bets_into_pot(self):
        for p in self.players:
            self.pot += p.current_bet
            p.total_contributed += p.current_bet
            p.current_bet = 0

    def run_betting_round(self, starting_player_index: int, agents: List, street_name: str):
        """
        Level-1 simplified betting:
        - 1 bet allowed per street
        - players can fold/call/bet/raise
        """

        current_bet = max(p.current_bet for p in self.players)
        num_players = len(self.players)
        acted = [False] * num_players

        idx = starting_player_index

        while not all(acted):
            player = self.players[idx]

            if not player.has_folded and player.stack > 0:
                to_call = current_bet - player.current_bet

                action = agents[idx].act(
                    hole_cards=player.hole_cards,
                    board=self.board,
                    pot=self.pot,
                    to_call=to_call,
                    stack=player.stack,
                    street=street_name
                )

                kind = action["type"]

                # ---------------------------
                # ACTIONS
                # ---------------------------
                if kind == "fold":
                    player.has_folded = True

                elif kind == "call":
                    amount = min(player.stack, to_call)
                    player.stack -= amount
                    player.current_bet += amount

                elif kind == "bet":
                    size = min(action["amount"], player.stack)
                    player.stack -= size
                    player.current_bet += size
                    current_bet = player.current_bet

                elif kind == "raise":
                    size = action["amount"]
                    target = current_bet + size
                    diff = target - player.current_bet
                    diff = min(diff, player.stack)
                    player.stack -= diff
                    player.current_bet += diff
                    current_bet = player.current_bet

            acted[idx] = True
            idx = (idx + 1) % num_players

        self.collect_bets_into_pot()

    # ----------------------------------------------------------------------
    # Side Pots
    # ----------------------------------------------------------------------

    def build_side_pots(self):
        contribs = {p: p.total_contributed for p in self.players}
        caps = sorted(set(contribs.values()))

        self.side_pots = []
        prev = 0

        for cap in caps:
            slice_amt = cap - prev
            pot_size = 0
            eligible = []

            for p in self.players:
                if contribs[p] >= cap:
                    pot_size += slice_amt
                    eligible.append(p)

            self.side_pots.append((pot_size, eligible))
            prev = cap

    # ----------------------------------------------------------------------
    # Showdown
    # ----------------------------------------------------------------------

    def showdown(self):
        results = []

        for pot_amount, eligible in self.side_pots:
            contenders = [p for p in eligible if not p.has_folded]
            if not contenders:
                continue

            scores = [(evaluate_hand(p.hole_cards, self.board), p) for p in contenders]
            scores.sort(key=lambda x: x[0])
            best = scores[0][0]

            winners = [p for score, p in scores if score == best]

            share = pot_amount // len(winners)
            for w in winners:
                w.stack += share

            results.append((pot_amount, winners))

        return results

    # ----------------------------------------------------------------------
    # Full Hand Execution
    # ----------------------------------------------------------------------

    def play_hand(self, agents, sb=5, bb=10):
        self.reset_for_new_deck()

        self.deal_hole_cards()
        self.post_blinds(sb, bb)

        self.run_betting_round(2, agents, "preflop")

        if len(self.living_players()) > 1:
            self.deal_flop()
            self.run_betting_round(0, agents, "flop")

        if len(self.living_players()) > 1:
            self.deal_turn()
            self.run_betting_round(0, agents, "turn")

        if len(self.living_players()) > 1:
            self.deal_river()
            self.run_betting_round(0, agents, "river")

        self.build_side_pots()
        result = self.showdown()

        return {
            "board": self.board,
            "side_pots": self.side_pots,
            "result": result,
            "players": self.players
        }

    # ----------------------------------------------------------------------

    def board_str(self):
        return " ".join(str(c) for c in self.board)
