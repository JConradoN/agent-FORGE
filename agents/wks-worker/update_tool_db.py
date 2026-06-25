import sqlite3, json, time, sys

DB_PATH = "C:/Users/morph/.open-webui/webui.db"
CODE_PATH = "C:/Users/morph/fox_wks_tool.py"

with open(CODE_PATH, "r", encoding="utf-8") as f:
    content = f.read()

SPECS = [
    {"name":"get_full_health","description":"Retorna saude COMPLETA do fox-wks: OS (Windows 11 detectado corretamente), CPU, RAM, GPU e disco D em uma so chamada. Use este quando o usuario pedir saude ou status do fox-wks.","parameters":{"type":"object","properties":{},"required":[]}},
    {"name":"get_system_info","description":"Retorna OS, CPU e RAM do fox-wks.","parameters":{"type":"object","properties":{},"required":[]}},
    {"name":"get_gpu_info","description":"Retorna temperatura, uso e VRAM da GPU NVIDIA do fox-wks.","parameters":{"type":"object","properties":{},"required":[]}},
    {"name":"list_directory","description":"Lista arquivos e pastas em D:\\ ou subdiretório.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho a listar. Padrão: D:\\"}},"required":[]}},
    {"name":"create_directory","description":"Cria um diretório (e subdiretórios) em D:\\.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho do diretório (deve começar com D:\\)"}},"required":["path"]}},
    {"name":"write_file","description":"Grava qualquer arquivo de texto em D:\\ (html, txt, md, json, py, js, css...).","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho completo (deve começar com D:\\)"},"content":{"type":"string","description":"Conteúdo do arquivo"}},"required":["path","content"]}},
    {"name":"read_file","description":"Lê o conteúdo de um arquivo em D:\\.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho do arquivo (deve começar com D:\\)"}},"required":["path"]}},
    {"name":"delete_file","description":"Deleta um arquivo em D:\\.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho do arquivo (deve começar com D:\\)"}},"required":["path"]}},
    {"name":"delete_directory","description":"Deleta um diretório e todo conteúdo em D:\\. Irreversível.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho do diretório (deve começar com D:\\)"}},"required":["path"]}},
    {"name":"run_powershell","description":"Executa PowerShell read-only no fox-wks (Get-*, dir, ls).","parameters":{"type":"object","properties":{"command":{"type":"string","description":"Comando PowerShell"}},"required":["command"]}},
    {"name":"fox_server_health","description":"Retorna saude do fox-server: CPU, RAM, disco, GPU e containers Docker.","parameters":{"type":"object","properties":{},"required":[]}},
    {"name":"read_agent_memory","description":"Le as memorias mais recentes do agent-mesh do fox-server.","parameters":{"type":"object","properties":{"limit":{"type":"integer","description":"Numero de memorias (padrao: 10)"}},"required":[]}},
    {"name":"write_agent_memory","description":"Grava uma memoria no agent-mesh do fox-server.","parameters":{"type":"object","properties":{"key":{"type":"string","description":"Chave da memoria"},"value":{"type":"string","description":"Valor a gravar"}},"required":["key","value"]}},
]

con = sqlite3.connect(DB_PATH)
cur = con.execute(
    "UPDATE tool SET content=?, specs=?, updated_at=? WHERE id='fox_wks_system'",
    (content, json.dumps(SPECS), int(time.time()))
)
con.commit()
print(f"Tool gravada: {cur.rowcount} linha(s), {len(SPECS)} funcoes")
