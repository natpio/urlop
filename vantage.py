import streamlit as st
import streamlit.components.v1 as components

def render_vantage():
    # Elegancki baner nagłówkowy w stylu naszej aplikacji
    st.markdown("""
        <div class="aviation-banner" style="background: linear-gradient(135deg, #030508 0%, #1e293b 100%); border-left: 8px solid #ed8936; margin-bottom: 10px;">
            <h1 style="color:white; margin:0;">📊 VANTAGE INTELLIGENCE</h1>
            <p style="color:#cbd5e1; margin:0;">Kalkulator stawek, postojów i rentowności tras.</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Próba wczytania Twojego pliku HTML
    try:
        with open("pricelist.html", "r", encoding="utf-8") as f:
            html_data = f.read()
        
        # Wyświetlenie HTMLa bezpośrednio w Streamlit (wysokość 850px, żeby uniknąć ucięcia)
        components.html(html_data, height=850, scrolling=False)
        
    except FileNotFoundError:
        st.error("⚠️ Nie znaleziono pliku 'pricelist.html'. Upewnij się, że wgrałeś go na GitHub.")
