def generate_quiz_data(api_key, topic_text, num_questions):
    if not api_key: return []
    
    genai.configure(api_key=api_key)
    
    # --- STRATÉGIE INTELLIGENTE ---
    # 1. On vise le sommet : Gemini 3 Pro (Le plus intelligent)
    primary_model = 'gemini-3-pro'
    
    # 2. Le plan de secours : Gemini 2.5 Flash (Le plus rapide et 10 RPM dispo)
    fallback_model = 'gemini-2.5-flash'
    
    model = None
    used_model_name = ""

    # TENTATIVE 1 : GEMINI 3
    try:
        model = genai.GenerativeModel(primary_model)
        # On teste juste si on a le droit de lui parler (ping rapide)
        # Si ça échoue (quota dépassé ou modèle introuvable), on passe au bloc except
        model.generate_content("test", request_options={'timeout': 5}) 
        used_model_name = primary_model
    except:
        # TENTATIVE 2 : REPLI SUR GEMINI 2.5 FLASH
        try:
            model = genai.GenerativeModel(fallback_model)
            used_model_name = fallback_model
        except Exception as e:
            st.error(f"Aucun modèle ne fonctionne. Vérifie ta clé. Erreur : {e}")
            return []

    # On affiche quel cerveau est utilisé (pour que tu saches)
    if used_model_name == primary_model:
        st.toast(f"🚀 Génération avec le moteur SUPRÊME : {primary_model}", icon="🧠")
    else:
        st.toast(f"⚡ Génération avec le moteur RAPIDE : {fallback_model}", icon="⚡")

    prompt = f"""
    Agis comme un professeur universitaire expert.
    Modèle utilisé : {used_model_name}
    
    Basé sur le texte suivant : {topic_text[:25000]}
    
    Crée un examen de {num_questions} questions au format JSON STRICT.
    Il ne doit y avoir QUE du JSON. Pas de Markdown (pas de ```json ... ```).
    
    Format attendu :
    [
        {{
            "question": "Énoncé complexe...",
            "options": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}},
            "correct_answer": "A",
            "explanation": "Explication détaillée..."
        }}
    ]
    """
    
    try:
        response = model.generate_content(prompt)
        # Nettoyage agressif du texte pour éviter les bugs JSON
        clean_json = response.text.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:]
        if clean_json.startswith("```"):
            clean_json = clean_json[3:]
        if clean_json.endswith("```"):
            clean_json = clean_json[:-3]
            
        return json.loads(clean_json.strip())
    except Exception as e:
        st.error(f"Erreur de génération ({used_model_name}) : {e}")
        return []
