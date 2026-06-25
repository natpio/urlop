import streamlit as st
import pandas as pd
from datetime import datetime
from geopy.geocoders import Nominatim

def clean_for_gsheets(df):
    """Usuwa błędy formatowania przed wysłaniem do Google Sheets"""
    cleaned = df.copy()
    for col in cleaned.columns:
        cleaned[col] = cleaned[col].astype(str).replace(['NaT', 'nan', 'None', '<NA>', 'NaN'], '')
    return cleaned

def get_current_stage(row):
    """Zaktualizowany Silnik Czasu uwzględniający minięte daty"""
    today = datetime.now().date()
    current_stage = 1
    
    stages_dates = [
        row.get("1_Zaladunek"), row.get("2_Montaz_Od"), row.get("3_Puste_Casy_1"), 
        row.get("4_Dzien_Klienta"), row.get("5_Dostawa_Pustych"), row.get("6_Odbior_Pelnych"), row.get("7_Rozladunek")
    ]
    
    for i, date_val in enumerate(stages_dates):
        if pd.notnull(date_val):
            if today > date_val:
                # Jeśli data już minęła (wczoraj i dawniej) -> Krok zakończony.
                # Aktywnym (złotym) celem staje się PRZYNAJMNIEJ kolejny etap.
                current_stage = i + 2 
            elif today == date_val:
                # Jeśli data to dokładnie DZIŚ -> To jest nasz złoty krok!
                current_stage = i + 1 
                break
            else:
                # Data jest w przyszłości (jutro i dalej) -> To jest nasz cel oczekujący.
                current_stage = i + 1 
                break
                
    return current_stage

@st.cache_data(ttl=3600)
def get_coordinates(city_name):
    """Pobieranie współrzędnych GPS dla mapy"""
    if not city_name or city_name.strip() == "": 
        return None, None
    try:
        location = Nominatim(user_agent="logistics_hub_agent").geocode(city_name)
        if location: 
            return location.latitude, location.longitude
        return None, None
    except: 
        return None, None
