# -*- coding: utf-8 -*-
"""
Serviço de automação de DM do Instagram por palavra-chave, com:
  - Webhook que recebe comentários e responde por DM (fixa ou personalizada por IA);
  - API REST para o frontend (listar publicações, CRUD de regras);
  - Regras e cooldown persistidos no Supabase.

Fluxo do webhook:
  comentário -> webhook `comments` -> acha regras ATIVAS daquela publicação ->
  casa a palavra-chave -> (fixa: texto literal | ia: Claude personaliza) -> DM.

Estrutura:
  config.py          -> variáveis de ambiente
  supabase_client.py -> regras + log/cooldown (PostgREST)
  instagram.py       -> Graph API (posts, /me, enviar DM)
  claude_dm.py       -> personalização via claude-opus-4-8
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

import os

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import claude_dm
import instagram
import supabase_client as db
from config import APP_SECRET, IG_USER_ID, WEBHOOK_VERIFY_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("instagram-webhook")

app = FastAPI(title="Instagram Auto-DM")

# CORS liberado para o frontend React em dev (ajuste as origens em produção).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Id real (app-scoped) da própria conta — detectado no startup via /me.
MY_APP_SCOPED_ID: str = ""


@app.on_event("startup")
async def _startup() -> None:
    global MY_APP_SCOPED_ID
    try:
        MY_APP_SCOPED_ID = await instagram.detectar_id_da_conta()
    except Exception as exc:
        MY_APP_SCOPED_ID = IG_USER_ID
        logger.warning("Falha ao detectar id via /me (%s) — usando IG_USER_ID.", exc)


# ===========================================================================
# Validação de assinatura (X-Hub-Signature-256)
# ===========================================================================
def _verify_signature(payload: bytes, signature_header: str | None) -> bool:
    """Valida HMAC-SHA256 do corpo bruto contra o APP_SECRET. Pula se não houver secret."""
    if not APP_SECRET:
        logger.warning("APP_SECRET ausente — pulando validacao de assinatura (so testes locais).")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    received = signature_header.split("=", 1)[1]
    expected = hmac.new(APP_SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received, expected)


# ===========================================================================
# Webhook — verificação (GET)
# ===========================================================================
@app.get("/webhook")
async def verify_subscription(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == WEBHOOK_VERIFY_TOKEN:
        logger.info("Webhook verificado com sucesso pela Meta.")
        return Response(content=params.get("hub.challenge") or "", media_type="text/plain")
    logger.warning("Falha na verificacao do webhook.")
    return Response(content="Forbidden", status_code=403)


# ===========================================================================
# Webhook — eventos (POST)
# ===========================================================================
@app.post("/webhook")
async def receive_event(request: Request):
    raw_body = await request.body()
    if not _verify_signature(raw_body, request.headers.get("X-Hub-Signature-256")):
        logger.warning("Assinatura invalida — rejeitada (403).")
        return Response(content="Invalid signature", status_code=403)

    try:
        payload = await request.json()
    except Exception:
        return Response(content="OK", status_code=200)

    if payload.get("object") != "instagram":
        return Response(content="OK", status_code=200)

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            await _processar_comentario(change.get("value", {}) or {})

    # Sempre 200 rápido.
    return Response(content="OK", status_code=200)


async def _processar_comentario(value: dict) -> None:
    """Processa um único comentário: filtros, casamento de regra, envio da DM."""
    comment_text = (value.get("text") or "").strip()
    commenter = value.get("from", {}) or {}
    commenter_id = commenter.get("id")
    username = commenter.get("username")
    parent_id = value.get("parent_id")
    media_id = (value.get("media") or {}).get("id") or value.get("media_id")

    # Só comentários de nível superior (ignora respostas a comentários).
    if parent_id:
        logger.info("Comentario ignorado (resposta, parent_id=%s).", parent_id)
        return
    # Nunca responder à própria conta.
    if commenter_id and commenter_id == MY_APP_SCOPED_ID:
        logger.info("Comentario ignorado (propria conta).")
        return
    if not comment_text or not commenter_id or not media_id:
        logger.info("Comentario ignorado (sem texto/autor/media_id).")
        return

    # Busca as regras ATIVAS daquela publicação.
    regras = await db.regras_da_publicacao(media_id)
    if not regras:
        logger.info("Nenhuma regra ativa para a publicacao %s.", media_id)
        return

    # Casa a primeira palavra-chave contida no comentário (texto em minúsculas).
    texto_lower = comment_text.lower()
    regra = next((r for r in regras if r["keyword"] in texto_lower), None)
    if regra is None:
        logger.info("Nenhuma palavra-chave casou para: %r", comment_text)
        return

    # Cooldown persistente: 1 DM por usuário a cada 24h.
    if await db.em_cooldown(commenter_id):
        logger.info("DM pulada (cooldown 24h) para user_id=%s.", commenter_id)
        return

    # Monta a resposta: fixa (literal) ou ia (Claude personaliza).
    via_ia = regra.get("tipo") == "ia"
    if via_ia:
        reply = await claude_dm.gerar_dm(regra["reply_text"], comment_text, username)
    else:
        reply = regra["reply_text"]

    enviado = await instagram.enviar_dm(commenter_id, reply)
    if enviado:
        # Registra (alimenta o cooldown). Só registramos quando de fato enviou.
        await db.registrar_dm(
            commenter_id=commenter_id,
            media_id=media_id,
            rule_id=regra["id"],
            comment_text=comment_text,
            reply_sent=reply,
            via_ia=via_ia,
        )


# ===========================================================================
# API REST para o frontend
# ===========================================================================
@app.get("/api/me")
async def api_perfil():
    """Dados do perfil do Instagram para o cabeçalho da UI."""
    try:
        return {"profile": await instagram.perfil()}
    except Exception as exc:
        logger.error("Erro ao buscar perfil: %s", exc)
        return Response(content=f'{{"error": "{exc}"}}', status_code=502, media_type="application/json")


@app.get("/api/posts")
async def api_listar_posts():
    """Lista as publicações do Instagram para a UI escolher."""
    try:
        return {"posts": await instagram.listar_publicacoes()}
    except Exception as exc:
        logger.error("Erro ao listar publicacoes: %s", exc)
        return Response(content=f'{{"error": "{exc}"}}', status_code=502, media_type="application/json")


@app.get("/api/rules")
async def api_listar_regras():
    """Lista todas as regras (para a UI)."""
    return {"rules": await db.listar_regras()}


class NovaRegra(BaseModel):
    media_id: str
    keyword: str
    reply_text: str
    tipo: str = "fixa"          # 'fixa' | 'ia'
    media_url: Optional[str] = None


@app.post("/api/rules")
async def api_criar_regra(regra: NovaRegra):
    """Cria uma nova regra (post + keyword + resposta)."""
    if regra.tipo not in ("fixa", "ia"):
        return Response(content='{"error": "tipo invalido"}', status_code=400, media_type="application/json")
    criada = await db.criar_regra(
        media_id=regra.media_id,
        keyword=regra.keyword,
        reply_text=regra.reply_text,
        tipo=regra.tipo,
        media_url=regra.media_url,
    )
    return {"rule": criada}


@app.delete("/api/rules/{rule_id}")
async def api_deletar_regra(rule_id: int):
    """Remove uma regra pelo id."""
    await db.deletar_regra(rule_id)
    return {"ok": True}


class Simulacao(BaseModel):
    media_id: str
    comment_text: str
    username: Optional[str] = "seguidor_teste"


@app.post("/api/simular")
async def api_simular(sim: Simulacao):
    """
    MODO DEMO — roda exatamente a mesma lógica do webhook (casar palavra-chave +
    gerar a DM, com IA quando a regra for do tipo 'ia'), mas SEM enviar a DM de
    verdade. Serve para demonstrar o fluxo comentário → DM no vídeo da App Review,
    já que o webhook real só dispara após a aprovação da Meta.

    Retorna o que aconteceria: qual regra casou e qual DM seria enviada.
    """
    texto = (sim.comment_text or "").strip()
    if not texto:
        return {"matched": False, "motivo": "comentário vazio"}

    regras = await db.regras_da_publicacao(sim.media_id)
    if not regras:
        return {"matched": False, "motivo": "nenhuma regra ativa para esta publicação"}

    texto_lower = texto.lower()
    regra = next((r for r in regras if r["keyword"] in texto_lower), None)
    if regra is None:
        return {"matched": False, "motivo": "nenhuma palavra-chave casou"}

    via_ia = regra.get("tipo") == "ia"
    if via_ia:
        reply = await claude_dm.gerar_dm(regra["reply_text"], texto, sim.username)
    else:
        reply = regra["reply_text"]

    logger.info("[DEMO] keyword=%r tipo=%s -> DM simulada: %r", regra["keyword"], regra["tipo"], reply)
    return {
        "matched": True,
        "keyword": regra["keyword"],
        "tipo": regra["tipo"],
        "via_ia": via_ia,
        "dm": reply,
    }


@app.get("/oauth/callback")
async def oauth_callback(request: Request):
    """
    Callback do OAuth do "login da empresa no Instagram".
    A Meta redireciona o usuário pra cá após autorizar o app, com ?code=...
    (ou ?error=...). Por enquanto só exibimos o resultado — a troca do code por
    token de longa duração pode ser implementada quando o app for distribuído.
    """
    params = request.query_params
    if params.get("error"):
        return Response(
            content=f"Autorizacao negada: {params.get('error_description', params.get('error'))}",
            media_type="text/plain",
            status_code=400,
        )
    code = params.get("code")
    if code:
        logger.info("OAuth callback recebeu code (primeiros chars): %s...", code[:12])
        return Response(
            content="Autorizacao recebida com sucesso! Pode fechar esta aba.",
            media_type="text/plain",
        )
    return Response(content="Callback do OAuth (sem code).", media_type="text/plain")


@app.get("/privacy")
async def privacy_policy():
    """
    Política de Privacidade exigida pela Meta para publicar o app / App Review.
    Servida como HTML simples. A URL pública (via ngrok ou produção) deve ser
    colada em Configurações do app > Básico > URL da Política de Privacidade.
    """
    html = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Política de Privacidade — Cataliad Auto DM</title>
<style>
 body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
   max-width:760px;margin:40px auto;padding:0 20px;line-height:1.6;color:#222}
 h1{border-bottom:2px solid #e1306c;padding-bottom:8px}
 h2{margin-top:28px;color:#333}
 small{color:#666}
</style></head><body>
<h1>Política de Privacidade — Cataliad Auto DM</h1>
<small>Última atualização: 17 de junho de 2026</small>

<p>Este serviço ("Cataliad Auto DM") automatiza respostas por mensagem direta (DM)
no Instagram quando seguidores comentam palavras-chave nas publicações da conta
profissional <strong>@cataliad.dev</strong>. Esta política descreve quais dados
tratamos e como.</p>

<h2>1. Dados que coletamos</h2>
<ul>
 <li><strong>Comentários públicos</strong> nas publicações da conta: texto do
   comentário, identificador e nome de usuário de quem comentou.</li>
 <li><strong>Identificador do remetente da DM</strong>, necessário para enviar a
   resposta automática.</li>
 <li><strong>Registro de envios</strong> (qual DM foi enviada e quando), para
   respeitar limites de frequência (1 DM por usuário a cada 24h).</li>
</ul>

<h2>2. Como usamos os dados</h2>
<p>Os dados são usados exclusivamente para identificar a palavra-chave no
comentário e enviar a mensagem direta correspondente. Quando configurado, o
texto do comentário pode ser enviado a um modelo de linguagem (Anthropic Claude)
apenas para gerar uma resposta personalizada. Não vendemos nem compartilhamos
dados com terceiros para publicidade.</p>

<h2>3. Armazenamento e retenção</h2>
<p>As regras de automação e o registro de envios são armazenados em banco de
dados (Supabase). Os dados são mantidos apenas enquanto necessários para a
operação do serviço e podem ser excluídos a qualquer momento.</p>

<h2>4. Compartilhamento com terceiros</h2>
<p>Utilizamos: a <strong>API do Instagram (Meta)</strong> para receber comentários
e enviar DMs; o <strong>Supabase</strong> para armazenamento; e a
<strong>Anthropic (Claude)</strong> para gerar respostas personalizadas (quando
ativado). Cada um trata os dados conforme suas próprias políticas.</p>

<h2>5. Seus direitos</h2>
<p>Você pode solicitar a exclusão dos seus dados ou parar de receber mensagens a
qualquer momento, entrando em contato pelo e-mail abaixo.</p>

<h2>6. Contato</h2>
<p>Dúvidas sobre esta política: <strong>rr2trafego@gmail.com</strong></p>
</body></html>"""
    return Response(content=html, media_type="text/html")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "instagram-auto-dm"}


# ===========================================================================
# Servir o frontend React buildado (produção) — DEVE ficar por último, depois
# de todas as rotas /api, /webhook, etc. Em dev (sem build) é ignorado.
# ===========================================================================
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")

if os.path.isdir(_FRONTEND_DIST):
    # Serve os assets estáticos (JS/CSS) e o index.html na raiz.
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")),
        name="assets",
    )

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))
else:
    @app.get("/")
    async def health_root():
        return {"status": "ok", "service": "instagram-auto-dm", "frontend": "nao buildado"}
