import os
import re
from datetime import datetime, timezone
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

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "A variável de ambiente DATABASE_URL não foi definida. "
        "Configure uma URL de conexão PostgreSQL válida (Supabase ou Render)."
    )

# Compatibilidade com provedores em nuvem (Render / Supabase) e SQLAlchemy 2.1+
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
# Configuração da API Oficial do Google Gemini (SDK atual: google-genai)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-4-hydrogen")

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

SYSTEM_INSTRUCTION_TEA = """Você é um tutor e assistente de estudos projetado especificamente para estudantes com TEA (Transtorno do Espectro Autista). Responda sempre em português brasileiro.

Siga rigorosamente estas regras em todas as respostas:
1. COMUNICAÇÃO LITERAL E DIRETA:
   - Use linguagem clara, objetiva e 100% literal.
   - Nunca utilize metáforas, ironias, sarcasmo, expressões idiomáticas, gírias ou duplo sentido.
   - Evite emojis ou símbolos visuais excessivos que causem sobrecarga sensorial.

2. ESTRUTURAÇÃO PREVISÍVEL EM PASSOS E TÓPICOS:
   - Sempre inicie dizendo de forma curta o que será explicado.
   - Divida toda explicação em etapas numeradas (Passo 1, Passo 2, Passo 3) ou listas de tópicos curtos.
   - Nunca escreva parágrafos longos ou blocos densos de texto.
   - Destaque conceitos importantes em **negrito**.

3. TOM ACOLHEDOR, CALMO E PACIENTE:
   - Seja respeitoso, encorajador e sereno.
   - Apresente um exemplo concreto e prático sempre que explicar um conceito teórico.
   - Finalize com uma única pergunta clara e objetiva perguntando se o estudante deseja revisar algum passo ou avançar para um exercício prático."""


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

    messages = db.relationship(
        "ChatMessage",
        back_populates="user",
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
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user = db.relationship("User", back_populates="messages")


# Cria as tabelas automaticamente no PostgreSQL ao iniciar a aplicação
with app.app_context():
    db.create_all()


# ---------------------------------------------------------------------------
# Decorador e Utilitários de Autenticação
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
# Rotas de Autenticação e Páginas
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
    password = data.get("password") or ""

    if not username or not password:
        msg = "Por favor, preencha o nome de usuário e a senha."
        if request.is_json:
            return jsonify({"error": msg}), 400
        return render_template("login.html", error=msg), 400

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
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
    password = data.get("password") or ""

    if len(username) < 3 or len(username) > 40 or not re.match(r"^[a-zA-Z0-9_.\-]+$", username):
        msg = "O usuário deve ter entre 3 e 40 caracteres (apenas letras, números, ponto, traço ou sublinhado)."
        if request.is_json:
            return jsonify({"error": msg}), 400
        return render_template("register.html", error=msg), 400

    if len(password) < 8:
        msg = "A senha deve ter no mínimo 8 caracteres."
        if request.is_json:
            return jsonify({"error": msg}), 400
        return render_template("register.html", error=msg), 400

    if User.query.filter_by(username=username).first():
        msg = "Este nome de usuário já está cadastrado."
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
# Rotas da API de Chat e Histórico
# ---------------------------------------------------------------------------
@app.route("/api/history", methods=["GET"])
@login_required
def get_history():
    user_id = session["user_id"]
    mensagens = (
        ChatMessage.query.filter_by(user_id=user_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(50)
        .all()
    )
    return jsonify(
        [
            {
                "id": m.id,
                "user_message": m.user_message,
                "bot_response": m.bot_response,
                "created_at": m.created_at.strftime("%d/%m/%Y %H:%M"),
            }
            for m in mensagens
        ]
    )


@app.route("/api/history", methods=["DELETE"])
@login_required
def clear_history():
    user_id = session["user_id"]
    ChatMessage.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify({"message": "Histórico apagado com sucesso."})


@app.route("/chat", methods=["POST"])
@login_required
def chat():
    if not gemini_client:
        return (
            jsonify(
                {
                    "error": "A chave GEMINI_API_KEY não está configurada no servidor."
                }
            ),
            500,
        )

    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()

    if not user_message:
        return jsonify({"error": "Digite uma mensagem antes de enviar."}), 400

    user_id = session["user_id"]

    # Recupera as últimas 5 interações no PostgreSQL para manter o contexto de estudo
    ultimas_mensagens = (
        ChatMessage.query.filter_by(user_id=user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(5)
        .all()
    )
    ultimas_mensagens.reverse()

    blocos_contexto = []
    for item in ultimas_mensagens:
        blocos_contexto.append(f"Estudante: {item.user_message}")
        blocos_contexto.append(f"Tutor: {item.bot_response}")

    if blocos_contexto:
        contexto_formatado = "\n".join(blocos_contexto)
        prompt_completo = (
            f"Histórico recente da sessão de estudo:\n{contexto_formatado}\n\n"
            f"Nova dúvida do estudante:\n{user_message}"
        )
    else:
        prompt_completo = user_message

    try:
        interaction = gemini_client.interactions.create(
            model=GEMINI_MODEL,
            input=prompt_completo,
            system_instruction=SYSTEM_INSTRUCTION_TEA,
        )
        bot_reply = (interaction.output_text or "").strip()
        if not bot_reply:
            bot_reply = (
                "Não consegui gerar uma explicação neste momento. "
                "Por favor, reformule sua pergunta em uma frase direta."
            )

        registro = ChatMessage(
            user_id=user_id,
            user_message=user_message,
            bot_response=bot_reply,
        )
        db.session.add(registro)
        db.session.commit()

        return jsonify(
            {
                "response": bot_reply,
                "message_id": registro.id,
                "timestamp": registro.created_at.strftime("%H:%M"),
            }
        )

    except Exception as exc:
        db.session.rollback()
        print(f"[ERRO GEMINI / POSTGRESQL]: {exc}")
        return (
            jsonify(
                {
                    "error": "Ocorreu um erro ao comunicar com o assistente de IA. Tente novamente em instantes."
                }
            ),
            500,
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
