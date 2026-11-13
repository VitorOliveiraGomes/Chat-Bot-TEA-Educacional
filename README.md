<div align="center">

![Banner Chat TEA Educacional](static/imagens/banner-chat-tea.svg)

# Chat TEA — Assistente Educacional Acessível

**Plataforma web de tutoria inteligente desenvolvida para apoiar estudantes com TEA (Transtorno do Espectro Autista) por meio de respostas 100% literais, previsíveis e organizadas passo a passo.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-google--genai-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://aistudio.google.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase%20%2F%20Render-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/Licen%C3%A7a-MIT-10b981?style=for-the-badge)](LICENSE)

</div>

---

## Sobre o Projeto

O **Chat TEA** foi projetado com foco em **acessibilidade cognitiva** e **redução de sobrecarga sensorial**. Diferente de chatbots genéricos que produzem blocos extensos de texto ou usam figuras de linguagem ambíguas, este assistente utiliza uma *System Instruction* especializada na API oficial do **Google Gemini** para garantir:

- **Literalidade absoluta:** zero metáforas, ironias, duplo sentido ou gírias.
- **Previsibilidade estrutural:** explicações sempre divididas em passos numerados (`Passo 1`, `Passo 2`, `Passo 3`) e tópicos curtos.
- **Interface limpa e calma:** paleta de cores suaves (Temas Escuro e Claro), sem animações bruscas ou poluição visual.
- **Persistência em nuvem:** histórico individualizado por estudante armazenado em banco de dados **PostgreSQL** (compatível com **Supabase** e **Render**).

---

## Prévia da Interface

### Ambiente Principal de Estudos (Explicações Passo a Passo)
![Interface do Chat TEA](static/imagens/preview-chat-interface.svg)

### Autenticação e Alternância de Temas (Escuro / Claro)
![Telas de Login e Cadastro](static/imagens/preview-auth-themes.svg)

---

## Arquitetura do Sistema

```mermaid
flowchart LR
    U["Estudante (Navegador)"] -- "Fetch API (JSON)" --> F["Backend Flask (Serv.py)"]
    F -- "SQLAlchemy + psycopg2" --> PG[("PostgreSQL Cloud\n(Supabase / Render)")]
    F -- "Interactions API\n(System Instruction TEA)" --> G["Google Gemini API\n(gemini-4-hydrogen)"]
    G -- "Resposta Literal em Passos" --> F
    F -- "HTML Estruturado e Seguro" --> U
```

---

## Tecnologias Utilizadas

| Camada | Tecnologia | Finalidade |
| :--- | :--- | :--- |
| **Backend** | Python + Flask (`Serv.py`) | Servidor web, rotas REST, sessões seguras e controle de autenticação |
| **Inteligência Artificial** | `google-genai` (`gemini-4-hydrogen`) | Geração de explicações pedagógicas literais e passo a passo |
| **Banco de Dados** | PostgreSQL + Flask-SQLAlchemy | Armazenamento em nuvem de contas de usuários e histórico de conversas |
| **Frontend** | HTML5 Semântico, CSS3, JavaScript (Fetch API) | Interface acessível de baixa estimulação visual com atualização em tempo real |
| **Produção / Deploy** | Gunicorn + Render + Supabase | Servidor WSGI pronto para nuvem |

---

## Estrutura de Arquivos

```text
Chat-Bot-Educacional/
├── Serv.py                        # Aplicação principal Flask, Modelos SQLAlchemy e integração Gemini
├── models.py                      # Exportação dos modelos User e ChatMessage
├── requirements.txt               # Dependências enxutas de produção
├── Procfile                       # Comando de inicialização para o Render (Gunicorn)
├── .env.example                   # Modelo de variáveis de ambiente
├── templates/
│   ├── index.html                 # Interface principal do chat de estudos
│   ├── login.html                 # Página de login acessível
│   └── register.html              # Página de cadastro de estudantes
└── static/
    ├── css/style.css              # Folha de estilos com temas escuro/claro de baixo ruído visual
    ├── js/script.js               # Comunicação assíncrona via Fetch API
    └── imagens/                   # Logotipo e ilustrações da documentação
```

---

## Como Executar Localmente

### 1. Clone o repositório
```bash
git clone https://github.com/VitorOliveiraGomes/Chat-Bot-Educacional.git
cd Chat-Bot-Educacional
```

### 2. Crie e ative um ambiente virtual
**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente (`.env`)
Copie o arquivo `.env.example` para `.env` e preencha suas credenciais:
```env
GEMINI_API_KEY=sua_chave_do_google_ai_studio
DATABASE_URL=postgresql://usuario:senha@host:5432/nome_do_banco
SECRET_KEY=sua_chave_secreta_aleatoria
```

### 5. Inicie o servidor
```bash
python Serv.py
```
Acesse em seu navegador: `http://localhost:5000`

---

## Deploy em Nuvem (Render + Supabase)

1. Crie um banco PostgreSQL gratuito no [Supabase](https://supabase.com/) ou no próprio [Render](https://render.com/).
2. No painel do seu **Web Service** no Render:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn Serv:app`
3. Em **Environment Variables**, adicione:
   - `DATABASE_URL`: URI de conexão do PostgreSQL (`postgresql://...`)
   - `GEMINI_API_KEY`: Chave gerada no [Google AI Studio](https://aistudio.google.com/apikey)
   - `SECRET_KEY`: String aleatória segura para assinatura de sessão

> As tabelas `users` e `chat_messages` são criadas automaticamente na primeira inicialização da aplicação.

---

## Autores

- **Vitor Oliveira Gomes** — [GitHub](https://github.com/VitorOliveiraGomes) | [LinkedIn](https://www.linkedin.com/in/vitor-oliveira-gomes-610670317)
- **Kaian Perez** — [GitHub](https://github.com/kaiiiarchives) | [LinkedIn](https://www.linkedin.com/in/kaian-perez-7803792bb/)

---

## Licença

Distribuído sob a [Licença MIT](LICENSE).
