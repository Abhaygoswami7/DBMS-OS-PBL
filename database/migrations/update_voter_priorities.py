import os, sys
sys.path.insert(0, os.getcwd())

from database.db_pool import db_pool

def migrate_voter_priorities():
    mapping = {
        'PREGNANT_WOMEN': 1,
        'PERSON_WITH_DISABILITY': 2,
        'SENIOR_CITIZEN': 3,
        'GENERAL': 4
    }
    with db_pool.get_cursor() as (conn, cursor):
        for category, priority in mapping.items():
            cursor.execute(
                "UPDATE voters SET priority_level = %s WHERE special_category = %s;",
                (priority, category)
            )
        conn.commit()
        
        cursor.execute("SELECT special_category, priority_level, COUNT(*) as cnt FROM voters GROUP BY special_category, priority_level ORDER BY priority_level;")
        rows = cursor.fetchall()
        print("Updated voter priorities in DB:")
        for r in rows:
            print(f"  {r['special_category']} -> Priority {r['priority_level']} (Count: {r['cnt']})")

if __name__ == '__main__':
    migrate_voter_priorities()
