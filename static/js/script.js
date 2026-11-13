// script.js - Interface limpa, moderna e responsiva (sem emojis)

let conversaIdAtual = null;
let temaAtual = localStorage.getItem('tema') || 'escuro';

document.addEventListener("DOMContentLoaded", function() {
    inicializar();
    configurarEventListeners();
    aplicarTema();
    carregarHistorico();
});

function inicializar() {
    const botaoTema = document.getElementById('tema-btn');
    if (botaoTema) {
        botaoTema.addEventListener('click', alternarTema);
    }

    const mobileToggle = document.getElementById('mobile-toggle');
    const sidebar = document.getElementById('historico-sidebar');
    if (mobileToggle && sidebar) {
        mobileToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });

        // Fechar ao clicar fora em telas pequenas
        document.addEventListener('click', (e) => {
            if (!sidebar.contains(e.target) && !mobileToggle.contains(e.target) && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
            }
        });
    }
}

function configurarEventListeners() {
    const userInput = document.getElementById("user-input");
    if (userInput) {
        userInput.addEventListener("keydown", function(event) {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                enviarMensagem();
            }
        });
    }

    const botaoEnviar = document.getElementById('btn-enviar');
    if (botaoEnviar) {
        botaoEnviar.addEventListener('click', enviarMensagem);
    }
    
    const fileInput = document.getElementById("file-input");
    if (fileInput) {
        fileInput.addEventListener("change", mostrarNomeArquivo);
    }
    
    configurarBotoesFuncionalidades();
}

function preencherPrompt(texto) {
    const userInput = document.getElementById("user-input");
    if (userInput) {
        userInput.value = texto;
        userInput.focus();
    }
}

function novaConversa() {
    fetch("/nova-conversa", {
        method: "POST",
        headers: { "Content-Type": "application/json" }
    })
    .then(response => response.json())
    .then(data => {
        if (data.conversa_id) {
            conversaIdAtual = data.conversa_id;
            const chatBox = document.getElementById("chat-box");
            if (chatBox) {
                chatBox.innerHTML = `
                    <div class="mensagem-boas-vindas">
                        <div class="welcome-icon">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M22 10v6M2 10l10-5 10 5-10 5z"></path>
                                <path d="M6 12v5c3 3 9 3 12 0v-5"></path>
                            </svg>
                        </div>
                        <h3>Nova conversa iniciada</h3>
                        <p>Como posso ajudar você nos seus estudos agora?</p>
                    </div>
                `;
            }
            carregarHistorico();
            mostrarNotificacao('Nova conversa pronta', 'success', 2000);
        }
    })
    .catch(error => {
        console.error('Erro ao criar nova conversa:', error);
        mostrarNotificacao('Erro ao criar conversa', 'error');
    });
}

async function carregarHistorico() {
    try {
        const response = await fetch("/historico");
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        
        const conversas = await response.json();
        const listaHistorico = document.getElementById("lista-historico");
        
        if (listaHistorico) {
            if (conversas.length === 0) {
                listaHistorico.innerHTML = '<li style="text-align: center; color: var(--text-muted); font-size: 0.85rem;">Nenhuma conversa anterior</li>';
                return;
            }
            listaHistorico.innerHTML = '';
            conversas.slice(0, 15).forEach(conv => {
                const li = document.createElement('li');
                if (conv.id === conversaIdAtual) li.classList.add('active');
                li.innerHTML = `
                    <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${conv.title || 'Conversa'}
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-muted);">${conv.created_at}</div>
                `;
                li.onclick = () => carregarConversa(conv.id);
                listaHistorico.appendChild(li);
            });
        }
    } catch (error) {
        console.error('Erro ao carregar histórico:', error);
    }
}

async function carregarConversa(conversaId) {
    try {
        const response = await fetch(`/mensagens/${conversaId}`);
        if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
        
        const mensagens = await response.json();
        const chatBox = document.getElementById("chat-box");
        if (chatBox) {
            chatBox.innerHTML = '';
            if (mensagens.length === 0) {
                chatBox.innerHTML = '<div class="mensagem-boas-vindas">Conversa vazia</div>';
                return;
            }
            mensagens.forEach(msg => {
                adicionarMensagemAoChat('usuario', msg.usuario, chatBox);
                adicionarMensagemAoChat('bot', msg.assistente, chatBox);
            });
            chatBox.scrollTop = chatBox.scrollHeight;
        }
        conversaIdAtual = conversaId;
        carregarHistorico();

        const sidebar = document.getElementById('historico-sidebar');
        if (sidebar && sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
        }
    } catch (error) {
        console.error('Erro ao carregar conversa:', error);
        mostrarNotificacao('Erro ao carregar conversa', 'error');
    }
}

function configurarBotoesFuncionalidades() {
    const botoes = [
        { id: 'btn-plano-estudos', funcao: carregarPlanoEstudos },
        { id: 'btn-relatorio-mensal', funcao: carregarRelatorioMensal },
        { id: 'btn-dicas-tempo', funcao: carregarDicasTempo },
        { id: 'btn-nova-conversa', funcao: novaConversa }
    ];
    
    botoes.forEach(botao => {
        const elemento = document.getElementById(botao.id);
        if (elemento) {
            elemento.addEventListener('click', botao.funcao);
        }
    });
}

async function enviarMensagem() {
    const input = document.getElementById("user-input");
    const fileInput = document.getElementById("file-input");
    const message = input.value.trim();
    const file = fileInput.files[0];
    const chatBox = document.getElementById("chat-box");

    if (!message && !file) return;

    desabilitarInterface(true);

    if (file) {
        adicionarMensagemAoChat('usuario', `Arquivo enviado: <strong>${file.name}</strong>`, chatBox);
    } else {
        adicionarMensagemAoChat('usuario', message, chatBox);
    }

    input.value = "";
    removerArquivo();

    const botDiv = adicionarMensagemAoChat('bot', '<div style="opacity: 0.7; font-size: 0.9rem;">Processando resposta...</div>', chatBox);

    try {
        let response;
        if (file) {
            const formData = new FormData();
            formData.append("file", file);
            if (conversaIdAtual) formData.append("conversation_id", conversaIdAtual);

            response = await fetch("/upload", { method: "POST", body: formData });
        } else {
            response = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: message, conversation_id: conversaIdAtual })
            });
        }

        const data = await response.json();

        if (response.ok) {
            botDiv.querySelector('.mensagem-conteudo').innerHTML = data.response;
            if (data.conversation_id) {
                conversaIdAtual = data.conversation_id;
                carregarHistorico();
            }
        } else {
            botDiv.querySelector('.mensagem-conteudo').innerHTML = `<span style="color:var(--accent-rose);">${data.error || 'Erro ao processar mensagem.'}</span>`;
        }
    } catch (error) {
        console.error('Erro na requisição:', error);
        botDiv.querySelector('.mensagem-conteudo').innerHTML = '<span style="color:var(--accent-rose);">Erro de conexão com o servidor.</span>';
    } finally {
        desabilitarInterface(false);
        chatBox.scrollTop = chatBox.scrollHeight;
        input.focus();
    }
}

function adicionarMensagemAoChat(remetente, conteudo, chatBox) {
    const div = document.createElement("div");
    div.className = `mensagem ${remetente}`;
    
    const agora = new Date();
    const horaAtual = agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    const nome = remetente === 'usuario' ? 'Você' : 'Assistente';

    div.innerHTML = `
        <div class="mensagem-header">
            <span>${nome}</span>
            <span>${horaAtual}</span>
        </div>
        <div class="mensagem-conteudo">${conteudo}</div>
    `;
    
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
    return div;
}

function alternarTema() {
    temaAtual = temaAtual === 'claro' ? 'escuro' : 'claro';
    localStorage.setItem('tema', temaAtual);
    aplicarTema();
}

function aplicarTema() {
    document.body.className = `tema-${temaAtual}`;
    const label = document.getElementById('tema-label');
    if (label) {
        label.textContent = temaAtual === 'claro' ? 'Tema Escuro' : 'Tema Claro';
    }
}

async function carregarPlanoEstudos() {
    const chatBox = document.getElementById("chat-box");
    const botDiv = adicionarMensagemAoChat('bot', '<em>Gerando plano personalizado...</em>', chatBox);
    try {
        const response = await fetch("/plano-estudos");
        const data = await response.json();
        botDiv.querySelector('.mensagem-conteudo').innerHTML = data.plano;
    } catch (e) {
        botDiv.querySelector('.mensagem-conteudo').innerHTML = 'Erro ao carregar o plano.';
    }
}

async function carregarRelatorioMensal() {
    const chatBox = document.getElementById("chat-box");
    const botDiv = adicionarMensagemAoChat('bot', '<em>Gerando relatório...</em>', chatBox);
    try {
        const response = await fetch("/relatorio-mensal");
        const data = await response.json();
        botDiv.querySelector('.mensagem-conteudo').innerHTML = data.relatorio;
    } catch (e) {
        botDiv.querySelector('.mensagem-conteudo').innerHTML = 'Erro ao carregar o relatório.';
    }
}

async function carregarDicasTempo() {
    const chatBox = document.getElementById("chat-box");
    const botDiv = adicionarMensagemAoChat('bot', '<em>Carregando dicas de estudo...</em>', chatBox);
    try {
        const response = await fetch("/dicas-tempo");
        const data = await response.json();
        botDiv.querySelector('.mensagem-conteudo').innerHTML = data.dicas;
    } catch (e) {
        botDiv.querySelector('.mensagem-conteudo').innerHTML = 'Erro ao carregar as dicas.';
    }
}

function mostrarNomeArquivo() {
    const fileInput = document.getElementById("file-input");
    const previewArea = document.getElementById("file-preview-area");
    const fileName = document.getElementById("file-name");

    if (fileInput.files.length > 0) {
        fileName.textContent = fileInput.files[0].name;
        previewArea.style.display = "flex";
    } else {
        removerArquivo();
    }
}

function removerArquivo() {
    const fileInput = document.getElementById("file-input");
    const previewArea = document.getElementById("file-preview-area");
    if (fileInput) fileInput.value = "";
    if (previewArea) previewArea.style.display = "none";
}

function desabilitarInterface(desabilitar) {
    const input = document.getElementById("user-input");
    const botaoEnviar = document.getElementById('btn-enviar');
    if (input) input.disabled = desabilitar;
    if (botaoEnviar) botaoEnviar.disabled = desabilitar;
}

function mostrarNotificacao(message, type = 'info', duration = 3000) {
    const existing = document.querySelector('.notification');
    if (existing) existing.remove();
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `<span>${message}</span><button onclick="this.parentElement.remove()" class="notification-close">&times;</button>`;
    document.body.appendChild(notification);
    setTimeout(() => { if (notification.parentElement) notification.remove(); }, duration);
}
