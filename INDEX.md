# Multi-Platform Game Launcher

Welcome to the documentation for the Multi-Platform Game Launcher! This project aims to provide a unified interface for managing your game libraries across various digital storefronts, including Steam, Epic Games Store, GOG, Xbox Game Pass, and Ubisoft+.

## Table of Contents

*   [Introduction](#introduction)
*   [Features](#features)
*   [Technology Stack](#technology-stack)
*   [Getting Started](#getting-started)
    *   [Prerequisites](#prerequisites)
    *   [Installation](#installation)
    *   [Running the Application](#running-the-application)
*   [Configuration](#configuration)
*   [API Documentation](#api-documentation)
*   [Contributing](#contributing)
*   [License](#license)

## Introduction

The Multi-Platform Game Launcher is a desktop application designed to simplify the way you access and manage your game collections. Tired of juggling multiple launchers and storefronts? This project brings them all together under one roof, offering a seamless experience for launching your games, regardless of where you purchased them.

## Features

*   **Unified Library View:** See all your games from supported platforms in a single, sortable, and searchable list.
*   **Platform Integration:** Connect and manage your accounts for Steam, Epic Games Store, GOG, Xbox Game Pass, and Ubisoft+.
*   **Game Launching:** Launch games directly from the application.
*   **Metadata Enrichment:** Automatically fetches and displays game details, artwork, and descriptions.
*   **Customizable Interface:** Personalize your game library view with themes and layouts.
*   **Cross-Platform Compatibility:** Designed to run on Windows, macOS, and Linux.

## Technology Stack

*   **Backend:** Python (FastAPI), SQLAlchemy, PostgreSQL
*   **Frontend:** React, TypeScript
*   **Desktop Application:** Electron
*   **Containerization:** Docker

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed on your system:

*   **Python:** Version 3.8 or higher.
*   **Node.js:** Version 16.0.0 or higher.
*   **npm** or **yarn:** Package manager for Node.js.
*   **Docker:** For containerized development and deployment.
*   **PostgreSQL:** A running PostgreSQL instance.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/multi-platform-game-launcher.git
    cd multi-platform-game-launcher
    ```

2.  **Set up the backend:**
    *   Create a virtual environment:
        ```bash
        python -m venv venv
        source venv/bin/activate  # On Windows use `venv\Scripts\activate`
        ```
    *   Install backend dependencies:
        ```bash
        pip install -r requirements.txt
        ```
    *   Configure your environment variables (see [Configuration](#configuration)).
    *   Run database migrations:
        ```bash
        # You might need to install alembic first: pip install alembic
        alembic upgrade head
        ```

3.  **Set up the frontend:**
    *   Navigate to the frontend directory:
        ```bash
        cd frontend
        ```
    *   Install frontend dependencies:
        ```bash
        npm install  # or yarn install
        ```

4.  **Build the Electron application:**
    *   Navigate to the root directory:
        ```bash
        cd ..
        ```
    *   Install Electron dependencies:
        ```bash
        npm install --save-dev electron electron-builder # or yarn add --dev electron electron-builder
        ```

### Running the Application

1.  **Start the backend API:**
    ```bash
    # Ensure your virtual environment is activated
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```

2.  **Start the frontend development server:**
    ```bash
    cd frontend
    npm run dev # or yarn dev
    ```

3.  **Run the Electron application:**
    ```bash
    # From the root directory
    electron .
    ```

## Configuration

The application uses environment variables for configuration. Create a `.env` file in the root directory of the project with the following variables:

```dotenv
# Backend Configuration
DATABASE_URL="postgresql://user:password@host:port/dbname"
SECRET_KEY="your-super-secret-key"
JWT_ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Platform Specific API Keys/Credentials (Example)
# STEAM_API_KEY="your_steam_api_key"
# EPIC_CLIENT_ID="your_epic_client_id"
# EPIC_CLIENT_SECRET="your_epic_client_secret"
# GOG_API_KEY="your_gog_api_key"
# XBOX_API_KEY="your_xbox_api_key"
# UBISOFT_API_KEY="your_ubisoft_api_key"

# Frontend Configuration (if needed)
# VITE_API_URL="http://localhost:8000"
```

**Note:** Replace placeholder values with your actual credentials. Some platform credentials might require specific setup through their developer portals.

## API Documentation

The backend API is built with FastAPI and provides a RESTful interface. You can access the interactive API documentation (Swagger UI) at:

`http://localhost:8000/docs`

## Contributing

We welcome contributions! Please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines on how to contribute to this project.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.