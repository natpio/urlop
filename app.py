import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# 1. KONFIGURACJA STRONY I STYLE
st.set_page_config(page_title="Logistics Terminal", page_icon="✈️", layout="wide")

# Zaawansowany CSS - stylizacja zakładek i kart, dokładnie jak na zrzucie ekranu
st.markdown("""
    <style>
    /* Stylizacja samych kart */
    .terminal-card {
        background-color: white;
        border-left: 6px solid #00205b; /* Granatowy akcent po lewej */
        border-radius: 4px;
        padding: 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.08);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 280px; /* Stała wysokość dla wyrównania rzędów */
        margin-bottom: 20px;
    }
    .terminal-card-category {
        color: #ffa500;
        font-weight: 800;
        font-size: 11px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-bottom: 15px;
    }
    .terminal-card-title {
        color: #00205b;
        font-weight: 900;
        font-size: 20px;
        margin-bottom: 15px;
        line-height: 1.2;
    }
    .terminal-card-desc {
        color: #6b7280;
        font-size: 13px;
        font-family: monospace; /* Czcionka jak w kodzie źródłowym URL */
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 3; /* Ucięcie po 3 linijkach */
        -webkit-box-orient: vertical;
        word-break: break-all;
    }
    .terminal-card-btn {
        background-color: #ff9800;
        color: #000000 !important;
        font-weight: bold;
        text-align: center;
        text-decoration: none;
        padding: 12px;
        border-radius: 4px;
        display: block;
        width: 100%;
        transition: background-color 0.2s;
    }
    .terminal-card-btn:hover {
        background-color: #e68a00;
        text-decoration: none;
    }

    /* Stylizacja zakładek (Tabs) na wzór interfejsu */
    div[data-testid="stTabs"] button[aria-selected="true"] {
        background-color: #00205b !important;
        color: white !important;
        border-radius: 6px 6px 0 0;
        border-bottom: 3px solid #ff9800 !important;
    }
    div[data-testid="stTabs"] button[aria-selected="false"] {
        background-color: white !important;
        color: #00205b !important;
        border-radius: 6px 6px 0 0;
        border: 1px solid #e5e7eb;
        border-bottom: none;
    }
    div[data-testid="stTabs"] button p {
        font-weight: 600 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. BEZPIECZEŃSTWO
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 Zaloguj do terminala")
    password = st.text_input("Wprowadź kod dostępu:", type="password")
    
    if password == st.secrets["APP_PASSWORD"]:  
        st.session_state["authenticated"] = True
        st.rerun()
    elif password:
        st.error("❌ Odmowa dostępu. Nieprawidłowy kod.")
    st.stop()

# 3. POŁĄCZENIE Z BAZĄ
conn = st.connection("gsheets", type=GSheetsConnection)
NAZWA_ZAKLADKI_ZADANIA = "Arkusz1" 
NAZWA_ZAKLADKI_LINKI = "Linki"

try:
    df_tasks = conn.read(worksheet=NAZWA_ZAKLADKI_ZADANIA, ttl=0)
    df_tasks = df_tasks.dropna(subset=["Temat", "Zadanie"]) 
    
    df_links = conn.read(worksheet=NAZWA_ZAKLADKI_LINKI, ttl=0)
    df_links = df_links.dropna(how="all") 
    
    for col in ["Nazwa", "URL", "Opis", "Kategoria"]:
        if col not in df_links.columns:
            df_links[col] = ""
        df_links[col] = df_links[col].fillna("").astype(str)
        
except Exception as e:
    st.error(f"⚠️ Błąd połączenia z serwerem bazy danych: {e}")
    st.stop()

# 4. NAWIGACJA TERMINALA (Sidebar)
with st.sidebar:
    st.header("✈️ LOGISTICS TERMINAL")
    st.markdown("---")
    st.write("**Nawigacja terminala:**")
    
    widok = st.radio("Wybierz moduł:", [
        "🛫 Tablica Odlotów (Zadania)", 
        "🌐 Odprawa (Główny Hub)", 
        "🛠️ Hangar (Edycja Linków)"
    ], label_visibility="collapsed")
    
    st.markdown("---")
    if st.button("🔒 Zamknij bezpieczną sesję", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()

# ==========================================
# WIDOK 1: TABLICA ODLOTÓW (Moduł Zadań)
# ==========================================
if widok == "🛫 Tablica Odlotów (Zadania)":
    st.title("🛫 Tablica Odlotów – Rejestr Zadań")
    st.subheader("Zarządzanie operacjami i przydziałami w trakcie urlopu.")
    
    lista_tematow = sorted(df_tasks["Temat"].unique().tolist())
    zakladki_zadania = st.tabs(["📊 METRYKI GŁÓWNE"] + lista_tematow)

    with zakladki_zadania[0]:
        col1, col2, col3 = st.columns(3)
        col1.metric("Wszystkie operacje", len(df_tasks))
        col2.metric("W toku", len(df_tasks[df_tasks["Status"] == "W trakcie"]))
        col3.metric("Oczekujące", len(df_tasks[df_tasks["Status"] == "Do zrobienia"]))

    for i, temat in enumerate(lista_tematow):
        with zakladki_zadania[i+1]:
            idx_tematu = df_tasks.index[df_tasks["Temat"] == temat]
            df_filtrowane = df_tasks.loc[idx_tematu].copy()
            
            edytowane_dane = st.data_editor(
                df_filtrowane, use_container_width=True, hide_index=True,
                column_config={"Status": st.column_config.SelectboxColumn("Status", options=["Do zrobienia", "W trakcie", "Zrobione"], required=True)},
                key=f"editor_{temat}"
            )
            
            if st.button(f"Zapisz statusy: {temat}", type="primary"):
                with st.spinner("Synchronizacja z serwerem..."):
                    for col in edytowane_dane.columns:
                        df_tasks.loc[idx_tematu, col] = edytowane_dane[col].values
                    conn.update(worksheet=NAZWA_ZAKLADKI_ZADANIA, data=df_tasks)
                    st.cache_data.clear()
                    st.success("✅ Synchronizacja zakończona pomyślnie.")
                    st.rerun()

# ==========================================
# WIDOK 2: ODPRAWA (Wizualny Hub Linków)
# ==========================================
elif widok == "🌐 Odprawa (Główny Hub)":
    st.title("✈️ Główny Hub Nawigacyjny")
    
    szukana_fraza = st.text_input("🔍 Wyszukiwarka operacyjna (targi, portale, spedycje, awizacje):", placeholder="Wpisz szukaną frazę...")
    st.divider()
    
    if szukana_fraza:
        mask = df_links.apply(lambda row: row.astype(str).str.contains(szukana_fraza, case=False).any(), axis=1)
        df_wyswietlane = df_links[mask]
    else:
        df_wyswietlane = df_links

    kategorie = ["🌐 Cała Sieć Operacyjna"] + sorted([k for k in df_links["Kategoria"].unique() if k.strip()])
    zakladki_linki = st.tabs(kategorie)
    
    for i, kategoria in enumerate(kategorie):
        with zakladki_linki[i]:
            if i == 0:
                df_kat = df_wyswietlane
            else:
                df_kat = df_wyswietlane[df_wyswietlane["Kategoria"] == kategoria]
                
            if df_kat.empty:
                st.write("Brak systemów w tej kategorii.")
            else:
                kolumny = st.columns(3)
                for index, row in df_kat.reset_index(drop=True).iterrows():
                    with kolumny[index % 3]:
                        
                        nazwa_kat = row['Kategoria'].upper() if row['Kategoria'] else "OGÓLNE"
                        # Jeśli opis jest pusty, wyświetlamy URL (jak na Twoim zrzucie)
                        opis_tekst = row['Opis'] if row['Opis'] else row['URL']
                        url = row['URL'] if row['URL'].startswith('http') else '#'
                        
                        # Generowanie HTML dla pojedynczej karty
                        karta_html = f"""
                        <div class="terminal-card">
                            <div>
                                <div class="terminal-card-category">✈️ {nazwa_kat}</div>
                                <div class="terminal-card-title">{row['Nazwa']}</div>
                                <div class="terminal-card-desc">{opis_tekst}</div>
                            </div>
                            <a href="{url}" target="_blank" class="terminal-card-btn">Uruchom procedurę ➔</a>
                        </div>
                        """
                        # Renderowanie karty w Streamlit
                        st.markdown(karta_html, unsafe_allow_html=True)

# ==========================================
# WIDOK 3: HANGAR (Moduł CRUD dla Linków)
# ==========================================
elif widok == "🛠️ Hangar (Edycja Linków)":
    st.title("🛠️ Hangar – Modyfikacja Baz")
    st.write("W tym module możesz dodawać nowe kafelki do Głównego Huba, edytować istniejące lub je usuwać. **Zjedź na dół tabeli, aby dodać nowy wiersz.** Pamiętaj, aby na koniec kliknąć Zapisz.")
    
    edytowane_linki = st.data_editor(
        df_links,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "URL": st.column_config.LinkColumn("Adres URL", help="Wklej pełny adres zaczynając od https://"),
            "Kategoria": st.column_config.TextColumn("Kategoria", help="Na podstawie tego pola utworzą się zakładki")
        },
        key="editor_bazy_linkow"
    )
    
    if st.button("💾 Zapisz konfigurację Huba do bazy", type="primary"):
        with st.spinner("Nadpisywanie rejestru systemów..."):
            conn.update(worksheet=NAZWA_ZAKLADKI_LINKI, data=edytowane_linki)
            st.cache_data.clear()
            st.success("✅ Baza systemów została zaktualizowana!")
            st.rerun()
