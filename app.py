import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# ==========================================
# 1. KONFIGURACJA STRONY I CSS
# ==========================================
st.set_page_config(page_title="Logistics Terminal", page_icon="✈️", layout="wide")

st.markdown("""
    <style>
    /* Wspólne style (Karty zadań i Linków) */
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
    .terminal-card-desc { color: #6b7280; font-size: 13px; display: block; overflow: hidden; margin-bottom:10px;}
    .terminal-card-btn { background-color: #ff9800; color: #000000 !important; font-weight: bold; text-align: center; text-decoration: none; padding: 10px; border-radius: 4px; display: block; width: 100%; transition: 0.2s; margin-top: auto;}
    .terminal-card-btn:hover { background-color: #e68a00; }

    /* CSS dla Ganta / Osi czasu (Stepper) */
    .timeline-container { background: white; padding: 25px; border-radius: 8px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 30px; }
    .timeline-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px; }
    .timeline-title { font-size: 20px; font-weight: 900; color: #00205b; }
    .timeline-truck { background: #ff9800; color: black; font-weight: bold; padding: 5px 15px; border-radius: 20px; font-size: 14px; }
    
    .stepper-wrapper { display: flex; justify-content: space-between; margin-bottom: 10px; position: relative; }
    .stepper-item { position: relative; display: flex; flex-direction: column; align-items: center; flex: 1; text-align: center; z-index: 2; }
    .stepper-item::before { position: absolute; content: ""; border-bottom: 4px solid #e2e8f0; width: 100%; top: 15px; left: -50%; z-index: -1; }
    .stepper-item:first-child::before { content: none; }
    
    /* Kolory statusów na osi */
    .step-counter { width: 34px; height: 34px; border-radius: 50%; background: #e2e8f0; color: #64748b; display: flex; justify-content: center; align-items: center; font-weight: bold; font-size: 14px; margin-bottom: 8px; border: 4px solid white; transition: 0.3s;}
    .step-name { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; }
    .step-date { font-size: 11px; color: #94a3b8; margin-top: 4px;}
    
    /* Etap Zakończony */
    .stepper-item.completed .step-counter { background: #10b981; color: white; }
    .stepper-item.completed + .stepper-item::before { border-color: #10b981; }
    /* Etap Aktualny (Pulsujący) */
    .stepper-item.active .step-counter { background: #ff9800; color: black; box-shadow: 0 0 0 5px rgba(255, 152, 0, 0.2); transform: scale(1.1); }
    .stepper-item.active .step-name { color: #ff9800; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. LOGOWANIE (RBAC)
# ==========================================
if "role" not in st.session_state:
    st.session_state["role"] = None

if not st.session_state["role"]:
    st.title("🔒 Autoryzacja Terminala")
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

# ==========================================
# 3. POŁĄCZENIE Z BAZĄ DANYCH
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_tasks = conn.read(worksheet="Arkusz1", ttl=0).dropna(how="all")
    df_links = conn.read(worksheet="Linki", ttl=0).dropna(how="all")
    df_carriers = conn.read(worksheet="Przewoznicy", ttl=0).dropna(how="all")
    df_schedule = conn.read(worksheet="Harmonogram", ttl=0).dropna(how="all")
    
    # Zabezpieczenie kolumn dla nowych zakładek (aby aplikacja nie wywaliła błędu, jeśli arkusz jest pusty)
    cols_tasks = ["Temat", "Zadanie", "Osoba", "Termin", "Status", "Notatki"]
    cols_links = ["Nazwa", "URL", "Opis", "Kategoria"]
    cols_carriers = ["Firma", "Kontakt", "Telefon", "Typ_Auta", "Uwagi"]
    cols_schedule = ["Event", "Auto", "1_Zaladunek", "2_Montaz_Od", "2_Montaz_Do", "3_Puste_Casy_1", "3_Puste_Casy_2", "4_Dzien_Klienta", "5_Dostawa_Pustych", "6_Odbior_Pelnych", "7_Rozladunek"]
    
    for col in cols_tasks: 
        if col not in df_tasks.columns: df_tasks[col] = ""
    for col in cols_links: 
        if col not in df_links.columns: df_links[col] = ""
    for col in cols_carriers: 
        if col not in df_carriers.columns: df_carriers[col] = ""
    for col in cols_schedule: 
        if col not in df_schedule.columns: df_schedule[col] = None
        # Konwersja na typ daty (jeśli możliwe) do ułatwienia obliczeń
        if col not in ["Event", "Auto"]:
            df_schedule[col] = pd.to_datetime(df_schedule[col], errors='coerce').dt.date

except Exception as e:
    st.error(f"Błąd połączenia z bazą danych Google: {e}")
    st.stop()

# ==========================================
# 4. FUNKCJA OBLICZAJĄCA AKTUALNY ETAP (GANTT)
# ==========================================
def get_current_stage(row):
    """Porównuje dzisiejszą datę z datami w tabeli i zwraca nr etapu (1-7)"""
    today = datetime.now().date()
    current_stage = 0
    
    stages_dates = [
        row.get("1_Zaladunek"),
        row.get("2_Montaz_Od"),
        row.get("3_Puste_Casy_1"),
        row.get("4_Dzien_Klienta"),
        row.get("5_Dostawa_Pustych"),
        row.get("6_Odbior_Pelnych"),
        row.get("7_Rozladunek")
    ]
    
    # Przechodzimy przez daty. Jeśli dzisiaj jest >= od daty etapu, to etap jest osiągnięty.
    for i, date_val in enumerate(stages_dates):
        if pd.notnull(date_val) and today >= date_val:
            current_stage = i + 1 
            
    # Jeśli mamy datę załadunku w przyszłości, a dzisiaj jest wcześniej -> etap 1 jako 'oczekujący' (active=1)
    if current_stage == 0 and pd.notnull(stages_dates[0]):
        current_stage = 1
        
    return current_stage

# ==========================================
# 5. PANEL BOCZNY (Wspólny)
# ==========================================
with st.sidebar:
    st.header("✈️ TERMINAL")
    if st.session_state["role"] == "admin":
        st.success("👨‍💻 Zalogowano: ADMIN")
    else:
        st.info("👥 Zalogowano: ZESPÓŁ")
    
    if st.button("🔒 Wyloguj", use_container_width=True):
        st.session_state["role"] = None
        st.rerun()

# =====================================================================
# WIDOK 1: ADMINISTRATOR (Pełna edycja z kalendarzami)
# =====================================================================
if st.session_state["role"] == "admin":
    st.title("🛠️ Centrum Dowodzenia (CMS)")
    st.write("Wprowadzaj dane bezpośrednio do tabel. Dodawaj nowe wiersze na dole tabeli.")
    
    tab_a1, tab_a2, tab_a3, tab_a4 = st.tabs(["📋 ZADANIA", "📅 HARMONOGRAM (GANTT)", "🚚 PRZEWOŹNICY", "🔗 LINKI"])
    
    with tab_a1:
        edytowane_zadania = st.data_editor(df_tasks, num_rows="dynamic", use_container_width=True, hide_index=True,
                                           column_config={"Status": st.column_config.SelectboxColumn(options=["Do zrobienia", "W trakcie", "Zrobione"])})
        if st.button("💾 ZAPISZ ZADANIA", type="primary"):
            conn.update(worksheet="Arkusz1", data=edytowane_zadania)
            st.cache_data.clear(); st.rerun()

    with tab_a2:
        st.info("Wybieraj daty w komórkach klikając w ikonę kalendarza.")
        
        # Konfiguracja kolumn daty, by wyświetlał się "DatePicker"
        date_cols_config = {col: st.column_config.DateColumn(col, format="YYYY-MM-DD") for col in cols_schedule if col not in ["Event", "Auto"]}
        
        edytowane_harm = st.data_editor(df_schedule, num_rows="dynamic", use_container_width=True, hide_index=True, column_config=date_cols_config)
        if st.button("💾 ZAPISZ HARMONOGRAM", type="primary"):
            conn.update(worksheet="Harmonogram", data=edytowane_harm)
            st.cache_data.clear(); st.rerun()

    with tab_a3:
        edytowane_przewoz = st.data_editor(df_carriers, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("💾 ZAPISZ PRZEWOŹNIKÓW", type="primary"):
            conn.update(worksheet="Przewoznicy", data=edytowane_przewoz)
            st.cache_data.clear(); st.rerun()

    with tab_a4:
        edytowane_linki = st.data_editor(df_links, num_rows="dynamic", use_container_width=True, hide_index=True,
                                         column_config={"URL": st.column_config.LinkColumn()})
        if st.button("💾 ZAPISZ LINKI", type="primary"):
            conn.update(worksheet="Linki", data=edytowane_linki)
            st.cache_data.clear(); st.rerun()

# =====================================================================
# WIDOK 2: ZESPÓŁ (Widok Operacyjny)
# =====================================================================
elif st.session_state["role"] == "team":
    
    colA, colB = st.columns([5, 1])
    with colA: st.title("✈️ Główny Hub Operacyjny")
    with colB: 
        st.write("")
        if st.button("🔄 Odśwież system", use_container_width=True): st.cache_data.clear(); st.rerun()
    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["🚦 HARMONOGRAM (LIVE)", "📋 REJESTR ZADAŃ", "🚚 FLOTA / PRZEWOŹNICY", "🌐 SYSTEMY"])

    # --- ZAKŁADKA 1: AKTYWNY HARMONOGRAM (GANTT STEPPER) ---
    with tab1:
        st.subheader("Bieżące śledzenie eventów i transportów")
        if df_schedule.empty or df_schedule["Event"].isnull().all():
            st.info("Brak aktywnych eventów w harmonogramie.")
        else:
            for index, row in df_schedule.dropna(subset=["Event"]).iterrows():
                
                etap = get_current_stage(row)
                
                # Definicja 7 etapów dla UI
                stages = [
                    {"name": "Załadunek", "date": row.get('1_Zaladunek')},
                    {"name": "Montaż", "date": row.get('2_Montaz_Od')},
                    {"name": "Puste Casy", "date": row.get('3_Puste_Casy_1')},
                    {"name": "Dzień Klienta", "date": row.get('4_Dzien_Klienta')},
                    {"name": "Dostawa Casy", "date": row.get('5_Dostawa_Pustych')},
                    {"name": "Odbiór Pełne", "date": row.get('6_Odbior_Pelnych')},
                    {"name": "Komorniki", "date": row.get('7_Rozladunek')}
                ]
                
                # Budowa kodu HTML dla Steppera
                stepper_html = f"""
                <div class="timeline-container">
                    <div class="timeline-header">
                        <div class="timeline-title">🎯 {row['Event']}</div>
                        <div class="timeline-truck">🚛 Przypisano: {row.get('Auto', 'Brak info')}</div>
                    </div>
                    <div class="stepper-wrapper">
                """
                
                for idx, s in enumerate(stages):
                    step_num = idx + 1
                    status_class = "completed" if step_num < etap else ("active" if step_num == etap else "")
                    
                    # Formatowanie daty do wyświetlenia
                    date_str = s['date'].strftime('%d.%m') if pd.notnull(s['date']) else "---"
                    
                    stepper_html += f"""
                        <div class="stepper-item {status_class}">
                            <div class="step-counter">{step_num}</div>
                            <div class="step-name">{s['name']}</div>
                            <div class="step-date">{date_str}</div>
                        </div>
                    """
                
                stepper_html += "</div></div>"
                st.markdown(stepper_html, unsafe_allow_html=True)

    # --- ZAKŁADKA 2: TABLICA ZADAŃ KANBAN ---
    with tab2:
        df_tasks_clean = df_tasks.dropna(subset=["Temat", "Zadanie"])
        lista_tematow = sorted(df_tasks_clean[df_tasks_clean["Temat"].str.strip() != ""]["Temat"].unique().tolist())
        wybrany_temat = st.selectbox("Filtruj według operacji:", ["Wszystkie"] + lista_tematow)
        st.markdown("---")
        df_kanban = df_tasks_clean if wybrany_temat == "Wszystkie" else df_tasks_clean[df_tasks_clean["Temat"] == wybrany_temat]
        
        k_todo, k_inprog, k_done = st.columns(3)
        with k_todo:
            st.markdown("### 🔴 Do zrobienia")
            for _, row in df_kanban[df_kanban["Status"] == "Do zrobienia"].iterrows():
                st.markdown(f"<div class='task-card todo'><div class='task-title'>{row['Zadanie']}</div><div class='task-assignee'>👤 {row['Osoba']}</div><div class='task-notes'>{row['Notatki']}</div></div>", unsafe_allow_html=True)
        with k_inprog:
            st.markdown("### 🟡 W trakcie")
            for _, row in df_kanban[df_kanban["Status"] == "W trakcie"].iterrows():
                st.markdown(f"<div class='task-card inprogress'><div class='task-title'>{row['Zadanie']}</div><div class='task-assignee'>👤 {row['Osoba']}</div><div class='task-notes'>{row['Notatki']}</div></div>", unsafe_allow_html=True)
        with k_done:
            st.markdown("### 🟢 Zrobione")
            for _, row in df_kanban[df_kanban["Status"] == "Zrobione"].iterrows():
                st.markdown(f"<div class='task-card done'><div class='task-title' style='text-decoration: line-through;'>{row['Zadanie']}</div><div class='task-assignee'>👤 {row['Osoba']}</div></div>", unsafe_allow_html=True)

    # --- ZAKŁADKA 3: BAZA PRZEWOŹNIKÓW ---
    with tab3:
        st.subheader("Rejestr floty i przewoźników")
        if df_carriers.empty or df_carriers["Firma"].isnull().all():
            st.write("Brak zapisanych przewoźników.")
        else:
            cols_c = st.columns(3)
            for index, row in df_carriers.dropna(subset=["Firma"]).reset_index(drop=True).iterrows():
                with cols_c[index % 3]:
                    st.markdown(f"""
                    <div class="terminal-card" style="height: auto; min-height: 200px;">
                        <div>
                            <div class="terminal-card-category">🚛 {row.get('Typ_Auta', 'Brak inf. o aucie')}</div>
                            <div class="terminal-card-title" style="font-size:16px;">{row['Firma']}</div>
                            <div class="terminal-card-desc">
                                <strong>📞 Telefon:</strong> {row.get('Telefon', '---')}<br>
                                <strong>👤 Kontakt:</strong> {row.get('Kontakt', '---')}<br>
                                <hr style="margin: 10px 0; border-top: 1px dashed #ccc;">
                                <i>{row.get('Uwagi', '')}</i>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    # --- ZAKŁADKA 4: SYSTEMY I LINKI ---
    with tab4:
        kategorie = sorted([k for k in df_links["Kategoria"].unique() if k.strip()])
        for kategoria in kategorie:
            st.markdown(f"#### 📂 {kategoria.upper()}")
            kolumny = st.columns(4) 
            for index, row in df_links[df_links["Kategoria"] == kategoria].reset_index(drop=True).iterrows():
                with kolumny[index % 4]:
                    url = row['URL'] if row['URL'].startswith('http') else '#'
                    opis = row['Opis'] if row['Opis'] else url
                    st.markdown(f"""
                    <div class="terminal-card">
                        <div>
                            <div class="terminal-card-category">✈️ {row['Kategoria']}</div>
                            <div class="terminal-card-title">{row['Nazwa']}</div>
                            <div class="terminal-card-desc">{opis}</div>
                        </div>
                        <a href="{url}" target="_blank" class="terminal-card-btn">Uruchom ➔</a>
                    </div>
                    """, unsafe_allow_html=True)
