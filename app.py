import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# 1. KONFIGURACJA STRONY W PRZEGLĄDARCE
st.set_page_config(
    page_title="Handover Hub",
    page_icon="📋",
    layout="wide"
)

# 2. BLOKADA HASŁEM
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
st.subheader("Wszystkie kluczowe tematy i linki na czas urlopu.")
st.divider()

# 4. NAWIĄZANIE POŁĄCZENIA Z GOOGLE SHEETS
conn = st.connection("gsheets", type=GSheetsConnection)

NAZWA_ZAKLADKI_ZADANIA = "Arkusz1" 
NAZWA_ZAKLADKI_LINKI = "Linki"

try:
    # Pobieranie zadań
    df_tasks = conn.read(worksheet=NAZWA_ZAKLADKI_ZADANIA, ttl=0)
    df_tasks = df_tasks.dropna(subset=["Temat", "Zadanie"]) 
    
    # Pobieranie linków
    df_links = conn.read(worksheet=NAZWA_ZAKLADKI_LINKI, ttl=0)
    df_links = df_links.dropna(how="all") # Usuwa wiersze, które są całkowicie puste
except Exception as e:
    st.error(f"⚠️ Błąd połączenia z arkuszem Google Sheets: {e}")
    st.stop()

# 5. STRUKTURA ZAKŁADEK
lista_tematow = sorted(df_tasks["Temat"].unique().tolist())
# Dodajemy moduł linków na początku
nazwy_zakladek = ["🚨 PODSUMOWANIE", "🔗 WAŻNE LINKI"] + lista_tematow

zakladki = st.tabs(nazwy_zakladek)

# --- ZAKŁADKA 0: PODSUMOWANIE ---
with zakladki[0]:
    st.header("Metryki i Statystyki")
    col1, col2, col3 = st.columns(3)
    col1.metric("Wszystkie zadania", len(df_tasks))
    col2.metric("W trakcie realizacji", len(df_tasks[df_tasks["Status"] == "W trakcie"]))
    col3.metric("Oczekujące (Do zrobienia)", len(df_tasks[df_tasks["Status"] == "Do zrobienia"]))
    
    st.markdown("""
    ### 📅 Jak korzystać z aplikacji:
    1. Każdy ważny temat ma powyżej **swoją własną zakładkę**.
    2. W zakładce **WAŻNE LINKI** znajdziesz i dodasz dostępy do innych systemów.
    3. Edytuj tabele i zawsze pamiętaj o kliknięciu **Zapisz zmiany**.
    """)

# --- ZAKŁADKA 1: MODUŁ WAŻNYCH LINKÓW (CRUD) ---
with zakladki[1]:
    st.header("🔗 Baza ważnych linków")
    st.write("Tutaj możesz dodawać nowe systemy, linki do bookowania slotów i inne narzędzia. Aby dodać wiersz, zjedź na dół tabeli. Aby usunąć, zaznacz wiersz po lewej stronie i naciśnij `Delete` na klawiaturze (lub ikonę kosza na telefonie).")
    
    # Edytor z funkcją num_rows="dynamic" pozwala na dodawanie i usuwanie wierszy!
    edytowane_linki = st.data_editor(
        df_links,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "URL": st.column_config.LinkColumn(
                "Link docelowy (URL)",
                help="Wklej pełny adres, np. https://...",
                max_chars=200
            )
        },
        key="editor_linki"
    )
    
    # Zapisywanie linków do arkusza "Linki"
    if st.button("💾 Zapisz zmiany w linkach", type="primary"):
        with st.spinner("Aktualizowanie bazy linków..."):
            conn.update(worksheet=NAZWA_ZAKLADKI_LINKI, data=edytowane_linki)
            st.cache_data.clear()
            st.success("✅ Baza linków została zaktualizowana!")
            st.rerun()

# --- POZOSTAŁE ZAKŁADKI TEMATYCZNE Z ZADANIAMI ---
for i, temat in enumerate(lista_tematow):
    # i+2 ponieważ mamy już dwie stałe zakładki (Podsumowanie i Linki)
    with zakladki[i+2]:
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
        
        if st.button(f"Zapisz zmiany w: {temat}", type="primary"):
            with st.spinner("Zapisywanie..."):
                for col in edytowane_dane.columns:
                    df_tasks.loc[idx_tematu, col] = edytowane_dane[col].values
                
                conn.update(worksheet=NAZWA_ZAKLADKI_ZADANIA, data=df_tasks)
                
                st.cache_data.clear()
                st.success("✅ Zmiany pomyślnie zapisane!")
                st.rerun()

# 6. STAŁY PANEL BOCZNY
with st.sidebar:
    st.header("☎️ Sytuacje Awaryjne")
    st.error("**JEŚLI COŚ SIĘ PALI:**\n\n1. Kontaktuj się z Janem (Zastępca): +48 999 888 777.\n2. Do mnie dzwoń tylko, jeśli sytuacja jest krytyczna.")
