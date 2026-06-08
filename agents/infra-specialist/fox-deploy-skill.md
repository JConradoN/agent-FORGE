---
name: "fox-deploy"
description: "Automatiza deploy completo de serviços Docker no fox-server com verificação de mudanças, testes, build, deployment e notificações via Telegram."
---

# 🦊 Skill: fox-deploy

## Quando usar esta skill

Use a `fox-deploy` quando precisar automatizar o processo de deploy de um serviço Docker no seu servidor. Esta skill é ideal para:

- Implementar CI/CD pipelines manuais ou automáticos
- Fazer deploys após commits em repositórios Git
- Garantir que todos os testes passem antes do deployment
- Recriar containers com as novas alterações da imagem
- Notificar a equipe sobre o status do deploy via Telegram

**Não use** para:
- Deploys de serviços não-Docker (aplicativos nativos)
- Ambientes sem acesso ao Git ou Docker instalado
- Serviços que requerem interação manual complexa durante o build

## Pré-requisitos

Antes de usar esta skill, certifique-se de ter:

1. **Acesso SSH** ao servidor `fox-server` (ou terminal local com docker)
2. **Docker e Docker Compose** instalados e rodando no sistema
3. **Git instalado** para verificar mudanças no repositório
4. **Conta do Telegram Bot API** configurada:
   - Token do bot (`BOT_TOKEN`)
   - Chat ID do canal/grupo de notificações
5. **Repositório Git** com o projeto a ser deployado (local ou remoto)
6. **Arquivo `docker-compose.yml`** no diretório raiz do projeto

## Passo a passo

### 1️⃣ Verificar mudanças no git

```bash
# Verifica se há alterações não commitadas e commits recentes
git status && git log -n 5 --oneline
```

**O que verificar:**
- ✅ Há novos commits desde o último deploy?
- ⚠️ Existem arquivos `.env` ou `docker-compose.yml` modificados?
- ❌ Se tudo estiver limpo, pode ser um rebase/merge — verifique se é seguro prosseguir

### 2️⃣ Rodar os testes do projeto

```bash
# Execute os testes (substitua pelo comando específico do seu projeto)
npm test || pytest || go test ./... || bundle exec rake test
```

**Dica:** Se o projeto tiver um script de teste no `package.json` ou similar, use-o:
```bash
npm run test:e2e && npm run lint
```

### 3️⃣ Fazer build da imagem Docker

```bash
# Build com cache e tags para facilitar rollback
docker-compose build --no-cache --pull || docker compose build --no-cache --pull
```

**O que acontece aqui:**
- Imagens são baixadas/criadas conforme necessário
- Tags podem ser adicionadas (ex: `myapp:v1.2.3`)
- Se o build falhar, pare e corrija antes de prosseguir

### 4️⃣ Deploy com docker compose

```bash
# Recria containers com as novas imagens
docker-compose up -d --force-recreate || docker compose up -d --force-recreate
```

**O que isso faz:**
- Para os containers existentes (segurança)
- Remove volumes de rede antigos se necessário
- Inicia novos containers com a nova imagem

### 5️⃣ Verificar status dos containers

```bash
# Lista containers e verifica saúde
docker ps -a --filter "name=myapp" && docker inspect myapp | grep Healthcheck || docker compose ps
```

**Verifique:**
- Status: `Up (healthy)` ou pelo menos `Up` sem erros de healthcheck
- Exit code do último comando no container é 0
- Logs não mostram crashes imediatos após o start

### 6️⃣ Notificar via Telegram (via Claudio)

```bash
# Envia notificação de sucesso/falha no Telegram
claudio send --api-token=SEU_TOKEN \
  --chat-id=SEU_CHAT_ID \
  "🦊 Deploy fox-deploy: SUCESSO ✅\n\nServiço 'myapp' foi deployado com sucesso!" || claudio send --api-token=...
```

**Mensagem de erro (caso algo falhe):**
```bash
claudio send --api-token=SEU_TOKEN \
  --chat-id=SEU_CHAT_ID \
  "🦊 Deploy fox-deploy: FALHA ❌\n\nOcorreu um problema no deploy. Verifique os logs."
```

## Tratamento de erros comuns

| Erro | Causa provável | Solução |
|------|----------------|---------|
| `git status` limpo mas sem commits recentes | Rebase/merge ou último commit foi há muito tempo | Verificar se é seguro prosseguir; talvez pular deploy automático |
| Testes falham (`npm test`, etc.) | Código não está pronto para produção | Corrigir bugs, rodar testes novamente antes de continuar |
| `docker-compose build` com erro 127/64 | Docker não instalado ou sem permissões | Instalar docker: `curl -fsSL https://get.docker.com \| bash && sudo usermod -aG docker $USER` |
| Container sai do status `Up (healthy)` para `Exited` | Imagem com erro de build, dependências faltando, etc. | Verificar logs: `docker-compose logs --tail=50 myapp` e corrigir a imagem |
| Notificação Telegram não chega | Token/Chat ID inválidos ou bloqueio do bot | Gerar novo token no BotFather; verificar permissões de envio na API |

## Exemplos de uso

### 📦 Deploy após commit local (manual)

```bash
# 1. Verificar mudanças
git status && git log -n 3 --oneline

# 2. Rodar testes
npm test

# 3-6. Build, deploy e notificação
docker-compose build --no-cache --pull \
&& docker-compose up -d --force-recreate \
&& echo "✅ Deploy concluído" || { echo "❌ Falha no deploy"; exit 1; }

claudio send --api-token=YOUR_TOKEN --chat-id=YOUR_CHAT_ID \
  "🦊 Deploy de 'myapp' realizado com sucesso!"
```

### 🔄 Integração em CI/CD (GitHub Actions, GitLab CI)

No seu arquivo `.github/workflows/deploy.yml`:

```yaml
- name: Run fox-deploy skill steps
  run: |
    git status && git log -n 5 --oneline
    npm test
    docker-compose build --no-cache --pull
    docker-compose up -d --force-recreate
    docker ps -a --filter "name=myapp"

- name: Notify via Telegram (success)
  if: success()
  run: |
    claudio send \
      --api-token=${{ secrets.TELEGRAM_TOKEN }} \
      --chat-id=${{ secrets.CHAT_ID }} \
      "🦊 Deploy de ${{ github.event.repository.name }} v${{ github.sha }} concluído!"

- name: Notify via Telegram (failure)
  if: failure()
  run: |
    claudio send \
      --api-token=${{ secrets.TELEGRAM_TOKEN }} \
      --chat-id=${{ secrets.CHAT_ID }} \
      "🦊 Deploy de ${{ github.event.repository.name }} falhou. Verifique os logs."
```

### 🚀 Script wrapper para deploy rápido (fox-deploy.sh)

Crie um script que encapsula todos os passos:

```bash
#!/bin/bash
# fox-deploy.sh - Wrapper para a skill fox-deploy

set -e  # Para falhar imediatamente em erro

echo "🦊 Iniciando processo de deploy..."

git status && git log -n 5 --oneline || true

npm test || exit 1

docker-compose build --no-cache --pull
docker-compose up -d --force-recreate

if docker ps | grep myapp; then
    echo "✅ Deploy concluído com sucesso!"
else
    echo "❌ Container não está rodando. Verifique os logs."
fi

claudio send \
  --api-token=${TELEGRAM_TOKEN} \
  --chat-id=${CHAT_ID} \
  "🦊 Deploy de 'myapp' realizado! ✅" || true
```

Use-o assim: `./fox-deploy.sh`

---

**SKILL READY**: Pronto para uso no seu fluxo de deploy Dockerizado. 🚀
