#!/usr/bin/env python3
"""
Migration script to create memories and assets tables.

This script creates the tables needed for the context enhancement system.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def table_exists(db, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = db.execute(text("""
        SELECT COUNT(*) as table_exists
        FROM information_schema.tables
        WHERE table_name = :table_name
        AND table_schema = DATABASE()
    """), {"table_name": table_name})
    return result.fetchone()[0] > 0


def migrate_add_memories_assets():
    """Create memories and assets tables."""

    with SessionLocal() as db:
        try:
            # Create memories table
            if not table_exists(db, "memories"):
                logger.info("Creating memories table...")

                db.execute(text("""
                    CREATE TABLE memories (
                        memory_id INT PRIMARY KEY AUTO_INCREMENT,
                        user_id INT NOT NULL,
                        memory_type ENUM('working', 'fact', 'preference', 'entity', 'project') NOT NULL,
                        category VARCHAR(100) NULL,
                        content TEXT NOT NULL,
                        source_conversation_id INT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NULL,
                        last_accessed_at TIMESTAMP NULL,
                        access_count INT DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        is_pinned BOOLEAN DEFAULT FALSE,
                        confidence FLOAT DEFAULT 1.0,
                        FOREIGN KEY (user_id) REFERENCES users(user_id),
                        FOREIGN KEY (source_conversation_id) REFERENCES conversations(conversation_id) ON DELETE SET NULL,
                        INDEX idx_user_id (user_id),
                        INDEX idx_memory_type (memory_type),
                        INDEX idx_is_active (is_active),
                        INDEX idx_is_pinned (is_pinned)
                    )
                """))
                db.commit()
                logger.info("memories table created successfully")
            else:
                logger.info("memories table already exists")

            # Create assets table
            if not table_exists(db, "assets"):
                logger.info("Creating assets table...")

                db.execute(text("""
                    CREATE TABLE assets (
                        asset_id INT PRIMARY KEY AUTO_INCREMENT,
                        user_id INT NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        asset_type ENUM('file', 'document', 'data', 'code', 'link') NOT NULL,
                        mime_type VARCHAR(100) NULL,
                        content TEXT NULL,
                        file_path VARCHAR(500) NULL,
                        external_url VARCHAR(500) NULL,
                        description TEXT NULL,
                        tags JSON,
                        extra_data JSON,
                        is_in_context BOOLEAN DEFAULT FALSE,
                        context_summary TEXT NULL,
                        source_conversation_id INT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(user_id),
                        FOREIGN KEY (source_conversation_id) REFERENCES conversations(conversation_id) ON DELETE SET NULL,
                        INDEX idx_user_id (user_id),
                        INDEX idx_asset_type (asset_type),
                        INDEX idx_is_in_context (is_in_context)
                    )
                """))
                db.commit()
                logger.info("assets table created successfully")
            else:
                logger.info("assets table already exists")

            # Show table structures
            for table_name in ["memories", "assets"]:
                if table_exists(db, table_name):
                    result = db.execute(text("""
                        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                        FROM information_schema.columns
                        WHERE table_name = :table_name
                        AND table_schema = DATABASE()
                        ORDER BY ORDINAL_POSITION
                    """), {"table_name": table_name})

                    logger.info(f"\n{table_name} table structure:")
                    for row in result:
                        logger.info(f"  {row[0]}: {row[1]} (Nullable: {row[2]})")

        except Exception as e:
            logger.error(f"Error during migration: {e}")
            db.rollback()
            raise

        logger.info("\nMigration completed successfully")


if __name__ == "__main__":
    migrate_add_memories_assets()
