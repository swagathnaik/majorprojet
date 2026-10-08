"""
Simple SQLite Database Inspector for SafeRoute.
Usage:
    python view_db.py                     # Shows summary of all tables
    python view_db.py users               # Shows all rows in 'users'
    python view_db.py emergency_contacts  # Shows contacts
    python view_db.py journeys            # Shows recent journeys
    python view_db.py "SELECT * FROM users" # Runs custom SQL query
"""
import os
import sys
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "saferoute.db")

def connect_db():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at: {DB_PATH}")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)

def show_summary(con):
    cur = con.cursor()
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()
    print("\n" + "=" * 50)
    print("SafeRoute Database Summary (instance/saferoute.db)")
    print("=" * 50)
    for (t_name,) in tables:
        count = cur.execute(f"SELECT count(*) FROM {t_name}").fetchone()[0]
        print(f"  - {t_name:<20} : {count} rows")
    print("=" * 50)
    print("\nTo view a specific table, run:")
    print("  python view_db.py <table_name>")
    print("Example:")
    print("  python view_db.py users")
    print("  python view_db.py emergency_contacts\n")

def show_table_or_query(con, target):
    cur = con.cursor()
    if target.strip().upper().startswith("SELECT"):
        sql = target
    else:
        sql = f"SELECT * FROM {target}"
    
    try:
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    except Exception as e:
        print(f"Error executing query: {e}")
        return

    print(f"\nQuery: {sql}")
    print(f"Found: {len(rows)} row(s)\n")
    if not rows:
        return

    # Print columns
    header = " | ".join(f"{col:<15}" for col in columns)
    print(header)
    print("-" * len(header))
    for row in rows:
        formatted_row = " | ".join(f"{str(val)[:15]:<15}" for val in row)
        print(formatted_row)
    print()

if __name__ == "__main__":
    con = connect_db()
    if len(sys.argv) == 1:
        show_summary(con)
    else:
        show_table_or_query(con, sys.argv[1])
    con.close()
