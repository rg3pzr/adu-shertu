/**
 * game.js - Client-side game logic and UI management
 * * Handles:
 * - WebSocket connection and event handling
 * - UI updates and screen transitions
 * - Player actions and card interactions
 * - Game state synchronization
 */

// Initialize Socket.IO connection
const socket = io();

// Game state
let gameState = {
    myPlayerId: null,
    myTeam: null,
    gameCode: null,
    myCards: [],
    selectedCardIndex: null
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
    createGameBtn.addEventListener('click', handleCreateGame);
    joinGameBtn.addEventListener('click', () => {
        joinGameForm.classList.toggle('hidden');
    });
    joinGameSubmit.addEventListener('click', handleJoinGame);
    copyCodeBtn.addEventListener('click', handleCopyCode);
    startGameBtn.addEventListener('click', handleStartGame);
    
    // Socket event listeners
    socket.on('connected', handleConnected);
    socket.on('error', handleError);
    socket.on('join_success', handleJoinSuccess);
    socket.on('player_joined', handlePlayerJoined);
    socket.on('game_started', handleGameStarted);
    // The server now emits 'game_state_update' for generic updates
    socket.on('game_state_update', handleGameStateUpdate); 
    // The server now sends specific player hand updates via 'card_played' payload
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
    // NOTE: 'hand_complete' is now integrated into the 'card_played' handler
    
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
        document.querySelector('.info-text').textContent = 'Ready to start!';
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
    showStatus(`${data.player_name} called JOINT! Okalu doubled.`, 'success');
    // NOTE: The game state update here will show the phase change.
    updateGameState(data.game_state);
}

function handleTrumpPassed(data) {
    updateGameState(data.game_state);
}

function handleChallengeIssued(data) {
    showStatus(`${data.player_name} called ${data.challenge_word.toUpperCase()}! Okalu: ${data.current_okalu}`, 'warning');
    updateGameState(data.game_state);
    
    if (data.awaiting_response) {
        // Show challenge response options if on opposing team
        const myTeam = gameState.myTeam;
        const challengerTeam = data.game_state.last_challenger_team;
        if (myTeam !== challengerTeam) {
            showChallengeResponseActions();
        }
    }
}

function handleChallengeAccepted(data) {
    showStatus('Challenge accepted!', 'success');
    hideChallengeResponseActions();
    updateGameState(data.game_state);
}

function handleTeamFolded(data) {
    showStatus(`Team ${data.team + 1} folded! Okalu applied: ${data.okalu_applied}`, 'warning');
    updateGameState(data.game_state);
    
    // Show new game button or return to lobby
    setTimeout(() => {
        showGameOverModal({
            message: `Team ${data.team + 1} folded`,
            okalu_change: data.okalu_applied
        });
    }, 2000);
}

function handleCardPlayed(data) {
    // Check if this player is the one who played the card, and update their hand immediately
    if (data.game_state_my_view) { // New data key added in app.py
        gameState.myCards = data.game_state_my_view.my_cards || [];
        renderMyCards();
    }
    
    // Update general game state for all players
    updateGameState(data.game_state);
    renderPlayedCards(data.game_state.current_hand_cards);
    
    if (data.hand_complete) {
        showStatus(`Hand won by ${data.game_state.players[data.winner].name}! Points: ${data.hand_points}`, 'success');
        
        if (data.game_over) {
            setTimeout(() => {
                showGameOverModal({
                    winning_team: data.winning_team,
                    final_points: data.points_scored,
                    okalu_change: data.game_state.current_game_okalu
                });
            }, 2000);
        } else {
            // Clear played cards after a delay
            setTimeout(() => {
                renderPlayedCards([]);
            }, 2000);
        }
    }
}

function handleCardsUpdated(data) {
    gameState.myCards = data.game_state.my_cards || [];
    renderMyCards();
    updateGameState(data.game_state);
}

function handleCardReplacementRequired(data) {
    showStatus('Your other card is the same suit! It will be replaced.', 'warning');
    // Auto-replace the card
    const suit = data.card_to_replace.suit;
    socket.emit('replace_card', { suit });
}

function handleCardReplaced(data) {
    showStatus('Card replaced and shown to all players', 'success');
}

function handleStage2Started(data) {
    gameState.myCards = data.game_state.my_cards || [];
    renderMyCards();
    updateGameState(data.game_state);
    showStatus('Stage 2: All cards dealt!', 'success');
}

function handleTrumpSelectedJoint(data) {
    showStatus(`Trump selected: ${data.trump_suit}`, 'success');
    updateGameState(data.game_state);
}

// UI Action handlers
async function handleCreateGame() {
    const playerName = playerNameInput.value.trim();
    // In Developer Mode, ignore player name input on the index page
    if (document.getElementById('developer-mode-info')) {
        showScreen('lobby');
        // No server request needed in dev mode, app.py sets up the initial state.
        return;
    }

    if (!playerName) {
        showStatus('Please enter your name', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/create_game', {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            // Join the game we just created
            socket.emit('join_game', {
                game_code: data.game_code,
                player_name: playerName
            });
        }
    } catch (error) {
        showStatus('Failed to create game', 'error');
    }
}

function handleJoinGame() {
    const playerName = playerNameInput.value.trim();
    const gameCode = gameCodeInput.value.trim().toUpperCase();
    
    if (!playerName) {
        showStatus('Please enter your name', 'error');
        return;
    }
    
    if (!gameCode || gameCode.length !== 6) {
        showStatus('Please enter a valid 6-character game code', 'error');
        return;
    }
    
    socket.emit('join_game', {
        game_code: gameCode,
        player_name: playerName
    });
}

function handleCopyCode() {
    const code = gameCodeDisplay.textContent;
    navigator.clipboard.writeText(code).then(() => {
        showStatus('Game code copied!', 'success');
    });
}

function handleStartGame() {
    socket.emit('start_game', {});
}

function handleTrumpSuitSelection(suit) {
    const currentPhase = gameState.game_state.phase;
    
    if (currentPhase === 'stage1_trump_calling') {
        // Regular trump calling
        socket.emit('call_trump', { suit });
    } else if (currentPhase === 'stage2_trump_selection') {
        // Joint trump selection (new phase)
        socket.emit('select_trump_joint', { suit });
    } else {
        showStatus('Cannot select trump at this time.', 'error');
    }
}

function handlePassTrump() {
    socket.emit('pass_trump', {});
}

function handleCallJoint() {
    // The server (game_state.py) now handles checking for the two 9s, so we send an empty data object.
    
    if (gameState.game_state.phase !== 'stage1_trump_calling') {
        showStatus('Joint can only be called during the trump calling phase.', 'error');
        return;
    }
    
    socket.emit('call_joint', {}); // MODIFIED: No suits passed
}

function handleChallenge(challengeWord) {
    socket.emit('challenge', { challenge_word: challengeWord });
}

function handleChallengeResponse(response) {
    socket.emit('respond_challenge', { response });
}

function handleProceedStage2() {
    socket.emit('proceed_stage2', {});
}

function handleCardClick(cardIndex) {
    if (gameState.selectedCardIndex === cardIndex) {
        // Play the card
        socket.emit('play_card', { card_index: cardIndex });
        gameState.selectedCardIndex = null;
    } else {
        // Select the card
        gameState.selectedCardIndex = cardIndex;
        renderMyCards();
    }
}

// UI Update functions
function showScreen(screenName) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    
    const screens = {
        'welcome': welcomeScreen,
        'lobby': lobbyScreen,
        'game': gameScreen
    };
    
    screens[screenName]?.classList.add('active');
}

function updatePlayersList(players) {
    playersList.innerHTML = '';
    
    players.forEach(player => {
        const playerCard = document.createElement('div');
        // Check for connection status (useful in dev mode)
        const connectionStatus = player.connected === false ? 'disconnected' : 'connected';
        playerCard.className = `player-card team-${player.team} ${connectionStatus}`;

        playerCard.innerHTML = `
            <div class="player-name">${player.name}</div>
            <div class="team-badge">Team ${player.team + 1}</div>
        `;
        playersList.appendChild(playerCard);
    });
    
    playerCountSpan.textContent = players.length;
}

function updateGameState(state) {
    // Store the full state globally for easy access
    gameState.game_state = state;

    // Update okalu display
    document.getElementById('team-0-okalu').textContent = state.team_okalu[0];
    document.getElementById('team-1-okalu').textContent = state.team_okalu[1];
    document.getElementById('current-okalu').textContent = state.current_game_okalu;
    
    // Update trump display
    const trumpSuit = document.getElementById('trump-suit');
    if (state.trump_suit) {
        // Render icon
        trumpSuit.innerHTML = `<span class="${getSuitClass(state.trump_suit)}">${state.trump_suit}</span>`;
    } else {
        trumpSuit.textContent = '?';
    }
    
    // Update phase
    document.getElementById('game-phase').textContent = getPhaseText(state.phase);
    
    // Update scores
    if (state.points_scored) {
        document.getElementById('team-0-score').textContent = state.points_scored[0];
        document.getElementById('team-1-score').textContent = state.points_scored[1];
    }
    
    // Update current hand number
    document.getElementById('current-hand').textContent = state.current_hand_number + 1;
    
    // Update player displays
    state.players.forEach((player, index) => {
        const playerEl = document.getElementById(`player-${index}`);
        if (playerEl) {
            const nameEl = playerEl.querySelector('.player-name');
            const cardCountEl = playerEl.querySelector('.card-count');
            
            if (nameEl) nameEl.textContent = player.name;
            if (cardCountEl) cardCountEl.textContent = player.card_count;
            
            // Highlight current player
            if (index === state.current_player_index) {
                playerEl.classList.add('active');
            } else {
                playerEl.classList.remove('active');
            }
            
            // Mark dealer
            if (index === state.dealer_index) {
                playerEl.classList.add('dealer');
            } else {
                playerEl.classList.remove('dealer');
            }
            // === NEW DEV MODE HAND DISPLAY LOGIC ===
            if (player.id !== gameState.myPlayerId && player.cards && player.cards.length > 0) {
                renderOpponentHandDev(player.id, player.cards);
            }
            // =======================================
        }
    });
    
    // Show/hide action panels based on phase and turn
    updateActionPanels(state);
    
    // Render played cards
    if (state.current_hand_cards) {
        renderPlayedCards(state.current_hand_cards);
    }
}

function getPhaseText(phase) {
    const phases = {
        'waiting': 'Waiting for players...',
        'stage1_dealing': 'Dealing cards...',
        'stage1_trump_calling': 'Calling trump...',
        'stage1_joint_pending': 'Joint called, dealing stage 2...', // NEW PHASE
        'stage1_challenging': 'Stage 1 challenges',
        'stage2_dealing': 'Dealing remaining cards...',
        'stage2_trump_selection': 'Joint caller selects trump...', // NEW PHASE
        'stage2_challenging': 'Stage 2 - Play or challenge',
        'playing_hand': 'Playing hand',
        'game_over': 'Game over'
    };
    
    return phases[phase] || phase;
}

function updateActionPanels(state) {
    // Hide all action groups first
    document.querySelectorAll('.action-group').forEach(group => {
        group.classList.add('hidden');
    });
    
    // Get my player index
    const myIndex = state.players.findIndex(p => p.id === gameState.myPlayerId);
    const isMyTurnForTrump = myIndex === state.trump_calling_index;
    const isMyTurnToPlay = myIndex === state.current_player_index;
    const isJointCaller = myIndex === state.joint_caller_index;
    
    // 1. Regular Trump Calling
    if (state.phase === 'stage1_trump_calling' && isMyTurnForTrump) {
        document.getElementById('trump-calling-actions').classList.remove('hidden');
    }
    
    // 2. Stage 1 Challenges
    if (state.phase === 'stage1_challenging') {
        document.getElementById('challenge-actions').classList.remove('hidden');
        document.getElementById('proceed-stage2-btn').classList.remove('hidden');
    }
    
    // 3. Joint Trump Selection (NEW)
    if (state.phase === 'stage2_trump_selection' && isJointCaller) {
        document.getElementById('joint-trump-selection').classList.remove('hidden');
        
        // Populate joint suit buttons with the two 9 suits
        const nines = gameState.myCards.filter(c => c.rank === '9');
        const jointButtons = document.getElementById('joint-suit-buttons');
        
        // Remove existing buttons before populating
        jointButtons.innerHTML = ''; 
        
        nines.forEach(card => {
            const btn = document.createElement('button');
            btn.className = `btn-suit ${getSuitClass(card.suit)}`;
            btn.dataset.suit = card.suit;
            btn.textContent = card.suit;
            
            // Add event listener to the dynamically created buttons
            btn.addEventListener('click', (e) => {
                const suit = e.target.dataset.suit;
                handleTrumpSuitSelection(suit);
            });
            
            jointButtons.appendChild(btn);
        });
    }

    // 4. Stage 2 Challenges / Playing
    if (state.phase === 'stage2_challenging' || state.phase === 'playing_hand') {
        if (!state.pending_challenge) {
            document.getElementById('challenge-actions').classList.remove('hidden');
            // The logic to play a card is handled in handleCardClick, which relies on isMyTurnToPlay
        }
        document.getElementById('proceed-stage2-btn').classList.add('hidden'); // Hide after Stage 1
    }

    // 5. Challenge Response
    if (state.pending_challenge && gameState.myTeam !== state.last_challenger_team) {
        showChallengeResponseActions();
    } else {
        hideChallengeResponseActions();
    }
}

function showChallengeResponseActions() {
    document.getElementById('challenge-response-actions').classList.remove('hidden');
}

function hideChallengeResponseActions() {
    document.getElementById('challenge-response-actions').classList.add('hidden');
}

function renderMyCards() {
    const container = document.getElementById('your-cards');
    container.innerHTML = '';
    
    gameState.myCards.forEach((card, index) => {
        const cardEl = document.createElement('div');
        // MODIFIED: Use the suit symbol directly for the card icon display
        const suitClass = getSuitClass(card.suit);
        
        cardEl.className = `card ${suitClass}`;
        
        if (index === gameState.selectedCardIndex) {
            cardEl.classList.add('selected');
        }
        
        // MODIFIED: Use Unicode symbols (♥, ♦, ♣, ♠) for visual cards
        const suitSymbol = card.suit;
        
        cardEl.innerHTML = `
            <div class="card-rank">${card.rank}</div>
            <div class="card-suit ${suitClass}">${suitSymbol}</div>
            <div class="card-rank">${card.rank}</div>
        `;
        
        cardEl.addEventListener('click', () => handleCardClick(index));
        
        container.appendChild(cardEl);
    });
}

function renderPlayedCards(playedCards) {
    const container = document.getElementById('played-cards');
    container.innerHTML = '';
    
    playedCards.forEach(([playerIndex, card]) => {
        const suitClass = getSuitClass(card.suit);
        const cardEl = document.createElement('div');
        cardEl.className = `played-card ${suitClass}`;
        cardEl.innerHTML = `
            <div class="card-rank">${card.rank}</div>
            <div class="card-suit ${suitClass}">${card.suit}</div>
        `;
        container.appendChild(cardEl);
    });
}

function getSuitClass(suit) {
    const suitMap = {
        '♥': 'hearts',
        '♦': 'diamonds',
        '♣': 'clubs',
        '♠': 'spades',
        // Support for Unicode escapes if they arrive that way
        '\u2665': 'hearts',
        '\u2666': 'diamonds',
        '\u2663': 'clubs',
        '\u2660': 'spades'
    };
    return suitMap[suit] || '';
}

function showStatus(message, type = 'info') {
    const messageEl = document.createElement('div');
    messageEl.className = `status-message ${type}`;
    messageEl.textContent = message;
    
    statusMessages.appendChild(messageEl);
    
    // Remove after 5 seconds
    setTimeout(() => {
        messageEl.remove();
    }, 5000);
}

function showGameOverModal(data) {
    const modal = document.getElementById('game-over-modal');
    const content = document.getElementById('game-over-content');
    
    if (data.winning_team !== undefined) {
        content.innerHTML = `
            <h3>Team ${data.winning_team + 1} Wins!</h3>
            <p>Final Score:</p>
            <p>Team 1: ${data.final_points[0]} points</p>
            <p>Team 2: ${data.final_points[1]} points</p>
            <p>Okalu Change: ${data.okalu_change}</p>
        `;
    } else if (data.message) {
        content.innerHTML = `<p>${data.message}</p>`;
    }
    
    modal.classList.remove('hidden');
}

// === DEVELOPER MODE FUNCTIONS ===
/**
 * Sends a POST request to reset the game state on the server.
 */
function resetGameDev() {
    if (confirm("Are you sure you want to reset the game state? All progress will be lost.")) {
        fetch('/dev/reset', { method: 'POST' })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Server responded with an error.');
                }
                return response.json();
            })
            .then(data => {
                console.log(data.message);
                // Reload the page to load the new, fresh game state
                window.location.reload(); 
            })
            .catch(error => {
                console.error('Error resetting game:', error);
                alert('Failed to reset game state. Check the server logs.');
            });
    }
}

/**
 * Switches the active player session in developer mode.
 * @param {string} newPlayerId The ID of the player to switch to.
 */
function switchPlayerDev(newPlayerId) {
    if (!newPlayerId) return;

    fetch(`/dev/switch_player/${newPlayerId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Server responded with an error.');
            }
            return response.json();
        })
        .then(data => {
            console.log(data.message);
            // Reload the page to display the new player's hand and UI
            window.location.reload(); 
        })
        .catch(error => {
            console.error('Error switching player:', error);
            alert('Failed to switch player. Check the server logs.');
        });
}

/**
 * Renders the hand of a specific player (used for Dev Mode visibility).
 * @param {string} playerId The ID of the player whose hand to render.
 * @param {Array<Object>} cards The cards array for that player.
 */
function renderOpponentHandDev(playerId, cards) {
    const playerContainerId = `player-${gameState.game_state.players.findIndex(p => p.id === playerId)}`;
    const playerEl = document.getElementById(playerContainerId);
    
    if (playerEl) {
        let handEl = playerEl.querySelector('.opponent-hand');
        if (!handEl) {
            handEl = document.createElement('div');
            handEl.className = 'opponent-hand';
            playerEl.appendChild(handEl);
        }
        
        handEl.innerHTML = '';
        cards.forEach(card => {
            const cardEl = document.createElement('div');
            const suitClass = getSuitClass(card.suit);
            cardEl.className = `played-card small-card ${suitClass}`; // Reusing played-card for small display
            
            cardEl.innerHTML = `
                <div class="card-rank">${card.rank}</div>
                <div class="card-suit ${suitClass}">${card.suit}</div>
            `;
            handEl.appendChild(cardEl);
        });
    }
}
// === END DEVELOPER MODE FUNCTIONS ===

// Initialize on page load
document.addEventListener('DOMContentLoaded', init);