import streamlit as st
import pandas as pd
import sys
import os
import datetime
import threading

# --- GLOBÁLNY ZÁMOK (Zdieľaný medzi všetkými používateľmi) ---
@st.cache_resource
def get_global_lock():
    return threading.Lock()

lock = get_global_lock()

# --- CHYTRÁ NAVIGÁCIA ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Cesta k Excelu (v hlavnom priečinku projektu)
EXCEL_PATH = "benchmark_master_v3_fixed.xlsx"

# --- KONFIGURÁCIA STRÁNKY ---
st.set_page_config(page_title="Kaldewei Master Dashboard", layout="wide", page_icon="🛀")

# Štýly pre tlačidlá
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# UI APLIKÁCIE
# ==============================================================================

st.title("🛀 Kaldewei: Master Benchmark Dashboard")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("🔌 1. Výber značiek")
use_viega = st.sidebar.checkbox("Viega", value=True)
use_geberit = st.sidebar.checkbox("Geberit", value=True)
use_alca = st.sidebar.checkbox("Alcadrain", value=False)
use_hans = st.sidebar.checkbox("Hansgrohe", value=False)

st.sidebar.header("⚙️ 2. Fázy na spustenie")
run_disc = st.sidebar.checkbox("🔍 Discovery (Technické dáta)", value=True)
run_bom = st.sidebar.checkbox("🏗️ BOM Builder / Kalkulátor", value=True)

st.sidebar.divider()
ref_price = st.sidebar.number_input("Ref. cena Kaldewei (EUR)", value=450.0)

# --- HLAVNÁ PLOCHA ---
col_cmd, col_stat = st.columns([1, 2])

with col_cmd:
    st.subheader("🚀 Ovládací panel")
    run_btn = st.button("SPUSTIŤ BENCHMARK", type="primary")
    
    if run_btn:
        # Kontrola, či už niekto iný nespustil agentov (Global Lock)
        if lock.locked():
            st.warning("⚠️ Agenti práve pracujú pre iného používateľa. Počkajte prosím na dokončenie.")
        else:
            with lock:
                status_msg = st.empty()
                status_msg.info("🔒 Prístup uzamknutý. Ostatní používatelia musia počkať.")
                
                try:
                    # --- 🔵 VIEGA ---
                    if use_viega:
                        st.markdown("### 🔵 Spracovávam: Viega")
                        if run_disc:
                            status_msg.info("Viega: Spúšťam Discovery...")
                            from viega_master_discovery import ViegaGreedyMaster
                            agent_v_disc = ViegaGreedyMaster(excel_path=EXCEL_PATH)
                            agent_v_disc.run()
                            st.success("Viega: Discovery fáza hotová.")

                        if run_bom:
                            status_msg.info("Viega: Spúšťam BOM Builder...")
                            from viega_bom_builder import ViegaBOMBuilder
                            agent_v_bom = ViegaBOMBuilder(excel_path=EXCEL_PATH)
                            # Príklad URL
                            test_urls = ["https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Einbauhoehe-ab-95-mm/Advantix-Cleviva-Duschrinne-4981-10.html"]
                            agent_v_bom.run(test_urls)
                            st.success("Viega: BOM zostavy vytvorené.")

                    # --- 🟢 GEBERIT ---
                    if use_geberit:
                        st.markdown("### 🟢 Spracovávam: Geberit")
                        if run_disc:
                            status_msg.info("Geberit: Spúšťam Discovery (BS4)...")
                            from geberit_master_discovery import GeberitMasterDiscovery
                            agent_g_disc = GeberitMasterDiscovery(excel_path=EXCEL_PATH)
                            agent_g_disc.run()
                            status_msg.success("Geberit: Discovery hotové.")
                        
                        if run_bom:
                            status_msg.info("Geberit: Počítam systémy (BOM)...")
                            from geberit_calculator import GeberitSystemCalculatorFinal
                            agent_g_calc = GeberitSystemCalculatorFinal(excel_path=EXCEL_PATH)
                            agent_g_calc.run()
                            status_msg.success("Geberit: Výpočet systémov dokončený.")

                    # --- 🔴 OSTATNÍ (Placeholder pre budúcnosť) ---
                    if use_alca:
                        st.info("Alcadrain modul: Čaká na pripojenie BS4 agenta.")
                    
                    if use_hans:
                        st.info("Hansgrohe modul: Čaká na pripojenie BS4 agenta.")

                    st.balloons()
                    st.success("✅ Všetky vybrané operácie boli dokončené!")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Neočakávaná chyba: {e}")

# --- VIZUALIZÁCIA A DÁTA ---
st.divider()

if os.path.exists(EXCEL_PATH):
    try:
        # Tlačidlo na stiahnutie
        with open(EXCEL_PATH, "rb") as f:
            st.download_button(
                label="📥 STIAHNUŤ AKTUÁLNY EXCEL",
                data=f,
                file_name=f"kaldewei_benchmark_{datetime.datetime.now().strftime('%d_%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # Zobrazenie dátovej tabuľky
        df = pd.read_excel(EXCEL_PATH, sheet_name="Products_Tech")
        if not df.empty:
            st.subheader("📋 Prehľad nájdených technických dát")
            st.dataframe(df, use_container_width=True)
    except Exception:
        st.info("Tabuľka sa pripravuje alebo Excel neobsahuje list 'Products_Tech'.")
else:
    st.warning("Databáza (Excel) zatiaľ neexistuje. Spustite Discovery agenta.")