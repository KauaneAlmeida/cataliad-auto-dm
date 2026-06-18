# Auto-DM do Instagram por palavra-chave (com painel e IA)

Ferramenta tipo **ManyChat** própria: um painel web onde você escolhe uma
publicação, define a **palavra-chave** que o seguidor vai comentar, e a mensagem
que ele recebe na **DM** — **fixa** (texto literal) ou **personalizada por IA**
(Claude). Tudo numa conta única.

- **Backend**: Python + FastAPI (webhook + API REST).
- **Frontend**: React (Vite) — o painel de configuração.
- **Banco**: Supabase (Postgres) — regras e log/cooldown (persistente).
- **IA**: Anthropic Claude (`claude-opus-4-8`) — personaliza a DM, 1 chamada por DM,
  só nas regras do tipo `ia`.
- Resposta sempre por **DM privada** — nunca como resposta pública ao comentário.

## Como funciona o fluxo

1. Você cria uma **regra** no painel: publicação + palavra-chave + resposta (fixa ou IA).
2. Alguém comenta a palavra-chave naquele post/Reel.
3. A Meta dispara o webhook `comments` para `/webhook`.
4. O backend acha a regra ativa daquela publicação e casa a palavra-chave.
5. **Fixa** → envia o texto literal. **IA** → o Claude personaliza a partir da sua
   instrução-base (usa o nome de quem comentou, responde à dúvida).
6. Envia a **DM privada** (respeitando o limite de 1 DM por usuário a cada 24h).

## Arquitetura

```
React (painel) ──► FastAPI ──► Instagram Graph (graph.instagram.com)
                      │   └────► Supabase (regras + log/cooldown)
                      └────────► Claude (claude-opus-4-8) [só regras 'ia']
```

## Mapa dos arquivos

| Arquivo | Papel |
|---|---|
| `main.py` | App FastAPI: webhook + API REST (`/api/posts`, `/api/rules`) |
| `config.py` | Todas as variáveis de ambiente |
| `instagram.py` | Graph API: listar posts, `/me`, enviar DM |
| `supabase_client.py` | Regras + log/cooldown via PostgREST |
| `claude_dm.py` | Personalização da DM via Claude |
| `supabase_schema.sql` | SQL das tabelas (rode no Supabase) |
| `frontend/` | Painel React (Vite) |

---

## Setup do banco (Supabase) e da IA (Claude)

### Supabase

1. No seu projeto Supabase: **SQL Editor → New query**, cole o conteúdo de
   [supabase_schema.sql](supabase_schema.sql) e rode. Isso cria as tabelas
   `rules` e `dm_log`.
2. Pegue **Project URL** e a **service_role key** em
   **Project Settings → API** e coloque no `.env`:
   ```
   SUPABASE_URL=https://SEU-PROJETO.supabase.co
   SUPABASE_KEY=sua_service_role_key
   ```
   > A `service_role` é uma chave de servidor (bypassa RLS). **Nunca** a exponha
   > no frontend — ela só vive no backend.

### Claude (Anthropic)

1. Em [console.anthropic.com](https://console.anthropic.com) gere uma **API key**
   e adicione crédito (é pago por uso; conta separada do Claude.ai).
2. No `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ANTHROPIC_MODEL=claude-opus-4-8
   ```
   Se a `ANTHROPIC_API_KEY` ficar vazia, as regras `ia` caem no texto-base sem
   personalizar (degradação graciosa).

### Rodar o painel (frontend)

```bash
cd frontend
npm install
npm run dev          # abre em http://localhost:5173
```

O painel chama o backend via proxy (`/api` → `:8000`), então rode o `uvicorn`
em paralelo (veja a Parte 2). No painel você: escolhe a publicação → define a
palavra-chave → escreve a resposta (fixa ou IA) → cria a regra.

---

## Parte 1 — Configuração do lado da Meta

> Esta é a parte mais trabalhosa. Faça na ordem.

### 1.1 Conta profissional do Instagram

- Sua conta do Instagram precisa ser **profissional** (Comercial ou Criador de Conteúdo).
- No app do Instagram: **Configurações → Conta → Mudar para conta profissional**.

### 1.2 Vincular Instagram ↔ Página do Facebook ↔ Gerenciador de Negócios

- Crie (ou use) uma **Página do Facebook**.
- Vincule a sua conta do Instagram a essa Página
  (na Página do Facebook: **Configurações → Contas vinculadas → Instagram**).
- Adicione tudo a um **Gerenciador de Negócios (Business Manager)** em
  [business.facebook.com](https://business.facebook.com): a Página e a conta do Instagram
  devem estar como ativos do seu negócio.

### 1.3 Criar um app do tipo **Business** (Negócios)

- Acesse [developers.facebook.com](https://developers.facebook.com) → **Meus Apps → Criar App**.
- Escolha o tipo **Business (Negócios)**.
- Associe o app ao seu Gerenciador de Negócios.

### 1.4 Adicionar os produtos **Instagram** e **Webhooks**

No painel do app, em **Adicionar produtos**:

- Adicione **Instagram** (Instagram API / Instagram Graph API).
- Adicione **Webhooks**.

### 1.5 Permissões necessárias

Seu app vai precisar destas três permissões:

- `instagram_basic` — ler informações básicas da conta.
- `instagram_manage_comments` — receber/gerenciar comentários.
- `instagram_manage_messages` — enviar DMs.

> **Modo de desenvolvimento:** Você pode **testar na sua própria conta** (e em contas
> adicionadas como testadoras/funções no app) **antes da App Review** ser aprovada.
> A App Review só é necessária para usar o app com o público geral em produção.

### 1.6 Pegar os valores para o `.env`

- **APP_SECRET**: em **Configurações do app → Básico → Chave secreta do app**.
- **ACCESS_TOKEN**: gere um **token de longa duração (long-lived)** da conta do Instagram.
  (Use o **Explorador da Graph API** ou o fluxo de geração de token do produto Instagram,
  trocando o token de curta duração por um de longa duração.)
- **IG_USER_ID**: o ID da sua conta profissional do Instagram (IG User ID / IG Business Account ID).
- **WEBHOOK_VERIFY_TOKEN**: uma string secreta que **você inventa** — você vai digitar
  exatamente a mesma no painel da Meta.

---

## Parte 2 — Rodar localmente

### 2.1 Instalar dependências

```bash
python -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2.2 Configurar o `.env`

```bash
cp .env.example .env
# edite o .env e preencha os valores
```

### 2.3 Subir o servidor com uvicorn

```bash
uvicorn main:app --reload --port 8000
```

O serviço sobe em `http://localhost:8000`. O webhook fica em `http://localhost:8000/webhook`.

### 2.4 Expor para a internet com ngrok

A Meta precisa acessar seu endpoint por uma URL pública **HTTPS**. Use o
[ngrok](https://ngrok.com) para expor a porta local:

```bash
ngrok http 8000
```

O ngrok te dá uma URL pública, por exemplo `https://abcd-1234.ngrok-free.app`.
A sua URL de callback do webhook será:

```
https://abcd-1234.ngrok-free.app/webhook
```

> A cada vez que você reinicia o ngrok (no plano grátis), a URL muda — então você
> precisa atualizar a URL de callback no painel da Meta.

---

## Parte 3 — Registrar o webhook no painel da Meta

1. No painel do app → produto **Webhooks** (ou na configuração de Webhooks do Instagram).
2. Em **Callback URL**, coloque a URL pública do ngrok com `/webhook` no final:
   `https://abcd-1234.ngrok-free.app/webhook`
3. Em **Verify Token**, digite **exatamente** o mesmo valor que você colocou em
   `WEBHOOK_VERIFY_TOKEN` no `.env`.
4. Clique em **Verificar e salvar**. A Meta vai fazer um `GET /webhook` e o seu
   serviço vai devolver o `hub.challenge` — se tudo estiver certo, a verificação passa.
5. Depois de verificado, **inscreva-se (Subscribe) no campo `comments`** para a conta
   do Instagram. (É esse campo que dispara o webhook quando alguém comenta.)

---

## Parte 4 — Testar

1. Deixe o servidor local rodando (`uvicorn`) e o `ngrok` ativo.
2. De **outra conta** do Instagram (ou peça para alguém), comente uma das
   palavras-chave (ex.: `preço`) em um post/Reel seu.
3. Em segundos, essa conta deve receber uma **DM** com a resposta configurada.
4. Acompanhe os logs no terminal — cada ação é registrada:
   - DM enviada
   - assinatura rejeitada
   - palavra-chave não casou (keyword miss)
   - DM pulada por cooldown

> **Lembre-se das regras da Meta (2026):** há uma **janela de 7 dias** para responder
> por DM quem comentou, e um **limite rígido de 1 DM por usuário a cada 24h** em
> gatilhos por comentário. Este serviço já respeita o limite de 24h com um cooldown.

---

## Parte 5 — Editar as respostas por palavra-chave

Abra o arquivo [main.py](main.py) e edite o dicionário `KEYWORD_REPLIES` no topo:

```python
KEYWORD_REPLIES = {
    "preco": "Oi! O valor é R$ 197...",
    "preço": "Oi! O valor é R$ 197...",
    "link":  "Aqui está o link: https://seusite.com.br",
    # adicione quantas quiser...
}
```

Dicas:

- Escreva as **chaves sempre em minúsculas** (o texto do comentário é comparado em minúsculas).
- Inclua **variantes com e sem acento** (ex.: `preco` e `preço`), pois muita gente comenta sem acento.
- Reinicie o servidor (ou deixe o `--reload` do uvicorn cuidar disso) após editar.

---

## Parte 6 — Deploy em produção (Azure App Service)

Para produção, hospede o serviço em um servidor com URL HTTPS fixa. Exemplo com
**Azure App Service**:

1. Crie um **App Service** (runtime Python).
2. Faça o deploy do código (Git, ZIP deploy, GitHub Actions etc.).
3. Comando de inicialização (Startup Command):
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   (O Azure costuma expor a porta via variável `PORT`; ajuste se necessário para
   `--port $PORT`.)
4. **NÃO use o arquivo `.env` em produção.** Em vez disso, defina as variáveis de
   ambiente no painel do Azure:
   **App Service → Configurações → Variáveis de ambiente (Application settings)**:
   - `WEBHOOK_VERIFY_TOKEN`
   - `IG_ACCESS_TOKEN`
   - `APP_SECRET`
   - `IG_USER_ID`
   - `GRAPH_VERSION`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `ANTHROPIC_API_KEY`
   - `ANTHROPIC_MODEL`
5. Use a URL pública do App Service como Callback URL do webhook no painel da Meta
   (ex.: `https://seu-app.azurewebsites.net/webhook`).
6. **Frontend**: rode `npm run build` na pasta `frontend/` e publique a pasta
   `dist/` (Vercel, Netlify, Azure Static Web Apps, ou sirva pelo próprio FastAPI).
   Ajuste a base da API se o frontend ficar em outro domínio.

> **Cooldown:** o limite de "1 DM por usuário a cada 24h" agora é **persistente**
> no Supabase (tabela `dm_log`) — sobrevive a restarts e funciona entre múltiplas
> instâncias. Não depende mais de memória.

---

## Estrutura do projeto

```
.
├── main.py              # FastAPI: webhook + API REST
├── config.py            # variáveis de ambiente
├── instagram.py         # Graph API (posts, /me, DM)
├── supabase_client.py   # regras + log/cooldown (PostgREST)
├── claude_dm.py         # personalização da DM via Claude
├── supabase_schema.sql  # SQL das tabelas
├── test_local.py        # testes locais (mock de I/O)
├── requirements.txt
├── .env.example
├── frontend/            # painel React (Vite)
│   ├── src/App.jsx
│   └── ...
└── README.md
```
