import streamlit as st
import pandas as pd
import sys
import os
import datetime
import threading

# --- GLOBÁLNÍ ZÁMEK (Sdílený mezi všemi uživateli) ---
@st.cache_resource
def get_global_lock():
    return threading.Lock()

lock = get_global_lock()

# --- CHYTRÁ NAVIGACE ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Cesta k Excelu (v hlavní složce projektu)
EXCEL_PATH = "benchmark_master_v3_fixed.xlsx"

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="Kaldewei Master Dashboard", layout="wide", page_icon="🛀")

# Styly pro tlačítka
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# UI APLIKACE
# ==============================================================================

st.title("🛀 Kaldewei: Master Benchmark Dashboard")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("🔌 1. Výběr značek")
use_viega = st.sidebar.checkbox("Viega", value=True)
use_geberit = st.sidebar.checkbox("Geberit", value=False)

st.sidebar.header("⚙️ 2. Fáze ke spuštění")
run_disc = st.sidebar.checkbox("🔍 Discovery (Technická data)", value=True)
run_bom = st.sidebar.checkbox("🏗️ BOM Builder (Sestavy)", value=True)

st.sidebar.divider()
ref_price = st.sidebar.number_input("Ref. cena Kaldewei (EUR)", value=450.0)

# --- HLAVNÍ PLOCHA ---
col_cmd, col_stat = st.columns([1, 2])

with col_cmd:
    st.subheader("🚀 Ovládací panel")
    run_btn = st.button("SPUSTIT BENCHMARK", type="primary")
    
    if run_btn:
        # Kontrola, zda už někdo jiný nespustil agenty (Global Lock)
        if lock.locked():
            st.warning("⚠️ Agenti právě pracují pro jiného uživatele. Počkejte prosím na dokončení.")
        else:
            with lock:
                status_msg = st.empty()
                status_msg.info("🔒 Přístup uzamčen. Ostatní uživatelé musí počkat.")
                
                try:
                    # --- 🔵 VIEGA ---
                    if use_viega:
                        st.markdown("### 🔵 Zpracovávám: Viega")
                        
                        if run_disc:
                            status_msg.info("Viega: Spouštím Discovery...")
                            from viega_master_discovery import ViegaGreedyMaster
                            agent_disc = ViegaGreedyMaster(excel_path=EXCEL_PATH)
                            agent_disc.run()
                            st.success("Viega: Discovery fáze hotova.")

                        if run_bom:
                            status_msg.info("Viega: Spouštím BOM Builder...")
                            from viega_bom_builder import ViegaBOMBuilder
                            agent_bom = ViegaBOMBuilder(excel_path=EXCEL_PATH)
                            # Předáme ukázkovou URL pro testování
                            test_urls = ["https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Einbauhoehe-ab-95-mm/Advantix-Cleviva-Duschrinne-4981-10.html"]
                            agent_bom.run(test_urls)
                            st.success("Viega: BOM sestavy vytvořeny.")

                    # --- 🟢 GEBERIT ---
                    if use_geberit:
                        st.markdown("### 🟢 Zpracovávám: Geberit")
                        st.info("Geberit modul se připravuje na stabilní verzi...")

                    st.balloons()
                    st.success("✅ Všechny vybrané operace byly dokončeny!")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Neočekávaná chyba: {e}")

# --- VIZUALIZACE A DATA ---
st.divider()

if os.path.exists(EXCEL_PATH):
    try:
        # Tlačítko pro stažení
        with open(EXCEL_PATH, "rb") as f:
            st.download_button(
                label="📥 STÁHNOUT AKTUÁLNÍ EXCEL VÝSLEDKY",
                data=f,
                file_name=f"kaldewei_benchmark_{datetime.datetime.now().strftime('%d_%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # Zobrazení datové tabulky
        df = pd.read_excel(EXCEL_PATH, sheet_name="Products_Tech")
        if not df.empty:
            st.subheader("📋 Přehled nalezených technických dat")
            st.dataframe(df, use_container_width=True)
    except Exception:
        st.info("Tabulka se připravuje nebo Excel neobsahuje list 'Products_Tech'.")
else:
    st.warning("Databáze (Excel) zatím neexistuje. Spusťte Discovery agenta.")