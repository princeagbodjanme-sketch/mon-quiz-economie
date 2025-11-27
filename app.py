import streamlit as st
import google.generativeai as genai
import json
import time
import pandas as pd
import requests
from bs4 import BeautifulSoup
import sqlite3
import hashlib
from datetime import datetime
import matplotlib.pyplot as plt
from openai import OpenAI

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Gemini/GPT Exam Platform", page_icon="🎓", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .main-header { text-align: center; margin-bottom: 1rem; }
    .main-header h1 { font-size: 2.5rem; margin-bottom: 0.3rem; }
    .main-header p { color: #9CA3AF; }
    .stButton>button { border-radius: 8px; font-weight: bold; }
    .timer-box { font-size: 24px; font-weight: bold; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; background-color: #1f2937; }
    .timer-normal { color: #4ade80; border: 2px solid #4ade80; }
    .timer-alert { color: #ef4444; border: 2px solid #ef4444; animation: blinker 1s linear infinite; }
    @keyframes blinker { 50% { opacity: 0; } }
    .card {
        padding: 1rem 1.2rem;
        border-radius: 0.75rem;
        background-color: #111827;
        border: 1px solid #1f2937;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect('quiz_database.db')
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, course_name TEXT, score REAL, total_questions INTEGER, date TEXT, details_json TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS public_exams (id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, title TEXT, questions_json TEXT, created_at TEXT)""")
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(str.encode(password)).hexdigest()

def create_user(username: str, password: str) -> bool:
    conn = sqlite3.connect('quiz_database.db')
    try:
        conn.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (username, hash_password(password), str(datetime.now()))
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def check_login(username: str, password: str) -> bool:
    conn = sqlite3.connect('quiz_database.db')
    res = conn.execute(
        "SELECT * FROM users WHERE username = ? AND password = ?",
        (username, hash_password(password))
    ).fetchone()
    conn.close()
    return res is not None

def save_result_private(username, course_name, score, total, details):
    conn = sqlite3.connect('quiz_database.db')
    conn.execute(
        "INSERT INTO history (username, course_name, score, total_questions, date, details_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (username, course_name, score, total, str(datetime.now())[:16], json.dumps(details))
    )
    conn.commit()
    conn.close()

def get_user_history(username):
    conn = sqlite3.connect('quiz_database.db')
    try:
        df = pd.read_sql_query(
            "SELECT * FROM history WHERE username = ? ORDER BY id DESC",
            conn,
            params=(username,)
        )
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def get_public_exams():
    conn = sqlite3.connect('quiz_database.db')
    try:
        df = pd.read_sql_query("SELECT * FROM public_exams ORDER BY id DESC", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def publish_exam(author, title, questions):
    conn = sqlite3.connect('quiz_database.db')
    conn.execute(
        "INSERT INTO public_exams (author, title, questions_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (author, title, json.dumps(questions), str(datetime.now())[:16])
    )
    conn.commit()
    conn.close()

init_db()

# --- 3. UTILITAIRES ---
def extract_text_from_file(f) -> str:
    try:
        return f.getvalue().decode("utf-8")
    except Exception:
        return ""

def extract_text_from_url(url: str) -> str:
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            return ' '.join(
                [p.get_text(separator=" ", strip=True) for p in soup.find_all(['p', 'h1', 'h2', 'li'])]
            )
    except Exception:
        return ""
    return ""

def render_graph(data):
    if not data:
        return
    try:
        x = data.get('x')
        y = data.get('y')
        if not (isinstance(x, list) and isinstance(y, list) and len(x) == len(y)):
            return
        fig, ax = plt.subplots(figsize=(6, 4))
        plt.style.use('dark_background')
        ax.plot(x, y, marker='o', linestyle='-', linewidth=2)
        ax.set_xlabel(data.get('xlabel', 'X'))
        ax.set_ylabel(data.get('ylabel', 'Y'))
        ax.set_title(data.get('title', 'Graphique'))
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)
    except Exception:
        pass

def parse_quiz_json(raw_text: str):
    """Nettoie les blocs ```json ... ``` et retourne une liste de questions."""
    if not raw_text:
        raise ValueError("Texte vide retourné par le modèle.")
    text = raw_text.strip()
    if "```" in text:
        # on enlève les balises markdown éventuelles
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
    text = text.strip()
    return json.loads(text)

# --- 4. IA : GEMINI + GPT ---
def build_quiz_prompt(topic_text: str, num_questions: int) -> str:
    return f"""
Tu es un professeur expert qui prépare des QCM pour des étudiants.

Texte ou contenu de référence (tronqué si très long) :
\"\"\"{topic_text[:25000]}\"\"\"


TÂCHE :
- Génère un examen de **{num_questions} questions** à choix multiples.
- Chaque question doit avoir exactement 4 options : A, B, C, D.
- Une seule bonne réponse par question.
- Explique brièvement la réponse correcte.
- Quand c'est pertinent (économie, stats, maths...), ajoute un petit jeu de données pour tracer un graphique.

FORMAT DE SORTIE (JSON STRICT, SANS TEXTE AUTOUR) :
[
  {{
    "question": "Question en français ...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct_answer": "A",
    "explanation": "Explication courte en français.",
    "graph_data": null
  }}
]

- `graph_data` doit être soit `null`, soit un objet du type :
{{
  "x": [1, 2, 3],
  "y": [10, 12, 9],
  "xlabel": "Années",
  "ylabel": "Valeurs",
  "title": "Titre du graphique"
}}
- Ne renvoie **que** le JSON, sans commentaire.
"""

def generate_quiz_with_gemini(api_key: str, topic_text: str, num_questions: int, model_name: str):
    if not api_key:
        return {"error": "Aucune clé API Gemini fournie."}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name,
        generation_config={
            "temperature": 0.3,
            "max_output_tokens": 4096,
        },
    )

    prompt = build_quiz_prompt(topic_text, num_questions)

    raw_text = ""
    try:
        response = model.generate_content(prompt)
        raw_text = getattr(response, "text", None) or ""
        questions = parse_quiz_json(raw_text)
        return questions
    except Exception as e:
        return {"error": f"[Gemini] {e}", "raw": raw_text}

def generate_quiz_with_gpt(api_key: str, topic_text: str, num_questions: int, model_name: str):
    if not api_key:
        return {"error": "Aucune clé API OpenAI fournie."}

    client = OpenAI(api_key=api_key)
    prompt = build_quiz_prompt(topic_text, num_questions)

    raw_text = ""
    try:
        response = client.chat.completions.create(
            model=model_name,
            temperature=0.3,
            max_tokens=4096,
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un professeur d'université qui génère des QCM au format JSON strict."
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw_text = response.choices[0].message.content
        questions = parse_quiz_json(raw_text)
        return questions
    except Exception as e:
        return {"error": f"[OpenAI] {e}", "raw": raw_text}

# --- 5. INTERFACE ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""

    # --- AUTHENTIFICATION ---
    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown(
                '<div class="main-header"><h1>🔐 Connexion</h1>'
                '<p>Plateforme d’examens générés par IA (Gemini & GPT)</p></div>',
                unsafe_allow_html=True,
            )
            tab_l, tab_s = st.tabs(["Connexion", "Créer un compte"])
            with tab_l:
                u = st.text_input("Identifiant")
                p = st.text_input("Mot de passe", type="password")
                if st.button("Entrer"):
                    if check_login(u, p):
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.rerun()
                    else:
                        st.error("Identifiant ou mot de passe invalide.")
            with tab_s:
                nu = st.text_input("Nouvel identifiant")
                np = st.text_input("Nouveau mot de passe", type="password")
                if st.button("Créer"):
                    if not nu or not np:
                        st.warning("Merci de remplir les deux champs.")
                    elif create_user(nu, np):
                        st.success("Compte créé ! Vous pouvez vous connecter.")
                    else:
                        st.error("Cet identifiant est déjà utilisé.")
        return

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"👤 **{st.session_state.username}**")
        if st.button("Déconnexion"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

        st.divider()
        st.header("🧠 Moteur IA")

        provider = st.radio(
            "Fournisseur",
            ["Google Gemini", "OpenAI GPT"],
            horizontal=False,
        )

        if provider == "Google Gemini":
            gemini_api_key = st.text_input("Clé API Gemini", type="password", key="gemini_key")
            gemini_model = st.selectbox(
                "Modèle Gemini",
                ["gemini-2.5-flash", "gemini-2.5-pro"],
                index=0,
                help="Choisis un modèle Gemini disponible sur ton compte."
            )
            st.session_state.current_provider = "gemini"
            st.session_state.gemini_api_key = gemini_api_key
            st.session_state.gemini_model = gemini_model
        else:
            openai_api_key = st.text_input("Clé API OpenAI", type="password", key="openai_key")
            gpt_model = st.selectbox(
                "Modèle GPT",
                ["gpt-4.1-mini", "gpt-4.1"],
                index=0,
                help="Modèles recommandés : gpt-4.1-mini (rapide) ou gpt-4.1 (plus puissant)."
            )
            st.session_state.current_provider = "gpt"
            st.session_state.openai_api_key = openai_api_key
            st.session_state.gpt_model = gpt_model

    # --- EN-TÊTE PRINCIPALE ---
    st.markdown(
        '<div class="main-header"><h1>🎓 Espace de Révision IA</h1>'
        '<p>Génère, passe et partage des examens à partir de tes supports de cours.</p></div>',
        unsafe_allow_html=True,
    )

    tab_new, tab_hist, tab_pub = st.tabs(["📝 Nouvel examen", "📊 Historique", "🌍 Examens publics"])

    # --- ONGLET : NOUVEL EXAMEN ---
    with tab_new:
        col_gen, col_load = st.columns([2, 1])

        with col_gen:
            st.subheader("🤖 Générateur d'examen IA")
            st.caption("Charge un texte ou une URL, choisis ton moteur IA, puis lance la génération.")

            with st.container():
                st.markdown('<div class="card">', unsafe_allow_html=True)
                src = st.radio("Source du contenu", ["Fichier (.txt)", "URL"], horizontal=True)
                txt = ""
                if src == "Fichier (.txt)":
                    up = st.file_uploader("Fichier texte", type=['txt'])
                    if up:
                        txt = extract_text_from_file(up)
                else:
                    url = st.text_input("URL de la ressource")
                    if url:
                        txt = extract_text_from_url(url)
                nb_q = st.slider("Nombre de questions", 5, 30, 10)
                st.markdown('</div>', unsafe_allow_html=True)

            if st.button("🚀 Générer l'examen", type="primary"):
                if not txt or len(txt) < 50:
                    st.warning("Le texte est trop court. Fournis un contenu plus complet.")
                else:
                    provider = st.session_state.get("current_provider", "gemini")
                    with st.spinner("Génération des questions..."):
                        if provider == "gemini":
                            data = generate_quiz_with_gemini(
                                st.session_state.get("gemini_api_key", ""),
                                txt,
                                nb_q,
                                st.session_state.get("gemini_model", "gemini-2.5-flash"),
                            )
                        else:
                            data = generate_quiz_with_gpt(
                                st.session_state.get("openai_api_key", ""),
                                txt,
                                nb_q,
                                st.session_state.get("gpt_model", "gpt-4.1-mini"),
                            )

                    if isinstance(data, dict) and "error" in data:
                        st.error("Erreur lors de l'appel à l'API :")
                        st.code(data["error"])
                        raw = data.get("raw")
                        if raw:
                            with st.expander("Voir la réponse brute du modèle"):
                                st.code(raw, language="json")
                    elif isinstance(data, list) and data:
                        st.success("Examen généré avec succès ✅")
                        st.session_state.quiz_data = data
                        st.session_state.quiz_mode = "active"
                        st.session_state.current_course = "Examen IA"
                        st.session_state.score = 0
                        st.session_state.idx = 0
                        st.session_state.ans = {}
                        st.session_state.start_time = time.time()
                        st.session_state.duration = 1800  # 30 minutes
                        st.rerun()
                    else:
                        st.warning("Le modèle n'a pas renvoyé de questions exploitables.")

        with col_load:
            st.subheader("📥 Bibliothèque d'examens")
            df_pub = get_public_exams()
            if df_pub.empty:
                st.info("Aucun examen public pour le moment.")
            else:
                ch = st.selectbox("Examens disponibles", df_pub['title'])
                if st.button("Charger l'examen sélectionné"):
                    sel = df_pub[df_pub['title'] == ch].iloc[0]
                    st.session_state.quiz_data = json.loads(sel['questions_json'])
                    st.session_state.quiz_mode = "active"
                    st.session_state.current_course = sel['title']
                    st.session_state.score = 0
                    st.session_state.idx = 0
                    st.session_state.ans = {}
                    st.session_state.start_time = time.time()
                    st.session_state.duration = 1800
                    st.rerun()

    # --- MODE EXAMEN ACTIF ---
    if st.session_state.get('quiz_mode') == "active":
        st.divider()
        elapsed = time.time() - st.session_state.start_time
        rem = st.session_state.duration - elapsed
        if rem < 0:
            rem = 0
        mins, secs = divmod(int(rem), 60)
        timer_class = "timer-alert" if rem <= 300 else "timer-normal"
        st.markdown(
            f'<div class="timer-box {timer_class}">⏳ Temps restant : {mins:02d}:{secs:02d}</div>',
            unsafe_allow_html=True,
        )

        qs = st.session_state.quiz_data
        i = st.session_state.idx

        if rem <= 0:
            # Temps écoulé : on termine l'examen
            i = len(qs)

        if i < len(qs):
            q = qs[i]
            st.progress(i / len(qs), text=f"Question {i + 1}/{len(qs)}")

            st.markdown(f"### {q.get('question', 'Question indisponible')}")
            if q.get('graph_data'):
                render_graph(q['graph_data'])

            options = q.get('options', {})
            keys = list(options.keys())
            r = st.radio(
                "Ta réponse :",
                keys,
                format_func=lambda x: f"{x}) {options.get(x, '')}",
                key=f"q_{i}",
            )

            if st.button("Valider la réponse"):
                st.session_state.ans[i] = {
                    "u": r,
                    "c": q.get('correct_answer'),
                    "e": q.get('explanation'),
                    "q": q.get('question'),
                }
                if r == q.get('correct_answer'):
                    st.session_state.score += 1
                st.session_state.idx += 1
                st.rerun()
        else:
            st.balloons()
            final = st.session_state.score
            st.markdown(f"## ✅ Résultat final : {final}/{len(qs)}")
            st.metric("Score (%)", f"{100 * final / len(qs):.1f} %")

            save_result_private(
                st.session_state.username,
                st.session_state.current_course,
                final,
                len(qs),
                st.session_state.ans,
            )

            # Publication possible uniquement pour les examens IA
            if st.session_state.current_course == "Examen IA":
                if st.button("📤 Publier cet examen"):
                    publish_exam(
                        st.session_state.username,
                        f"Examen de {st.session_state.username}",
                        qs,
                    )
                    st.success("Examen publié dans les examens publics !")

            if st.button("Quitter l'examen"):
                st.session_state.quiz_mode = "inactive"
                st.rerun()

    # --- ONGLET : HISTORIQUE ---
    with tab_hist:
        st.subheader("📊 Historique personnel")
        df = get_user_history(st.session_state.username)
        if df.empty:
            st.info("Aucun examen passé pour l'instant.")
        else:
            st.dataframe(df[['date', 'course_name', 'score', 'total_questions']])

    # --- ONGLET : EXAMENS PUBLICS ---
    with tab_pub:
        st.subheader("🌍 Examens publics")
        df = get_public_exams()
        if df.empty:
            st.info("Aucun examen public pour le moment.")
        else:
            st.dataframe(df[['title', 'author', 'created_at']])

if __name__ == "__main__":
    main()
