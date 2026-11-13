from flask import Flask, request, jsonify, render_template, redirect
from google import genai
from google.genai import types
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import re, os
import PyPDF2
import bleach
from datetime import datetime, timedelta
from collections import Counter
from models import db, User, Message, Conversation
from markdown import markdown as md_to_html

# ---------------------------------------------------------------------------
# Configuração de ambiente
# ---------------------------------------------------------------------------
load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, "instance")
os.makedirs(instance_path, exist_ok=True)

# ---------------------------------------------------------------------------
# Inicialização do Flask
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", template_folder="templates", instance_path=instance_path)

# Database URL com fallback SQLite e compatibilidade Render/Supabase
database_url = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(instance_path, 'db.sqlite3')}")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "chave-secreta-padrao-desenvolvimento")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB

# ---------------------------------------------------------------------------
# Extensões
# ---------------------------------------------------------------------------
db.init_app(app)
CORS(app)

# Rate Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "60 per minute"],
    storage_uri="memory://",
)

# ---------------------------------------------------------------------------
# Headers de segurança
# ---------------------------------------------------------------------------
@app.after_request
def aplicar_headers_seguranca(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# ---------------------------------------------------------------------------
# Sanitização de Markdown
# ---------------------------------------------------------------------------
TAGS_PERMITIDAS = [
    "p", "h1", "h2", "h3", "h4", "strong", "em", "u", "ul", "ol", "li",
    "code", "pre", "blockquote", "hr", "table", "thead", "tbody", "tr",
    "th", "td", "span",
]
ATRIBUTOS_PERMITIDOS = {"*": ["class"], "code": ["class"]}


def renderizar_markdown_seguro(texto_markdown):
    """Converte markdown em HTML e sanitiza contra tags/scripts maliciosos."""
    html_puro = md_to_html(texto_markdown or "", extensions=["fenced_code", "tables"])
    return bleach.clean(
        html_puro, tags=TAGS_PERMITIDAS, attributes=ATRIBUTOS_PERMITIDOS, strip=True
    )

# ---------------------------------------------------------------------------
# Login Manager
# ---------------------------------------------------------------------------
login_manager = LoginManager()
login_manager.login_view = "login_page"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------------------------------------------------------------
# Gemini – cliente e instrução de sistema
# ---------------------------------------------------------------------------
gemini_key = os.getenv("GEMINI_API_KEY", "")
if gemini_key:
    gemini_key = gemini_key.strip()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")


def get_gemini_client():
    """Retorna o cliente Gemini se a chave de API estiver presente e válida."""
    if gemini_key and gemini_key != "insira_sua_api_aqui":
        return genai.Client(api_key=gemini_key.strip())
    return None


SYSTEM_INSTRUCTION_TEA = """\
Você é um assistente educacional acolhedor, calmo e previsível, desenvolvido \
especialmente para apoiar estudantes no espectro autista (TEA) e estudantes em \
geral com seus estudos e rotina de aprendizado. Responda sempre em português \
brasileiro.

DIRETRIZES FUNDAMENTAIS DE COMUNICAÇÃO:

1. LITERALIDADE E CLAREZA (Zero Ambiguidade):
   - Seja direto, literal, objetivo e factual em todas as respostas.
   - NUNCA use emojis, emoticons, metáforas complexas, figuras de linguagem \
abstratas, piadas, duplo sentido, sarcasmo ou gírias.
   - Jamais invente fatos ou alucine. Se você não tiver certeza de uma \
informação ou se faltarem dados para responder com precisão, declare \
claramente: "Não tenho informações suficientes para responder a essa parte \
com certeza."

2. ESTRUTURA VISUAL E PROGRESSIVA:
   - NUNCA escreva blocos gigantes ou densos de texto corrido.
   - NUNCA use emojis nem símbolos decorativos nos tópicos ou títulos. Use \
apenas numeração tradicional ou marcadores simples (-).
   - Organize a resposta com passos numerados sequenciais (Passo 1, Passo 2, \
Passo 3) e marcadores (bullet points).
   - Use formatação Markdown: negrito em **conceitos-chave** e títulos \
curtos para facilitar a leitura e diminuir a sobrecarga cognitiva.

3. PREVISIBILIDADE E ORGANIZAÇÃO MENTAL:
   - No início da explicação, antecipe brevemente o que será visto (ex: \
"Vamos ver este assunto em 3 etapas simples...").
   - Guie a transição entre as etapas com clareza (ex: "Agora que entendemos \
a definição, vamos ao próximo passo: o exemplo prático.").

4. TOM ACOLHEDOR E INCENTIVO CALMO:
   - Mantenha um tom encorajador, sereno, paciente e seguro, sem \
informalidade exagerada e sem emojis.
   - Valide o esforço do estudante sem excesso de pontos de exclamação ou \
estímulos sensoriais exagerados.

5. RESPOSTAS SUBSTANTIVAS:
   - Quando o estudante perguntar sobre um tema (exemplo: Leis de Newton, \
fotossíntese, equações de segundo grau), EXPLIQUE o tema de fato, com \
definição, exemplos práticos e estrutura clara. NÃO dê respostas genéricas \
como "posso te ajudar com isso".
   - Inclua exemplos concretos, números ou situações do cotidiano sempre que \
possível.

6. FECHAMENTO:
   - Ao final de cada resposta, faça uma pergunta de fechamento clara e \
opcional, como: "Quer que eu repita algum desses passos ou prefere fazer um \
exercício sobre isso?"
"""

# ---------------------------------------------------------------------------
# Geração de resposta via Gemini (com fallback em cadeia)
# ---------------------------------------------------------------------------

def gerar_resposta_ia_melhorada(pergunta, conversation_context=None):
    """Sistema de IA com Google Gemini API e fallback inteligente."""
    try:
        gemini_client = get_gemini_client()
        if gemini_client:
            primary_model = GEMINI_MODEL
            candidate_models = [primary_model]
            if "gemini-3.5-flash-lite" not in candidate_models:
                candidate_models.append("gemini-3.5-flash-lite")
            if "gemini-3.8-flash" not in candidate_models:
                candidate_models.append("gemini-3.8-flash")

            contexto_str = ""
            if conversation_context:
                contexto_str = "\n".join(
                    [
                        f"Estudante: {ctx['user']}\nAssistente: {ctx['bot']}"
                        for ctx in conversation_context[-5:]
                    ]
                )

            conteudo_prompt = ""
            if contexto_str:
                conteudo_prompt += f"Histórico recente da conversa:\n{contexto_str}\n\n"
            conteudo_prompt += f"Pergunta atual do estudante:\n{pergunta}"

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION_TEA,
                temperature=0.3,
                top_p=0.85,
                max_output_tokens=2000,
            )

            for model_name in candidate_models:
                try:
                    response = gemini_client.models.generate_content(
                        model=model_name,
                        contents=conteudo_prompt,
                        config=config,
                    )
                    if response.text:
                        return {
                            "resposta": response.text.strip(),
                            "tipo": "ia",
                            "cache_usado": False,
                        }
                except Exception as model_err:
                    print(f"Aviso ao usar modelo {model_name}: {model_err}")
                    continue
    except Exception as e:
        print(f"Erro na API do Gemini: {e}")

    # Fallback caso a API não esteja configurada ou ocorra erro
    return gerar_resposta_fallback_inteligente(pergunta, conversation_context)


def gerar_resposta_fallback_inteligente(pergunta, conversation_context=None):
    """Respostas de fallback quando a API Gemini não está disponível."""
    pergunta_lower = pergunta.lower().strip()

    if any(p in pergunta_lower for p in ["olá", "ola", "oi", "hello", "hi", "eae"]):
        return {
            "resposta": "Olá. Como posso ajudar você hoje? Posso auxiliar com estudos, responder perguntas ou conversar sobre diversos assuntos.",
            "tipo": "saudacao",
            "cache_usado": False,
        }

    if any(p in pergunta_lower for p in ["tudo bem", "como vai", "tudo bom", "como está"]):
        return {
            "resposta": "Estou bem, obrigado por perguntar. Estou aqui para ajudar com seus estudos e responder suas dúvidas. E com você, como está indo?",
            "tipo": "saudacao",
            "cache_usado": False,
        }

    if any(p in pergunta_lower for p in ["obrigado", "obrigada", "valeu", "vlw", "thanks"]):
        return {
            "resposta": "De nada. Fico feliz em ajudar. Se tiver mais dúvidas ou quiser conversar sobre algum assunto, estarei aqui.",
            "tipo": "agradecimento",
            "cache_usado": False,
        }

    if any(p in pergunta_lower for p in ["tchau", "bye", "até mais", "flw", "até logo"]):
        return {
            "resposta": "Até mais. Foi um prazer conversar com você. Volte sempre que precisar de ajuda nos estudos.",
            "tipo": "despedida",
            "cache_usado": False,
        }

    if any(p in pergunta_lower for p in ["estudar", "estudo", "matéria", "prova", "exame"]):
        return {
            "resposta": "Que bom que você está focado nos estudos. Posso ajudar com dúvidas sobre diversas matérias, técnicas de estudo ou criar um plano personalizado. Sobre qual assunto específico você gostaria de conversar?",
            "tipo": "estudo",
            "cache_usado": False,
        }

    materias = [
        "matemática", "português", "história", "geografia",
        "ciências", "física", "química", "biologia",
    ]
    for materia in materias:
        if materia in pergunta_lower:
            return {
                "resposta": f"{materia.capitalize()} é uma matéria muito interessante. Posso ajudar você com conceitos, exercícios, explicações ou dúvidas específicas. O que exatamente você gostaria de saber sobre {materia}?",
                "tipo": "materia",
                "cache_usado": False,
            }

    return {
        "resposta": "Interessante pergunta. Embora eu possa não ter todas as respostas, estou aqui para ajudar da melhor forma possível. Pode me dar mais detalhes sobre o que você gostaria de saber? Posso auxiliar com estudos, explicações ou simplesmente conversar.",
        "tipo": "chat",
        "cache_usado": False,
    }

# ---------------------------------------------------------------------------
# Utilitários de contexto e análise
# ---------------------------------------------------------------------------

def obter_contexto_conversa(conversation_id, user_id, limite=5):
    """Obtém as últimas mensagens da conversa para contexto."""
    if not conversation_id:
        return []
    try:
        mensagens = (
            Message.query.filter_by(conversation_id=conversation_id, user_id=user_id)
            .order_by(Message.timestamp.desc())
            .limit(limite)
            .all()
        )
        return [
            {"user": msg.user_message[:200], "bot": msg.bot_response[:200]}
            for msg in reversed(mensagens)
        ]
    except Exception as e:
        print(f"Erro ao obter contexto: {e}")
        return []


def calcular_assuntos_populares(mensagens):
    """Calcula os assuntos mais estudados."""
    assuntos = Counter([msg.assunto for msg in mensagens if msg.assunto])
    return assuntos.most_common(5)


def analisar_horarios_uso(mensagens):
    """Analisa os horários de maior atividade."""
    horarios = Counter([msg.timestamp.hour for msg in mensagens])
    return dict(horarios)


def calcular_progresso_semanal(mensagens):
    """Calcula progresso por semana (últimas 4)."""
    semanas = {}
    for msg in mensagens:
        semana = msg.timestamp.strftime("%Y-W%U")
        semanas[semana] = semanas.get(semana, 0) + 1
    return dict(sorted(semanas.items())[-4:])


def classificar_assunto(texto):
    """Classifica o assunto com base em palavras-chave da mensagem."""
    texto_lower = texto.lower()
    mapeamento = {
        "Matemática": ["matemática", "math", "equação", "número", "cálculo", "álgebra", "geometria"],
        "Português": ["português", "texto", "redação", "gramática", "literatura", "ortografia"],
        "História": ["história", "histórico", "guerra", "império", "revolução", "civilização"],
        "Geografia": ["geografia", "país", "capital", "continente", "clima", "relevo"],
        "Ciências": ["ciência", "física", "química", "biologia", "célula", "átomo", "energia"],
    }
    for assunto, palavras in mapeamento.items():
        if any(p in texto_lower for p in palavras):
            return assunto
    return "Geral"

# ---------------------------------------------------------------------------
# Geradores de HTML para plano / relatório / dicas
# ---------------------------------------------------------------------------

def gerar_plano_personalizado(assuntos_data, total_mensagens):
    """Gera plano de estudos personalizado em HTML."""
    if not assuntos_data:
        return """
        <div class="plano-estudos">
            <h3>Seu Plano de Estudos Personalizado</h3>
            <div class="plano-item">
                <h4>Primeiros Passos</h4>
                <p>Como você está começando, vamos criar uma base sólida:</p>
                <ul>
                    <li>Estabeleça uma rotina diária de estudos de 30-60 minutos</li>
                    <li>Escolha 2-3 matérias prioritárias para focar</li>
                    <li>Faça anotações e resumos dos principais conceitos</li>
                    <li>Use o chat para tirar dúvidas sempre que precisar</li>
                </ul>
            </div>
            <div class="dica-especial">
                <strong>Dica:</strong> Comece com sessões curtas e aumente gradualmente o tempo de estudo.
            </div>
        </div>
        """

    assunto_principal = assuntos_data[0][0]
    quantidade_principal = assuntos_data[0][1]

    html = f"""
    <div class="plano-estudos">
        <h3>Seu Plano de Estudos Personalizado</h3>
        <div class="estatisticas">
            <p><strong>Baseado em {total_mensagens} interações</strong></p>
            <p>Assunto mais estudado: <strong>{assunto_principal}</strong> ({quantidade_principal} sessões)</p>
        </div>

        <div class="plano-item">
            <h4>Rotina Semanal Recomendada</h4>
            <ul>
                <li><strong>Segunda a Sexta:</strong> 45min de {assunto_principal}</li>
                <li><strong>Sábado:</strong> Revisão geral e exercícios</li>
                <li><strong>Domingo:</strong> Descanso ou leitura leve</li>
            </ul>
        </div>

        <div class="plano-item">
            <h4>Foco por Matéria</h4>
            <ul>"""

    for assunto, freq in assuntos_data:
        if freq > 1:
            html += f"<li><strong>{assunto}:</strong> {freq} sessões - Continue praticando</li>"
        else:
            html += f"<li><strong>{assunto}:</strong> Matéria nova - Dedique mais tempo</li>"

    html += """
            </ul>
        </div>

        <div class="dica-especial">
            <strong>Dica Personalizada:</strong> Você está no caminho certo. Continue interagindo regularmente para eu ajustar seu plano de estudos.
        </div>
    </div>
    """
    return html


def gerar_relatorio_html(stats):
    """Gera relatório mensal em HTML."""
    total_mensagens = stats["total_mensagens"]
    assuntos_populares = stats["assuntos_mais_estudados"]
    progresso_semanal = stats["progresso_semanal"]

    if total_mensagens == 0:
        return """
        <div class="relatorio-mensal">
            <h3>Relatório Mensal - Últimos 30 Dias</h3>
            <div class="sem-dados">
                <p>Ainda não há dados suficientes para gerar seu relatório.</p>
                <p>Continue estudando e interagindo para ver suas estatísticas aqui.</p>
            </div>
        </div>
        """

    html = f"""
    <div class="relatorio-mensal">
        <h3>Relatório Mensal - Últimos 30 Dias</h3>

        <div class="resumo-geral">
            <div class="stat-card">
                <h4>Total de Interações</h4>
                <div class="stat-number">{total_mensagens}</div>
            </div>
            <div class="stat-card">
                <h4>Média Diária</h4>
                <div class="stat-number">{round(total_mensagens / 30, 1)}</div>
            </div>
        </div>

        <div class="assuntos-populares">
            <h4>Assuntos Mais Estudados</h4>
            <ol>"""

    for assunto, freq in assuntos_populares:
        porcentagem = round((freq / total_mensagens) * 100, 1) if total_mensagens > 0 else 0
        html += f"<li><strong>{assunto}:</strong> {freq} sessões ({porcentagem}%)</li>"

    html += """
            </ol>
        </div>

        <div class="progresso-semanal">
            <h4>Progresso Semanal</h4>
            <div class="semanas">"""

    for semana, atividade in progresso_semanal.items():
        html += f"<div class='semana-item'>Semana {semana.split('W')[1]}: {atividade} interações</div>"

    html += """
            </div>
        </div>

        <div class="motivacao">
            <h4>Avaliação</h4>"""

    if total_mensagens >= 20:
        html += "<p>Excelente. Você está muito ativo nos estudos. Continue assim.</p>"
    elif total_mensagens >= 10:
        html += "<p>Bom progresso. Tente aumentar um pouco a frequência de estudos.</p>"
    else:
        html += "<p>Que tal estudar um pouco mais? Estou aqui para ajudar sempre.</p>"

    html += """
        </div>
    </div>
    """
    return html


def gerar_dicas_personalizadas(horarios_uso, total_mensagens):
    """Gera dicas de organização de tempo personalizadas."""
    if not horarios_uso:
        return """
        <div class="dicas-tempo">
            <h3>Dicas de Organização de Tempo</h3>
            <div class="dica-item">
                <h4>Estabeleça uma Rotina</h4>
                <p>Comece criando um horário fixo para estudos. Pode ser de manhã, tarde ou noite - o importante é ser consistente.</p>
            </div>
            <div class="dica-item">
                <h4>Técnica Pomodoro</h4>
                <p>Estude por 25 minutos, depois faça uma pausa de 5 minutos. Repita 4 vezes e faça uma pausa maior de 30 minutos.</p>
            </div>
            <div class="dica-item">
                <h4>Defina Metas Pequenas</h4>
                <p>Ao invés de "estudar matemática", tente "resolver 10 exercícios de equações". Metas específicas são mais motivadoras.</p>
            </div>
        </div>
        """

    horario_favorito = max(horarios_uso, key=horarios_uso.get)
    periodo = "manhã" if horario_favorito < 12 else "tarde" if horario_favorito < 18 else "noite"

    html = f"""
    <div class="dicas-tempo">
        <h3>Dicas Personalizadas de Organização</h3>

        <div class="analise-pessoal">
            <h4>Sua Análise de Uso</h4>
            <p>Você é mais ativo durante a <strong>{periodo}</strong> (às {horario_favorito}h).</p>
            <p>Total de interações analisadas: <strong>{total_mensagens}</strong></p>
        </div>

        <div class="dica-item">
            <h4>Aproveite Seu Pico de Produtividade</h4>
            <p>Como você estuda mais às {horario_favorito}h, reserve esse horário para as matérias mais desafiadoras.</p>
        </div>

        <div class="dica-item">
            <h4>Distribua Suas Sessões</h4>"""

    if total_mensagens >= 20:
        html += "<p>Você está muito ativo. Que tal distribuir mais as sessões ao longo do dia para melhor fixação?</p>"
    elif total_mensagens >= 10:
        html += "<p>Bom ritmo. Tente adicionar uma sessão extra em outro período do dia.</p>"
    else:
        html += "<p>Aumente gradualmente suas sessões de estudo. Comece com 15-20 minutos por dia.</p>"

    html += """
        </div>

        <div class="dica-item">
            <h4>Planejamento Semanal</h4>
            <ul>
                <li>Segunda/Quarta/Sexta: Matérias principais</li>
                <li>Terça/Quinta: Revisão e exercícios</li>
                <li>Sábado: Estudos livres ou dúvidas pendentes</li>
                <li>Domingo: Descanso (importante para consolidação)</li>
            </ul>
        </div>

        <div class="motivacao-tempo">
            <strong>Lembre-se:</strong> Consistência é mais importante que quantidade. 30 minutos todo dia vale mais que 3 horas uma vez por semana.
        </div>
    </div>
    """
    return html

# ---------------------------------------------------------------------------
# Validação de senha
# ---------------------------------------------------------------------------
SENHAS_BLOQUEADAS = {
    "12345678", "123456789", "1234567890", "password", "senha123",
    "admin123", "abcdefgh", "qwerty123", "letmein01", "welcome1",
}


def validar_forca_senha(password):
    """Valida requisitos de segurança para senhas."""
    if len(password) < 8:
        return "A senha deve ter no mínimo 8 caracteres."
    if len(password) > 50:
        return "A senha deve ter no máximo 50 caracteres."
    if not re.search(r"[a-zA-Z]", password):
        return "A senha deve conter pelo menos uma letra."
    if not re.search(r"[0-9]", password):
        return "A senha deve conter pelo menos um número."
    if password.lower() in SENHAS_BLOQUEADAS:
        return "Essa senha é muito previsível. Escolha uma senha mais forte."
    return None

# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
@login_required
def chat():
    try:
        data = request.get_json()
        user_message = (data.get("message") or "").strip()
        conversation_id = data.get("conversation_id")

        if not user_message:
            return jsonify({"error": "Mensagem vazia"}), 400

        # Gerenciar conversa
        if conversation_id:
            conversation = db.session.get(Conversation, conversation_id)
            if not conversation or conversation.user_id != current_user.id:
                return jsonify({"error": "Conversa inválida"}), 403
        else:
            title = user_message[:50] + "..." if len(user_message) > 50 else user_message
            conversation = Conversation(user_id=current_user.id, title=title)
            db.session.add(conversation)
            db.session.commit()

        # Contexto das últimas 5 mensagens
        contexto = obter_contexto_conversa(conversation.id, current_user.id, limite=5)

        # Chamar IA
        llm_response = gerar_resposta_ia_melhorada(user_message, contexto)
        bot_message = llm_response["resposta"]

        # Markdown -> HTML sanitizado
        bot_message_html = renderizar_markdown_seguro(bot_message)

        # Classificação de assunto
        assunto = classificar_assunto(user_message)

        # Persistir mensagem
        mensagem = Message(
            user_id=current_user.id,
            conversation_id=conversation.id,
            user_message=user_message,
            bot_response=bot_message,
            assunto=assunto,
            subassunto=llm_response.get("tipo", "chat"),
            dificuldade=3,
        )
        db.session.add(mensagem)
        db.session.commit()

        return jsonify({"response": bot_message_html, "conversation_id": conversation.id})

    except Exception as e:
        print(f"Erro no /chat: {e}")
        return jsonify({"error": "Erro interno ao processar a mensagem."}), 500


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Arquivo não enviado"}), 400

    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    EXTENSOES_PERMITIDAS = {"txt", "pdf", "docx"}
    if ext not in EXTENSOES_PERMITIDAS:
        return jsonify({"error": "Formato de arquivo não suportado. Envie apenas TXT, PDF ou DOCX."}), 400

    # Validação de tamanho
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > 5 * 1024 * 1024:
        return jsonify({"error": "Arquivo muito grande (máximo 5MB)"}), 400

    try:
        content = ""
        if ext == "txt":
            content = file.read().decode("utf-8", errors="ignore")[:1000]
        elif ext == "pdf":
            reader = PyPDF2.PdfReader(file)
            content = "\n".join(page.extract_text() or "" for page in reader.pages[:3])[:1000]
        elif ext == "docx":
            import docx
            doc = docx.Document(file)
            content = "\n".join(p.text for p in doc.paragraphs[:10])[:1000]

        pergunta = f"Analise este conteúdo do arquivo '{filename}' e me dê um resumo útil:\n\n{content}"
        llm_response = gerar_resposta_ia_melhorada(pergunta)
        bot_message = llm_response["resposta"]
        bot_message_html = renderizar_markdown_seguro(bot_message)

        mensagem = Message(
            user_id=current_user.id,
            user_message=f"[Arquivo: {filename}]",
            bot_response=bot_message,
            assunto="Upload",
            subassunto="Análise",
            dificuldade=3,
        )
        db.session.add(mensagem)
        db.session.commit()

        return jsonify({"response": bot_message_html})

    except Exception as e:
        print(f"Erro no upload: {e}")
        return jsonify({"error": "Erro ao processar o arquivo"}), 500


@app.route("/plano-estudos", methods=["GET"])
@login_required
def plano_estudos():
    try:
        data_limite = datetime.now() - timedelta(days=30)
        mensagens = Message.query.filter(
            Message.user_id == current_user.id,
            Message.timestamp >= data_limite,
        ).all()

        assuntos_populares = calcular_assuntos_populares(mensagens)
        total_mensagens = len(mensagens)
        plano_html = gerar_plano_personalizado(assuntos_populares, total_mensagens)

        return jsonify({
            "plano": plano_html,
            "metadata": {
                "total_interacoes": total_mensagens,
                "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
            },
        })
    except Exception as e:
        print(f"Erro no plano de estudos: {e}")
        return jsonify({
            "plano": "<div class='error'>Erro ao gerar plano de estudos. Tente novamente.</div>",
            "metadata": {"total_interacoes": 0, "ultima_atualizacao": "Erro"},
        }), 500


@app.route("/relatorio-mensal", methods=["GET"])
@login_required
def relatorio_mensal():
    try:
        data_limite = datetime.now() - timedelta(days=30)
        mensagens = Message.query.filter(
            Message.user_id == current_user.id,
            Message.timestamp >= data_limite,
        ).all()

        stats = {
            "total_mensagens": len(mensagens),
            "assuntos_mais_estudados": calcular_assuntos_populares(mensagens),
            "progresso_semanal": calcular_progresso_semanal(mensagens),
        }

        relatorio_html = gerar_relatorio_html(stats)

        return jsonify({
            "relatorio": relatorio_html,
            "periodo": "Últimos 30 dias",
            "total_interacoes": len(mensagens),
        })
    except Exception as e:
        print(f"Erro no relatório mensal: {e}")
        return jsonify({
            "relatorio": "<div class='error'>Erro ao gerar relatório mensal. Tente novamente.</div>",
            "periodo": "Últimos 30 dias",
            "total_interacoes": 0,
        }), 500


@app.route("/dicas-tempo", methods=["GET"])
@login_required
def dicas_tempo():
    try:
        data_limite = datetime.now() - timedelta(days=7)
        mensagens_recentes = Message.query.filter(
            Message.user_id == current_user.id,
            Message.timestamp >= data_limite,
        ).all()

        horarios_uso = analisar_horarios_uso(mensagens_recentes)
        total_mensagens = len(mensagens_recentes)
        dicas_html = gerar_dicas_personalizadas(horarios_uso, total_mensagens)

        return jsonify({
            "dicas": dicas_html,
            "metadata": {
                "periodo_analise": "Últimos 7 dias",
                "total_interacoes": total_mensagens,
            },
        })
    except Exception as e:
        print(f"Erro nas dicas de tempo: {e}")
        return jsonify({
            "dicas": "<div class='error'>Erro ao gerar dicas de tempo. Tente novamente.</div>",
            "metadata": {"periodo_analise": "N/A", "total_interacoes": 0},
        }), 500

# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET"])
def login_page():
    if current_user.is_authenticated:
        return redirect("/")
    return render_template("login.html")


@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    data = request.form if request.form else request.get_json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        if request.form:
            return render_template("login.html", error="Preencha todos os campos.")
        return jsonify({"error": "Preencha todos os campos."}), 400

    user = User.query.filter_by(username=username).first()

    if user and check_password_hash(user.password, password):
        login_user(user)
        return redirect("/") if request.form else jsonify({"message": "Login realizado com sucesso"})

    if request.form:
        return render_template("login.html", error="Credenciais inválidas")
    return jsonify({"error": "Credenciais inválidas"}), 401


@app.route("/register", methods=["GET"])
def register_page():
    if current_user.is_authenticated:
        return redirect("/")
    return render_template("register.html")


@app.route("/register", methods=["POST"])
@limiter.limit("5 per minute")
def register():
    data = request.form if request.form else request.get_json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or len(username) < 3 or len(username) > 30:
        msg = "O nome de usuário deve ter entre 3 e 30 caracteres."
        if request.form:
            return render_template("register.html", error=msg)
        return jsonify({"error": msg}), 400

    if not re.match(r"^[a-zA-Z0-9_.\-]+$", username):
        msg = "O nome de usuário deve conter apenas letras, números e ponto/traço."
        if request.form:
            return render_template("register.html", error=msg)
        return jsonify({"error": msg}), 400

    erro_senha = validar_forca_senha(password)
    if erro_senha:
        if request.form:
            return render_template("register.html", error=erro_senha)
        return jsonify({"error": erro_senha}), 400

    if User.query.filter_by(username=username).first():
        msg = "Esse nome de usuário já está em uso."
        if request.form:
            return render_template("register.html", error=msg)
        return jsonify({"error": msg}), 409

    hashed_password = generate_password_hash(password, method="scrypt")
    user = User(username=username, password=hashed_password)
    db.session.add(user)
    db.session.commit()

    # Login automático imediato após o cadastro
    login_user(user)

    if request.form:
        return redirect("/")
    return jsonify({"message": "Conta criada e login realizado com sucesso", "user_id": user.id})


@app.route("/logout", methods=["POST", "GET"])
@login_required
def logout():
    logout_user()
    return redirect("/login")

# ---------------------------------------------------------------------------
# Conversas e histórico
# ---------------------------------------------------------------------------

@app.route("/nova-conversa", methods=["POST"])
@login_required
def nova_conversa():
    conversa = Conversation(user_id=current_user.id, title="Nova conversa")
    db.session.add(conversa)
    db.session.commit()
    return jsonify({"message": "Conversa criada", "conversa_id": conversa.id})


@app.route("/historico", methods=["GET"])
@login_required
def historico():
    conversas = (
        Conversation.query.filter_by(user_id=current_user.id)
        .order_by(Conversation.created_at.desc())
        .limit(15)
        .all()
    )
    return jsonify([
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.strftime("%d/%m/%Y %H:%M"),
        }
        for c in conversas
    ])


@app.route("/mensagens/<int:conversa_id>")
@login_required
def mensagens(conversa_id):
    conversa = Conversation.query.get_or_404(conversa_id)
    if conversa.user_id != current_user.id:
        return jsonify({"error": "Acesso negado"}), 403

    msgs = (
        Message.query.filter_by(conversation_id=conversa_id)
        .order_by(Message.timestamp.asc())
        .limit(30)
        .all()
    )
    return jsonify([
        {
            "usuario": msg.user_message,
            "assistente": renderizar_markdown_seguro(msg.bot_response),
            "timestamp": msg.timestamp.strftime("%H:%M"),
        }
        for msg in msgs
    ])

# ---------------------------------------------------------------------------
# Criação de tabelas (funciona tanto com gunicorn quanto com __main__)
# ---------------------------------------------------------------------------
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
