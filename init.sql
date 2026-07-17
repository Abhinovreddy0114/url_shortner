-- init.sql: Database schema and stored functions for URL Shortener

-- 1. Create table `urls`
CREATE TABLE IF NOT EXISTS urls (
    -- short_code is VARCHAR(50) to support custom aliases up to 50 characters as short_code.
    short_code VARCHAR(50) PRIMARY KEY,
    long_url TEXT NOT NULL,
    custom_alias VARCHAR(50) UNIQUE NULL,
    expiration_date TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for expiration checking and alias lookups
CREATE INDEX IF NOT EXISTS idx_urls_expiration ON urls(expiration_date);

-- 2. Utility Function: Generate a random Base62 string of a given length
CREATE OR REPLACE FUNCTION generate_random_base62(length INT) 
RETURNS TEXT AS $$
DECLARE
    chars TEXT := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';
    result TEXT := '';
    i INT;
BEGIN
    FOR i IN 1..length LOOP
        result := result || substr(chars, floor(random() * 62)::integer + 1, 1);
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- 3. Stored Function: shorten_url
-- Accepts long_url, custom_alias (optional), and expiration_date (optional).
-- Returns the inserted urls record.
CREATE OR REPLACE FUNCTION shorten_url(
    p_long_url TEXT,
    p_custom_alias VARCHAR(50) DEFAULT NULL,
    p_expiration_date TIMESTAMP DEFAULT NULL
) 
RETURNS urls AS $$
DECLARE
    v_short_code VARCHAR(50);
    v_ret urls;
    v_collision_count INT := 0;
    v_max_attempts INT := 20;
BEGIN
    -- Validate long URL
    IF p_long_url IS NULL OR p_long_url = '' THEN
        RAISE EXCEPTION 'Long URL cannot be empty';
    END IF;

    -- Handle Custom Alias
    IF p_custom_alias IS NOT NULL AND p_custom_alias <> '' THEN
        -- Standardize input (trim spaces)
        p_custom_alias := trim(p_custom_alias);
        
        -- Check if custom alias contains invalid characters (we allow alphanumeric, dash, underscore)
        IF p_custom_alias !~ '^[a-zA-Z0-9\-_]+$' THEN
            RAISE EXCEPTION 'Custom alias contains invalid characters. Only alphanumeric, dashes, and underscores are allowed.';
        END IF;

        -- Check for uniqueness: must not exist as short_code or custom_alias in the database
        IF EXISTS (
            SELECT 1 FROM urls 
            WHERE short_code = p_custom_alias OR custom_alias = p_custom_alias
        ) THEN
            RAISE EXCEPTION 'Alias % is already taken', p_custom_alias;
        END IF;
        
        v_short_code := p_custom_alias;
    ELSE
        -- Generate a unique, pseudo-random Base62 string (6-7 characters)
        LOOP
            IF v_collision_count < 10 THEN
                v_short_code := generate_random_base62(6);
            ELSE
                v_short_code := generate_random_base62(7);
            END IF;

            -- Check for uniqueness
            IF NOT EXISTS (
                SELECT 1 FROM urls 
                WHERE short_code = v_short_code OR custom_alias = v_short_code
            ) THEN
                EXIT;
            END IF;

            v_collision_count := v_collision_count + 1;
            IF v_collision_count >= v_max_attempts THEN
                RAISE EXCEPTION 'Failed to generate a unique short code after % attempts', v_max_attempts;
            END IF;
        END LOOP;
        
        -- Since custom_alias was not provided, keep custom_alias column as NULL
        p_custom_alias := NULL;
    END IF;

    -- Insert record into the database
    INSERT INTO urls (short_code, long_url, custom_alias, expiration_date)
    VALUES (v_short_code, p_long_url, p_custom_alias, p_expiration_date)
    RETURNING * INTO v_ret;

    RETURN v_ret;
END;
$$ LANGUAGE plpgsql;

-- 4. Stored Function: resolve_url
-- Accepts short_code.
-- Returns long_url if found and not expired; returns NULL otherwise.
CREATE OR REPLACE FUNCTION resolve_url(p_short_code VARCHAR(50)) 
RETURNS TEXT AS $$
DECLARE
    v_long_url TEXT;
    v_expiration_date TIMESTAMP;
BEGIN
    SELECT long_url, expiration_date INTO v_long_url, v_expiration_date
    FROM urls
    WHERE short_code = p_short_code;

    -- If not found, return NULL
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    -- If expired, return NULL
    IF v_expiration_date IS NOT NULL AND v_expiration_date < CURRENT_TIMESTAMP THEN
        RETURN NULL;
    END IF;

    RETURN v_long_url;
END;
$$ LANGUAGE plpgsql;
