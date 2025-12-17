"""
app.py - Main Flask application with WebSocket support

This file handles:
- HTTP routes for serving the web interface
- WebSocket connections for real-time multiplayer
- Game room management
- Player connection/disconnection handling
- Broadcasting game state updates to all players
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import random
import string
from game_state import AduShertuGame, Suit, Rank
from typing import Dict

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Store active games: {game_code: AduShertuGame}
active_games: Dict[str, AduShertuGame] = {}

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
        if game_code in active_games:
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
            socketio.emit('game_started', {
                'game_state': game.get_game_state(player['id'])
            }, room=request.sid)
        
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
        # Broadcast trump called
        socketio.emit('trump_called', {
            'player_index': player_index,
            'player_name': game.players[player_index]['name'],
            'trump_suit': result['trump_suit'],
            'base_okalu': result['base_okalu'],
            'game_state': game.get_game_state()
        }, room=game_code)
    elif result.get('requires_replacement'):
        # Send replacement requirement to player
        emit('card_replacement_required', result)
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
    
    suit1 = Suit(data.get('suit1'))
    suit2 = Suit(data.get('suit2'))
    
    result = game.attempt_joint_call(player_index, suit1, suit2)
    
    if result['success']:
        socketio.emit('joint_called', {
            'player_index': player_index,
            'player_name': game.players[player_index]['name'],
            'current_okalu': result['current_okalu'],
            'game_state': game.get_game_state()
        }, room=game_code)
        
        # Send updated cards to joint caller
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
                socketio.emit('cards_updated', {
                    'game_state': game.get_game_state(player['id']),
                    'message': 'No trump called, new cards dealt'
                }, room=request.sid)
        
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
        # Broadcast card replacement to all
        socketio.emit('card_replaced', {
            'player_index': player_index,
            'discarded': result['discarded'],
            'replacements_shown': result['replacements_shown'],
            'final_card': result['final_card']
        }, room=game_code)
        
        # Send updated cards to player
        socketio.emit('cards_updated', {
            'game_state': game.get_game_state(player_id)
        }, room=request.sid)
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
    """Handle proceeding from stage 1 to stage 2."""
    if request.sid not in player_connections:
        emit('error', {'message': 'Not in a game'})
        return
    
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    result = game.proceed_to_stage2()
    
    if result['success']:
        # Send updated cards to all players
        for player in game.players:
            socketio.emit('stage2_started', {
                'game_state': game.get_game_state(player['id'])
            }, room=request.sid)
        
        socketio.emit('game_state_update', {
            'game_state': game.get_game_state()
        }, room=game_code)
    else:
        emit('error', {'message': result.get('message', 'Failed to proceed')})

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
        for player in game.players:
            socketio.emit('card_played', {
                'player_index': player_index,
                'card': result.get('card_played'),
                'game_state': game.get_game_state(player['id']),
                'hand_complete': result.get('hand_complete', False),
                'winner': result.get('winner'),
                'winner_team': result.get('winner_team'),
                'hand_points': result.get('hand_points'),
                'points_scored': result.get('points_scored'),
                'game_over': result.get('game_over', False),
                'winning_team': result.get('winning_team')
            }, room=request.sid)
        
        socketio.emit('game_state_update', {
            'game_state': game.get_game_state()
        }, room=game_code)
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

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)