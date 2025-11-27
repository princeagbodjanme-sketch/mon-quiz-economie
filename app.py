import streamlit as st
import google.generativeai as genai
import json
import time
import pandas as pd
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup
import sqlite3
import hashlib
from datetime import datetime

# --- CONFIGURATION STYLE & PAGE ---
st.set_page_config(page_title="Gemini Exam Platform", page_icon="🔐", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .stButton>button { border-radius: 8px; }
    .timer-box { font-size: 24px; font-weight: bold; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 20px; }
    .timer-normal { color: #00ff00; border: 1px solid #00ff00; }
    .timer-alert { color: #ff0000; border: 2px solid #ff0000; animation: blinker 1s linear infinite; }
    .metric-card { background-color: #262730; padding: 15px; border-radius: 10px; border-left: 5px solid #4fa8d1; }
    @keyframes blinker { 50% { opacity: 0; } }
</style>
""", unsafe_allow_html=True)

# --- GESTION BASE DE DONNÉES (SQLite) ---

def init_db():
    conn = sqlite3.connect('quiz_database.db')
    c = conn.cursor()
    # Table Utilisateurs
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, created_at TEXT)''')
    # Table Historique Personnel (Privé)
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, 
                  course_name TEXT, score REAL, total_questions INTEGER, date TEXT, details_json TEXT)''')
    # Table Examens Publics (Partagés sans le dataset source)
    c.execute('''CREATE TABLE IF NOT EXISTS public_exams
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, 
                  title TEXT, questions_json TEXT, created_at TEXT)''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def create_user(username, password):
    conn = sqlite3.connect('quiz_database.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?)", (username, hash_password(password), str(datetime.now())))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def check_login(username, password):
    conn = sqlite3.connect('quiz_database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hash_password(password)))
    result = c.fetchone()
    conn.close()
    return result is not None

def save_result_private(username, course_name, score, total, details):
    conn = sqlite3.connect('quiz_database.db')
    c = conn.cursor()
    c.execute("INSERT INTO history (username, course_name, score, total_questions, date, details_json) VALUES (?, ?, ?, ?, ?, ?)",
              (username, course_name, score, total, str(datetime.now())[:16], json.dumps(details)))
    conn.commit()
    conn.close()

def publish_exam(author, title, questions):
    conn = sqlite3.connect('quiz_database.db')
    c = conn.cursor()
    # On ne sauvegarde QUE les questions, pas le texte source (Dataset)
    c.execute("INSERT INTO public_exams (author, title, questions_json, created_at) VALUES (?, ?, ?, ?)",
              (author, title, json.dumps(questions), str(datetime.now())[:16]))
    conn.commit()
    conn.close()

def get_user_history(username):
    conn = sqlite3.connect('quiz_database.db')
    df = pd.read_sql_query("SELECT * FROM history WHERE username = ?", conn, params=(username,))
    conn.close()
    return df

def get_public_exams():
    conn = sqlite3.connect('quiz_database.db')
    df = pd.read_sql_query("SELECT * FROM public_exams ORDER BY id DESC", conn)
    conn.close()
    return df

# Initialisation DB au démarrage
init_db()

# --- FONCTIONS UTILITAIRES IA --- (Similaires à avant)

def extract_text_from_file(uploaded_file):
    try: return uploaded_file.getvalue().decode("utf-8")
    except: return ""

def extract_text_from_url(url):
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            return ' '.join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2', 'li'])])
    except: return ""
    return ""

def generate_quiz_data(api_key, topic_text, num_questions):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    Tu es un expert pédagogique. Basé sur ce texte : {topic_text[:20000]}
    Crée un examen de {num_questions} questions au format JSON STRICT.
    Structure: [{{ "question": "...", "options": {{"A":"..","B":".."}}, "correct_answer": "A", "explanation": ".." }}]
    """
    try:
        response = model.generate_content(prompt)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except: return []

# --- INTERFACE ---

def main():
    # Gestion de Session
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""

    # --- ÉCRAN DE CONNEXION ---
    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔐 Connexion Sécurisée")
            st.info("Connecte-toi pour accéder à ton espace privé.")
            
            tab_login, tab_signup = st.tabs(["Se Connecter", "Créer un compte"])
            
            with tab_login:
                login_user = st.text_input("Identifiant")
                login_pass = st.text_input("Mot de passe", type="password")
                if st.button("Entrer"):
                    if check_login(login_user, login_pass):
                        st.session_state.logged_in = True
                        st.session_state.username = login_user
                        st.success("Connexion réussie !")
                        st.rerun()
                    else:
                        st.error("Identifiant ou mot de passe incorrect.")
            
            with tab_signup:
                new_user = st.text_input("Nouvel Identifiant")
                new_pass = st.text_input("Nouveau mot de passe", type="password")
                if st.button("S'inscrire"):
                    if create_user(new_user, new_pass):
                        st.success("Compte créé ! Tu peux te connecter.")
                    else:
                        st.error("Cet identifiant existe déjà.")
        return # On arrête l'exécution ici si pas connecté

    # --- APP PRINCIPALE (Une fois connecté) ---
    
    # Sidebar
    with st.sidebar:
        st.write(f"👤 Connecté en tant que : **{st.session_state.username}**")
        if st.button("Se déconnecter"):
            st.session_state.logged_in = False
            st.rerun()
        st.divider()
        api_key = st.text_input("Clé API Gemini", type="password")
        
    st.title(f"Bienvenue, {st.session_state.username} 👋")
    
    # Navigation par Onglets
    tab_new, tab_hist, tab_public = st.tabs(["📝 Nouvel Examen", "📊 Mon Historique Privé", "🌍 Examens Partagés"])

    # --- ONGLET 1 : GÉNÉRER OU CHARGER ---
    with tab_new:
        col_gen, col_load = st.columns(2)
        
        # Option A : Générer avec l'IA
        with col_gen:
            st.subheader("🤖 Générer via IA")
            source_type = st.radio("Source", ["Fichier .txt", "URL Web"], horizontal=True)
            course_text = ""
            
            if source_type == "Fichier .txt":
                f = st.file_uploader("Fichier", type=['txt'])
                if f: course_text = extract_text_from_file(f)
            else:
                url = st.text_input("URL")
                if url: course_text = extract_text_from_url(url)
            
            num_q = st.slider("Nb Questions", 5, 20, 5)
            
            if st.button("Générer l'examen IA", type="primary"):
                if api_key and len(course_text) > 50:
                    with st.spinner("Création en cours..."):
                        data = generate_quiz_data(api_key, course_text, num_q)
                        if data:
                            st.session_state.quiz_data = data
                            st.session_state.quiz_mode = "active"
                            st.session_state.current_course_name = "Généré par IA"
                            st.session_state.score = 0
                            st.session_state.current_index = 0
                            st.session_state.user_answers = {}
                            st.rerun()
                else:
                    st.warning("Clé API manquante ou texte trop court.")

        # Option B : Charger un examen public
        with col_load:
            st.subheader("📥 Charger un Public")
            df_pub = get_public_exams()
            if not df_pub.empty:
                exam_choice = st.selectbox("Choisir un examen", df_pub['title'] + " (par " + df_pub['author'] + ")")
                if st.button("Lancer cet examen"):
                    selected_row = df_pub[df_pub['title'] + " (par " + df_pub['author'] + ")" == exam_choice].iloc[0]
                    st.session_state.quiz_data = json.loads(selected_row['questions_json'])
                    st.session_state.quiz_mode = "active"
                    st.session_state.current_course_name = selected_row['title']
                    st.session_state.score = 0
                    st.session_state.current_index = 0
                    st.session_state.user_answers = {}
                    st.rerun()
            else:
                st.info("Aucun examen public disponible.")

    # --- MODE QUIZ ACTIF ---
    if 'quiz_mode' in st.session_state and st.session_state.quiz_mode == "active":
        st.divider()
        questions = st.session_state.quiz_data
        idx = st.session_state.current_index
        
        if idx < len(questions):
            q = questions[idx]
            st.markdown(f"### Question {idx+1}/{len(questions)}")
            st.write(q['question'])
            
            choice = st.radio("Réponse", list(q['options'].keys()), format_func=lambda x: f"{x}) {q['options'][x]}", key=f"q_{idx}")
            
            if st.button("Valider"):
                st.session_state.user_answers[idx] = {
                    "user": choice, "correct": q['correct_answer'], "expl": q['explanation'], "q_text": q['question']
                }
                if choice == q['correct_answer']: st.session_state.score += 1
                st.session_state.current_index += 1
                st.rerun()
        else:
            # FIN DU QUIZ
            st.balloons()
            final = st.session_state.score
            total = len(questions)
            st.success(f"Terminé ! Score : {final}/{total}")
            
            # Sauvegarde automatique dans historique privé
            save_result_private(st.session_state.username, st.session_state.current_course_name, final, total, st.session_state.user_answers)
            st.info("✅ Résultat sauvegardé dans ton historique privé.")
            
            # Option de partage (Seulement si c'est une génération IA, pas si on passe déjà un test public)
            if st.session_state.current_course_name == "Généré par IA":
                st.markdown("### 🤝 Partager cet examen ?")
                st.write("Cela rendra les questions publiques, mais **gardera ton cours d'origine (dataset) secret**.")
                exam_title = st.text_input("Donne un titre à cet examen (ex: Économie Chap 1)")
                if st.button("Publier l'examen"):
                    publish_exam(st.session_state.username, exam_title, questions)
                    st.success("Examen publié pour les autres utilisateurs !")
            
            if st.button("Fermer"):
                st.session_state.quiz_mode = "inactive"
                st.rerun()

    # --- ONGLET 2 : HISTORIQUE ---
    with tab_hist:
        st.header("Ton Carnet de Notes")
        df_hist = get_user_history(st.session_state.username)
        if not df_hist.empty:
            st.dataframe(df_hist[['date', 'course_name', 'score', 'total_questions']])
            
            # Graphique de progression
            st.markdown("### Ta progression")
            st.line_chart(df_hist.set_index('date')['score'])
        else:
            st.info("Aucun historique pour l'instant.")

    # --- ONGLET 3 : EXAMENS PUBLICS ---
    with tab_public:
        st.header("Bibliothèque Communautaire")
        st.write("Ici, tu peux voir les examens créés par d'autres, sans voir leurs notes ni leurs cours d'origine.")
        df_pub_view = get_public_exams()
        if not df_pub_view.empty:
            st.dataframe(df_pub_view[['created_at', 'title', 'author']])
        else:
            st.info("La bibliothèque est vide.")

if __name__ == "__main__":
    main()
