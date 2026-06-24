import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.express as px
from geopy.geocoders import Nominatim

# ==========================================
# 1. KONFIGURACJA STRONY I CSS
# ==========================================
st.set_page_config(page_title="Global Logistics Hub", page_icon="✈️", layout="wide")

def local_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        pass

local_css("style.css")

# ==========================================
# 2. AUTORYZACJA (FIRST CLASS SECURITY)
# ==========================================
if "role" not in st.session_state:
    st.session_state["role"] = None

if not st.session_state["role"]:
    st.markdown("""<div class="aviation-banner" style="text-align: center; margin-top: 10vh;">
<h1>✈️ GLOBAL LOGISTICS TERMINAL</h1>
<p>Wprowadź kod dostępu do systemu operacyjnego</p>
</div>""", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input("Security Code:", type="password", placeholder="Wpisz hasło...", label_visibility="collapsed")
        if password == st.secrets["ADMIN_PASSWORD"]:
            st.session_state["role"] = "admin"
            st.rerun()
        elif password == st.secrets["TEAM_PASSWORD"]:
            st.session_state["role"] = "team"
            st.rerun()
        elif password:
            st.error("❌ Odmowa dostępu. Nierozpoznany kod.")
    st.stop()

# ==========================================
# 3. POŁĄCZENIE Z BAZĄ DANYCH
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_tasks = conn.read(worksheet="Arkusz1", ttl=60).dropna(how="all")
    df_links = conn.read(worksheet="Linki", ttl=60).dropna(how="all")
    df_carriers = conn.read(worksheet="Przewoznicy", ttl=60).dropna(how="all")
    df_schedule = conn.read(worksheet="Harmonogram", ttl=60).dropna(how="all")
    df_notes = conn.read(worksheet="Notatnik", ttl=60).dropna(how="all")
    
    # Dodano nową kolumnę "Lokalizacja"
    cols_tasks = ["Temat", "Zadanie", "Osoba", "Termin", "Status", "Notatki"]
    cols_links = ["Nazwa", "URL", "Opis", "Kategoria"]
    cols_carriers = ["Firma", "Kontakt", "Telefon", "Typ_Auta", "Uwagi"]
    cols_schedule = ["Event", "Lokalizacja", "Auto", "1_Zaladunek", "2_Montaz_Od", "2_Montaz_Do", "3_Puste_Casy_1", "3_Puste_Casy_2", "4_Dzien_Klienta", "5_Dostawa_Pustych", "6_Odbior_Pelnych", "7_Rozladunek"]
    cols_notes = ["Data", "Kto", "Wiadomość"]
    
    for col in cols_tasks: 
        if col not in df_tasks.columns: df_tasks[col] = ""
        df_tasks[col] = df_tasks[col].fillna("").astype(str)
    for col in cols_links: 
        if col not in df_links.columns: df_links[col] = ""
        df_links[col] = df_links[col].fillna("").astype(str)
    for col in cols_carriers: 
        if col not in df_carriers.columns: df_carriers[col] = ""
        df_carriers[col] = df_carriers[col].fillna("").astype(str)
    for col in cols_notes: 
        if col not in df_notes.columns: df_notes[col] = ""
        df_notes[col] = df_notes[col].fillna("").astype(str)
        
    for col in cols_schedule: 
        if col not in df_schedule.columns: df_schedule[col] = None
        if col not in ["Event", "Auto", "Lokalizacja"]:
            df_schedule[col] = pd.to_datetime(df_schedule[col], errors='coerce').dt.date
        else:
            df_schedule[col] = df_schedule[col].fillna("").astype(str)

except Exception as e:
    st.error(f"⚠️ Błąd połączenia z bazą: {e}")
    st.stop()

# ==========================================
# 4. FUNKCJE BIZNESOWE I GEOKODOWANIE (RADAR)
# ==========================================
def get_current_stage(row):
    today = datetime.now().date()
    current_stage = 0
    stages_dates = [
        row.get("1_Zaladunek"), row.get("2_Montaz_Od"), row.get("3_Puste_Casy_1"),
        row.get("4_Dzien_Klienta"), row.get("5_Dostawa_Pustych"), row.get("6_Odbior_Pelnych"), row.get("7_Rozladunek")
    ]
    for i, date_val in enumerate(stages_dates):
        if pd.notnull(date_val) and today >= date_val:
            current_stage = i + 1 
    if current_stage == 0 and pd.notnull(stages_dates[0]):
        current_stage = 1
    return current_stage

def clean_for_gsheets(df):
    cleaned = df.copy()
    for col in cleaned.columns:
        cleaned[col] = cleaned[col].astype(str).replace(['NaT', 'nan', 'None', '<NA>', 'NaN'], '')
    return cleaned

@st.cache_data(ttl=3600) # Czasujemy współrzędne, żeby nie pytać API za każdym razem
def get_coordinates(city_name):
    if not city_name or city_name.strip() == "":
        return None, None
    geolocator = Nominatim(user_agent="logistics_hub_agent")
    try:
        location = geolocator.geocode(city_name)
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

def render_radar(schedule_df):
    st.markdown("<h3 style='color: #002244; font-weight: 900;'>🗺️ Radar Operacyjny</h3>", unsafe_allow_html=True)
    
    df_active = schedule_df[schedule_df["Event"].str.strip() != ""].copy()
    if df_active.empty:
        st.info("Brak aktywnych eventów na radarze.")
        return
        
    map_data = []
    for _, row in df_active.iterrows():
        lat, lon = get_coordinates(row.get('Lokalizacja', ''))
        if lat and lon:
            stage = get_current_stage(row)
            
            # Kategoryzacja statusów na mapie
            if stage <= 1:
                status_txt = "🔴 Oczekujący (Przed załadunkiem)"
                color = "#EF4444" # Czerwony
            elif stage < 7:
                status_txt = "🟡 Aktywny (W trasie / Targi)"
                color = "#FFB81C" # Żółty lotniczy
            else:
                status_txt = "🟢 Zakończony (Rozładunek)"
                color = "#10B981" # Zielony
                
            map_data.append({
                "Event": row['Event'],
                "Lokalizacja": row['Lokalizacja'],
                "Auto": row.get('Auto', 'Nie przypisano'),
                "Status": status_txt,
                "Kolor": color,
                "lat": lat,
                "lon": lon
            })
            
    if not map_data:
        st.warning("Uzupełnij kolumnę 'Lokalizacja' w Harmonogramie, aby aktywować radar (np. wpisz 'Berlin').")
        return

    df_map = pd.DataFrame(map_data)
    
    # Tworzenie ciemnej mapy lotniczej z Plotly
    fig = px.scatter_mapbox(
        df_map, 
        lat="lat", lon="lon", 
        hover_name="Event", 
        hover_data={"lat": False, "lon": False, "Status": True, "Auto": True, "Lokalizacja": True},
        color="Status",
        color_discrete_map={
            "🔴 Oczekujący (Przed załadunkiem)": "#EF4444", 
            "🟡 Aktywny (W trasie / Targi)": "#FFB81C", 
            "🟢 Zakończony (Rozładunek)": "#10B981"
        },
        zoom=3.5, 
        height=550
    )
    fig.update_layout(
        mapbox_style="carto-darkmatter", # Ciemny motyw lotniczy
        margin={"r":0,"t":0,"l":0,"b":0},
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0.5)", font=dict(color="white"))
    )
    
    st.plotly_chart(fig, use_container_width=True)

# === FUNKCJA: RENDEROWANIE LOGBOOKA ===
def render_logbook(conn_obj, notes_dataframe, user_role):
    st.markdown("<br>", unsafe_allow_html=True)
    col_hist, col_form = st.columns([3, 2], gap="large")
    
    with col_form:
        st.markdown("""<div style="background: white; padding: 20px; border-radius: 8px 8px 0 0; border-bottom: 2px solid #F3F5F7; border-top: 5px solid #FFB81C; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
<h3 style="margin: 0; color: #002244; font-weight: 900; font-size: 18px;">📡 Nadaj Komunikat (New Scenario)</h3>
</div>""", unsafe_allow_html=True)
        
        with st.form("logbook_form", clear_on_submit=True):
            kto = st.text_input("Identyfikator (Kto):", placeholder="np. Janek / Dyspozycja")
            wiadomosc = st.text_area("Treść komunikatu:", placeholder="Wpisz pilną wiadomość...", height=150)
            submitted = st.form_submit_button("Wyślij do systemu ➔", use_container_width=True)
            
            if submitted:
                if kto.strip() == "" or wiadomosc.strip() == "":
                    st.warning("⚠️ Wypełnij oba pola przed wysłaniem!")
                else:
                    nowy_wpis = pd.DataFrame([{"Data": datetime.now().strftime("%Y-%m-%d | %H:%M:%S"), "Kto": kto, "Wiadomość": wiadomosc}])
                    updated_df = pd.concat([notes_dataframe, nowy_wpis], ignore_index=True)
                    with st.spinner("Szyfrowanie i nadawanie..."):
                        conn_obj.update(worksheet="Notatnik", data=clean_for_gsheets(updated_df))
                        st.cache_data.clear(); st.rerun()

    with col_hist:
        st.markdown("<h3 style='color: #002244; font-weight: 900; margin-bottom: 20px;'>📻 Dziennik Pokładowy (Logistics Scripts)</h3>", unsafe_allow_html=True)
        df_notes_clean = notes_dataframe[notes_dataframe["Wiadomość"].str.strip() != ""]
        
        if df_notes_clean.empty:
            st.info("Brak komunikatów w systemie.")
        else:
            for idx, row in df_notes_clean.iloc[::-1].iterrows():
                st.markdown(f"""<div style="background-color: #1E293B; border-left: 6px solid #FFB81C; border-radius: 6px; padding: 18px; margin-bottom: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
<span style="color: #94A3B8; font-size: 11px; font-family: monospace;">🗓️ {row['Data']}</span>
<span style="background: #002244; color: #FFB81C; padding: 3px 12px; border-radius: 20px; font-size: 11px; font-weight: 800; border: 1px solid #FFB81C;">👤 {row['Kto']}</span>
</div>
<div style="color: #F8FAFC; font-size: 16px; font-weight: 400; font-family: monospace; letter-spacing: 0.5px;">"{row['Wiadomość']}"</div>
</div>""", unsafe_allow_html=True)
                
                if user_role == "admin":
                    col_btn, _ = st.columns([1, 4])
                    with col_btn:
                        if st.button("✂️ CUT", key=f"del_{idx}", help="Usuń ten komunikat", use_container_width=True):
                            updated_df = notes_dataframe.drop(idx)
                            conn_obj.update(worksheet="Notatnik", data=clean_for_gsheets(updated_df))
                            st.cache_data.clear(); st.rerun()
                    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

# ==========================================
# 5. WSPÓLNY PANEL BOCZNY
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=60)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.session_state["role"] == "admin":
        st.success("👨‍✈️ STATUS: CAPTAIN (ADMIN)")
    else:
        st.info("👨‍💼 STATUS: CREW (ZESPÓŁ)")
    st.markdown("---")
    if st.button("🚪 Zakończ zmianę (Wyloguj)", use_container_width=True):
        st.session_state["role"] = None
        st.rerun()

# =====================================================================
# WIDOK 1: ADMINISTRATOR
# =====================================================================
if st.session_state["role"] == "admin":
    st.markdown("""<div class="aviation-banner">
<h1>⚙️ FLIGHT DECK (CMS)</h1>
<p>Zarządzanie infrastrukturą, zadaniami, flotą i logbookiem.</p>
</div>""", unsafe_allow_html=True)
    
    tab_a1, tab_a2, tab_a3, tab_a4, tab_a5 = st.tabs(["📋 REJESTR ZADAŃ", "📅 HARMONOGRAM", "🚚 FLOTA", "🔗 SYSTEMY", "📝 LOGBOOK"])
    
    with tab_a1:
        edytowane_zadania = st.data_editor(df_tasks, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"Status": st.column_config.SelectboxColumn(options=["Do zrobienia", "W trakcie", "Zrobione"])})
        if st.button("🛫 Wgraj aktualizację zadań", type="primary"):
            conn.update(worksheet="Arkusz1", data=clean_for_gsheets(edytowane_zadania)); st.cache_data.clear(); st.rerun()

    with tab_a2:
        date_cols_config = {col: st.column_config.DateColumn(col, format="YYYY-MM-DD") for col in cols_schedule if col not in ["Event", "Auto", "Lokalizacja"]}
        edytowane_harm = st.data_editor(df_schedule, num_rows="dynamic", use_container_width=True, hide_index=True, column_config=date_cols_config)
        if st.button("🛫 Wgraj aktualizację harmonogramu", type="primary"):
            conn.update(worksheet="Harmonogram", data=clean_for_gsheets(edytowane_harm)); st.cache_data.clear(); st.rerun()

    with tab_a3:
        edytowane_przewoz = st.data_editor(df_carriers, num_rows="dynamic", use_container_width=True, hide_index=True)
        if st.button("🛫 Wgraj aktualizację floty", type="primary"):
            conn.update(worksheet="Przewoznicy", data=clean_for_gsheets(edytowane_przewoz)); st.cache_data.clear(); st.rerun()

    with tab_a4:
        edytowane_linki = st.data_editor(df_links, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"URL": st.column_config.LinkColumn()})
        if st.button("🛫 Wgraj aktualizację systemów", type="primary"):
            conn.update(worksheet="Linki", data=clean_for_gsheets(edytowane_linki)); st.cache_data.clear(); st.rerun()

    with tab_a5:
        render_logbook(conn, df_notes, st.session_state["role"])

# =====================================================================
# WIDOK 2: ZESPÓŁ (Widok Operacyjny)
# =====================================================================
elif st.session_state["role"] == "team":
    
    colA, colB = st.columns([5, 1])
    with colA: 
        st.markdown("""<div class="aviation-banner">
<h1>🌐 GLOBAL OPERATIONS HUB</h1>
<p>Bieżący monitoring statusów logistycznych i komunikacja</p>
</div>""", unsafe_allow_html=True)
    with colB: 
        st.write("")
        st.write("")
        if st.button("🔄 POBIERZ DANE", use_container_width=True): 
            st.cache_data.clear(); st.rerun()

    # TABS - Radar idzie na pierwsze miejsce!
    tab_radar, tab1, tab2, tab3, tab4, tab5 = st.tabs(["🗺️ RADAR (MAPA)", "🚦 MONITOR EVENTÓW", "📋 KANBAN BOARD", "🚚 FLOTA / PRZEWOŹNICY", "🔗 PORTALE", "📝 LOGBOOK"])

    # --- NOWA ZAKŁADKA: RADAR ---
    with tab_radar:
        render_radar(df_schedule)

    with tab1:
        st.markdown("<br>", unsafe_allow_html=True)
        df_schedule_clean = df_schedule[df_schedule["Event"].str.strip() != ""]
        if df_schedule_clean.empty:
            st.info("Brak aktywnych eventów w systemie lotów.")
        else:
            for index, row in df_schedule_clean.iterrows():
                etap = get_current_stage(row)
                stages = [
                    {"name": "Załadunek", "date": row.get('1_Zaladunek')},
                    {"name": "Montaż", "date": row.get('2_Montaz_Od')},
                    {"name": "Casy (Pust)", "date": row.get('3_Puste_Casy_1')},
                    {"name": "Start Targów", "date": row.get('4_Dzien_Klienta')},
                    {"name": "Dostawa Casy", "date": row.get('5_Dostawa_Pustych')},
                    {"name": "Odbiór Pełn.", "date": row.get('6_Odbior_Pelnych')},
                    {"name": "Rozładunek", "date": row.get('7_Rozladunek')}
                ]
                
                stepper_html = f"""<div class="timeline-container">
<div class="timeline-header">
<div class="timeline-title">✈️ {row['Event']} <span style='font-size:14px; color: #6B7280; font-weight:normal;'>({row.get('Lokalizacja', '')})</span></div>
<div class="timeline-truck">TRUCK: {row.get('Auto', 'Oczekuje na przypisanie')}</div>
</div>
<div class="stepper-wrapper">"""
                for idx, s in enumerate(stages):
                    step_num = idx + 1
                    status_class = "completed" if step_num < etap else ("active" if step_num == etap else "")
                    date_str = s['date'].strftime('%d.%m') if pd.notnull(s['date']) else "---"
                    stepper_html += f"""<div class="stepper-item {status_class}">
<div class="step-counter">{step_num}</div>
<div class="step-name">{s['name']}</div>
<div class="step-date">{date_str}</div>
</div>"""
                stepper_html += "</div></div>"
                st.markdown(stepper_html, unsafe_allow_html=True)

    with tab2:
        st.markdown("<br>", unsafe_allow_html=True)
        df_tasks_clean = df_tasks[df_tasks["Temat"].str.strip() != ""]
        lista_tematow = sorted(df_tasks_clean["Temat"].unique().tolist())
        wybrany_temat = st.selectbox("Filtruj obszar zadań:", ["Widok globalny"] + lista_tematow)
        st.markdown("---")
        
        df_kanban = df_tasks_clean if wybrany_temat == "Widok globalny" else df_tasks_clean[df_tasks_clean["Temat"] == wybrany_temat]
        
        k_todo, k_inprog, k_done = st.columns(3)
        with k_todo:
            st.markdown("<h3 style='color: #EF4444; font-size:16px; font-weight:800;'>🔴 STANDBY (Do zrobienia)</h3>", unsafe_allow_html=True)
            for _, row in df_kanban[df_kanban["Status"] == "Do zrobienia"].iterrows():
                st.markdown(f"<div class='task-card todo'><div class='task-title'>{row['Zadanie']}</div><div class='task-assignee'>👨‍✈️ {row['Osoba']}</div><div class='task-notes'>{row['Notatki']}</div></div>", unsafe_allow_html=True)
        with k_inprog:
            st.markdown("<h3 style='color: #FFB81C; font-size:16px; font-weight:800;'>🟡 IN TRANSIT (W trakcie)</h3>", unsafe_allow_html=True)
            for _, row in df_kanban[df_kanban["Status"] == "W trakcie"].iterrows():
                st.markdown(f"<div class='task-card inprogress'><div class='task-title'>{row['Zadanie']}</div><div class='task-assignee'>👨‍✈️ {row['Osoba']}</div><div class='task-notes'>{row['Notatki']}</div></div>", unsafe_allow_html=True)
        with k_done:
            st.markdown("<h3 style='color: #10B981; font-size:16px; font-weight:800;'>🟢 ARRIVED (Zrobione)</h3>", unsafe_allow_html=True)
            for _, row in df_kanban[df_kanban["Status"] == "Zrobione"].iterrows():
                st.markdown(f"<div class='task-card done'><div class='task-title' style='text-decoration: line-through; color: #9CA3AF;'>{row['Zadanie']}</div><div class='task-assignee'>👨‍✈️ {row['Osoba']}</div></div>", unsafe_allow_html=True)

    with tab3:
        st.markdown("<br>", unsafe_allow_html=True)
        df_carriers_clean = df_carriers[df_carriers["Firma"].str.strip() != ""]
        if df_carriers_clean.empty:
            st.info("Brak danych floty w rejestrze.")
        else:
            cols_c = st.columns(3)
            for index, row in df_carriers_clean.reset_index(drop=True).iterrows():
                with cols_c[index % 3]:
                    st.markdown(f"""<div class="terminal-card" style="min-height: 220px;">
<div>
<div class="terminal-card-category">🚛 {row.get('Typ_Auta', 'Typ Nieznany')}</div>
<div class="terminal-card-title">{row['Firma']}</div>
<div class="terminal-card-desc">
<strong>📞 Tel:</strong> {row.get('Telefon', '---')}<br>
<strong>👤 Kontakt:</strong> {row.get('Kontakt', '---')}<br>
<br><i>{row.get('Uwagi', '')}</i>
</div>
</div>
</div>""", unsafe_allow_html=True)

    with tab4:
        st.markdown("<br>", unsafe_allow_html=True)
        df_links_clean = df_links[df_links["Kategoria"].str.strip() != ""]
        kategorie = sorted(df_links_clean["Kategoria"].unique().tolist())
        for kategoria in kategorie:
            st.markdown(f"<h4 style='color: #002244; font-weight: 900; letter-spacing: 1px; margin-top:20px;'>📂 {kategoria.upper()}</h4>", unsafe_allow_html=True)
            kolumny = st.columns(4) 
            for index, row in df_links_clean[df_links_clean["Kategoria"] == kategoria].reset_index(drop=True).iterrows():
                with kolumny[index % 4]:
                    url = row['URL'] if row['URL'].startswith('http') else '#'
                    opis = row['Opis'] if row['Opis'] else url
                    st.markdown(f"""<div class="terminal-card">
<div>
<div class="terminal-card-category">🌐 P.O.D.</div>
<div class="terminal-card-title">{row['Nazwa']}</div>
<div class="terminal-card-desc">{opis}</div>
</div>
<a href="{url}" target="_blank" class="terminal-card-btn">Zainicjuj Połączenie ➔</a>
</div>""", unsafe_allow_html=True)

    with tab5:
        render_logbook(conn, df_notes, st.session_state["role"])
