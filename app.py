import streamlit as st
import json
import time
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime
import matplotlib.pyplot as plt
import random

# --- CONFIGURATION ---
st.set_page_config(page_title="Gemini Exam (Mode DÉMO)", page_icon="🧪", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .stButton>button { border-radius: 8px; font-weight: bold; background-color: #7c3aed; color: white; }
    .timer-box { font-size: 24px; font-weight: bold; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; background-color: #1f2937; }
    .timer-normal { color: #4ade80; border: 2px solid #4ade80; }
    .timer-alert { color: #ef4444; border: 2px solid #ef4444; animation: blinker 1s linear infinite; }
    @keyframes blinker { 50% { opacity: 0; } }
</style>
""", unsafe_allow_html=True)

# --- BASE DE DONNÉES ---
def init_db():
    conn = sqlite3.connect('quiz_database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, course_name TEXT, score REAL, total_questions INTEGER, date TEXT, details_json TEXT)''')
    conn.commit()
    conn.close()

def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()
def create_user(u, p):
    try:
        conn = sqlite3.connect('quiz_database.db')
        conn.execute("INSERT INTO users VALUES (?, ?, ?)", (u, hash_password(p), str(datetime.now())))
        conn.commit()
        conn.close()
        return True
    except: return False
def check_login(u, p):
    conn = sqlite3.connect('quiz_database.db')
    res = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (u, hash_password(p))).fetchone()
    conn.close()
    return res is not None
def save_hist(u, c, s, t, d):
    conn = sqlite3.connect('quiz_database.db')
    conn.execute("INSERT INTO history (username, course_name, score, total_questions, date, details_json) VALUES (?, ?, ?, ?, ?, ?)", (u, c, s, t, str(datetime.now())[:16], json.dumps(d)))
    conn.commit()
    conn.close()
def get_hist(u):
    conn = sqlite3.connect('quiz_database.db')
    try: df = pd.read_sql_query("SELECT * FROM history WHERE username = ? ORDER BY id DESC", conn, params=(u,))
    except: df = pd.DataFrame()
    conn.close()
    return df

init_db()

# --- FAUSSE IA (SIMULATEUR) ---
def generate_fake_quiz():
    """Génère un faux quiz parfait pour tester l'interface"""
    time.sleep(2) # On fait semblant de réfléchir
    return [
        {
            "question": "Analyse du Coût Marginal : D'après la théorie standard, quelle est la relation entre le coût marginal (Cm) et le coût moyen (CM) à l'optimum technique ?",
            "options": {"A": "Cm est supérieur à CM", "B": "Cm coupe CM en son minimum", "C": "Cm est toujours décroissant", "D": "Il n'y a aucun lien"},
            "correct_answer": "B",
            "explanation": "Mathématiquement, lorsque le coût moyen est à son minimum, il est égal au coût marginal. C'est le point d'efficience productive.",
            "graph_data": {"x": [1,2,3,4,5], "y": [10, 8, 5, 8, 12], "xlabel": "Quantité (Q)", "ylabel": "Coûts (€)", "title": "Courbe de Coût Moyen"}
        },
        {
            "question": "Élasticité-Prix : Si le prix du bien X augmente de 10% et que la demande chute de 20%, quelle est l'élasticité ?",
            "options": {"A": "-0.5 (Inélastique)", "B": "-2.0 (Élastique)", "C": "-1.0 (Unitaire)", "D": "0 (Rigide)"},
            "correct_answer": "B",
            "explanation": "Élasticité = Variation % Q / Variation % P = -20% / +10% = -2.0. La valeur absolue est > 1, donc la demande est élastique.",
            "graph_data": None
        },
        {
            "question": "Marché Concurrentiel : Que se passe-t-il graphiquement si l'Offre augmente (déplacement vers la droite) alors que la Demande reste stable ?",
            "options": {"A": "Prix augmente, Quantité baisse", "B": "Prix baisse, Quantité augmente", "C": "Prix et Quantité augmentent", "D": "Prix et Quantité baissent"},
            "correct_answer": "B",
            "explanation": "Une hausse de l'offre crée un excédent au prix initial, poussant le prix à la baisse jusqu'à un nouvel équilibre avec une quantité plus élevée.",
            "graph_data": {"x": [1, 2, 3, 4], "y": [1, 2, 3, 4], "xlabel": "Q", "ylabel": "P", "title": "Offre et Demande (Simulé)"}
        }
    ]

def render_graph(data):
    if not data: return
    fig, ax = plt.subplots(figsize=(6, 3))
    plt.style.use('dark_background')
    ax.plot(data['x'], data['y'], marker='o', linestyle='-', color='#4fa8d1', linewidth=2)
    ax.set_xlabel(data.get('xlabel', 'X'))
    ax.set_ylabel(data.get('ylabel', 'Y'))
    ax.set_title(data.get('title', 'Graphique'))
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)

# --- APPLICATION ---
def main():
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False
    
    # LOGIN
    if not st.session_state.logged_in:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title("🧪 Connexion (Mode Démo)")
            st.info("Ceci est une version SANS CLÉ API pour tester l'interface.")
            tab1, tab2 = st.tabs(["Connexion", "Créer Compte"])
            with tab1:
                u = st.text_input("User")
                p = st.text_input("Pass", type="password")
                if st.button("Go"):
                    if check_login(u,p): 
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.rerun()
                    else: st.error("Erreur")
            with tab2:
                nu = st.text_input("New User")
                np = st.text_input("New Pass", type="password")
                if st.button("Créer"):
                    if create_user(nu,np): st.success("Créé !")
                    else: st.error("Pris")
        return

    # INTERFACE PRINCIPALE
    with st.sidebar:
        st.write(f"👤 **{st.session_state.username}**")
        if st.button("Déconnexion"): st.session_state.logged_in = False; st.rerun()
        st.divider()
        st.warning("⚠️ MODE DÉMO ACTIF\nL'IA est simulée. La clé API n'est pas requise.")

    st.title("🎓 Simulateur d'Examen (Simulation)")
    
    tab1, tab2 = st.tabs(["📝 Quiz", "📊 Notes"])

    with tab1:
        if 'quiz_mode' not in st.session_state or st.session_state.quiz_mode == 'inactive':
            st.subheader("Générer un faux examen pour tester")
            st.write("Clique ci-dessous pour voir comment le site réagit (graphiques, timer, notation).")
            if st.button("🚀 Lancer la Simulation", type="primary"):
                with st.spinner("L'IA (simulée) prépare le sujet..."):
                    st.session_state.quiz_data = generate_fake_quiz()
                    st.session_state.quiz_mode = "active"
                    st.session_state.score = 0
                    st.session_state.idx = 0
                    st.session_state.ans = {}
                    st.session_state.start_time = time.time()
                    st.session_state.duration = 600 # 10 minutes
                    st.rerun()

        else:
            # MODE QUIZ
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
                if q['graph_data']: render_graph(q['graph_data'])
                
                ops = q['options']
                r = st.radio("Réponse", list(ops.keys()), format_func=lambda x: f"{x}) {ops[x]}", key=f"q{i}")
                
                if st.button("Valider"):
                    st.session_state.ans[i] = {"u": r, "c": q['correct_answer'], "e": q['explanation'], "q": q['question']}
                    if r == q['correct_answer']: st.session_state.score += 1
                    st.session_state.idx += 1
                    st.rerun()
            else:
                st.balloons()
                st.markdown(f"# Note : {st.session_state.score}/{len(qs)}")
                save_hist(st.session_state.username, "Simulation Éco", st.session_state.score, len(qs), st.session_state.ans)
                st.success("Sauvegardé dans l'historique !")
                if st.button("Quitter"):
                    st.session_state.quiz_mode = "inactive"
                    st.rerun()

    with tab2:
        df = get_hist(st.session_state.username)
        if not df.empty: st.dataframe(df[['date', 'course_name', 'score']])
        else: st.info("Historique vide")

if __name__ == "__main__":
    main()
