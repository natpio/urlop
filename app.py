import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import plotly.express as px
from geopy.geocoders import Nominatim
from fpdf import FPDF
import qrcode
import tempfile
import os
import hashlib
import difflib
import time

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
# 2. AUTORYZACJA
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
        if password == st.secrets.get("ADMIN_PASSWORD", "MojeTajneHaslo123"):
            st.session_state["role"] = "admin"
            st.rerun()
        elif password == st.secrets.get("TEAM_PASSWORD", "Urlop2026"):
            st.session_state["role"] = "team"
            st.rerun()
        elif password:
            st.error("❌ Odmowa dostępu. Nierozpoznany kod.")
    st.stop()

# ==========================================
# 3. POŁĄCZENIE Z BAZĄ DANYCH (TARCZA ANTI-429)
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

# Zabezpieczenie przed limitem 60 zapytań/minutę
dane_pobrane = False
for attempt in range(3):
    try:
        # Wydłużamy TTL do 10 minut. Każdy zapis i tak sam zresetuje cache.
        df_tasks = conn.read(worksheet="Arkusz1", ttl=600).dropna(how="all")
        df_links = conn.read(worksheet="Linki", ttl=600).dropna(how="all")
        df_carriers = conn.read(worksheet="Przewoznicy", ttl=600).dropna(how="all")
        df_schedule = conn.read(worksheet="Harmonogram", ttl=600).dropna(how="all")
        df_notes = conn.read(worksheet="Notatnik", ttl=600).dropna(how="all")
        df_miejsca = conn.read(worksheet="Miejsca", ttl=600).dropna(how="all")
        df_zlecenia = conn.read(worksheet="Zlecenia", ttl=600).dropna(how="all")
        dane_pobrane = True
        break # Udało się, wychodzimy z pętli
    except Exception as e:
        if '429' in str(e) or 'Quota exceeded' in str(e):
            if attempt < 2:
                st.toast(f"⏳ Oczekiwanie na przepustowość Google (Limit). Próba {attempt+2}/3...")
                time.sleep(8) # Czekamy 8 sekund i próbujemy ponownie
            else:
                st.error("⚠️ Serwery Google są przeciążone zbyt wieloma zapytaniami na minutę. Zrób 60 sekund przerwy i odśwież stronę.")
                st.stop()
        else:
            st.error(f"⚠️ Krytyczny błąd bazy: {e}")
            st.stop()

if dane_pobrane:
    # Wymuszanie typów danych
    for df, cols in [
        (df_tasks, ["Temat", "Zadanie", "Osoba", "Termin", "Status", "Notatki"]),
        (df_links, ["Nazwa", "URL", "Opis", "Kategoria"]),
        (df_carriers, ["Firma", "Adres", "NIP", "Kontakt", "Telefon", "Typ_Auta", "Uwagi"]),
        (df_notes, ["Data", "Kto", "Wiadomość"]),
        (df_miejsca, ["Nazwa do listy", "Nazwa pełna / Firma", "Ulica i numer", "Kod pocztowy", "Miasto", "Kraj"])
    ]:
        for col in cols:
            if col not in df.columns: df[col] = ""
            df[col] = df[col].fillna("").astype(str)

    if "Numer zlecenia" not in df_zlecenia.columns: df_zlecenia["Numer zlecenia"] = ""
    df_zlecenia["Numer zlecenia"] = df_zlecenia["Numer zlecenia"].astype(str).replace('nan', '')

    cols_schedule = ["Event", "Lokalizacja", "Auto", "1_Zaladunek", "2_Montaz_Od", "2_Montaz_Do", "3_Puste_Casy_1", "3_Puste_Casy_2", "4_Dzien_Klienta", "5_Dostawa_Pustych", "6_Odbior_Pelnych", "7_Rozladunek"]
    for col in cols_schedule: 
        if col not in df_schedule.columns: df_schedule[col] = None
        if col not in ["Event", "Auto", "Lokalizacja"]:
            df_schedule[col] = pd.to_datetime(df_schedule[col], errors='coerce').dt.date
        else:
            df_schedule[col] = df_schedule[col].fillna("").astype(str)

# ==========================================
# 4. FUNKCJE BIZNESOWE (Gantt, Radar, Czystość)
# ==========================================
def clean_for_gsheets(df):
    cleaned = df.copy()
    for col in cleaned.columns:
        cleaned[col] = cleaned[col].astype(str).replace(['NaT', 'nan', 'None', '<NA>', 'NaN'], '')
    return cleaned

def get_current_stage(row):
    today = datetime.now().date()
    current_stage = 0
    stages_dates = [row.get("1_Zaladunek"), row.get("2_Montaz_Od"), row.get("3_Puste_Casy_1"), row.get("4_Dzien_Klienta"), row.get("5_Dostawa_Pustych"), row.get("6_Odbior_Pelnych"), row.get("7_Rozladunek")]
    for i, date_val in enumerate(stages_dates):
        if pd.notnull(date_val) and today >= date_val: current_stage = i + 1 
    if current_stage == 0 and pd.notnull(stages_dates[0]): current_stage = 1
    return current_stage

@st.cache_data(ttl=3600)
def get_coordinates(city_name):
    if not city_name or city_name.strip() == "": return None, None
    try:
        location = Nominatim(user_agent="logistics_hub_agent").geocode(city_name)
        if location: return location.latitude, location.longitude
        return None, None
    except: return None, None

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
            map_data.append({"Event": row['Event'], "Lokalizacja": row['Lokalizacja'], "Auto": row.get('Auto', ''), "Status": status_txt, "Kolor": color, "lat": lat, "lon": lon})
    if not map_data:
        st.warning("Uzupełnij 'Lokalizacja' w Harmonogramie, aby aktywować radar.")
        return
    df_map = pd.DataFrame(map_data)
    fig = px.scatter_mapbox(df_map, lat="lat", lon="lon", hover_name="Event", hover_data={"lat": False, "lon": False, "Status": True, "Auto": True, "Lokalizacja": True}, color="Status", color_discrete_map={"🔴 Oczekujący": "#EF4444", "🟡 Aktywny (W trasie)": "#FFB81C", "🟢 Zakończony": "#10B981"}, zoom=3.5, height=550)
    fig.update_layout(mapbox_style="carto-darkmatter", margin={"r":0,"t":0,"l":0,"b":0}, legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0.5)", font=dict(color="white")))
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 5. KREATOR ZLECEŃ PDF (SILNIK)
# ==========================================
def pdf_sanitize(text):
    text = str(text)
    replacements = {'ą':'a', 'ć':'c', 'ę':'e', 'ł':'l', 'ń':'n', 'ó':'o', 'ś':'s', 'ź':'z', 'ż':'z', 'Ą':'A', 'Ć':'C', 'Ę':'E', 'Ł':'L', 'Ń':'N', 'Ó':'O', 'Ś':'S', 'Ź':'Z', 'Ż':'Z', '€':'EUR', '–':'-', '—':'-', '”':'"', '„':'"', '’':"'", '“':'"', '\xa0':' '}
    for pl, eng in replacements.items(): text = text.replace(pl, eng)
    return text.encode('latin-1', 'ignore').decode('latin-1')

class PRO_TransportOrder(FPDF):
    def __init__(self, watermark_text="SQM", opiekun="PD"):
        super().__init__()
        self.watermark_text = pdf_sanitize(watermark_text)
        self.opiekun = opiekun
    def add_watermark(self):
        self.set_font("Arial", 'B', 45); self.set_text_color(245, 245, 245) 
        for j in range(80, 297, 45):
            przesuniecie = 35 if (j // 45) % 2 == 0 else 0
            for i in range(-20, 210, 70): self.text(i + przesuniecie, j, self.watermark_text)
        self.set_text_color(0, 0, 0)
    def header(self):
        try:
            if os.path.exists("logosqm.png"):
                self.image("logosqm.png", 10, 8, 50)
            elif os.path.exists("logosqm.jpg"):
                self.image("logosqm.jpg", 10, 8, 50)
        except Exception as e:
            pass
        self.set_font("Arial", 'B', 18); self.set_text_color(40, 40, 40); self.set_xy(65, 12); self.cell(105, 8, pdf_sanitize("TRANSPORT ORDER"), ln=True, align='R')
        self.set_font("Arial", 'B', 11); self.set_text_color(100, 100, 100); self.set_xy(65, 20); self.cell(105, 5, pdf_sanitize("ZLECENIE TRANSPORTOWE"), ln=True, align='R')
        self.set_font("Arial", '', 8); self.set_xy(65, 26); self.cell(105, 5, pdf_sanitize("Logistics Department"), ln=True, align='R'); self.ln(15)
    def footer(self):
        self.set_y(-30); self.set_font("Arial", 'I', 10); self.set_text_color(25, 118, 210); self.cell(0, 5, pdf_sanitize("Thank you for your cooperation! / Dziękujemy za współpracę!"), ln=True, align='C')
        self.set_font("Arial", '', 8); self.set_text_color(100, 100, 100)
        email = "logistics@company.com" if self.opiekun == "PD" else "transport@company.com"
        self.cell(0, 5, pdf_sanitize(f"Generated by Global Logistics Terminal | {email}"), ln=True, align='C')

def generate_pro_pdf(dane):
    pdf = PRO_TransportOrder(opiekun=dane.get('opiekun', 'PD'))
    pdf.alias_nb_pages(); pdf.add_page(); pdf.add_watermark()
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(f"VERIFY: {dane['nr']}\nSYS: TERMINAL PRO")
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        img_qr.save(tmp, format="PNG"); qr_path = tmp.name
    pdf.image(qr_path, 175, 10, 25)
    if os.path.exists(qr_path): os.remove(qr_path)
    pdf.set_xy(10, 40); pdf.set_font("Arial", 'B', 9); pdf.set_fill_color(25, 118, 210); pdf.set_text_color(255, 255, 255)
    pdf.cell(25, 8, pdf_sanitize(" REF "), border=0, fill=True, align='C'); pdf.set_fill_color(245, 245, 245); pdf.set_text_color(40, 40, 40)
    pdf.cell(60, 8, pdf_sanitize(f" {dane['nr']}"), border=0, fill=True); pdf.cell(5, 8, "", border=0) 
    pdf.set_fill_color(25, 118, 210); pdf.set_text_color(255, 255, 255); pdf.cell(25, 8, pdf_sanitize(" DATE "), border=0, fill=True, align='C')
    pdf.set_fill_color(245, 245, 245); pdf.set_text_color(40, 40, 40); pdf.cell(60, 8, pdf_sanitize(f" {datetime.now().strftime('%d.%m.%Y')}"), border=0, fill=True); pdf.ln(12)

    def draw_section_header(num, title):
        pdf.set_fill_color(25, 118, 210); pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", 'B', 12)
        pdf.cell(10, 10, pdf_sanitize(str(num).zfill(2)), fill=True, align='C'); pdf.set_text_color(40, 40, 40); pdf.cell(5, 10, "", border=0); pdf.cell(0, 10, pdf_sanitize(title), ln=True); pdf.ln(2)

    def draw_row(label, val, border_b=True):
        x_start, y_start = pdf.get_x(), pdf.get_y()
        pdf.set_font("Arial", 'B', 8); pdf.set_text_color(100, 100, 100); pdf.cell(65, 6, pdf_sanitize(label), border=0)
        pdf.set_font("Arial", 'B', 10); pdf.set_text_color(40, 40, 40); pdf.set_xy(x_start + 65, y_start + 0.5)
        pdf.multi_cell(125, 5, pdf_sanitize(val), border=0)
        y_end = pdf.get_y() + 1.5
        if border_b: pdf.set_draw_color(230, 230, 230); pdf.line(10, y_end, 200, y_end)
        pdf.set_xy(10, y_end + 2)

    draw_section_header(1, "PARTIES & ASSETS / STRONY I POJAZD")
    draw_row("CONTRACTOR / PRZEWOŹNIK:", dane['przewoznik_detale'])
    draw_row("VEHICLE & DRIVER / AUTO I KIEROWCA:", dane['auto'] if dane['auto'] else "TBA / Do podania")
    draw_row("VALUATION MODEL / TRYB WYCENY:", dane['typ_zlecenia'], border_b=False); pdf.ln(4)

    draw_section_header(2, "LOGISTICS TIMELINE / HARMONOGRAM")
    draw_row("LOADING PLACE / MIEJSCE ZAŁADUNKU:", dane['zaladunek'])
    draw_row("LOADING DATE / DATA ZAŁADUNKU:", dane['data_zal'])
    draw_row("UNLOADING PLACE / MIEJSCE ROZŁADUNKU:", dane['rozladunek'])
    if dane['typ_zlecenia'] == "Pełny event":
        draw_row("UNLOADING DATE / DATA ROZŁADUNKU:", dane['data_roz'])
        draw_row("EMPTIES IN / ODBIÓR PUSTYCH:", dane['data_emp_in'])
        draw_row("RETURN LOAD / DATA POWROTU:", dane['data_emp_out'], border_b=False)
    else: draw_row("UNLOADING DATE / DATA ROZŁADUNKU:", dane['data_roz'], border_b=False)
    pdf.ln(4)

    draw_section_header(3, "FINANCIALS & CARGO / FINANSE I ŁADUNEK")
    sy = pdf.get_y()
    pdf.set_xy(120, sy); pdf.set_fill_color(25, 118, 210); pdf.rect(120, sy, 80, 25, 'F')
    pdf.set_xy(125, sy + 3); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(255, 255, 255)
    pdf.cell(70, 5, pdf_sanitize("TOTAL NET RATE / KWOTA NETTO"), ln=True)
    pdf.set_xy(125, sy + 10); pdf.set_font("Arial", 'B', 20)
    pdf.cell(70, 10, pdf_sanitize(f"{dane['stawka']} {dane['waluta']}"), ln=True)
    
    pdf.set_xy(10, sy); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(100, 100, 100); pdf.cell(55, 5, pdf_sanitize("CARGO TYPE / TOWAR:"), border=0)
    pdf.set_font("Arial", 'B', 10); pdf.set_text_color(40, 40, 40); pdf.set_xy(65, sy); pdf.multi_cell(50, 5, pdf_sanitize("Exhibition Structures / AV Equipment"))
    pdf.set_xy(10, pdf.get_y() + 2); pdf.set_font("Arial", 'B', 8); pdf.set_text_color(100, 100, 100); pdf.cell(55, 5, pdf_sanitize("GROSS WEIGHT / WAGA BRUTTO:"), border=0)
    pdf.set_font("Arial", 'B', 10); pdf.set_text_color(40, 40, 40); pdf.set_xy(65, pdf.get_y()); pdf.cell(50, 5, pdf_sanitize(f"{dane['waga']} kg"))
    
    pdf.set_xy(10, sy + 35); draw_section_header(4, "SPECIAL PROVISIONS / UWAGI SPECJALNE")
    pdf.set_font("Arial", 'I', 10); pdf.multi_cell(0, 6, pdf_sanitize(dane['uwagi']))

    return bytes(pdf.output(dest='S').encode('latin1'))

# ==========================================
# 6. WSPÓLNY PANEL BOCZNY (NAWIGACJA)
# ==========================================
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=60)
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.session_state["role"] == "admin":
        st.success("👨‍✈️ CAPTAIN (ADMIN)")
    else:
        st.info("👨‍💼 CREW (ZESPÓŁ)")
        
    nav_mode = st.radio("Nawigacja Modułów:", ["🌍 Hub Operacyjny", "📄 Kreator Zleceń PRO"])
    
    st.markdown("---")
    if st.button("🚪 Zakończ zmianę", use_container_width=True):
        st.session_state["role"] = None
        st.rerun()

# =====================================================================
# WIDOK 1: HUB OPERACYJNY (GŁÓWNY SYSTEM)
# =====================================================================
if nav_mode == "🌍 Hub Operacyjny":
    if st.session_state["role"] == "admin":
        st.markdown("""<div class="aviation-banner"><h1>⚙️ FLIGHT DECK (CMS)</h1><p>Zarządzanie infrastrukturą, zadaniami, flotą i logbookiem.</p></div>""", unsafe_allow_html=True)
        tab_a1, tab_a2, tab_a3, tab_a4, tab_a5 = st.tabs(["📋 REJESTR ZADAŃ", "📅 HARMONOGRAM", "🚚 FLOTA", "🔗 SYSTEMY", "📝 LOGBOOK"])
        with tab_a1:
            edytowane_zadania = st.data_editor(df_tasks, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"Status": st.column_config.SelectboxColumn(options=["Do zrobienia", "W trakcie", "Zrobione"])})
            if st.button("🛫 Wgraj aktualizację zadań", type="primary"): 
                with st.spinner("Przesyłanie do bazy..."):
                    try:
                        conn.update(worksheet="Arkusz1", data=clean_for_gsheets(edytowane_zadania))
                        time.sleep(1.5)
                        st.cache_data.clear(); st.rerun()
                    except Exception as e: st.error(f"Błąd zapisu: {e}")
        with tab_a2:
            date_cols_config = {col: st.column_config.DateColumn(col, format="YYYY-MM-DD") for col in cols_schedule if col not in ["Event", "Auto", "Lokalizacja"]}
            edytowane_harm = st.data_editor(df_schedule, num_rows="dynamic", use_container_width=True, hide_index=True, column_config=date_cols_config)
            if st.button("🛫 Wgraj aktualizację harmonogramu", type="primary"): 
                with st.spinner("Przesyłanie do bazy..."):
                    try:
                        conn.update(worksheet="Harmonogram", data=clean_for_gsheets(edytowane_harm))
                        time.sleep(1.5)
                        st.cache_data.clear(); st.rerun()
                    except Exception as e: st.error(f"Błąd zapisu: {e}")
        with tab_a3:
            edytowane_przewoz = st.data_editor(df_carriers, num_rows="dynamic", use_container_width=True, hide_index=True)
            if st.button("🛫 Wgraj aktualizację floty", type="primary"): 
                with st.spinner("Przesyłanie do bazy..."):
                    try:
                        conn.update(worksheet="Przewoznicy", data=clean_for_gsheets(edytowane_przewoz))
                        time.sleep(1.5)
                        st.cache_data.clear(); st.rerun()
                    except Exception as e: st.error(f"Błąd zapisu: {e}")
        with tab_a4:
            edytowane_linki = st.data_editor(df_links, num_rows="dynamic", use_container_width=True, hide_index=True, column_config={"URL": st.column_config.LinkColumn()})
            if st.button("🛫 Wgraj aktualizację systemów", type="primary"): 
                with st.spinner("Przesyłanie do bazy..."):
                    try:
                        conn.update(worksheet="Linki", data=clean_for_gsheets(edytowane_linki))
                        time.sleep(1.5)
                        st.cache_data.clear(); st.rerun()
                    except Exception as e: st.error(f"Błąd zapisu: {e}")
        with tab_a5:
            col_hist, col_form = st.columns([3, 2], gap="large")
            with col_form:
                st.markdown("""<div style="background: white; padding: 20px; border-radius: 8px 8px 0 0; border-bottom: 2px solid #F3F5F7; border-top: 5px solid #FFB81C; box-shadow: 0 2px 4px rgba(0,0,0,0.02);"><h3 style="margin: 0; color: #002244; font-weight: 900; font-size: 18px;">📡 Nadaj Komunikat</h3></div>""", unsafe_allow_html=True)
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
                                    st.cache_data.clear(); st.rerun()
                                except Exception as e: st.error(f"Błąd zapisu: {e}")
            with col_hist:
                df_notes_clean = df_notes[df_notes["Wiadomość"].str.strip() != ""]
                for idx, row in df_notes_clean.iloc[::-1].iterrows():
                    st.markdown(f"""<div style="background-color: #1E293B; border-left: 6px solid #FFB81C; border-radius: 6px; padding: 18px; margin-bottom: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"><div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;"><span style="color: #94A3B8; font-size: 11px; font-family: monospace;">🗓️ {row['Data']}</span><span style="background: #002244; color: #FFB81C; padding: 3px 12px; border-radius: 20px; font-size: 11px; font-weight: 800; border: 1px solid #FFB81C;">👤 {row['Kto']}</span></div><div style="color: #F8FAFC; font-size: 16px; font-weight: 400; font-family: monospace; letter-spacing: 0.5px;">"{row['Wiadomość']}"</div></div>""", unsafe_allow_html=True)
                    if st.button("✂️ CUT", key=f"del_{idx}"):
                        with st.spinner("Usuwanie..."):
                            try:
                                conn.update(worksheet="Notatnik", data=clean_for_gsheets(df_notes.drop(idx)))
                                time.sleep(1.5)
                                st.cache_data.clear(); st.rerun()
                            except Exception as e: st.error(f"Błąd usuwania: {e}")

    elif st.session_state["role"] == "team":
        colA, colB = st.columns([5, 1])
        with colA: st.markdown("""<div class="aviation-banner"><h1>🌐 GLOBAL OPERATIONS HUB</h1><p>Bieżący monitoring statusów logistycznych i komunikacja</p></div>""", unsafe_allow_html=True)
        with colB: 
            st.write(""); st.write("")
            if st.button("🔄 POBIERZ DANE", use_container_width=True): st.cache_data.clear(); st.rerun()
        
        tab_radar, tab1, tab2, tab3, tab4, tab5 = st.tabs(["🗺️ RADAR", "🚦 EVENTY", "📋 KANBAN", "🚚 FLOTA", "🔗 PORTALE", "📝 LOGBOOK"])
        with tab_radar: render_radar(df_schedule)
        with tab1:
            st.markdown("<br>", unsafe_allow_html=True)
            for _, row in df_schedule[df_schedule["Event"].str.strip() != ""].iterrows():
                etap = get_current_stage(row)
                stages = [{"name": "Załadunek", "date": row.get('1_Zaladunek')}, {"name": "Montaż", "date": row.get('2_Montaz_Od')}, {"name": "Casy", "date": row.get('3_Puste_Casy_1')}, {"name": "Targi", "date": row.get('4_Dzien_Klienta')}, {"name": "Dostawa Casów", "date": row.get('5_Dostawa_Pustych')}, {"name": "Odbiór Pełn.", "date": row.get('6_Odbior_Pelnych')}, {"name": "Rozładunek", "date": row.get('7_Rozladunek')}]
                stepper_html = f"""<div class="timeline-container"><div class="timeline-header"><div class="timeline-title">✈️ {row['Event']} <span style='font-size:14px; color: #6B7280; font-weight:normal;'>({row.get('Lokalizacja', '')})</span></div><div class="timeline-truck">TRUCK: {row.get('Auto', 'Brak')}</div></div><div class="stepper-wrapper">"""
                for idx, s in enumerate(stages):
                    step_num, status_class = idx + 1, "completed" if (idx+1) < etap else ("active" if (idx+1) == etap else "")
                    date_str = s['date'].strftime('%d.%m') if pd.notnull(s['date']) else "---"
                    stepper_html += f"""<div class="stepper-item {status_class}"><div class="step-counter">{step_num}</div><div class="step-name">{s['name']}</div><div class="step-date">{date_str}</div></div>"""
                st.markdown(stepper_html + "</div></div>", unsafe_allow_html=True)
        with tab2:
            df_tasks_clean = df_tasks[df_tasks["Temat"].str.strip() != ""]
            k_todo, k_inprog, k_done = st.columns(3)
            with k_todo:
                st.markdown("<h3 style='color: #EF4444; font-size:16px; font-weight:800;'>🔴 STANDBY (Do zrobienia)</h3>", unsafe_allow_html=True)
                for _, row in df_tasks_clean[df_tasks_clean["Status"] == "Do zrobienia"].iterrows(): st.markdown(f"<div class='task-card todo'><div class='task-title'>{row['Zadanie']}</div><div class='task-assignee'>👨‍✈️ {row['Osoba']}</div><div class='task-notes'>{row['Notatki']}</div></div>", unsafe_allow_html=True)
            with k_inprog:
                st.markdown("<h3 style='color: #FFB81C; font-size:16px; font-weight:800;'>🟡 IN TRANSIT (W trakcie)</h3>", unsafe_allow_html=True)
                for _, row in df_tasks_clean[df_tasks_clean["Status"] == "W trakcie"].iterrows(): st.markdown(f"<div class='task-card inprogress'><div class='task-title'>{row['Zadanie']}</div><div class='task-assignee'>👨‍✈️ {row['Osoba']}</div><div class='task-notes'>{row['Notatki']}</div></div>", unsafe_allow_html=True)
            with k_done:
                st.markdown("<h3 style='color: #10B981; font-size:16px; font-weight:800;'>🟢 ARRIVED (Zrobione)</h3>", unsafe_allow_html=True)
                for _, row in df_tasks_clean[df_tasks_clean["Status"] == "Zrobione"].iterrows(): st.markdown(f"<div class='task-card done'><div class='task-title' style='text-decoration: line-through; color: #9CA3AF;'>{row['Zadanie']}</div><div class='task-assignee'>👨‍✈️ {row['Osoba']}</div></div>", unsafe_allow_html=True)
        with tab3:
            cols_c = st.columns(3)
            for index, row in df_carriers[df_carriers["Firma"].str.strip() != ""].reset_index(drop=True).iterrows():
                with cols_c[index % 3]: st.markdown(f"""<div class="terminal-card" style="min-height: 220px;"><div><div class="terminal-card-category">🚛 {row.get('Typ_Auta', 'Typ Nieznany')}</div><div class="terminal-card-title">{row['Firma']}</div><div class="terminal-card-desc"><strong>📍 Adres:</strong> {row.get('Adres', '---')}<br><strong>🏢 NIP:</strong> {row.get('NIP', '---')}<br><strong>📞 Tel:</strong> {row.get('Telefon', '---')}<br><strong>👤 Kontakt:</strong> {row.get('Kontakt', '---')}<br><br><i>{row.get('Uwagi', '')}</i></div></div></div>""", unsafe_allow_html=True)
        with tab4:
            df_links_clean = df_links[df_links["Kategoria"].str.strip() != ""]
            for kategoria in sorted(df_links_clean["Kategoria"].unique().tolist()):
                st.markdown(f"<h4 style='color: #002244; font-weight: 900; letter-spacing: 1px; margin-top:20px;'>📂 {kategoria.upper()}</h4>", unsafe_allow_html=True)
                kolumny = st.columns(4) 
                for index, row in df_links_clean[df_links_clean["Kategoria"] == kategoria].reset_index(drop=True).iterrows():
                    with kolumny[index % 4]: st.markdown(f"""<div class="terminal-card"><div><div class="terminal-card-category">🌐 P.O.D.</div><div class="terminal-card-title">{row['Nazwa']}</div><div class="terminal-card-desc">{row['Opis']}</div></div><a href="{row['URL']}" target="_blank" class="terminal-card-btn">Zainicjuj Połączenie ➔</a></div>""", unsafe_allow_html=True)
        with tab5:
            col_hist, col_form = st.columns([3, 2], gap="large")
            with col_form:
                st.markdown("""<div style="background: white; padding: 20px; border-radius: 8px 8px 0 0; border-bottom: 2px solid #F3F5F7; border-top: 5px solid #FFB81C; box-shadow: 0 2px 4px rgba(0,0,0,0.02);"><h3 style="margin: 0; color: #002244; font-weight: 900; font-size: 18px;">📡 Nadaj Komunikat</h3></div>""", unsafe_allow_html=True)
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
                                    st.cache_data.clear(); st.rerun()
                                except Exception as e: st.error(f"Błąd zapisu: {e}")
            with col_hist:
                for idx, row in df_notes[df_notes["Wiadomość"].str.strip() != ""].iloc[::-1].iterrows():
                    st.markdown(f"""<div style="background-color: #1E293B; border-left: 6px solid #FFB81C; border-radius: 6px; padding: 18px; margin-bottom: 5px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"><div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;"><span style="color: #94A3B8; font-size: 11px; font-family: monospace;">🗓️ {row['Data']}</span><span style="background: #002244; color: #FFB81C; padding: 3px 12px; border-radius: 20px; font-size: 11px; font-weight: 800; border: 1px solid #FFB81C;">👤 {row['Kto']}</span></div><div style="color: #F8FAFC; font-size: 16px; font-weight: 400; font-family: monospace; letter-spacing: 0.5px;">"{row['Wiadomość']}"</div></div><br>""", unsafe_allow_html=True)

# =====================================================================
# WIDOK 2: KREATOR ZLECEŃ PRO (PDF)
# =====================================================================
elif nav_mode == "📄 Kreator Zleceń PRO":
    st.markdown("""<div class="aviation-banner" style="background: linear-gradient(135deg, #1E293B 0%, #334155 100%); border-left: 8px solid #38BDF8;">
    <h1 style="color:white;">📄 KREATOR ZLECEŃ PRO v5.4</h1><p style="color:#CBD5E1;">Zautomatyzowane generowanie zasileń PDF i rejestracja w bazie Zlecenia.</p></div>""", unsafe_allow_html=True)
    
    if "pdf_data" in st.session_state:
        st.success(f"✅ Zlecenie {st.session_state.get('pdf_nr', '')} zapisane bezpiecznie w bazie!")
        st.download_button("📥 POBIERZ DOKUMENT PDF", data=st.session_state["pdf_data"], file_name=st.session_state["pdf_name"], mime="application/pdf", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 ZAMKNIJ I WRÓĆ DO KREATORA", use_container_width=True):
            del st.session_state["pdf_data"]
            st.rerun()
    else:
        tryb_pracy = st.radio("Tryb działania kreatora:", ["Nowe Zlecenie", "Edycja Istniejącego Zlecenia"], horizontal=True)
        
        val_typ_zlecenia, val_waga, val_data_zal, val_data_roz = "Tylko dostawa", 1000, datetime.now().date(), datetime.now().date()
        val_data_emp_in, val_data_emp_out = datetime.now().date(), datetime.now().date()
        val_nazwa_przewoznika, val_detale_przewoznika, val_stawka_final, val_waluta = "Wybierz...", "", 0.0, "EUR"
        val_z_sel, val_z_man, val_c_auto, val_instrukcje, val_podpis = "Magazyn SQM Komorniki", "", "", "Parking strzeżony, pasy zabezpieczające; załadować po długości, casy nie mogą leżeć.", "PD"
        val_wartosc_towaru, val_projekt, wybrane_zlecenie_nr, gs_row_index = 100000, "Brak", None, None
        val_zrodlo = "Przewoźnik z bazy"
        
        lista_eventow = df_schedule['Event'].dropna().unique().tolist() if not df_schedule.empty else []
        lista_miejsc_baza = df_miejsca['Nazwa do listy'].tolist() if not df_miejsca.empty else []
        opcje_lokalizacji = ["Magazyn SQM Komorniki"] + lista_miejsc_baza + ["INNE (wpisz ręcznie)"]
        lista_miast_baza = df_miejsca['Miasto'].dropna().unique().tolist() if not df_miejsca.empty else ["Berlin", "Amsterdam", "Paryż"]
        
        if tryb_pracy == "Edycja Istniejącego Zlecenia":
            if df_zlecenia.empty or len(df_zlecenia[df_zlecenia['Numer zlecenia'].str.strip() != ""]) == 0:
                st.warning("Baza zleceń jest pusta - brak danych do edycji.")
                st.stop()
            else:
                lista_nr = df_zlecenia[df_zlecenia['Numer zlecenia'].str.strip() != ""]['Numer zlecenia'].tolist()
                wybrane_zlecenie_nr = st.selectbox("🎯 Wybierz numer zlecenia do edycji:", lista_nr)
                idx_pd = df_zlecenia[df_zlecenia['Numer zlecenia'] == wybrane_zlecenie_nr].index[0]
                r_edit = df_zlecenia.iloc[idx_pd]
                gs_row_index = int(idx_pd) + 2 
                
                val_typ_zlecenia = "Pełny event" if "TARGI" in str(r_edit.get('Typ', '')) or "CYKL:" in str(r_edit.get('Uwagi / Instrukcje', '')) else "Tylko dostawa"
                try: val_data_zal = datetime.strptime(str(r_edit.get('Data załadunku', '')), "%Y-%m-%d").date()
                except: pass
                try: val_data_roz = datetime.strptime(str(r_edit.get('Data rozładunku', '')), "%Y-%m-%d").date()
                except: pass
                
                stawka_str = str(r_edit.get('Stawka', '0 EUR'))
                if " " in stawka_str:
                    try: val_stawka_final = float(stawka_str.split(" ")[0]); val_waluta = stawka_str.split(" ")[1]
                    except: pass
                else:
                    try: val_stawka_final = float(stawka_str)
                    except: pass
                    
                val_nazwa_przewoznika = str(r_edit.get('Zleceniobiorca', ''))
                val_projekt = str(r_edit.get('ID Projektu', ''))
                val_z_sel = str(r_edit.get('Miejsce Zaladunku', ''))
                
                uwagi_baza = str(r_edit.get('Uwagi / Instrukcje', ''))
                if "AUTO: " in uwagi_baza:
                    try: val_c_auto = uwagi_baza.split("AUTO: ")[1].split(" ||")[0]
                    except: pass
                
                if "WART: " in uwagi_baza:
                    try: val_wartosc_towaru = int(uwagi_baza.split("WART: ")[1].split(" EUR")[0])
                    except: 
                        try: val_wartosc_towaru = int(uwagi_baza.split("WART: ")[1].split(" PLN")[0])
                        except: pass
                        
                if " || " in uwagi_baza:
                    parts = uwagi_baza.split(" || ")
                    if len(parts) >= 4: val_instrukcje = parts[3]
                    elif len(parts) == 3 and "CYKL:" not in parts[2]: val_instrukcje = parts[2]
                
                r_p = df_carriers[df_carriers['Firma'] == val_nazwa_przewoznika]
                if not r_p.empty:
                    r = r_p.iloc[0]
                    val_detale_przewoznika = f"{str(r.get('Firma', ''))}\n{str(r.get('Adres', ''))}\nNIP: {str(r.get('NIP', ''))}\nTel: {str(r.get('Telefon', ''))} | {str(r.get('Kontakt', ''))}".strip()
                    val_zrodlo = "Przewoźnik z bazy"
                else:
                    val_zrodlo = "Przewoźnik z giełdy"
                    val_detale_przewoznika = ""

        with st.container(border=True):
            st.markdown("#### 1. Kierunek i Harmonogram")
            typ_zlecenia = st.radio("Tryb operacji:", ["Tylko dostawa", "Pełny event"], index=["Tylko dostawa", "Pełny event"].index(val_typ_zlecenia), horizontal=True)
            waga = st.number_input("Waga (kg):", min_value=100, step=100, value=val_waga)
            d1, d2 = st.columns(2)
            data_zal = d1.date_input("Data załadunku (PL):", val_data_zal)
            data_roz = d2.date_input("Data rozładunku (Cel):", val_data_roz)
            if typ_zlecenia == "Pełny event":
                h1, h2 = st.columns(2)
                data_emp_in = h1.date_input("Odbiór pustych:", val_data_emp_in)
                data_emp_out = h2.date_input("Powrót / Załadunek:", val_data_emp_out)
            else: data_emp_in, data_emp_out = "", ""

        with st.container(border=True):
            st.markdown("#### 2. Przewoźnik i Koszty")
            zrodlo_idx = ["Przewoźnik z bazy", "Przewoźnik z giełdy"].index(val_zrodlo) if val_zrodlo in ["Przewoźnik z bazy", "Przewoźnik z giełdy"] else 0
            zrodlo = st.radio("Źródło przewoźnika:", ["Przewoźnik z bazy", "Przewoźnik z giełdy"], index=zrodlo_idx, horizontal=True)
            
            lista_cennikowa = df_carriers['Firma'].dropna().unique().tolist() if not df_carriers.empty else []
            
            if zrodlo == "Przewoźnik z bazy":
                if tryb_pracy == "Edycja Istniejącego Zlecenia" and val_nazwa_przewoznika not in lista_cennikowa and val_nazwa_przewoznika != "":
                    lista_cennikowa.append(val_nazwa_przewoznika)
                
                f1, f2, f3 = st.columns([2, 1, 1])
                nazwa_przewoznika = f1.selectbox("Wybierz partnera z bazy:", ["Wybierz..."] + lista_cennikowa, index=(lista_cennikowa.index(val_nazwa_przewoznika)+1 if val_nazwa_przewoznika in lista_cennikowa else 0))
                
                if nazwa_przewoznika != "Wybierz...":
                    r_p = df_carriers[df_carriers['Firma'] == nazwa_przewoznika]
                    if not r_p.empty:
                        r = r_p.iloc[0]
                        detale_przewoznika = f"{str(r.get('Firma', ''))}\n{str(r.get('Adres', ''))}\nNIP: {str(r.get('NIP', ''))}\nTel: {str(r.get('Telefon', ''))} | {str(r.get('Kontakt', ''))}".strip()
                    else: detale_przewoznika = nazwa_przewoznika
                else: detale_przewoznika = ""
                
                stawka_final = f2.number_input("Cena Total:", value=float(val_stawka_final))
                waluta = f3.selectbox("Waluta:", ["EUR", "PLN"], index=(["EUR", "PLN"].index(val_waluta) if val_waluta in ["EUR", "PLN"] else 0))
                
            else:
                nazwa_przewoznika = st.text_input("Nazwa firmy z giełdy:", value=val_nazwa_przewoznika if val_zrodlo == "Przewoźnik z giełdy" else "")
                detale_przewoznika = st.text_area("Pełne dane (Adres, NIP, Kontakt):", value=val_detale_przewoznika if val_zrodlo == "Przewoźnik z giełdy" else "", placeholder="Wklej pełne dane przewoźnika do zamówienia...")
                f1, f2 = st.columns(2)
                stawka_final = f1.number_input("Cena Total:", value=float(val_stawka_final))
                waluta = f2.selectbox("Waluta:", ["EUR", "PLN"], index=(["EUR", "PLN"].index(val_waluta) if val_waluta in ["EUR", "PLN"] else 0))

        with st.container(border=True):
            st.markdown("#### 3. Logistyka Miejsc")
            projekt = st.selectbox("Przypisz do Projektu:", ["Brak"] + lista_eventow, index=(lista_eventow.index(val_projekt)+1 if val_projekt in lista_eventow else 0))
            l1, l2 = st.columns(2)
            with l1:
                z_sel = st.selectbox("Miejsce startu:", opcje_lokalizacji, index=(opcje_lokalizacji.index(val_z_sel) if val_z_sel in opcje_lokalizacji else 0))
                z_man = st.text_input("Adres startu (ręcznie):", value=val_z_man) if z_sel == "INNE (wpisz ręcznie)" else ""
            with l2:
                r_s = st.selectbox("Miejsce celu:", opcje_lokalizacji)
                r_m = st.text_input("Adres celu (ręcznie):") if r_s == "INNE (wpisz ręcznie)" else ""

        with st.container(border=True):
            st.markdown("#### 4. Realizacja i Uwagi")
            d_auto, d_wart = st.columns(2)
            c_auto = d_auto.text_input("Auto / Kierowca:", value=val_c_auto, placeholder="np. PO 12345 / Jan Kowalski")
            wartosc_towaru = d_wart.number_input("Wartość towaru (EUR):", min_value=0, value=val_wartosc_towaru)
            u1, u2 = st.columns([3, 1])
            instrukcje = u1.text_area("Instrukcje dodatkowe:", value=val_instrukcje, height=80)
            podpis = u2.radio("Podpis:", ["PD", "PK"], index=(["PD", "PK"].index(val_podpis) if val_podpis in ["PD", "PK"] else 0), horizontal=True)

        btn_label = "⚡ ZAPISZ ZMIANY I REGENERUJ PDF" if tryb_pracy == "Edycja Istniejącego Zlecenia" else "⚡ GENERUJ I ZAPISZ ZLECENIE PRO"

        if st.button(btn_label, type="primary", use_container_width=True):
            if not nazwa_przewoznika or nazwa_przewoznika == "Wybierz...":
                st.error("Podaj nazwę przewoźnika!")
            else:
                with st.spinner("Przetwarzanie dokumentów i zapis do bazy..."):
                    try:
                        final_zal_db = z_man if z_sel == "INNE (wpisz ręcznie)" else z_sel
                        final_roz_db = r_m if r_s == "INNE (wpisz ręcznie)" else r_s
                        
                        def build_full_address(place_name, manual_addr, df):
                            if place_name == "INNE (wpisz ręcznie)": return manual_addr
                            if place_name == "Magazyn SQM Komorniki": return "Magazyn Centralny;\nul. Poznańska 165, Komorniki"
                            if df is not None and not df.empty:
                                row = df[df['Nazwa do listy'] == place_name]
                                if not row.empty:
                                    r = row.iloc[0]
                                    return f"{r.get('Nazwa pełna / Firma', place_name)}\n{r.get('Ulica i numer', '')}\n{r.get('Kod pocztowy', '')} {r.get('Miasto', '')}, {r.get('Kraj', '')}"
                            return place_name

                        full_zal_pdf = build_full_address(z_sel, z_man, df_miejsca)
                        full_roz_pdf = build_full_address(r_s, r_m, df_miejsca)
                        
                        historia_cyklu = f"CYKL: {data_zal} -> {data_roz}" + (f" | EMP: {data_emp_in} | POWRÓT: {data_emp_out}" if typ_zlecenia == "Pełny event" else "")
                        pelne_uwagi_db = f"AUTO: {c_auto} || WART: {wartosc_towaru} EUR || {historia_cyklu} || {instrukcje}"
                        uwagi_na_pdf = f"VEHICLE/DRIVER: {c_auto}\n{instrukcje}"
                        
                        if tryb_pracy == "Edycja Istniejącego Zlecenia":
                            nr_zlecenia = wybrane_zlecenie_nr
                        else:
                            dzis_ile = len(df_zlecenia[df_zlecenia['Numer zlecenia'].str.contains(datetime.now().strftime('%y/%m%d'))]) if not df_zlecenia.empty else 0
                            idx_nowy = dzis_ile + 1
                            nr_zlecenia = f"CRG{datetime.now().strftime('%y/%m%d')}/{podpis}{idx_nowy:02d}"
                        
                        paczka_pdf = {
                            "typ_zlecenia": typ_zlecenia, "nr": nr_zlecenia, "przewoznik_nazwa": nazwa_przewoznika, "przewoznik_detale": detale_przewoznika,
                            "stawka": stawka_final, "waluta": waluta, "zaladunek": full_zal_pdf, "data_zal": str(data_zal),
                            "rozladunek": full_roz_pdf, "data_roz": str(data_roz), "data_emp_in": str(data_emp_in), "data_emp_out": str(data_emp_out),
                            "waga": waga, "auto": c_auto, "uwagi": uwagi_na_pdf, "opiekun": podpis 
                        }
                        
                        nowy_wiersz = pd.DataFrame([{
                            "Data": datetime.now().strftime("%Y-%m-%d %H:%M"), "Numer zlecenia": nr_zlecenia, "Dział": "LOGISTYKA CARGO", "Zleceniobiorca": nazwa_przewoznika,
                            "Miejsce Zaladunku": final_zal_db, "Miejsce Rozladunku": final_roz_db, "Data załadunku": str(data_zal), "Data rozładunku": str(data_roz),
                            "Typ": "Zabudowa Targowa PRO", "Puste1": "", "Puste2": "", "Puste3": "", "Puste4": "", 
                            "Uwagi / Instrukcje": pelne_uwagi_db, "Puste5": "", "ID Projektu": projekt, "Rodzaj": "TARGI", "Stawka": f"{stawka_final} {waluta}"
                        }])
                        
                        if tryb_pracy == "Edycja Istniejącego Zlecenia":
                            df_zlecenia.iloc[idx_pd] = nowy_wiersz.iloc[0]
                            conn.update(worksheet="Zlecenia", data=clean_for_gsheets(df_zlecenia))
                        else:
                            conn.update(worksheet="Zlecenia", data=clean_for_gsheets(pd.concat([df_zlecenia, nowy_wiersz], ignore_index=True)))
                            
                        time.sleep(1.5) 
                        
                        pdf_bytes = generate_pro_pdf(paczka_pdf)
                        st.session_state["pdf_data"] = pdf_bytes
                        st.session_state["pdf_name"] = f"Order_{nr_zlecenia.replace('/', '_')}.pdf"
                        st.session_state["pdf_nr"] = nr_zlecenia
                        
                        st.cache_data.clear()
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"⚠️ Wystąpił błąd zapisu: {e}")
