# Environment Configuration Template

This document outlines the required environment variables for the application.  
Copy the template below into a `.env` file and replace the placeholder values with your actual configuration.

---

## Variable Reference

| Category          | Variable          | Description                                                                 |
|-------------------|-------------------|-----------------------------------------------------------------------------|
| **Secret Key**    | `SECRET_KEY`      | Django secret key – used for cryptographic signing. Keep it private. |
| **Database**      | `DB_NAME`         | Name of the database (e.g., `myapp_db`).                                   |
|                   | `DB_USER`         | Database username.                                                          |
|                   | `DB_PASSWORD`     | Database password.                                                          |
|                   | `DB_HOST`         | Database host (e.g., `localhost` or `postgres-server`).                     |
|                   | `DB_PORT`         | Database port (e.g., `5432` for PostgreSQL, `3306` for MySQL).             |
| **Celery**        | `CELERY_BROKER_URL` | Broker URL for Celery (e.g., `redis://localhost:6379/0`).                   |
| **Google OAuth**  | `CLIENT_ID`       | OAuth 2.0 Client ID from Google Cloud Console.                              |
|                   | `CLIENT_SECRET`   | OAuth 2.0 Client Secret from Google Cloud Console.                         |

---

## Template – Copy this block

```ini
# ----------------------------------------------------------------------
# Django Secret Key
# ----------------------------------------------------------------------
SECRET_KEY=your-secret-key-here

# ----------------------------------------------------------------------
# Database Configuration
# ----------------------------------------------------------------------
DB_NAME=your-database-name
DB_USER=your-database-user
DB_PASSWORD=your-database-password
DB_HOST=localhost
DB_PORT=5432

# ----------------------------------------------------------------------
# Celery Broker (Redis / RabbitMQ)
# ----------------------------------------------------------------------
CELERY_BROKER_URL=redis://localhost:6379/0

# ----------------------------------------------------------------------
# Google OAuth Credentials
# ----------------------------------------------------------------------
CLIENT_ID=your-google-client-id.apps.googleusercontent.com
CLIENT_SECRET=your-google-client-secret