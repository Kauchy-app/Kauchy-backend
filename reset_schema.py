import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Pymarket.settings')
django.setup()

from django.db import connection

print("Dropping public schema...")
with connection.cursor() as cursor:
    cursor.execute("DROP SCHEMA public CASCADE;")
    cursor.execute("CREATE SCHEMA public;")
    cursor.execute("GRANT ALL ON SCHEMA public TO postgres;")
    cursor.execute("GRANT ALL ON SCHEMA public TO public;")

print("Schema dropped and recreated successfully!")
