from services.database import get_connection

connection = get_connection()

columns = connection.execute(
    "PRAGMA table_info(social_reports)"
).fetchall()

for column in columns:
    print(column["name"])

connection.close()