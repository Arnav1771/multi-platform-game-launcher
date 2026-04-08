```markdown
# Database Schema Design

This document outlines the database schema for the Multi-Platform Game Launcher. We are using PostgreSQL as our relational database, managed with SQLAlchemy as our ORM.

## Core Entities

### 1. `users`

Stores information about the application users.

| Column Name     | Data Type                  | Constraints                               | Description                                     |
| :-------------- | :------------------------- | :---------------------------------------- | :---------------------------------------------- |
| `id`            | `UUID`                     | `PRIMARY KEY`                             | Unique identifier for the user.                 |
| `username`      | `VARCHAR(50)`              | `NOT NULL`, `UNIQUE`                      | User's chosen username.                         |
| `email`         | `VARCHAR(100)`             | `NOT NULL`, `UNIQUE`                      | User's email address.                           |
| `password_hash` | `VARCHAR(255)`             | `NOT NULL`                                | Hashed password for authentication.             |
| `created_at`    | `TIMESTAMP WITH TIME ZONE` | `DEFAULT CURRENT_TIMESTAMP`               | Timestamp when the user was created.            |
| `updated_at`    | `TIMESTAMP WITH TIME ZONE` | `DEFAULT CURRENT_TIMESTAMP`               | Timestamp when the user was last updated.       |
| `is_active`     | `BOOLEAN`                  | `DEFAULT TRUE`                            | Flag indicating if the user account is active.  |
| `last_login`    | `TIMESTAMP WITH TIME ZONE` | `NULL`                                    | Timestamp of the user's last login.             |

### 2. `game_platforms`

Represents the different game platforms supported by the launcher.

| Column Name | Data Type   | Constraints               | Description                               |
| :---------- | :---------- | :------------------------ | :---------------------------------------- |
| `id`        | `INTEGER`   | `PRIMARY KEY`, `SERIAL`   | Unique identifier for the platform.       |
| `name`      | `VARCHAR(50)` | `NOT NULL`, `UNIQUE`      | Name of the game platform (e.g., Steam, Epic Games). |
| `icon_url`  | `VARCHAR(255)`| `NULL`                    | URL to an icon representing the platform. |

### 3. `games`

Stores general information about each game, regardless of platform.

| Column Name      | Data Type                  | Constraints                               | Description                                     |
| :--------------- | :------------------------- | :---------------------------------------- | :---------------------------------------------- |
| `id`             | `UUID`                     | `PRIMARY KEY`                             | Unique identifier for the game.                 |
| `title`          | `VARCHAR(255)`             | `NOT NULL`                                | The official title of the game.                 |
| `developer`      | `VARCHAR(100)`             | `NULL`                                    | The developer of the game.                      |
| `publisher`      | `VARCHAR(100)`             | `NULL`                                    | The publisher of the game.                      |
| `release_date`   | `DATE`                     | `NULL`                                    | The official release date of the game.          |
| `cover_image_url`| `VARCHAR(255)`             | `NULL`                                    | URL to the game's cover art.                    |
| `description`    | `TEXT`                     | `NULL`                                    | A brief description of the game.                |
| `added_at`       | `TIMESTAMP WITH TIME ZONE` | `DEFAULT CURRENT_TIMESTAMP`               | Timestamp when the game was added to the library. |
| `updated_at`     | `TIMESTAMP WITH TIME ZONE` | `DEFAULT CURRENT_TIMESTAMP`               | Timestamp when the game's info was last updated. |

### 4. `user_games`

Links users to the games in their library and stores platform-specific details.

| Column Name         | Data Type                  | Constraints                               | Description                                                                 |
| :------------------ | :------------------------- | :---------------------------------------- | :-------------------------------------------------------------------------- |
| `user_id`           | `UUID`                     | `NOT NULL`, `FOREIGN KEY (users.id)`      | The user who owns this game entry.                                          |
| `game_id`           | `UUID`                     | `NOT NULL`, `FOREIGN KEY (games.id)`      | The general game information.                                               |
| `platform_game_id`  | `VARCHAR(255)`             | `NOT NULL`                                | The unique identifier for the game on a specific platform (e.g., Steam App ID). |
| `platform_id`       | `INTEGER`                  | `NOT NULL`, `FOREIGN KEY (game_platforms.id)` | The platform on which the user owns this game.                              |
| `install_path`      | `VARCHAR(512)`             | `NULL`                                    | The local installation directory of the game on this platform.              |
| `is_installed`      | `BOOLEAN`                  | `DEFAULT FALSE`                           | Flag indicating if the game is currently installed locally.                 |
| `last_played_at`    | `TIMESTAMP WITH TIME ZONE` | `NULL`                                    | Timestamp of the last time the game was played.                             |
| `added_at`          | `TIMESTAMP WITH TIME ZONE` | `DEFAULT CURRENT_TIMESTAMP`               | Timestamp when this game was added to the user's library for this platform. |
| `updated_at`        | `TIMESTAMP WITH TIME ZONE` | `DEFAULT CURRENT_TIMESTAMP`               | Timestamp when this entry was last updated.                                 |
| `playtime_seconds`  | `INTEGER`                  | `DEFAULT 0`                               | Total playtime in seconds for this game on this platform.                   |
| `is_favorite`       | `BOOLEAN`                  | `DEFAULT FALSE`                           | Flag indicating if the user has favorited this game.                        |
| `notes`             | `TEXT`                     | `NULL`                                    | User-added notes for this game.                                             |

**Composite Primary Key:** `(user_id, game_id, platform_id)`

### 5. `platform_credentials`

Stores authentication credentials for each game platform per user.

| Column Name      | Data Type                  | Constraints                               | Description                                     |
| :--------------- | :------------------------- | :---------------------------------------- | :---------------------------------------------- |
| `id`             | `UUID`                     | `PRIMARY KEY`                             | Unique identifier for the credential entry.     |
| `user_id`        | `UUID`                     | `NOT NULL`, `FOREIGN KEY (users.id)`      | The user associated with these credentials.     |
| `platform_id`    | `INTEGER`                  | `NOT NULL`, `FOREIGN KEY (game_platforms.id)` | The platform these credentials are for.         |
| `username`       | `VARCHAR(100)`             | `NULL`                                    | Username or email for platform login.           |
| `encrypted_token`| `TEXT`                     | `NULL`                                    | Encrypted authentication token or password.     |
| `created_at`     | `TIMESTAMP WITH TIME ZONE` | `DEFAULT CURRENT_TIMESTAMP`               | Timestamp when the credentials were added.      |
| `updated_at`     | `TIMESTAMP WITH TIME ZONE` | `DEFAULT CURRENT_TIMESTAMP`               | Timestamp when the credentials were last updated. |

**Unique Constraint:** `(user_id, platform_id)`

## Relationships

*   **One-to-Many:**
    *   A `user` can have many `user_games` entries.
    *   A `user` can have many `platform_credentials` entries.
    *   A `game` can be associated with many `user_games` entries.
    *   A `game_platform` can be associated with many `user_games` entries.
    *   A `game_platform` can be associated with many `platform_credentials` entries.

*   **Many-to-Many (through `user_games`):**
    *   `users` and `games` are related via the `user_games` table, representing which user owns which game on which platform.

## Indexes

To optimize query performance, the following indexes are recommended:

*   `users`: `username`, `email`
*   `user_games`: `user_id`, `game_id`, `platform_id`, `install_path`, `is_installed`, `last_played_at`
*   `platform_credentials`: `user_id`, `platform_id`

## Future Considerations

*   **Game Metadata Caching:** A separate table or cache mechanism might be needed for frequently accessed, large metadata like screenshots, trailers, or detailed system requirements to reduce load on external APIs.
*   **Tags/Genres:** A many-to-many relationship between `games` and a new `tags` table for better game organization and filtering.
*   **Achievements:** A dedicated table to store user achievements for games, potentially linked to platforms.
*   **User Settings:** A table for user-specific application settings.
*   **Syncing:** Mechanisms for syncing game library status and playtime across multiple devices.

This schema provides a solid foundation for the Multi-Platform Game Launcher, allowing for efficient storage and retrieval of user game libraries and platform-specific information.
```