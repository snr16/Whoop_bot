# WHOOP Data Fetch and Store System

## Overview

The **WHOOP Data Fetch and Store System** is a Flask-based Python application that interacts with the **WHOOP API** to fetch health data and store it into a PostgreSQL database. The application automates the retrieval and storage of user health information, including:
- **User Profile**
- **Body Measurements**
- **Cycle Data**
- **Recovery Metrics**
- **Sleep Details**
- **Workout Data**

The system ensures that data is retrieved efficiently via API requests and handles pagination, date ranges, and data storage seamlessly.

---

## What the Code Does

1. **Authentication**:
   - Authenticates with the WHOOP API using OAuth2 credentials.

2. **Data Fetching**:
   - Retrieves various types of health data:
     - User profile information
     - Body measurements
     - Activity and sleep metrics
     - Workout data
     - Recovery scores
   - Handles paginated API requests to fetch large datasets.

3. **Data Storage**:
   - Stores the fetched data into corresponding PostgreSQL tables:
     - `users`
     - `body_measurements`
     - `cycle_data`
     - `recovery_data`
     - `sleep_data`
     - `workout_data`

4. **Logging**:
   - Generates detailed log files for monitoring and debugging.

5. **Flask API**:
   - Provides a simple Flask endpoint (`/`) to trigger the data fetching process.

---

## Code Explanation

### Key Components

1. **WHOOP API Client**:
   - The `WhoopClient` class handles:
     - OAuth2 authentication
     - API requests to fetch health data
     - Pagination management

2. **Data Storage**:
   - Methods like `store_user`, `store_cycle_data`, and `store_sleep_data` insert data into PostgreSQL tables.

3. **Flask Web Server**:
   - A Flask API (`/`) triggers the entire data-fetching and storage process when accessed.

4. **Logging**:
   - Logs are stored in a timestamped file within the `Logs` directory.

---

## Setup Instructions

### Prerequisites

1. **Python Environment**:
   - Python 3.8 or higher.

2. **Required Libraries**:
   Install the necessary libraries:
   ```bash
   pip install flask authlib psycopg2-binary requests
   
3. **PostgreSQL Database:**
   - Ensure PostgreSQL is installed and configured.
   - Create the following tables:
```sql
CREATE TABLE users (
    user_id VARCHAR PRIMARY KEY,
    first_name VARCHAR,
    last_name VARCHAR,
    email VARCHAR
);

CREATE TABLE body_measurements (
    user_id VARCHAR PRIMARY KEY,
    height_meter FLOAT,
    weight_kilogram FLOAT,
    max_heart_rate INT
);

CREATE TABLE cycle_data (
    cycle_id VARCHAR PRIMARY KEY,
    user_id VARCHAR,
    strain FLOAT,
    kilojoule FLOAT,
    average_heart_rate INT,
    max_heart_rate INT,
    created_at TIMESTAMP
);

CREATE TABLE recovery_data (
    cycle_id VARCHAR PRIMARY KEY,
    user_id VARCHAR,
    recovery_score FLOAT,
    resting_heart_rate FLOAT,
    hrv_rmssd_milli FLOAT,
    created_at TIMESTAMP
);

CREATE TABLE sleep_data (
    user_id VARCHAR,
    total_sleep_time INT,
    rem_sleep_time INT,
    deep_sleep_time INT,
    efficiency FLOAT,
    timestamp TIMESTAMP,
    nap BOOLEAN,
    respiratory_rate FLOAT
);

CREATE TABLE workout_data (
    workout_id VARCHAR PRIMARY KEY,
    user_id VARCHAR,
    start TIMESTAMP,
    strain FLOAT,
    kilojoule FLOAT,
    average_heart_rate FLOAT,
    max_heart_rate FLOAT,
    distance_meter FLOAT,
    created_at TIMESTAMP
);
```

4. **WHOOP API Credentials:**
    - Obtain the API credentials (Username and Password).

# How to Set Up

1. **Configure the Application:**
    - Replace the following placeholders in the script:
        - Username and Password for WHOOP API:
        ```bash
        USERNAME = "your_email@example.com"
        PASSWORD = "your_password"

    - PostgreSQL database credentials in `DB_CONFIG`:
    ```bash
    DB_CONFIG = {
    "database": "health_monitor_whoop",
    "user": "your_postgres_user",
    "password": "your_postgres_password",
    "host": "your_postgres_host",
    "port": "5432"
    }

2. **Install Dependencies:** Install all necessary libraries:
    ```bash
    pip install flask authlib psycopg2-binary requests



# How to Run the Application
## Option 1:
1. **Run the Flask Server**: Execute the following command:

    ```bash
    python whoop_fetch_and_store.py
    ```

2. **Trigger Data Fetch**: Open a browser or API client and access the following URL:

    ```arduino
    http://localhost:8080/
    ```

3. **Verify the Logs**: Logs will be saved in the `Logs` directory with a timestamped filename:

    ```bash
    Logs/whoop_fetch_and_store_YYYYMMDD_HHMMSS.log
    ```

4. **Check the PostgreSQL Database**: Verify that data has been inserted into the corresponding tables.




# Example Output

### Logs:
    
    [INFO] Authenticating with WHOOP API...
    [INFO] Authenticated successfully! User ID: 12345678
    [INFO] Fetching body measurements...
    [INFO] Storing body measurements...
    [INFO] Fetching sleep data...
    [INFO] Storing sleep data...
    [INFO] WHOOP data fetch and store process completed successfully!

### **Database Verification:** Example query:
    
    
    SELECT * FROM cycle_data LIMIT 5;



# Troubleshooting

1. **Database Connection Errors**:
   - Ensure PostgreSQL is running and accessible.
   - Verify database credentials.

2. **WHOOP API Authentication Errors**:
   - Check your WHOOP credentials (username/password).

3. **Missing Libraries**:
   - Install the required libraries:

     ```bash
     pip install -r requirements.txt
     ```

4. **API Errors**:
   - Review the logs in the `Logs` directory for detailed error messages.

---
## Option 2:
# Run Manually

1. Double-click the batch file `run_whoop_fetch.bat`.
2. The script will run, fetch the WHOOP data, and store it in the database.
3. Logs will be saved in the `Logs/` directory.

---

# Batch File: `run_whoop_fetch.bat`

Place the following content in a file named `run_whoop_fetch.bat` in the project directory:

    ```batch
    @echo off
    echo Starting WHOOP Fetch and Store Script...
    python whoop_fetch_and_store.py
    echo Script Execution Completed.
    pause


# Schedule with Windows Task Scheduler

1. **Open Task Scheduler**:
   - Press `Win + R`, type `taskschd.msc`, and press Enter.

2. **Create Basic Task**:
   - Click on “Create Basic Task” and provide a name and description.

3. **Set Trigger**:
   - Choose a schedule (Daily, Weekly, etc.) as per your preference.

4. **Set Action**:
   - Select **Start a Program**.
   - Browse and select the `run_whoop_fetch.bat` file.

5. **Finish**:
   - Save the task, and it will automatically run the batch file at the scheduled time.

---

# Example Output

## Logs:
    ```csharp
    [INFO] Authenticating with WHOOP API...
    [INFO] Authenticated successfully! User ID: 12345678
    [INFO] Fetching sleep data...
    [INFO] Storing sleep data...
    [INFO] WHOOP data fetch and store process completed successfully!


### **Database Verification:** Example query:
    
    
    SELECT * FROM sleep_data LIMIT 5;


# Troubleshooting

1. **Batch File Does Not Run**:
   - Ensure Python is added to the system `PATH`.

2. **Database Connection Errors**:
   - Verify your PostgreSQL credentials and ensure the database server is running.

3. **API Authentication Errors**:
   - Check your WHOOP credentials (username/password).

4. **Task Scheduler Errors**:
   - Ensure the batch file path is correct and accessible.
---



### How to Use:
1. Copy this content.
2. Save it into a file named **`README.md`** in the project directory.
3. Replace placeholders like `your_email@example.com` and `your_postgres_user` with your credentials. 

This markdown provides everything from **setup**, **code explanation**, and **troubleshooting** in a single structured file.

---

### Key Notes:
1. **Batch File Section**: A section about `run_whoop_fetch.bat` is included with content and usage instructions.
2. **Windows Task Scheduler**: Detailed steps are provided for scheduling the script using Windows Task Scheduler.
3. **Single Markdown File**: The entire content is structured into a single, organized **`README.md`** file. 

Copy the above markdown content into your `README.md` file.

## License
This project is licensed under the MIT License.