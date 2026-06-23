import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# 1. KONFIGURACJA STRONY I STYLE
st.set_page_config(page_title="Logistics Terminal", page_icon="✈️", layout="wide")

# Wstrzyknięcie CSS dla zaokrąglonych kart i estetyki
st.markdown("""
    <style>
    div[data-testid="stVerticalBlock"] div[data-testid="stBorderBox"] {
        border-radius: 10px;
        background-color: #ffffff;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        padding: 15px;
        transition: transform 0.2s;
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stBorderBox"]:hover {
        transform: translateY(-2px);
        border-color: #ff9800;
    }
    </style>
    """, unsafe_allow_html=True)

# 2. BEZPIECZEŃSTWO (Hasło pobierane z Secrets)
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

# 3. POŁĄCZENIE Z BAZĄ (Google Sheets)
conn = st.connection("gsheets", type=GSheetsConnection)

NAZWA_ZAKLADKI_ZADANIA = "Arkusz1" 
NAZWA_ZAKLADKI_LINKI = "Linki"

try:
    # Pobieranie Zadań
    df_tasks = conn.read(worksheet=NAZWA_ZAKLADKI_ZADANIA, ttl=0)
    df_tasks = df_tasks.dropna(subset=["Temat", "Zadanie"]) 
    
    # Pobieranie Linków
    df_links = conn.read(worksheet=NAZWA_ZAKLADKI_LINKI, ttl=0)
    df_links = df_links.dropna(how="all") 
    
    # Zabezpieczenie typów danych dla bazy linków
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
    
    # Wybór modułu jako Radio Buttons (jak na Twoim screenie)
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
        st.info("💡 Przejdź do konkretnej zakładki powyżej, aby edytować statusy. Zmiany wysyłane są bezpośrednio do centrali (Google Sheets).")

    for i, temat in enumerate(lista_tematow):
        with zakladki_zadania[i+1]:
            st.markdown(f"### Operacja: **{temat}**")
            
            idx_tematu = df_tasks.index[df_tasks["Temat"] == temat]
            df_filtrowane = df_tasks.loc[idx_tematu].copy()
            
            edytowane_dane = st.data_editor(
                df_filtrowane,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Status": st.column_config.SelectboxColumn("Status", options=["Do zrobienia", "W trakcie", "Zrobione"], required=True)
                },
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
    
    # Wyszukiwarka
    szukana_fraza = st.text_input("🔍 Wyszukiwarka operacyjna (targi, portale, spedycje, awizacje):", placeholder="Wpisz szukaną frazę...")
    st.divider()
    
    # Filtrowanie danych po wyszukiwarce
    if szukana_fraza:
        mask = df_links.apply(lambda row: row.astype(str).str.contains(szukana_fraza, case=False).any(), axis=1)
        df_wyswietlane = df_links[mask]
    else:
        df_wyswietlane = df_links

    # Tworzenie dynamicznych zakładek z Kategorii z Google Sheets
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
                # Wyświetlanie linków jako kafelków (po 3 w rzędzie)
                kolumny = st.columns(3)
                for index, row in df_kat.reset_index(drop=True).iterrows():
                    with kolumny[index % 3]:
                        with st.container(border=True):
                            nazwa_kat = row['Kategoria'].upper() if row['Kategoria'] else "OGÓLNE"
                            st.caption(f"✈️ {nazwa_kat}")
                            st.markdown(f"#### {row['Nazwa']}")
                            
                            # Obcinamy opis jeśli jest za długi
                            opis = row['Opis']
                            st.write(opis if len(opis) < 80 else opis[:80] + "...")
                            
                            # Przycisk przenoszący do URL
                            if row['URL'].startswith('http'):
                                st.link_button("Uruchom procedurę ➔", row['URL'], use_container_width=True)
                            else:
                                st.button("Brak adresu URL", disabled=True, key=f"btn_{index}_{kategoria}", use_container_width=True)

# ==========================================
# WIDOK 3: HANGAR (Moduł CRUD dla Linków)
# ==========================================
elif widok == "🛠️ Hangar (Edycja Linków)":
    st.title("🛠️ Hangar – Modyfikacja Baz i Systemów")
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
