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
    
    # Sprawdzamy hasło zapisane w konfiguracji Streamlit Secrets
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
# ttl=0 oznacza, że pobieramy świeże dane przy każdym przeładowaniu strony
conn = st.connection("gsheets", type=GSheetsConnection)

# Zmień "Arkusz1" na taką nazwę zakładki, jaką masz na samym dole w swoim pliku Google Sheets
NAZWA_ZAKLADKI = "Arkusz1" 

try:
    # Odczyt danych z arkusza
    df_tasks = conn.read(worksheet=NAZWA_ZAKLADKI, ttl=0)
    # Usunięcie pustych wierszy, żeby tabela wyglądała czysto
    df_tasks = df_tasks.dropna(subset=["Temat", "Zadanie"]) 
except Exception as e:
    st.error(f"⚠️ Błąd połączenia z bazą danych: {e}")
    st.stop()

# 5. DYNAMICZNE ZAKŁADKI (DLA KAŻDEGO EVENTU / TEMATU OSOBNA)
# Wyciągamy listę unikalnych tematów z tabeli
lista_tematow = sorted(df_tasks["Temat"].unique().tolist())
nazwy_zakladek = ["🚨 PODSUMOWANIE"] + lista_tematow

# Tworzenie zakładek na stronie internetowej
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
    3. Zmiana zostanie automatycznie wysłana do zamkniętego arkusza Google Sheets.
    """)

# --- Dynamiczne Zakładki Tematyczne z funkcją EDYCJI ---
for i, temat in enumerate(lista_tematow):
    with zakladki[i+1]:
        st.header(f"Zarządzanie: {temat}")
        
        # Filtrujemy wiersze, które pasują do tego tematu i zapisujemy ich oryginalne indeksy
        idx_tematu = df_tasks.index[df_tasks["Temat"] == temat]
        df_filtrowane = df_tasks.loc[idx_tematu].copy()
        
        st.write("Edytuj statusy lub osoby w tabeli poniżej. Zmiany zostaną przesłane do arkusza głównego.")
        
        # Wyświetlamy interaktywny edytor danych
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
        
        # 6. ZAPISYWANIE DANYCH Z POWROTEM DO GOOGLE SHEETS
        if st.button(f"Zapisz zmiany w: {temat}", type="primary"):
            with st.spinner("Zapisywanie w chmurze..."):
                # Nadpisujemy główne dane zmianami z tego konkretnego tematu
                for col in edytowane_dane.columns:
                    df_tasks.loc[idx_tematu, col] = edytowane_dane[col].values
                
                # Wysyłamy cały zaktualizowany arkusz z powrotem do Google Sheets
                conn.update(worksheet=NAZWA_ZAKLADKI, data=df_tasks)
                
                # Czyścimy cache, żeby strona pobrała odświeżone dane
                st.cache_data.clear()
                st.success("✅ Zmiany pomyślnie zapisane w Google Sheets!")
                st.rerun()

# 7. STAŁY PANEL BOCZNY (SIDEBAR) Z KONTAKTAMI ALARMOWYMI
with st.sidebar:
    st.header("☎️ Sytuacje Awaryjne")
    st.error("**JEŚLI COŚ SIĘ PALI:**\n\n1. Kontaktuj się z Janem (Zastępca): +48 999 888 777.\n2. Do mnie dzwoń tylko, jeśli stoi transport lub produkcja.")
    st.divider()
    st.markdown("📂 **Ważne Linki:**")
    st.markdown("[📁 Dysk Google - Folder Główny](https://drive.google.com)")
