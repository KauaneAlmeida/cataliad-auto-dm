# -*- coding: utf-8 -*-
"""
Personalização da DM via Claude (Anthropic Messages API).

Usamos UMA chamada por DM, só quando a regra é do tipo 'ia'. O modelo recebe:
  - a instrução/base que você escreveu na regra (reply_text)
  - o texto do comentário
  - o username de quem comentou
e devolve uma DM curta, em pt-BR, pronta para enviar.

Modelo padrão: claude-opus-4-8 (configurável via ANTHROPIC_MODEL).
"""

from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

logger = logging.getLogger("instagram-webhook.claude")

# Cliente assíncrono. Lê a chave de ANTHROPIC_API_KEY (passamos explicitamente
# para deixar claro de onde vem). Reutilizável entre requisições.
_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic | None:
    global _client
    if not ANTHROPIC_API_KEY:
        return None
    if _client is None:
        _client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = (
    "Você escreve mensagens diretas (DM) curtas e simpáticas no Instagram, em "
    "português do Brasil, em nome do dono da conta, respondendo a quem comentou "
    "em um post. Use no máximo 2 frases. Soe humano e caloroso, sem parecer "
    "robô. Não use hashtags. Pode usar no máximo 1 emoji. Responda APENAS com o "
    "texto da DM, sem aspas, sem rótulos, sem explicações."
)


async def gerar_dm(instrucao_base: str, comment_text: str, username: str | None) -> str:
    """
    Gera o texto da DM personalizada. Se a API não estiver configurada ou falhar,
    retorna a instrução_base como fallback (assim a DM ainda sai, só não personalizada).
    """
    client = _get_client()
    if client is None:
        logger.warning("ANTHROPIC_API_KEY ausente — usando texto base sem personalizar.")
        return instrucao_base

    quem = f"@{username}" if username else "a pessoa"
    user_prompt = (
        f"Instrução/base da resposta: {instrucao_base}\n"
        f"Quem comentou: {quem}\n"
        f"Comentário recebido: \"{comment_text}\"\n\n"
        f"Escreva a DM personalizada seguindo a instrução acima."
    )

    try:
        resp = await client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # Pega o primeiro bloco de texto da resposta.
        texto = next((b.text for b in resp.content if b.type == "text"), "").strip()
        if texto:
            logger.info("DM personalizada gerada pelo Claude (%s).", ANTHROPIC_MODEL)
            return texto
        logger.warning("Claude retornou vazio — usando texto base.")
        return instrucao_base
    except Exception as exc:
        # Qualquer erro (rate limit, refusal, rede) -> fallback para o texto base.
        logger.error("Erro ao chamar Claude: %s — usando texto base.", exc)
        return instrucao_base
