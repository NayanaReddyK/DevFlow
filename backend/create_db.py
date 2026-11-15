
import getpass
import psycopg
from psycopg import sql

password = getpass.getpass("PostgreSQL password: ")

try:
    with psycopg.connect(
        dbname="postgres",
        user="postgres",
        password=password,
        host="localhost",
        port=5432,
        autocommit=True
    ) as connection:

        with connection.cursor() as cursor:

            # Close existing connections to devflow
            cursor.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = 'devflow'
                AND pid <> pg_backend_pid();
            """)

            # Drop the old database
            cursor.execute(
                sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier("devflow")
                )
            )

            # Create a fresh database
            cursor.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier("devflow"),
                    sql.Identifier("postgres")
                )
            )

        print("DevFlow database recreated successfully!")

except psycopg.Error as error:
    print("Database operation failed:", error)
