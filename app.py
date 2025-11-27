import streamlit as st
import google.generativeai as genai
import json
import time
import pandas as pd
import matplotlib.pyplot as plt
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION STYLE & PAGE ---
st.set_page_config(page_title="Gemini Exam Sim", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .stButton>button {
        background-color: #2e4a9e;
        color: white;
        border-radius: 8px;
        border: none;
    }
    .stRadio {
        background-color: #161b22;
        padding: 20px;
        border-radius: 10px;
    }
    .timer-box {
        font-size: 24px;
        font-weight: bold;
        padding: 10px;
        border-radius: 5px;
        text-align: center;
        margin-bottom: 20px;
    }
    .timer-normal {
        color: #00ff00;
        border: 1px solid #00ff00;
    }
    .timer-alert {
        color: #ff0000;
        border: 2px solid #ff0000;
        animation: blinker 1s linear infinite;
    }
    @keyframes blinker {
        50% { opacity: 0; }
    }
</style>
""", unsafe_allow_html=True)

# --- FONCTIONS D'EXTRACTION ---

def extract_text_from_file(uploaded_file):
    """Lit un fichier texte uploadé"""
    if uploaded_file is None:
        return ""
    try:
        return uploaded_file.getvalue().decode("utf-8")
    except Exception as e:
        return f"Erreur de lecture : {e}"

def extract_text_from_url(url):
    """Aspire le texte d'une page web"""
    if not url:
        return ""
    try:
        # On se fait passer pour un navigateur pour éviter les blocages basiques
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # On prend tous les paragraphes et les titres
            paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])
            text = ' '.join([p.get_text() for p in paragraphs])
            return text
        else:
            return f"Erreur : Impossible d'accéder au site (Code {response.status_code})"
    except Exception as e:
        return f"Erreur de scraping : {e}"

# --- FONCTIONS GÉNÉRATION & AFFICHAGE ---

def generate_quiz_data(topic_text, num_questions, include_graphs=True):
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    graph_instruction = ""
    if include_graphs:
        graph_instruction = """
        Pour 30% des questions, inclus un champ 'graph_data' contenant des points (x, y) 
        pour tracer une courbe économique simple (ex: offre/demande, coût marginal).
        Structure: {"x": [1,2,3], "y": [10,20,30], "xlabel": "Qté", "ylabel": "Prix", "title": "..."}
        La question doit nécessiter la lecture de ce graphe.
        """

    prompt = f"""
    Tu es un créateur d'examen universitaire expert.
    Basé sur le contenu suivant (qui peut être brut issu du web) : 
    ---
    {topic_text[:20000]} 
    ---
    (Note: Ignore les menus de navigation ou pieds de page si c'est du web).
    
    Génère un examen de {num_questions} questions au format JSON STRICT.
    Il ne doit y avoir QUE du JSON, pas de texte avant ou après.
    
    Format attendu :
    [
        {{
            "id": 1,
            "question": "L'énoncé de la question...",
            "options": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}},
            "correct_answer": "A",
            "explanation": "L'explication détaillée...",
            "graph_data": nullOrObject
        }}
    ]
    
    {graph_instruction}
    """
    
    try:
        response = model.generate_content(prompt)
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"Erreur de génération IA : {e}")
        return []

def render_graph(data):
    if not data:
        return
    fig, ax = plt.subplots(figsize=(6, 4))
    plt.style.use('dark_background')
    ax.plot(data['x'], data['y'], marker='o', linestyle='-', color='#4fa8d1', linewidth=2)
    ax.set_xlabel(data.get('xlabel', 'X'))
    ax.set_ylabel(data.get('ylabel', 'Y'))
    ax.set_title(data.get('title', 'Graphique'))
    ax.grid(True, alpha=0.3)
    st.pyplot(fig)

# --- APPLICATION ---

def main():
    st.title("🎓 Gemini Exam Simulator 2.0")

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Configuration")
        api_key = st.text_input("Clé API Gemini", type="password")
        if api_key:
            genai.configure(api_key=api_key)

        st.divider()
        st.subheader("📂 Source du cours")
        
        # SÉLECTEUR DE SOURCE (NOUVEAU)
        source_type = st.radio("Je veux charger :", ["Un fichier texte (.txt)", "Un lien Web (URL)"])
        
        course_text = ""
        
        if source_type == "Un fichier texte (.txt)":
            uploaded_file = st.file_uploader("Upload ton fichier", type=['txt'])
            if uploaded_file:
                course_text = extract_text_from_file(uploaded_file)
        else:
            url_input = st.text_input("Colle l'URL ici (ex: Wikipedia, Article)")
            if url_input:
                with st.spinner("Lecture du site web..."):
                    course_text = extract_text_from_url(url_input)
                    if len(course_text) > 100:
                        st.success("✅ Site lu avec succès !")
                    else:
                        st.warning("⚠️ Attention : Peu de texte trouvé sur cette page.")
        
        st.divider()
        st.subheader("⏱️ Paramètres du Test")
        mode = st.radio("Type d'épreuve", ["Entraînement Chapitre", "Examen Final (Simulé)"])
        
        if mode == "Entraînement Chapitre":
            num_q = st.slider("Questions", 5, 15, 8)
            time_limit = st.slider("Minutes", 10, 60, 30)
        else:
            num_q = st.number_input("Questions", min_value=10, max_value=100, value=70)
            time_limit = st.number_input("Heures", 1, 4, 3) * 60

        if st.button("🚀 LANCER L'EXAMEN", type="primary"):
            if not api_key:
                st.warning("Il manque la clé API !")
            elif len(course_text) < 50:
                st.warning("Pas assez de contenu trouvé (fichier vide ou URL protégée).")
            else:
                with st.spinner("Génération de l'examen..."):
                    quiz_data = generate_quiz_data(course_text, num_q, include_graphs=True)
                    if quiz_data:
                        st.session_state.quiz_data = quiz_data
                        st.session_state.current_index = 0
                        st.session_state.score = 0
                        st.session_state.start_time = time.time()
                        st.session_state.total_time_seconds = time_limit * 60
                        st.session_state.user_answers = {}
                        st.session_state.quiz_active = True
                        st.rerun()

    # --- QUIZ LOGIC ---
    if 'quiz_active' in st.session_state and st.session_state.quiz_active:
        
        # GESTION TEMPS
        elapsed = time.time() - st.session_state.start_time
        remaining = st.session_state.total_time_seconds - elapsed
        mins, secs = divmod(int(remaining), 60)
        timer_text = f"{mins:02d}:{secs:02d}"
        
        timer_class = "timer-normal"
        if remaining < 0:
            timer_class = "timer-alert"
            timer_text = f"RETARD: {timer_text}"
        elif remaining < 600:
            timer_class = "timer-alert"
            
        st.markdown(f'<div class="timer-box {timer_class}">⏳ {timer_text}</div>', unsafe_allow_html=True)

        # AFFICHAGE QUESTION
        questions = st.session_state.quiz_data
        idx = st.session_state.current_index
        
        if idx < len(questions):
            q_data = questions[idx]
            st.progress((idx) / len(questions), text=f"Question {idx + 1}/{len(questions)}")
            
            st.markdown(f"### {q_data['question']}")
            
            if q_data.get('graph_data'):
                st.info("📊 Analyse le graphique ci-dessous :")
                render_graph(q_data['graph_data'])
            
            options = q_data['options']
            choice = st.radio(
                "Ta réponse :",
                list(options.keys()),
                format_func=lambda x: f"{x}) {options[x]}",
                key=f"q_{idx}"
            )
            
            if st.button("Valider et Suivant ➡️"):
                st.session_state.user_answers[idx] = {
                    "user": choice,
                    "correct": q_data['correct_answer'],
                    "explanation": q_data['explanation']
                }
                if choice == q_data['correct_answer']:
                    st.session_state.score += 1
                st.session_state.current_index += 1
                st.rerun()
                
        else:
            # RÉSULTATS
            st.session_state.quiz_active = False
            st.balloons()
            final_score = st.session_state.score
            total = len(questions)
            note = round((final_score / total) * 10, 1)
            
            st.markdown(f"# 🏁 Note Finale : {note}/10")
            
            with st.expander("Voir le corrigé détaillé", expanded=True):
                for i, q in enumerate(questions):
                    ans = st.session_state.user_answers.get(i)
                    is_correct = ans['user'] == ans['correct']
                    color = "green" if is_correct else "red"
                    st.markdown(f"**Q{i+1}: {q['question']}**")
                    st.markdown(f":{color}[Ton choix: {ans['user']} | Bonne réponse: {ans['correct']}]")
                    st.info(f"💡 {ans['explanation']}")
                    st.divider()

            if st.button("Recommencer"):
                del st.session_state.quiz_active
                st.rerun()

    else:
        st.info("👈 Colle un lien URL ou charge un fichier pour commencer.")

if __name__ == "__main__":
    main()
