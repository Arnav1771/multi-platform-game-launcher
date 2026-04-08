# QUICK START GUIDE

Welcome to the multi-platform-game-launcher! This guide will walk you through the steps to get the application up and running quickly.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

1.  **Docker and Docker Compose:** The application is containerized for easy setup and management.
    *   Download and install Docker Desktop: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)
    *   Docker Compose is included with Docker Desktop.

2.  **Git:** For cloning the repository.
    *   Download and install Git: [https://git-scm.com/downloads](https://git-scm.com/downloads)

## Step 1: Clone the Repository

First, clone the project repository from GitHub to your local machine.

```bash
git clone https://github.com/your-username/multi-platform-game-launcher.git
cd multi-platform-game-launcher
```

**Note:** Replace `https://github.com/your-username/multi-platform-game-launcher.git` with the actual URL of the repository if it's different.

## Step 2: Configure Environment Variables

The application uses environment variables for configuration, especially for database credentials and API keys. Create a `.env` file in the root of the project directory and populate it with the necessary values.

```dotenv
# .env

# Database Configuration
POSTGRES_USER=game_launcher_user
POSTGRES_PASSWORD=supersecretpassword
POSTGRES_DB=game_launcher_db
POSTGRES_HOST=db
POSTGRES_PORT=5432

# FastAPI Application Configuration
SECRET_KEY=a_very_long_and_complex_secret_key_for_jwt
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Optional: Add any other necessary API keys or configurations here
# EXAMPLE_API_KEY=your_example_api_key
```

**Important:**
*   **`POSTGRES_HOST`**: Set this to `db` if you are using Docker Compose as provided in the `docker-compose.yml` file. If running PostgreSQL outside of Docker, use the appropriate host address.
*   **`POSTGRES_USER`**, **`POSTGRES_PASSWORD`**, **`POSTGRES_DB`**: These should match the values used in the `docker-compose.yml` file for the PostgreSQL service.
*   **`SECRET_KEY`**: Generate a strong, random secret key. This is crucial for security.

## Step 3: Build and Run with Docker Compose

Docker Compose is the recommended way to run the application. It will build the necessary Docker images (backend, frontend, and database) and start them in a coordinated manner.

Navigate to the root of the project directory in your terminal and run:

```bash
docker-compose up --build
```

This command will:
1.  **`--build`**: Build the Docker images for the backend (FastAPI) and frontend (React/Electron) if they don't exist or if changes have been made.
2.  **`up`**: Create and start the containers defined in your `docker-compose.yml` file. This includes the PostgreSQL database, the FastAPI backend, and the Electron frontend.

The application will be accessible at:

*   **Backend API:** `http://localhost:8000`
*   **Frontend:** `http://localhost:3000` (or the port specified in your frontend Docker configuration)

Logs from all services will be streamed to your terminal. You can stop the application by pressing `Ctrl+C` in the terminal where `docker-compose up` is running. To stop and remove the containers, use `docker-compose down`.

## Step 4: Access the Application

Once the Docker containers are running, open your web browser and navigate to `http://localhost:3000` (or the frontend port). You should see the multi-platform-game-launcher interface.

## Development Workflow

If you are developing the application, you might want to run the backend and frontend services separately for faster iteration.

### Backend Development

1.  **Install Dependencies:**
    ```bash
    cd backend
    pip install -r requirements.txt
    ```
2.  **Run the FastAPI Server:**
    ```bash
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```
    This will start the backend API server, which will automatically reload on code changes. Ensure your PostgreSQL database is running (either via `docker-compose up db` or a separate instance).

### Frontend Development

1.  **Install Dependencies:**
    ```bash
    cd frontend
    npm install
    ```
2.  **Start the Development Server:**
    ```bash
    npm start
    ```
    This will start the React development server, typically accessible at `http://localhost:3000`.

### Electron App Development

For building the desktop application:

1.  **Navigate to the Electron directory:**
    ```bash
    cd electron
    ```
2.  **Install Dependencies:**
    ```bash
    npm install
    ```
3.  **Start the Electron App:**
    ```bash
    npm start
    ```
    This command will build and run the Electron application. You might need to adjust the `main` script in `electron/package.json` to point to your compiled frontend assets if you are building the frontend separately.

## Troubleshooting

*   **Database Connection Errors:** Ensure your `.env` file has the correct PostgreSQL credentials and that the `POSTGRES_HOST` is set correctly (usually `db` when using Docker Compose). Check if the PostgreSQL container is running using `docker ps`.
*   **Port Conflicts:** If you encounter "port already in use" errors, it means another application is using the port that Docker is trying to assign. You can either stop the other application or change the port mapping in the `docker-compose.yml` file.
*   **Build Failures:** Check the output of the `docker-compose up --build` command for specific error messages. Ensure you have enough disk space and that your Docker daemon is running correctly.
*   **Frontend Not Loading:** Verify that the frontend service is running and accessible at the specified port. Check the browser's developer console for any JavaScript errors.

This quick start guide should get you up and running with the multi-platform-game-launcher. Happy gaming!