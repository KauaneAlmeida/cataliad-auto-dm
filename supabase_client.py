# -*- coding: utf-8 -*-
"""
Cliente do Supabase via PostgREST (REST API), usando httpx async.

Tabelas: rules, dm_log (veja supabase_schema.sql).
Toda a comunicação usa a service_role key — portanto este código roda SOMENTE
no servidor (nunca exponha a service_role no frontend).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from config import COOLDOWN_SECONDS, SUPABASE_KEY, SUPABASE_REST_URL

logger = logging.getLogger("instagram-webhook.supabase")


def _headers() -> dict:
    """Cabeçalhos padrão do PostgREST (autenticação + retorno do registro)."""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _configurado() -> bool:
    """True se as credenciais do Supabase estão presentes."""
    return bool(SUPABASE_REST_URL and SUPABASE_KEY)


# ---------------------------------------------------------------------------
# Regras (rules)
# ---------------------------------------------------------------------------
async def listar_regras() -> list[dict]:
    """Retorna todas as regras (mais novas primeiro), para a UI."""
    if not _configurado():
        return []
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{SUPABASE_REST_URL}/rules",
            headers=_headers(),
            params={"select": "*", "order": "created_at.desc"},
        )
    resp.raise_for_status()
    return resp.json()


async def regras_da_publicacao(media_id: str) -> list[dict]:
    """Retorna as regras ATIVAS de uma publicação específica (usado no webhook)."""
    if not _configurado():
        return []
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{SUPABASE_REST_URL}/rules",
            headers=_headers(),
            params={
                "select": "*",
                "media_id": f"eq.{media_id}",
                "ativo": "is.true",
            },
        )
    resp.raise_for_status()
    return resp.json()


async def criar_regra(media_id: str, keyword: str, reply_text: str,
                      tipo: str = "fixa", media_url: str | None = None) -> dict:
    """Cria uma nova regra. keyword é normalizada para minúsculas."""
    payload = {
        "media_id": media_id,
        "media_url": media_url,
        "keyword": keyword.strip().lower(),
        "reply_text": reply_text,
        "tipo": tipo,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{SUPABASE_REST_URL}/rules",
            headers=_headers(),
            json=payload,
        )
    resp.raise_for_status()
    return resp.json()[0]


async def deletar_regra(rule_id: int) -> None:
    """Remove uma regra pelo id."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.delete(
            f"{SUPABASE_REST_URL}/rules",
            headers=_headers(),
            params={"id": f"eq.{rule_id}"},
        )
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Log de DMs / cooldown
# ---------------------------------------------------------------------------
async def em_cooldown(commenter_id: str) -> bool:
    """
    True se já enviamos uma DM para esse usuário nas últimas 24h.
    Lê do dm_log (cooldown PERSISTENTE — sobrevive a restarts).
    """
    if not _configurado():
        return False
    limite = datetime.now(timezone.utc) - timedelta(seconds=COOLDOWN_SECONDS)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{SUPABASE_REST_URL}/dm_log",
            headers=_headers(),
            params={
                "select": "id",
                "commenter_id": f"eq.{commenter_id}",
                "created_at": f"gte.{limite.isoformat()}",
                "limit": "1",
            },
        )
    resp.raise_for_status()
    return len(resp.json()) > 0


async def registrar_dm(commenter_id: str, media_id: str | None, rule_id: int | None,
                       comment_text: str, reply_sent: str, via_ia: bool) -> None:
    """Registra uma DM enviada (também alimenta o cooldown)."""
    if not _configurado():
        return
    payload = {
        "commenter_id": commenter_id,
        "media_id": media_id,
        "rule_id": rule_id,
        "comment_text": comment_text,
        "reply_sent": reply_sent,
        "via_ia": via_ia,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{SUPABASE_REST_URL}/dm_log",
            headers={**_headers(), "Prefer": "return=minimal"},
            json=payload,
        )
    if resp.status_code >= 400:
        logger.error("Falha ao registrar dm_log: %s %s", resp.status_code, resp.text)
