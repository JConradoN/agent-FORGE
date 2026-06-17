import json
import ollama
import time

def test_gen():
    prompt = """Você é um gerador de datasets sintéticos de alta qualidade.
Gere um exemplo de treino para o assistente Cláudio.

Categoria: tool_calling
Subcategoria: read_link
Dificuldade: medium
Tópico: Direct Preference Optimization (DPO) vs ORPO.

Regras do assistente:
1. Resposta em português (PT-BR), direta, técnica, sem rodeios ou emojis.
2. NUNCA usar markdown (proibido usar *, **, #, _, links em markdown).
3. Usar apenas hífen (-) para listas e crases (```) para código.
4. Resposta deve ser concisa e no estilo de um expert.

Retorne APENAS um objeto JSON com as seguintes chaves:
{
  "user_message": "mensagem ou link enviado pelo usuário",
  "assistant_tool_call": {
    "name": "read_link",
    "arguments": "{\\"url\\": \\"https://arxiv.org/abs/2403.07691\\"}"
  },
  "tool_output": "conteúdo resumido e realista da página (2-4 frases)",
  "assistant_final_response": "resposta final do assistente em texto puro (sem markdown, usando hífens para listas)"
}
"""

    start = time.time()
    response = ollama.chat(
        model="qwen3.5:9b",
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.7},
        format="json"
    )
    duration = time.time() - start
    print(f"Generated in {duration:.2f}s")
    print("Response:")
    print(response['message']['content'])

if __name__ == "__main__":
    test_gen()
