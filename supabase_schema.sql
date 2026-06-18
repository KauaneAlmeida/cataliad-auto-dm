-- ===========================================================================
-- Schema do Supabase para a automação de DM do Instagram.
-- Rode este SQL no editor SQL do Supabase (Dashboard > SQL Editor > New query).
-- ===========================================================================

-- Tabela de regras: cada regra liga uma PUBLICAÇÃO + PALAVRA-CHAVE a uma RESPOSTA.
-- tipo = 'fixa'  -> envia reply_text literalmente.
-- tipo = 'ia'    -> o Claude personaliza a DM usando reply_text como base/instrução.
create table if not exists public.rules (
    id          bigint generated always as identity primary key,
    media_id    text        not null,                 -- id da publicação no Instagram
    media_url   text,                                 -- thumbnail/permalink (cache p/ a UI)
    keyword     text        not null,                 -- palavra-chave (armazenada em minúsculas)
    reply_text  text        not null,                 -- texto fixo OU instrução base p/ a IA
    tipo        text        not null default 'fixa'   -- 'fixa' | 'ia'
                check (tipo in ('fixa', 'ia')),
    ativo       boolean     not null default true,    -- liga/desliga a regra sem apagar
    created_at  timestamptz not null default now()
);

-- Índice para a busca quente do webhook (por publicação, só regras ativas).
create index if not exists idx_rules_media_ativo on public.rules (media_id, ativo);

-- Log de DMs enviadas. Também serve como cooldown PERSISTENTE de 24h
-- (substitui o dict em memória que reseta a cada restart).
create table if not exists public.dm_log (
    id            bigint generated always as identity primary key,
    commenter_id  text        not null,               -- id (app-scoped) de quem comentou
    media_id      text,                               -- publicação onde comentou
    rule_id       bigint      references public.rules (id) on delete set null,
    comment_text  text,
    reply_sent    text,                               -- o que de fato foi enviado
    via_ia        boolean     not null default false,
    created_at    timestamptz not null default now()
);

-- Índice para a checagem de cooldown (último envio por usuário).
create index if not exists idx_dm_log_commenter_created on public.dm_log (commenter_id, created_at desc);
