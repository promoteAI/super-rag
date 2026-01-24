

"""
Migration utilities for common operations.
"""

from pathlib import Path
from alembic import op
import sqlalchemy as sa


def execute_sql_file(filename: str):
    """
    Execute a SQL file relative to the migration/sql directory.
    
    Args:
        filename: Name of the SQL file (e.g., "model_configs_init.sql")
    """
    # Get the SQL file path relative to migration directory
    migration_dir = Path(__file__).parent
    sql_file_path = migration_dir / "sql" / filename
    
    if not sql_file_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_file_path}")
    
    # Read and execute the SQL file
    with open(sql_file_path, 'r', encoding='utf-8') as f:
        sql_content = f.read().strip()
    
    if sql_content:
        # Execute the complete SQL script
        op.execute(sa.text(sql_content)) 