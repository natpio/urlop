import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import time

# Import naszych funkcji pomocniczych z nowo utworzonego pliku utils.py
from utils import clean_for_gsheets, get_current_stage, get_coordinates

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
            if stage <= 1: 
                status_txt, color = "🔴 Oczekujący", "#EF4444"
            elif stage < 7: 
                status_txt, color = "🟡 Aktywny (W trasie)", "#FFB81C"
            else: 
                status_txt, color = "🟢 Zakończony", "#10B981"
            
            map_data.append({
                "Event": row['Event'], "Lokalizacja": row['Lokalizacja'], "Auto": row.get('Auto', ''), 
                "Status": status_txt, "Kolor": color, "lat": lat, "lon": lon
            })
            
    if not map_data:
        st.warning("Uzupełnij kolumnę 'Lokalizacja' w Harmonogramie, aby aktywować radar.")
        return
        
    df_map = pd.DataFrame(map_data)
    fig = px.scatter_mapbox(
        df_map, lat="lat", lon="lon", hover_name="Event", 
        hover_data={"lat": False, "lon": False, "Status": True, "Auto": True, "Lokalizacja": True}, 
        color="Status", 
        color_discrete_map={"🔴 Oczekujący": "#EF4444", "🟡 Aktywny (W trasie)": "#FFB81C", "🟢 Zakończony": "#10B981"}, 
        zoom=3.5, height=550
    )
    fig.update_layout(
        mapbox_style="carto-darkmatter", margin={"r":0,"t":0,"l":0,"b":0}, 
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0.5)", font=dict(color="white"))
    )
    st.plotly_chart(fig, use_container_width=True)


def render_hub(conn, df_tasks, df_schedule, df_carriers, df_links, df_notes):
    role = st.session_state.get("role")
    
    # ==========================================
    # WIDOK ADMINA
    # ==========================================
    if role == "admin":
        st.markdown("""<div class="aviation-banner">
<h1>⚙️ FLIGHT DECK (CMS)</h1>
<p>Zarządzanie infrastrukturą, zadaniami, flotą i logbookiem.</p>
</div>""", unsafe_allow_html=True)
        
        tab_a1, tab_a2, tab_a3, tab_a4, tab_a5 = st.tabs(["📋 REJESTR ZADAŃ", "📅 HARMONOGRAM", "🚚 FLOTA", "🔗 SYSTEMY", "📝 LOGBOOK"])
        
        with tab_a1:
            edytowane_zadania = st.data_editor(df_tasks, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"Status": st.column_config.SelectboxColumn(options=["Do zrobienia", "W trakcie", "Zrobione"])})
            if st.button("🛫 Wgraj aktualizację zadań", type="primary"): 
                with st.spinner("Przesyłanie do bazy..."):
                    try:
                        conn.update(worksheet="Arkusz1", data=clean_for_gsheets(edytowane_zadania))
                        time.sleep(1.5)
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Błąd zapisu: {e}")
                    
        with tab_a2:
            cols_schedule = ["Event", "Lokalizacja", "Auto", "1_Zaladunek", "2_Montaz_Od", "2_Montaz_Do", "3_Puste_Casy_1", "3_Puste_Casy_2", "4_Dzien_Klienta", "5_Dostawa_Pustych", "6_Odbior_Pelnych", "7_Rozladunek"]
            date_cols_config = {col: st.column_config.DateColumn(col, format="YYYY-MM-DD") for col in cols_schedule if col not in ["Event", "Auto", "Lokalizacja"]}
            edytowane_harm = st.data_editor(df_schedule, num_rows="dynamic", use_container_width=True, hide_index=True, column_config=date_cols_config)
            if st.button("🛫 Wgraj aktualizację harmonogramu", type="primary"): 
                with st.spinner("Przesyłanie do bazy..."):
                    try:
                        conn.update(worksheet="Harmonogram", data=clean_for_gsheets(edytowane_harm))
                        time.sleep(1.5)
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Błąd zapisu: {e}")
                    
        with tab_a3:
            edytowane_przewoz = st.data_editor(df_carriers, num_rows="dynamic", use_container_width=True, hide_index=True)
            if st.button("🛫 Wgraj aktualizację floty", type="primary"): 
                with st.spinner("Przesyłanie do bazy..."):
                    try:
                        conn.update(worksheet="Przewoznicy", data=clean_for_gsheets(edytowane_przewoz))
                        time.sleep(1.5)
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Błąd zapisu: {e}")
                    
        with tab_a4:
            edytowane_linki = st.data_editor(df_links, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"URL": st.column_config.LinkColumn()})
            if st.button("🛫 Wgraj aktualizację systemów", type="primary"): 
                with st.spinner("Przesyłanie do bazy..."):
                    try:
                        conn.update(worksheet="Linki", data=clean_for_gsheets(edytowane_linki))
                        time.sleep(1.5)
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Błąd zapisu: {e}")
                    
        with tab_a5:
            col_hist, col_form = st.columns([3, 2], gap="large")
            with col_form:
                st.markdown("""<div style="background: white; padding: 20px; border-radius: 8px 8px 0 0; border-bottom: 2px solid #F3F5F7; border-top: 5px solid #FFB81C; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
<h3 style="margin: 0; color: #002244; font-weight: 900; font-size: 18px;">📡 Nadaj Komunikat</h3>
</div>""", unsafe_allow_html=True)
                with st.form("logbook_form_admin", clear_on_submit=True):
                    kto = st.text_input("Identyfikator (Kto):", placeholder="np. Janek / Dyspozycja")
                    wiadomosc = st.text_area("Treść komunikatu:", placeholder="Wpisz pilną wiadomość...", height=150)
                    if st.form_submit_button("Wyślij do systemu ➔", use_container_width=True):
                        if kto.strip() != "" and wiadomosc.strip() != "":
                            with st.spinner("Nadawanie komunikatu..."):
                                try:
                                    nowy_wpis = pd.DataFrame([{"Data": datetime.now().strftime("%Y-%m-%d | %H:%M:%S"), "Kto": kto, "Wiadomość": wiadomosc}])
                                    conn.update(worksheet="Notatnik", data=clean_for_gsheets(pd.concat([df_notes, nowy_wpis], ignore_index=True)))
                                    time.sleep(1.5)
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e: st.error(f"Błąd zapisu: {e}")
                                
            with col_hist:
                df_notes_clean = df_notes[df_notes["Wiadomość"].str.strip() != ""]
                for idx, row in df_notes_clean.iloc[::-1].iterrows():
                    st.markdown(f"""<div style="background-color: #1E293B; border-left: 6px solid #FFB81C; border-radius: 6px; padding: 18px; margin-bottom: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
<span style="color: #94A3B8; font-size: 11px; font-family: monospace;">🗓️ {row['Data']}</span>
<span style="background: #002244; color: #FFB81C; padding: 3px 12px; border-radius: 20px; font-size: 11px; font-weight: 800; border: 1px solid #FFB81C;">👤 {row['Kto']}</span>
</div>
<div style="color: #F8FAFC; font-size: 16px; font-weight: 400; font-family: monospace; letter-spacing: 0.5px;">"{row['Wiadomość']}"</div>
</div>""", unsafe_allow_html=True)
                    if st.button("✂️ CUT", key=f"del_{idx}"):
                        with st.spinner("Usuwanie..."):
                            try:
                                conn.update(worksheet="Notatnik", data=clean_for_gsheets(df_notes.drop(idx)))
                                time.sleep(1.5)
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e: st.error(f"Błąd usuwania: {e}")

    # ==========================================
    # WIDOK ZESPOŁU
    # ==========================================
    elif role == "team":
        colA, colB = st.columns([5, 1])
        with colA: 
            st.markdown("""<div class="aviation-banner">
<h1>🌐 GLOBAL OPERATIONS HUB</h1>
<p>Bieżący monitoring statusów logistycznych i komunikacja</p>
</div>""", unsafe_allow_html=True)
        with colB: 
            st.write(""); st.write("")
            if st.button("🔄 POBIERZ DANE", use_container_width=True): 
                st.cache_data.clear()
                st.rerun()
        
        tab_radar, tab1, tab2, tab3, tab4, tab5 = st.tabs(["🗺️ RADAR", "🚦 EVENTY", "📋 KANBAN", "🚚 FLOTA", "🔗 PORTALE", "📝 LOGBOOK"])
        
        with tab_radar: 
            render_radar(df_schedule)
            
        with tab1:
            st.markdown("<br>", unsafe_allow_html=True)
            for _, row in df_schedule[df_schedule["Event"].str.strip() != ""].iterrows():
                etap = get_current_stage(row)
                stages = [
                    {"name": "Załadunek", "date": row.get('1_Zaladunek')}, 
                    {"name": "Montaż", "date": row.get('2_Montaz_Od')}, 
                    {"name": "Casy", "date": row.get('3_Puste_Casy_1')}, 
                    {"name": "Targi", "date": row.get('4_Dzien_Klienta')}, 
                    {"name": "Dostawa Casów", "date": row.get('5_Dostawa_Pustych')}, 
                    {"name": "Odbiór Pełn.", "date": row.get('6_Odbior_Pelnych')}, 
                    {"name": "Rozładunek", "date": row.get('7_Rozladunek')}
                ]
                
                stepper_html = f"""<div class="timeline-container">
<div class="timeline-header">
<div class="timeline-title">✈️ {row['Event']} <span style='font-size:14px; color: #6B7280; font-weight:normal;'>({row.get('Lokalizacja', '')})</span></div>
<div class="timeline-truck">TRUCK: {row.get('Auto', 'Brak')}</div>
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

                st.markdown(stepper_html + "</div></div>", unsafe_allow_html=True)
                
        with tab2:
            df_tasks_clean = df_tasks[df_tasks["Temat"].str.strip() != ""]
            
            # --- ZABEZPIECZENIE PRZED LITERÓWKAMI ---
            # Tworzymy ustandaryzowaną kolumnę "Status", która eliminuje spacje i wielkie litery
            status_norm = df_tasks_clean["Status"].str.strip().str.lower()
            
            k_todo, k_inprog, k_done = st.columns(3)
            with k_todo:
                st.markdown("<h3 style='color: #EF4444; font-size:16px; font-weight:800;'>🔴 STANDBY (Do zrobienia)</h3>", unsafe_allow_html=True)
                # Filtrujemy wg znormalizowanej wartości
                for _, row in df_tasks_clean[status_norm == "do zrobienia"].iterrows(): 
                    st.markdown(f"""<div class='task-card todo'>
<div class='task-title'>{row['Zadanie']}</div>
<div class='task-assignee'>👨‍✈️ {row['Osoba']}</div>
<div class='task-notes'>{row['Notatki']}</div>
</div>""", unsafe_allow_html=True)
            with k_inprog:
                st.markdown("<h3 style='color: #FFB81C; font-size:16px; font-weight:800;'>🟡 IN TRANSIT (W trakcie)</h3>", unsafe_allow_html=True)
                for _, row in df_tasks_clean[status_norm == "w trakcie"].iterrows(): 
                    st.markdown(f"""<div class='task-card inprogress'>
<div class='task-title'>{row['Zadanie']}</div>
<div class='task-assignee'>👨‍✈️ {row['Osoba']}</div>
<div class='task-notes'>{row['Notatki']}</div>
</div>""", unsafe_allow_html=True)
            with k_done:
                st.markdown("<h3 style='color: #10B981; font-size:16px; font-weight:800;'>🟢 ARRIVED (Zrobione)</h3>", unsafe_allow_html=True)
                for _, row in df_tasks_clean[status_norm == "zrobione"].iterrows(): 
                    st.markdown(f"""<div class='task-card done'>
<div class='task-title' style='text-decoration: line-through; color: #9CA3AF;'>{row['Zadanie']}</div>
<div class='task-assignee'>👨‍✈️ {row['Osoba']}</div>
</div>""", unsafe_allow_html=True)
                    
        with tab3:
            cols_c = st.columns(3)
            for index, row in df_carriers[df_carriers["Firma"].str.strip() != ""].reset_index(drop=True).iterrows():
                with cols_c[index % 3]: 
                    st.markdown(f"""<div class="terminal-card" style="min-height: 220px;">
<div>
<div class="terminal-card-category">🚛 {row.get('Typ_Auta', 'Typ Nieznany')}</div>
<div class="terminal-card-title">{row['Firma']}</div>
<div class="terminal-card-desc">
<strong>📍 Adres:</strong> {row.get('Adres', '---')}<br>
<strong>🏢 NIP:</strong> {row.get('NIP', '---')}<br>
<strong>📞 Tel:</strong> {row.get('Telefon', '---')}<br>
<strong>👤 Kontakt:</strong> {row.get('Kontakt', '---')}<br>
<br><i>{row.get('Uwagi', '')}</i>
</div>
</div>
</div>""", unsafe_allow_html=True)
                    
        with tab4:
            df_links_clean = df_links[df_links["Kategoria"].str.strip() != ""]
            for kategoria in sorted(df_links_clean["Kategoria"].unique().tolist()):
                st.markdown(f"<h4 style='color: #002244; font-weight: 900; letter-spacing: 1px; margin-top:20px;'>📂 {kategoria.upper()}</h4>", unsafe_allow_html=True)
                kolumny = st.columns(4) 
                for index, row in df_links_clean[df_links_clean["Kategoria"] == kategoria].reset_index(drop=True).iterrows():
                    with kolumny[index % 4]: 
                        st.markdown(f"""<div class="terminal-card">
<div>
<div class="terminal-card-category">🌐 P.O.D.</div>
<div class="terminal-card-title">{row['Nazwa']}</div>
<div class="terminal-card-desc">{row['Opis']}</div>
</div>
<a href="{row['URL']}" target="_blank" class="terminal-card-btn">Zainicjuj Połączenie ➔</a>
</div>""", unsafe_allow_html=True)
                        
        with tab5:
            col_hist, col_form = st.columns([3, 2], gap="large")
            with col_form:
                st.markdown("""<div style="background: white; padding: 20px; border-radius: 8px 8px 0 0; border-bottom: 2px solid #F3F5F7; border-top: 5px solid #FFB81C; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
<h3 style="margin: 0; color: #002244; font-weight: 900; font-size: 18px;">📡 Nadaj Komunikat</h3>
</div>""", unsafe_allow_html=True)
                with st.form("logbook_form_team", clear_on_submit=True):
                    kto = st.text_input("Identyfikator (Kto):")
                    wiadomosc = st.text_area("Treść komunikatu:", height=150)
                    if st.form_submit_button("Wyślij do systemu ➔", use_container_width=True):
                        if kto.strip() != "" and wiadomosc.strip() != "":
                            with st.spinner("Nadawanie komunikatu..."):
                                try:
                                    nowy_wpis = pd.DataFrame([{"Data": datetime.now().strftime("%Y-%m-%d | %H:%M:%S"), "Kto": kto, "Wiadomość": wiadomosc}])
                                    conn.update(worksheet="Notatnik", data=clean_for_gsheets(pd.concat([df_notes, nowy_wpis], ignore_index=True)))
                                    time.sleep(1.5)
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e: 
                                    st.error(f"Błąd zapisu: {e}")
                                    
            with col_hist:
                for idx, row in df_notes[df_notes["Wiadomość"].str.strip() != ""].iloc[::-1].iterrows():
                    st.markdown(f"""<div style="background-color: #1E293B; border-left: 6px solid #FFB81C; border-radius: 6px; padding: 18px; margin-bottom: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
<span style="color: #94A3B8; font-size: 11px; font-family: monospace;">🗓️ {row['Data']}</span>
<span style="background: #002244; color: #FFB81C; padding: 3px 12px; border-radius: 20px; font-size: 11px; font-weight: 800; border: 1px solid #FFB81C;">👤 {row['Kto']}</span>
</div>
<div style="color: #F8FAFC; font-size: 16px; font-weight: 400; font-family: monospace; letter-spacing: 0.5px;">"{row['Wiadomość']}"</div>
</div><br>""", unsafe_allow_html=True)
