from typing import List
from player import PlayerState
from actions import Action, ActionType

class BettingRound:
    def __init__(self, players: List[PlayerState], starting_player: int):
        self.players = players
        self.current_player = starting_player

        # highest bet at start (handles blinds)
        self.highest_bet = max(p.current_bet for p in players)

        # Track whether each player has acted in this round
        self.has_acted = {p.seat_id: False for p in players}

    def next_player_index(self, i: int) -> int:
        n = len(self.players)
        return (i + 1) % n

    def one_player_left(self) -> bool:
        active = [p for p in self.players if not p.has_folded]
        return len(active) <= 1

    def all_bets_settled(self) -> bool:
        if self.one_player_left():
            return True

        # Must satisfy both conditions:
        # 1. Everyone has acted AT LEAST ONCE
        # 2. All bets match the highest bet (ignoring all-in/folded)
        for p in self.players:
            if p.has_folded or p.is_all_in:
                continue
            if not self.has_acted[p.seat_id]:
                return False
            if p.current_bet != self.highest_bet:
                return False

        return True

    def apply_action(self, player: PlayerState, action: Action):
        self.has_acted[player.seat_id] = True

        if action.type == ActionType.FOLD:
            player.has_folded = True
            return

        if action.type == ActionType.CHECK:
            return  # valid only when equal bets; agent handles choice

        if action.type == ActionType.CALL:
            to_call = self.highest_bet - player.current_bet
            call_amount = min(to_call, player.stack)
            player.current_bet += call_amount
            player.stack -= call_amount
            if player.stack == 0:
                player.is_all_in = True
            return

        if action.type == ActionType.BET:
            amount = min(action.amount, player.stack)
            player.current_bet += amount
            player.stack -= amount
            self.highest_bet = player.current_bet
            if player.stack == 0:
                player.is_all_in = True

            # IMPORTANT: On a new bet, everyone else must act again
            for p in self.players:
                self.has_acted[p.seat_id] = (p is player)
            return

        if action.type == ActionType.RAISE:
            to_call = self.highest_bet - player.current_bet
            total = min(to_call + action.amount, player.stack)
            player.current_bet += total
            player.stack -= total
            self.highest_bet = player.current_bet
            if player.stack == 0:
                player.is_all_in = True

            # New raise means everyone must act again
            for p in self.players:
                self.has_acted[p.seat_id] = (p is player)
            return

    def run(self, agent_fn, street_name=""):
        # First round: invalid to exit before first action
        first_action_taken = False

        while True:
            if first_action_taken and self.all_bets_settled():
                break

            player = self.players[self.current_player]

            if not (player.has_folded or player.is_all_in):
                action = agent_fn(player, self)
                self.apply_action(player, action)
                first_action_taken = True

            self.current_player = self.next_player_index(self.current_player)
