import streamlit as st
import requests
import json

st.set_page_config(page_title="Test Direct API", page_icon="🕵️")

st.title("🕵️ Test Direct de l'API (Sans intermédiaire)")
st.warning("Ce test contourne la librairie Python pour interroger Google directement.")

# 1. On récupère la clé
api_key = st.text_input("Colle ta clé API (AIza...)", type="password")

if st.button("Lancer le test ULTIME"):
    if not api_key:
        st.error("Il manque la clé.")
    else:
        # 2. L'adresse directe des serveurs Google
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        # 3. Le message qu'on envoie
        payload = {
            "contents": [{
                "parts": [{"text": "Si tu reçois ce message, réponds juste par le mot BRAVO."}]
            }]
        }
        headers = {'Content-Type': 'application/json'}

        try:
            with st.spinner("Envoi de la requête directe..."):
                # On envoie la requête POST (comme un formulaire web)
                response = requests.post(url, headers=headers, json=payload)
            
            # 4. ANALYSE DU RÉSULTAT
            if response.status_code == 200:
                st.balloons()
                st.success("✅ CA FONCTIONNE ! La clé est valide.")
                data = response.json()
                try:
                    texte_reponse = data['candidates'][0]['content']['parts'][0]['text']
                    st.info(f"Réponse de Google : {texte_reponse}")
                    st.markdown("---")
                    st.write("👉 Le problème venait donc de la librairie 'google-generativeai' ou de son installation.")
                except:
                    st.warning("Ça a marché, mais la réponse est vide (bizarre, mais la connexion est OK).")
            
            else:
                st.error(f"❌ ÉCHEC. Code d'erreur : {response.status_code}")
                st.markdown("### Voici le message d'erreur EXACT renvoyé par Google :")
                # C'est ici qu'on aura la vraie raison
                st.json(response.json())
                
        except Exception as e:
            st.error(f"Erreur technique de connexion : {e}")
