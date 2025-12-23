"""
app.py - Main Flask application with WebSocket support

This file handles:
- HTTP routes for serving the web interface
- WebSocket connections for real-time multiplayer
- Game room management
- Player connection/disconnection handling
- Broadcasting game state updates to all players
"""

from flask import Flask, render_template, request, jsonify, session # CHANGE: ADDED session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import random
import string
from game_state import AduShertuGame, Suit, Rank
from typing import Dict
import os # NEW: ADDED os

# Set DEVELOPER_MODE using an environment variable, defaulting to False.
# To enable, run with: DEVELOPER_MODE=True python app.py
DEVELOPER_MODE = os.environ.get('DEVELOPER_MODE', 'False').lower() in ('true', '1', 't')

print(f"*** DEBUG: DEVELOPER_MODE is set to: {DEVELOPER_MODE} ***")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Store active games: {game_code: AduShertuGame}
active_games: Dict[str, AduShertuGame] = {}

# NEW: Global Game State for Developer Mode (SINGLE INSTANCE)
DEV_GAME_CODE = "DEVGAME"
if DEVELOPER_MODE and DEV_GAME_CODE not in active_games:
    active_games[DEV_GAME_CODE] = AduShertuGame(DEV_GAME_CODE, is_dev_game=True)

# Store player connections: {session_id: (game_code, player_id)}
player_connections: Dict[str, tuple] = {}

def generate_game_code() -> str:
    """Generate a unique 6-character game code."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in active_games:
            return code

@app.route('/')
def index():
    """Serve the main game interface."""
    player_id = session.get('player_id')
    
    # === DEVELOPER MODE PLAYER SETUP ===
    if DEVELOPER_MODE:
        # FIX: game_state is now scoped correctly from the global active_games dictionary
        game_state = active_games[DEV_GAME_CODE]
        player_id = session.get('player_id')

        # Auto-create 6 players if they don't exist
        if len(game_state.players) < 6:
            for i in range(1, 7):
                pid = f"dev_player_{i}"
                # Team 0 for players 1, 3, 5; Team 1 for players 2, 4, 6
                game_state.add_player(pid, f"Player {i}")

        # Set the current session ID to Player 1 if not set or if the current ID is invalid
        player_ids_list = [p['id'] for p in game_state.players]
        if not player_id or player_id not in player_ids_list:
            player_id = "dev_player_1"
            session['player_id'] = player_id
            
        # Ensure the session player is "connected" in the dev game
        if player_id:
            player_data = next((p for p in game_state.players if p['id'] == player_id), None)
            if player_data:
                 player_data['connected'] = True

        # === NEW: AUTO-START THE GAME ===
        if len(game_state.players) == 6 and game_state.phase.value == 'waiting':
            try:
                game_state.start_game()
                print("DEBUG: Dev game auto-started successfully.")
            except ValueError as e:
                # This catches the error if you try to start without 6 players, but 
                # shouldn't happen here if player creation is correct.
                print(f"DEBUG: Error auto-starting dev game: {e}")
        # ================================

        # Render the template with the necessary dev variables
        return render_template(
            'index.html',
            game_state=game_state.get_game_state(player_id),
            current_player_id=player_id,
            developer_mode=DEVELOPER_MODE,
            all_player_ids=player_ids_list # Pass all player IDs for the switch dropdown
        )
    # === END DEVELOPER MODE PLAYER SETUP ===

    # Standard (Non-Dev) Mode
    return render_template('index.html')


@app.route('/api/create_game', methods=['POST'])
def create_game():
    """Create a new game and return the game code."""
    game_code = generate_game_code()
    active_games[game_code] = AduShertuGame(game_code)
    
    return jsonify({
        'success': True,
        'game_code': game_code
    })

@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connection."""
    print(f"Client connected: {request.sid}")
    emit('connected', {'session_id': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection."""
    print(f"Client disconnected: {request.sid}")
    
    # Remove player from game if they were in one
    if request.sid in player_connections:
        game_code, player_id = player_connections[request.sid]
        
        # In Developer Mode, players are not removed, just marked disconnected
        if game_code == DEV_GAME_CODE and DEVELOPER_MODE:
            game = active_games[game_code]
            player_data = next((p for p in game.players if p['id'] == player_id), None)
            if player_data:
                player_data['connected'] = False
        
        # Standard Game Logic
        elif game_code in active_games:
            game = active_games[game_code]
            # Find and mark player as disconnected
            for player in game.players:
                if player['id'] == player_id:
                    player['connected'] = False
            
            # Broadcast player disconnection
            socketio.emit('player_disconnected', {
                'player_id': player_id
            }, room=game_code)
        
        del player_connections[request.sid]


@socketio.on('join_game')
def handle_join_game(data):
    """Handle player joining a game."""
    game_code = data.get('game_code', '').upper()
    player_name = data.get('player_name', 'Anonymous')

    player_id = data.get('player_id')
    
    if game_code not in active_games:
        emit('error', {'message': 'Game not found'})
        return
    
    game = active_games[game_code]
    
    # DEV MODE LOGIC: If a player_id is provided, don't generate a new one
    if DEVELOPER_MODE and game_code == DEV_GAME_CODE and player_id:
        # Check if this dev_player exists
        if not any(p['id'] == player_id for p in game.players):
            emit('error', {'message': 'Dev player not found'})
            return
    else:
        # Standard Game Logic: Generate new ID
        player_id = f"player_{len(game.players)}_{request.sid[:6]}"
        success = game.add_player(player_id, player_name)
        if not success:
            emit('error', {'message': 'Game is full'})
            return
    
    # CRITICAL: Link the socket to the game code and player ID
    join_room(game_code)
    player_connections[request.sid] = (game_code, player_id)
    
    print(f"DEBUG: Linked SID {request.sid} to {player_id} in {game_code}")
    
    if game_code not in active_games:
        emit('error', {'message': 'Game not found'})
        return
    
    game = active_games[game_code]
    
    # Add player to game
    player_id = f"player_{len(game.players)}_{request.sid[:6]}"
    success = game.add_player(player_id, player_name)
    
    if not success:
        emit('error', {'message': 'Game is full'})
        return
    
    # Join the Socket.IO room
    join_room(game_code)
    
    # Store connection
    player_connections[request.sid] = (game_code, player_id)
    
    # Send success to joining player
    emit('join_success', {
        'player_id': player_id,
        'game_code': game_code,
        'game_state': game.get_game_state(player_id)
    })
    
    # Broadcast to all players in room
    socketio.emit('player_joined', {
        'player_name': player_name,
        'player_count': len(game.players),
        'game_state': game.get_game_state()
    }, room=game_code)

@socketio.on('start_game')
def handle_start_game(data):
    """Handle game start request."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    try:
        game.start_game()
        
        # Send personalized game state to each player
        for player in game.players:
            # Send to player's specific SID (for their hand data)
            socketio.emit('game_started', {
                'game_state': game.get_game_state(player['id'])
            }, room=player_connections.get(player['id'])) # Need a way to map player_id to SID
            # NOTE: The original code used room=request.sid which is only the host. 
            # This is a general improvement, but for dev mode it's less critical.
        
        # Broadcast general game state
        socketio.emit('game_state_update', {
            'game_state': game.get_game_state()
        }, room=game_code)
        
    except ValueError as e:
        emit('error', {'message': str(e)})

@socketio.on('call_trump')
def handle_call_trump(data):
    """Handle trump calling."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    # Find player index
    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    if player_index is None:
        emit('error', {'message': 'Player not found'})
        return
    
    suit_str = data.get('suit')
    suit = Suit(suit_str)
    
    result = game.attempt_trump_call(player_index, suit)
    
    if result['success']:
        # If it needs replacement, we tell the specific player
        if result.get('requires_replacement'):
            emit('card_replacement_required', result)
            # Broadcast a general update so others know a call happened but replacement is pending
            socketio.emit('game_state_update', {'game_state': game.get_game_state()}, room=game_code)
        else:
            # Standard success: Move everyone to Stage 1 Challenges
            socketio.emit('trump_called', {
                'player_index': player_index,
                'player_name': game.players[player_index]['name'],
                'trump_suit': result['trump_suit'],
                'game_state': game.get_game_state()
            }, room=game_code)
    else:
        emit('error', {'message': result.get('message', 'Failed to call trump')})

@socketio.on('call_joint')
def handle_call_joint(data):
    """Handle joint calling."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    if player_index is None:
        emit('error', {'message': 'Player not found'})
        return
    
    # NOTE: suits are no longer passed from client for joint call, game_state handles it
    result = game.attempt_joint_call(player_index) # CHANGE: Removed suit arguments
    
    if result['success']:
        socketio.emit('joint_called', {
            'player_index': player_index,
            'player_name': game.players[player_index]['name'],
            'current_okalu': result['current_okalu'],
            'game_state': game.get_game_state()
        }, room=game_code)
        
        # Send updated cards to joint caller (who needs to see 4 cards now)
        socketio.emit('cards_updated', {
            'game_state': game.get_game_state(player_id)
        }, room=request.sid)
    else:
        emit('error', {'message': result.get('message', 'Failed to call joint')})

@socketio.on('pass_trump')
def handle_pass_trump(data):
    """Handle passing on trump call."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    if player_index is None:
        emit('error', {'message': 'Player not found'})
        return
    
    result = game.pass_trump_call(player_index)
    
    if result['success']:
        if result.get('reshuffled'):
            # Cards were reshuffled, send new cards to all players
            for player in game.players:
                # NOTE: This broadcast needs to be fixed to target specific SIDs in a real game
                # For developer mode, a simple reload is often enough.
                # Keeping original structure for now.
                pass 
        
        socketio.emit('trump_passed', {
            'player_index': player_index,
            'next_player': result.get('next_player'),
            'game_state': game.get_game_state()
        }, room=game_code)
    else:
        emit('error', {'message': result.get('message', 'Failed to pass')})

@socketio.on('replace_card')
def handle_replace_card(data):
    """Handle card replacement for same-suit scenario."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    if player_index is None:
        emit('error', {'message': 'Player not found'})
        return
    
    suit = Suit(data.get('suit'))
    result = game.replace_same_suit_card(player_index, suit)
    
    if result['success']:
        # Broadcast the replacement visuals
        socketio.emit('card_replaced', result, room=game_code)
        
        # IMPORTANT: Broadcast the new game state so phase changes to STAGE1_CHALLENGING
        socketio.emit('game_state_update', {
            'game_state': game.get_game_state()
        }, room=game_code)
    else:
        emit('error', {'message': result.get('message', 'Failed to replace card')})

@socketio.on('challenge')
def handle_challenge(data):
    """Handle challenge calls (Adu, Shertu, Double, Shubble)."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    if player_index is None:
        emit('error', {'message': 'Player not found'})
        return
    
    challenge_word = data.get('challenge_word', '').lower()
    result = game.attempt_challenge(player_index, challenge_word)
    
    if result['success']:
        socketio.emit('challenge_issued', {
            'player_index': player_index,
            'player_name': game.players[player_index]['name'],
            'challenge_word': challenge_word,
            'current_okalu': result['current_okalu'],
            'awaiting_response': result.get('awaiting_response', False),
            'game_state': game.get_game_state()
        }, room=game_code)
    else:
        emit('error', {'message': result.get('message', 'Failed to challenge')})

@socketio.on('respond_challenge')
def handle_respond_challenge(data):
    """Handle response to challenge (accept/fold)."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    if player_index is None:
        emit('error', {'message': 'Player not found'})
        return
    
    team = game.players[player_index]['team']
    response = data.get('response')  # 'accept' or 'fold'
    
    result = game.respond_to_challenge(team, response)
    
    if result['success']:
        if result.get('folded'):
            socketio.emit('team_folded', {
                'team': team,
                'okalu_applied': result['okalu_applied'],
                'team_okalu': result['team_okalu'],
                'game_state': game.get_game_state()
            }, room=game_code)
        else:
            socketio.emit('challenge_accepted', {
                'team': team,
                'current_okalu': result['current_okalu'],
                'game_state': game.get_game_state()
            }, room=game_code)
    else:
        emit('error', {'message': result.get('message', 'Failed to respond')})

@socketio.on('proceed_stage2')
def handle_proceed_stage2(data):
    """Handle the consensus-based proceeding to stage 2."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    # toggle_ready_stage2 will return True only when the 6th player joins the list
    all_ready = game.toggle_ready_stage2(player_id)
    
    # Always broadcast the update so everyone sees the dots turn green
    socketio.emit('game_state_update', {
        'game_state': game.get_game_state()
    }, room=game_code)
    
    if all_ready:
        # We broadcast to the room that Stage 2 started
        # IMPORTANT: Since cards are private, we emit a general update 
        # but the client needs to know to refresh their specific hand.
        socketio.emit('stage2_started', {
            'game_state': game.get_game_state() 
        }, room=game_code)
    else:
        socketio.emit('game_state_update', {
            'game_state': game.get_game_state()
        }, room=game_code)
        
        # Log it for the dev console
        print(f"DEBUG: All players ready in {game_code}. Stage 2 started.")

@socketio.on('select_trump_joint')
def handle_select_trump_joint(data):
    """Handle trump selection after joint call."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    if player_index is None:
        emit('error', {'message': 'Player not found'})
        return
    
    suit = Suit(data.get('suit'))
    result = game.select_trump_after_joint(player_index, suit)
    
    if result['success']:
        socketio.emit('trump_selected_joint', {
            'player_index': player_index,
            'trump_suit': result['trump_suit'],
            'game_state': game.get_game_state()
        }, room=game_code)
    else:
        emit('error', {'message': result.get('message', 'Failed to select trump')})

@socketio.on('play_card')
def handle_play_card(data):
    """Handle playing a card."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    if player_index is None:
        emit('error', {'message': 'Player not found'})
        return
    
    card_index = data.get('card_index')
    result = game.play_card(player_index, card_index)
    
    if result['success']:
        # Update all players
        # NOTE: This section has a common anti-pattern (looping and using room=request.sid)
        # We broadcast to the game room, and let the clients update their specific view
        
        socketio.emit('card_played', {
            'player_index': player_index,
            'card': result.get('card_played'),
            'hand_complete': result.get('hand_complete', False),
            'winner': result.get('winner'),
            'winner_team': result.get('winner_team'),
            'hand_points': result.get('hand_points'),
            'points_scored': result.get('points_scored'),
            'game_over': result.get('game_over', False),
            'winning_team': result.get('winning_team'),
            # Game state specific to the player who played the card (for card removal)
            'game_state_my_view': game.get_game_state(player_id) 
        }, room=game_code) # Emit to the game room
        
    else:
        emit('error', {'message': result.get('message', 'Failed to play card')})

@socketio.on('request_game_state')
def handle_request_game_state(data):
    """Handle request for current game state."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    emit('game_state_update', {
        'game_state': game.get_game_state(player_id)
    })

# =========================================================================
# === DEVELOPER MODE ROUTES ===
# =========================================================================
if DEVELOPER_MODE:
    # Helper to get the single dev game instance
    def get_dev_game():
        return active_games[DEV_GAME_CODE]

    @app.route('/dev/status')
    def dev_status():
        """Returns the full current game state as JSON for debugging."""
        return jsonify(get_dev_game().get_game_state())

    @app.route('/dev/reset', methods=['POST'])
    def dev_reset():
        """Resets the global game state."""
        active_games[DEV_GAME_CODE] = AduShertuGame(DEV_GAME_CODE)
        
        # Re-run setup to regenerate players
        game_state = active_games[DEV_GAME_CODE]
        for i in range(1, 7):
            pid = f"dev_player_{i}"
            game_state.add_player(pid, f"Player {i}")
            
        # Broadcast reset event
        socketio.emit('game_state_update', {
            'game_state': game_state.get_game_state()
        }, room=DEV_GAME_CODE)

        return jsonify({'message': 'Game state reset successfully. Players regenerated.'})

    @app.route('/dev/switch_player/<new_player_id>')
    def dev_switch_player(new_player_id):
        game = get_dev_game()
        player_ids = [p['id'] for p in game.players]
        
        if new_player_id in player_ids:
            # Mark old player as disconnected
            old_player_id = session.get('player_id')
            if old_player_id:
                 old_player_data = next((p for p in game.players if p['id'] == old_player_id), None)
                 if old_player_data:
                     old_player_data['connected'] = False

            # Set new session ID and mark as connected
            session['player_id'] = new_player_id
            new_player_data = next((p for p in game.players if p['id'] == new_player_id), None)
            if new_player_data:
                new_player_data['connected'] = True
            
            # Broadcast update so all clients get the latest player connection status
            socketio.emit('game_state_update', {
                'game_state': game.get_game_state()
            }, room=DEV_GAME_CODE)
            
            return jsonify({'success': True, 'message': f'Switched to {new_player_id}'})
        return jsonify({'success': False, 'message': 'Invalid player ID.'}), 404
# =========================================================================
# === END DEVELOPER MODE ROUTES ===
# =========================================================================

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)