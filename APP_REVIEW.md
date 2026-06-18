# Guia de App Review — Cataliad Auto DM

Este arquivo reúne tudo que você precisa para submeter o app à análise da Meta e
liberar o **Advanced Access** das permissões de comentário/mensagem (sem isso, o
fluxo comentário → DM não funciona com o público em geral).

> **Por que precisa:** no fluxo *Instagram API with Instagram Login*, as
> permissões `instagram_business_manage_comments` e `instagram_business_manage_messages`
> só funcionam para comentários/DMs de terceiros em **Advanced Access**, que é
> concedido **após** a App Review aprovada. No modo de desenvolvimento, a API
> mostra `comments_count` mas devolve a lista de comentários vazia — foi o que
> confirmamos nos testes.

---

## Estado atual (tudo pronto, menos a aprovação)

| Item | Status |
|---|---|
| Backend (webhook + API REST) | ✅ funcionando |
| Recebimento de webhook (teste do painel → HTTP 200) | ✅ provado |
| Inscrição no campo `comments` | ✅ ativa |
| Supabase (regras + cooldown) | ✅ conectado |
| Claude (personalização da DM) | ✅ testado |
| **Advanced Access das permissões** | ❌ **pendente de App Review** |

App: **Cataliad Auto DM** (Facebook App ID `943942295358451`)
App do Instagram: **Cataliad Auto DM-IG** (`27721807214103851`)

---

## Passo 1 — Política de Privacidade (OBRIGATÓRIA)

Já está pronta e sendo servida pelo backend em **`/privacy`**.

- URL pública (via ngrok): `https://SEU-NGROK.ngrok-free.dev/privacy`
- Cole em: **Configurações do app → Básico → URL da Política de Privacidade**

> ⚠️ A URL do ngrok muda quando reinicia. Para a App Review (que leva dias), o
> ideal é hospedar em uma URL **fixa** — opções gratuitas: publicar o arquivo em
> uma página estática (GitHub Pages, Vercel, Netlify) ou hospedar o backend em
> produção (Azure App Service, conforme o README). A Meta vai acessar essa URL
> durante a análise, então ela precisa estar no ar de forma estável.

---

## Passo 2 — Ajustar os Casos de Uso

No app há casos de uso de **Marketing/Anúncios** que NÃO são necessários.

- Em **Casos de uso**, mantenha apenas **"API do Instagram"** (mensagens/comentários).
- Os 3 itens de permissão que importam (já aparecem com ✅ no caso de uso):
  - `instagram_business_basic`
  - `instagram_business_manage_comments`
  - `instagram_business_manage_messages`

---

## Passo 3 — Justificativa de cada permissão (cole no formulário)

A Meta pede, para cada permissão, uma explicação de **como** o app usa e **por que**
precisa. Use os textos abaixo (em pt-BR; se o formulário exigir inglês, há versão
em inglês logo após).

### instagram_business_basic
> O app usa esta permissão para identificar a conta profissional do Instagram do
> próprio dono e ler informações básicas do perfil (id e nome de usuário),
> necessárias para associar os comentários recebidos à conta correta e operar a
> automação de respostas.

### instagram_business_manage_comments
> O app usa esta permissão para receber, via webhook, os comentários feitos nas
> publicações da própria conta e ler o texto desses comentários. Isso é essencial
> para detectar uma palavra-chave configurada pelo dono da conta (ex.: "preço") e
> então acionar o envio de uma resposta por mensagem direta.

### instagram_business_manage_messages
> O app usa esta permissão para enviar uma mensagem direta (DM) ao usuário que
> comentou uma palavra-chave, entregando a resposta configurada pelo dono da
> conta. O envio respeita os limites da plataforma (janela de 7 dias e no máximo
> 1 DM por usuário a cada 24h).

#### Versão em inglês (caso o formulário exija)
- **instagram_business_basic**: The app uses this permission to identify the
  owner's Instagram professional account and read basic profile info (id and
  username), needed to associate incoming comments with the correct account.
- **instagram_business_manage_comments**: The app uses this permission to receive
  (via webhook) and read comments on the account's own posts, in order to detect a
  keyword configured by the account owner and trigger an automated direct-message
  reply.
- **instagram_business_manage_messages**: The app uses this permission to send a
  direct message to the user who commented a keyword, delivering the reply
  configured by the account owner, respecting platform limits (7-day window and
  at most 1 DM per user per 24h).

---

## Passo 4 — Roteiro do vídeo de demonstração (OBRIGATÓRIO)

> **Importante (paradoxo do modo dev):** o fluxo comentário→DM REAL só dispara
> APÓS a aprovação (Advanced Access). No modo de desenvolvimento, a API não
> entrega os comentários nem dispara o webhook deles. Por isso o vídeo demonstra
> as partes que JÁ funcionam em dev: o recebimento real do webhook (botão "Teste"
> da Meta) e a lógica de casar palavra-chave + gerar a DM (o **Modo Demo** do
> painel, que roda o mesmo código do webhook). Isso é aceito pela Meta.

Grave a tela mostrando, nesta ordem:

1. **Login** no painel do app (developers.facebook.com): é o app "Cataliad Auto DM",
   você é admin, a conta @cataliad.dev está conectada e o campo `comments` está assinado.
2. **Painel da ferramenta** (localhost:5173): mostre o perfil @cataliad.dev no topo,
   escolha uma publicação e **crie uma regra** (palavra-chave → resposta). Crie uma
   regra do tipo **IA** para demonstrar a personalização.
3. **Modo Demo** (seção "🧪 Testar fluxo"): digite um comentário com a palavra-chave
   e clique em **Simular comentário**. O chat mostra o comentário entrando e a
   **DM sendo gerada** (com a IA personalizando, quando a regra for do tipo ia).
   Isso demonstra a lógica de `manage_comments` (ler/casar) + a montagem da DM.
4. **Botão "Teste" do webhook** (painel da Meta → campo `comments` → "Teste" →
   "Enviar para o servidor"): mostre o servidor recebendo o POST e respondendo
   **HTTP 200**. Isso prova o recebimento real do webhook de comentários.
5. **Narração/legenda**: "O app se inscreve no webhook de comentários (demonstrado
   pelo teste, HTTP 200). Quando um seguidor comenta uma palavra-chave configurada
   pelo dono da conta, o app detecta a palavra e envia a resposta por mensagem
   direta — lógica demonstrada no simulador. Em produção, com Advanced Access, esse
   fluxo dispara automaticamente a cada comentário."

> Dica: 1–3 minutos. Deixe explícito cada permissão: `manage_comments` (receber/ler
> comentário, visto no teste do webhook + no simulador) e `manage_messages` (montar/
> enviar a DM, visto no simulador). Suba como link não listado do YouTube ou faça
> upload direto no formulário.

---

## Passo 5 — Submeter e aguardar

1. Em **Publicar** (ou **Análise do app → Permissões e recursos**), solicite
   **Advanced Access** para as 3 permissões.
2. Anexe as justificativas (Passo 3) e o vídeo (Passo 4).
3. Clique em **Enviar para análise**.
4. **Aguarde a aprovação da Meta** (normalmente alguns dias, pode chegar a ~2 semanas).
5. Aprovado → as permissões viram Advanced Access automaticamente. **Nada precisa
   mudar no código** — o webhook de comentário passa a disparar e a DM sai sozinha.

---

## Depois da aprovação — checklist de produção

- [ ] Hospedar o backend em URL fixa (Azure App Service — ver README) em vez do ngrok.
- [ ] Atualizar a Callback URL do webhook e a URL da Política de Privacidade para o domínio fixo.
- [ ] Refazer o `subscribed_apps` (subscribe do campo comments) com o token no host de produção.
- [ ] Confirmar que o token de longa duração (IGAA..., ~60 dias) será renovado antes de expirar.
