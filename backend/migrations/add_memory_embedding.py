"""
Migration: Add embedding column to memories table

Run with: python migrations/add_memory_embedding.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import engine


def run_migration():
    """Add embedding column to memories table."""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT COUNT(*) as cnt
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'memories'
            AND COLUMN_NAME = 'embedding'
        """))
        if result.fetchone()[0] > 0:
            print("Column 'embedding' already exists in 'memories' table. Skipping.")
            return

        # Add embedding column (JSON type for storing vector)
        conn.execute(text("""
            ALTER TABLE memories
            ADD COLUMN embedding JSON NULL
            AFTER source_conversation_id
        """))
        conn.commit()
        print("Added 'embedding' column to 'memories' table.")


if __name__ == "__main__":
    run_migration()
