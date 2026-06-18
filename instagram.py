# -*- coding: utf-8 -*-
"""
Chamadas à Instagram Graph API (fluxo "Instagram API with Instagram Login").
Host: graph.instagram.com. Token: IG_ACCESS_TOKEN (IGAA..., ~60 dias).
"""

from __future__ import annotations

import logging

import httpx

from config import GRAPH_BASE_URL, IG_ACCESS_TOKEN

logger = logging.getLogger("instagram-webhook.instagram")


async def detectar_id_da_conta() -> str:
    """
    Descobre o id real (app-scoped) da própria conta via /me.
    Esse é o id que aparece como from.id nos webhooks.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{GRAPH_BASE_URL}/me",
            params={"fields": "id,username", "access_token": IG_ACCESS_TOKEN},
        )
    resp.raise_for_status()
    data = resp.json()
    logger.info("Conta detectada: id=%s username=%s", data.get("id"), data.get("username"))
    return str(data.get("id"))


async def perfil() -> dict:
    """
    Retorna dados do perfil para exibir no cabeçalho da UI:
    username, foto, nome e contagem de seguidores (quando disponível).
    """
    campos = "id,username,name,profile_picture_url,followers_count"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{GRAPH_BASE_URL}/me",
            params={"fields": campos, "access_token": IG_ACCESS_TOKEN},
        )
    resp.raise_for_status()
    return resp.json()


async def listar_publicacoes(limite: int = 25) -> list[dict]:
    """
    Lista as publicações da conta (para a UI escolher).
    Retorna id, legenda, tipo de mídia, url da mídia/thumbnail e permalink.
    """
    campos = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{GRAPH_BASE_URL}/me/media",
            params={"fields": campos, "limit": str(limite), "access_token": IG_ACCESS_TOKEN},
        )
    resp.raise_for_status()
    return resp.json().get("data", [])


async def enviar_dm(recipient_id: str, text: str) -> bool:
    """
    Envia uma DM privada via POST /me/messages.
    Retorna True se enviou (HTTP 200), False caso contrário.
    Nunca levanta exceção — o webhook precisa responder 200 rápido.
    """
    url = f"{GRAPH_BASE_URL}/me/messages"
    body = {"recipient": {"id": recipient_id}, "message": {"text": text}}
    params = {"access_token": IG_ACCESS_TOKEN}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, params=params, json=body)
    except Exception as exc:  # rede, timeout etc.
        logger.error("Erro de rede ao enviar DM para %s: %s", recipient_id, exc)
        return False

    if resp.status_code == 200:
        logger.info("DM enviada com sucesso para user_id=%s", recipient_id)
        return True

    logger.error(
        "Falha ao enviar DM para user_id=%s — status=%s body=%s",
        recipient_id, resp.status_code, resp.text,
    )
    return False
