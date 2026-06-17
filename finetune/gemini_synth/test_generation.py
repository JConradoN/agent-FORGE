import json
import ollama
import time

def test_category(cat, subcat, difficulty, topic, details):
    prompt = f"""Você é um gerador de dados de treino para o assistente pessoal Cláudio.
Gere um exemplo realista em português (PT-BR) de acordo com os seguintes dados:

Categoria: {cat}
Subcategoria: {subcat}
Dificuldade: {difficulty}
Tópico: {topic}
Instruções específicas: {details}

Regras para a resposta do assistente (assistant_final_response):
1. Deve ser no tom do Cláudio: expert, direto, sem rodeios, sem emojis.
2. Não use nenhum caractere de formatação markdown (sem *, **, #, _, ou links [text](url)).
3. Use apenas hífen (-) para listas e crases (```) para código.

Retorne APENAS um objeto JSON com a seguinte estrutura:
{{
  "user_message": "A mensagem enviada pelo usuário.",
  "tool_name": "Nome da ferramenta a chamar ('read_link' ou 'run_bash' ou null se não houver chamada)",
  "tool_args": {{ "url": "..." }} ou {{ "command": "..." }} ou null,
  "tool_output": "A saída simulada da ferramenta como string" ou null,
  "assistant_final_response": "A resposta final do assistente em texto puro (ou pedido de confirmação no caso de comandos destrutivos)"
}}
"""

    start = time.time()
    try:
        response = ollama.chat(
            model="qwen3.5:9b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.7, "num_predict": 1024},
            format="json"
        )
        duration = time.time() - start
        print(f"\n--- {cat}/{subcat} ({difficulty}) - {duration:.2f}s ---")
        print(response['message']['content'])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test read_link
    test_category(
        "tool_calling", "read_link", "easy", 
        "Artigo sobre RAG avançado", 
        "O usuário manda um link do arXiv sobre RAG e o assistente lê e resume."
    )
    # Test run_bash (non-destructive)
    test_category(
        "tool_calling", "run_bash", "medium", 
        "Checar processos consumindo GPU", 
        "O usuário pergunta quais processos estão consumindo memória na GPU e o assistente roda nvidia-smi."
    )
    # Test run_bash (destructive)
    test_category(
        "tool_calling", "run_bash", "hard", 
        "Parar o container do n8n", 
        "O usuário pede para parar o container do n8n. Por ser ação destrutiva, o assistente DEVE pedir confirmação antes, sem fazer chamada de ferramenta."
    )
    # Test chat/persona
    test_category(
        "chat", "persona", "medium", 
        "Diferença entre DPO e ORPO", 
        "O usuário pede uma explicação técnica comparando DPO e ORPO."
    )
    # Test refusal
    test_category(
        "refusal", "mixed", "easy", 
        "Fazer git commit", 
        "O usuário pede para fazer um git commit. O assistente deve recusar de forma direta, pois não faz operações de versionamento."
    )
