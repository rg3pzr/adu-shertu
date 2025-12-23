"""
app.py - Main Flask application with WebSocket support
"""

from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import random
import string
from game_state import AduShertuGame, Suit, Rank
from typing import Dict
import os

DEVELOPER_MODE = os.environ.get('DEVELOPER_MODE', 'False').lower() in ('true', '1', 't')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

active_games: Dict[str, AduShertuGame] = {}
DEV_GAME_CODE = "DEVGAME"
if DEVELOPER_MODE and DEV_GAME_CODE not in active_games:
    active_games[DEV_GAME_CODE] = AduShertuGame(DEV_GAME_CODE, is_dev_game=True)

player_connections: Dict[str, tuple] = {}

def generate_game_code() -> str:
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in active_games:
            return code

@app.route('/')
def index():
    if DEVELOPER_MODE:
        game_state = active_games[DEV_GAME_CODE]
        player_id = session.get('player_id')

        if len(game_state.players) < 6:
            for i in range(1, 7):
                pid = f"dev_player_{i}"
                game_state.add_player(pid, f"Player {i}")

        player_ids_list = [p['id'] for p in game_state.players]
        if not player_id or player_id not in player_ids_list:
            player_id = "dev_player_1"
            session['player_id'] = player_id
            
        if player_id:
            player_data = next((p for p in game_state.players if p['id'] == player_id), None)
            if player_data:
                 player_data['connected'] = True

        if len(game_state.players) == 6 and game_state.phase.value == 'waiting':
            try:
                game_state.start_game()
            except ValueError as e:
                print(f"DEBUG: Error auto-starting dev game: {e}")

        return render_template(
            'index.html',
            game_state=game_state.get_game_state(player_id),
            current_player_id=player_id,
            developer_mode=DEVELOPER_MODE,
            all_player_ids=player_ids_list
        )
    return render_template('index.html')

@app.route('/api/create_game', methods=['POST'])
def create_game():
    game_code = generate_game_code()
    active_games[game_code] = AduShertuGame(game_code)
    return jsonify({'success': True, 'game_code': game_code})

@socketio.on('connect')
def handle_connect():
    emit('connected', {'session_id': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in player_connections:
        game_code, player_id = player_connections[request.sid]
        if game_code == DEV_GAME_CODE and DEVELOPER_MODE:
            game = active_games[game_code]
            player_data = next((p for p in game.players if p['id'] == player_id), None)
            if player_data:
                player_data['connected'] = False
        elif game_code in active_games:
            game = active_games[game_code]
            for player in game.players:
                if player['id'] == player_id:
                    player['connected'] = False
            socketio.emit('player_disconnected', {'player_id': player_id}, room=game_code)
        del player_connections[request.sid]

@socketio.on('join_game')
def handle_join_game(data):
    game_code = data.get('game_code', '').upper()
    player_name = data.get('player_name', 'Anonymous')
    player_id = data.get('player_id')
    
    if game_code not in active_games:
        emit('error', {'message': 'Game not found'})
        return
    
    game = active_games[game_code]
    
    if not (DEVELOPER_MODE and game_code == DEV_GAME_CODE and player_id):
        player_id = f"player_{len(game.players)}_{request.sid[:6]}"
        if not game.add_player(player_id, player_name):
            emit('error', {'message': 'Game is full'})
            return
    
    join_room(game_code)
    player_connections[request.sid] = (game_code, player_id)
    
    emit('join_success', {
        'player_id': player_id,
        'game_code': game_code,
        'game_state': game.get_game_state(player_id)
    })
    
    socketio.emit('player_joined', {
        'player_name': player_name,
        'player_count': len(game.players),
        'game_state': game.get_game_state()
    }, room=game_code)

@socketio.on('start_game')
def handle_start_game(data):
    if request.sid not in player_connections: return
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    try:
        game.start_game()
        socketio.emit('game_started', {'game_state': game.get_game_state()}, room=game_code)
        socketio.emit('game_state_update', {'game_state': game.get_game_state()}, room=game_code)
    except ValueError as e:
        emit('error', {'message': str(e)})

@socketio.on('call_trump')
def handle_call_trump(data):
    if request.sid not in player_connections: return
    game_code, player_id = player_connections[request.sid]
    game = active_games.get(game_code)
    if not game: return

    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    if player_index is None: return

    suit_str = data.get('suit')
    try:
        suit = Suit(suit_str)
    except ValueError:
        emit('error', {'message': 'Invalid suit'})
        return

    result = game.attempt_trump_call(player_index, suit)
    
    if result.get('requires_card_choice'):
        emit('trump_choice_required', result)
    elif result['success']:
        socketio.emit('trump_called', {
            'player_index': player_index,
            'player_name': game.players[player_index]['name'],
            'trump_suit': result.get('trump_suit'),
            'game_state': game.get_game_state()
        }, room=game_code)
    else:
        emit('error', {'message': result.get('message', 'Failed to call trump')})

@socketio.on('finalize_trump_selection')
def handle_finalize_trump_selection(data):
    if request.sid not in player_connections: return
    game_code, player_id = player_connections[request.sid]
    game = active_games.get(game_code)
    if not game: return

    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    
    result = game.finalize_trump_call_selection(player_index, data['suit'], data['calling_card'])
    
    if result['success']:
        socketio.emit('card_replaced', result, room=game_code)
        socketio.emit('game_state_update', {'game_state': game.get_game_state()}, room=game_code)
    else:
        emit('error', {'message': result.get('message', 'Choice failed')})

@socketio.on('call_joint')
def handle_call_joint(data):
    if request.sid not in player_connections: return
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    
    result = game.attempt_joint_call(player_index)
    
    if result['success']:
        socketio.emit('joint_called', {
            'player_index': player_index,
            'player_name': game.players[player_index]['name'],
            'current_okalu': result['current_okalu'],
            'game_state': game.get_game_state()
        }, room=game_code)
    else:
        emit('error', {'message': result.get('message', 'Failed joint call')})

@socketio.on('pass_trump')
def handle_pass_trump(data):
    if request.sid not in player_connections: return
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    
    result = game.pass_trump_call(player_index)
    if result['success']:
        socketio.emit('trump_passed', {
            'player_index': player_index,
            'next_player': result.get('next_player'),
            'game_state': game.get_game_state()
        }, room=game_code)

@socketio.on('proceed_stage2')
def handle_proceed_stage2(data):
    if request.sid not in player_connections: return
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    
    all_ready = game.toggle_ready_stage2(player_id)
    
    if all_ready:
        socketio.emit('stage2_started', {'game_state': game.get_game_state()}, room=game_code)
    else:
        socketio.emit('game_state_update', {'game_state': game.get_game_state()}, room=game_code)

@socketio.on('play_card')
def handle_play_card(data):
    if request.sid not in player_connections: return
    game_code, player_id = player_connections[request.sid]
    game = active_games[game_code]
    player_index = next((i for i, p in enumerate(game.players) if p['id'] == player_id), None)
    
    result = game.play_card(player_index, data.get('card_index'))
    if result['success']:
        socketio.emit('card_played', {
            'player_index': player_index,
            'card': result.get('card_played'),
            'hand_complete': result.get('hand_complete', False),
            'game_state': game.get_game_state()
        }, room=game_code)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)