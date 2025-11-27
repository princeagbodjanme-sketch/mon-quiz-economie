import streamlit as st
import google.generativeai as genai

st.title("🔧 Outil de Diagnostic API Gemini")

st.info("Ce petit site sert juste à tester si ta clé fonctionne.")

# Zone pour coller la clé
api_key = st.text_input("Colle ta clé API ici :", type="password")

if st.button("Lancer le test"):
    if not api_key:
        st.warning("Il faut coller une clé d'abord !")
    else:
        try:
            # 1. On configure
            genai.configure(api_key=api_key)
            
            # 2. On essaie de parler au modèle
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content("Dis juste 'OK' si tu me reçois.")
            
            # 3. Si on arrive ici, c'est que ça marche
            st.success("✅ VICTOIRE ! Ta clé fonctionne parfaitement.")
            st.write(f"Réponse de Gemini : {response.text}")
            st.markdown("---")
            st.write("👉 Tu peux maintenant remettre le code complet de l'application dans GitHub.")
            
        except Exception as e:
            # 4. Si ça plante, on affiche l'erreur exacte
            st.error("❌ ÉCHEC. La clé ne marche pas.")
            st.code(f"Message d'erreur technique : {e}")
            
            # Aide au diagnostic
            erreur_str = str(e)
            if "400" in erreur_str:
                st.warning("💡 Indice : Vérifie que tu n'as pas copié d'espace en trop avant ou après la clé.")
            elif "403" in erreur_str:
                st.warning("💡 Indice : Tu n'as peut-être pas les droits ou c'est une clé Google Cloud au lieu de AI Studio.")
            elif "location" in erreur_str:
                st.warning("💡 Indice : Problème de localisation (VPN ?).")
