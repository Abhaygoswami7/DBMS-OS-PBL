"""
Database Initialization Script
Project: Smart Polling Booth & Time-Slot Allocation Platform (One Nation One Election)
Description: Connects to MySQL 8.0+, executes schema.sql (tables, triggers, stored procedures, views)
             and seed_data.sql (synthetic demo voters, slots, booths).
"""

import os
import sys
import re
from pathlib import Path

# Try to load dotenv if available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        # Fall back to .env.example if .env doesn't exist yet
        example_env = Path(__file__).resolve().parent.parent / '.env.example'
        if example_env.exists():
            load_dotenv(dotenv_path=example_env)
except ImportError:
    pass

def get_connection():
    """Establish connection to MySQL server using mysql-connector or pymysql."""
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    
    # First try mysql.connector
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            autocommit=True
        )
        return conn, "mysql-connector"
    except ImportError:
        pass

    # Then try pymysql
    try:
        import pymysql
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            autocommit=True
        )
        return conn, "pymysql"
    except ImportError:
        pass

    return None, None

def parse_sql_file(file_path):
    """
    Parses a SQL script containing DELIMITER commands ($$, //) into individual executable statements.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    statements = []
    current_delimiter = ";"
    lines = content.splitlines()
    buffer = []

    for line in lines:
        stripped = line.strip()

        # Check for DELIMITER change
        if stripped.upper().startswith("DELIMITER"):
            parts = stripped.split()
            if len(parts) >= 2:
                current_delimiter = parts[1]
            continue

        # Ignore standalone single-line comments in top level
        if stripped.startswith("--") and not buffer:
            continue

        buffer.append(line)

        # Check if buffer ends with current delimiter
        joined = "\n".join(buffer).rstrip()
        if joined.endswith(current_delimiter):
            # Strip delimiter from statement
            stmt = joined[:-len(current_delimiter)].strip()
            if stmt:
                statements.append(stmt)
            buffer = []

    if buffer:
        remaining = "\n".join(buffer).strip()
        if remaining:
            statements.append(remaining)

    return statements

def execute_statements(cursor, statements, filename):
    """Executes a list of SQL statements with error tracking."""
    success_count = 0
    error_count = 0

    print(f"\n[*] Executing {filename} ({len(statements)} statements)...")
    for idx, stmt in enumerate(statements, 1):
        clean_stmt = stmt.strip()
        if not clean_stmt:
            continue
        try:
            cursor.execute(clean_stmt)
            success_count += 1
        except Exception as e:
            # Print condensed error
            error_count += 1
            first_line = clean_stmt.splitlines()[0][:60]
            print(f"  [!] Statement #{idx} Failed: '{first_line}...' -> {e}")

    print(f"  [+] Completed {filename}: {success_count} succeeded, {error_count} failed.")
    return success_count, error_count

def run_init():
    print("=" * 70)
    print(" SMART POLLING BOOTH & TIME-SLOT ALLOCATION PLATFORM (ONOE)")
    print(" Database Migration & Synthetic Seed Initialization")
    print("=" * 70)

    db_dir = Path(__file__).resolve().parent
    schema_file = db_dir / "schema.sql"
    seed_file = db_dir / "seed_data.sql"

    if not schema_file.exists():
        print(f"[!] Error: schema.sql not found at {schema_file}")
        sys.exit(1)

    conn, driver = get_connection()
    if not conn:
        print("[!] Error: Neither 'mysql.connector' nor 'pymysql' is installed.")
        print("    Please install dependencies: pip install -r requirements.txt")
        sys.exit(1)

    print(f"[+] Connected to MySQL using {driver} driver.")
    cursor = conn.cursor()

    # Parse and execute schema
    schema_statements = parse_sql_file(schema_file)
    _, schema_err = execute_statements(cursor, schema_statements, "schema.sql")

    # Parse and execute seed data if present
    seed_err = 0
    if seed_file.exists():
        seed_statements = parse_sql_file(seed_file)
        _, seed_err = execute_statements(cursor, seed_statements, "seed_data.sql")
    else:
        print(f"[-] No seed_data.sql found at {seed_file}. Skipping seed step.")

    if schema_err > 0 or seed_err > 0:
        print(f"\n[!] Database initialization failed with {schema_err + seed_err} errors.")
        cursor.close()
        conn.close()
        sys.exit(1)

    # Verification summary
    print("\n" + "=" * 70)
    print(" VERIFICATION SUMMARY: Core Table Row Counts")
    print("=" * 70)
    
    tables = [
        "states", "constituencies", "polling_stations", "polling_booths",
        "election_events", "time_slots", "voters", "slot_allocations",
        "simulated_verifications", "crowd_telemetry", "os_concurrency_audit"
    ]

    cursor.execute("USE `smart_poll_allocation_db`;")
    for tbl in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
            count = cursor.fetchone()[0]
            print(f"  - {tbl:<28}: {count:>5} records")
        except Exception as e:
            print(f"  - {tbl:<28}: [ERROR] {e}")

    cursor.close()
    conn.close()
    print("\n[+] Database setup completed successfully.")

if __name__ == "__main__":
    run_init()
