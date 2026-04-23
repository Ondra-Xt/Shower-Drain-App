import streamlit as st
import pandas as pd
import sys
import os
import datetime
import threading

# --- GLOBÁLNÍ ZÁMEK (Proti kolizi více uživatelů) ---
if 'global_lock' not in st.cache_resource:
    st.cache_resource.global_lock = threading.Lock()

lock = st.cache_resource.global_lock

# --- CHYTRÁ NAVIGACE ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

EXCEL_PATH = "benchmark_master_v3_fixed.xlsx"

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="Kaldewei Master Dashboard", layout="wide", page_icon="🛀")

st.title("🛀 Kaldewei: Master Benchmark Dashboard")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("🔌 1. Výběr značek")
use_viega = st.sidebar.checkbox("Viega", value=True)
use_geberit = st.sidebar.checkbox("Geberit", value=False)

st.sidebar.header("⚙️ 2. Fáze ke spuštění")
run_disc = st.sidebar.checkbox("🔍 Discovery (Technická data)", value=True)
run_bom = st.sidebar.checkbox("🏗️ BOM Builder (Sestavy)", value=True)

# --- OVLÁDACÍ PANEL ---
col_cmd, col_stat = st.columns([1, 2])

with col_cmd:
    st.subheader("🚀 Ovládací panel")
    
    if st.button("SPUSTIT BENCHMARK", type="primary"):
        # Kontrola, zda už někdo jiný nespustil agenty
        if lock.locked():
            st.warning("⚠️ Agenti právě pracují pro jiného uživatele. Počkejte prosím chvíli.")
        else:
            with lock:
                st.info("🔒 Spuštěno. Ostatní uživatelé jsou nyní blokováni, dokud neskončím.")
                try:
                    if use_viega:
                        st.markdown("### 🔵 Zpracovávám: Viega")
                        if run_disc:
                            from viega_master_discovery import ViegaGreedyMaster
                            agent = ViegaGreedyMaster(excel_path=EXCEL_PATH)
                            agent.run()
                            st.success("Viega Discovery hotovo!")
                        
                        if run_bom:
                            from viega_bom_builder import ViegaBOMBuilder
                            agent_bom = ViegaBOMBuilder(excel_path=EXCEL_PATH)
                            urls = ["https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Einbauhoehe-ab-95-mm/Advantix-Cleviva-Duschrinne-4981-10.html"]
                            agent_bom.run(urls)
                            st.success("Viega BOM hotovo!")
                    
                    st.balloons()
                    st.success("✅ Všechny úkoly dokončeny.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Neočekávaná chyba: {e}")

# --- DATA A STAŽENÍ ---
st.divider()
if os.path.exists(EXCEL_PATH):
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name="Products_Tech")
        st.subheader("📋 Výsledky v databázi")
        st.dataframe(df)
        
        with open(EXCEL_PATH, "rb") as f:
            st.download_button("📥 STÁHNOUT VÝSLEDNÝ EXCEL", f, file_name="kaldewei_benchmark.xlsx")
    except:
        st.info("Tabulka se připravuje...")
else:
    st.warning("Databáze zatím neexistuje. Spusťte agenty.")