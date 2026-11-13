// ============================================================================
// Chat TEA — Script Principal (Histórico, Upload PDF/DOCX/XLSX/TXT e Relatórios)
// ============================================================================

let conversaIdAtual = null;

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
  const btnTogglePassword = document.getElementById("btn-toggle-password");
  const passwordInput = document.getElementById("password");

  // Botão Mostrar / Ocultar Senha para facilitar a digitação
  if (btnTogglePassword && passwordInput) {
    btnTogglePassword.addEventListener("click", () => {
      const estaOculta = passwordInput.type === "password";
      passwordInput.type = estaOculta ? "text" : "password";
      btnTogglePassword.textContent = estaOculta ? "Ocultar" : "Mostrar";
    });
  }

  // Validação dinâmica dos requisitos de senha no formulário de cadastro
  const reqTip = document.getElementById("password-req-tip");
  if (registerForm && passwordInput && reqTip) {
    passwordInput.addEventListener("input", () => {
      const val = passwordInput.value;
      if (!val) {
        reqTip.innerHTML =
          "Requisitos: mínimo de 8 caracteres, com letras (pelo menos uma maiúscula) e números (ex: <strong>Estudo2026</strong>).";
        reqTip.className = "password-helper-text";
        return;
      }

      const temTamanho = val.length >= 8;
      const temLetra = /[a-zA-Z]/.test(val);
      const temMaiuscula = /[A-Z]/.test(val);
      const temNumero = /[0-9]/.test(val);

      if (temTamanho && temLetra && temMaiuscula && temNumero) {
        reqTip.textContent = "Senha atende a todos os requisitos!";
        reqTip.className = "password-helper-text tip-ok";
      } else {
        const pendentes = [];
        if (!temTamanho) pendentes.push(`mínimo 8 caracteres (faltam ${8 - val.length})`);
        if (!temMaiuscula) pendentes.push("uma letra maiúscula");
        if (!temNumero) pendentes.push("um número");

        reqTip.textContent = `Atenção: adicione ${pendentes.join(", ")}.`;
        reqTip.className = "password-helper-text tip-warning";
      }
    });
  }

  const formAtivo = loginForm || registerForm;
  if (!formAtivo) return;

  formAtivo.addEventListener("submit", async (event) => {
    event.preventDefault();

    const alertBox = document.getElementById("auth-alert");
    const submitBtn = document.getElementById("btn-submit");
    const formData = new FormData(formAtivo);
    const payload = {
      username: (formData.get("username") || "").trim(),
      password: (formData.get("password") || "").trim(),
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
// 4. Chat, Upload de Arquivos, Histórico e Relatórios
// ----------------------------------------------------------------------------
function configurarChat() {
  const chatForm = document.getElementById("chat-form");
  const messageInput = document.getElementById("message-input");
  const fileInput = document.getElementById("file-input");
  const filePreviewBar = document.getElementById("file-preview-bar");
  const filePreviewName = document.getElementById("file-preview-name");
  const btnRemoveFile = document.getElementById("btn-remove-file");
  const chatMessages = document.getElementById("chat-messages");
  const btnNovaConversa = document.getElementById("btn-nova-conversa");
  const btnClearHistory = document.getElementById("btn-clear-history");
  const btnPlano = document.getElementById("btn-plano-estudos");
  const btnDicas = document.getElementById("btn-dicas-tempo");
  const btnRelatorio = document.getElementById("btn-relatorio-mensal");

  if (!chatForm || !messageInput || !chatMessages) return;

  // Carrega a lista de conversas na barra lateral
  carregarListaHistorico();

  // Sugestões de perguntas rápidas
  document.querySelectorAll(".prompt-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const promptTexto = chip.getAttribute("data-prompt");
      if (promptTexto) {
        messageInput.value = promptTexto;
        messageInput.focus();
      }
    });
  });

  // Seleção e remoção de arquivo anexado (.pdf, .docx, .xlsx, .txt)
  if (fileInput) {
    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files.length > 0) {
        filePreviewName.textContent = fileInput.files[0].name;
        filePreviewBar.hidden = false;
      } else {
        limparArquivoSelecionado();
      }
    });
  }

  if (btnRemoveFile) {
    btnRemoveFile.addEventListener("click", limparArquivoSelecionado);
  }

  function limparArquivoSelecionado() {
    if (fileInput) fileInput.value = "";
    if (filePreviewBar) filePreviewBar.hidden = true;
    if (filePreviewName) filePreviewName.textContent = "";
  }

  // Botão Nova Conversa
  if (btnNovaConversa) {
    btnNovaConversa.addEventListener("click", async () => {
      try {
        const res = await fetch("/nova-conversa", { method: "POST" });
        const data = await res.json();
        if (res.ok && data.conversa_id) {
          conversaIdAtual = data.conversa_id;
          chatMessages.innerHTML = `
            <div class="welcome-card">
              <h2>Nova conversa iniciada.</h2>
              <p>Digite sua dúvida abaixo ou anexe um arquivo (.pdf, .docx, .xlsx, .txt).</p>
            </div>
          `;
          carregarListaHistorico();
        }
      } catch (e) {
        console.error("Erro ao criar nova conversa:", e);
      }
    });
  }

  // Botão Apagar Histórico
  if (btnClearHistory) {
    btnClearHistory.addEventListener("click", async () => {
      if (!confirm("Deseja realmente apagar todo o seu histórico de conversas?")) {
        return;
      }
      try {
        const res = await fetch("/api/history", { method: "DELETE" });
        if (res.ok) {
          conversaIdAtual = null;
          chatMessages.innerHTML = `
            <div class="welcome-card">
              <h2>Histórico apagado.</h2>
              <p>Envie uma nova pergunta abaixo para iniciar outra sessão de estudo.</p>
            </div>
          `;
          carregarListaHistorico();
        }
      } catch (err) {
        console.error("Erro ao limpar histórico:", err);
      }
    });
  }

  // Botões de Plano de Estudos, Dicas e Relatório
  if (btnPlano) {
    btnPlano.addEventListener("click", () =>
      carregarRecursoPedagogico("/plano-estudos", "Gerando seu Plano de Estudos...")
    );
  }
  if (btnDicas) {
    btnDicas.addEventListener("click", () =>
      carregarRecursoPedagogico("/dicas-tempo", "Carregando Dicas de Estudos...")
    );
  }
  if (btnRelatorio) {
    btnRelatorio.addEventListener("click", () =>
      carregarRecursoPedagogico("/relatorio-mensal", "Calculando seu Relatório Mensal...")
    );
  }

  // Envio de mensagem ou arquivo
  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const texto = messageInput.value.trim();
    const arquivo = fileInput && fileInput.files ? fileInput.files[0] : null;

    if (!texto && !arquivo) return;

    const btnSend = document.getElementById("btn-send");
    messageInput.value = "";
    messageInput.disabled = true;
    if (btnSend) btnSend.disabled = true;

    const textoExibicaoUsuario = arquivo
      ? `[Arquivo anexado: ${arquivo.name}] ${texto}`.trim()
      : texto;

    adicionarBalao("user", textoExibicaoUsuario, obterHoraAtual());
    limparArquivoSelecionado();

    const balaoBot = adicionarBalao("bot", "Respondendo...", obterHoraAtual());

    try {
      let response;
      if (arquivo) {
        const formData = new FormData();
        formData.append("file", arquivo);
        if (texto) formData.append("message", texto);
        if (conversaIdAtual) formData.append("conversation_id", conversaIdAtual);

        response = await fetch("/upload", {
          method: "POST",
          body: formData,
        });
      } else {
        response = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: texto,
            conversation_id: conversaIdAtual,
          }),
        });
      }

      const rawText = await response.text();
      let data = {};
      try {
        data = JSON.parse(rawText);
      } catch (_) {
        data = {
          error: `O servidor demorou para responder (HTTP ${response.status}). Tente novamente.`,
        };
      }

      const corpoBot = balaoBot.querySelector(".message-body");

      if (response.ok && data.response) {
        corpoBot.innerHTML = formatarTextoEstruturado(data.response);
        if (data.conversation_id) {
          conversaIdAtual = data.conversation_id;
          carregarListaHistorico();
        }
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

async function carregarListaHistorico() {
  const lista = document.getElementById("lista-historico");
  if (!lista) return;

  try {
    const res = await fetch("/historico");
    if (!res.ok) return;

    const conversas = await res.json();
    if (!Array.isArray(conversas) || conversas.length === 0) {
      lista.innerHTML = `<li class="history-empty">Nenhuma conversa salva</li>`;
      return;
    }

    lista.innerHTML = "";
    conversas.forEach((conv) => {
      const li = document.createElement("li");
      li.className =
        conv.id === conversaIdAtual ? "history-item active" : "history-item";
      li.innerHTML = `
        <div class="history-item-title">${escaparHtml(conv.title || "Conversa")}</div>
        <div class="history-item-date">${escaparHtml(conv.created_at || "")}</div>
      `;
      li.addEventListener("click", () => abrirConversa(conv.id));
      lista.appendChild(li);
    });
  } catch (err) {
    console.error("Erro ao carregar lista de histórico:", err);
  }
}

async function abrirConversa(conversaId) {
  const chatMessages = document.getElementById("chat-messages");
  if (!chatMessages) return;

  try {
    const res = await fetch(`/mensagens/${conversaId}`);
    if (!res.ok) return;

    const mensagens = await res.json();
    conversaIdAtual = conversaId;
    chatMessages.innerHTML = "";

    if (mensagens.length === 0) {
      chatMessages.innerHTML = `
        <div class="welcome-card">
          <h2>Conversa vazia.</h2>
          <p>Envie uma pergunta abaixo para começar.</p>
        </div>
      `;
    } else {
      mensagens.forEach((m) => {
        adicionarBalao("user", m.user_message, m.created_at);
        adicionarBalao("bot", m.bot_response, m.created_at);
      });
    }

    carregarListaHistorico();
    rolarParaFinal();

    const sidebar = document.getElementById("sidebar");
    if (sidebar && sidebar.classList.contains("aberta")) {
      sidebar.classList.remove("aberta");
    }
  } catch (err) {
    console.error("Erro ao abrir conversa:", err);
  }
}

async function carregarRecursoPedagogico(url, mensagemCarregamento) {
  const balaoBot = adicionarBalao("bot", mensagemCarregamento, obterHoraAtual());
  const corpoBot = balaoBot.querySelector(".message-body");

  try {
    const res = await fetch(url);
    const data = await res.json();
    if (res.ok && data.response) {
      corpoBot.innerHTML = formatarTextoEstruturado(data.response);
    } else {
      corpoBot.textContent = data.error || "Erro ao carregar informação.";
    }
  } catch (err) {
    corpoBot.textContent = "Erro de conexão ao carregar recurso.";
  } finally {
    rolarParaFinal();
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
