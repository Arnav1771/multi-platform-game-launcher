# Multi-Platform Game Launcher

A unified game library manager for Steam, Epic Games, GOG, Xbox Game Pass, and Ubisoft+.

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [Docker Setup](#docker-setup)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Introduction

The Multi-Platform Game Launcher aims to simplify the management of your diverse game library across multiple digital storefronts. Tired of juggling different launchers and remembering where you own which game? This project provides a single, elegant interface to view, organize, and launch your games, regardless of their origin.

## Features

*   **Unified Library View:** See all your games from Steam, Epic Games, GOG, Xbox Game Pass, and Ubisoft+ in one place.
*   **Game Information:** Access details like game title, developer, publisher, genre, and cover art.
*   **Launch Games:** Launch games directly from the launcher.
*   **Platform Integration:** Seamless integration with major game platforms.
*   **Customizable Organization:** Tag, sort, and filter your games to create personalized collections.
*   **Cross-Platform Compatibility:** Designed to run on Windows, macOS, and Linux.

## Tech Stack

*   **Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL
*   **Frontend:** React, TypeScript
*   **Desktop Application:** Electron
*   **Containerization:** Docker

## Installation

### Prerequisites

Before you begin, ensure you have the following installed:

*   **Node.js:** (LTS version recommended) - [https://nodejs.org/](https://nodejs.org/)
*   **Python:** (3.8+) - [https://www.python.org/](https://www.python.org/)
*   **Docker:** (if using Docker setup) - [https://www.docker.com/get-started](https://www.docker.com/get-started)
*   **Git:** - [https://git-scm.com/downloads](https://git-scm.com/downloads)

### Backend Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/multi-platform-game-launcher.git
    cd multi-platform-game-launcher
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install backend dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a `.env` file in the root of the project and add your PostgreSQL connection details and any necessary API keys for game platforms.

    ```env
    # Example .env file
    DATABASE_URL="postgresql://user:password@host:port/dbname"
    STEAM_API_KEY="your_steam_api_key"
    EPIC_CLIENT_ID="your_epic_client_id"
    EPIC_CLIENT_SECRET="your_epic_client_secret"
    # Add other platform-specific credentials as needed
    ```

5.  **Run database migrations:**
    (Assuming you have a migration tool like Alembic set up)
    ```bash
    alembic upgrade head
    ```
    *Note: If you haven't set up Alembic, you'll need to configure it or use SQLAlchemy's ORM to create tables directly.*

6.  **Start the FastAPI backend:**
    ```bash
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```

### Frontend Setup

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```

2.  **Install frontend dependencies:**
    ```bash
    npm install
    ```

3.  **Start the React development server:**
    ```bash
    npm start
    ```
    This will typically start the frontend on `http://localhost:3000`.

### Docker Setup

1.  **Build the Docker images:**
    ```bash
    docker-compose build
    ```

2.  **Start the Docker containers:**
    ```bash
    docker-compose up
    ```
    This command will start the PostgreSQL database, the FastAPI backend, and the React frontend in separate containers. You may need to configure environment variables for the backend container as described in the backend setup section, potentially by mounting a `.env` file or using Docker secrets.

## Usage

Once the backend and frontend are running, you can access the application through your web browser at `http://localhost:3000` (or the port specified by your frontend setup).

Follow the on-screen instructions to connect your game platform accounts and import your game library.

## Contributing

We welcome contributions! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to submit bug reports, feature requests, and pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.