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
    STAGE1_JOINT_PENDING = "stage1_joint_pending"  # NEW: Joint called, waiting for stage 2 deal completion
    STAGE2_DEALING = "stage2_dealing"  # Dealing remaining 2 cards
    STAGE2_TRUMP_SELECTION = "stage2_trump_selection"  # NEW: Joint caller selecting trump
    STAGE2_CHALLENGING = "stage2_challenging"  # Double/Shubble challenges
    PLAYING_HAND = "playing_hand"  # Playing cards in current hand
    GAME_OVER = "game_over"  # Game finished

class AduShertuGame:
    def __init__(self, game_code: str, is_dev_game: bool = False):
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
        self.joint_caller_index: Optional[int] = None # NEW: Index of player who called joint
        
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

        self.is_dev_game = is_dev_game

        self.ready_players = [] # List of player_ids who clicked 'Continue'
        
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
            "ready": False,
            "connected": True # Added for dev mode
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
        self.joint_caller_index = None # NEW: Reset joint caller
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
        
        # Trump calling starts to the left of the dealer
        self.trump_calling_index = (self.dealer_index + 1) % 6
    
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
        """Deal remaining 2 cards to each player to reach a total of 4."""
        # Start dealing from the person after the dealer
        for i in range(1, 7):
            player_index = (self.dealer_index + i) % 6
            # Deal exactly enough to reach 4 cards
            cards_needed = 4 - len(self.players[player_index]["cards"])
            for _ in range(cards_needed):
                if self.deck:
                    self.players[player_index]["cards"].append(self.deck.pop())
    
        # Identify jack trump team
        self._identify_jack_trump_team()
        
        # IMPORTANT: Transition the phase so the UI updates
        self.phase = GamePhase.STAGE2_CHALLENGING
    
    def attempt_trump_call(self, player_index: int, suit: Suit) -> Dict:
        if self.phase != GamePhase.STAGE1_TRUMP_CALLING:
            return {"success": False, "message": "Not in trump calling phase"}
        
        player = self.players[player_index]
        # Filter for cards of the chosen suit
        matching_cards = [c for c in player["cards"] if c.suit == suit]
        
        if not matching_cards:
            return {"success": False, "message": "You don't have that suit"}

        # If they have 2 of the suit, we must ask which one to keep
        if len(matching_cards) > 1:
            return {
                "success": True,
                "requires_card_choice": True,
                "choices": [c.to_dict() for c in matching_cards],
                "suit": suit.value,
                "message": "You have two of this suit. Which card are you calling trump on?"
            }

        # Standard call (only 1 card of that suit)
        self.trump_suit = suit
        self.trump_caller_index = player_index
        self.base_okalu = self._calculate_base_okalu(player_index)
        self.current_game_okalu = self.base_okalu
        self.phase = GamePhase.STAGE1_CHALLENGING
        return {"success": True, "trump_suit": suit.value}
            
    
    def attempt_joint_call(self, player_index: int) -> Dict: # MODIFIED: Removed suit arguments
        """Attempt to call joint with any pair of the same rank."""
        if self.phase != GamePhase.STAGE1_TRUMP_CALLING:
            return {"success": False, "message": "Not in trump calling phase"}
        
        if player_index != self.trump_calling_index:
            return {"success": False, "message": "Not your turn to call trump"}
        
        player = self.players[player_index]
        
        # NEW LOGIC: Joint on ANY pair (e.g., Q-Q, 10-10, A-A)
        ranks = [c.rank for c in player["cards"]]
        # A pair means there are 2 cards and both have the same rank
        if len(ranks) != 2 or ranks[0] != ranks[1]:
            return {"success": False, "message": "You need a pair of the same rank for Joint"}
        
        # Valid joint call
        self.joint_called = True
        self.trump_caller_index = player_index
        self.joint_caller_index = player_index 
        self.base_okalu = self._calculate_base_okalu(player_index)
        self.current_game_okalu = self.base_okalu * 2  # Joint auto-doubles
        self.challenge_multiplier = 2
        
        # Deal remaining cards (everyone moves to 4 cards)
        self._deal_stage2()
        
        # Wait for caller to pick suit from their 4 cards
        self.phase = GamePhase.STAGE2_TRUMP_SELECTION
        
        # Return ALL original fields so the frontend doesn't break
        return {
            "success": True,
            "joint_called": True,
            "base_okalu": self.base_okalu,
            "current_okalu": self.current_game_okalu,
            "message": f"Joint called with a pair of {ranks[0].value}s!"
        }
    
    def pass_trump_call(self, player_index: int) -> Dict:
        """Player passes on calling trump."""
        if player_index != self.trump_calling_index:
            return {"success": False, "message": "Not your turn"}
        
        # Move to next player
        self.trump_calling_index = (self.trump_calling_index + 1) % 6
        
        # The trump calling cycle ends at the dealer (whose turn it would be after player 5)
        # Note: The trump calling starts at (dealer + 1) % 6.
        start_index = (self.dealer_index + 1) % 6
        
        if self.trump_calling_index == start_index:
            # All players passed, need to reshuffle/discard
            if self.stage1_round == 1:
                # First round failed, shuffle all 12 dealt cards back into discarded_cards
                # The next 12 cards are dealt (which should contain the other two 9s)
                
                self.stage1_round = 2
                
                # Collect cards from all players and the deck (remaining 12 from 24-card deck)
                self.discarded_cards.extend([c for p in self.players for c in p["cards"]])
                # If there are still cards in the deck, they become the new 'deck'
                # In a 24-card deck, the first 12 were dealt. The remaining 12 are the new deck.
                # The assumption is that the second 12 cards are *already* in self.deck if not dealt.
                
                # Clear player hands
                for player in self.players:
                    player["cards"] = []
                
                # Deal the next 12 cards (the remaining ones)
                self._deal_stage1()
                
                # Reset trump calling turn back to dealer's left
                self.trump_calling_index = (self.dealer_index + 1) % 6
                
                return {
                    "success": True,
                    "reshuffled": True,
                    "message": "No trump called in first round, dealing new cards"
                }
            else:
                # Second round failed (this implies an error or unusual game state based on rules)
                # The PDF states it is *necessary* for a 9 to be called in this round.
                self.phase = GamePhase.GAME_OVER
                return {"success": False, "message": "Game ended prematurely: No trump called in two rounds."}
        
        return {"success": True, "next_player": self.trump_calling_index}
    
    def replace_same_suit_card(self, player_index: int, suit: Suit) -> Dict:
        """
        Replace a card that's the same suit as the trump 9.
        This repeats until a non-trump card is found, then moves the game to Stage 1 Challenging.
        """
        player = self.players[player_index]
        
        # 1. Find the card that matches the trump suit (and isn't the 9 used to call)
        # We copy the cards and remove one 9 of the trump suit to find the 'other' card
        temp_cards = player["cards"].copy()
        trump_nine = next((c for c in temp_cards if c.rank == Rank.NINE and c.suit == suit), None)
        if trump_nine:
            temp_cards.remove(trump_nine)
        
        same_suit_card = temp_cards[0] if temp_cards else None
        
        if not same_suit_card or same_suit_card.suit != suit:
            return {"success": False, "message": "No same-suit card found to replace"}
        
        # Remove the illegal card from the real player hand
        player["cards"].remove(same_suit_card)
        self.discarded_cards.append(same_suit_card)
        
        # 2. Draw replacement cards until we get a different suit
        replacements_shown = []
        new_card = None
        
        while True:
            if not self.deck:
                return {"success": False, "message": "Deck empty during replacement"}
            
            new_card = self.deck.pop()
            replacements_shown.append(new_card)
            
            # If the new card is NOT the trump suit, the player keeps it
            if new_card.suit != suit:
                player["cards"].append(new_card)
                break
            else:
                # New card is ALSO trump suit, show it to everyone and discard
                self.discarded_cards.append(new_card)
        
        # 3. TRANSITION THE GAME
        # The caller now has a legal 2-card hand. Now we finalize the call.
        self.base_okalu = self._calculate_base_okalu(player_index)
        self.current_game_okalu = self.base_okalu
        
        # Move to Challenging Phase
        self.phase = GamePhase.STAGE1_CHALLENGING
        
        return {
            "success": True,
            "discarded": same_suit_card.to_dict(),
            "replacements_shown": [c.to_dict() for c in replacements_shown],
            "final_card": new_card.to_dict(),
            "game_state": self.get_game_state() # Include state so UI updates to Challenging
        }
    def finalize_trump_call_selection(self, player_index: int, suit_val: str, calling_card_dict: Dict) -> Dict:
        player = self.players[player_index]
        suit = Suit(suit_val)
        
        # Identify the 'calling card' and the 'other card'
        other_card = None
        for c in player["cards"]:
            if c.suit == suit and (c.rank.value != calling_card_dict['rank']):
                other_card = c
                break
        
        if not other_card:
            return {"success": False, "message": "Could not identify card to replace"}

        # Remove the illegal 'other card' and discard it
        player["cards"].remove(other_card)
        self.discarded_cards.append(other_card)
        
        # Draw replacement
        replacements_shown = []
        new_card = None
        while True:
            new_card = self.deck.pop()
            replacements_shown.append(new_card)
            if new_card.suit != suit:
                player["cards"].append(new_card)
                break
            else:
                self.discarded_cards.append(new_card)

        # Finalize Call
        self.trump_suit = suit
        self.trump_caller_index = player_index
        self.base_okalu = self._calculate_base_okalu(player_index)
        self.current_game_okalu = self.base_okalu
        self.phase = GamePhase.STAGE1_CHALLENGING
        
        return {
            "success": True,
            "discarded": other_card.to_dict(),
            "replacements_shown": [c.to_dict() for c in replacements_shown],
            "final_card": new_card.to_dict()
        }

    def _calculate_base_okalu(self, trump_caller_index: int) -> int:
        """Calculate base okalu based on trump caller's distance from dealer."""
        # Calculate distance from dealer: (caller_index - dealer_index) % 6
        # The PDF describes the order relative to the dealer:
        # 0: Dealer (6 points)
        # 1: Player to left (5 points)
        # 2: Player next to that (4 points)
        # 3: Furthest player (3 points)
        # 4: Player next to that on the right side of dealer (4 points)
        # 5: Player to right of dealer (5 points)
        distance = (trump_caller_index - self.dealer_index) % 6
        okalu_map = {0: 6, 1: 5, 2: 4, 3: 3, 4: 4, 5: 5}
        
        # NOTE: The rule states: "Starting from the dealer, the player will look at their cards..."
        # This implies the dealer is the first person to check, making distance 0.
        
        return okalu_map[distance]
    
    def attempt_challenge(self, player_index: int, challenge_word: str) -> Dict:
        """
        Handles strict back-and-forth: Adu -> Shertu -> Challenge xN.
        """
        player_team = self.players[player_index]["team"]
        initial_team = self.players[self.trump_caller_index]["team"]

        # 1. Back-and-Forth Validation
        # If the last person to challenge was on YOUR team, you must wait.
        if self.last_challenger_team == player_team:
            return {"success": False, "message": "Wait for the other team to respond."}

        # 2. Sequential Word Validation
        if self.challenge_multiplier == 1:
            if player_team == initial_team:
                return {"success": False, "message": "Opponents must initiate Adu."}
            if challenge_word != "adu":
                return {"success": False, "message": "First challenge must be 'adu'."}
        
        elif self.challenge_multiplier == 2:
            if challenge_word != "shertu":
                return {"success": False, "message": "Second challenge must be 'shertu'."}

        # 3. Apply state changes
        self.challenge_multiplier *= 2 
        self.current_game_okalu = self.base_okalu * self.challenge_multiplier
        self.last_challenger_team = player_team
        self.challenge_type = challenge_word
        
        # CRITICAL: Reset ready players so everyone has to click 'Ready' again 
        # for the new Okalu value.
        self.ready_players = []

        return {
            "success": True, 
            "current_okalu": self.current_game_okalu,
            "challenge_type": challenge_word,
            "player_name": self.players[player_index]['name'],
            "game_state": self.get_game_state() # Ensure fresh state is returned
        }
    
    def respond_to_challenge(self, team: int, response: str) -> Dict:
        """
        Respond to a pending challenge.
        response: "accept", "fold"
        """
        if not self.pending_challenge:
            return {"success": False, "message": "No pending challenge"}
        
        # The team responding should be the opposing team
        if team == self.last_challenger_team:
            return {"success": False, "message": "Cannot respond to own challenge"}
        
        if response == "fold":
            # Team folds, apply okalu from one challenge before
            fold_okalu = self.base_okalu * (self.challenge_multiplier // 2)
            self.team_okalu[team] += fold_okalu
            
            # Game ends and state is reset
            self.phase = GamePhase.GAME_OVER 
            
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
            
            # If still in stage 2 challenging (before any card played), the game needs to continue.
            # If a card was played, the game continues normally.
            
            return {
                "success": True,
                "accepted": True,
                "current_okalu": self.current_game_okalu
            }
        
        return {"success": False, "message": "Invalid response"}
    
    def proceed_to_stage2(self):
        """Move from stage 1 (Adu/Shertu) to stage 2 (playing/Double/Shubble)."""
        if self.phase != GamePhase.STAGE1_CHALLENGING:
            return {"success": False, "message": "Not ready for stage 2"}
        
        # The Stage 2 deal happened immediately after the trump call/joint, 
        # so we skip GamePhase.STAGE2_DEALING.
        
        self.phase = GamePhase.STAGE2_CHALLENGING
        
        # Set current player to right of dealer for first hand
        # NOTE: The first player to go is the person to the right of the dealer.
        self.current_player_index = (self.dealer_index + 1) % 6
        
        return {"success": True}
    
    def toggle_ready_stage2(self, player_id: str) -> bool:
        """Tracks player readiness. Transitions phase and deals cards when 6/6 ready."""
        if player_id not in self.ready_players:
            self.ready_players.append(player_id)
            
        if len(self.ready_players) == 6:
            # THIS IS WHERE THE PROCEED LOGIC LIVES NOW
            self._deal_stage2()
            self.phase = GamePhase.STAGE2_CHALLENGING
            self.ready_players = [] # Reset for next time
            return True # Signal to app.py that we officially proceeded
            
        return False # Not everyone is ready yet

    def select_trump_after_joint(self, player_index: int, suit: Suit) -> Dict:
        """Select trump suit after calling joint."""
        if self.phase != GamePhase.STAGE2_TRUMP_SELECTION:
            return {"success": False, "message": "Not in trump selection phase"}
            
        if player_index != self.joint_caller_index: # MODIFIED: Use joint_caller_index
            return {"success": False, "message": "Only joint caller can select trump"}
        
        # Must be one of the two 9 suits (the player has the 9 in their hand)
        player = self.players[player_index]
        has_nine = any(c.rank == Rank.NINE and c.suit == suit for c in player["cards"])
        if not has_nine:
            return {"success": False, "message": "Must select a suit you have a 9 in"}
        
        self.trump_suit = suit
        self._identify_jack_trump_team() # Now that trump is set, identify Jack team
        
        # Move directly to challenging/playing phase
        self.phase = GamePhase.STAGE2_CHALLENGING
        
        # Set current player to right of dealer for first hand
        self.current_player_index = (self.dealer_index + 1) % 6
        
        return {"success": True, "trump_suit": suit.value}
    
    def _identify_jack_trump_team(self):
        """Identify which team has the jack of trump."""
        if not self.trump_suit:
            return
        
        # Only search if Jack-trump team hasn't been identified (important for Stage 2 joint)
        if self.jack_trump_team is not None:
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
        played_card = player["cards"].pop(card_index)
        self.current_hand_cards.append((player_index, played_card))
        
        # Set leading suit if first card
        if len(self.current_hand_cards) == 1:
            self.leading_suit = card.suit
            self.phase = GamePhase.PLAYING_HAND
        
        # Check if hand is complete
        if len(self.current_hand_cards) == 6:
            return self._complete_hand()
        
        # Move to next player
        self.current_player_index = (self.current_player_index + 1) % 6
        
        return {"success": True, "card_played": played_card.to_dict()}
    
    def _validate_card_play(self, player_index: int, card: Card) -> Dict:
        """Validate if a card can be played according to rules."""
        player = self.players[player_index]
        
        # First card of hand, any card is valid
        if not self.current_hand_cards:
            return {"valid": True}
        
        # --- Rule 1: Must follow leading suit if available ---
        has_leading_suit = any(c.suit == self.leading_suit for c in player["cards"])
        
        if has_leading_suit and card.suit != self.leading_suit:
            # Exception 1: They have a trump card that is higher than any currently placed trump.
            if card.suit == self.trump_suit and self.trump_suit is not None:
                highest_trump = self._get_highest_trump_in_hand()
                
                # Check if the played card is higher than the current highest trump
                is_higher_trump = highest_trump is None or self._compare_trump_cards(card, highest_trump) > 0
                
                if is_higher_trump:
                    return {"valid": True}
                else:
                    return {"valid": False, "reason": "Must play leading suit or a higher trump card."}
            
            # Exception 2: They have multiple cards in the leading suit and can choose which one to pick
            # This exception is implicitly handled by the user selecting a card that matches the leading suit
            # if the logic reaches here, they are attempting to play a non-leading, non-trump card when they have the leading suit, which is invalid.
            
            # If it's a non-trump, non-leading suit, it's an illegal play if they have the leading suit.
            return {"valid": False, "reason": "Must play the leading suit if you have it."}
        
        # --- Rule 2: Non-leading suit played ---
        if card.suit != self.leading_suit:
            # Exception 3: They have no cards in the leading suit and can place any card they wish, 
            # except if it is a trump card of lower hierarchy than the highest trump card placed.
            
            # Check if it's an invalid lower trump card
            if card.suit == self.trump_suit and self.trump_suit is not None:
                highest_trump = self._get_highest_trump_in_hand()
                
                if highest_trump and self._compare_trump_cards(card, highest_trump) < 0:
                    # Check exception to exception 3: If player only has trumps left
                    if all(c.suit == self.trump_suit for c in player["cards"]):
                        return {"valid": True}
                    else:
                        return {"valid": False, "reason": "Cannot play a lower trump card if you have other non-leading, non-trump cards."}
            
            # If the card is not a trump, or is a higher trump, or the only card left is a lower trump, it's valid (they couldn't follow suit).
            return {"valid": True}

        # --- Rule 3: Leading suit played (always valid if they reach here) ---
        return {"valid": True}
    
    def _get_highest_trump_in_hand(self) -> Optional[Card]:
        """Get the highest trump card currently in the hand."""
        if self.trump_suit is None:
            return None
        
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
        # Hierarchy: 10 < Q < K < A < 9 < J
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
        # Hierarchy: 9 < 10 < J < Q < K < A
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
        # NOTE: Okalu logic seems to favor the winning team by reducing their okalu debt first.
        
        okalu_to_apply = self.current_game_okalu
        
        # 1. Reduce winner's debt (if any)
        if self.team_okalu[winning_team] > 0:
            reduction = min(self.team_okalu[winning_team], okalu_to_apply)
            self.team_okalu[winning_team] -= reduction
            okalu_to_apply -= reduction
            
        # 2. Apply remaining okalu to loser's debt
        self.team_okalu[losing_team] += okalu_to_apply
        
        self.phase = GamePhase.GAME_OVER
        
        return {
            "success": True,
            "game_over": True,
            "winning_team": winning_team,
            "final_points": self.points_scored.copy(),
            "okalu_change": self.current_game_okalu,
            "team_okalu": self.team_okalu.copy()
        }
    
    def get_player_order(self) -> List[str]: # NEW METHOD
        """Returns the player IDs in their current seating order (0 to 5)."""
        return [p["id"] for p in self.players]

    def get_game_state(self, player_id: Optional[str] = None) -> Dict:
        """Get current game state, optionally filtered for a specific player."""
        state = {
            "game_code": self.game_code,
            "phase": self.phase.value,
            "ready_players": self.ready_players,
            "players": [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "team": p["team"],
                    "card_count": len(p["cards"]),
                    "connected": p.get("connected", True) # Added for dev mode
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
            "joint_called": self.joint_called,
            "joint_caller_index": self.joint_caller_index # NEW
        }

        # --- MODIFIED PLAYER LIST GENERATION ---
        state["players"] = []
        for p in self.players:
            player_data = {
                "id": p["id"],
                "name": p["name"],
                "team": p["team"],
                "card_count": len(p["cards"]),
                "connected": p.get("connected", True)
            }
            
            # If in Developer Mode, or if the client is the active player, expose cards
            if self.is_dev_game or p["id"] == player_id: # MODIFIED
                player_data["cards"] = [c.to_dict() for c in p["cards"]]
            
            state["players"].append(player_data)
        # --- END MODIFIED PLAYER LIST GENERATION ---
        
        # Add player-specific info if player_id provided
        if player_id:
            player = next((p for p in self.players if p["id"] == player_id), None)
            if player:
                state["my_cards"] = [c.to_dict() for c in player["cards"]]
                state["my_team"] = player["team"]
        
        return state