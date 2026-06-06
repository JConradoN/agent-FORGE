"""Memory search tool for fox-server agent-mesh shared memory."""

import os
import sqlite3
from typing import Optional


def _get_default_db_path() -> str:
    """Retorna o caminho padrão para o banco de dados SQLite do agent-mesh.
    
    Returns:
        Caminho completo para ~/.agent-mesh/state.db
    
    Raises:
        RuntimeError: Se não for possível determinar a home directory.
    """
    home_dir = os.path.expanduser("~")
    if not home_dir or home_dir == "~":
        raise RuntimeError("Unable to determine user's home directory")
    return os.path.join(home_dir, ".agent-mesh", "state.db")


def _connect_to_db(db_path: str) -> sqlite3.Connection | None:
    """Conecta ao banco de dados SQLite se ele existir.
    
    Args:
        db_path: Caminho para o arquivo do banco de dados.
        
    Returns:
        Conexão SQLite ou None se o arquivo não existir.
    """
    if not os.path.exists(db_path):
        return None
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def search_memory(query: str, db_path: Optional[str] = None) -> list[dict]:
    """Busca na shared_memory do agent-mesh por termos similares ao query.
    
    Realiza uma busca LIKE nas colunas 'key' e 'value' da tabela 
    'shared_memory', retornando os 3 melhores resultados com previews
    dos valores truncados para 200 caracteres.
    
    Args:
        query: Termo de busca obrigatório (não pode ser vazio).
        db_path: Caminho opcional para o banco de dados SQLite. Se não 
                 fornecido, usa ~/.agent-mesh/state.db por padrão.
        
    Returns:
        Lista de dicionários com estrutura: [{key, value_preview, agent, updated_at}].
        Retorna lista vazia se o arquivo do banco não existir ou não houver resultados.
        
    Raises:
        ValueError: Se a query for vazia ou apenas espaços em branco.
        
    Example:
        >>> results = search_memory("tarefa importante")
        >>> print(len(results))  # até 3 resultados
        
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
        
        # Busca LIKE em key e value, ordenada por relevância (aproximada via updated_at DESC)
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
