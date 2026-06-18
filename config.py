# -*- coding: utf-8 -*-
"""
Configuração central: carrega todas as variáveis de ambiente em um só lugar.
Importe daqui (`from config import ...`) em vez de chamar os.getenv espalhado.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Instagram / Meta -------------------------------------------------------
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
APP_SECRET = os.getenv("APP_SECRET", "")
IG_USER_ID = os.getenv("IG_USER_ID", "")
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")

# Fluxo "Instagram API with Instagram Login" -> host do Instagram Graph.
GRAPH_BASE_URL = f"https://graph.instagram.com/{GRAPH_VERSION}"

# --- Supabase (PostgREST) ---------------------------------------------------
# Ex.: https://abcdxyz.supabase.co  (SEM barra no final)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
# Chave service_role (server-side). NÃO exponha no frontend.
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_REST_URL = f"{SUPABASE_URL}/rest/v1" if SUPABASE_URL else ""

# --- Anthropic (Claude) -----------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Modelo padrão recomendado.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

# --- Cooldown ---------------------------------------------------------------
# Regra Meta 2026: no máximo 1 DM por usuário a cada 24h em gatilhos por comentário.
COOLDOWN_SECONDS = 24 * 60 * 60
