import logging
from authlib.integrations.requests_client import OAuth2Session
import psycopg2
from datetime import datetime
from flask import Flask

import os

log_dir = "Logs"
os.makedirs(log_dir, exist_ok=True)  # Create the Logs directory if it doesn't exist
log_file_path = os.path.join(log_dir, "whoop_fetch_and_store_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")


# User credentials for WHOOP API
USERNAME = "WHOOP_USERNAME"
PASSWORD = "WHOOP_PASSWORD"

# Database configuration for connecting to PostgreSQL
DB_CONFIG = {
        "database": "health_monitor_whoop",
        "user": "USERNAME",
        "password": "PASSWORD",
        "host": "PUBLIC_IP_OF_YOUR_DB",
        "port": "5432"
    }

class WhoopClient:
    """A client for interacting with the WHOOP API."""

    AUTH_URL = "https://api-7.whoop.com"
    REQUEST_URL = "https://api.prod.whoop.com/developer"
    TOKEN_ENDPOINT_AUTH_METHOD = "password_json"

    def __init__(self, username, password):
        # Initialize with user credentials and set up OAuth2 session
        self.username = username
        self.password = password
        self.session = OAuth2Session(
            token_endpoint=f"{self.AUTH_URL}/oauth/token",
            token_endpoint_auth_method=self.TOKEN_ENDPOINT_AUTH_METHOD,
        )
        # Register custom authentication method for password grant
        self.session.register_client_auth_method(("password_json", self._auth_password_json))
        self.user_id = None
        self.authenticate()

    def _auth_password_json(self, _client, _method, uri, headers, body):
        """Custom auth method to handle JSON body for password grant."""
        import json
        from authlib.common.urls import extract_params
        body = json.dumps(dict(extract_params(body)))
        headers["Content-Type"] = "application/json"
        return uri, headers, body

    def authenticate(self):
        """Authenticate the client and fetch the access token."""
        logging.info("Authenticating with WHOOP API...")
        token = self.session.fetch_token(
            url=f"{self.AUTH_URL}/oauth/token",
            username=self.username,
            password=self.password,
            grant_type="password",
        )
        # Extract user ID from the token
        self.user_id = token.get("user", {}).get("id", "")
        logging.info(f"Authenticated successfully! User ID: {self.user_id}")

    def make_request(self, method, endpoint, params=None):
        """Make a single API request to the specified endpoint."""
        url = f"{self.REQUEST_URL}/{endpoint}"
        response = self.session.request(method, url, params=params)
        response.raise_for_status()  # Raise an error for HTTP issues
        return response.json()

    def _make_paginated_request(self, method, endpoint, params=None, max_records=500):
        """Handle paginated API requests to fetch a specified number of records."""
        if params is None:
            params = {}
        all_records = []
        count = 0

        # Loop through paginated results
        while count < max_records:
            response = self.make_request(method, endpoint, params)
            records = response.get("records", [])
            all_records.extend(records)

            count += len(records)
            # Stop if no more records or max_records reached
            if count >= max_records or not response.get("next_token"):
                break

            params["next_token"] = response.get("next_token")

        return all_records[:max_records]

    # API Endpoints
    def get_profile(self):
        """Fetch basic user profile data."""
        return self.make_request("GET", "v1/user/profile/basic")

    def get_body_measurement(self):
        """Fetch body measurement data."""
        return self.make_request("GET", "v1/user/measurement/body")

    def get_cycle_collection(self, start_date=None, end_date=None):
        """Fetch cycle data within a date range."""
        params = {}
        if start_date:
            params["filter"] = f"start={start_date}T00:00:00.000Z"
        if end_date:
            params["filter"] += f"&end={end_date}T00:00:00.000Z"
        return self._make_paginated_request("GET", "v1/cycle", params)

    def get_recovery_collection(self, start_date=None, end_date=None):
        """Fetch recovery data within a date range."""
        params = {}
        if start_date:
            params["filter"] = f"start={start_date}T00:00:00.000Z"
        if end_date:
            params["filter"] += f"&end={end_date}T00:00:00.000Z"
        return self._make_paginated_request("GET", "v1/recovery", params)

    def get_sleep_collection(self, start_date=None, end_date=None):
        """Fetch sleep data within a date range."""
        params = {}
        if start_date:
            params["filter"] = f"start={start_date}T00:00:00.000Z"
        if end_date:
            params["filter"] += f"&end={end_date}T00:00:00.000Z"
        return self._make_paginated_request("GET", "v1/activity/sleep", params)

    def get_workout_collection(self, start_date=None, end_date=None):
        """Fetch workout data within a date range."""
        params = {}
        if start_date:
            params["filter"] = f"start={start_date}T00:00:00.000Z"
        if end_date:
            params["filter"] += f"&end={end_date}T00:00:00.000Z"
        return self._make_paginated_request("GET", "v1/activity/workout", params)

    # Database storage methods
    def store_user(self, data, db_config):
        """Store user profile data in the database."""
        try:
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (user_id, first_name, last_name, email)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (
                data.get("user_id"),
                data.get("first_name"),
                data.get("last_name"),
                data.get("email")
            ))
            conn.commit()
            cursor.close()
            conn.close()
            logging.info("User data stored successfully!")
        except Exception as e:
            logging.error(f"Error storing user data: {e}")

    def store_body_measurements(self, data, db_config):
        """Store body measurement data in the database."""
        try:
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO body_measurements (user_id, height_meter, weight_kilogram, max_heart_rate)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (
                self.user_id,
                data.get("height_meter"),
                data.get("weight_kilogram"),
                data.get("max_heart_rate")
            ))
            conn.commit()
            cursor.close()
            conn.close()
            logging.info("Body measurements stored successfully!")
        except Exception as e:
            logging.error(f"Error storing body measurements: {e}")

    def store_cycle_data(self, data, db_config):
        """Store cycle data in the database."""
        try:
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            for record in data:
                cursor.execute("""
                    INSERT INTO cycle_data (cycle_id, user_id, strain, kilojoule, average_heart_rate, max_heart_rate, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (cycle_id) DO NOTHING
                """, (
                    record.get("id"),
                    self.user_id,
                    record.get("score", {}).get("strain", None),
                    record.get("score", {}).get("kilojoule", None),
                    record.get("score", {}).get("average_heart_rate", None),
                    record.get("score", {}).get("max_heart_rate", None),
                    record.get("created_at")
                ))
            conn.commit()
            cursor.close()
            conn.close()
            logging.info("Cycle data stored successfully!")
        except Exception as e:
            logging.error(f"Error storing cycle data: {e}")

    def store_recovery_data(self, data, db_config):
        """Store recovery data in the database."""
        try:
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            for record in data:
                cursor.execute("""
                    INSERT INTO recovery_data (cycle_id, sleep_id, user_id, score_state, recovery_score, resting_heart_rate,
                                               hrv_rmssd_milli, spo2_percentage, skin_temp_celsius, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (cycle_id) DO NOTHING
                """, (
                    record.get("cycle_id"),
                    record.get("sleep_id", None),
                    self.user_id,
                    record.get("score_state", None),
                    record.get("score", {}).get("recovery_score", None),
                    record.get("score", {}).get("resting_heart_rate", None),
                    record.get("score", {}).get("hrv_rmssd_milli", None),
                    record.get("score", {}).get("spo2_percentage", None),
                    record.get("score", {}).get("skin_temp_celsius", None),
                    record.get("created_at"),
                    record.get("updated_at")
                ))
            conn.commit()
            cursor.close()
            conn.close()
            logging.info("Recovery data stored successfully!")
        except Exception as e:
            logging.error(f"Error storing recovery data: {e}")

    def store_sleep_data(self, data, db_config):
        """Store sleep data in the database."""
        try:
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            for record in data:
                cursor.execute("""
                    INSERT INTO sleep_data (user_id, total_sleep_time, rem_sleep_time, deep_sleep_time, efficiency,
                                            timestamp, disturbance_count, light_sleep_time, nap, respiratory_rate)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    self.user_id,
                    record.get("score", {}).get("stage_summary", {}).get("total_in_bed_time_milli", 0) // 60000,
                    record.get("score", {}).get("stage_summary", {}).get("total_rem_sleep_time_milli", 0) // 60000,
                    record.get("score", {}).get("stage_summary", {}).get("total_slow_wave_sleep_time_milli", 0) // 60000,
                    record.get("score", {}).get("sleep_efficiency_percentage", None),
                    record.get("start"),
                    record.get("score", {}).get("stage_summary", {}).get("disturbance_count", 0),
                    record.get("score", {}).get("stage_summary", {}).get("total_light_sleep_time_milli", 0) // 60000,
                    record.get("nap", None),
                    record.get("score", {}).get("respiratory_rate", None)
                ))
            conn.commit()
            cursor.close()
            conn.close()
            logging.info("Sleep data stored successfully!")
        except Exception as e:
            logging.error(f"Error storing sleep data: {e}")

    def store_workout_data(self, data, db_config):
        """Store workout data in the database."""
        try:
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            for record in data:
                cursor.execute("""
                    INSERT INTO workout_data (workout_id, user_id, start, end_time, strain, kilojoule, average_heart_rate,
                                              max_heart_rate, percent_recorded, distance_meter, altitude_gain_meter,
                                              altitude_change_meter, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (workout_id) DO NOTHING
                """, (
                    record.get("id"),
                    self.user_id,
                    record.get("start"),
                    record.get("end", None),
                    record.get("score", {}).get("strain", None),
                    record.get("score", {}).get("kilojoule", None),
                    record.get("score", {}).get("average_heart_rate", None),
                    record.get("score", {}).get("max_heart_rate", None),
                    record.get("score", {}).get("percent_recorded", None),
                    record.get("score", {}).get("distance_meter", 0),
                    record.get("score", {}).get("altitude_gain_meter", 0),
                    record.get("score", {}).get("altitude_change_meter", 0),
                    record.get("created_at", None)
                ))
            conn.commit()
            cursor.close()
            conn.close()
            logging.info("Workout data stored successfully!")
        except Exception as e:
            logging.error(f"Error storing workout data: {e}")



# Create a Flask app
app = Flask(__name__)

@app.route("/", methods=["GET"])
def run_whoop_fetch():
    """Trigger the WHOOP data fetch and store process."""
    try:
        logging.info("Starting WHOOP data fetch and store process.")
        client = WhoopClient(username=USERNAME, password=PASSWORD)

        # Fetch and store user profile
        profile = client.get_profile()
        if profile:
            logging.info("Storing user profile data...")
            client.store_user(profile, DB_CONFIG)

        # Fetch and store body measurements
        body_measurements = client.get_body_measurement()
        if body_measurements:
            logging.info("Storing body measurements...")
            client.store_body_measurements(body_measurements, DB_CONFIG)

        # Fetch and store cycle data
        cycle_data = client.get_cycle_collection(start_date="2024-12-01", end_date="2024-12-12")
        if cycle_data:
            logging.info(f"Storing {len(cycle_data)} cycle records...")
            client.store_cycle_data(cycle_data, DB_CONFIG)

        # Fetch and store recovery data
        recovery_data = client.get_recovery_collection(start_date="2024-12-01", end_date="2024-12-12")
        if recovery_data:
            logging.info(f"Storing {len(recovery_data)} recovery records...")
            client.store_recovery_data(recovery_data, DB_CONFIG)

        # Fetch and store sleep data
        sleep_data = client.get_sleep_collection(start_date="2024-12-01", end_date="2024-12-12")
        if sleep_data:
            logging.info(f"Storing {len(sleep_data)} sleep records...")
            client.store_sleep_data(sleep_data, DB_CONFIG)

        # Fetch and store workout data
        workout_data = client.get_workout_collection(start_date="2024-12-01", end_date="2024-12-12")
        if workout_data:
            logging.info(f"Storing {len(workout_data)} workout records...")
            client.store_workout_data(workout_data, DB_CONFIG)

        logging.info("WHOOP data fetch and store process completed successfully.")
        return "WHOOP data fetch and store process completed successfully!", 200

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return f"Error: {e}", 500

if __name__ == "__main__":
    # Start the Flask app
    app.run(host="0.0.0.0", port=8080, debug=True)
    