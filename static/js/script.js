// ============================================================================
// Chat TEA — Script Principal (Fetch API Assíncrono + Formatação Acessível)
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
  inicializarTema();
  configurarMenuMobile();
  configurarFormulariosAuth();
  configurarChat();
});

// ----------------------------------------------------------------------------
// 1. Controle de Tema (Escuro / Claro)
// ----------------------------------------------------------------------------
function inicializarTema() {
  const temaSalvo = localStorage.getItem("chat_tea_tema") || "escuro";
  aplicarTema(temaSalvo);

  const btnTheme = document.getElementById("btn-theme");
  if (btnTheme) {
    btnTheme.addEventListener("click", () => {
      const novoTema = document.body.classList.contains("tema-claro")
        ? "escuro"
        : "claro";
      localStorage.setItem("chat_tea_tema", novoTema);
      aplicarTema(novoTema);
    });
  }
}

function aplicarTema(tema) {
  document.body.classList.remove("tema-escuro", "tema-claro");
  document.body.classList.add(`tema-${tema}`);

  const btnTheme = document.getElementById("btn-theme");
  if (btnTheme) {
    btnTheme.textContent =
      tema === "claro" ? "Alternar para Tema Escuro" : "Alternar para Tema Claro";
  }
}

// ----------------------------------------------------------------------------
// 2. Menu Lateral Responsivo
// ----------------------------------------------------------------------------
function configurarMenuMobile() {
  const btnMobile = document.getElementById("btn-mobile-menu");
  const sidebar = document.getElementById("sidebar");

  if (btnMobile && sidebar) {
    btnMobile.addEventListener("click", () => {
      sidebar.classList.toggle("aberta");
    });
  }
}

// ----------------------------------------------------------------------------
// 3. Autenticação Assíncrona via Fetch API (Login e Registro)
// ----------------------------------------------------------------------------
function configurarFormulariosAuth() {
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");

  const formAtivo = loginForm || registerForm;
  if (!formAtivo) return;

  formAtivo.addEventListener("submit", async (event) => {
    event.preventDefault();

    const alertBox = document.getElementById("auth-alert");
    const submitBtn = document.getElementById("btn-submit");
    const formData = new FormData(formAtivo);
    const payload = {
      username: (formData.get("username") || "").trim(),
      password: formData.get("password") || "",
    };

    if (alertBox) alertBox.hidden = true;
    if (submitBtn) submitBtn.disabled = true;

    try {
      const response = await fetch(formAtivo.action, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (response.ok && data.redirect) {
        window.location.href = data.redirect;
        return;
      }

      if (alertBox) {
        alertBox.textContent = data.error || "Não foi possível autenticar.";
        alertBox.hidden = false;
      }
    } catch (err) {
      if (alertBox) {
        alertBox.textContent = "Erro de conexão com o servidor.";
        alertBox.hidden = false;
      }
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

// ----------------------------------------------------------------------------
// 4. Chat em Tempo Real e Histórico via Fetch API
// ----------------------------------------------------------------------------
function configurarChat() {
  const chatForm = document.getElementById("chat-form");
  const messageInput = document.getElementById("message-input");
  const chatMessages = document.getElementById("chat-messages");
  const btnClearHistory = document.getElementById("btn-clear-history");

  if (!chatForm || !messageInput || !chatMessages) return;

  // Carrega histórico salvo no PostgreSQL
  carregarHistoricoInicial();

  // Botões de sugestão rápida na barra lateral
  document.querySelectorAll(".prompt-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const promptTexto = chip.getAttribute("data-prompt");
      if (promptTexto) {
        messageInput.value = promptTexto;
        messageInput.focus();
      }
    });
  });

  // Limpar histórico
  if (btnClearHistory) {
    btnClearHistory.addEventListener("click", async () => {
      if (!confirm("Deseja realmente apagar todo o seu histórico de mensagens?")) {
        return;
      }
      try {
        const res = await fetch("/api/history", { method: "DELETE" });
        if (res.ok) {
          chatMessages.innerHTML = `
            <div class="welcome-card">
              <h2>Histórico limpo.</h2>
              <p>Envie uma nova pergunta abaixo para iniciar outra sessão de estudo.</p>
            </div>
          `;
        }
      } catch (err) {
        console.error("Erro ao limpar histórico:", err);
      }
    });
  }

  // Envio de mensagem
  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const texto = messageInput.value.trim();
    if (!texto) return;

    const btnSend = document.getElementById("btn-send");
    messageInput.value = "";
    messageInput.disabled = true;
    if (btnSend) btnSend.disabled = true;

    adicionarBalao("user", texto, obterHoraAtual());
    const balaoBot = adicionarBalao(
      "bot",
      "Organizando explicação passo a passo...",
      obterHoraAtual()
    );

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: texto }),
      });

      const rawText = await response.text();
      let data = {};
      try {
        data = JSON.parse(rawText);
      } catch (_) {
        data = { error: `O servidor demorou para responder (HTTP ${response.status}). Tente enviar novamente.` };
      }

      const corpoBot = balaoBot.querySelector(".message-body");

      if (response.ok && data.response) {
        corpoBot.innerHTML = formatarTextoEstruturado(data.response);
      } else {
        corpoBot.textContent =
          data.error || "Não foi possível obter resposta no momento.";
      }
    } catch (error) {
      const corpoBot = balaoBot.querySelector(".message-body");
      corpoBot.textContent =
        "Erro de conexão com o servidor. Verifique sua internet e tente novamente.";
    } finally {
      messageInput.disabled = false;
      if (btnSend) btnSend.disabled = false;
      messageInput.focus();
      rolarParaFinal();
    }
  });
}

async function carregarHistoricoInicial() {
  const chatMessages = document.getElementById("chat-messages");
  if (!chatMessages) return;

  try {
    const response = await fetch("/api/history");
    if (!response.ok) return;

    const historico = await response.json();
    if (!Array.isArray(historico) || historico.length === 0) return;

    historico.forEach((item) => {
      adicionarBalao("user", item.user_message, item.created_at);
      adicionarBalao("bot", item.bot_response, item.created_at);
    });
    rolarParaFinal();
  } catch (err) {
    console.error("Erro ao carregar histórico:", err);
  }
}

function adicionarBalao(tipo, texto, horario) {
  const chatMessages = document.getElementById("chat-messages");
  const artigo = document.createElement("article");
  artigo.className = `message-bubble ${tipo}`;

  const autor = tipo === "user" ? "Você" : "Tutor TEA";
  const conteudoHtml =
    tipo === "bot" ? formatarTextoEstruturado(texto) : escaparHtml(texto);

  artigo.innerHTML = `
    <div class="message-meta">
      <span>${autor}</span>
      <span>${horario || ""}</span>
    </div>
    <div class="message-body">${conteudoHtml}</div>
  `;

  chatMessages.appendChild(artigo);
  rolarParaFinal();
  return artigo;
}

function rolarParaFinal() {
  const chatMessages = document.getElementById("chat-messages");
  if (chatMessages) {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

function obterHoraAtual() {
  return new Date().toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

// Converte Markdown simples (negrito e listas/passos) em HTML seguro e limpo
function formatarTextoEstruturado(texto) {
  const seguro = escaparHtml(texto || "");
  const comNegrito = seguro.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  const linhas = comNegrito.split(/\r?\n/);
  let html = "";
  let emLista = false;

  for (const linha of linhas) {
    const limpa = linha.trim();
    if (!limpa) {
      if (emLista) {
        html += "</ul>";
        emLista = false;
      }
      continue;
    }

    if (limpa.startsWith("- ") || limpa.startsWith("* ")) {
      if (!emLista) {
        html += "<ul>";
        emLista = true;
      }
      html += `<li>${limpa.slice(2)}</li>`;
    } else {
      if (emLista) {
        html += "</ul>";
        emLista = false;
      }
      html += `<p>${limpa}</p>`;
    }
  }

  if (emLista) {
    html += "</ul>";
  }

  return html || `<p>${comNegrito}</p>`;
}
