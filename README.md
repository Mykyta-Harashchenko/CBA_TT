# Local Project Setup

## 1. Prepare your `.env` file

- Copy `.env.example` to `.env`:
  ```bash
  cp .env.example .env
  ```
- Edit `.env` and fill in all required environment variables (database credentials, secret keys, etc).

## 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Build and start containers

```bash
docker-compose up --build
```

- This will start the PostgreSQL database using the settings from your `.env` file.

## 5. Initialize the database schema

- After containers are running, apply the SQL schema to PostgreSQL:

  ```bash
  docker-compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -f /app/models_db.sql
  ```

  - Replace `/app/models_db.sql` with the correct path to your SQL schema file inside the container if needed.
  - `$POSTGRES_USER` and `$POSTGRES_DB` should match your `.env` values.

## 6. Start the FastAPI application

- If running locally (not in Docker):

  ```bash
  uvicorn main:app --reload
  ```

- Or configure a service/container for the app as needed.

## 7. Access the API

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

## 8. Run tests (optional)

```bash
pytest tests
```

---

**Notes:**  
- All configuration is managed via the `.env` file.
- The database will be ready with all schemas after running the SQL file in step 5.
- The virtual environment must be activated for all Python commands.