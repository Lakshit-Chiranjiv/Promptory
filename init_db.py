"""
One-time script to initialise the SQLite database and verify all 4 tables exist.
Run from project root: python init_db.py
Delete this file after Step 6 is done.
"""

import os
from app.database import Base, engine

# Models MUST be imported before create_all() — importing them registers
# each class with Base.metadata so SQLAlchemy knows what tables to create.
import app.models  # noqa: F401

# Create the data/ directory if it doesn't exist yet
os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)

# Creates all tables that are registered with Base.metadata.
# Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS internally.
Base.metadata.create_all(bind=engine)

# Verify by listing all table names SQLAlchemy knows about
tables = Base.metadata.tables.keys()
print("✅ Database initialised. Tables created:")
for t in tables:
    print(f"   • {t}")
