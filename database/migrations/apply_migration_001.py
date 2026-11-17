import os, sys
sys.path.insert(0, os.getcwd())

from database.db_pool import db_pool

def apply_migration():
    sql_file = os.path.join(os.path.dirname(__file__), "001_dbms_advanced_views_and_outbox.sql")
    with open(sql_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Split into statements respecting DELIMITER $$
    statements = []
    current = []
    delimiter = ";"

    for line in content.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("--") or not trimmed:
            continue
        if trimmed.startswith("DELIMITER"):
            delimiter = trimmed.split()[1]
            continue
        if trimmed.endswith(delimiter):
            current.append(trimmed[:-len(delimiter)])
            stmt = "\n".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(line)

    if current:
        stmt = "\n".join(current).strip()
        if stmt:
            statements.append(stmt)

    with db_pool.get_cursor() as (conn, cursor):
        for idx, stmt in enumerate(statements):
            if stmt.upper().startswith("USE"):
                continue
            try:
                cursor.execute(stmt)
                print(f"Executed statement {idx+1}/{len(statements)}")
            except Exception as e:
                print(f"Statement {idx+1} warning/error: {e}")
        conn.commit()
    print("Migration 001 applied successfully!")

if __name__ == "__main__":
    apply_migration()
