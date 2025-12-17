# Adu Shertu - Multiplayer Card Game

A real-time multiplayer implementation of the traditional Adu Shertu card game for 6 players, built with Python Flask and WebSockets.

## 📁 Project Structure

```
adu_shertu/
├── app.py                 # Main Flask server with WebSocket handlers
├── game_state.py          # Core game logic and rules engine
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Main game interface (HTML)
├── static/
│   ├── style.css         # Responsive styling
│   └── game.js           # Client-side JavaScript logic
└── README.md             # This file
```

## 🎯 File Descriptions

### **app.py** - Flask Server & WebSocket Handler
- Manages HTTP routes and WebSocket connections
- Handles player connections/disconnections
- Broadcasts game state updates to all players
- Manages active games and player sessions
- Routes events between clients and game logic

### **game_state.py** - Game Logic Engine
- Implements all Adu Shertu rules and mechanics
- Manages deck, cards, and trump system
- Handles trump calling, joint calls, and validation
- Implements challenge system (Adu, Shertu, Double, Shubble)
- Validates card plays according to complex rules
- Calculates scoring and manages okalu system
- Tracks game phases and player turns

### **templates/index.html** - Game Interface
- Single-page application with multiple screens
- Welcome screen for creating/joining games
- Lobby screen showing players and game code
- Main game screen with:
  - Player positions around virtual table
  - Card display and interaction
  - Action panels for trump calling and challenges
  - Real-time score and okalu tracking

### **static/style.css** - Responsive Styling
- Mobile-first responsive design
- Card game themed UI with suit colors
- Smooth animations and transitions
- Flexible layout for phones, tablets, and desktops
- Dark/light theme elements

### **static/game.js** - Client Logic
- WebSocket connection management
- Real-time UI updates based on game events
- Handles all player actions and inputs
- Manages game state synchronization
- Card selection and playing logic
- Status messages and notifications

## 🚀 Setup Instructions

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Local Development

1. **Create project directory and files:**

```bash
mkdir adu_shertu
cd adu_shertu
```

2. **Create the directory structure:**

```bash
mkdir templates static
```

3. **Create all the files** by copying the code from each artifact:
   - `app.py`
   - `game_state.py`
   - `requirements.txt`
   - `templates/index.html`
   - `static/style.css`
   - `static/game.js`

4. **Install dependencies:**

```bash
pip install -r requirements.txt
```

5. **Run the server:**

```bash
python app.py
```

6. **Access the game:**
   - Open your browser to: `http://localhost:5000`
   - The server runs on port 5000 by default

### Playing Locally

1. Open `http://localhost:5000` in your browser
2. Enter your name and create a new game
3. Share the 6-character game code with friends
4. Friends can join by entering the code
5. Once 6 players join, the host can start the game

## 🌐 Online Deployment Options

### Option 1: Heroku (Recommended for beginners)

1. **Install Heroku CLI:**
   - Download from: https://devcenter.heroku.com/articles/heroku-cli

2. **Create a `Procfile`:**

```bash
echo "web: python app.py" > Procfile
```

3. **Initialize git and deploy:**

```bash
git init
git add .
git commit -m "Initial commit"
heroku create your-adu-shertu-game
git push heroku main
```

4. **Open your game:**

```bash
heroku open
```

Your game will be accessible at: `https://your-adu-shertu-game.herokuapp.com`

### Option 2: Railway

1. **Go to:** https://railway.app
2. **Create new project** → Deploy from GitHub
3. **Connect your repository**
4. **Railway auto-detects** Python and installs dependencies
5. **Get your public URL** from Railway dashboard

### Option 3: Render

1. **Go to:** https://render.com
2. **New Web Service** → Connect repository
3. **Build Command:** `pip install -r requirements.txt`
4. **Start Command:** `python app.py`
5. **Deploy** and get your public URL

### Option 4: DigitalOcean App Platform

1. **Go to:** https://www.digitalocean.com/products/app-platform
2. **Create new app** from GitHub
3. **Select your repository**
4. **Configure:**
   - Type: Web Service
   - Build Command: `pip install -r requirements.txt`
   - Run Command: `python app.py`
5. **Deploy** and access via provided URL

### Option 5: AWS Elastic Beanstalk

1. **Install AWS CLI and EB CLI**
2. **Initialize EB:**

```bash
eb init -p python-3.9 adu-shertu
eb create adu-shertu-env
eb open
```

## 📱 Mobile Access

The game is fully mobile-responsive! Players can:
- Join from phones, tablets, or computers
- Play seamlessly across devices
- Use touch controls on mobile devices
- Communicate via separate phone call while playing

To play with friends:
1. Host creates game and shares code
2. Players join from their devices (phone/tablet/laptop)
3. Everyone can see their own cards and play in real-time
4. Use a separate call app (WhatsApp, Discord, etc.) for voice chat

## 🎮 Game Features

### Implemented Mechanics
✅ 6-player multiplayer with teams
✅ Full trump calling system with 9s
✅ Joint calling with two 9s
✅ Same-suit card replacement with public display
✅ Stage 1 challenges (Adu, Shertu)
✅ Stage 2 challenges (Double, Shubble)
✅ Fold system with okalu penalties
✅ Complete card hierarchy (trump and non-trump)
✅ Card playing rules and validation
✅ Hand winning determination
✅ Point scoring system
✅ Early game end (47 points rule)
✅ Okalu tracking across games
✅ Dealer rotation based on okalu
✅ Last hand +5 point bonus
✅ Real-time game state synchronization

## 🐛 Troubleshooting

### Port Already in Use
If port 5000 is occupied:

```python
# In app.py, change the last line:
socketio.run(app, host='0.0.0.0', port=8000, debug=True)
```

### WebSocket Connection Issues
- Ensure your firewall allows WebSocket connections
- On some hosting platforms, you may need to enable WebSocket support
- Check browser console for connection errors

### Cards Not Displaying
- Clear browser cache
- Check browser console for JavaScript errors
- Ensure all static files are properly served

## 🔧 Configuration

### Change Port
Edit `app.py` line at bottom:
```python
socketio.run(app, host='0.0.0.0', port=YOUR_PORT, debug=True)
```

### Enable/Disable Debug Mode
```python
socketio.run(app, host='0.0.0.0', port=5000, debug=False)
```

### Secure WebSocket (WSS) for Production
For HTTPS deployments, Socket.IO automatically upgrades to WSS. Most hosting platforms (Heroku, Render, Railway) handle SSL certificates automatically.

## 📝 Game Rules Summary

- **Players:** 6 (2 teams of 3, alternating seats)
- **Deck:** 24 cards (9, 10, J, Q, K, A of each suit)
- **Objective:** Jack-trump team needs 100+ points; opposing team can win with 47+
- **Trump Calling:** Player with 9 calls trump suit
- **Challenges:** Double okalu at stake through Adu/Shertu/Double/Shubble
- **Hands:** 4 hands per game, winner leads next hand
- **Scoring:** Cards have different values, trump cards score highest

## 🤝 Contributing

To modify the game:
1. Edit `game_state.py` for rule changes
2. Edit `app.py` for server/networking changes
3. Edit `game.js` for client behavior
4. Edit `style.css` for visual updates
5. Test locally before deploying

## 📄 License

This is a personal project. Feel free to use and modify for your own games with friends!

## 🎉 Enjoy Playing!

Share the game link with friends and enjoy Adu Shertu from anywhere in the world!