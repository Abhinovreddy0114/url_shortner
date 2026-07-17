# 📖 The Story of SnapURL: From Local Code to Docker Containers

This is the step-by-step story of how we built **SnapURL**—a premium URL shortener application. It explains exactly how we designed the database, connected the backend, crafted the frontend, and packaged the entire system into Docker containers.

---

## 🎭 Chapter 1: The Local Genesis
Our story begins on your Mac. We had a goal: to build a URL shortener that followed the **Hello Interview Bitly system design**. 

Before installing anything new, we checked what tools your Mac already had. We discovered:
1. **Python 3** was already installed.
2. **Postgres.app** (a local PostgreSQL database manager) was already running in your system menu bar.
3. Python libraries like `Flask` and `psycopg2` (for database connections) were already installed.

Since we had everything we needed, we decided to build the project locally first.

---

## 🧠 Chapter 2: Making the Database the "Brain" (`init.sql`)
In typical web apps, the backend code (Python/Node.js) does all the calculations, and the database only stores plain text. For **SnapURL**, we did the opposite: **we put all the logic directly inside the database**.

We wrote `init.sql` to define:
1. **The `urls` Table**:
   - `short_code` (Primary Key): The final unique identifier (like `3x9GzA` or a custom alias like `github-code`).
   - `long_url`: The destination web address.
   - `custom_alias`: An optional unique name chosen by the user.
   - `expiration_date`: A timestamp to check if the link is expired.
   - `created_at`: The link's creation date.

2. **The Base62 Generator (`generate_random_base62`)**:
   A custom PL/pgSQL database function that pulls characters from `0-9`, `a-z`, and `A-Z` to generate random 6-character strings.

3. **The Shortener Function (`shorten_url`)**:
   A database-level function:
   - If the user provides a **custom alias**, it checks if it's already taken. If taken, it throws a database error: `Alias is already taken`.
   - If the user doesn't provide an alias, it generates a random Base62 code. If a duplicate is found (collision), it loops and tries again up to 20 times to find a unique key.
   - It inserts the URL details and returns the row.

4. **The Resolver Function (`resolve_url`)**:
   A database-level lookup:
   - Takes a `short_code`, retrieves the row, and compares the `expiration_date` with the current time.
   - If the time has expired or the code doesn't exist, it returns `NULL`.
   - If valid, it returns the `long_url`.

---

## 🔌 Chapter 3: The Translation Bridge (`app.py`)
With the database handling the logic, we wrote a lightweight Python Flask script (`app.py`) to act as a wrapper. It does only three simple tasks:

1. **Serves the Web Page**: Sends the dashboard HTML/CSS to the user's browser.
2. **Handles URL Creation (`POST /urls`)**:
   - Takes input from the browser.
   - Calls the database function: `SELECT * FROM shorten_url(...)`.
   - If Postgres returns a success, Flask forwards it. If Postgres throws a "duplicate alias" error, Flask catches the exception and returns a `400 Bad Request` code with the database error message.
3. **Redirects Visitors (`GET /<short_code>`)**:
   - When a user visits `http://127.0.0.1:5001/code`, Flask calls the database's lookup function: `SELECT resolve_url('code')`.
   - If a URL is returned, it issues an HTTP 302 redirect.
   - If `NULL` is returned, it shows a custom `404.html` error page.

---

## 🎨 Chapter 4: The Glassmorphism UI
To make the app look stunning, we avoided plain styles and created a premium **Glassmorphism UI** using CSS and HTML:
* **Background Blobs**: Soft glowing neon gradients float behind the card.
* **Frosted Glass Card**: The form sits in a container with a blurred, semi-transparent background (`backdrop-filter`).
* **Micro-interactions**: Subtle hover transitions, button load animations, and copy feedback.
* **Native JavaScript**: A simple script manages form submission using browser `fetch()`. It shows loading spinners, displays success cards with copy buttons, and shakes the screen with error messages if a custom alias is already taken.

---

## 🐳 Chapter 5: Shipping it to Docker (Containerization)
Running code locally works, but what if you want to run this application on another computer or server without setting up Postgres and Python manually? That's where **Docker** comes in.

We created two files to package the application:

### 1. The `requirements.txt` & `Dockerfile`
A `Dockerfile` is a recipe to build a custom container for the Flask web application:
- It pulls a lightweight Python image.
- It installs our required Python packages (`Flask` and `psycopg2-binary`).
- It copies our code and templates, and configures the container to run `python app.py` on port `5001`.

### 2. The `docker-compose.yml`
A Docker Compose file orchestrates multiple containers so they run together. It sets up two services:
1. **`db` (Postgres Container)**:
   - Uses the official `postgres` database image.
   - Configures the database name to `url_shortener`.
   - **Important Detail**: It copies our `init.sql` file into a special directory (`/docker-entrypoint-initdb.d/`) inside the container. PostgreSQL automatically runs any scripts in this directory on startup!
   - Maps the database to host port `5433` (instead of standard `5432`). This ensures that if you already have Postgres.app running on your Mac, they won't fight over the same port.
2. **`web` (Flask Container)**:
   - Builds the Python container from our `Dockerfile`.
   - Maps port `5001` to your computer.
   - Connects to the `db` service using environment variables so they can talk to each other.

---

## 🚀 How to Run the App (Two Ways)

### Way 1: Running in Docker (Recommended)
This runs the entire app (database + web server) inside isolated containers:

1. **Start the containers**:
   ```bash
   docker-compose up --build
   ```
2. **Access the application**:
   Open **[http://127.0.0.1:5001](http://127.0.0.1:5001)**.
3. **Stop the containers**:
   ```bash
   docker-compose down
   ```

### Way 2: Running Locally (No Docker)
This runs the application using your Mac's pre-installed tools:

1. **Make sure your local Postgres.app is running**.
2. **Start the server**:
   ```bash
   python3 app.py
   ```
3. **Access the application**:
   Open **[http://127.0.0.1:5001](http://127.0.0.1:5001)**.
