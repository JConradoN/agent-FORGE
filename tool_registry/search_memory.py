"""Memory search tool for fox-server agent-mesh shared memory."""

import os
import sqlite3
from typing import Optional


def _get_default_db_path() -> str:
    """Returns the default path for the agent-mesh SQLite database.
    
    Returns:
        Full path to ~/.agent-mesh/state.db
    
    Raises:
        RuntimeError: If it's not possible to determine the home directory.
    """
    home_dir = os.path.expanduser("~")
    if not home_dir or home_dir == "~":
        raise RuntimeError("Unable to determine user's home directory")
    return os.path.join(home_dir, ".agent-mesh", "state.db")


def _connect_to_db(db_path: str) -> sqlite3.Connection | None:
    """Connects to the SQLite database if it exists.
    
    Args:
        db_path: Path to the database file.
        
    Returns:
        SQLite connection or None if the file does not exist.
    """
    if not os.path.exists(db_path):
        return None
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def search_memory(query: str, db_path: Optional[str] = None) -> list[dict]:
    """Searches the agent-mesh shared_memory for terms similar to the query.
    
    Performs a LIKE search on the 'key' and 'value' columns of the 
    'shared_memory' table, returning the top 3 results with value previews 
    truncated to 200 characters.
    
    Args:
        query: Mandatory search term (cannot be empty).
        db_path: Optional path to the SQLite database. If not 
                 provided, uses ~/.agent-mesh/state.db by default.
        
    Returns:
        List of dictionaries with structure: [{key, value_preview, agent, updated_at}].
        Returns an empty list if the database file does not exist or there are no results.
        
    Raises:
        ValueError: If the query is empty or just whitespace.
        
    Example:
        >>> results = search_memory("important task")
        >>> print(len(results))  # up to 3 results
        
        >>> from mypath import db_file
        >>> custom_results = search_memory("config", "/custom/path/db.sqlite")
    """
    if not query or not query.strip():
        raise ValueError("query cannot be empty")
    
    actual_db_path = db_path if db_path else _get_default_db_path()
    conn = _connect_to_db(actual_db_path)
    
    if conn is None:
        return []
    
    try:
        cursor = conn.cursor()
        
        # LIKE search in key and value, ordered by relevance (approximated via updated_at DESC)
        search_pattern = f"%{query}%"
        sql_query = """
            SELECT 
                key,
                substr(value, 1, 200) as value_preview,
                agent,
                datetime(updated_at, 'unixepoch') as updated_at
            FROM shared_memory
            WHERE (key LIKE ? ESCAPE '\\' OR value LIKE ? ESCAPE '\\')
            ORDER BY 
                CASE WHEN key LIKE ? THEN 1 ELSE 3 END,
                CASE WHEN value LIKE ? THEN 2 ELSE 4 END DESC,
                updated_at DESC
            LIMIT 3;
        """
        
        cursor.execute(sql_query, (search_pattern, search_pattern, f"%{query}%", search_pattern))
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            results.append({
                "key": row["key"],
                "value_preview": row["value_preview"],
                "agent": row["agent"],
                "updated_at": row["updated_at"]
            })
            
        return results
        
    finally:
        conn.close()
