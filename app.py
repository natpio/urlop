import streamlit as st
import pandas as pd

# Konfiguracja strony
st.set_page_config(
    page_title="Handover Hub - Urlop",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 1. PROSTE ZABEZPIECZENIE HASŁEM (Opcjonalne)
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
        
    if st.session_state["password_correct"]:
        return True

    st.title("🔒 Dostęp zablokowany")
    password = st.text_input("Podaj hasło zespołu, aby zobaczyć przekazanie obowiązków:", type="password")
    if password == "Urlop2026":  # Tutaj wpisz swoje hasło
        st.session_state["password_correct"] = True
        st.rerun()
    elif password:
        st.error("❌ Nieprawidłowe hasło!")
    return False

if not check_password():
    st.stop()

# 2. POŁĄCZENIE Z GOOGLE SHEETS (INSTRUKCJA)
# W produkcyjnej wersji odkomentuj poniższe linie, aby czytać dane na żywo z Google Sheets:
# from streamlit_gsheets import GSheetsConnection
# conn = st.connection("gsheets", type=GSheetsConnection)
# df_tasks = conn.read(worksheet="Zadania")

# T營MCZASOWE DANE PRZYKŁADOWE (Symulacja danych z Google Sheets)
@st.cache_data
def load_mock_data():
    tasks = pd.DataFrame([
        {"Temat": "🎪 Event: Targi Poznań", "Zadanie": "Opłacenie faktury za stoisko", "Osoba": "Anna", "Termin": "2026-06-25", "Status": "Do zrobienia", "Notatki": "Faktura jest na Dysku Google w folderze Targi/Finanse."},
        {"Temat": "🎪 Event: Targi Poznań", "Zadanie": "Koordynacja kuriera z materiałami", "Osoba": "Jan", "Termin": "2026-06-28", "Status": "W trakcie", "Notatki": "Kurier DHL, nr zlecenia w bazie wiedzy."},
        {"Temat": "🚀 Projekt: Wysyłka XYZ", "Zadanie": "Odprawa celna kontenera", "Osoba": "Anna", "Termin": "2026-07-02", "Status": "Do zrobienia", "Notatki": "Agencja celna ma wszystkie dokumenty. W razie problemów dzwonić do p. Marka."},
        {"Temat": "📦 Logistyka Magazynowa", "Zadanie": "Inwentaryzacja palet zwrotnych", "Osoba": "Tomasz", "Termin": "2026-07-05", "Status": "Zrobione", "Notatki": "Zrobione wcześniej, raport w arkuszu głównym."}
    ])
    
    notes = {
        "🎪 Event: Targi Poznań": "Kontakt do organizatora: +48 123 456 789 (p. Kryspin). Wszystkie wejściówki są na mailu biurowym.",
        "🚀 Projekt: Wysyłka XYZ": "Kluczowy klient. Jeśli zgłosi reklamację, od razu eskalować do Dyrektora.",
        "📦 Logistyka Magazynowa": "Wózek widłowy nr 2 jedzie na przegląd w środę. Zastępczy będzie od rana."
    }
    return tasks, notes

df_tasks, dict_notes = load_mock_data()


# 3. GŁÓWNY INTERFEJS APLIKACJI
st.title("📋 Handover Hub – Centrum Przekazania Obowiązków")
st.subheader("Wszystkie kluczowe tematy i zadania na czas mojego urlopu w jednym miejscu.")
st.divider()

# Wyciągamy unikalne tematy (np. eventy), które posłużą jako nazwy zakładek
lista_tematow = sorted(df_tasks["Temat"].unique().tolist())
# Dodajemy na początek stałą zakładkę z ogólnym podsumowaniem
nazwy_zakladek = ["🚨 GŁÓWNE PRIORYTETY"] + lista_tematow

# Tworzenie dynamicznych zakładek w Streamlit
zakladki = st.tabs(nazwy_zakladek)

# --- ZAKŁADKA 1: OGÓLNE PRIORYTETY ---
with zakladki[0]:
    st.header("🚨 Najważniejsze wskaźniki i zadania na ten tydzień")
    
    # Metryki na górze strony
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Wszystkie zadania", len(df_tasks))
    with col2:
        st.metric("W trakcie realizacji", len(df_tasks[df_tasks["Status"] == "W trakcie"]))
    with col3:
        st.metric("Do zrobienia", len(df_tasks[df_tasks["Status"] == "Do zrobienia"]))
        
    st.markdown("""
    ### 📅 Instrukcja ogólna:
    1. Przejrzyj dedykowaną zakładkę dla danego eventu/projektu.
    2. W każdej zakładce znajdziesz **notatki strategiczne** oraz **listę konkretnych zadań**.
    3. Pilne awarie zgłaszajcie zgodnie z listą kontaktów alarmowych w sekcji bocznej.
    """)
    
    st.info("💡 Wszystkie dane w zakładkach pochodzą bezpośrednio z arkusza Google Sheets. Zmiana statusu w arkuszu automatycznie odświeży tę stronę.")

# --- DYNAMICZNE ZAKŁADKI DLA KAŻDEGO TEMATU/EVENTU ---
for i, temat in enumerate(lista_tematow):
    # i+1 ponieważ indeks 0 to zakładka ogólna
    with zakladki[i+1]:
        st.header(f"Zarządzanie: {temat}")
        
        # Sekcja z notatkami i opisem (Wymieniane przez Ciebie kluczowe notatki)
        st.subheader("🧠 Moje notatki i wytyczne:")
        opis_tematu = dict_notes.get(temat, "Brak dodatkowych notatek dla tego tematu.")
        st.info(opis_tematu)
        
        # Filtrowanie tabeli zadań tylko dla tego konkretnego tematu
        df_filtrowane = df_tasks[df_tasks["Temat"] == temat][["Zadanie", "Osoba", "Termin", "Status", "Notatki"]]
        
        st.subheader("✅ Lista zadań i obowiązków:")
        
        # Interaktywne filtry wewnątrz zakładki (np. po osobie lub statusie)
        wybrana_osoba = st.selectbox(f"Filtruj po osobie ({temat}):", ["Wszyscy"] + df_filtrowane["Osoba"].unique().tolist(), key=f"user_{temat}")
        
        if wybrana_osoba != "Wszyscy":
            df_filtrowane = df_filtrowane[df_filtrowane["Osoba"] == wybrana_osoba]
            
        # Wyświetlenie tabeli w ładnej formie
        st.dataframe(
            df_filtrowane, 
            use_container_width=True,
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Do zrobienia", "W trakcie", "Zrobione"],
                    required=True,
                )
            }
        )

# 4. PASEK BOCZNY (SIDEBAR) - STAŁE ELEMENTY (KRACH / KONTAKTY)
with st.sidebar:
    st.header("☎️ Sytuacje Awaryjne")
    st.error("**JEŚLI COŚ SIĘ PALI:**\n\n1. Sprawdź procedurę w zakładce.\n2. Kontaktuj się z Janem (Zastępca): +48 999 888 777.\n3. Do mnie dzwoń tylko jeśli stoi produkcja/transport.")
    
    st.divider()
    st.markdown("📂 **Przydatne Linki:**")
    st.markdown("[📁 Dysk Google - Folder Główny](https://drive.google.com)") # Tutaj wkleisz swój link do Dysku
    st.markdown("[📊 Dokumentacja Procedur](https://docs.google.com)")
