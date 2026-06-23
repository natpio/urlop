import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# 1. KONFIGURACJA STRONY W PRZEGLĄDARCE
st.set_page_config(
    page_title="Handover Hub",
    page_icon="📋",
    layout="wide"
)

# 2. BLOKADA HASŁEM (Wpisz swoje hasło dla zespołu)
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 Dostęp zablokowany")
    password = st.text_input("Podaj hasło zespołu, aby zobaczyć przekazanie obowiązków:", type="password")
    if password == "Urlop2026":  # <-- TUTAJ WPISZ SWOJE HASŁO
        st.session_state["authenticated"] = True
        st.rerun()
    elif password:
        st.error("❌ Nieprawidłowe hasło!")
    st.stop()

# 3. TYTUŁ I NAGŁÓWEK
st.title("📋 Handover Hub – Centrum Przekazania Obowiązków")
st.subheader("Wszystkie kluczowe tematy, notatki i zadania na czas urlopu.")
st.divider()

# 4. POBIERANIE DANYCH Z GOOGLE SHEETS
# Aplikacja spróbuje połączyć się z Twoim arkuszem. Jeśli jeszcze go nie podepniesz, wyświetli dane demonstracyjne.
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Czytamy dane (domyślnie z pierwszej zakładki arkusza)
    df_tasks = conn.read()
    
    # Czyszczenie pustych wierszy
    df_tasks = df_tasks.dropna(subset=["Temat", "Zadanie"])
except Exception as e:
    st.warning("⚠️ Brak połączenia z prawdziwym Google Sheets (lub błędny link). Wyświetlam dane demonstracyjne.")
    # Dane demonstracyjne pokazujące strukturę tabeli, jakiej oczekuje aplikacja:
    df_tasks = pd.DataFrame([
        {"Temat": "🎪 Event: Targi Poznań", "Zadanie": "Opłacenie faktury za stoisko", "Osoba": "Anna", "Termin": "2026-06-25", "Status": "Do zrobienia", "Notatki": "Kontakt do organizatora: p. Kryspin. Faktura jest na Dysku Google."},
        {"Temat": "🎪 Event: Targi Poznań", "Zadanie": "Wysyłka katalogów kurierem", "Osoba": "Jan", "Termin": "2026-06-28", "Status": "W trakcie", "Notatki": "Materiały spakowane leżą w sekcji B magazynu."},
        {"Temat": "🚀 Projekt: Klient XYZ", "Zadanie": "Odprawa celna kontenera", "Osoba": "Anna", "Termin": "2026-07-02", "Status": "Do zrobienia", "Notatki": "Agencja celna ma dokumenty. W razie problemów dzwonić do p. Marka."},
        {"Temat": "📦 Logistyka Magazynowa", "Zadanie": "Przegląd wózka widłowego", "Osoba": "Tomasz", "Termin": "2026-07-05", "Status": "Zrobione", "Notatki": "Wózek nr 2 jedzie do serwisu w środę od rana."}
    ])

# 5. DYNAMICZNE ZAKŁADKI (DLA KAŻDEGO EVENTU / TEMATU OSOBNA)
# Wyciągamy listę unikalnych tematów z tabeli
lista_tematow = sorted(df_tasks["Temat"].unique().tolist())
nazwy_zakladek = ["🚨 GŁÓWNE PRIORYTETY"] + lista_tematow

# Tworzenie zakładek na stronie internetowej
zakladki = st.tabs(nazwy_zakladek)

# --- Zakładka Ogólna ---
with zakladki[0]:
    st.header("🚨 Statystyki i instrukcja ogólna")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Wszystkie zadania", len(df_tasks))
    col2.metric("W trakcie realizacji", len(df_tasks[df_tasks["Status"] == "W trakcie"]))
    col3.metric("Oczekujące (Do zrobienia)", len(df_tasks[df_tasks["Status"] == "Do zrobienia"]))
    
    st.markdown("""
    ### 📅 Jak korzystać z aplikacji:
    1. Każdy ważny temat (np. konkretny event lub projekt) ma powyżej **swoją własną, dedykowaną zakładkę**.
    2. Kliknij w zakładkę wybranego eventu, aby zobaczyć powiązane z nim **notatki, wytyczne i listę zadań**.
    3. Wszelkie aktualizacje wprowadzaj bezpośrednio w pliku Google Sheets – ta strona odświeży się automatycznie.
    """)

# --- Dynamiczne Zakładki Tematyczne ---
for i, temat in enumerate(lista_tematow):
    with zakladki[i+1]:
        st.header(f"Zarządzanie tematem: {temat}")
        
        # Filtrujemy wiersze tylko dla tego konkretnego eventu/tematu
        df_filtrowane = df_tasks[df_tasks["Temat"] == temat][["Zadanie", "Osoba", "Termin", "Status", "Notatki"]]
        
        # Wyświetlamy zadania w postaci przejrzystej tabeli
        st.subheader("📋 Lista obowiązków i notatek szczegółowych:")
        st.dataframe(df_filtrowane, use_container_width=True, hide_index=True)

# 6. STAŁY PANEL BOCZNY (SIDEBAR) Z KONTAKTAMI ALARMOWYMI
with st.sidebar:
    st.header("☎️ Sytuacje Awaryjne")
    st.error("**JEŚLI COŚ SIĘ PALI:**\n\n1. Kontaktuj się z Janem (Zastępca): +48 999 888 777.\n2. Do mnie dzwoń tylko, jeśli stoi transport lub produkcja.")
    st.divider()
    st.markdown("📂 **Ważne Linki:**")
    st.markdown("[📁 Dysk Google - Folder Główny](https://drive.google.com)")
