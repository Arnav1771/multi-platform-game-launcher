from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Platform Game Launcher API",
    description="API for managing games across Steam, Epic Games, GOG, Xbox Game Pass, and Ubisoft+.",
    version="0.1.0",
)

# CORS Middleware for allowing requests from the frontend (React/Electron)
# In production, restrict origins to your specific frontend domain(s)
origins = [
    "http://localhost:3000",  # React development server
    "http://localhost:5173",  # Vite development server (if used)
    "http://localhost:8080",  # Electron development server
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Setup (Placeholder - SQLAlchemy integration would go here) ---
# Example:
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@host:port/dbname")
# engine = create_engine(DATABASE_URL)
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()
# --- End Database Setup ---

# --- Pydantic Models (Example) ---
class Game(BaseModel):
    id: int
    title: str
    platform: str # e.g., "Steam", "Epic", "GOG", "Xbox", "Ubisoft"
    installed: bool = False
    launch_command: str | None = None

# --- In-memory data store (Replace with database in production) ---
# This is a placeholder for demonstration purposes.
# In a real application, this data would be fetched from and stored in a database.
mock_games = {
    1: {"id": 1, "title": "The Witcher 3: Wild Hunt", "platform": "GOG", "installed": True, "launch_command": "/path/to/witcher3/gog/launcher.exe"},
    2: {"id": 2, "title": "Cyberpunk 2077", "platform": "Steam", "installed": False, "launch_command": None},
    3: {"id": 3, "title": "Hades", "platform": "Epic", "installed": True, "launch_command": "/path/to/hades/epic/launcher.exe"},
    4: {"id": 4, "title": "Forza Horizon 5", "platform": "Xbox", "installed": True, "launch_command": "xbox://game/ForzaHorizon5"},
    5: {"id": 5, "title": "Assassin's Creed Valhalla", "platform": "Ubisoft", "installed": False, "launch_command": None},
}

# --- API Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """
    Serves the main HTML page for the game launcher frontend.
    This is useful for Electron applications or direct browser access.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Multi-Platform Game Launcher</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Montserrat:wght@400;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --background-light: #f0f2f5;
                --background-dark: #1a1a2e;
                --card-background-light: #ffffff;
                --card-background-dark: #2c2c44;
                --text-light: #333;
                --text-dark: #e0e0e0;
                --accent-gradient-light: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                --accent-gradient-dark: linear-gradient(135deg, #8360c3 0%, #2ebf91 100%);
                --button-hover-light: #5a67d8;
                --button-hover-dark: #3a3a60;
                --shadow-light: 0 4px 15px rgba(0, 0, 0, 0.1);
                --shadow-dark: 0 4px 15px rgba(0, 0, 0, 0.3);
                --border-color-light: #e2e8f0;
                --border-color-dark: #4a4a6a;
            }

            body {
                font-family: 'Inter', sans-serif;
                margin: 0;
                padding: 0;
                background-color: var(--background-light);
                color: var(--text-light);
                transition: background-color 0.3s ease, color 0.3s ease;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                overflow-x: hidden;
            }

            .dark-mode body {
                background-color: var(--background-dark);
                color: var(--text-dark);
            }

            .container {
                text-align: center;
                padding: 40px 20px;
                width: 100%;
                max-width: 1200px;
            }

            h1 {
                font-family: 'Montserrat', sans-serif;
                font-size: 3.5em;
                margin-bottom: 20px;
                background: var(--accent-gradient-light);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                animation: gradient-animation 5s ease infinite;
                transition: background 0.3s ease;
            }

            .dark-mode h1 {
                background: var(--accent-gradient-dark);
            }

            p {
                font-size: 1.2em;
                margin-bottom: 40px;
                line-height: 1.6;
            }

            .game-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 30px;
                margin-top: 40px;
            }

            .game-card {
                background-color: var(--card-background-light);
                border-radius: 12px;
                padding: 25px;
                box-shadow: var(--shadow-light);
                transition: transform 0.3s ease, box-shadow 0.3s ease, background-color 0.3s ease;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                align-items: center;
                text-align: center;
                border: 1px solid var(--border-color-light);
            }

            .dark-mode .game-card {
                background-color: var(--card-background-dark);
                box-shadow: var(--shadow-dark);
                border-color: var(--border-color-dark);
            }

            .game-card:hover {
                transform: translateY(-10px);
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
            }

            .dark-mode .game-card:hover {
                 box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
            }

            .game-card h3 {
                font-family: 'Montserrat', sans-serif;
                font-size: 1.8em;
                margin-bottom: 15px;
                color: var(--text-light);
            }

            .dark-mode .game-card h3 {
                 color: var(--text-dark);
            }

            .game-card p {
                font-size: 0.95em;
                color: #6b7280; /* Gray text */
                margin-bottom: 20px;
            }

            .dark-mode .game-card p {
                color: #9ca3af; /* Lighter gray text */
            }

            .platform-icon {
                font-size: 1.5em;
                margin-bottom: 15px;
                opacity: 0.8;
            }

            .launch-button {
                background: var(--accent-gradient-light);
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 8px;
                font-size: 1.1em;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.3s ease, transform 0.2s ease;
                text-decoration: none;
                display: inline-block;
            }

            .dark-mode .launch-button {
                background: var(--accent-gradient-dark);
            }

            .launch-button:hover {
                background-position: right center; /* for gradient */
                transform: translateY(-3px);
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            }

            .dark-mode .launch-button:hover {
                 box-shadow: 0 5px 15px rgba(0, 0, 0, 0.4);
            }

            .installed-status {
                font-size: 0.9em;
                margin-top: 15px;
                padding: 5px 10px;
                border-radius: 5px;
                font-weight: 500;
            }

            .installed-status.yes {
                background-color: #d1fae5; /* Green background */
                color: #065f46; /* Dark green text */
            }

            .dark-mode .installed-status.yes {
                background-color: #10b981; /* Darker green */
                color: #ffffff;
            }

            .installed-status.no {
                background-color: #fee2e2; /* Red background */
                color: #991b1b; /* Dark red text */
            }

            .dark-mode .installed-status.no {
                background-color: #f87171; /* Darker red */
                color: #ffffff;
            }

            /* Theme Toggle Button */
            .theme-toggle {
                position: fixed;
                top: 20px;
                right: 20px;
                background: #ccc;
                color: #333;
                border: none;
                padding: 10px 15px;
                border-radius: 50%;
                cursor: pointer;
                font-size: 1.2em;
                transition: background 0.3s ease, color 0.3s ease;
                z-index: 1000;
                box-shadow: var(--shadow-light);
            }

            .dark-mode .theme-toggle {
                background: #444;
                color: #eee;
                box-shadow: var(--shadow-dark);
            }

            .theme-toggle:hover {
                background: #aaa;
            }

            .dark-mode .theme-toggle:hover {
                background: #666;
            }

            /* Animations */
            @keyframes gradient-animation {
                0% { background-position: 0% 50%; }
                50% { background-position: 100% 50%; }
                100% { background-position: 0% 50%; }
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .game-card {
                animation: fadeIn 0.5s ease-out forwards;
                animation-delay: calc(var(--i) * 0.1s); /* Staggered animation */
            }

            /* Mobile Responsiveness */
            @media (max-width: 768px) {
                h1 {
                    font-size: 2.5em;
                }
                p {
                    font-size: 1em;
                }
                .game-grid {
                    grid-template-columns: 1fr;
                }
                .theme-toggle {
                    top: 15px;
                    right: 15px;
                    padding: 8px 12px;
                    font-size: 1em;
                }
            }
        </style>
    </head>
    <body>
        <button class="theme-toggle" aria-label="Toggle dark mode">🌙</button>
        <div class="container">
            <h1>Your Unified Game Library</h1>
            <p>Access and launch all your games from one place.</p>
            <div class="game-grid" id="gameGrid">
                <!-- Game cards will be loaded here by JavaScript -->
            </div>
        </div>

        <script>
            const toggleButton = document.querySelector('.theme-toggle');
            const body = document.body;
            const gameGrid = document.getElementById('gameGrid');

            // Function to apply theme class
            function applyTheme(isDark) {
                if (isDark) {
                    body.classList.add('dark-mode');
                    toggleButton.textContent = '☀️'; // Sun icon for dark mode
                } else {
                    body.classList.remove('dark-mode');
                    toggleButton.textContent = '🌙'; // Moon icon for light mode
                }
                localStorage.setItem('theme', isDark ? 'dark' : 'light');
            }

            // Event listener for theme toggle
            toggleButton.addEventListener('click', () => {
                const isDark = body.classList.toggle('dark-mode');
                applyTheme(isDark);
            });

            // Initialize theme from localStorage
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'dark') {
                applyTheme(true);
            } else {
                applyTheme(false); // Default to light mode if not set or set to 'light'
            }

            // Function to fetch and display games
            async function fetchAndDisplayGames() {
                try {
                    const response = await fetch('/api/games');
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    const games = await response.json();
                    displayGames(games);
                } catch (error) {
                    console.error("Failed to fetch games:", error);
                    gameGrid.innerHTML = '<p style="color: red;">Error loading games. Please try again later.</p>';
                }
            }

            // Function to display games in the grid
            function displayGames(games) {
                gameGrid.innerHTML = ''; // Clear existing content
                if (games.length === 0) {
                    gameGrid.innerHTML = '<p>No games found. Add some games to your library!</p>';
                    return;
                }

                games.forEach((game, index) => {
                    const card = document.createElement('div');
                    card.className = 'game-card';
                    card.style.setProperty('--i', index); // Set index for staggered animation

                    let platformIcon = '';
                    switch (game.platform.toLowerCase()) {
                        case 'steam': platformIcon = '☁️'; break; // Cloud icon for Steam
                        case 'epic': platformIcon = '🚀'; break; // Rocket for Epic
                        case 'gog': platformIcon = '🎮'; break; // Game controller for GOG
                        case 'xbox': platformIcon = '❎'; break; // X for Xbox
                        case 'ubisoft': platformIcon = '⚔️'; break; // Crossed swords for Ubisoft
                        default: platformIcon = '❓'; // Question mark for unknown
                    }

                    const installedStatusClass = game.installed ? 'yes' : 'no';
                    const installedStatusText = game.installed ? 'Installed' : 'Not Installed';

                    card.innerHTML = `
                        <div class="platform-icon">${platformIcon}</div>
                        <h3>${game.title}</h3>
                        <p>${game.platform}</p>
                        <div class="installed-status ${installedStatusClass}">${installedStatusText}</div>
                        ${game.launch_command ? `<a href="#" class="launch-button" onclick="launchGame(${game.id}); return false;">Launch</a>` : ''}
                    `;
                    gameGrid.appendChild(card);
                });
            }

            // Placeholder function for launching a game
            async function launchGame(gameId) {
                console.log(`Attempting to launch game with ID: ${gameId}`);
                // In a real Electron app, you would use ipcRenderer to send a message to the main process
                // Example:
                // if (window.electronAPI) {
                //     try {
                //         await window.electronAPI.launchGame(gameId);
                //         alert(`Launch command sent for game ID ${gameId}!`);
                //     } catch (error) {
                //         console.error("Failed to launch game:", error);
                //         alert(`Error launching game: ${error.message}`);
                //     }
                // } else {
                //     alert("Electron API not available. Cannot launch game directly.");
                // }

                // For web-based testing or if not in Electron:
                alert(`Simulating launch for game ID ${gameId}. Check console for details.`);
                try {
                    const response = await fetch(`/api/games/${gameId}/launch`, { method: 'POST' });
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
                    }
                    const result = await response.json();
                    alert(result.message);
                } catch (error) {
                    console.error("Failed to launch game via API:", error);
                    alert(`Error launching game: ${error.message}`);
                }
            }

            // Initial fetch when the page loads
            fetchAndDisplayGames();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/api/games", response_model=list[Game])
async def get_all_games():
    """
    Retrieves a list of all games in the library.
    """
    logger.info("Fetching all games.")
    # In a real application, this would query the database.
    # Example:
    # db = next(get_db())
    # games_from_db = db.query(GameModel).all()
    # return [Game.from_orm(game) for game in games_from_db]
    try:
        # Convert mock data to list of Game objects
        game_list = [Game(**data) for data in mock_games.values()]
        logger.info(f"Found {len(game_list)} games.")
        return game_list
    except Exception as e:
        logger.error(f"Error fetching games: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while fetching games.")

@app.get("/api/games/{game_id}", response_model=Game)
async def get_game_by_id(game_id: int):
    """
    Retrieves details for a specific game by its ID.
    """
    logger.info(f"Fetching game with ID: {game_id}")
    # In a real application, this would query the database.
    game_data = mock_games.get(game_id)
    if game_data is None:
        logger.warning(f"Game with ID {game_id} not found.")
        raise HTTPException(status_code=404, detail=f"Game with ID {game_id} not found.")
    try:
        game = Game(**game_data)
        logger.info(f"Found game: {game.title}")
        return game
    except Exception as e:
        logger.error(f"Error processing game data for ID {game_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while processing game data.")

@app.post("/api/games/{game_id}/launch", status_code=200)
async def launch_game_by_id(game_id: int):
    """
    Initiates the launch process for a specific game.
    This endpoint simulates launching the game. In an Electron environment,
    this would typically trigger an IPC message to the main process to execute the launch command.
    """
    logger.info(f"Received request to launch game with ID: {game_id}")
    game_data = mock_games.get(game_id)

    if game_data is None:
        logger.warning(f"Launch request failed: Game with ID {game_id} not found.")
        raise HTTPException(status_code=404, detail=f"Game with ID {game_id} not found.")

    if not game_data.get("installed", False):
        logger.warning(f"Launch request failed: Game '{game_data.get('title', 'Unknown')}' (ID: {game_id}) is not installed.")
        raise HTTPException(status_code=400, detail=f"Game '{game_data.get('title', 'Unknown')}' is not installed.")

    launch_command = game_data.get("launch_command")
    if not launch_command:
        logger.warning(f"Launch request failed: No launch command found for game '{game_data.get('title', 'Unknown')}' (ID: {game_id}).")
        raise HTTPException(status_code=500, detail=f"Launch command not configured for game '{game_data.get('title', 'Unknown')}'.")

    # --- Actual Launch Logic ---
    # In a real scenario, especially with Electron, you'd use inter-process communication (IPC)
    # to send the launch_command to the main Electron process, which would then execute it
    # using Node.js's child_process module (e.g., `child_process.exec` or `child_process.spawn`).
    #
    # Example (conceptual, requires Electron IPC setup):
    #
    # from your_electron_ipc_module import send_launch_command
    # try:
    #     success = send_launch_command(launch_command)
    #     if success:
    #         logger.info(f"Successfully initiated launch for game: {game_data.get('title', 'Unknown')} (ID: {game_id})")
    #         return {"message": f"Launch command sent for {game_data.get('title', 'Unknown')}"}
    #     else:
    #         logger.error(f"Failed to send launch command for game: {game_data.get('title', 'Unknown')} (ID: {game_id})")
    #         raise HTTPException(status_code=500, detail="Failed to communicate with the system to launch the game.")
    # except Exception as e:
    #     logger.error(f"Error during launch command execution for game ID {game_id}: {e}", exc_info=True)
    #     raise HTTPException(status_code=500, detail=f"An error occurred while trying to launch the game: {e}")

    # For this example, we'll just log and return a success message.
    logger.info(f"Simulating launch for game: {game_data.get('title', 'Unknown')} (ID: {game_id}) with command: {launch_command}")
    return {"message": f"Simulated launch command sent for {game_data.get('title', 'Unknown')}"}

# --- Health Check Endpoint ---
@app.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    """
    logger.debug("Health check endpoint called.")
    # In a real app, you might check database connection status here
    return {"status": "ok"}

# --- Main execution block (for running with uvicorn directly) ---
if __name__ == "__main__":
    import uvicorn
    # Get port from environment variable or default to 8000
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting FastAPI server on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
```