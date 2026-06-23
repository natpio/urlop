import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# 1. KONFIGURACJA STRONY W PRZEGLĄDARCE
st.set_page_config(
    page_title="Handover Hub",
    page_icon="📋",
    layout="wide"
)

# 2. BLOKADA HASŁEM (Pobierane bezpiecznie z Secrets)
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 Dostęp zablokowany")
    password = st.text_input("Podaj hasło zespołu, aby zobaczyć przekazanie obowiązków:", type="password")
    
    if password == st.secrets["APP_PASSWORD"]:  
        st.session_state["authenticated"] = True
        st.rerun()
    elif password:
        st.error("❌ Nieprawidłowe hasło!")
    st.stop()

# 3. TYTUŁ I NAGŁÓWEK
st.title("📋 Handover Hub – Interaktywny Panel")
st.subheader("Wszystkie kluczowe tematy na czas urlopu. Zmieniaj statusy, a zapiszą się w arkuszu.")
st.divider()

# 4. NAWIĄZANIE POŁĄCZENIA Z GOOGLE SHEETS
conn = st.connection("gsheets", type=GSheetsConnection)

# Zmień "Arkusz1" na nazwę zakładki w Twoim pliku Google Sheets (na samym dole arkusza)
NAZWA_ZAKLADKI = "Arkusz1" 

try:
    df_tasks = conn.read(worksheet=NAZWA_ZAKLADKI, ttl=0)
    df_tasks = df_tasks.dropna(subset=["Temat", "Zadanie"]) 
except Exception as e:
    st.error(f"⚠️ Błąd połączenia z arkuszem Google Sheets: {e}")
    st.stop()

# 5. DYNAMICZNE ZAKŁADKI
lista_tematow = sorted(df_tasks["Temat"].unique().tolist())
nazwy_zakladek = ["🚨 PODSUMOWANIE"] + lista_tematow

zakladki = st.tabs(nazwy_zakladek)

# --- Zakładka Podsumowania ---
with zakladki[0]:
    st.header("Metryki i Statystyki")
    col1, col2, col3 = st.columns(3)
    col1.metric("Wszystkie zadania", len(df_tasks))
    col2.metric("W trakcie realizacji", len(df_tasks[df_tasks["Status"] == "W trakcie"]))
    col3.metric("Oczekujące (Do zrobienia)", len(df_tasks[df_tasks["Status"] == "Do zrobienia"]))
    
    st.markdown("""
    ### 📅 Jak korzystać z aplikacji:
    1. Każdy ważny temat (np. konkretny event lub projekt) ma powyżej **swoją własną zakładkę**.
    2. Jeśli wykonasz zadanie, zmień jego status w odpowiedniej zakładce i kliknij **Zapisz zmiany**.
    3. Zmiana zostanie automatycznie wysłana do arkusza bazy.
    """)

# --- Dynamiczne Zakładki Tematyczne z funkcją EDYCJI ---
for i, temat in enumerate(lista_tematow):
    with zakladki[i+1]:
        st.header(f"Zarządzanie: {temat}")
        
        idx_tematu = df_tasks.index[df_tasks["Temat"] == temat]
        df_filtrowane = df_tasks.loc[idx_tematu].copy()
        
        st.write("Edytuj statusy w tabeli poniżej. Zmiany zostaną przesłane do arkusza.")
        
        edytowane_dane = st.data_editor(
            df_filtrowane,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Do zrobienia", "W trakcie", "Zrobione"],
                    required=True,
                )
            },
            key=f"editor_{temat}"
        )
        
        # 6. ZAPISYWANIE DANYCH
        if st.button(f"Zapisz zmiany w: {temat}", type="primary"):
            with st.spinner("Zapisywanie..."):
                for col in edytowane_dane.columns:
                    df_tasks.loc[idx_tematu, col] = edytowane_dane[col].values
                
                conn.update(worksheet=NAZWA_ZAKLADKI, data=df_tasks)
                
                st.cache_data.clear()
                st.success("✅ Zmiany pomyślnie zapisane!")
                st.rerun()

# 7. STAŁY PANEL BOCZNY (Tylko najpilniejsze kontakty)
with st.sidebar:
    st.header("☎️ Sytuacje Awaryjne")
    st.error("**JEŚLI COŚ SIĘ PALI:**\n\n1. Kontaktuj się z Janem (Zastępca): +48 999 888 777.\n2. Do mnie dzwoń tylko, jeśli sytuacja jest krytyczna.")
