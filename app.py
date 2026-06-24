import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# 1. KONFIGURACJA STRONY I CSS
st.set_page_config(page_title="Logistics Terminal", page_icon="✈️", layout="wide")

st.markdown("""
    <style>
    /* CSS dla widoku Zespołu (Kanban i Karty) */
    .task-card { background-color: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); border-left: 4px solid #94a3b8; }
    .task-card.todo { border-left-color: #ef4444; } 
    .task-card.inprogress { border-left-color: #f59e0b; } 
    .task-card.done { border-left-color: #10b981; opacity: 0.7; } 
    .task-title { font-weight: 700; color: #1e293b; font-size: 16px; margin-bottom: 8px; }
    .task-assignee { font-size: 12px; color: #64748b; background: #f1f5f9; padding: 3px 8px; border-radius: 12px; display: inline-block; margin-bottom: 8px;}
    .task-notes { font-size: 13px; color: #475569; margin-top: 8px; font-style: italic; border-top: 1px dashed #e2e8f0; padding-top: 8px;}

    .terminal-card { background-color: white; border-left: 6px solid #00205b; border-radius: 4px; padding: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.08); display: flex; flex-direction: column; justify-content: space-between; height: 250px; margin-bottom: 20px; }
    .terminal-card-category { color: #ffa500; font-weight: 800; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 10px; }
    .terminal-card-title { color: #00205b; font-weight: 900; font-size: 18px; margin-bottom: 10px; line-height: 1.2; }
    .terminal-card-desc { color: #6b7280; font-size: 13px; font-family: monospace; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; word-break: break-word; }
    .terminal-card-btn { background-color: #ff9800; color: #000000 !important; font-weight: bold; text-align: center; text-decoration: none; padding: 10px; border-radius: 4px; display: block; width: 100%; transition: 0.2s; margin-top: 15px;}
    .terminal-card-btn:hover { background-color: #e68a00; }
    </style>
    """, unsafe_allow_html=True)

# 2. LOGOWANIE I SYSTEM RÓW (RBAC)
if "role" not in st.session_state:
    st.session_state["role"] = None

if not st.session_state["role"]:
    st.title("🔒 Autoryzacja")
    password = st.text_input("Podaj kod dostępu:", type="password")
    
    if password == st.secrets["ADMIN_PASSWORD"]:
        st.session_state["role"] = "admin"
        st.rerun()
    elif password == st.secrets["TEAM_PASSWORD"]:
        st.session_state["role"] = "team"
        st.rerun()
    elif password:
        st.error("❌ Odmowa dostępu. Nieprawidłowy kod.")
    st.stop()

# 3. POŁĄCZENIE Z BAZĄ DANYCH
conn = st.connection("gsheets", type=GSheetsConnection)
NAZWA_ZAKLADKI_ZADANIA = "Arkusz1"
NAZWA_ZAKLADKI_LINKI = "Linki"

try:
    df_tasks = conn.read(worksheet=NAZWA_ZAKLADKI_ZADANIA, ttl=0).dropna(how="all")
    df_links = conn.read(worksheet=NAZWA_ZAKLADKI_LINKI, ttl=0).dropna(how="all")
    
    # Czyszczenie typów danych dla pustych tabel
    for col in ["Temat", "Zadanie", "Osoba", "Termin", "Status", "Notatki"]:
        if col not in df_tasks.columns: df_tasks[col] = ""
    for col in ["Nazwa", "URL", "Opis", "Kategoria"]:
        if col not in df_links.columns: df_links[col] = ""
        df_links[col] = df_links[col].fillna("").astype(str)
except Exception as e:
    st.error(f"Błąd połączenia z bazą: {e}")
    st.stop()

# WSPÓLNY SIDEBAR DLA OBU RÓL
with st.sidebar:
    st.header("✈️ TERMINAL")
    if st.session_state["role"] == "admin":
        st.success("👨‍💻 Jesteś zalogowany jako: ADMIN")
    else:
        st.info("👥 Jesteś zalogowany jako: ZESPÓŁ")
    
    if st.button("🔒 Wyloguj", use_container_width=True):
        st.session_state["role"] = None
        st.rerun()

# =====================================================================
# WIDOK 1: ADMINISTRATOR (Pełna edycja bazy)
# =====================================================================
if st.session_state["role"] == "admin":
    st.title("🛠️ Panel Administratora")
    st.write("W tym trybie masz pełną kontrolę nad bazą danych. Możesz dodawać nowe wiersze (zjedź na dół tabeli), edytować komórki i usuwać dane (zaznacz wiersz po lewej i naciśnij Delete).")
    
    tab_admin1, tab_admin2 = st.tabs(["📋 EDYCJA ZADAŃ", "🔗 EDYCJA LINKÓW"])
    
    with tab_admin1:
        st.subheader("Baza Operacji i Zadań")
        edytowane_zadania = st.data_editor(
            df_tasks,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.SelectboxColumn("Status", options=["Do zrobienia", "W trakcie", "Zrobione"], required=True)
            },
            key="admin_tasks_editor"
        )
        if st.button("💾 ZAPISZ ZMIANY W ZADANIACH", type="primary"):
            with st.spinner("Zapisywanie w chmurze..."):
                conn.update(worksheet=NAZWA_ZAKLADKI_ZADANIA, data=edytowane_zadania)
                st.cache_data.clear()
                st.success("✅ Zapisano zadania!")
                st.rerun()

    with tab_admin2:
        st.subheader("Baza Systemów i Linków")
        edytowane_linki = st.data_editor(
            df_links,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn("Adres URL")
            },
            key="admin_links_editor"
        )
        if st.button("💾 ZAPISZ ZMIANY W LINKACH", type="primary"):
            with st.spinner("Zapisywanie w chmurze..."):
                conn.update(worksheet=NAZWA_ZAKLADKI_LINKI, data=edytowane_linki)
                st.cache_data.clear()
                st.success("✅ Zapisano linki!")
                st.rerun()

# =====================================================================
# WIDOK 2: ZESPÓŁ (Tylko do odczytu - Kanban i Karty)
# =====================================================================
elif st.session_state["role"] == "team":
    
    colA, colB = st.columns([4, 1])
    with colA:
        st.title("✈️ Główny Hub Operacyjny")
        st.markdown("Witaj w widoku operacyjnym. Dane są aktualizowane na bieżąco.")
    with colB:
        st.write("") 
        if st.button("🔄 Odśwież dane", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    st.divider()

    df_tasks_clean = df_tasks.dropna(subset=["Temat", "Zadanie"])
    df_tasks_clean = df_tasks_clean[df_tasks_clean["Temat"].str.strip() != ""] # Filtrujemy puste tematy
    lista_tematow = sorted(df_tasks_clean["Temat"].unique().tolist())
    
    tab1, tab2, tab3 = st.tabs(["📊 PODSUMOWANIE", "📋 TABLICA KANBAN", "🌐 SYSTEMY I LINKI"])

    with tab1:
        st.subheader("Bieżący status operacji")
        for temat in lista_tematow:
            zadania_tematu = df_tasks_clean[df_tasks_clean["Temat"] == temat]
            wszystkie = len(zadania_tematu)
            zrobione = len(zadania_tematu[zadania_tematu["Status"] == "Zrobione"])
            progress = int((zrobione / wszystkie) * 100) if wszystkie > 0 else 0
            
            st.markdown(f"**{temat}** ({zrobione}/{wszystkie} zrobione)")
            st.progress(progress)

    with tab2:
        st.subheader("Rejestr Zadań")
        wybrany_temat = st.selectbox("Filtruj według operacji:", ["Pokaż wszystkie"] + lista_tematow)
        st.markdown("---")
        
        df_kanban = df_tasks_clean if wybrany_temat == "Pokaż wszystkie" else df_tasks_clean[df_tasks_clean["Temat"] == wybrany_temat]
            
        k_todo, k_inprog, k_done = st.columns(3)
        
        with k_todo:
            st.markdown("### 🔴 Do zrobienia")
            for _, row in df_kanban[df_kanban["Status"] == "Do zrobienia"].iterrows():
                st.markdown(f"""
                <div class="task-card todo">
                    <div class="task-title">{row['Zadanie']}</div>
                    <div class="task-assignee">👤 {row['Osoba']} | 📅 {row['Termin']}</div>
                    <div class="task-notes">{row['Notatki']}</div>
                </div>
                """, unsafe_allow_html=True)
                
        with k_inprog:
            st.markdown("### 🟡 W trakcie")
            for _, row in df_kanban[df_kanban["Status"] == "W trakcie"].iterrows():
                st.markdown(f"""
                <div class="task-card inprogress">
                    <div class="task-title">{row['Zadanie']}</div>
                    <div class="task-assignee">👤 {row['Osoba']} | 📅 {row['Termin']}</div>
                    <div class="task-notes">{row['Notatki']}</div>
                </div>
                """, unsafe_allow_html=True)

        with k_done:
            st.markdown("### 🟢 Zrobione")
            for _, row in df_kanban[df_kanban["Status"] == "Zrobione"].iterrows():
                st.markdown(f"""
                <div class="task-card done">
                    <div class="task-title" style="text-decoration: line-through;">{row['Zadanie']}</div>
                    <div class="task-assignee">👤 {row['Osoba']}</div>
                </div>
                """, unsafe_allow_html=True)

    with tab3:
        st.subheader("Nawigacja do systemów zewnętrznych")
        kategorie = sorted([k for k in df_links["Kategoria"].unique() if k.strip()])
        
        for kategoria in kategorie:
            st.markdown(f"#### 📂 {kategoria.upper()}")
            df_kat = df_links[df_links["Kategoria"] == kategoria]
            
            kolumny = st.columns(4) 
            for index, row in df_kat.reset_index(drop=True).iterrows():
                with kolumny[index % 4]:
                    opis_tekst = row['Opis'] if row['Opis'] else row['URL']
                    url = row['URL'] if row['URL'].startswith('http') else '#'
                    
                    st.markdown(f"""
                    <div class="terminal-card">
                        <div>
                            <div class="terminal-card-category">✈️ {row['Kategoria']}</div>
                            <div class="terminal-card-title">{row['Nazwa']}</div>
                            <div class="terminal-card-desc">{opis_tekst}</div>
                        </div>
                        <a href="{url}" target="_blank" class="terminal-card-btn">Uruchom ➔</a>
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown("---")
