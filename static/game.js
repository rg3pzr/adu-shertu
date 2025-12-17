/**
 * game.js - Client-side game logic and UI management
 */

// Initialize Socket.IO connection
const socket = io();

// Game state
let gameState = {
    myPlayerId: null,
    myTeam: null,
    gameCode: null,
    myCards: [],
    selectedCardIndex: null,
    game_state: null
};

// DOM Elements
const welcomeScreen = document.getElementById('welcome-screen');
const lobbyScreen = document.getElementById('lobby-screen');
const gameScreen = document.getElementById('game-screen');

const playerNameInput = document.getElementById('player-name');
const createGameBtn = document.getElementById('create-game-btn');
const joinGameBtn = document.getElementById('join-game-btn');
const joinGameForm = document.getElementById('join-game-form');
const gameCodeInput = document.getElementById('game-code-input');
const joinGameSubmit = document.getElementById('join-game-submit');

const gameCodeDisplay = document.getElementById('game-code');
const copyCodeBtn = document.getElementById('copy-code-btn');
const playerCountSpan = document.getElementById('player-count');
const playersList = document.getElementById('players-list');
const startGameBtn = document.getElementById('start-game-btn');

const statusMessages = document.getElementById('status-messages');

// Initialize event listeners
function init() {
    if(createGameBtn) createGameBtn.addEventListener('click', handleCreateGame);
    if(joinGameBtn) joinGameBtn.addEventListener('click', () => {
        joinGameForm.classList.toggle('hidden');
    });
    if(joinGameSubmit) joinGameSubmit.addEventListener('click', handleJoinGame);
    if(copyCodeBtn) copyCodeBtn.addEventListener('click', handleCopyCode);
    if(startGameBtn) startGameBtn.addEventListener('click', handleStartGame);
    
    // Socket event listeners
    socket.on('connected', handleConnected);
    socket.on('error', handleError);
    socket.on('join_success', handleJoinSuccess);
    socket.on('player_joined', handlePlayerJoined);
    socket.on('game_started', handleGameStarted);
    socket.on('game_state_update', handleGameStateUpdate); 
    socket.on('card_played', handleCardPlayed); 
    
    socket.on('trump_called', handleTrumpCalled);
    socket.on('joint_called', handleJointCalled);
    socket.on('trump_passed', handleTrumpPassed);
    socket.on('challenge_issued', handleChallengeIssued);
    socket.on('challenge_accepted', handleChallengeAccepted);
    socket.on('team_folded', handleTeamFolded);
    
    socket.on('cards_updated', handleCardsUpdated);
    socket.on('card_replacement_required', handleCardReplacementRequired);
    socket.on('card_replaced', handleCardReplaced);
    socket.on('stage2_started', handleStage2Started);
    socket.on('trump_selected_joint', handleTrumpSelectedJoint);
    
    // Trump calling action buttons
    document.querySelectorAll('.btn-suit').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const suit = e.target.dataset.suit;
            handleTrumpSuitSelection(suit);
        });
    });
    
    document.getElementById('pass-trump-btn').addEventListener('click', handlePassTrump);
    document.getElementById('call-joint-btn').addEventListener('click', handleCallJoint);
    
    // Challenge buttons
    document.getElementById('adu-btn').addEventListener('click', () => handleChallenge('adu'));
    document.getElementById('shertu-btn').addEventListener('click', () => handleChallenge('shertu'));
    document.getElementById('double-btn').addEventListener('click', () => handleChallenge('double'));
    document.getElementById('shubble-btn').addEventListener('click', () => handleChallenge('shubble'));
    
    // Challenge response buttons
    document.getElementById('accept-challenge-btn').addEventListener('click', () => handleChallengeResponse('accept'));
    document.getElementById('fold-btn').addEventListener('click', () => handleChallengeResponse('fold'));
    
    // Proceed to stage 2
    document.getElementById('proceed-stage2-btn').addEventListener('click', handleProceedStage2);
    
    // New game button
    document.getElementById('new-game-btn').addEventListener('click', () => {
        location.reload();
    });
}

// Socket event handlers
function handleConnected(data) {
    console.log('Connected to server:', data.session_id);
}

function handleError(data) {
    showStatus(data.message, 'error');
}

function handleJoinSuccess(data) {
    gameState.myPlayerId = data.player_id;
    gameState.gameCode = data.game_code;
    gameState.myTeam = data.game_state.my_team;
    gameState.myCards = data.game_state.my_cards || [];
    gameCodeDisplay.textContent = data.game_code;
    showScreen('lobby');
    updatePlayersList(data.game_state.players);
    showStatus('Joined game successfully!', 'success');
}

function handlePlayerJoined(data) {
    updatePlayersList(data.game_state.players);
    playerCountSpan.textContent = data.player_count;
    if (data.player_count === 6) {
        startGameBtn.disabled = false;
    }
}

function handleGameStarted(data) {
    gameState.myCards = data.game_state.my_cards || [];
    showScreen('game');
    updateGameState(data.game_state);
    renderMyCards();
    showStatus('Game started!', 'success');
}

function handleGameStateUpdate(data) {
    updateGameState(data.game_state);
}

function handleTrumpCalled(data) {
    showStatus(`${data.player_name} called trump: ${data.trump_suit}`, 'success');
    updateGameState(data.game_state);
}

function handleJointCalled(data) {
    showStatus(`${data.player_name} called JOINT!`, 'success');
    updateGameState(data.game_state);
}

function handleTrumpPassed(data) {
    updateGameState(data.game_state);
}

function handleChallengeIssued(data) {
    showStatus(`${data.player_name} called ${data.challenge_word.toUpperCase()}!`, 'warning');
    updateGameState(data.game_state);
}

function handleChallengeAccepted(data) {
    showStatus('Challenge accepted!', 'success');
    updateGameState(data.game_state);
}

function handleTeamFolded(data) {
    showStatus(`Team folded!`, 'warning');
    updateGameState(data.game_state);
    setTimeout(() => {
        showGameOverModal({ message: "Team folded", okalu_change: data.okalu_applied });
    }, 2000);
}

function handleCardPlayed(data) {
    if (data.game_state_my_view) {
        gameState.myCards = data.game_state_my_view.my_cards || [];
        renderMyCards();
    }
    updateGameState(data.game_state);
    renderPlayedCards(data.game_state.current_hand_cards);
    
    if (data.hand_complete) {
        if (data.game_over) {
            setTimeout(() => {
                showGameOverModal({
                    winning_team: data.winning_team,
                    final_points: data.points_scored,
                    okalu_change: data.game_state.current_game_okalu
                });
            }, 2000);
        } else {
            setTimeout(() => { renderPlayedCards([]); }, 2000);
        }
    }
}

function handleCardsUpdated(data) {
    gameState.myCards = data.game_state.my_cards || [];
    renderMyCards();
    updateGameState(data.game_state);
}

function handleCardReplacementRequired(data) {
    socket.emit('replace_card', { suit: data.card_to_replace.suit });
}

function handleCardReplaced(data) {
    showStatus('Card replaced', 'success');
}

function handleStage2Started(data) {
    gameState.myCards = data.game_state.my_cards || [];
    renderMyCards();
    updateGameState(data.game_state);
}

function handleTrumpSelectedJoint(data) {
    updateGameState(data.game_state);
}

// UI Actions
async function handleCreateGame() {
    if (document.getElementById('developer-mode-info')) {
        showScreen('lobby');
        return;
    }
    const playerName = playerNameInput.value.trim();
    if (!playerName) return;
    try {
        const response = await fetch('/api/create_game', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            socket.emit('join_game', { game_code: data.game_code, player_name: playerName });
        }
    } catch (error) { console.error(error); }
}

function handleJoinGame() {
    const playerName = playerNameInput.value.trim();
    const gameCode = gameCodeInput.value.trim().toUpperCase();
    if (!playerName || !gameCode) return;
    socket.emit('join_game', { game_code: gameCode, player_name: playerName });
}

function handleCopyCode() {
    navigator.clipboard.writeText(gameCodeDisplay.textContent);
    showStatus('Copied!', 'success');
}

function handleStartGame() {
    socket.emit('start_game', {});
}

function handleTrumpSuitSelection(suit) {
    const phase = gameState.game_state.phase;
    if (phase === 'stage1_trump_calling') socket.emit('call_trump', { suit });
    else if (phase === 'stage2_trump_selection') socket.emit('select_trump_joint', { suit });
}

function handlePassTrump() { socket.emit('pass_trump', {}); }
function handleCallJoint() { socket.emit('call_joint', {}); }
function handleChallenge(word) { socket.emit('challenge', { challenge_word: word }); }
function handleChallengeResponse(res) { socket.emit('respond_challenge', { response: res }); }
function handleProceedStage2() { socket.emit('proceed_stage2', {}); }

function handleCardClick(index) {
    if (gameState.selectedCardIndex === index) {
        socket.emit('play_card', { card_index: index });
        gameState.selectedCardIndex = null;
    } else {
        gameState.selectedCardIndex = index;
        renderMyCards();
    }
}

// UI Updates
function showScreen(name) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(name + '-screen').classList.add('active');
}

function updatePlayersList(players) {
    playersList.innerHTML = '';
    players.forEach(p => {
        const div = document.createElement('div');
        div.className = `player-card team-${p.team} ${p.connected ? '' : 'disconnected'}`;
        div.innerHTML = `<div class="player-name">${p.name}</div>`;
        playersList.appendChild(div);
    });
    playerCountSpan.textContent = players.length;
}

function updateGameState(state) {
    gameState.game_state = state;
    document.getElementById('team-0-okalu').textContent = state.team_okalu[0];
    document.getElementById('team-1-okalu').textContent = state.team_okalu[1];
    document.getElementById('current-okalu').textContent = state.current_game_okalu;
    
    const trumpEl = document.getElementById('trump-suit');
    if (state.trump_suit) {
        trumpEl.innerHTML = `<span class="${getSuitClass(state.trump_suit)}">${state.trump_suit}</span>`;
    } else { trumpEl.textContent = '?'; }

    document.getElementById('game-phase').textContent = getPhaseText(state.phase);
    document.getElementById('team-0-score').textContent = state.points_scored[0];
    document.getElementById('team-1-score').textContent = state.points_scored[1];
    document.getElementById('current-hand').textContent = state.current_hand_number + 1;

    state.players.forEach((p, i) => {
        const el = document.getElementById(`player-${i}`);
        if (el) {
            el.querySelector('.player-name').textContent = p.name;
            el.querySelector('.card-count').textContent = p.card_count;
            el.classList.toggle('active', i === state.current_player_index);
            el.classList.toggle('dealer', i === state.dealer_index);
            if (p.id !== gameState.myPlayerId && p.cards) renderOpponentHandDev(p.id, p.cards);
        }
    });
    updateActionPanels(state);
    if (state.current_hand_cards) renderPlayedCards(state.current_hand_cards);
}

function getPhaseText(phase) {
    const phases = {
        'waiting': 'Waiting...', 'stage1_trump_calling': 'Calling trump...',
        'stage1_challenging': 'Stage 1 Challenges', 'playing_hand': 'Playing...',
        'stage2_trump_selection': 'Select Trump (Joint)'
    };
    return phases[phase] || phase;
}

function updateActionPanels(state) {
    document.querySelectorAll('.action-group').forEach(g => g.classList.add('hidden'));
    const myIdx = state.players.findIndex(p => p.id === gameState.myPlayerId);
    
    if (state.phase === 'stage1_trump_calling' && myIdx === state.trump_calling_index) {
        document.getElementById('trump-calling-actions').classList.remove('hidden');

        // === JOINT VISIBILITY LOGIC ===
        const jointBtn = document.getElementById('call-joint-btn');
        if (jointBtn) {
            // Count how many 9s are in the current hand
            const nineCount = gameState.myCards.filter(card => card.rank === '9').length;
            
            if (nineCount >= 2) {
                jointBtn.classList.remove('hidden');
                jointBtn.style.display = "inline-block"; // Ensure it's not hidden by other CSS
            } else {
                jointBtn.classList.add('hidden');
                jointBtn.style.display = "none";
            }
        }
        // ==============================
    }
    if (state.phase === 'stage1_challenging') {
        document.getElementById('challenge-actions').classList.remove('hidden');
        document.getElementById('proceed-stage2-btn').classList.remove('hidden');
    }
    if (state.phase === 'stage2_trump_selection' && myIdx === state.joint_caller_index) {
        document.getElementById('joint-trump-selection').classList.remove('hidden');
        renderJointSuitButtons();
    }
    if (state.pending_challenge && gameState.myTeam !== state.last_challenger_team) {
        document.getElementById('challenge-response-actions').classList.remove('hidden');
    }
}

function renderJointSuitButtons() {
    const container = document.getElementById('joint-suit-buttons');
    container.innerHTML = '';
    const nines = gameState.myCards.filter(c => c.rank === '9');
    nines.forEach(c => {
        const btn = document.createElement('button');
        btn.className = `btn-suit ${getSuitClass(c.suit)}`;
        btn.textContent = c.suit;
        btn.onclick = () => handleTrumpSuitSelection(c.suit);
        container.appendChild(btn);
    });
}

function renderMyCards() {
    const container = document.getElementById('your-cards');
    if (!container) return;
    container.innerHTML = '';
    const suitMap = {'♥':'H','♦':'D','♣':'C','♠':'S','\u2665':'H','\u2666':'D','\u2663':'C','\u2660':'S'};

    gameState.myCards.forEach((card, index) => {
        const cardEl = document.createElement('div');
        const suitClass = getSuitClass(card.suit);
        cardEl.className = `card ${suitClass} ${index === gameState.selectedCardIndex ? 'selected' : ''}`;
        cardEl.innerHTML = `
            <div class="card-rank">${card.rank}</div>
            <div class="card-suit">${suitMap[card.suit] || card.suit}</div>
            <div class="card-rank">${card.rank}</div>
        `;
        cardEl.onclick = () => handleCardClick(index);
        container.appendChild(cardEl);
    });
}

function renderPlayedCards(cards) {
    const container = document.getElementById('played-cards');
    container.innerHTML = '';
    cards.forEach(([pIdx, card]) => {
        const div = document.createElement('div');
        div.className = `played-card ${getSuitClass(card.suit)}`;
        div.innerHTML = `<div class="card-rank">${card.rank}</div><div class="card-suit">${card.suit}</div>`;
        container.appendChild(div);
    });
}

function getSuitClass(suit) {
    const map = {'♥':'hearts','♦':'diamonds','♣':'clubs','♠':'spades','\u2665':'hearts','\u2666':'diamonds','\u2663':'clubs','\u2660':'spades'};
    return map[suit] || '';
}

function showStatus(msg, type) {
    const div = document.createElement('div');
    div.className = `status-message ${type}`;
    div.textContent = msg;
    statusMessages.appendChild(div);
    setTimeout(() => div.remove(), 5000);
}

function showGameOverModal(data) {
    document.getElementById('game-over-modal').classList.remove('hidden');
    document.getElementById('game-over-content').innerHTML = data.message || `Team ${data.winning_team + 1} Wins!`;
}

// Dev Mode
function resetGameDev() { if (confirm("Reset?")) fetch('/dev/reset', { method: 'POST' }).then(() => location.reload()); }
function switchPlayerDev(id) { fetch(`/dev/switch_player/${id}`).then(() => location.reload()); }

function renderOpponentHandDev(pid, cards) {
    const idx = gameState.game_state.players.findIndex(p => p.id === pid);
    const el = document.getElementById(`player-${idx}`);
    if (!el) return;
    let hand = el.querySelector('.opponent-hand') || document.createElement('div');
    hand.className = 'opponent-hand';
    el.appendChild(hand);
    hand.innerHTML = cards.map(c => `<div class="small-card ${getSuitClass(c.suit)}">${c.rank}</div>`).join('');
}

document.addEventListener('DOMContentLoaded', init);