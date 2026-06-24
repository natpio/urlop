import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# 1. KONFIGURACJA STRONY
st.set_page_config(page_title="Logistics Terminal", page_icon="✈️", layout="wide")

# 2. ZAAWANSOWANY CSS (Tylko do odczytu - estetyka Kanban i Kart)
st.markdown("""
    <style>
    /* Karty Zadań (Kanban) */
    .task-card {
        background-color: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        border-left: 4px solid #94a3b8; /* Domyślny szary */
    }
    .task-card.todo { border-left-color: #ef4444; } /* Czerwony - do zrobienia */
    .task-card.inprogress { border-left-color: #f59e0b; } /* Żółty - w trakcie */
    .task-card.done { border-left-color: #10b981; opacity: 0.7; } /* Zielony - zrobione */
    
    .task-title { font-weight: 700; color: #1e293b; font-size: 16px; margin-bottom: 8px; }
    .task-assignee { font-size: 12px; color: #64748b; background: #f1f5f9; padding: 3px 8px; border-radius: 12px; display: inline-block; margin-bottom: 8px;}
    .task-notes { font-size: 13px; color: #475569; margin-top: 8px; font-style: italic; border-top: 1px dashed #e2e8f0; padding-top: 8px;}

    /* Karty Linków (Z poprzedniego designu) */
    .terminal-card {
        background-color: white;
        border-left: 6px solid #00205b;
        border-radius: 4px;
        padding: 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.08);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 250px;
        margin-bottom: 20px;
    }
    .terminal-card-category { color: #ffa500; font-weight: 800; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 10px; }
    .terminal-card-title { color: #00205b; font-weight: 900; font-size: 18px; margin-bottom: 10px; line-height: 1.2; }
    .terminal-card-desc { color: #6b7280; font-size: 13px; font-family: monospace; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; word-break: break-word; }
    .terminal-card-btn { background-color: #ff9800; color: #000000 !important; font-weight: bold; text-align: center; text-decoration: none; padding: 10px; border-radius: 4px; display: block; width: 100%; transition: 0.2s; margin-top: 15px;}
    .terminal-card-btn:hover { background-color: #e68a00; }
    </style>
    """, unsafe_allow_html=True)

# 3. BEZPIECZEŃSTWO
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔒 Terminal Logistyczny")
    password = st.text_input("Podaj kod dostępu zespołu:", type="password")
    if password == st.secrets["APP_PASSWORD"]:  
        st.session_state["authenticated"] = True
        st.rerun()
    st.stop()

# 4. POBIERANIE DANYCH Z GOOGLE SHEETS
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_tasks = conn.read(worksheet="Arkusz1", ttl=0).dropna(subset=["Temat", "Zadanie"])
    df_links = conn.read(worksheet="Linki", ttl=0).dropna(how="all")
    for col in ["Nazwa", "URL", "Opis", "Kategoria"]:
        if col not in df_links.columns: df_links[col] = ""
        df_links[col] = df_links[col].fillna("").astype(str)
except Exception as e:
    st.error(f"Błąd połączenia z bazą: {e}")
    st.stop()

# 5. NAGŁÓWEK I ODŚWIEŻANIE
colA, colB = st.columns([4, 1])
with colA:
    st.title("✈️ Główny Hub Operacyjny")
    st.markdown("Witaj w widoku zespołu. Zmian dokonuje administrator w arkuszu centralnym.")
with colB:
    st.write("") # Pusty odstęp
    if st.button("🔄 Odśwież dane", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
st.divider()

# 6. NAWIGACJA (TABS)
tab1, tab2, tab3 = st.tabs(["📊 PODSUMOWANIE", "📋 TABLICA KANBAN (ZADANIA)", "🌐 SYSTEMY I LINKI"])

# --- ZAKŁADKA 1: PODSUMOWANIE ---
with tab1:
    st.subheader("Bieżący status operacji")
    lista_tematow = sorted(df_tasks["Temat"].unique().tolist())
    
    for temat in lista_tematow:
        zadania_tematu = df_tasks[df_tasks["Temat"] == temat]
        wszystkie = len(zadania_tematu)
        zrobione = len(zadania_tematu[zadania_tematu["Status"] == "Zrobione"])
        progress = int((zrobione / wszystkie) * 100) if wszystkie > 0 else 0
        
        st.markdown(f"**{temat}** ({zrobione}/{wszystkie} zrobione)")
        st.progress(progress)

# --- ZAKŁADKA 2: KANBAN BOARD ---
with tab2:
    st.subheader("Rejestr Zadań")
    wybrany_temat = st.selectbox("Wybierz event / temat operacji:", ["Pokaż wszystkie"] + lista_tematow)
    st.markdown("---")
    
    if wybrany_temat != "Pokaż wszystkie":
        df_tasks = df_tasks[df_tasks["Temat"] == wybrany_temat]
        
    # Tworzenie 3 kolumn Kanbana
    k_todo, k_inprog, k_done = st.columns(3)
    
    with k_todo:
        st.markdown("### 🔴 Do zrobienia")
        for _, row in df_tasks[df_tasks["Status"] == "Do zrobienia"].iterrows():
            st.markdown(f"""
            <div class="task-card todo">
                <div class="task-title">{row['Zadanie']}</div>
                <div class="task-assignee">👤 {row['Osoba']} | 📅 {row['Termin']}</div>
                <div class="task-notes">{row['Notatki']}</div>
            </div>
            """, unsafe_allow_html=True)
            
    with k_inprog:
        st.markdown("### 🟡 W trakcie")
        for _, row in df_tasks[df_tasks["Status"] == "W trakcie"].iterrows():
            st.markdown(f"""
            <div class="task-card inprogress">
                <div class="task-title">{row['Zadanie']}</div>
                <div class="task-assignee">👤 {row['Osoba']} | 📅 {row['Termin']}</div>
                <div class="task-notes">{row['Notatki']}</div>
            </div>
            """, unsafe_allow_html=True)

    with k_done:
        st.markdown("### 🟢 Zrobione")
        for _, row in df_tasks[df_tasks["Status"] == "Zrobione"].iterrows():
            st.markdown(f"""
            <div class="task-card done">
                <div class="task-title" style="text-decoration: line-through;">{row['Zadanie']}</div>
                <div class="task-assignee">👤 {row['Osoba']}</div>
            </div>
            """, unsafe_allow_html=True)

# --- ZAKŁADKA 3: LINKI (KARTY) ---
with tab3:
    st.subheader("Nawigacja do systemów zewnętrznych")
    kategorie = sorted([k for k in df_links["Kategoria"].unique() if k.strip()])
    
    for kategoria in kategorie:
        st.markdown(f"#### 📂 {kategoria.upper()}")
        df_kat = df_links[df_links["Kategoria"] == kategoria]
        
        kolumny = st.columns(4) # 4 karty w rzędzie dla lepszego rozłożenia
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
