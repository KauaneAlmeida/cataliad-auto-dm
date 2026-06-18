# -*- coding: utf-8 -*-
"""
Teste local ponta a ponta SEM chamar APIs externas (Instagram, Supabase, Claude).
Faz mock das funções de I/O e exercita o fluxo do webhook + casamento de regra +
cooldown + escolha fixa/ia.
"""
import hashlib
import hmac
import json
import os

os.environ["WEBHOOK_VERIFY_TOKEN"] = "token_de_teste"
os.environ["APP_SECRET"] = "segredo_de_teste"
os.environ["IG_USER_ID"] = "17841400000000000"
os.environ["IG_ACCESS_TOKEN"] = "fake"

import main
import instagram
import claude_dm
import supabase_client as db
from fastapi.testclient import TestClient

main.MY_APP_SCOPED_ID = "17841400000000000"  # id da "nossa" conta

# --- Mocks ------------------------------------------------------------------
enviadas = []          # DMs que SERIAM enviadas
registros = []         # entradas no dm_log
_cooldown = set()      # commenter_ids em cooldown


async def fake_enviar_dm(recipient_id, text):
    enviadas.append((recipient_id, text))
    return True


async def fake_gerar_dm(instrucao_base, comment_text, username):
    # Simula a personalização do Claude sem chamar a API.
    return f"[IA p/ @{username}] {instrucao_base} (resp a: {comment_text})"


# Regras "no banco": post ABC tem keyword 'preço' (fixa) e 'curso' (ia).
REGRAS = {
    "ABC": [
        {"id": 1, "media_id": "ABC", "keyword": "preço", "reply_text": "R$ 197!", "tipo": "fixa"},
        {"id": 2, "media_id": "ABC", "keyword": "curso", "reply_text": "Oferte o curso.", "tipo": "ia"},
    ]
}


async def fake_regras_da_publicacao(media_id):
    return REGRAS.get(media_id, [])


async def fake_em_cooldown(commenter_id):
    return commenter_id in _cooldown


async def fake_registrar_dm(commenter_id, media_id, rule_id, comment_text, reply_sent, via_ia):
    registros.append((commenter_id, rule_id, via_ia))
    _cooldown.add(commenter_id)  # simula o cooldown persistente


instagram.enviar_dm = fake_enviar_dm
claude_dm.gerar_dm = fake_gerar_dm
db.regras_da_publicacao = fake_regras_da_publicacao
db.em_cooldown = fake_em_cooldown
db.registrar_dm = fake_registrar_dm
# main importou os nomes via "import ... as", então aponta para os mocks via módulos.
main.instagram = instagram
main.claude_dm = claude_dm
main.db = db

client = TestClient(main.app)


def assinar(corpo: bytes) -> str:
    mac = hmac.new(b"segredo_de_teste", corpo, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def post_comentario(text, commenter_id, media_id="ABC", username="fulano", parent_id=None):
    value = {
        "text": text,
        "from": {"id": commenter_id, "username": username},
        "media": {"id": media_id},
    }
    if parent_id:
        value["parent_id"] = parent_id
    payload = {"object": "instagram", "entry": [{"changes": [{"field": "comments", "value": value}]}]}
    corpo = json.dumps(payload).encode("utf-8")
    return client.post("/webhook", content=corpo, headers={"X-Hub-Signature-256": assinar(corpo)})


def ok(cond, msg):
    print(("  OK   " if cond else "  FALHOU ") + msg)
    assert cond, msg


print("\n=== 1) GET verificacao ===")
r = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "token_de_teste", "hub.challenge": "123"})
ok(r.status_code == 200 and r.text == "123", f"challenge (status={r.status_code})")

print("\n=== 2) Assinatura invalida -> 403 ===")
r = client.post("/webhook", content=b'{}', headers={"X-Hub-Signature-256": "sha256=deadbeef"})
ok(r.status_code == 403, f"403 (status={r.status_code})")

print("\n=== 3) Keyword fixa 'preço' -> DM literal ===")
enviadas.clear(); registros.clear(); _cooldown.clear()
r = post_comentario("Qual o PREÇO?", "user1")
ok(len(enviadas) == 1 and enviadas[0][1] == "R$ 197!", f"DM fixa (enviadas={enviadas})")
ok(registros and registros[0][2] is False, f"registrado via_ia=False (registros={registros})")

print("\n=== 4) Keyword ia 'curso' -> DM personalizada pelo Claude (mock) ===")
enviadas.clear(); registros.clear(); _cooldown.clear()
r = post_comentario("quero o curso", "user2")
ok(len(enviadas) == 1 and enviadas[0][1].startswith("[IA p/ @fulano]"), f"DM ia (enviadas={enviadas})")
ok(registros and registros[0][2] is True, f"registrado via_ia=True (registros={registros})")

print("\n=== 5) Cooldown: 2o comentario do mesmo user -> pulado ===")
enviadas.clear()
r = post_comentario("e o preço?", "user2")  # user2 já está em cooldown do teste 4
ok(len(enviadas) == 0, f"nenhuma DM (cooldown) (enviadas={enviadas})")

print("\n=== 6) Sem keyword -> nada ===")
enviadas.clear(); _cooldown.clear()
r = post_comentario("post lindo!", "user3")
ok(len(enviadas) == 0, f"nenhuma DM (keyword miss) (enviadas={enviadas})")

print("\n=== 7) Reply (parent_id) -> ignorado ===")
enviadas.clear(); _cooldown.clear()
r = post_comentario("preço", "user4", parent_id="xyz")
ok(len(enviadas) == 0, f"nenhuma DM (reply) (enviadas={enviadas})")

print("\n=== 8) Propria conta -> ignorado ===")
enviadas.clear(); _cooldown.clear()
r = post_comentario("preço", "17841400000000000")
ok(len(enviadas) == 0, f"nenhuma DM (propria conta) (enviadas={enviadas})")

print("\n=== 9) Publicacao sem regra -> nada ===")
enviadas.clear(); _cooldown.clear()
r = post_comentario("preço", "user5", media_id="OUTRO")
ok(len(enviadas) == 0, f"nenhuma DM (sem regra) (enviadas={enviadas})")

print("\n=== TODOS OS TESTES PASSARAM ===")
