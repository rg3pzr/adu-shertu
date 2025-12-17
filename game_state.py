"""
game_state.py - Core game state management and rules engine for Adu Shertu

This file handles:
- Deck management and shuffling
- Card dealing logic
- Trump calling validation
- Hand/pattu gameplay rules
- Scoring and point calculation
- Okalu tracking
- Challenge system (Adu, Shertu, Double, Shubble)
"""

import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

class Suit(Enum):
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"
    SPADES = "♠"

class Rank(Enum):
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"

@dataclass
class Card:
    suit: Suit
    rank: Rank
    
    def __str__(self):
        return f"{self.rank.value}{self.suit.value}"
    
    def to_dict(self):
        return {
            "suit": self.suit.value,
            "rank": self.rank.value
        }

class GamePhase(Enum):
    WAITING = "waiting"  # Waiting for players
    STAGE1_DEALING = "stage1_dealing"  # Dealing first 2 cards
    STAGE1_TRUMP_CALLING = "stage1_trump_calling"  # Players calling trump
    STAGE1_CHALLENGING = "stage1_challenging"  # Adu/Shertu challenges
    STAGE2_DEALING = "stage2_dealing"  # Dealing remaining 2 cards
    STAGE2_CHALLENGING = "stage2_challenging"  # Double/Shubble challenges
    PLAYING_HAND = "playing_hand"  # Playing cards in current hand
    GAME_OVER = "game_over"  # Game finished

class AduShertuGame:
    def __init__(self, game_code: str):
        self.game_code = game_code
        self.players: List[Dict] = []  # List of player dicts with id, name, team, cards, etc.
        self.phase = GamePhase.WAITING
        
        # Deck management
        self.deck: List[Card] = []
        self.discarded_cards: List[Card] = []
        
        # Game state
        self.dealer_index: Optional[int] = None
        self.current_player_index: Optional[int] = None
        self.trump_suit: Optional[Suit] = None
        self.trump_caller_index: Optional[int] = None
        self.joint_called = False
        
        # Okalu tracking
        self.team_okalu = [0, 0]  # [Team 0, Team 1]
        self.current_game_okalu = 0
        self.base_okalu = 0
        
        # Challenge tracking
        self.challenge_multiplier = 1
        self.last_challenger_team: Optional[int] = None
        self.pending_challenge = False
        self.challenge_type: Optional[str] = None  # "double" or "shubble"
        
        # Hand/Pattu state
        self.current_hand_number = 0  # 0-3 for four hands
        self.current_hand_cards: List[Tuple[int, Card]] = []  # [(player_index, card), ...]
        self.leading_suit: Optional[Suit] = None
        self.hands_won = [0, 0]  # [Team 0, Team 1]
        self.points_scored = [0, 0]  # [Team 0, Team 1]
        
        # Jack tracking
        self.jack_trump_team: Optional[int] = None
        
        # Stage 1 trump calling
        self.stage1_round = 1  # Track which round of trump calling (1 or 2)
        self.trump_calling_index = 0  # Track whose turn to call trump
        
    def add_player(self, player_id: str, player_name: str) -> bool:
        """Add a player to the game. Returns True if successful."""
        if len(self.players) >= 6:
            return False
        
        team = len(self.players) % 2  # Alternate teams: 0, 1, 0, 1, 0, 1
        self.players.append({
            "id": player_id,
            "name": player_name,
            "team": team,
            "cards": [],
            "ready": False
        })
        return True
    
    def start_game(self):
        """Initialize a new game round."""
        if len(self.players) != 6:
            raise ValueError("Need exactly 6 players to start")
        
        # Determine dealer based on okalu
        if self.team_okalu[0] > 0:
            # Team 0 has okalu, they deal
            team_0_players = [i for i, p in enumerate(self.players) if p["team"] == 0]
            self.dealer_index = random.choice(team_0_players)
        elif self.team_okalu[1] > 0:
            # Team 1 has okalu, they deal
            team_1_players = [i for i, p in enumerate(self.players) if p["team"] == 1]
            self.dealer_index = random.choice(team_1_players)
        else:
            # First game, random dealer
            self.dealer_index = random.randint(0, 5)
        
        # Reset game state
        self.deck = self._create_deck()
        random.shuffle(self.deck)
        self.discarded_cards = []
        self.trump_suit = None
        self.trump_caller_index = None
        self.joint_called = False
        self.challenge_multiplier = 1
        self.last_challenger_team = None
        self.pending_challenge = False
        self.challenge_type = None
        self.current_hand_number = 0
        self.current_hand_cards = []
        self.leading_suit = None
        self.hands_won = [0, 0]
        self.points_scored = [0, 0]
        self.jack_trump_team = None
        self.stage1_round = 1
        
        # Clear player cards
        for player in self.players:
            player["cards"] = []
        
        # Start stage 1: deal 2 cards to each player
        self._deal_stage1()
        self.phase = GamePhase.STAGE1_TRUMP_CALLING
        self.trump_calling_index = self.dealer_index
    
    def _create_deck(self) -> List[Card]:
        """Create a 24-card deck (9, 10, J, Q, K, A of each suit)."""
        deck = []
        for suit in Suit:
            for rank in Rank:
                deck.append(Card(suit, rank))
        return deck
    
    def _deal_stage1(self):
        """Deal 2 cards to each player starting from dealer."""
        for i in range(6):
            player_index = (self.dealer_index + i) % 6
            for _ in range(2):
                if self.deck:
                    self.players[player_index]["cards"].append(self.deck.pop())
    
    def _deal_stage2(self):
        """Deal remaining 2 cards to each player."""
        for i in range(6):
            player_index = (self.dealer_index + i) % 6
            for _ in range(2):
                if self.deck:
                    self.players[player_index]["cards"].append(self.deck.pop())
        
        # Identify jack trump team
        self._identify_jack_trump_team()
    
    def attempt_trump_call(self, player_index: int, suit: Suit) -> Dict:
        """
        Attempt to call trump with a 9 of the specified suit.
        Returns dict with success status and any required actions.
        """
        if self.phase != GamePhase.STAGE1_TRUMP_CALLING:
            return {"success": False, "message": "Not in trump calling phase"}
        
        if player_index != self.trump_calling_index:
            return {"success": False, "message": "Not your turn to call trump"}
        
        player = self.players[player_index]
        
        # Check if player has the 9 of the specified suit
        has_nine = any(c.rank == Rank.NINE and c.suit == suit for c in player["cards"])
        if not has_nine:
            return {"success": False, "message": "You don't have the 9 of that suit"}
        
        # Check if other card is same suit
        other_cards = [c for c in player["cards"] if not (c.rank == Rank.NINE and c.suit == suit)]
        same_suit_card = next((c for c in other_cards if c.suit == suit), None)
        
        if same_suit_card:
            # Must show and replace
            return {
                "success": False,
                "requires_replacement": True,
                "card_to_replace": same_suit_card.to_dict(),
                "message": "Other card is same suit, must replace"
            }
        
        # Valid trump call
        self.trump_suit = suit
        self.trump_caller_index = player_index
        self.base_okalu = self._calculate_base_okalu(player_index)
        self.current_game_okalu = self.base_okalu
        self.phase = GamePhase.STAGE1_CHALLENGING
        
        return {
            "success": True,
            "trump_suit": suit.value,
            "base_okalu": self.base_okalu,
            "message": f"Trump called: {suit.value}"
        }
    
    def attempt_joint_call(self, player_index: int, suit1: Suit, suit2: Suit) -> Dict:
        """Attempt to call joint with two 9s."""
        if self.phase != GamePhase.STAGE1_TRUMP_CALLING:
            return {"success": False, "message": "Not in trump calling phase"}
        
        if player_index != self.trump_calling_index:
            return {"success": False, "message": "Not your turn to call trump"}
        
        player = self.players[player_index]
        
        # Check if player has both 9s
        has_nine_1 = any(c.rank == Rank.NINE and c.suit == suit1 for c in player["cards"])
        has_nine_2 = any(c.rank == Rank.NINE and c.suit == suit2 for c in player["cards"])
        
        if not (has_nine_1 and has_nine_2):
            return {"success": False, "message": "You don't have both 9s"}
        
        # Valid joint call
        self.joint_called = True
        self.trump_caller_index = player_index
        self.base_okalu = self._calculate_base_okalu(player_index)
        self.current_game_okalu = self.base_okalu * 2  # Joint auto-doubles
        self.challenge_multiplier = 2
        
        # Don't set trump yet, will be set after stage 2
        self.phase = GamePhase.STAGE2_DEALING
        self._deal_stage2()
        
        return {
            "success": True,
            "joint_called": True,
            "base_okalu": self.base_okalu,
            "current_okalu": self.current_game_okalu,
            "message": "Joint called! Choose trump after seeing all 4 cards"
        }
    
    def pass_trump_call(self, player_index: int) -> Dict:
        """Player passes on calling trump."""
        if player_index != self.trump_calling_index:
            return {"success": False, "message": "Not your turn"}
        
        # Move to next player
        self.trump_calling_index = (self.trump_calling_index + 1) % 6
        
        # Check if we've gone full circle
        if self.trump_calling_index == self.dealer_index:
            # All players passed, need to reshuffle
            if self.stage1_round == 1:
                # First round failed, try again with remaining 12 cards
                self.stage1_round = 2
                self.discarded_cards.extend([c for p in self.players for c in p["cards"]])
                for player in self.players:
                    player["cards"] = []
                self._deal_stage1()
                return {
                    "success": True,
                    "reshuffled": True,
                    "message": "No trump called, dealing new cards"
                }
            else:
                # This shouldn't happen (deck has 4 nines)
                return {"success": False, "message": "ERROR: No trump in second round"}
        
        return {"success": True, "next_player": self.trump_calling_index}
    
    def replace_same_suit_card(self, player_index: int, suit: Suit) -> Dict:
        """Replace a card that's the same suit as the trump 9."""
        player = self.players[player_index]
        
        # Find and remove the same-suit card
        same_suit_card = next((c for c in player["cards"] if c.suit == suit and c.rank != Rank.NINE), None)
        if not same_suit_card:
            return {"success": False, "message": "No same-suit card found"}
        
        player["cards"].remove(same_suit_card)
        self.discarded_cards.append(same_suit_card)
        
        # Draw replacement cards until we get a different suit
        replacements_shown = []
        while True:
            if not self.deck:
                return {"success": False, "message": "Deck empty"}
            
            new_card = self.deck.pop()
            replacements_shown.append(new_card)
            
            if new_card.suit != suit:
                player["cards"].append(new_card)
                break
            else:
                self.discarded_cards.append(new_card)
        
        return {
            "success": True,
            "discarded": same_suit_card.to_dict(),
            "replacements_shown": [c.to_dict() for c in replacements_shown],
            "final_card": new_card.to_dict()
        }
    
    def _calculate_base_okalu(self, trump_caller_index: int) -> int:
        """Calculate base okalu based on trump caller's distance from dealer."""
        distance = (trump_caller_index - self.dealer_index) % 6
        okalu_map = {0: 6, 1: 5, 2: 4, 3: 3, 4: 4, 5: 5}
        return okalu_map[distance]
    
    def attempt_challenge(self, player_index: int, challenge_word: str) -> Dict:
        """
        Attempt to issue a challenge (Adu, Shertu, Double, Shubble).
        challenge_word: "adu", "shertu", "double", "shubble"
        """
        player_team = self.players[player_index]["team"]
        trump_caller_team = self.players[self.trump_caller_index]["team"]
        
        if self.phase == GamePhase.STAGE1_CHALLENGING:
            if challenge_word == "adu":
                # Only opposing team can call Adu
                if player_team == trump_caller_team:
                    return {"success": False, "message": "Only opposing team can call Adu"}
                
                self.challenge_multiplier *= 2
                self.current_game_okalu = self.base_okalu * self.challenge_multiplier
                self.last_challenger_team = player_team
                
                return {"success": True, "current_okalu": self.current_game_okalu}
            
            elif challenge_word == "shertu":
                # Only trump calling team can call Shertu (after Adu)
                if player_team != trump_caller_team:
                    return {"success": False, "message": "Only trump calling team can call Shertu"}
                if self.last_challenger_team != (1 - player_team):
                    return {"success": False, "message": "Can only call Shertu after Adu"}
                
                self.challenge_multiplier *= 2
                self.current_game_okalu = self.base_okalu * self.challenge_multiplier
                self.last_challenger_team = player_team
                
                return {"success": True, "current_okalu": self.current_game_okalu}
        
        elif self.phase == GamePhase.STAGE2_CHALLENGING or self.phase == GamePhase.PLAYING_HAND:
            # Can only call double before 2nd card is played
            if len(self.current_hand_cards) >= 2:
                return {"success": False, "message": "Too late to challenge"}
            
            if challenge_word == "double":
                if self.pending_challenge:
                    return {"success": False, "message": "Challenge already pending"}
                
                self.challenge_multiplier *= 2
                self.current_game_okalu = self.base_okalu * self.challenge_multiplier
                self.last_challenger_team = player_team
                self.pending_challenge = True
                self.challenge_type = "double"
                
                return {"success": True, "current_okalu": self.current_game_okalu, "awaiting_response": True}
            
            elif challenge_word == "shubble":
                if not self.pending_challenge:
                    return {"success": False, "message": "No pending challenge to shubble"}
                if player_team == self.last_challenger_team:
                    return {"success": False, "message": "Cannot shubble your own challenge"}
                
                self.challenge_multiplier *= 2
                self.current_game_okalu = self.base_okalu * self.challenge_multiplier
                self.last_challenger_team = player_team
                self.challenge_type = "shubble"
                
                return {"success": True, "current_okalu": self.current_game_okalu, "awaiting_response": True}
        
        return {"success": False, "message": "Invalid challenge"}
    
    def respond_to_challenge(self, team: int, response: str) -> Dict:
        """
        Respond to a pending challenge.
        response: "accept", "fold"
        """
        if not self.pending_challenge:
            return {"success": False, "message": "No pending challenge"}
        
        if team == self.last_challenger_team:
            return {"success": False, "message": "Cannot respond to own challenge"}
        
        if response == "fold":
            # Team folds, apply okalu from one challenge before
            fold_okalu = self.base_okalu * (self.challenge_multiplier // 2)
            self.team_okalu[team] += fold_okalu
            
            return {
                "success": True,
                "folded": True,
                "okalu_applied": fold_okalu,
                "team_okalu": self.team_okalu.copy()
            }
        
        elif response == "accept":
            # Challenge accepted, continue game
            self.pending_challenge = False
            self.challenge_type = None
            
            return {
                "success": True,
                "accepted": True,
                "current_okalu": self.current_game_okalu
            }
        
        return {"success": False, "message": "Invalid response"}
    
    def proceed_to_stage2(self):
        """Move from stage 1 to stage 2."""
        if self.phase != GamePhase.STAGE1_CHALLENGING:
            return {"success": False, "message": "Not ready for stage 2"}
        
        self.phase = GamePhase.STAGE2_DEALING
        self._deal_stage2()
        self.phase = GamePhase.STAGE2_CHALLENGING
        
        # Set current player to right of dealer for first hand
        self.current_player_index = (self.dealer_index + 1) % 6
        
        return {"success": True}
    
    def select_trump_after_joint(self, player_index: int, suit: Suit) -> Dict:
        """Select trump suit after calling joint."""
        if player_index != self.trump_caller_index:
            return {"success": False, "message": "Only joint caller can select trump"}
        
        # Must be one of the two 9 suits
        player = self.players[player_index]
        has_nine = any(c.rank == Rank.NINE and c.suit == suit for c in player["cards"])
        if not has_nine:
            return {"success": False, "message": "Must select a suit you have a 9 in"}
        
        self.trump_suit = suit
        self.phase = GamePhase.STAGE2_CHALLENGING
        self.current_player_index = (self.dealer_index + 1) % 6
        
        return {"success": True, "trump_suit": suit.value}
    
    def _identify_jack_trump_team(self):
        """Identify which team has the jack of trump."""
        if not self.trump_suit:
            return
        
        for i, player in enumerate(self.players):
            for card in player["cards"]:
                if card.rank == Rank.JACK and card.suit == self.trump_suit:
                    self.jack_trump_team = player["team"]
                    return
    
    def play_card(self, player_index: int, card_index: int) -> Dict:
        """Play a card in the current hand."""
        if self.phase not in [GamePhase.PLAYING_HAND, GamePhase.STAGE2_CHALLENGING]:
            return {"success": False, "message": "Not in playing phase"}
        
        if self.pending_challenge:
            return {"success": False, "message": "Challenge pending, cannot play"}
        
        if player_index != self.current_player_index:
            return {"success": False, "message": "Not your turn"}
        
        player = self.players[player_index]
        if card_index >= len(player["cards"]):
            return {"success": False, "message": "Invalid card"}
        
        card = player["cards"][card_index]
        
        # Validate card play
        validation = self._validate_card_play(player_index, card)
        if not validation["valid"]:
            return {"success": False, "message": validation["reason"]}
        
        # Play the card
        player["cards"].pop(card_index)
        self.current_hand_cards.append((player_index, card))
        
        # Set leading suit if first card
        if len(self.current_hand_cards) == 1:
            self.leading_suit = card.suit
            self.phase = GamePhase.PLAYING_HAND
        
        # Check if hand is complete
        if len(self.current_hand_cards) == 6:
            return self._complete_hand()
        
        # Move to next player
        self.current_player_index = (self.current_player_index + 1) % 6
        
        return {"success": True, "card_played": card.to_dict()}
    
    def _validate_card_play(self, player_index: int, card: Card) -> Dict:
        """Validate if a card can be played according to rules."""
        player = self.players[player_index]
        
        # First card of hand, any card is valid
        if not self.current_hand_cards:
            return {"valid": True}
        
        # Check leading suit requirement
        has_leading_suit = any(c.suit == self.leading_suit for c in player["cards"])
        
        if has_leading_suit and card.suit != self.leading_suit:
            # Must play leading suit if you have it, unless...
            # Exception 1: Playing higher trump
            if card.suit == self.trump_suit:
                highest_trump = self._get_highest_trump_in_hand()
                if highest_trump and self._compare_trump_cards(card, highest_trump) > 0:
                    return {"valid": True}
                else:
                    return {"valid": False, "reason": "Must play leading suit or higher trump"}
            else:
                return {"valid": False, "reason": "Must play leading suit"}
        
        # Not leading suit, check trump restrictions
        if card.suit == self.trump_suit:
            highest_trump = self._get_highest_trump_in_hand()
            if highest_trump:
                if self._compare_trump_cards(card, highest_trump) < 0:
                    # Playing lower trump
                    # Only allowed if only have trump cards
                    if all(c.suit == self.trump_suit for c in player["cards"]):
                        return {"valid": True}
                    else:
                        return {"valid": False, "reason": "Cannot play lower trump"}
        
        return {"valid": True}
    
    def _get_highest_trump_in_hand(self) -> Optional[Card]:
        """Get the highest trump card currently in the hand."""
        trump_cards = [card for _, card in self.current_hand_cards if card.suit == self.trump_suit]
        if not trump_cards:
            return None
        
        return max(trump_cards, key=lambda c: self._get_trump_rank(c.rank))
    
    def _compare_trump_cards(self, card1: Card, card2: Card) -> int:
        """Compare two trump cards. Returns 1 if card1 > card2, -1 if card1 < card2, 0 if equal."""
        rank1 = self._get_trump_rank(card1.rank)
        rank2 = self._get_trump_rank(card2.rank)
        
        if rank1 > rank2:
            return 1
        elif rank1 < rank2:
            return -1
        return 0
    
    def _get_trump_rank(self, rank: Rank) -> int:
        """Get the hierarchy value for a trump card."""
        trump_hierarchy = {
            Rank.TEN: 1,
            Rank.QUEEN: 2,
            Rank.KING: 3,
            Rank.ACE: 4,
            Rank.NINE: 5,
            Rank.JACK: 6
        }
        return trump_hierarchy[rank]
    
    def _get_non_trump_rank(self, rank: Rank) -> int:
        """Get the hierarchy value for a non-trump card."""
        non_trump_hierarchy = {
            Rank.NINE: 1,
            Rank.TEN: 2,
            Rank.JACK: 3,
            Rank.QUEEN: 4,
            Rank.KING: 5,
            Rank.ACE: 6
        }
        return non_trump_hierarchy[rank]
    
    def _complete_hand(self) -> Dict:
        """Complete the current hand and determine winner."""
        # Determine winner
        winner_index = self._determine_hand_winner()
        winner_team = self.players[winner_index]["team"]
        
        # Calculate points
        hand_points = sum(self._get_card_points(card) for _, card in self.current_hand_cards)
        
        # Add bonus for last hand
        if self.current_hand_number == 3:
            hand_points += 5
        
        self.points_scored[winner_team] += hand_points
        self.hands_won[winner_team] += 1
        
        # Check for early game end
        non_jack_team = 1 - self.jack_trump_team if self.jack_trump_team is not None else None
        if non_jack_team is not None and self.points_scored[non_jack_team] >= 47:
            return self._end_game(non_jack_team)
        
        # Check if all hands complete
        if self.current_hand_number == 3:
            # Game over, check if jack team made 100
            if self.jack_trump_team is not None:
                if self.points_scored[self.jack_trump_team] >= 100:
                    return self._end_game(self.jack_trump_team)
                else:
                    return self._end_game(non_jack_team)
        
        # Move to next hand
        self.current_hand_number += 1
        self.current_hand_cards = []
        self.leading_suit = None
        self.current_player_index = winner_index  # Winner leads next hand
        
        return {
            "success": True,
            "hand_complete": True,
            "winner": winner_index,
            "winner_team": winner_team,
            "hand_points": hand_points,
            "points_scored": self.points_scored.copy(),
            "next_leader": winner_index
        }
    
    def _determine_hand_winner(self) -> int:
        """Determine the winner of the current hand."""
        # Find highest card
        trump_cards = [(i, card) for i, card in self.current_hand_cards if card.suit == self.trump_suit]
        
        if trump_cards:
            # Highest trump wins
            winner = max(trump_cards, key=lambda x: self._get_trump_rank(x[1].rank))
            return winner[0]
        
        # No trumps, highest card of leading suit wins
        leading_cards = [(i, card) for i, card in self.current_hand_cards if card.suit == self.leading_suit]
        winner = max(leading_cards, key=lambda x: self._get_non_trump_rank(x[1].rank))
        return winner[0]
    
    def _get_card_points(self, card: Card) -> int:
        """Get point value for a card."""
        if card.suit == self.trump_suit:
            trump_points = {
                Rank.NINE: 14,
                Rank.TEN: 10,
                Rank.JACK: 20,
                Rank.QUEEN: 2,
                Rank.KING: 3,
                Rank.ACE: 11
            }
            return trump_points[card.rank]
        else:
            non_trump_points = {
                Rank.NINE: 0,
                Rank.TEN: 10,
                Rank.JACK: 1,
                Rank.QUEEN: 2,
                Rank.KING: 3,
                Rank.ACE: 11
            }
            return non_trump_points[card.rank]
    
    def _end_game(self, winning_team: int) -> Dict:
        """End the game and update okalu."""
        losing_team = 1 - winning_team
        
        # Update okalu
        self.team_okalu[losing_team] += self.current_game_okalu
        
        # Check if winning team had okalu to reduce
        if self.team_okalu[winning_team] > 0:
            reduction = min(self.team_okalu[winning_team], self.current_game_okalu)
            self.team_okalu[winning_team] -= reduction
            remaining = self.current_game_okalu - reduction
            if remaining > 0:
                self.team_okalu[losing_team] += remaining
        
        self.phase = GamePhase.GAME_OVER
        
        return {
            "success": True,
            "game_over": True,
            "winning_team": winning_team,
            "final_points": self.points_scored.copy(),
            "okalu_change": self.current_game_okalu,
            "team_okalu": self.team_okalu.copy()
        }
    
    def get_game_state(self, player_id: Optional[str] = None) -> Dict:
        """Get current game state, optionally filtered for a specific player."""
        state = {
            "game_code": self.game_code,
            "phase": self.phase.value,
            "players": [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "team": p["team"],
                    "card_count": len(p["cards"])
                }
                for p in self.players
            ],
            "dealer_index": self.dealer_index,
            "current_player_index": self.current_player_index,
            "trump_suit": self.trump_suit.value if self.trump_suit else None,
            "trump_caller_index": self.trump_caller_index,
            "team_okalu": self.team_okalu.copy(),
            "current_game_okalu": self.current_game_okalu,
            "current_hand_number": self.current_hand_number,
            "current_hand_cards": [(i, c.to_dict()) for i, c in self.current_hand_cards],
            "leading_suit": self.leading_suit.value if self.leading_suit else None,
            "points_scored": self.points_scored.copy(),
            "hands_won": self.hands_won.copy(),
            "pending_challenge": self.pending_challenge,
            "challenge_type": self.challenge_type,
            "last_challenger_team": self.last_challenger_team,
            "trump_calling_index": self.trump_calling_index,
            "joint_called": self.joint_called
        }
        
        # Add player-specific info if player_id provided
        if player_id:
            player = next((p for p in self.players if p["id"] == player_id), None)
            if player:
                state["my_cards"] = [c.to_dict() for c in player["cards"]]
                state["my_team"] = player["team"]
        
        return state