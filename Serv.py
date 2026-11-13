import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from google import genai

# Carrega variáveis de ambiente do arquivo .env (apenas em desenvolvimento local)
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")

# ---------------------------------------------------------------------------
# Configuração de Segurança e Banco de Dados PostgreSQL (Supabase / Render)
# ---------------------------------------------------------------------------
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "chave-secreta-producao-chat-tea-2026"
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # Limite de 10 MB para uploads

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "A variável de ambiente DATABASE_URL não foi definida. "
        "Configure uma URL de conexão PostgreSQL válida (Supabase ou Render)."
    )

try:
    import psycopg2  # noqa: F401
    pg_scheme = "postgresql+psycopg2://"
except ImportError:
    pg_scheme = "postgresql+psycopg://"

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", pg_scheme, 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", pg_scheme, 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# Configuração da API Oficial do Google Gemini (Respostas Rápidas)
# ---------------------------------------------------------------------------
# Usa gemini-3.5-flash-lite por padrão para respostas ultrarrápidas (~2-3s)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()


def obter_cliente_gemini():
    """Inicializa o cliente Gemini limpando eventuais espaços ou aspas na chave."""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


SYSTEM_INSTRUCTION_TEA = """Você é um tutor e assistente de estudos projetado especificamente para estudantes com TEA (Transtorno do Espectro Autista). Responda sempre em português brasileiro.

Siga rigorosamente estas regras:
1. MENSAGENS DE AGRADECIMENTO, SAUDAÇÃO OU DESPEDIDA:
   - Se o estudante estiver apenas agradecendo (ex: "obrigado", "me ajudou muito", "valeu"), cumprimentando ou se despedindo, responda em 1 ou 2 frases curtas, diretas e acolhedoras. NÃO use "Passo 1", "Passo 2" nem listas para agradecimentos ou cumprimentos.

2. EXPLICAÇÕES DE ESTUDO (LITERALIDADE E PASSO A PASSO):
   - Quando o estudante fizer uma pergunta de estudo ou enviar um arquivo, use linguagem 100% literal, direta e sem metáforas, ironias ou duplo sentido.
   - Evite emojis para não gerar sobrecarga visual.
   - Divida a explicação do conteúdo em etapas claras (**Passo 1**, **Passo 2**, **Passo 3**) ou tópicos curtos.
   - Nunca escreva parágrafos longos. Destaque conceitos importantes em **negrito** e inclua um exemplo prático.
   - Ao final de explicações de matéria, faça uma única pergunta simples perguntando se o estudante quer revisar algum ponto ou fazer um exercício."""


# ---------------------------------------------------------------------------
# Modelos de Banco de Dados (PostgreSQL)
# ---------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    conversations = db.relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )
    messages = db.relationship(
        "ChatMessage",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(150), nullable=False, default="Nova conversa")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User", back_populates="conversations")
    messages = db.relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    assunto = db.Column(db.String(100), nullable=True, default="Geral")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User", back_populates="messages")
    conversation = db.relationship("Conversation", back_populates="messages")


# Cria tabelas e aplica migração automática segura no PostgreSQL
with app.app_context():
    db.create_all()
    try:
        db.session.execute(
            db.text(
                "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE;"
            )
        )
        db.session.execute(
            db.text(
                "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS assunto VARCHAR(100) DEFAULT 'Geral';"
            )
        )
        db.session.commit()
    except Exception as mig_err:
        db.session.rollback()
        print(f"[AVISO MIGRAÇÃO]: {mig_err}")


# ---------------------------------------------------------------------------
# Utilitários Pedagógicos e Respostas Instantâneas
# ---------------------------------------------------------------------------
def detectar_resposta_social_instantanea(mensagem):
    """Retorna resposta imediata (sem raciocínio em passos) para agradecimentos, saudações e despedidas."""
    texto = re.sub(r"[^\w\sáéíóúâêôãõç]", "", mensagem.lower()).strip()
    palavras = texto.split()

    # Se a mensagem contém palavras de dúvida/pergunta técnica, deve ir para a IA
    gatilhos_pergunta = {
        "como", "qual", "quais", "explique", "explica", "ensine", "ensina",
        "porque", "por", "que", "calcula", "calcular", "exemplo", "ajudar",
        "ajude", "duvida", "dúvida", "fazer", "exercício", "exercicio",
    }

    agradecimentos = [
        "obrigado", "obrigada", "valeu", "vlw", "agradecido", "agradecida",
        "muito obrigado", "muito obrigada", "me ajudou muito", "ajudou bastante",
        "perfeito obrigado", "entendi obrigado", "entendi obrigada",
    ]
    if len(palavras) <= 10 and any(a in texto for a in agradecimentos):
        return (
            "De nada! Fico feliz em ter ajudado você nos seus estudos. "
            "Se precisar tirar outra dúvida ou praticar mais algum conteúdo, é só escrever aqui."
        )

    despedidas = ["tchau", "ate mais", "até mais", "ate logo", "até logo", "flw", "bye"]
    if len(palavras) <= 7 and any(d in texto for d in despedidas):
        return (
            "Até logo! Parabéns pela dedicação aos estudos hoje. "
            "Estarei por aqui sempre que quiser continuar."
        )

    saudacoes = {"oi", "ola", "olá", "bom dia", "boa tarde", "boa noite", "tudo bem"}
    if len(palavras) <= 4 and (texto in saudacoes or all(p in {"oi", "ola", "olá", "chat", "tutor", "tudo", "bem"} for p in palavras)):
        if not any(p in gatilhos_pergunta for p in palavras):
            return (
                "Olá! Estou pronto para ajudar você. "
                "Qual matéria ou assunto você gostaria de estudar agora?"
            )

    return None


def classificar_assunto(texto):
    """Classifica a matéria estudada para os relatórios e plano de estudos."""
    t = texto.lower()
    mapa = {
        "Programação e Tecnologia": ["python", "código", "programação", "algoritmo", "variável", "javascript", "html", "sql", "computador"],
        "Matemática": ["matemática", "equação", "fração", "número", "cálculo", "álgebra", "geometria", "soma", "multiplicação", "porcentagem"],
        "Português e Redação": ["português", "gramática", "redação", "verbo", "substantivo", "texto", "literatura", "ortografia"],
        "Ciências e Biologia": ["biologia", "ciências", "célula", "fotossíntese", "ecologia", "corpo humano", "genética", "dna"],
        "Física e Química": ["física", "química", "newton", "força", "energia", "átomo", "tabela periódica", "velocidade", "reação"],
        "História e Geografia": ["história", "geografia", "guerra", "revolução", "império", "clima", "relevo", "continente", "brasil"],
    }
    for materia, termos in mapa.items():
        if any(termo in t for termo in termos):
            return materia
    return "Estudos Gerais"


def chamar_gemini_rapido(prompt_completo):
    """Chama o Gemini priorizando velocidade máxima (gemini-3.5-flash-lite com thinking minimal)."""
    gemini_client = obter_cliente_gemini()
    if not gemini_client:
        return None, "A chave GEMINI_API_KEY não está configurada no servidor."

    modelos = [GEMINI_MODEL]
    for fallback in ("gemini-3.5-flash-lite", "gemini-4-hydrogen"):
        if fallback not in modelos:
            modelos.append(fallback)

    ultimo_erro = None
    for modelo in modelos:
        try:
            nivel = "minimal" if "flash-lite" in modelo else "low"
            interaction = gemini_client.interactions.create(
                model=modelo,
                input=prompt_completo,
                system_instruction=SYSTEM_INSTRUCTION_TEA,
                generation_config={"thinking_level": nivel},
            )
            texto = (interaction.output_text or "").strip()
            if texto:
                return texto, None
        except Exception as err:
            ultimo_erro = err
            print(f"[AVISO GEMINI - {modelo}]: {err}")
            continue

    print(f"[ERRO GEMINI FINAL]: {ultimo_erro}")
    return None, "Não foi possível obter resposta da IA no momento. Tente novamente em instantes."


# ---------------------------------------------------------------------------
# Decorador de Autenticação
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Sessão expirada. Faça login novamente."}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


# ---------------------------------------------------------------------------
# Rotas de Autenticação
# ---------------------------------------------------------------------------
@app.route("/")
@login_required
def index():
    return render_template("index.html", username=session.get("username", "Estudante"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if "user_id" in session:
            return redirect(url_for("index"))
        return render_template("login.html")

    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        msg = "Por favor, preencha o nome de usuário e a senha."
        if request.is_json:
            return jsonify({"error": msg}), 400
        return render_template("login.html", error=msg), 400

    user = User.query.filter(db.func.lower(User.username) == username.lower()).first()
    if not user:
        msg = (
            f"O usuário '{username}' ainda não possui cadastro. "
            "Clique em 'Criar conta' abaixo para se cadastrar."
        )
        if request.is_json:
            return jsonify({"error": msg, "user_not_found": True}), 404
        return render_template("login.html", error=msg), 404

    if not check_password_hash(user.password_hash, password):
        msg = "Nome de usuário ou senha incorretos."
        if request.is_json:
            return jsonify({"error": msg}), 401
        return render_template("login.html", error=msg), 401

    session.clear()
    session["user_id"] = user.id
    session["username"] = user.username

    if request.is_json:
        return jsonify({"message": "Login realizado com sucesso.", "redirect": url_for("index")})
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        if "user_id" in session:
            return redirect(url_for("index"))
        return render_template("register.html")

    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if len(username) < 3 or len(username) > 40 or not re.match(r"^[a-zA-Z0-9_.\-\s]+$", username):
        msg = "O usuário deve ter entre 3 e 40 caracteres (letras, números, espaços, ponto, traço ou sublinhado)."
        if request.is_json:
            return jsonify({"error": msg}), 400
        return render_template("register.html", error=msg), 400

    if len(password) < 8:
        msg = "A senha deve ter no mínimo 8 caracteres."
        if request.is_json:
            return jsonify({"error": msg}), 400
        return render_template("register.html", error=msg), 400

    tem_letra = any(c.isalpha() for c in password)
    tem_numero = any(c.isdigit() for c in password)
    tem_maiuscula = any(c.isupper() for c in password)

    if not (tem_letra and tem_numero and tem_maiuscula):
        msg = "A senha deve ter no mínimo 8 caracteres, contendo pelo menos uma letra maiúscula, letras minúsculas e números (exemplo: Estudo2026)."
        if request.is_json:
            return jsonify({"error": msg}), 400
        return render_template("register.html", error=msg), 400

    if User.query.filter(db.func.lower(User.username) == username.lower()).first():
        msg = "Este nome de usuário já está cadastrado. Vá para a tela de login para entrar."
        if request.is_json:
            return jsonify({"error": msg}), 409
        return render_template("register.html", error=msg), 409

    novo_usuario = User(
        username=username,
        password_hash=generate_password_hash(password, method="scrypt"),
    )
    db.session.add(novo_usuario)
    db.session.commit()

    session.clear()
    session["user_id"] = novo_usuario.id
    session["username"] = novo_usuario.username

    if request.is_json:
        return jsonify({"message": "Conta criada com sucesso.", "redirect": url_for("index")}), 201
    return redirect(url_for("index"))


@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Rotas de Conversas e Histórico
# ---------------------------------------------------------------------------
@app.route("/nova-conversa", methods=["POST"])
@login_required
def nova_conversa():
    conversa = Conversation(user_id=session["user_id"], title="Nova conversa")
    db.session.add(conversa)
    db.session.commit()
    return jsonify({"message": "Nova conversa criada", "conversa_id": conversa.id})


@app.route("/historico", methods=["GET"])
@login_required
def historico():
    conversas = (
        Conversation.query.filter_by(user_id=session["user_id"])
        .order_by(Conversation.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify(
        [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.strftime("%d/%m/%Y %H:%M"),
            }
            for c in conversas
        ]
    )


@app.route("/mensagens/<int:conversa_id>", methods=["GET"])
@login_required
def mensagens_conversa(conversa_id):
    conversa = db.session.get(Conversation, conversa_id)
    if not conversa or conversa.user_id != session["user_id"]:
        return jsonify({"error": "Conversa não encontrada"}), 404

    msgs = (
        ChatMessage.query.filter_by(conversation_id=conversa_id, user_id=session["user_id"])
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return jsonify(
        [
            {
                "id": m.id,
                "user_message": m.user_message,
                "bot_response": m.bot_response,
                "created_at": m.created_at.strftime("%H:%M"),
            }
            for m in msgs
        ]
    )


@app.route("/api/history", methods=["DELETE"])
@login_required
def clear_history():
    user_id = session["user_id"]
    ChatMessage.query.filter_by(user_id=user_id).delete()
    Conversation.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify({"message": "Histórico apagado com sucesso."})


# ---------------------------------------------------------------------------
# Rota Principal do Chat
# ---------------------------------------------------------------------------
@app.route("/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    conversation_id = data.get("conversation_id")

    if not user_message:
        return jsonify({"error": "Digite uma mensagem antes de enviar."}), 400

    user_id = session["user_id"]

    # Obtém ou cria a conversa atual
    conversa = None
    if conversation_id:
        conversa = db.session.get(Conversation, int(conversation_id))
        if not conversa or conversa.user_id != user_id:
            conversa = None

    if not conversa:
        titulo = user_message[:45] + "..." if len(user_message) > 45 else user_message
        conversa = Conversation(user_id=user_id, title=titulo)
        db.session.add(conversa)
        db.session.commit()
    elif conversa.title == "Nova conversa":
        conversa.title = user_message[:45] + "..." if len(user_message) > 45 else user_message
        db.session.commit()

    # 1. Verifica se é agradecimento, saudação ou despedida (resposta instantânea sem passos)
    resposta_social = detectar_resposta_social_instantanea(user_message)
    if resposta_social:
        registro = ChatMessage(
            user_id=user_id,
            conversation_id=conversa.id,
            user_message=user_message,
            bot_response=resposta_social,
            assunto="Interação Social",
        )
        db.session.add(registro)
        db.session.commit()
        return jsonify(
            {
                "response": resposta_social,
                "conversation_id": conversa.id,
                "timestamp": registro.created_at.strftime("%H:%M"),
            }
        )

    # 2. Recupera as últimas 4 mensagens da conversa para manter o contexto
    ultimas_mensagens = (
        ChatMessage.query.filter_by(user_id=user_id, conversation_id=conversa.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(4)
        .all()
    )
    ultimas_mensagens.reverse()

    blocos_contexto = []
    for item in ultimas_mensagens:
        blocos_contexto.append(f"Estudante: {item.user_message[:300]}")
        blocos_contexto.append(f"Tutor: {item.bot_response[:300]}")

    if blocos_contexto:
        contexto_formatado = "\n".join(blocos_contexto)
        prompt_completo = (
            f"Histórico recente desta conversa:\n{contexto_formatado}\n\n"
            f"Mensagem atual do estudante:\n{user_message}"
        )
    else:
        prompt_completo = user_message

    bot_reply, erro = chamar_gemini_rapido(prompt_completo)
    if erro:
        return jsonify({"error": erro}), 500

    assunto = classificar_assunto(user_message)
    try:
        registro = ChatMessage(
            user_id=user_id,
            conversation_id=conversa.id,
            user_message=user_message,
            bot_response=bot_reply,
            assunto=assunto,
        )
        db.session.add(registro)
        db.session.commit()
        horario = registro.created_at.strftime("%H:%M")
    except Exception as exc:
        db.session.rollback()
        print(f"[ERRO POSTGRESQL]: {exc}")
        horario = datetime.now(timezone.utc).strftime("%H:%M")

    return jsonify(
        {
            "response": bot_reply,
            "conversation_id": conversa.id,
            "timestamp": horario,
        }
    )


# ---------------------------------------------------------------------------
# Rota de Leitura de Arquivos (TXT, PDF, DOCX e Excel XLSX)
# ---------------------------------------------------------------------------
def extrair_texto_arquivo(file_storage, ext):
    """Extrai o texto de arquivos TXT, PDF, DOCX e XLSX."""
    if ext == "txt":
        return file_storage.read().decode("utf-8", errors="ignore")[:4000]

    if ext == "pdf":
        import PyPDF2
        reader = PyPDF2.PdfReader(file_storage)
        paginas = [page.extract_text() or "" for page in reader.pages[:6]]
        return "\n".join(paginas)[:4000]

    if ext == "docx":
        import docx
        doc = docx.Document(file_storage)
        paragrafos = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragrafos)[:4000]

    if ext == "xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(file_storage, data_only=True)
        linhas_extraidas = []
        for sheet_name in wb.sheetnames[:3]:
            sheet = wb[sheet_name]
            linhas_extraidas.append(f"Planilha: {sheet_name}")
            for row in list(sheet.iter_rows(values_only=True))[:40]:
                valores = [str(cell) for cell in row if cell is not None and str(cell).strip() != ""]
                if valores:
                    linhas_extraidas.append(" | ".join(valores))
        return "\n".join(linhas_extraidas)[:4000]

    return ""


@app.route("/upload", methods=["POST"])
@login_required
def upload_arquivo():
    arquivo = request.files.get("file")
    instrucao_usuario = (request.form.get("message") or "").strip()
    conversation_id = request.form.get("conversation_id")

    if not arquivo or not arquivo.filename:
        return jsonify({"error": "Nenhum arquivo foi selecionado."}), 400

    nome_seguro = secure_filename(arquivo.filename)
    ext = nome_seguro.rsplit(".", 1)[-1].lower() if "." in nome_seguro else ""

    extensoes_aceitas = {"txt", "pdf", "docx", "xlsx"}
    if ext not in extensoes_aceitas:
        return (
            jsonify(
                {
                    "error": "Formato não suportado. Envie arquivos .txt, .pdf, .docx ou .xlsx."
                }
            ),
            400,
        )

    try:
        conteudo_extraido = extrair_texto_arquivo(arquivo, ext).strip()
        if not conteudo_extraido:
            return (
                jsonify(
                    {
                        "error": f"Não foi possível extrair texto legível do arquivo '{nome_seguro}'."
                    }
                ),
                400,
            )

        user_id = session["user_id"]
        conversa = None
        if conversation_id:
            conversa = db.session.get(Conversation, int(conversation_id))
            if not conversa or conversa.user_id != user_id:
                conversa = None

        if not conversa:
            conversa = Conversation(user_id=user_id, title=f"Arquivo: {nome_seguro[:35]}")
            db.session.add(conversa)
            db.session.commit()

        pedido = (
            instrucao_usuario
            if instrucao_usuario
            else "Faça um resumo claro e explique os pontos principais passo a passo."
        )
        prompt = (
            f"O estudante enviou o arquivo '{nome_seguro}'.\n"
            f"Pedido do estudante: {pedido}\n\n"
            f"Conteúdo extraído do arquivo:\n{conteudo_extraido}"
        )

        bot_reply, erro = chamar_gemini_rapido(prompt)
        if erro:
            return jsonify({"error": erro}), 500

        descricao_msg = (
            f"[Arquivo: {nome_seguro}] {instrucao_usuario}".strip()
        )
        registro = ChatMessage(
            user_id=user_id,
            conversation_id=conversa.id,
            user_message=descricao_msg,
            bot_response=bot_reply,
            assunto=classificar_assunto(conteudo_extraido),
        )
        db.session.add(registro)
        db.session.commit()

        return jsonify(
            {
                "response": bot_reply,
                "conversation_id": conversa.id,
                "timestamp": registro.created_at.strftime("%H:%M"),
            }
        )
    except Exception as exc:
        db.session.rollback()
        print(f"[ERRO UPLOAD]: {exc}")
        return jsonify({"error": "Erro ao processar o arquivo enviado."}), 500


# ---------------------------------------------------------------------------
# Rotas de Plano de Estudos, Dicas de Tempo e Relatório Mensal
# ---------------------------------------------------------------------------
@app.route("/plano-estudos", methods=["GET"])
@login_required
def plano_estudos():
    user_id = session["user_id"]
    limite = datetime.now(timezone.utc) - timedelta(days=30)
    msgs = ChatMessage.query.filter(
        ChatMessage.user_id == user_id,
        ChatMessage.created_at >= limite,
        ChatMessage.assunto != "Interação Social",
    ).all()

    total = len(msgs)
    contagem = Counter([m.assunto or "Estudos Gerais" for m in msgs]).most_common(4)

    if total == 0:
        texto = (
            "**Plano de Estudos Personalizado**\n\n"
            "Você ainda está iniciando sua jornada. Siga estes 3 passos para criar sua rotina:\n"
            "- **Passo 1 (Tempo Diário):** Separe 30 minutos por dia em um horário fixo e silencioso.\n"
            "- **Passo 2 (Escolha do Tema):** Escolha 1 matéria por dia para não gerar sobrecarga.\n"
            "- **Passo 3 (Prática):** Envie uma dúvida ou arquivo (.pdf, .docx, .xlsx, .txt) aqui no chat para estudarmos juntos."
        )
    else:
        principal, qtd = contagem[0]
        itens_materias = "\n".join(
            [f"- **{assunto}:** {freq} sessões registradas" for assunto, freq in contagem]
        )
        texto = (
            f"**Plano de Estudos Personalizado (Baseado em {total} estudos)**\n\n"
            f"Seu foco principal recente foi **{principal}** ({qtd} interações).\n\n"
            f"**Matérias que você mais estudou:**\n{itens_materias}\n\n"
            f"**Rotina Recomendada em 3 Passos:**\n"
            f"- **Passo 1 (Bloco de Foco):** Estude 25 minutos de **{principal}** e faça 5 minutos de pausa.\n"
            f"- **Passo 2 (Revisão Prática):** Resolva 2 exercícios curtos sobre o tema estudado.\n"
            f"- **Passo 3 (Previsibilidade):** Mantenha sempre o mesmo horário de início para facilitar sua rotina."
        )

    return jsonify({"response": texto})


@app.route("/dicas-tempo", methods=["GET"])
@login_required
def dicas_tempo():
    user_id = session["user_id"]
    msgs = ChatMessage.query.filter_by(user_id=user_id).all()
    horarios = Counter([m.created_at.hour for m in msgs if m.created_at])

    if horarios:
        hora_pico = max(horarios, key=horarios.get)
        foco_horario = f"Suas interações costumam ocorrer por volta das **{hora_pico:02d}h**. Aproveite esse horário em que você já está habituado para estudar os assuntos mais importantes."
    else:
        foco_horario = "Escolha um horário fixo do dia (manhã ou tarde) com menos ruídos no ambiente."

    texto = (
        "**Dicas de Organização e Ritmo de Estudos**\n\n"
        f"{foco_horario}\n\n"
        "- **Passo 1 (Prepare o Ambiente):** Antes de começar, deixe apenas o material da matéria atual sobre a mesa.\n"
        "- **Passo 2 (Divida em Blocos Curtos):** Estude por 25 minutos e descanse por 5 minutos longe da tela.\n"
        "- **Passo 3 (Uma Tarefa por Vez):** Evite estudar duas matérias diferentes no mesmo bloco de tempo.\n"
        "- **Passo 4 (Checklist Visual):** Anote os 3 tópicos que você vai estudar no dia e marque cada um ao concluir."
    )
    return jsonify({"response": texto})


@app.route("/relatorio-mensal", methods=["GET"])
@login_required
def relatorio_mensal():
    user_id = session["user_id"]
    limite = datetime.now(timezone.utc) - timedelta(days=30)
    msgs = ChatMessage.query.filter(
        ChatMessage.user_id == user_id,
        ChatMessage.created_at >= limite,
    ).all()

    total = len(msgs)
    msgs_estudo = [m for m in msgs if m.assunto != "Interação Social"]
    contagem = Counter([m.assunto or "Estudos Gerais" for m in msgs_estudo]).most_common(5)

    if total == 0:
        texto = (
            "**Relatório Mensal (Últimos 30 Dias)**\n\n"
            "- **Total de interações:** 0\n"
            "- Comece a enviar suas dúvidas ou arquivos de estudo para acompanhar suas estatísticas aqui."
        )
    else:
        media_diaria = round(total / 30, 1)
        linhas_assuntos = "\n".join(
            [
                f"- **{assunto}:** {freq} interações ({round((freq / max(len(msgs_estudo), 1)) * 100)}%)"
                for assunto, freq in contagem
            ]
        ) or "- **Estudos Gerais:** 100%"

        texto = (
            "**Relatório Mensal de Desempenho (Últimos 30 Dias)**\n\n"
            f"- **Total de mensagens no período:** {total}\n"
            f"- **Dúvidas de conteúdo e arquivos analisados:** {len(msgs_estudo)}\n"
            f"- **Média diária de atividade:** {media_diaria} interações/dia\n\n"
            f"**Distribuição por Área de Estudo:**\n{linhas_assuntos}\n\n"
            "**Avaliação de Progresso:**\n"
            "- Você está mantendo um histórico consistente. Continue fazendo perguntas diretas sempre que quiser revisar um tema."
        )

    return jsonify({"response": texto})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
