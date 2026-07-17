import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template, redirect
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# Database configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "url_shortener")
DB_USER = os.environ.get("DB_USER", "abhinovreddy0114")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

# Initialize connection pool
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
except Exception as e:
    print(f"Error initializing PostgreSQL connection pool: {e}")
    db_pool = None

def get_db_connection():
    if db_pool is None:
        raise Exception("Database connection pool is not initialized")
    return db_pool.getconn()

def release_db_connection(conn):
    if db_pool and conn:
        db_pool.putconn(conn)

@app.teardown_appcontext
def close_db_connections(exception):
    # This ensures connections are cleaned up if thread-bound (not strictly needed with SimpleConnectionPool, but good practice)
    pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/urls', methods=['POST'])
def create_short_url():
    data = request.get_json() or {}
    
    long_url = data.get('long_url', '').strip()
    custom_alias = data.get('custom_alias', '').strip() or None
    expiration_date_raw = data.get('expiration_date', '').strip() or None

    if not long_url:
        return jsonify({"error": "Long URL is required"}), 400

    # Parse expiration date if provided
    expiration_date = None
    if expiration_date_raw:
        try:
            # HTML datetime-local format: YYYY-MM-DDTHH:MM
            # Standard ISO formats: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD
            if 'T' in expiration_date_raw:
                expiration_date = datetime.fromisoformat(expiration_date_raw)
            else:
                expiration_date = datetime.strptime(expiration_date_raw, "%Y-%m-%d")
        except ValueError as e:
            return jsonify({"error": f"Invalid expiration date format: {e}"}), 400

    conn = None
    try:
        conn = get_db_connection()
        # Use RealDictCursor to get results as key-value dictionaries
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Call stored function shorten_url
            cur.execute(
                "SELECT * FROM shorten_url(%s, %s, %s);",
                (long_url, custom_alias, expiration_date)
            )
            result = cur.fetchone()
            conn.commit()
            
            if result:
                # Format dates for JSON response
                if result.get('expiration_date'):
                    result['expiration_date'] = result['expiration_date'].isoformat()
                if result.get('created_at'):
                    result['created_at'] = result['created_at'].isoformat()
                return jsonify(result), 201
            else:
                return jsonify({"error": "Failed to create short URL"}), 500
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        # Extract the custom RAISE EXCEPTION message from Postgres
        error_msg = str(e).split('\n')[0]
        # Clean up Postgres prefix if present
        if "EXCEPTION:" in error_msg:
            error_msg = error_msg.split("EXCEPTION:")[1].strip()
        return jsonify({"error": error_msg}), 400
    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)

@app.route('/<short_code>', methods=['GET'])
def redirect_to_long_url(short_code):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Call stored function resolve_url
            cur.execute("SELECT resolve_url(%s);", (short_code,))
            result = cur.fetchone()
            
            # If the database function returns a URL, redirect 302
            if result and result[0]:
                long_url = result[0]
                # Ensure long_url has a protocol schema
                if not (long_url.startswith('http://') or long_url.startswith('https://')):
                    long_url = 'http://' + long_url
                return redirect(long_url, code=302)
            else:
                return render_template('404.html'), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            release_db_connection(conn)

if __name__ == '__main__':
    # Run application
    app.run(host='0.0.0.0', port=5001, debug=True)
