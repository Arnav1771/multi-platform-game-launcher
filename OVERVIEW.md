# OVERVIEW.md

## Multi-Platform Game Launcher

A unified game library manager for Steam, Epic Games, GOG, Xbox Game Pass, and Ubisoft+.

### Features

*   **Unified Library:** View all your games from supported platforms (Steam, Epic Games, GOG, Xbox Game Pass, Ubisoft+) in a single, sortable, and searchable interface.
*   **Platform Integration:** Seamlessly launch games directly from the launcher, regardless of the original platform.
*   **Metadata Enrichment:** Automatically fetches and displays rich game metadata, including cover art, descriptions, release dates, and user ratings.
*   **Wishlist Management:** Consolidate wishlists from different platforms.
*   **Installation Tracking:** Keep track of installed games and their locations.
*   **Customizable Views:** Personalize your library with filters, tags, and custom sorting options.
*   **Cross-Platform Compatibility:** Runs on Windows, macOS, and Linux.
*   **Offline Mode:** Access your library and launch installed games even without an internet connection.
*   **Extensible Architecture:** Designed with a plugin system for future platform integrations.

### Technology Stack

This project leverages a modern and robust technology stack to deliver a high-performance and user-friendly experience:

*   **Backend:**
    *   **Python:** The primary programming language for the backend API.
    *   **FastAPI:** A modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints.
    *   **SQLAlchemy:** A powerful and flexible SQL toolkit and Object-Relational Mapper (ORM) for Python, used for database interactions.
    *   **PostgreSQL:** A robust, open-source relational database system, chosen for its reliability, scalability, and advanced features.
    *   **Docker:** For containerizing the backend application and database, ensuring consistent deployment across different environments.

*   **Frontend:**
    *   **React:** A popular JavaScript library for building user interfaces.
    *   **TypeScript:** A superset of JavaScript that adds static typing, improving code quality and maintainability.
    *   **Electron:** A framework for building desktop applications using web technologies (HTML, CSS, JavaScript). This allows us to create a cross-platform desktop application with a single codebase.

*   **Development & Deployment:**
    *   **Docker Compose:** For orchestrating multi-container Docker applications, simplifying the setup and management of the backend and database during development and deployment.
    *   **Environment Variables:** Used for managing configuration and sensitive information (e.g., API keys, database credentials) securely.

### Architecture Overview

The application follows a client-server architecture:

1.  **Desktop Application (Electron Frontend):**
    *   Built with React and TypeScript, providing a rich and interactive user interface.
    *   Communicates with the backend API via HTTP requests.
    *   Handles user interactions, displays game library data, and initiates game launches.

2.  **Backend API (FastAPI):**
    *   Exposes RESTful endpoints for the desktop application to consume.
    *   Handles business logic, data retrieval from the database, and interactions with third-party platform APIs (e.g., Steam API, Epic Games API).
    *   Uses SQLAlchemy to interact with the PostgreSQL database.

3.  **Database (PostgreSQL):**
    *   Stores user data, game library information, metadata, and configuration settings.

4.  **Containerization (Docker):**
    *   The backend API and PostgreSQL database are containerized using Docker, ensuring isolated and reproducible environments. Docker Compose is used to manage these services during development.

This architecture allows for a clear separation of concerns, enabling independent development and scaling of the frontend and backend components. The use of Electron ensures a native-like desktop experience across multiple operating systems, while FastAPI and PostgreSQL provide a performant and reliable backend.