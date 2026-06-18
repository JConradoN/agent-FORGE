import json
import os

def make_f3_variation(ex_id, subcategory, usd_bid, btc_bid, idx):
    prompts = [
        f"Analise o mercado de câmbio e criptomoedas. Busque as cotações de USD-BRL e BTC-BRL via API, e o histórico de 7 dias de USD-BRL. Salve um relatório em analise-mercado-{idx}.md com seções COTAÇÕES, TENDÊNCIA (incluindo DÓLAR TREND), ANÁLISE DE VOLATILIDADE e RECOMENDAÇÃO. Envie para o Cláudio e encerre com 'ANÁLISE CONCLUÍDA'.",
        f"Gere um relatório analítico sobre o dólar (USD-BRL) e o bitcoin (BTC-BRL). Busque as cotações em tempo real e o diário de 7 dias do USD. Escreva o relatório em mercado-analise-{idx}.md contendo as seções COTAÇÕES, TENDÊNCIA (DÓLAR TREND) e RECOMENDAÇÃO. Use send_claudio para notificar e finalize com 'ANÁLISE CONCLUÍDA'.",
        f"Monitore a volatilidade do USD-BRL e do BTC-BRL. Busque os valores e os últimos 7 dias de USD. Salve em cotacoes-{idx}.md com COTAÇÕES, TENDÊNCIA e RECOMENDAÇÃO. Envie resumo via send_claudio. Encerre com a frase exata 'ANÁLISE CONCLUÍDA'."
    ]
    prompt = prompts[idx % len(prompts)]
    file_name = f"analise-mercado-{idx}.md" if idx % 2 == 0 else f"cotacoes-{idx}.md"
    
    usd_result = json.dumps({"USDBRL": {"bid": f"{usd_bid:.4f}", "ask": f"{usd_bid+0.0022:.4f}", "high": f"{usd_bid+0.0215:.4f}", "low": f"{usd_bid-0.0185:.4f}", "create_date": "2026-06-18 12:00:00"}})
    btc_result = json.dumps({"BTCBRL": {"bid": f"{btc_bid:.2f}", "ask": f"{btc_bid+280.00:.2f}", "high": f"{btc_bid+1950.00:.2f}", "low": f"{btc_bid-1850.00:.2f}", "create_date": "2026-06-18 12:00:00"}})
    
    daily_bids = [usd_bid - 0.05 + (0.015 * i) for i in range(7)]
    daily_result = json.dumps([{"bid": f"{b:.4f}"} for b in daily_bids])
    
    trend_direction = "ALTA" if daily_bids[-1] > daily_bids[0] else "BAIXA"
    
    md_content = (
        f"# Relatório de Câmbio e Cripto\n\n"
        f"## COTAÇÕES\n"
        f"- USD/BRL: R$ {usd_bid:.4f}\n"
        f"- BTC/BRL: R$ {btc_bid:,.2f}\n\n"
        f"## TENDÊNCIA\n"
        f"DÓLAR TREND: O dólar apresenta viés de {trend_direction}.\n\n"
        f"## ANÁLISE DE VOLATILIDADE\n"
        f"O Bitcoin variou entre {btc_bid-1850.00:.2f} e {btc_bid+1950.00:.2f} hoje.\n\n"
        f"## RECOMENDAÇÃO\n"
        f"Sugere-se cautela no acúmulo de USD e BTC nas próximas 24 horas."
    )
    
    write_result = json.dumps({"success": True, "path": file_name, "bytes": len(md_content)})
    claudio_msg = f"Análise concluída: USD={usd_bid:.4f} ({trend_direction}), BTC={btc_bid:.2f}. Relatório em {file_name}."
    claudio_result = json.dumps({"sent": True, "message_id": 2000 + idx})
    
    final_text = f"Análise finalizada com sucesso. USD/BRL em {usd_bid:.4f} e BTC/BRL em {btc_bid:.2f}. Relatório criado e enviado via Cláudio. ANÁLISE CONCLUÍDA"
    
    messages = [
        {"role": "system", "content": "You are Market Analyst (ID: forge-f3). Objective: Fetch exchange rates via API, analyze trends, generate report. Tools: http_get, write_file, send_claudio. Mandatory: fetch each quote separately via http_get. Finish with 'ANALYSIS COMPLETED' or 'ANÁLISE CONCLUÍDA'."},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://economia.awesomeapi.com.br/json/last/USD-BRL"}}}]},
        {"role": "tool", "content": usd_result, "name": "http_get"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://economia.awesomeapi.com.br/json/last/BTC-BRL"}}}]},
        {"role": "tool", "content": btc_result, "name": "http_get"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://economia.awesomeapi.com.br/json/daily/USD-BRL/7"}}}]},
        {"role": "tool", "content": daily_result, "name": "http_get"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": file_name, "content": md_content}}}]},
        {"role": "tool", "content": write_result, "name": "write_file"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "send_claudio", "arguments": {"message": claudio_msg}}}]},
        {"role": "tool", "content": claudio_result, "name": "send_claudio"},
        {"role": "assistant", "content": final_text}
    ]
    
    return {
        "id": ex_id,
        "source": "synthetic_agy",
        "category": "agentforge",
        "subcategory": subcategory,
        "messages": messages
    }

def make_p3_variation(ex_id, subcategory, bug_type, idx):
    # Function returns a Python tool builder iterative fix example that satisfies P3 checks:
    # 1. memory_search.py created
    # 2. Valid Python syntax
    # 3. Has type hints (-> )
    # 4. Has docstring (""")
    # 5. Uses sqlite3
    # 6. Handles exception (except)
    # 7. test_memory_search.py created
    # 8. Tests pass (run_bash "python3 -m pytest..." returns passed)
    # 9. Final response contains TOOL CRIADO
    
    prompts = [
        f"Crie a ferramenta search_memory para buscar registros em um banco de dados SQLite. A assinatura deve ser search_memory(db: str, query: str) -> list[dict]. Escreva testes com pytest, execute pytest e finalize com a frase 'TOOL CRIADO'.",
        f"Escreva um módulo python memory_search.py com uma função search_memory(db: str, query: str) -> list[dict] que consulta uma tabela memory usando LIKE. Crie test_memory_search.py para validar o comportamento, execute pytest para garantir que passam e encerre com 'TOOL CRIADO'.",
        f"Desenvolva a ferramenta python `search_memory` usando sqlite3. A tabela tem as colunas key e value. A busca deve retornar uma lista de dicionários. Inclua type hints e docstrings. Execute pytest antes de responder e termine com 'TOOL CRIADO'."
    ]
    prompt = prompts[idx % len(prompts)]
    
    # Correct memory_search.py code
    correct_code = (
        "import sqlite3\n"
        "from pathlib import Path\n\n"
        "def search_memory(db: str, query: str) -> list[dict]:\n"
        "    \"\"\"Busca registros no banco SQLite onde a coluna value contem a query substring.\"\"\"\n"
        "    if not Path(db).exists():\n"
        "        raise FileNotFoundError(f\"Banco de dados nao encontrado: {db}\")\n"
        "    \n"
        "    conn = sqlite3.connect(db)\n"
        "    try:\n"
        "        cursor = conn.cursor()\n"
        "        cursor.execute(\"SELECT key, value FROM memory WHERE value LIKE ?\", (f\"%{query}%\",))\n"
        "        rows = cursor.fetchall()\n"
        "        return [{\"key\": row[0], \"value\": row[1]} for row in rows]\n"
        "    except sqlite3.Error as e:\n"
        "        raise RuntimeError(f\"Erro no banco de dados: {e}\")\n"
        "    finally:\n"
        "        conn.close()\n"
    )
    
    # Test code
    test_code = (
        "import pytest\n"
        "import sqlite3\n"
        "from pathlib import Path\n"
        "from memory_search import search_memory\n\n"
        "@pytest.fixture\n"
        "def temp_db(tmp_path):\n"
        "    db_file = tmp_path / \"test_mem.db\"\n"
        "    conn = sqlite3.connect(str(db_file))\n"
        "    conn.execute(\"CREATE TABLE memory (key TEXT, value TEXT)\")\n"
        "    conn.execute(\"INSERT INTO memory (key, value) VALUES ('k1', 'ollama config')\")\n"
        "    conn.execute(\"INSERT INTO memory (key, value) VALUES ('k2', 'docker stats')\")\n"
        "    conn.commit()\n"
        "    conn.close()\n"
        "    return str(db_file)\n\n"
        "def test_found(temp_db):\n"
        "    res = search_memory(temp_db, 'ollama')\n"
        "    assert len(res) == 1\n"
        "    assert res[0]['key'] == 'k1'\n"
        "    assert res[0]['value'] == 'ollama config'\n\n"
        "def test_not_found(temp_db):\n"
        "    res = search_memory(temp_db, 'xyz')\n"
        "    assert res == []\n\n"
        "def test_file_not_found():\n"
        "    with pytest.raises(FileNotFoundError):\n"
        "        search_memory('nonexistent.db', 'q')\n"
    )
    
    # Different bugs
    bugs = [
        # Bug 0: Missing import sqlite3
        {
            "code": "from pathlib import Path\n\ndef search_memory(db: str, query: str) -> list[dict]:\n    \"\"\"Search database.\"\"\"\n    if not Path(db).exists():\n        raise FileNotFoundError()\n    conn = sqlite3.connect(db)\n    return []\n",
            "err": "NameError: name 'sqlite3' is not defined"
        },
        # Bug 1: Function name search_mem instead of search_memory
        {
            "code": "import sqlite3\nfrom pathlib import Path\n\ndef search_mem(db: str, query: str) -> list[dict]:\n    \"\"\"Search.\"\"\"\n    if not Path(db).exists(): raise FileNotFoundError()\n    return []\n",
            "err": "ImportError: cannot import name 'search_memory' from 'memory_search'"
        },
        # Bug 2: Missing FileNotFoundError check
        {
            "code": "import sqlite3\n\ndef search_memory(db: str, query: str) -> list[dict]:\n    \"\"\"Search.\"\"\"\n    conn = sqlite3.connect(db)\n    cursor = conn.execute('SELECT key, value FROM memory')\n    return []\n",
            "err": "Failed: DID NOT RAISE <class 'FileNotFoundError'>"
        },
        # Bug 3: Typo in LIKE parameter syntax (missing comma in tuple)
        {
            "code": "import sqlite3\nfrom pathlib import Path\n\ndef search_memory(db: str, query: str) -> list[dict]:\n    \"\"\"Search.\"\"\"\n    if not Path(db).exists(): raise FileNotFoundError()\n    conn = sqlite3.connect(db)\n    try:\n        cursor = conn.execute('SELECT key, value FROM memory WHERE value LIKE ?', (f'%{query}%'))\n        return []\n    finally: conn.close()\n",
            "err": "sqlite3.ProgrammingError: Incorrect number of bindings supplied. The current statement uses 1, and there are X supplied."
        },
        # Bug 4: Returns list of tuples instead of list of dicts
        {
            "code": "import sqlite3\nfrom pathlib import Path\n\ndef search_memory(db: str, query: str) -> list[dict]:\n    \"\"\"Search.\"\"\"\n    if not Path(db).exists(): raise FileNotFoundError()\n    conn = sqlite3.connect(db)\n    try:\n        cursor = conn.execute('SELECT key, value FROM memory WHERE value LIKE ?', (f'%{query}%',))\n        return cursor.fetchall()\n    finally: conn.close()\n",
            "err": "TypeError: tuple indices must be integers or slices, not str"
        },
        # Bug 5: sqlite3.OperationalError due to typo in query
        {
            "code": "import sqlite3\nfrom pathlib import Path\n\ndef search_memory(db: str, query: str) -> list[dict]:\n    \"\"\"Search.\"\"\"\n    if not Path(db).exists(): raise FileNotFoundError()\n    conn = sqlite3.connect(db)\n    try:\n        cursor = conn.execute('SELECT key, value FROM memory_table WHERE value LIKE ?', (f'%{query}%',))\n        return []\n    finally: conn.close()\n",
            "err": "sqlite3.OperationalError: no such table: memory_table"
        },
        # Bug 6: Typo in dict key names
        {
            "code": "import sqlite3\nfrom pathlib import Path\n\ndef search_memory(db: str, query: str) -> list[dict]:\n    \"\"\"Search.\"\"\"\n    if not Path(db).exists(): raise FileNotFoundError()\n    conn = sqlite3.connect(db)\n    try:\n        cursor = conn.execute('SELECT key, value FROM memory WHERE value LIKE ?', (f'%{query}%',))\n        return [{'k': r[0], 'v': r[1]} for r in cursor.fetchall()]\n    finally: conn.close()\n",
            "err": "KeyError: 'key'"
        },
        # Bug 7: Returns None instead of list[dict]
        {
            "code": "import sqlite3\nfrom pathlib import Path\n\ndef search_memory(db: str, query: str) -> list[dict]:\n    \"\"\"Search.\"\"\"\n    if not Path(db).exists(): raise FileNotFoundError()\n    conn = sqlite3.connect(db)\n    try:\n        cursor = conn.execute('SELECT key, value FROM memory WHERE value LIKE ?', (f'%{query}%',))\n    finally: conn.close()\n",
            "err": "TypeError: object of type 'NoneType' has no len()"
        },
        # Bug 8: Missing except handler
        {
            "code": "import sqlite3\nfrom pathlib import Path\n\ndef search_memory(db: str, query: str) -> list[dict]:\n    \"\"\"Search.\"\"\"\n    if not Path(db).exists(): raise FileNotFoundError()\n    conn = sqlite3.connect(db)\n    cursor = conn.execute('SELECT key, value FROM memory WHERE value LIKE ?', (f'%{query}%',))\n    return []\n",
            "err": "AssertionError: assert [] == [{'key': 'k1', 'value': 'ollama config'}]"
        },
        # Bug 9: sqlite3 database error raising wrong format
        {
            "code": "import sqlite3\nfrom pathlib import Path\n\ndef search_memory(db: str, query: str) -> list[dict]:\n    \"\"\"Search.\"\"\"\n    if not Path(db).exists(): raise FileNotFoundError()\n    conn = sqlite3.connect(db)\n    cursor = conn.execute('SELECT key, value FROM memory WHERE value LIKE ?', (f'%{query}%',))\n    return [{'key': r[0], 'value': r[1]} for r in cursor.fetchall()]\n",
            "err": "AssertionError: assert [] == [{'key': 'k1', 'value': 'ollama config'}]"
        }
    ]
    
    selected_bug = bugs[bug_type % len(bugs)]
    buggy_code = selected_bug["code"]
    err_msg = selected_bug["err"]
    
    write_initial = json.dumps({"success": True, "path": "memory_search.py", "bytes": len(buggy_code)})
    write_test = json.dumps({"success": True, "path": "test_memory_search.py", "bytes": len(test_code)})
    
    pytest_fail_output = (
        "============================= test session starts ==============================\n"
        "test_memory_search.py FAILED\n\n"
        f"E   {err_msg}\n"
        "============================== 1 failed in 0.05s =============================="
    )
    
    read_file_res = json.dumps({"content": buggy_code, "path": "memory_search.py"})
    write_fixed = json.dumps({"success": True, "path": "memory_search.py", "bytes": len(correct_code)})
    
    pytest_pass_output = (
        "============================= test session starts ==============================\n"
        "test_memory_search.py::test_found PASSED\n"
        "test_memory_search.py::test_not_found PASSED\n"
        "test_memory_search.py::test_file_not_found PASSED\n\n"
        "============================== 3 passed in 0.04s =============================="
    )
    
    messages = [
        {"role": "system", "content": "You are Python Tool Builder (ID: real-p3). Objective: Create Python tools, write unit tests, run pytest, fix errors. Tools: write_file, read_file, run_bash."},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "memory_search.py", "content": buggy_code}}}]},
        {"role": "tool", "content": write_initial, "name": "write_file"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "test_memory_search.py", "content": test_code}}}]},
        {"role": "tool", "content": write_test, "name": "write_file"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "python3 -m pytest test_memory_search.py -v"}}}]},
        {"role": "tool", "content": pytest_fail_output, "name": "run_bash"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "memory_search.py"}}}]},
        {"role": "tool", "content": read_file_res, "name": "read_file"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "memory_search.py", "content": correct_code}}}]},
        {"role": "tool", "content": write_fixed, "name": "write_file"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "python3 -m pytest test_memory_search.py -v"}}}]},
        {"role": "tool", "content": pytest_pass_output, "name": "run_bash"},
        {"role": "assistant", "content": f"A ferramenta `search_memory` foi corrigida e todos os testes pytest passaram com sucesso. TOOL CRIADO"}
    ]
    
    return {
        "id": ex_id,
        "source": "synthetic_agy",
        "category": "agentforge",
        "subcategory": subcategory,
        "messages": messages
    }

def make_p4_variation(ex_id, subcategory, app_name, app_desc, idx):
    # Function returns a Skill Doc Builder variation that satisfies P4 checks:
    # 1. fox-deploy.md created
    # 2. YAML frontmatter valid (starts with ---, has name: and description:)
    # 3. Section with "quando usar" (case-insensitive)
    # 4. Section with "passo" (passos)
    # 5. Section with "erro" (erros comuns)
    # 6. Section with "exemplo"
    # 7. Mentions "docker compose"
    # 8. Mentions "Claudio" (notification)
    # 9. Test file created
    # 10. run_bash called to run test
    # 11. Final response contains SKILL CRIADA
    
    prompts = [
        f"Crie a documentação do skill fox-deploy para gerenciar o deploy do {app_name}. Siga as regras obrigatórias de YAML frontmatter, as seções de quando usar, pré-requisitos, passo-a-passo, erros comuns e exemplos. Mencione docker compose e Claudio. Escreva um teste em fox-deploy-test.sh, execute-o e finalize com 'SKILL CRIADA'.",
        f"Escreva um skill doc chamado fox-deploy.md para o {app_name} ({app_desc}). Deve conter YAML frontmatter, as seções obrigatórias: quando usar, pré-requisitos, passo-a-passo, erros comuns, exemplos. Mencione docker compose e Claudio. Crie um script de teste fox-deploy-test.sh para checar os requisitos, rode via run_bash e termine com 'SKILL CRIADA'.",
        f"Documente o deploy do {app_name} no skill fox-deploy.md. Inclua YAML frontmatter válido. Certifique-se de incluir as seções: quando usar, passos, erros comuns, exemplos. Fale sobre comandos docker compose e notificação via Claudio. Crie e rode o script fox-deploy-test.sh. Responda terminando com 'SKILL CRIADA'."
    ]
    prompt = prompts[idx % len(prompts)]
    
    yaml_name = "fox-deploy"
    md_content = (
        "---\n"
        f"name: {yaml_name}\n"
        f"description: Skill para deploy e atualizacao do {app_name} ({app_desc}) no fox-server\n"
        "---\n\n"
        "## Quando usar\n"
        f"Use este skill quando precisar inicializar, atualizar ou restaurar a instancia do {app_name}.\n\n"
        "## Pré-requisitos\n"
        "- Docker e Docker Compose instalados no fox-server.\n"
        f"- Arquivo docker-compose.yml configurado para {app_name}.\n\n"
        "## Passo-a-passo\n"
        f"1. Acesse o diretorio: `cd ~/apps/{app_name.lower()}`\n"
        "2. Execute docker compose para subir o container:\n"
        "   ```bash\n"
        "   docker compose up -d --build\n"
        "   ```\n"
        "3. Valide o status com `docker compose ps`.\n"
        "4. Envie uma notificacao via Claudio informando o sucesso do deploy.\n\n"
        "## Erros comuns\n"
        "- **Porta em uso**: Pare o container conflitante e execute docker compose novamente.\n"
        "- **Erro no Claudio**: Verifique a conectividade de rede do fox-server.\n\n"
        "## Exemplos\n"
        "```bash\n"
        f"cd ~/apps/{app_name.lower()} && docker compose pull && docker compose up -d\n"
        "```\n"
    )
    
    test_script_content = (
        "#!/bin/bash\n"
        "set -e\n"
        "echo 'Running deployment validations on fox-deploy.md...'\n"
        "grep -qi 'quando usar' fox-deploy.md && echo 'OK: quando usar'\n"
        "grep -qi 'passo' fox-deploy.md && echo 'OK: passos'\n"
        "grep -qi 'erro' fox-deploy.md && echo 'OK: erros'\n"
        "grep -qi 'exemplo' fox-deploy.md && echo 'OK: exemplos'\n"
        "grep -q 'docker compose' fox-deploy.md && echo 'OK: docker compose'\n"
        "grep -q 'Claudio' fox-deploy.md && echo 'OK: Claudio'\n"
        "echo 'Validation Successful!'\n"
    )
    
    test_file_name = f"fox-deploy-test-{idx}.sh" if idx % 2 == 0 else f"validate-deploy-{idx}.sh"
    
    write_md_res = json.dumps({"success": True, "path": "fox-deploy.md", "bytes": len(md_content)})
    write_test_res = json.dumps({"success": True, "path": test_file_name, "bytes": len(test_script_content)})
    
    bash_output = (
        "Running deployment validations on fox-deploy.md...\n"
        "OK: quando usar\n"
        "OK: passos\n"
        "OK: erros\n"
        "OK: exemplos\n"
        "OK: docker compose\n"
        "OK: Claudio\n"
        "Validation Successful!\n"
    )
    
    messages = [
        {"role": "system", "content": "You are Skill Doc Builder (ID: real-p4). Objective: Write and validate skill documentation. Tools: write_file, read_file, run_bash."},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "fox-deploy.md", "content": md_content}}}]},
        {"role": "tool", "content": write_md_res, "name": "write_file"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": test_file_name, "content": test_script_content}}}]},
        {"role": "tool", "content": write_test_res, "name": "write_file"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": f"bash {test_file_name}"}}}]},
        {"role": "tool", "content": bash_output, "name": "run_bash"},
        {"role": "assistant", "content": f"O documento fox-deploy.md para o {app_name} foi criado e testado. Todos os checks passaram. SKILL CRIADA"}
    ]
    
    return {
        "id": ex_id,
        "source": "synthetic_agy",
        "category": "agentforge",
        "subcategory": subcategory,
        "messages": messages
    }

def main():
    examples = []
    
    # 1. tool_chain_complete (20 examples): af-c001 to af-c020
    # Let's generate F3 variations for the first 10, and other diverse tool chains for the next 10.
    for idx in range(10):
        ex_id = f"af-c{idx+1:03d}"
        usd_bids = [5.1623, 5.2341, 5.0872, 5.1120, 5.2910, 5.3412, 5.1989, 5.0456, 5.1550, 5.2100]
        btc_bids = [329134.00, 331500.00, 325400.00, 340000.00, 318000.00, 335000.00, 328000.00, 345000.00, 327000.00, 333000.00]
        examples.append(make_f3_variation(ex_id, "tool_chain_complete", usd_bids[idx], btc_bids[idx], idx))
        
    # Other diverse tool chains (10 examples)
    # Server status (2 examples)
    for idx in range(2):
        ex_id = f"af-c{idx+11:03d}"
        messages = [
            {"role": "system", "content": "You are SysAdmin (ID: forge-f3-sys). Tools: run_bash, write_file."},
            {"role": "user", "content": f"Verifique o status do ping e recursos dos servidores: fox-server, fox-note, nerds-dev, igor-dev. Salve um relatorio em server-status-{idx}.md e termine com 'ANALYSIS COMPLETED'."},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "ping -c 2 fox-server"}}}]},
            {"role": "tool", "content": "PING fox-server (192.168.1.10) 56(84) bytes of data.\n64 bytes: icmp_seq=1 ttl=64 time=0.22 ms\n64 bytes: icmp_seq=2 ttl=64 time=0.25 ms\n--- fox-server ping statistics ---\n2 packets transmitted, 2 received, 0% packet loss", "name": "run_bash"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "ping -c 2 fox-note"}}}]},
            {"role": "tool", "content": "PING fox-note (192.168.1.11) 56(84) bytes of data.\n64 bytes: icmp_seq=1 ttl=64 time=1.45 ms\n64 bytes: icmp_seq=2 ttl=64 time=1.32 ms\n--- fox-note ping statistics ---\n2 packets transmitted, 2 received, 0% packet loss", "name": "run_bash"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "ping -c 2 nerds-dev"}}}]},
            {"role": "tool", "content": "PING nerds-dev (192.168.1.12) 56(84) bytes of data.\n64 bytes: icmp_seq=1 ttl=64 time=0.95 ms\n64 bytes: icmp_seq=2 ttl=64 time=1.02 ms\n--- nerds-dev ping statistics ---\n2 packets transmitted, 2 received, 0% packet loss", "name": "run_bash"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "ping -c 2 igor-dev"}}}]},
            {"role": "tool", "content": "PING igor-dev (192.168.1.13) 56(84) bytes of data.\n64 bytes: icmp_seq=1 ttl=64 time=0.18 ms\n64 bytes: icmp_seq=2 ttl=64 time=0.21 ms\n--- igor-dev ping statistics ---\n2 packets transmitted, 2 received, 0% packet loss", "name": "run_bash"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": f"server-status-{idx}.md", "content": f"# Server Status Report {idx}\nAll nodes (fox-server, fox-note, nerds-dev, igor-dev) are responding under 2ms. No packet loss."}}}]},
            {"role": "tool", "content": json.dumps({"success": True, "path": f"server-status-{idx}.md", "bytes": 120}), "name": "write_file"},
            {"role": "assistant", "content": f"Servidores validados com sucesso. Relatorio salvo em server-status-{idx}.md. ANALYSIS COMPLETED"}
        ]
        examples.append({"id": ex_id, "source": "synthetic_agy", "category": "agentforge", "subcategory": "tool_chain_complete", "messages": messages})
        
    # Stock prices (2 examples)
    for idx in range(2):
        ex_id = f"af-c{idx+13:03d}"
        messages = [
            {"role": "system", "content": "You are Stock Monitor. Tools: http_get, write_file."},
            {"role": "user", "content": f"Busque o preco das acoes: PETR4.SA, VALE3.SA, ITUB4.SA, BBDC4.SA. Salve em acoes-{idx}.md e conclua com 'ANALYSIS COMPLETED'."},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://query1.finance.yahoo.com/v8/finance/chart/PETR4.SA"}}}]},
            {"role": "tool", "content": '{"chart":{"result":[{"meta":{"regularMarketPrice":38.45}}]}}', "name": "http_get"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://query1.finance.yahoo.com/v8/finance/chart/VALE3.SA"}}}]},
            {"role": "tool", "content": '{"chart":{"result":[{"meta":{"regularMarketPrice":62.10}}]}}', "name": "http_get"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://query1.finance.yahoo.com/v8/finance/chart/ITUB4.SA"}}}]},
            {"role": "tool", "content": '{"chart":{"result":[{"meta":{"regularMarketPrice":32.90}}]}}', "name": "http_get"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://query1.finance.yahoo.com/v8/finance/chart/BBDC4.SA"}}}]},
            {"role": "tool", "content": '{"chart":{"result":[{"meta":{"regularMarketPrice":14.25}}]}}', "name": "http_get"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": f"acoes-{idx}.md", "content": f"# Stock Price Report {idx}\n- PETR4: R$ 38,45\n- VALE3: R$ 62,10\n- ITUB4: R$ 32,90\n- BBDC4: R$ 14,25"}}}]},
            {"role": "tool", "content": json.dumps({"success": True, "path": f"acoes-{idx}.md", "bytes": 105}), "name": "write_file"},
            {"role": "assistant", "content": f"Cotacoes de acoes obtidas com sucesso. Relatorio salvo em acoes-{idx}.md. ANALYSIS COMPLETED"}
        ]
        examples.append({"id": ex_id, "source": "synthetic_agy", "category": "agentforge", "subcategory": "tool_chain_complete", "messages": messages})
        
    # Weather APIs (2 examples)
    for idx in range(2):
        ex_id = f"af-c{idx+15:03d}"
        messages = [
            {"role": "system", "content": "You are Weather Reporter. Tools: http_get, write_file."},
            {"role": "user", "content": f"Busque o clima atual de: SP, RJ, BH, Brasilia. Crie o relatorio clima-{idx}.md e termine com 'ANALYSIS COMPLETED'."},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://api.weatherapi.com/v1/current.json?q=Sao+Paulo"}}}]},
            {"role": "tool", "content": '{"current":{"temp_c":21.5,"condition":{"text":"Partly cloudy"}}}', "name": "http_get"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://api.weatherapi.com/v1/current.json?q=Rio+de+Janeiro"}}}]},
            {"role": "tool", "content": '{"current":{"temp_c":25.0,"condition":{"text":"Sunny"}}}', "name": "http_get"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://api.weatherapi.com/v1/current.json?q=Belo+Horizonte"}}}]},
            {"role": "tool", "content": '{"current":{"temp_c":22.8,"condition":{"text":"Clear"}}}', "name": "http_get"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://api.weatherapi.com/v1/current.json?q=Brasilia"}}}]},
            {"role": "tool", "content": '{"current":{"temp_c":20.1,"condition":{"text":"Clear"}}}', "name": "http_get"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": f"clima-{idx}.md", "content": f"# Clima Report {idx}\n- Sao Paulo: 21.5C (Partly cloudy)\n- Rio de Janeiro: 25.0C (Sunny)\n- Belo Horizonte: 22.8C (Clear)\n- Brasilia: 20.1C (Clear)"}}}]},
            {"role": "tool", "content": json.dumps({"success": True, "path": f"clima-{idx}.md", "bytes": 160}), "name": "write_file"},
            {"role": "assistant", "content": f"Dados de clima coletados. Relatorio salvo em clima-{idx}.md. ANALYSIS COMPLETED"}
        ]
        examples.append({"id": ex_id, "source": "synthetic_agy", "category": "agentforge", "subcategory": "tool_chain_complete", "messages": messages})
        
    # Container metrics (2 examples)
    for idx in range(2):
        ex_id = f"af-c{idx+17:03d}"
        messages = [
            {"role": "system", "content": "You are Container Monitor. Tools: run_bash, write_file."},
            {"role": "user", "content": f"Obtenha estatisticas de n8n, qdrant, ollama, open-webui. Grave em containers-{idx}.md e finalize com 'ANALYSIS COMPLETED'."},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "docker stats n8n --no-stream --format '{{.MemUsage}}'"}}}]},
            {"role": "tool", "content": "150MiB / 16GiB", "name": "run_bash"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "docker stats qdrant --no-stream --format '{{.MemUsage}}'"}}}]},
            {"role": "tool", "content": "450MiB / 16GiB", "name": "run_bash"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "docker stats ollama --no-stream --format '{{.MemUsage}}'"}}}]},
            {"role": "tool", "content": "4.2GiB / 16GiB", "name": "run_bash"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "docker stats open-webui --no-stream --format '{{.MemUsage}}'"}}}]},
            {"role": "tool", "content": "200MiB / 16GiB", "name": "run_bash"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": f"containers-{idx}.md", "content": f"# Container Memory Stats {idx}\n- n8n: 150MiB\n- qdrant: 450MiB\n- ollama: 4.2GiB\n- open-webui: 200MiB"}}}]},
            {"role": "tool", "content": json.dumps({"success": True, "path": f"containers-{idx}.md", "bytes": 130}), "name": "write_file"},
            {"role": "assistant", "content": f"Estatisticas salvas em containers-{idx}.md. ANALYSIS COMPLETED"}
        ]
        examples.append({"id": ex_id, "source": "synthetic_agy", "category": "agentforge", "subcategory": "tool_chain_complete", "messages": messages})
        
    # Mixed (2 examples)
    for idx in range(2):
        ex_id = f"af-c{idx+19:03d}"
        messages = [
            {"role": "system", "content": "You are Mixed Admin. Tools: http_get, run_bash, write_file."},
            {"role": "user", "content": f"Busque o status de nvidia-smi, a cotacao de USD-BRL e o espaco em disco. Crie o log mixed-{idx}.log e finalize com 'ANALYSIS COMPLETED'."},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits"}}}]},
            {"role": "tool", "content": "5120", "name": "run_bash"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "http_get", "arguments": {"url": "https://economia.awesomeapi.com.br/json/last/USD-BRL"}}}]},
            {"role": "tool", "content": '{"USDBRL":{"bid":"5.1623"}}', "name": "http_get"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "df -h / | tail -n 1 | awk '{print $5}'"}}}]},
            {"role": "tool", "content": "45%", "name": "run_bash"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": f"mixed-{idx}.log", "content": f"System log:\n- GPU Used: 5120MiB\n- USD-BRL: 5.1623\n- Disk Used: 45%"}}}]},
            {"role": "tool", "content": json.dumps({"success": True, "path": f"mixed-{idx}.log", "bytes": 85}), "name": "write_file"},
            {"role": "assistant", "content": f"Dados combinados gerados em mixed-{idx}.log. ANALYSIS COMPLETED"}
        ]
        examples.append({"id": ex_id, "source": "synthetic_agy", "category": "agentforge", "subcategory": "tool_chain_complete", "messages": messages})

    # 2. completion_signal (20 examples): af-c021 to af-c040
    # Let's generate 10 of scenario 2a (engine injection) and 10 of scenario 2b (prompt rules).
    phrases = [
        "SKILL CREATED", "TOOL CREATED", "ANALYSIS COMPLETED", "TASK COMPLETED",
        "DEPLOY COMPLETE", "MONITORING ACTIVE", "REPORT GENERATED", "MIGRATION DONE"
    ]
    
    # 2a (10 examples): af-c021 to af-c030
    for idx in range(10):
        ex_id = f"af-c{idx+21:03d}"
        phrase = phrases[idx % len(phrases)]
        messages = [
            {"role": "system", "content": "You are Automation Agent. Tools: run_bash, write_file."},
            {"role": "user", "content": f"Execute a tarefa de backup da pasta config para o diretorio /mnt/backup/config-{idx}."},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": f"mkdir -p /mnt/backup/config-{idx} && cp -r config/* /mnt/backup/config-{idx}/"}}}]},
            {"role": "tool", "content": "Backup complete. Copying 15 files.", "name": "run_bash"},
            {"role": "user", "content": f"Produce your final response based on the tools executed above.\nTools already executed:\n  - run_bash(...)\nYour response MUST include: '{phrase}'"},
            {"role": "assistant", "content": f"O backup do diretorio config para /mnt/backup/config-{idx} foi realizado com sucesso. Todos os 15 arquivos copiados. {phrase}"}
        ]
        examples.append({"id": ex_id, "source": "synthetic_agy", "category": "agentforge", "subcategory": "completion_signal", "messages": messages})
        
    # 2b (10 examples): af-c031 to af-c040
    for idx in range(10):
        ex_id = f"af-c{idx+31:03d}"
        phrase = phrases[idx % len(phrases)]
        messages = [
            {"role": "system", "content": "You are Setup Agent. Tools: run_bash, write_file."},
            {"role": "user", "content": f"Crie um link simbolico para o app.py na pasta bin. MANDATORY RULES: - verify if link exists - finish the response with the exact phrase '{phrase}'"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": "ln -sf /home/conrado/app.py /usr/local/bin/app"}}}]},
            {"role": "tool", "content": "", "name": "run_bash"},
            {"role": "assistant", "content": f"Link simbolico para app.py criado com sucesso em /usr/local/bin/app. {phrase}"}
        ]
        examples.append({"id": ex_id, "source": "synthetic_agy", "category": "agentforge", "subcategory": "completion_signal", "messages": messages})

    # 3. structured_file (15 examples): af-c041 to af-c055
    # All are P4 (Skill Doc Builder) variations, satisfying P4 checks.
    apps = [
        ("N8N", "Automacao de workflows"),
        ("Qdrant", "Banco de dados vetorial"),
        ("Ollama", "Inferência local de LLMs"),
        ("Open-WebUI", "Interface web para chat"),
        ("PostgreSQL", "Banco relacional para logs"),
        ("Redis", "Cache em memoria"),
        ("Metabase", "Painel de Business Intelligence"),
        ("Ghost", "Blog engine com volume persistente"),
        ("Chat-UI", "Frontend customizável"),
        ("AuthGate", "Gateway de autenticação"),
        ("Flowise", "Visual builder para langchain"),
        ("Meilisearch", "Motor de busca indexado"),
        ("ForgeAgent", "Agente secundário local"),
        ("Grafana", "Visualizador de métricas"),
        ("Portainer", "Gerenciador gráfico de docker")
    ]
    for idx, (app_name, app_desc) in enumerate(apps):
        ex_id = f"af-c{idx+41:03d}"
        examples.append(make_p4_variation(ex_id, "structured_file", app_name, app_desc, idx))

    # 4. iterative_fix (15 examples): af-c056 to af-c070
    # All are P3 (Python Tool Builder with error fix loop) variations, satisfying P3 checks.
    for idx in range(15):
        ex_id = f"af-c{idx+56:03d}"
        examples.append(make_p3_variation(ex_id, "iterative_fix", idx, idx))

    # 5. no_tool_redirect (10 examples): af-c071 to af-c080
    redirect_tasks = [
        {"q": "Verifique quais containers Docker estao ativos no fox-server.", "cmd": "docker ps --format 'table {{.Names}}\t{{.Status}}'", "res": "Names               Status\nollama              Up 3 days\nqdrant              Up 3 days\nn8n                 Up 2 hours", "ans": "Os containers ativos sao: ollama, qdrant e n8n."},
        {"q": "Qual o status da VRAM da GPU RTX 3060?", "cmd": "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits", "res": "5120, 12288", "ans": "A GPU RTX 3060 esta com 5120MB usados de um total de 12288MB (VRAM)."},
        {"q": "Leia o arquivo de configuracao /home/conrado/config.json.", "cmd": "cat /home/conrado/config.json", "res": '{"port": 8080, "host": "127.0.0.1"}', "ans": "O arquivo de configuracao define a porta 8080 e host 127.0.0.1."},
        {"q": "Verifique o espaco livre em disco na raiz.", "cmd": "df -h /", "res": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1       120G   80G   35G  70% /", "ans": "O disco raiz tem 35G disponiveis (70% em uso)."},
        {"q": "Liste os modelos atualmente baixados no Ollama.", "cmd": "ollama list", "res": "NAME                 ID           SIZE      MODIFIED\nqwen2.5-coder:7b     c28a8a25c602 4.7 GB    2 days ago\nllama3.1:8b          e9f743c3f412 4.7 GB    5 days ago", "ans": "Os modelos baixados sao qwen2.5-coder:7b e llama3.1:8b."},
        {"q": "Descubra qual o PID do processo n8n em execucao.", "cmd": "ps aux | grep n8n | grep -v grep", "res": "conrado    12345  0.5  1.2 1253400 152340 ?      Sl   12:00   0:15 node /usr/local/bin/n8n", "ans": "O PID do processo n8n e 12345."},
        {"q": "Teste a conectividade ping para o Google.", "cmd": "ping -c 3 google.com", "res": "3 packets transmitted, 3 received, 0% packet loss, time 2002ms", "ans": "A conexao ping para o Google esta funcionando normalmente com 0% de perda."},
        {"q": "Veja os ultimos 5 logs do sistema syslog.", "cmd": "tail -n 5 /var/log/syslog", "res": "Jun 18 12:00:00 fox systemd: Started Periodic Command Scheduler.\nJun 18 12:10:00 fox cron: log-rotation finished.", "ans": "Os logs mostram que o cron iniciou com sucesso e a rotatividade de log terminou."},
        {"q": "Verifique quais portas TCP estao ouvindo no servidor.", "cmd": "netstat -tuln | grep LISTEN", "res": "tcp        0      0 127.0.0.1:8080          0.0.0.0:*               LISTEN\ntcp        0      0 0.0.0.0:11434           0.0.0.0:*               LISTEN", "ans": "As portas 8080 (local) e 11434 (ollama) estao em modo LISTEN."},
        {"q": "Liste os arquivos ocultos na home do usuario.", "cmd": "ls -la /home/conrado | grep '^\\.'", "res": ".bashrc\n.profile\n.gemini", "ans": "Os arquivos ocultos na home sao .bashrc, .profile e .gemini."}
    ]
    for idx, item in enumerate(redirect_tasks):
        ex_id = f"af-c{idx+71:03d}"
        messages = [
            {"role": "system", "content": "You are Utility Agent. Tools: run_bash, read_file."},
            {"role": "user", "content": item["q"]},
            {"role": "assistant", "content": f"Para responder a isso, voce deve checar as informacoes. Pode executar `{item['cmd']}` para verificar."},
            {"role": "user", "content": "You have not used any tools yet. Do NOT output code or text directly — use the available tools to complete the task. Call the appropriate tool now to proceed."},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_bash", "arguments": {"command": item["cmd"]}}}]},
            {"role": "tool", "content": item["res"], "name": "run_bash"},
            {"role": "assistant", "content": f"{item['ans']}"}
        ]
        examples.append({"id": ex_id, "source": "synthetic_agy", "category": "agentforge", "subcategory": "no_tool_redirect", "messages": messages})

    # 6. must_rules_compliance (15 examples): af-c081 to af-c095
    # Let's write 5 Set A (F3-like), 5 Set B (P3-like), 5 Set C (P4-like). This ensures priority variations are fully generated.
    # Set A (F3-like) - 5 examples: af-c081 to af-c085
    for idx in range(5):
        ex_id = f"af-c{idx+81:03d}"
        usd_rate = 5.1200 + (idx * 0.02)
        btc_rate = 327000.00 + (idx * 1500)
        examples.append(make_f3_variation(ex_id, "must_rules_compliance", usd_rate, btc_rate, idx + 10))
        
    # Set B (P3-like) - 5 examples: af-c086 to af-c090
    for idx in range(5):
        ex_id = f"af-c{idx+86:03d}"
        examples.append(make_p3_variation(ex_id, "must_rules_compliance", idx + 15, idx + 15))
        
    # Set C (P4-like) - 5 examples: af-c091 to af-c095
    apps_compliance = [
        ("N8N-Compliance", "Verificacoes estritas de workflow"),
        ("Qdrant-Compliance", "Indexacao estrita vetorial"),
        ("Ollama-Compliance", "Monitoramento de modelos Ollama"),
        ("Open-WebUI-Compliance", "Deploy de frontend seguro"),
        ("PostgreSQL-Compliance", "Banco relacional homologado")
    ]
    for idx, (app_name, app_desc) in enumerate(apps_compliance):
        ex_id = f"af-c{idx+91:03d}"
        examples.append(make_p4_variation(ex_id, "must_rules_compliance", app_name, app_desc, idx + 20))

    # 7. memory_multi_turn (15 examples): af-c096 to af-c110
    memories = [
        {"ctx": "meu servidor usa RTX 3060", "q": "quanto VRAM tenho disponivel?", "ans": "Com base na RTX 3060 que voce mencionou anteriormente, voce tem 12GB de VRAM disponiveis."},
        {"ctx": "a pasta do projeto e /var/www/html", "q": "onde devo criar o index.php?", "ans": "Como a pasta do projeto e /var/www/html, crie o arquivo index.php nesse mesmo diretorio: /var/www/html/index.php."},
        {"ctx": "o repositório git e git@github.com:JConradoN/agent-FORGE.git", "q": "qual o link para dar clone?", "ans": "O link para clone e o que voce informou antes: git@github.com:JConradoN/agent-FORGE.git."},
        {"ctx": "o servidor de testes igor-dev esta rodando na porta 8080", "q": "em qual porta posso acessar a API?", "ans": "A API pode ser acessada na porta 8080 do servidor igor-dev, conforme o contexto inicial."},
        {"ctx": "o IP do endpoint e 192.168.1.150", "q": "qual IP devo pingar?", "ans": "Voce deve pingar o IP informado: 192.168.1.150."},
        {"ctx": "estamos usando python 3.11 neste ambiente", "q": "com qual versao devo rodar o pytest?", "ans": "Rode o pytest com o python 3.11, que e a versao definida para o ambiente."},
        {"ctx": "a rede docker chama-se forge-net", "q": "qual o parametro --network que uso?", "ans": "Use o parametro `--network forge-net` para se conectar a rede docker configurada."},
        {"ctx": "o canal de alertas no slack e #deploy-alerts", "q": "para onde mando as notificacoes de erro?", "ans": "As notificacoes de erro devem ser enviadas para o canal #deploy-alerts que voce registrou no inicio."},
        {"ctx": "o banco tem colunas id, email e created_at", "q": "quais campos devo selecionar na query?", "ans": "A query deve selecionar as colunas informadas: id, email e created_at."},
        {"ctx": "a porta da web UI do app e 8080", "q": "onde abro o painel?", "ans": "Abra o painel acessando a porta 8080 no seu navegador."},
        {"ctx": "estamos rodando o modelo qwen2.5-coder:7b no ollama", "q": "qual modelo passo no parametro model?", "ans": "Passe 'qwen2.5-coder:7b' no parametro model da API do Ollama."},
        {"ctx": "a pasta de backup diario e /mnt/backup/daily", "q": "onde busco o arquivo compactado?", "ans": "Busque o arquivo compactado na pasta de backup diario: /mnt/backup/daily."},
        {"ctx": "a senha do redis e super-secure-pass", "q": "como configuro a string de conexao?", "ans": "Configure a conexao usando a senha registrada: super-secure-pass."},
        {"ctx": "o github token e ghp_abcdef", "q": "qual token uso no curl?", "ans": "Use o token ghp_abcdef para autenticar a chamada curl ao Github."},
        {"ctx": "o dominio de homologacao e staging.agentforge.local", "q": "qual o host para testar o HTTPS?", "ans": "O host para testar o certificado HTTPS e staging.agentforge.local."}
    ]
    for idx, item in enumerate(memories):
        ex_id = f"af-c{idx+96:03d}"
        messages = [
            {"role": "system", "content": "You are Context Agent. Memory enabled. Previous context available."},
            {"role": "user", "content": f"Ola, lembre-se que {item['ctx']}."},
            {"role": "assistant", "content": f"Entendido. Registro guardado em memoria: {item['ctx']}."},
            {"role": "user", "content": f"{item['q']}"},
            {"role": "assistant", "content": f"{item['ans']}"}
        ]
        examples.append({"id": ex_id, "source": "synthetic_agy", "category": "agentforge", "subcategory": "memory_multi_turn", "messages": messages})

    # 8. agent_delegation (10 examples): af-c111 to af-c120
    delegation_tasks = [
        {"q": "verifica o estado completo do fox-server", "dir": "agents/fox-health", "inp": "full health check", "out": '{"output": "CPU 35%, MEM 12GB/128GB, GPU OK, containers OK"}', "ans": "O fox-health reportou status operacional estavel: CPU 35%, MEM 12GB/128GB, GPU OK e todos os containers ativos."},
        {"q": "limpe os logs antigos da maquina", "dir": "agents/lab-ops", "inp": "clean logs older than 7 days", "out": '{"output": "Successfully freed 2.4GB. Log rotation complete."}', "ans": "A limpeza foi delegada ao lab-ops. Sucesso: 2.4GB de espaco liberados e log rotation completo."},
        {"q": "faca deploy da versao mais recente no container", "dir": "agents/lab-ops", "inp": "redeploy latest image docker compose", "out": '{"output": "Container n8n updated and recreated. Status: running."}', "ans": "O lab-ops realizou o redeploy do container com a imagem mais recente. Status: ativo e operando."},
        {"q": "diagnostique se ha erros de conexao no banco", "dir": "agents/fox-health", "inp": "check postgres connections status", "out": '{"output": "Active connections: 14/100. Latency: 1.2ms. Status: healthy."}', "ans": "O fox-health confirmou conexao saudavel no banco com apenas 14/100 conexoes e latencia de 1.2ms."},
        {"q": "crie um snapshot diario da base sqlite", "dir": "agents/lab-ops", "inp": "sqlite snapshot save to backup", "out": '{"output": "Database snapshot created successfully at /backup/db_snapshot.db (512KB)"}', "ans": "O snapshot da base SQLite foi gerado com sucesso pelo lab-ops em /backup/db_snapshot.db."},
        {"q": "valide os recursos e limpe caches se necessario", "dir": "agents/lab-ops", "inp": "check RAM resources and clear cache if > 80% used", "out": '{"output": "RAM at 45%. No cache purge required."}', "ans": "O lab-ops verificou os recursos: RAM atualmente em 45%, portanto nao foi necessario limpar caches."},
        {"q": "faca uma auditoria de performance no sqlite", "dir": "agents/fox-health", "inp": "audit index and slow queries", "out": '{"output": "Audit passed. All queries indexed properly."}', "ans": "A auditoria pelo fox-health passou sem anomalias, com todas as queries indexadas corretamente."},
        {"q": "verifique se ha portas abertas em conflito", "dir": "agents/fox-health", "inp": "check port conflicts on 8080 and 11434", "out": '{"output": "No conflict detected. Port 8080 is used by open-webui and 11434 by ollama."}', "ans": "O fox-health verificou que as portas 8080 e 11434 estao alocadas de forma correta sem conflitos."},
        {"q": "agende uma tarefa cron de backup diário", "dir": "agents/lab-ops", "inp": "configure daily cron tab at 02:00", "out": '{"output": "Crontab updated successfully: 0 2 * * * backup.sh"}', "ans": "O lab-ops configurou o cron de backup diario para rodar as 02:00. Crontab atualizada."},
        {"q": "limpe caches temporarios de logs e valide status", "dir": "agents/lab-ops", "inp": "clear temp files and return disk availability", "out": '{"output": "Temp files cleared. Disk availability is now 42GB."}', "ans": "O lab-ops limpou os temporarios. Espaco livre em disco atualizado para 42GB."}
    ]
    for idx, item in enumerate(delegation_tasks):
        ex_id = f"af-c{idx+111:03d}"
        messages = [
            {"role": "system", "content": "You are Orchestrator. Available agents: \n  - lab-ops (agent_dir=agents/lab-ops): system monitoring and maintenance\n  - fox-health (agent_dir=agents/fox-health): health check and diagnostics\nTools: run_agent(agent_dir, input)."},
            {"role": "user", "content": item["q"]},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "run_agent", "arguments": {"agent_dir": item["dir"], "input": item["inp"]}}}]},
            {"role": "tool", "content": item["out"], "name": "run_agent"},
            {"role": "assistant", "content": item["ans"]}
        ]
        examples.append({"id": ex_id, "source": "synthetic_agy", "category": "agentforge", "subcategory": "agent_delegation", "messages": messages})

    # Assert correct count
    assert len(examples) == 120, f"Expected 120 examples, but generated {len(examples)}"
    
    # Save path
    out_dir = "/home/conrado/repos/estudo/agents-framework/finetune/dataset"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "synth_agentforge_batch1.jsonl")
    
    with open(out_path, "w", encoding="utf-8") as f:
        for ex in examples:
            # Validate dict format inside tool call arguments
            for msg in ex["messages"]:
                if "tool_calls" in msg:
                    for tc in msg["tool_calls"]:
                        assert isinstance(tc["function"]["arguments"], dict), f"Arguments must be dict, but got: {tc['function']['arguments']} in ID {ex['id']}"
                if msg["role"] == "tool":
                    assert "name" in msg, f"Tool message must contain name field in ID {ex['id']}"
                    
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
            
    print(f"Generated {len(examples)} examples successfully in {out_path}!")

if __name__ == "__main__":
    main()
