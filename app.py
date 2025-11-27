import streamlit as st
import google.generativeai as genai

# Configuration de la page
st.set_page_config(page_title="Mon Super Quiz Gemini", page_icon="🎓")

st.title("🎓 Révise ton Exam avec Gemini")

# Barre latérale pour la configuration
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("Ta clé API Gemini", type="password")
    topic = st.text_area("Sujet de l'examen ou notes de cours", height=150)
    
    if api_key:
        genai.configure(api_key=api_key)

# Initialisation de l'état (mémoire de l'app)
if 'question' not in st.session_state:
    st.session_state.question = None
if 'feedback' not in st.session_state:
    st.session_state.feedback = None

def generate_question():
    if not api_key or not topic:
        st.error("Merci d'entrer une clé API et un sujet.")
        return
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    # On demande à Gemini de générer une question
    prompt = f"Tu es un professeur expert. Basé sur le sujet suivant : '{topic}', pose-moi une question d'examen difficile et précise. Ne donne pas la réponse."
    response = model.generate_content(prompt)
    st.session_state.question = response.text
    st.session_state.feedback = None # Reset du feedback

def check_answer(user_answer):
    model = genai.GenerativeModel('gemini-1.5-flash')
    # On demande à Gemini de corriger
    prompt = f"""
    Sujet: {topic}
    Question posée: {st.session_state.question}
    Réponse de l'étudiant: {user_answer}
    
    Tâche : Agis comme un correcteur bienveillant mais rigoureux.
    1. Note la réponse sur 10.
    2. Indique si c'est correct ou non.
    3. Donne la réponse complète et détaillée.
    """
    response = model.generate_content(prompt)
    st.session_state.feedback = response.text

# Interface principale
if st.button("Générer une nouvelle question"):
    generate_question()

if st.session_state.question:
    st.info(f"❓ **Question :** {st.session_state.question}")
    
    user_answer = st.text_area("Ta réponse :")
    
    if st.button("Envoyer la réponse"):
        if user_answer:
            with st.spinner('Gemini corrige ta copie...'):
                check_answer(user_answer)
        else:
            st.warning("Écris une réponse avant d'envoyer !")

if st.session_state.feedback:
    st.success("✅ **Correction :**")
    st.markdown(st.session_state.feedback)
