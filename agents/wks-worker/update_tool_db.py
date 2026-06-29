import sqlite3, json, time, sys

DB_PATH = "C:/open-webui-data/webui.db"
CODE_PATH = "C:/Users/morph/fox_wks_tool.py"

with open(CODE_PATH, "r", encoding="utf-8") as f:
    content = f.read()

SPECS = [
    {"name":"get_full_health","description":"Use quando o usuario pedir status, saude ou informacoes do fox-wks. Retorna OS, CPU, RAM, GPU e disco D em uma so chamada.","parameters":{"type":"object","properties":{},"required":[]}},
    {"name":"get_system_info","description":"Retorna OS, CPU e RAM do fox-wks.","parameters":{"type":"object","properties":{},"required":[]}},
    {"name":"get_gpu_info","description":"Retorna temperatura, uso e VRAM da GPU NVIDIA do fox-wks.","parameters":{"type":"object","properties":{},"required":[]}},
    {"name":"list_directory","description":"Use para listar arquivos e pastas em D:\\ ou subdiretorio. Exemplo: list_directory('D:\\\\') ou list_directory('D:\\\\Projetos').","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho a listar. Padrao: D:\\"}},"required":[]}},
    {"name":"create_directory","description":"Use para criar uma pasta em D:\\. Sempre chame ANTES de write_file quando a pasta pode nao existir. Exemplo: create_directory('D:\\\\MinhaPasta').","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho da pasta (deve comecar com D:\\)"}},"required":["path"]}},
    {"name":"write_file","description":"USAR ESTA TOOL para salvar, criar ou gravar qualquer arquivo em D:\\. NAO use Python. NAO escreva codigo. NAO use tags XML. CHAME DIRETAMENTE write_file(path, content) com o conteudo completo. Funciona com html, txt, md, json, py, js, css e qualquer texto. Exemplo: write_file('D:\\\\Vai_Dormir\\\\index.html', '<html>...</html>').","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho completo (deve comecar com D:\\)"},"content":{"type":"string","description":"Conteudo completo do arquivo como string"}},"required":["path","content"]}},
    {"name":"read_file","description":"Use para ler o conteudo de um arquivo em D:\\. Retorna ate 8000 caracteres.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho do arquivo (deve comecar com D:\\)"}},"required":["path"]}},
    {"name":"delete_file","description":"Use para deletar um arquivo em D:\\.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho do arquivo (deve comecar com D:\\)"}},"required":["path"]}},
    {"name":"delete_directory","description":"Use para deletar uma pasta e todo seu conteudo em D:\\. Irreversivel.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Caminho da pasta (deve comecar com D:\\)"}},"required":["path"]}},
    {"name":"run_powershell","description":"Executa comando PowerShell read-only no fox-wks. Use Get-*, dir, ls. Bloqueado: shutdown, restart, format, iex.","parameters":{"type":"object","properties":{"command":{"type":"string","description":"Comando PowerShell"}},"required":["command"]}},
    {"name":"fox_server_health","description":"Use quando o usuario pedir status do fox-server (Linux). Retorna CPU, RAM, disco, GPU e containers Docker via SSH.","parameters":{"type":"object","properties":{},"required":[]}},
    {"name":"read_agent_memory","description":"Le as memorias mais recentes do agent-mesh compartilhado entre fox-server, fox-wks e Claudio.","parameters":{"type":"object","properties":{"limit":{"type":"integer","description":"Numero de memorias (padrao: 10)"}},"required":[]}},
    {"name":"write_agent_memory","description":"Grava uma memoria no agent-mesh do fox-server (compartilhado com todos os agentes do lab).","parameters":{"type":"object","properties":{"key":{"type":"string","description":"Chave da memoria"},"value":{"type":"string","description":"Valor a gravar"}},"required":["key","value"]}},
    {"name":"generate_image","description":"Gera uma imagem de alta qualidade usando o modelo FLUX Schnell localmente via ComfyUI. Retorna uma tag markdown da imagem gerada.","parameters":{"type":"object","properties":{"prompt":{"type":"string","description":"Descricao detalhada da imagem a ser gerada (em ingles). Ex: 'a majestic red fox in a forest, digital art'"}},"required":["prompt"]}},
    {"name":"generate_audio","description":"Gera uma sintese de voz (TTS) com o OmniVoice local via ComfyUI. Retorna uma tag de audio HTML para tocar o arquivo gerado.","parameters":{"type":"object","properties":{"text":{"type":"string","description":"O texto que deve ser falado pelo personagem."},"voice_profile":{"type":"string","description":"O perfil da voz a ser gerada. Deve ser 'raposa' (voz masculina, jovem adulto) ou 'tartaruga' (voz feminina, idosa, mais lenta)."}},"required":["text","voice_profile"]}}
]

con = sqlite3.connect(DB_PATH)
cur = con.execute(
    "UPDATE tool SET content=?, specs=?, updated_at=? WHERE id='fox_wks_system'",
    (content, json.dumps(SPECS), int(time.time()))
)
con.commit()
print(f"Tool gravada: {cur.rowcount} linha(s), {len(SPECS)} funcoes")
