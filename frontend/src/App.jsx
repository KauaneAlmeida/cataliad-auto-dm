import { useEffect, useState } from "react";

// Base da API. Em dev o proxy do Vite manda /api -> :8000.
const API = "";

// Detecta URLs no texto e devolve pedaços (texto puro + links).
// Usado no preview da DM para mostrar links em azul, como o Instagram faz.
function partesComLinks(texto) {
  const regex = /(https?:\/\/[^\s]+)/g;
  const partes = [];
  let ultimo = 0;
  let m;
  while ((m = regex.exec(texto)) !== null) {
    if (m.index > ultimo) partes.push({ t: "txt", v: texto.slice(ultimo, m.index) });
    partes.push({ t: "link", v: m[0] });
    ultimo = m.index + m[0].length;
  }
  if (ultimo < texto.length) partes.push({ t: "txt", v: texto.slice(ultimo) });
  return partes;
}

export default function App() {
  const [posts, setPosts] = useState([]);
  const [rules, setRules] = useState([]);
  const [profile, setProfile] = useState(null);
  const [postsErro, setPostsErro] = useState("");
  const [carregando, setCarregando] = useState(true);

  // Publicação selecionada + campos do formulário.
  const [selecionado, setSelecionado] = useState(null);
  const [keyword, setKeyword] = useState("");
  const [reply, setReply] = useState("");
  const [tipo, setTipo] = useState("fixa"); // 'fixa' | 'ia'
  const [salvando, setSalvando] = useState(false);

  // Modo demo (para o vídeo da App Review): simula um comentário e mostra a DM.
  const [demoComment, setDemoComment] = useState("");
  const [demoResult, setDemoResult] = useState(null);
  const [simulando, setSimulando] = useState(false);

  async function simular(e) {
    e.preventDefault();
    if (!selecionado || !demoComment.trim()) return;
    setSimulando(true);
    setDemoResult(null);
    try {
      const res = await fetch(`${API}/api/simular`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          media_id: selecionado.id,
          comment_text: demoComment.trim(),
        }),
      }).then((r) => r.json());
      setDemoResult(res);
    } finally {
      setSimulando(false);
    }
  }

  async function carregarTudo() {
    setCarregando(true);
    try {
      const [rp, rr, rm] = await Promise.all([
        fetch(`${API}/api/posts`).then((r) => r.json()),
        fetch(`${API}/api/rules`).then((r) => r.json()),
        fetch(`${API}/api/me`).then((r) => r.json()),
      ]);
      if (rp.error) setPostsErro(rp.error);
      else setPosts(rp.posts || []);
      setRules(rr.rules || []);
      if (rm.profile) setProfile(rm.profile);
    } catch (e) {
      setPostsErro(String(e));
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregarTudo();
  }, []);

  async function criarRegra(e) {
    e.preventDefault();
    if (!selecionado || !keyword.trim() || !reply.trim()) return;
    setSalvando(true);
    try {
      const body = {
        media_id: selecionado.id,
        media_url: selecionado.thumbnail_url || selecionado.media_url || null,
        keyword: keyword.trim(),
        reply_text: reply.trim(),
        tipo,
      };
      const res = await fetch(`${API}/api/rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }).then((r) => r.json());
      if (res.rule) {
        setRules((prev) => [res.rule, ...prev]);
        setKeyword("");
        setReply("");
      }
    } finally {
      setSalvando(false);
    }
  }

  async function removerRegra(id) {
    await fetch(`${API}/api/rules/${id}`, { method: "DELETE" });
    setRules((prev) => prev.filter((r) => r.id !== id));
  }

  function thumb(p) {
    return p.thumbnail_url || p.media_url || "";
  }

  const regrasPorPost = rules.reduce((acc, r) => {
    acc[r.media_id] = (acc[r.media_id] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">🤖</span>
          <div>
            <h1>Automação de DM</h1>
            <p className="sub">
              Escolha uma publicação à direita, defina a palavra-chave e a
              mensagem da DM aqui ao lado.
            </p>
          </div>
        </div>

        {/* Perfil do Instagram no topo direito */}
        {profile && (
          <div className="perfil">
            {profile.profile_picture_url && (
              <img src={profile.profile_picture_url} alt="" />
            )}
            <div className="perfil-info">
              <strong>@{profile.username}</strong>
              {typeof profile.followers_count === "number" && (
                <span>{profile.followers_count.toLocaleString("pt-BR")} seguidores</span>
              )}
            </div>
          </div>
        )}
      </header>

      <div className="layout">
        {/* ESQUERDA: painel de trabalho (formulário + regras), sticky */}
        <aside className="painel">
          <section className="bloco">
            <h2>Defina a resposta</h2>

            {!selecionado && (
              <div className="placeholder">
                <span className="ph-icon">👉</span>
                Selecione uma publicação à direita para começar.
              </div>
            )}

            {selecionado && (
              <form onSubmit={criarRegra} className="form">
                <div className="selinfo">
                  {thumb(selecionado) && <img src={thumb(selecionado)} alt="" />}
                  <div>
                    <strong>Publicação selecionada</strong>
                    <span className="cap">
                      {(selecionado.caption || "").slice(0, 48) || "—"}
                    </span>
                  </div>
                </div>

                <label>
                  Palavra-chave
                  <span className="hint">o que o seguidor vai comentar</span>
                  <input
                    value={keyword}
                    onChange={(e) => setKeyword(e.target.value)}
                    placeholder="ex.: preço"
                  />
                </label>

                <div className="tipo">
                  <label className={tipo === "fixa" ? "on" : ""}>
                    <input
                      type="radio"
                      name="tipo"
                      checked={tipo === "fixa"}
                      onChange={() => setTipo("fixa")}
                    />
                    Resposta fixa
                  </label>
                  <label className={tipo === "ia" ? "on" : ""}>
                    <input
                      type="radio"
                      name="tipo"
                      checked={tipo === "ia"}
                      onChange={() => setTipo("ia")}
                    />
                    Personalizar com IA ✨
                  </label>
                </div>

                <label>
                  {tipo === "fixa" ? "Texto da DM" : "Instrução para a IA"}
                  <span className="hint">
                    {tipo === "fixa"
                      ? "enviado exatamente assim"
                      : "o Claude personaliza a partir disso"}
                  </span>
                  <textarea
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    rows={4}
                    placeholder={
                      tipo === "fixa"
                        ? "Oi! Aqui está o link: https://cataliad.dev"
                        : "Agradeça o interesse e mande o link https://cataliad.dev de forma simpática."
                    }
                  />
                </label>

                {/* Preview de como a DM aparece pro seguidor (links em azul) */}
                {reply.trim() && (
                  <div className="preview">
                    <span className="preview-label">
                      Prévia da DM {tipo === "ia" && "(base — a IA personaliza)"}
                    </span>
                    <div className="bubble">
                      {partesComLinks(reply).map((p, i) =>
                        p.t === "link" ? (
                          <a
                            key={i}
                            href={p.v}
                            target="_blank"
                            rel="noreferrer"
                            className="dm-link"
                          >
                            {p.v}
                          </a>
                        ) : (
                          <span key={i}>{p.v}</span>
                        )
                      )}
                    </div>
                  </div>
                )}

                <button type="submit" disabled={salvando}>
                  {salvando ? "Salvando…" : "Criar regra"}
                </button>
              </form>
            )}
          </section>

          <section className="bloco">
            <h2>
              Regras ativas <span className="contador">{rules.length}</span>
            </h2>
            {rules.length === 0 && <p className="dica">Nenhuma regra ainda.</p>}
            <ul className="rules">
              {rules.map((r) => (
                <li key={r.id}>
                  {r.media_url && <img src={r.media_url} alt="" />}
                  <div className="rinfo">
                    <div className="rtop">
                      <code>{r.keyword}</code>
                      <span className={"tag " + r.tipo}>
                        {r.tipo === "ia" ? "IA ✨" : "fixa"}
                      </span>
                    </div>
                    <p>{r.reply_text}</p>
                  </div>
                  <button className="del" onClick={() => removerRegra(r.id)}>
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          </section>

          {/* MODO DEMO — simula o fluxo comentário → DM (para teste e vídeo) */}
          <section className="bloco demo">
            <h2>🧪 Testar fluxo (demo)</h2>
            {!selecionado && (
              <p className="dica">Selecione uma publicação para simular.</p>
            )}
            {selecionado && (
              <form onSubmit={simular} className="form">
                <label>
                  Simular um comentário
                  <span className="hint">
                    roda a mesma lógica do webhook, sem enviar DM de verdade
                  </span>
                  <input
                    value={demoComment}
                    onChange={(e) => setDemoComment(e.target.value)}
                    placeholder="ex.: quanto é o preço?"
                  />
                </label>
                <button type="submit" disabled={simulando}>
                  {simulando ? "Processando…" : "▶ Simular comentário"}
                </button>
              </form>
            )}

            {demoResult && (
              <div className="demo-chat">
                {/* comentário que "entrou" */}
                <div className="chat-row left">
                  <div className="chat-bubble comment">
                    <span className="who">@seguidor</span>
                    {demoComment}
                  </div>
                </div>
                {/* resultado */}
                {demoResult.matched ? (
                  <>
                    <div className="chat-meta">
                      ✅ casou <code>{demoResult.keyword}</code>
                      <span className={"tag " + demoResult.tipo}>
                        {demoResult.tipo === "ia" ? "IA ✨" : "fixa"}
                      </span>
                      → DM:
                    </div>
                    <div className="chat-row right">
                      <div className="chat-bubble dm">{demoResult.dm}</div>
                    </div>
                  </>
                ) : (
                  <div className="chat-meta naomatch">
                    ✕ {demoResult.motivo} — nenhuma DM seria enviada.
                  </div>
                )}
              </div>
            )}
          </section>
        </aside>

        {/* DIREITA: grade de publicações */}
        <main className="conteudo">
          <div className="bloco">
            <h2>Escolha a publicação</h2>
            {carregando && <p className="dica">Carregando publicações…</p>}
            {postsErro && (
              <div className="erro">
                Não consegui carregar suas publicações: {postsErro}
                <br />
                <small>
                  Verifique o IG_ACCESS_TOKEN no .env e se o backend está rodando.
                </small>
              </div>
            )}
            <div className="grid">
              {posts.map((p) => (
                <button
                  key={p.id}
                  className={"card" + (selecionado?.id === p.id ? " sel" : "")}
                  onClick={() => setSelecionado(p)}
                  title={p.caption || ""}
                >
                  {thumb(p) ? (
                    <img src={thumb(p)} alt="" loading="lazy" />
                  ) : (
                    <div className="noimg">{p.media_type}</div>
                  )}
                  {regrasPorPost[p.id] > 0 && (
                    <span className="badge">{regrasPorPost[p.id]}</span>
                  )}
                  <span className="legenda">
                    {(p.caption || "").slice(0, 60)}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
