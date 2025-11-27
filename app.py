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

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Gemini Exam Platform", page_icon="🎓", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .stButton>button { border-radius: 8px; font-weight: bold; }
    .timer-box { font-size: 24px; font-weight: bold; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; background-color: #1f2937; }
    .timer-normal { color: #4ade80; border: 2px solid #4ade80; }
    .timer-alert { color: #ef4444; border: 2px solid #ef4444; animation: blinker 1s linear infinite; }
    @keyframes blinker { 50% { opacity: 0; } }
</style>
""", unsafe_allow_html=True)

# --- 2. BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect('quiz_database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, course_name TEXT, score REAL, total_questions INTEGER, date TEXT, details_json TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS public_exams (id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, title TEXT, questions_json TEXT, created_at TEXT)''')
    conn.commit()
    conn.close()

def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()

def create_user(username, password):
    conn = sqlite3.connect('quiz_database.db')
    try:
        conn.execute("INSERT INTO users VALUES (?, ?, ?)", (username, hash_password(password), str(datetime.now())))
        conn.commit()
        return True
    except: return False
    finally: conn.close()

def check_login(username, password):
    conn = sqlite3.connect('quiz_database.db')
    res = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hash_password(password))).fetchone()
    conn.close()
    return res is not None

def save_result_private(username, course_name, score, total, details):
    conn = sqlite3.connect('quiz_database.db')
    conn.execute("INSERT INTO history (username, course_name, score, total_questions, date, details_json) VALUES (?, ?, ?, ?, ?, ?)", 
                 (username, course_name, score, total, str(datetime.now())[:16], json.dumps(details)))
    conn.commit()
    conn.close()

def get_user_history(username):
    conn = sqlite3.connect('quiz_database.db')
    try: df = pd.read_sql_query("SELECT * FROM history WHERE username = ? ORDER BY id DESC", conn, params=(username,))
    except: df = pd.DataFrame()
    conn.close()
    return df

def get_public_exams():
    conn = sqlite3.connect('quiz_database.db')
    try: df = pd.read_sql_query("SELECT * FROM public_exams ORDER BY id DESC", conn)
    except: df = pd.DataFrame()
    conn.close()
    return df

def publish_exam(author, title, questions):
    conn = sqlite3.connect('quiz_database.db')
    conn.execute("INSERT INTO public_exams (author, title, questions_json, created_at) VALUES (?, ?, ?, ?)",
              (author, title, json.dumps(questions), str(datetime.now())[:16]))
    conn.commit()
    conn.close()

init_db()

# --- 3. UTILITAIRES ---
def extract_text_from_file(f):
    try: return f.getvalue().decode("utf-8")
    except: return ""

def extract_text_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            return ' '.join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2', 'li'])])
    except: return ""
    return ""

def render_graph(data):
    if not data: return
    try:
        fig, ax = plt.subplots(figsize=(6, 4))
        plt.style.use('dark_background')
        ax.plot(data['x'], data['y'], marker='o', linestyle='-', color='#4fa8d1', linewidth=2)
        ax.set_xlabel(data.get('xlabel', 'X'))
        ax.set_ylabel(data.get('ylabel', 'Y'))
        ax.set_title(data.get('title', 'Graphique'))
        ax.grid(True, alpha=0.3)
        st.pyplot(fig)
    except: pass

# --- 4. IA AVEC SÉLECTEUR ---
def generate_quiz_data(api_key, topic_text, num_questions, selected_model):
    if not api_key: return []
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(selected_model)

    prompt = f"""
    Agis comme un professeur expert. Texte source : {topic_text[:25000]}
    
    Génère un examen de {num_questions} questions au format JSON STRICT.
    Inclus 'graph_data' (x, y, label) pour 20% des questions si pertinent (éco/maths).
    
    Format JSON attendu (Liste d'objets) :
    [
        {{
            "question": "...",
            "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
            "correct_answer": "A",
            "explanation": "...",
            "graph_data": null
        }}
    ]
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text
        # Nettoyage JSON
        if "```json" in text: text = text.split("```json")[1]
        if "```" in text: text = text.split("```")[0]
        return json.loads(text.strip())
    except Exception as e:
        # On retourne l'erreur exacte pour l'afficher à l'utilisateur
        return {"error": str(e)}

# --- 5. INTERFACE ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""

    # Login
    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔐 Connexion")
            tab_l, tab_s = st.tabs(["Connexion", "Créer Compte"])
            with tab_l:
                u = st.text_input("Identifiant")
                p = st.text_input("Mot de passe", type="password")
                if st.button("Entrer"):
                    if check_login(u, p):
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.rerun()
                    else: st.error("Erreur login")
            with tab_s:
                nu = st.text_input("Nouvel ID")
                np = st.text_input("Nouveau MDP", type="password")
                if st.button("Créer"):
                    if create_user(nu, np): st.success("OK! Connecte-toi.")
                    else: st.error("Pris")
        return

    # Sidebar
    with st.sidebar:
        st.write(f"👤 **{st.session_state.username}**")
        if st.button("Déconnexion"):
            st.session_state.logged_in = False
            st.rerun()
        st.divider()
        st.header("🔑 Configuration IA")
        api_key = st.text_input("Clé API Gemini", type="password")
        
        # LE SÉLECTEUR DE CERVEAU (C'est ici la magie !)
        model_choice = st.selectbox(
            "Choisis ton modèle :",
            ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro", "gemini-1.0-pro"],
            help="Si l'un ne marche pas, essaie l'autre !"
        )

    st.title("🎓 Espace de Révision")
    
    tab_new, tab_hist, tab_pub = st.tabs(["📝 Nouvel Examen", "📊 Historique", "🌍 Public"])

    with tab_new:
        col_gen, col_load = st.columns(2)
        
        with col_gen:
            st.subheader("🤖 Générateur IA")
            src = st.radio("Source", ["Fichier (.txt)", "URL"], horizontal=True)
            txt = ""
            if src == "Fichier (.txt)":
                up = st.file_uploader("Fichier", type=['txt'])
                if up: txt = extract_text_from_file(up)
            else:
                url = st.text_input("URL")
                if url: txt = extract_text_from_url(url)
            
            nb_q = st.slider("Questions", 5, 20, 5)
            
            if st.button("🚀 Générer", type="primary"):
                if api_key and len(txt) > 50:
                    with st.spinner(f"Génération avec {model_choice}..."):
                        # Appel de l'IA avec le modèle choisi
                        data = generate_quiz_data(api_key, txt, nb_q, model_choice)
                        
                        # Gestion des erreurs
                        if isinstance(data, dict) and "error" in data:
                            st.error(f"Erreur avec le modèle {model_choice} :")
                            st.code(data["error"])
                            st.warning("👉 Essaie de changer de modèle dans la barre latérale !")
                        elif data:
                            st.session_state.quiz_data = data
                            st.session_state.quiz_mode = "active"
                            st.session_state.current_course = "Généré par IA"
                            st.session_state.score = 0
                            st.session_state.idx = 0
                            st.session_state.ans = {}
                            st.session_state.start_time = time.time()
                            st.session_state.duration = 1800
                            st.rerun()
                else: st.warning("Clé API ou Texte manquant")

        with col_load:
            st.subheader("📥 Bibliothèque")
            df_pub = get_public_exams()
            if not df_pub.empty:
                ch = st.selectbox("Examen", df_pub['title'])
                if st.button("Charger"):
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

    if 'quiz_mode' in st.session_state and st.session_state.quiz_mode == "active":
        st.divider()
        elapsed = time.time() - st.session_state.start_time
        rem = st.session_state.duration - elapsed
        mins, secs = divmod(int(rem), 60)
        st.markdown(f'<div class="timer-box timer-normal">⏳ {mins:02d}:{secs:02d}</div>', unsafe_allow_html=True)

        qs = st.session_state.quiz_data
        i = st.session_state.idx
        if i < len(qs):
            q = qs[i]
            st.progress((i)/len(qs), text=f"Question {i+1}/{len(qs)}")
            st.markdown(f"### {q['question']}")
            if q.get('graph_data'): render_graph(q['graph_data'])
            r = st.radio("Réponse", list(q['options'].keys()), format_func=lambda x: f"{x}) {q['options'][x]}", key=f"q_{i}")
            if st.button("Valider"):
                st.session_state.ans[i] = {"u": r, "c": q['correct_answer'], "e": q['explanation'], "q": q['question']}
                if r == q['correct_answer']: st.session_state.score += 1
                st.session_state.idx += 1
                st.rerun()
        else:
            st.balloons()
            final = st.session_state.score
            st.markdown(f"# Note : {final}/{len(qs)}")
            save_result_private(st.session_state.username, st.session_state.current_course, final, len(qs), st.session_state.ans)
            
            if st.session_state.current_course == "Généré par IA":
                if st.button("Publier l'examen"):
                    publish_exam(st.session_state.username, f"Examen de {st.session_state.username}", qs)
                    st.success("Publié !")
            
            if st.button("Quitter"):
                st.session_state.quiz_mode = "inactive"
                st.rerun()

    with tab_hist:
        df = get_user_history(st.session_state.username)
        if not df.empty: st.dataframe(df[['date', 'course_name', 'score']])

    with tab_pub:
        df = get_public_exams()
        if not df.empty: st.dataframe(df[['title', 'author']])

if __name__ == "__main__":
    main()
