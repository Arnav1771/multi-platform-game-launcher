# Multi-Platform Game Launcher Architecture

## 1. Overview

The Multi-Platform Game Launcher is a desktop application designed to unify the management of game libraries across various digital storefronts, including Steam, Epic Games Store, GOG, Xbox Game Pass, and Ubisoft+. It provides a single interface for launching games, tracking playtime, and managing installations, abstracting away the complexities of individual platform clients.

## 2. Technology Stack

*   **Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL
*   **Frontend:** React, TypeScript, Vite
*   **Desktop Application:** Electron
*   **Containerization:** Docker
*   **Database:** PostgreSQL

## 3. System Design

The system is architected as a client-server application, where the Electron desktop application acts as the client and a FastAPI-based backend server runs locally on the user's machine. This approach allows for:

*   **Centralized Logic:** Game launching, library management, and API integrations are handled by the backend.
*   **Decoupled UI:** The frontend can be developed and updated independently.
*   **Platform Abstraction:** The backend interacts with platform-specific APIs and executables, presenting a unified interface to the frontend.
*   **Local Operation:** All data and processing occur on the user's machine, ensuring privacy and offline functionality for launched games.

### 3.1. Backend (FastAPI)

The FastAPI backend serves as the core of the application. It handles:

*   **API Endpoints:** Exposes RESTful APIs for the Electron frontend to interact with.
*   **Database Operations:** Manages game metadata, user configurations, and platform credentials using SQLAlchemy and PostgreSQL.
*   **Platform Integrations:** Implements modules for interacting with Steam, Epic Games, GOG, Xbox Game Pass, and Ubisoft+ APIs and executables.
*   **Authentication & Authorization:** Manages local user sessions and potentially platform-specific OAuth flows.
*   **Background Tasks:** Handles asynchronous operations like library scanning and game updates.

**Key Components:**

*   **`main.py`:** FastAPI application entry point.
*   **`api/`:** Directory for API route definitions.
    *   `v1/`: Versioned API routes.
        *   `endpoints/`: Individual API endpoint modules (e.g., `games.py`, `platforms.py`, `settings.py`).
        *   `deps.py`: Dependency injection utilities.
        *   `schemas.py`: Pydantic models for request/response validation.
*   **`core/`:** Core application logic.
    *   `config.py`: Environment variable loading and configuration.
    *   `security.py`: Authentication and authorization utilities.
    *   `logging_config.py`: Centralized logging configuration.
*   **`db/`:** Database interaction layer.
    *   `session.py`: Database session management.
    *   `models.py`: SQLAlchemy ORM models.
    *   `crud.py`: CRUD operations for database models.
*   **`integrations/`:** Platform-specific integration modules.
    *   `steam.py`
    *   `epic.py`
    *   `gog.py`
    *   `xbox.py`
    *   `ubisoft.py`
    *   `base.py`: Abstract base class for integrations.
*   **`services/`:** Business logic services.
    *   `game_service.py`: Logic for game discovery, launching, and management.
    *   `platform_service.py`: Logic for managing platform connections and credentials.
*   **`utils/`:** Utility functions.

**Environment Variables:**

*   `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:password@host:port/dbname`).
*   `SECRET_KEY`: For JWT signing and other security-sensitive operations.
*   `STEAM_API_KEY`: Optional, for enhanced Steam API access.
*   `EPIC_CLIENT_ID`, `EPIC_CLIENT_SECRET`: For Epic Games API integration.
*   Other platform-specific credentials and API keys.

**Logging:**

*   Structured logging using `python-json-logger`.
*   Logs are written to a file and/or console, configurable via environment variables.
*   Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) are configurable.

### 3.2. Frontend (React/TypeScript)

The React frontend provides the user interface for the launcher. It communicates with the local FastAPI backend via HTTP requests.

**Key Components:**

*   **`src/`:** Frontend source code.
    *   **`components/`:** Reusable UI components (e.g., `GameCard`, `PlatformSelector`, `SettingsForm`).
    *   **`pages/`:** Top-level page components (e.g., `HomePage`, `LibraryPage`, `SettingsPage`).
    *   **`services/`:** API client functions for interacting with the backend.
    *   **`store/`:** State management (e.g., using Zustand or Redux Toolkit).
    *   **`hooks/`:** Custom React hooks.
    *   **`utils/`:** Frontend utility functions.
    *   **`App.tsx`:** Main application component.
    *   **`main.tsx`:** Entry point for the React application.
*   **`public/`:** Static assets.
*   **`index.html`:** Main HTML file.

**Styling:**

*   Modern, responsive design using CSS Modules or a CSS-in-JS library.
*   Integration with Google Fonts for typography.
*   Dark/Light theme support with smooth transitions and gradient accents.

### 3.3. Desktop Application (Electron)

Electron is used to package the React frontend and the FastAPI backend into a cross-platform desktop application.

*   **`electron/`:** Electron-specific configuration and main process code.
    *   **`main.js`:** Electron main process script. Responsible for:
        *   Creating the browser window.
        *   Managing the application lifecycle.
        *   Launching and managing the FastAPI backend process.
        *   Inter-process communication (IPC) between the main process and renderer process (React frontend).
    *   **`preload.js`:** Script to safely expose Node.js APIs to the renderer process.
*   **`package.json`:** Project configuration, including build scripts for Electron.

**Backend Process Management:**

The Electron `main.js` script will:

1.  Start the FastAPI backend server as a child process.
2.  Handle configuration and environment variables for the backend.
3.  Ensure the backend server is running before the frontend loads.
4.  Gracefully shut down the backend process when the application closes.

### 3.4. Database (PostgreSQL)

A PostgreSQL database is used to store:

*   User account information (if applicable, though primarily local).
*   Game metadata (title, icon, platform, installation path, etc.).
*   Platform credentials (encrypted).
*   User preferences and settings.
*   Playtime tracking data.

**Schema Design:**

*   **`users`**: Stores user profiles (if multi-user support is added).
*   **`platforms`**: Stores information about connected platforms (e.g., Steam, Epic).
*   **`credentials`**: Stores encrypted platform credentials.
*   **`games`**: Stores unified game metadata.
*   **`game_platforms`**: Many-to-many relationship between games and platforms.
*   **`settings`**: User-specific application settings.
*   **`playtime_logs`**: Records of game sessions and durations.

## 4. Data Flow

1.  **Startup:**
    *   Electron app starts.
    *   `electron/main.js` launches the FastAPI backend process.
    *   FastAPI backend initializes, connects to PostgreSQL, and loads configurations.
    *   Electron loads the React frontend (`index.html`).
2.  **Frontend Interaction:**
    *   User interacts with the React UI.
    *   React components make API calls to the local FastAPI backend.
3.  **Backend Processing:**
    *   FastAPI receives requests, performs validation, and interacts with the database (SQLAlchemy).
    *   For platform-specific actions (e.g., launching a game), the relevant integration module is invoked.
    *   Integrations may interact with platform executables (e.g., `steam://run/<appid>`) or APIs.
4.  **Data Synchronization:**
    *   Periodic background tasks scan installed games on each platform.
    *   New games are added to the `games` table.
    *   Playtime is logged during active game sessions.
5.  **Response:**
    *   FastAPI sends responses back to the React frontend.
    *   React UI updates based on the received data.

## 5. Security Considerations

*   **Credential Storage:** Platform credentials (API keys, tokens, passwords) must be stored securely. This involves:
    *   Encryption at rest using a strong, symmetric encryption algorithm (e.g., AES-256) with a key derived from the `SECRET_KEY` environment variable or a system-specific secure storage mechanism.
    *   Using environment variables for sensitive configuration.
*   **API Security:** All API endpoints should be protected, especially those that modify data or access sensitive information. JWT-based authentication is recommended for inter-process communication.
*   **Input Validation:** Rigorous validation of all incoming data (API requests, user input) using Pydantic models.
*   **Dependency Management:** Regularly update dependencies to patch known vulnerabilities.
*   **Least Privilege:** The backend process should run with the minimum necessary permissions.
*   **Platform Executable Interaction:** Be cautious when executing external platform executables. Sanitize any arguments passed to them.

## 6. Development Workflow

1.  **Setup:**
    *   Install Python, Node.js, and Docker.
    *   Set up PostgreSQL database.
    *   Configure environment variables (`.env` file).
2.  **Backend Development:**
    *   Navigate to the backend directory (`cd backend`).
    *   Create a virtual environment (`python -m venv venv`, `source venv/bin/activate`).
    *   Install dependencies (`pip install -r requirements.txt`).
    *   Run the backend server (`uvicorn main:app --reload`).
3.  **Frontend Development:**
    *   Navigate to the frontend directory (`cd frontend`).
    *   Install dependencies (`npm install` or `yarn install`).
    *   Run the development server (`npm run dev` or `yarn dev`).
4.  **Electron Development:**
    *   Navigate to the root directory.
    *   Install dependencies (`npm install` or `yarn install`).
    *   Run the Electron app (`npm run electron:dev` or `yarn electron:dev`).
5.  **Docker:**
    *   Build and run services using Docker Compose (`docker-compose up --build`).
6.  **Testing:**
    *   Write unit and integration tests for both backend and frontend.
    *   Use pytest for backend testing.
    *   Use Jest/React Testing Library for frontend testing.

## 7. Deployment

1.  **Build:**
    *   Build the production React frontend.
    *   Build the production FastAPI backend.
    *   Package the application using Electron Builder for target platforms (Windows, macOS, Linux).
2.  **Containerization (Optional but Recommended):**
    *   Use Docker Compose to define and run the PostgreSQL database and the FastAPI backend service.
    *   The Electron application would typically be installed directly on the user's system, not containerized itself.
3.  **Distribution:**
    *   Sign the application executables for each platform.
    *   Distribute installers via a website or platform-specific stores.

## 8. Future Enhancements

*   **Cloud Sync:** Sync game libraries and settings across multiple devices via a cloud backend.
*   **Community Features:** Social features, game recommendations, friend lists.
*   **Advanced Filtering & Sorting:** More sophisticated ways to manage large game libraries.
*   **Mod Management:** Integration with mod managers for supported games.
*   **Achievement Tracking:** Aggregating achievements across platforms.
*   **Enhanced Platform Support:** Adding support for more storefronts (e.g., Itch.io, Humble Bundle).
*   **Automated Updates:** Automatically update platform clients or games where feasible.

---

This document outlines the architectural design of the Multi-Platform Game Launcher. It emphasizes modularity, security, and maintainability, leveraging a modern technology stack for a robust and user-friendly experience.