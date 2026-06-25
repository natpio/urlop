import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import time

# --- IMPORT MODUŁÓW ZEWNĘTRZNYCH ---
from vantage import render_vantage
from hub import render_hub
from kreator import render_kreator

# ==========================================
# 1. KONFIGURACJA STRONY I CSS
# ==========================================
st.set_page_config(page_title="Global Logistics Hub", page_icon="✈️", layout="wide")

hide_st_style = """<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}
[data-testid="collapsedControl"] {display: none;}

/* --- 999+ PRO: TOP NAVIGATION (SEGMENTED CONTROL) --- */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    display: flex; flex-direction: row; background: #F1F5F9; padding: 6px; border-radius: 16px;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.05); gap: 8px; justify-content: center; margin-top: 10px;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label {
    background: transparent; padding: 12px 30px; border-radius: 12px; cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); border: 1px solid transparent; margin: 0;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child { display: none !important; }
div[data-testid="stRadio"] > div[role="radiogroup"] > label p { font-weight: 700 !important; color: #64748B !important; font-size: 15px; margin: 0;}
div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover { background: #FFFFFF; box-shadow: 0 4px 6px rgba(0,0,0,0.05); transform: translateY(-1px); }
div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"] { background: #002244 !important; border: 1px solid #00152b !important; box-shadow: 0 8px 15px rgba(0, 34, 68, 0.25) !important; }
div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-checked="true"] p { color: #FFFFFF !important; }

/* --- 999+ PRO: ZAKŁADKI (TABS JAKO KARTY) --- */
div[data-testid="stTabs"] > div[role="tablist"] { gap: 10px; padding-bottom: 10px; border-bottom: 2px solid #E2E8F0; }
div[data-testid="stTabs"] button[role="tab"] { background: #FFFFFF !important; border: 1px solid #E2E8F0 !important; border-bottom: none !important; border-radius: 12px 12px 0 0 !important; padding: 12px 24px !important; transition: all 0.3s ease !important; box-shadow: 0 -2px 10px rgba(0,0,0,0.02); }
div[data-testid="stTabs"] button[role="tab"] p { font-weight: 700 !important; color: #64748B !important; font-size: 14px; }
div[data-testid="stTabs"] button[role="tab"]:hover { background: #F8FAFC !important; transform: translateY(-2px); }
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { background: #002244 !important; border-color: #002244 !important; border-bottom: 4px solid #FFB81C !important; box-shadow: 0 -6px 15px rgba(0,34,68,0.15) !important; }
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p { color: #FFFFFF !important; }
</style>"""
st.markdown(hide_st_style, unsafe_allow_html=True)

try:
    with open("style.css") as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except: pass

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
# 3. POBIERANIE BAZY DANYCH (ANTI-429)
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)
dane_pobrane = False

for attempt in range(3):
    try:
        df_tasks = conn.read(worksheet="Arkusz1", ttl=600).dropna(how="all")
        df_links = conn.read(worksheet="Linki", ttl=600).dropna(how="all")
        df_carriers = conn.read(worksheet="Przewoznicy", ttl=600).dropna(how="all")
        df_schedule = conn.read(worksheet="Harmonogram", ttl=600).dropna(how="all")
        df_notes = conn.read(worksheet="Notatnik", ttl=600).dropna(how="all")
        df_miejsca = conn.read(worksheet="Miejsca", ttl=600).dropna(how="all")
        df_zlecenia = conn.read(worksheet="Zlecenia", ttl=600).dropna(how="all")
        dane_pobrane = True
        break
    except Exception as e:
        if '429' in str(e) or 'Quota' in str(e):
            if attempt < 2:
                st.toast(f"⏳ Oczekiwanie na przepustowość Google. Próba {attempt+2}/3...")
                time.sleep(8)
            else:
                st.error("⚠️ Serwery Google są przeciążone. Odczekaj chwilę i odśwież.")
                st.stop()
        else:
            st.error(f"⚠️ Krytyczny błąd bazy: {e}"); st.stop()

if dane_pobrane:
    for df, cols in [(df_tasks, ["Temat", "Zadanie", "Osoba", "Termin", "Status", "Notatki"]), (df_links, ["Nazwa", "URL", "Opis", "Kategoria"]), (df_carriers, ["Firma", "Adres", "NIP", "Kontakt", "Telefon", "Typ_Auta", "Uwagi"]), (df_notes, ["Data", "Kto", "Wiadomość"]), (df_miejsca, ["Nazwa do listy", "Nazwa pełna / Firma", "Ulica i numer", "Kod pocztowy", "Miasto", "Kraj"])]:
        for col in cols:
            if col not in df.columns: df[col] = ""
            df[col] = df[col].fillna("").astype(str)

    if "Numer zlecenia" not in df_zlecenia.columns: df_zlecenia["Numer zlecenia"] = ""
    df_zlecenia["Numer zlecenia"] = df_zlecenia["Numer zlecenia"].astype(str).replace('nan', '')

    cols_schedule = ["Event", "Lokalizacja", "Auto", "1_Zaladunek", "2_Montaz_Od", "2_Montaz_Do", "3_Puste_Casy_1", "3_Puste_Casy_2", "4_Dzien_Klienta", "5_Dostawa_Pustych", "6_Odbior_Pelnych", "7_Rozladunek"]
    for col in cols_schedule: 
        if col not in df_schedule.columns: df_schedule[col] = None
        if col not in ["Event", "Auto", "Lokalizacja"]: df_schedule[col] = pd.to_datetime(df_schedule[col], errors='coerce').dt.date
        else: df_schedule[col] = df_schedule[col].fillna("").astype(str)

# ==========================================
# 4. GŁÓWNA NAWIGACJA (TOP-BAR)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
top_c1, top_c2, top_c3 = st.columns([1, 4, 1], gap="medium")

with top_c1:
    if st.session_state["role"] == "admin": st.markdown("""<div style="background: #002244; color: #FFB81C; padding: 12px; border-radius: 8px; text-align: center; font-weight: 900; letter-spacing: 1px; border: 1px solid #FFB81C; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">👨‍✈️ CAPTAIN (ADMIN)</div>""", unsafe_allow_html=True)
    else: st.markdown("""<div style="background: #E0E7FF; color: #002244; padding: 12px; border-radius: 8px; text-align: center; font-weight: 900; letter-spacing: 1px; border: 1px solid #93C5FD; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">👨‍💼 CREW (ZESPÓŁ)</div>""", unsafe_allow_html=True)

with top_c2:
    nav_mode = st.radio("Nawigacja:", ["🌍 Hub Operacyjny", "📄 Kreator Zleceń PRO", "📊 Kalkulator Vantage"], horizontal=True, label_visibility="collapsed")

with top_c3:
    if st.button("🚪 Wyloguj", use_container_width=True):
        st.session_state["role"] = None; st.rerun()

st.markdown("<hr style='margin: 10px 0 30px 0; border: none; border-top: 2px solid #E5E7EB;'>", unsafe_allow_html=True)

# ==========================================
# 5. ROUTING DO MODUŁÓW
# ==========================================
if nav_mode == "🌍 Hub Operacyjny":
    render_hub(conn, df_tasks, df_schedule, df_carriers, df_links, df_notes)

elif nav_mode == "📄 Kreator Zleceń PRO":
    render_kreator(conn, df_zlecenia, df_schedule, df_miejsca, df_carriers)

elif nav_mode == "📊 Kalkulator Vantage":
    render_vantage()
