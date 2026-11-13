# Chatbot Educacional para Pessoas com TEA

Este é um chatbot web feito com Flask + Together AI, projetado para auxiliar pessoas no espectro autista a estudar de forma clara, acolhedora e acessível.

# Site
https://chattea.yanramos.com.br/

## Funcionalidades

- Login e registro de usuários
- Histórico de conversas por usuário
- Upload de arquivos (.txt, .pdf, .docx, .pptx, .xlsx, .img)
- IA com contexto de conversa (usando Together AI)
- Tema escuro/claro
- Interface responsiva e acessível

## Tecnologias usadas

- Python (Flask)
- Together AI (GPT-OSS-20b)
- SQLite + SQLAlchemy
- HTML, CSS, JS
- Flask-Login
  
<img width="1889" height="910" alt="image" src="https://github.com/user-attachments/assets/4a19b900-7b72-448f-b7f7-0dcfc652eb66" />

<img width="1889" height="901" alt="image" src="https://github.com/user-attachments/assets/11e1da11-4f9c-4498-a801-d55ddca5ad28" />

<img width="1910" height="907" alt="Captura de tela 2026-01-27 021942" src="https://github.com/user-attachments/assets/dbe860a0-3073-4171-93df-8e4bf645e199" />

<img width="1879" height="906" alt="Captura de tela 2026-01-27 021956" src="https://github.com/user-attachments/assets/ba20b0f4-3db0-460c-a469-68cbe27ec9bc" />

<img width="1875" height="884" alt="Captura de tela 2026-01-27 022022" src="https://github.com/user-attachments/assets/8a97bc4a-0f3d-48d6-bfe3-b2a596568455" />


## Como rodar localmente

1. **Clone o repositório**
   ```bash
   git clone https://github.com/VitorOliveiraGomes/Chat-Bot-Educacional.git
   ```

2. **Acesse a pasta do projeto**
   ```bash
   cd Chat-Bot-Educacional
   ```

3. **Crie um ambiente virtual (recomendado)**
   ```bash
   python -m venv venv
   ```

4. **Ative o ambiente virtual**

   **No Windows:**
   ```bash
   venv\Scripts\activate
   ```

   **No Linux/macOS:**
   ```bash
   source venv/bin/activate
   ```

5. **Instale as dependências**
   ```bash
   pip install -r requirements.txt
   ```

6. **Configuração do `.env`**
   - Renomeie o arquivo:
     ```bash
     mv .env.example .env
     ```
   - Abra o `.env` e edite com:
     - Sua **API Key**: [Obtenha aqui](https://api.together.ai/)
     - Sua **Secret Key**: gere executando:
       ```python
       import secrets
       print(secrets.token_hex(16))
       ```

7. **Execute o chatbot**
   ```bash
   python Serv.py
   ```

## Licença

Este projeto está licenciado sob a [Licença MIT](LICENSE).

## Contato

**Vitor Oliveira Gomes**  
[GitHub](https://github.com/VitorOliveiraGomes) | [LinkedIn](https://www.linkedin.com/in/vitor-oliveira-gomes-610670317)

**Kaian Perez**  
[GitHub](https://github.com/kaiiiarchives) | [LinkedIn](https://www.linkedin.com/in/kaian-perez-7803792bb/)

