import unittest
import json
from datetime import datetime, timedelta
import psycopg2
from app import app, get_db_connection, release_db_connection

class URLShortenerTestCase(unittest.TestCase):
    def setUp(self):
        # Configure the test client
        self.app = app.test_client()
        self.app.testing = True

        # Clear the database before each test to ensure a clean state
        self.clear_db()

    def tearDown(self):
        # Clear database after each test as well
        self.clear_db()

    def clear_db(self):
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE urls RESTART IDENTITY CASCADE;")
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error cleaning up test database: {e}")
        finally:
            if conn:
                release_db_connection(conn)

    def test_shorten_url_random_code(self):
        # 1. Test shortening URL and receiving a random short code
        response = self.app.post('/urls', 
            data=json.dumps({
                "long_url": "https://www.google.com"
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertIn('short_code', data)
        self.assertEqual(data['long_url'], "https://www.google.com")
        self.assertIsNone(data['custom_alias'])
        self.assertIsNone(data['expiration_date'])
        
        # Verify length of generated code (should be 6 characters)
        self.assertEqual(len(data['short_code']), 6)

    def test_resolve_url_redirect(self):
        # 2. Shorten URL
        shorten_resp = self.app.post('/urls', 
            data=json.dumps({
                "long_url": "https://www.google.com"
            }),
            content_type='application/json'
        )
        short_code = json.loads(shorten_resp.data)['short_code']

        # Resolve URL and check redirection
        response = self.app.get(f'/{short_code}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], "https://www.google.com")

    def test_shorten_url_custom_alias(self):
        # 3. Shorten with custom alias
        alias = "my-custom-link"
        response = self.app.post('/urls', 
            data=json.dumps({
                "long_url": "https://github.com",
                "custom_alias": alias
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['short_code'], alias)
        self.assertEqual(data['custom_alias'], alias)

        # Resolve custom alias
        resolve_resp = self.app.get(f'/{alias}')
        self.assertEqual(resolve_resp.status_code, 302)
        self.assertEqual(resolve_resp.headers['Location'], "https://github.com")

    def test_duplicate_custom_alias_fails(self):
        # 4. Shorten first time
        alias = "taken-alias"
        self.app.post('/urls', 
            data=json.dumps({
                "long_url": "https://github.com",
                "custom_alias": alias
            }),
            content_type='application/json'
        )

        # Shorten second time with duplicate alias
        response = self.app.post('/urls', 
            data=json.dumps({
                "long_url": "https://gitlab.com",
                "custom_alias": alias
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('already taken', data['error'].lower())

    def test_expired_url_returns_404(self):
        # 5. Shorten URL with expiration date in the past
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        response = self.app.post('/urls', 
            data=json.dumps({
                "long_url": "https://expired.com",
                "expiration_date": past_time
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        short_code = json.loads(response.data)['short_code']

        # Try to resolve expired URL
        resolve_resp = self.app.get(f'/{short_code}')
        self.assertEqual(resolve_resp.status_code, 404)

    def test_non_existent_url_returns_404(self):
        # 6. Resolve non-existent short code
        response = self.app.get('/nonexistent')
        self.assertEqual(response.status_code, 404)

    def test_invalid_long_url_fails(self):
        # 7. Empty long_url
        response = self.app.post('/urls', 
            data=json.dumps({
                "long_url": ""
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], "Long URL is required")

    def test_invalid_alias_format_fails(self):
        # 8. Alias with special symbols (unsupported characters)
        response = self.app.post('/urls', 
            data=json.dumps({
                "long_url": "https://google.com",
                "custom_alias": "cool/link!"
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('invalid characters', data['error'].lower())

if __name__ == '__main__':
    unittest.main()
