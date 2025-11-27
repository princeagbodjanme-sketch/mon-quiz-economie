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

# --- 1. CONFIGURATION DE LA PAGE (Doit être la première ligne) ---
st.set_page_config(page_title="Gemini Exam Platform", page_icon="🧠", layout="wide")

# --- 2. STYLE CSS & JAVASCRIPT ---
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

# --- 3. BASE DE DONNÉES (SQLite) ---
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

# --- 4. FONCTIONS UTILITAIRES (Texte & Graphiques) ---
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
    except: st.error("Erreur d'affichage du graphique")

# --- 5. COEUR IA (La stratégie Hybride) ---
def generate_quiz_data(api_key, topic_text, num_questions):
    if not api_key: return []
    
    genai.configure(api_key=api_key)
    
    # STRATÉGIE : On tente le modèle le plus fort (3 Pro), sinon le plus rapide (2.5 Flash)
    primary_model = 'gemini-3-pro'
    fallback_model = 'gemini-2.5-flash'
    
    model = None
    used_model_name = ""

    # Tentative 1
    try:
        model = genai.GenerativeModel(primary_model)
        model.generate_content("test", request_options={'timeout': 5}) 
        used_model_name = primary_model
    except:
        # Tentative 2
        try:
            model = genai.GenerativeModel(fallback_model)
            used_model_name = fallback_model
        except Exception as e:
            st.error(f"Erreur critique : Aucun modèle ne répond. Vérifie ta clé API. ({e})")
            return []

    # Notification discrète
    st.toast(f"Moteur IA actif : {used_model_name}", icon="🤖")

    prompt = f"""
    Agis comme un professeur expert universitaire.
    Basé sur le texte suivant : {topic_text[:25000]}
    
    Génère un examen de {num_questions} questions au format JSON STRICT.
    IMPORTANT : Pour 20% des questions, inclus des données graphiques (champs 'graph_data') si pertinent (économie, stats).
    
    Format attendu (Liste de JSON) :
    [
        {{
            "question": "...",
            "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
            "correct_answer": "A",
            "explanation": "...",
            "graph_data": {{"x": [1,2,3], "y": [10,20,5], "xlabel": "Qté", "ylabel": "Prix", "title": "Offre"}} 
            (ou null si pas de graphique)
        }}
    ]
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text
        # Nettoyage bourrin du JSON pour éviter les bugs
        if "```json" in text: text = text.split("```json")[1]
        if "```" in text: text = text.split("```")[0]
        return json.loads(text.strip())
    except Exception as e:
        st.error(f"Erreur de lecture de la réponse IA : {e}")
        return []

# --- 6. APPLICATION PRINCIPALE (Interface) ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""

    # -- ECRAN LOGIN --
    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔐 Gemini Exam")
            tab_l, tab_s = st.tabs(["Se Connecter", "Créer Compte"])
            with tab_l:
                u = st.text_input("Identifiant")
                p = st.text_input("Mot de passe", type="password")
                if st.button("Entrer"):
                    if check_login(u, p):
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.rerun()
                    else: st.error("Inconnu ou mauvais mot de passe")
            with tab_s:
                nu = st.text_input("Nouvel ID")
                np = st.text_input("Nouveau MDP", type="password")
                if st.button("S'inscrire"):
                    if create_user(nu, np): st.success("Créé ! Tu peux te connecter.")
                    else: st.error("Déjà pris.")
        return

    # -- ECRAN CONNECTÉ --
    with st.sidebar:
        st.write(f"Bonjour, **{st.session_state.username}** 👋")
        if st.button("Déconnexion"):
            st.session_state.logged_in = False
            st.rerun()
        st.divider()
        api_key = st.text_input("Clé API Gemini", type="password", help="Commence par AIza...")

    st.title("🎓 Simulateur d'Examen")
    
    tab_new, tab_hist, tab_pub = st.tabs(["📝 Nouvel Examen", "📊 Mon Historique", "🌍 Bibliothèque Publique"])

    # ONGLET 1 : NOUVEL EXAMEN
    with tab_new:
        col_gen, col_load = st.columns(2)
        
        # A. Générateur IA
        with col_gen:
            st.subheader("🤖 Générer via IA")
            src = st.radio("Source", ["Fichier (.txt)", "Lien URL"], horizontal=True)
            txt = ""
            if src == "Fichier (.txt)":
                up = st.file_uploader("Fichier", type=['txt'])
                if up: txt = extract_text_from_file(up)
            else:
                url = st.text_input("URL du cours")
                if url: txt = extract_text_from_url(url)
            
            nb_q = st.slider("Questions", 5, 20, 8)
            time_limit = st.slider("Temps (minutes)", 5, 60, 20)
            
            if st.button("🚀 Générer l'examen", type="primary"):
                if api_key and len(txt) > 50:
                    with st.spinner("Analyse du cours et génération des questions..."):
                        data = generate_quiz_data(api_key, txt, nb_q)
                        if data:
                            st.session_state.quiz_data = data
                            st.session_state.quiz_mode = "active"
                            st.session_state.current_course = "Généré par IA"
                            st.session_state.score = 0
                            st.session_state.idx = 0
                            st.session_state.ans = {}
                            st.session_state.start_time = time.time()
                            st.session_state.duration = time_limit * 60
                            st.rerun()
                else: st.warning("Il manque la Clé API ou le texte du cours.")

        # B. Charger Public
        with col_load:
            st.subheader("📥 Charger un Examen Public")
            df_pub = get_public_exams()
            if not df_pub.empty:
                ch = st.selectbox("Choisir", df_pub['title'] + " (par " + df_pub['author'] + ")")
                if st.button("Lancer cet examen"):
                    sel = df_pub[df_pub['title'] + " (par " + df_pub['author'] + ")" == ch].iloc[0]
                    st.session_state.quiz_data = json.loads(sel['questions_json'])
                    st.session_state.quiz_mode = "active"
                    st.session_state.current_course = sel['title']
                    st.session_state.score = 0
                    st.session_state.idx = 0
                    st.session_state.ans = {}
                    st.session_state.start_time = time.time()
                    st.session_state.duration = 30 * 60 # Défaut 30 min pour public
                    st.rerun()
            else: st.info("Aucun examen public.")

    # ONGLET 2 : HISTORIQUE
    with tab_hist:
        df = get_user_history(st.session_state.username)
        if not df.empty:
            st.dataframe(df[['date', 'course_name', 'score', 'total_questions']])
        else: st.info("Vide.")

    # ONGLET 3 : PUBLIQUE
    with tab_pub:
        df_p = get_public_exams()
        if not df_p.empty: st.dataframe(df_p[['created_at', 'title', 'author']])
        else: st.info("Vide.")

    # --- MODE QUIZ ACTIF ---
    if 'quiz_mode' in st.session_state and st.session_state.quiz_mode == "active":
        st.divider()
        
        # Timer
        elapsed = time.time() - st.session_state.start_time
        remaining = st.session_state.duration - elapsed
        mins, secs = divmod(int(remaining), 60)
        style = "timer-normal" if remaining > 300 else "timer-alert"
        if remaining < 0: 
            st.error("TEMPS ÉCOULÉ !")
            remaining = 0
        
        st.markdown(f'<div class="timer-box {style}">⏳ {mins:02d}:{secs:02d}</div>', unsafe_allow_html=True)

        qs = st.session_state.quiz_data
        i = st.session_state.idx

        if i < len(qs):
            q = qs[i]
            st.progress((i)/len(qs), text=f"Question {i+1}/{len(qs)}")
            st.markdown(f"### {q['question']}")
            
            # Graphique ?
            if q.get('graph_data'):
                render_graph(q['graph_data'])
            
            ops = q['options']
            r = st.radio("Votre réponse :", list(ops.keys()), format_func=lambda x: f"{x}) {ops[x]}", key=f"rad_{i}")
            
            if st.button("Valider ➡️"):
                st.session_state.ans[i] = {"u": r, "c": q['correct_answer'], "e": q['explanation'], "q": q['question']}
                if r == q['correct_answer']: st.session_state.score += 1
                st.session_state.idx += 1
                st.rerun()
        else:
            st.balloons()
            final = st.session_state.score
            total = len(qs)
            st.markdown(f"# 🏁 Note : {final}/{total}")
            
            # Sauvegarde
            save_result_private(st.session_state.username, st.session_state.current_course, final, total, st.session_state.ans)
            st.success("Résultat sauvegardé en privé.")
            
            # Corrections
            with st.expander("Voir les corrections détaillées"):
                for k, v in st.session_state.ans.items():
                    color = "green" if v['u'] == v['c'] else "red"
                    st.markdown(f"**Q : {v['q']}**")
                    st.markdown(f":{color}[Toi: {v['u']} | Correct: {v['c']}]")
                    st.info(v['e'])
                    st.divider()

            # Publication
            if st.session_state.current_course == "Généré par IA":
                st.write("---")
                st.subheader("🤝 Partager cet examen ?")
                st.caption("Seules les questions seront partagées. Ton cours source reste secret.")
                titre = st.text_input("Titre pour la bibliothèque publique")
                if st.button("Publier maintenant"):
                    publish_exam(st.session_state.username, titre, qs)
                    st.success("Publié !")

            if st.button("Quitter"):
                st.session_state.quiz_mode = "inactive"
                st.rerun()

if __name__ == "__main__":
    main()
