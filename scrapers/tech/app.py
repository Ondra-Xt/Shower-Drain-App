import streamlit as st
import pandas as pd
import sys
import os
import datetime
import threading

# --- GLOBÁLNÍ ZÁMEK (Zabraňuje kolizi, když klikne víc lidí najednou) ---
@st.cache_resource
def get_global_lock():
    return threading.Lock()

lock = get_global_lock()

# --- CESTY A IMPORTY ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

EXCEL_PATH = "benchmark_master_v3_fixed.xlsx"

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="Goro BOM Builder", layout="wide", page_icon="🛀")

# Custom CSS pro hezčí tlačítka
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .stDownloadButton>button { background-color: #28a745; color: white; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# UI APLIKACE
# ==============================================================================

st.title("🛀 Goro: Master Benchmark Dashboard")
st.info("Tento nástroj automaticky sbírá technická data a ceny žlabů Viega a Geberit.")

# --- BOČNÍ PANEL (NASTAVENÍ) ---
st.sidebar.header("⚙️ Nastavení benchmarku")
use_viega = st.sidebar.checkbox("Zahrnout Viega", value=True)
use_geberit = st.sidebar.checkbox("Zahrnout Geberit", value=True)

st.sidebar.divider()
st.sidebar.subheader("🚀 Fáze ke spuštění")
run_disc = st.sidebar.checkbox("Discovery (Hledání nových SKU)", value=True)
run_specs = st.sidebar.checkbox("Specs (Technické parametry)", value=True)
run_price = st.sidebar.checkbox("Pricing (Ceny z eshopů)", value=True)

# --- HLAVNÍ OVLÁDACÍ PANEL ---
col_main, col_info = st.columns([2, 1])

with col_main:
    st.subheader("🕹️ Ovládací panel")
    run_btn = st.button("SPUSTIT AGENTY", type="primary")

    if run_btn:
        if lock.locked():
            st.warning("⚠️ Agenti právě pracují. Počkejte prosím na dokončení.")
        else:
            with lock:
                status = st.empty()
                
                try:
                    # --- 🔵 VIEGA (Placeholder - pokud máš i pro ni BS4 verze) ---
                    if use_viega:
                        st.markdown("### 🔵 Zpracovávám: Viega")
                        # Zde se volají tvé Viega skripty...
                        st.success("Viega: Fáze dokončeny (pokud jsou implementovány).")

                    # --- 🟢 GEBERIT (Tvůj aktuální fokus) ---
                    if use_geberit:
                        st.markdown("### 🟢 Zpracovávám: Geberit")
                        
                        if run_disc:
                            status.info("Geberit: Spouštím Discovery (Hledám SKU)...")
                            from geberit_master_discovery import GeberitMasterDiscovery
                            GeberitMasterDiscovery(EXCEL_PATH).run()
                            st.toast("Geberit Discovery Hotovo!")

                        if run_specs:
                            status.info("Geberit: Stahuji technické parametry...")
                            from geberit_official_specs import GeberitOfficialSpecsBot
                            GeberitOfficialSpecsBot(EXCEL_PATH).run()
                            st.toast("Geberit Specs Hotovo!")

                        if run_price:
                            status.info("Geberit: Zjišťuji ceny na Megabad...")
                            from geberit_pricing import GeberitPricingV11_EdgeCase
                            GeberitPricingV11_EdgeCase(EXCEL_PATH).run()
                            st.toast("Geberit Pricing Hotovo!")

                    st.balloons()
                    st.success("✅ Všechny vybrané operace byly dokončeny!")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Neočekávaná chyba: {e}")

with col_info:
    st.subheader("📊 Stav databáze")
    if os.path.exists(EXCEL_PATH):
        st.success(f"Soubor nalezen: {EXCEL_PATH}")
        # Tlačítko pro stažení
        with open(EXCEL_PATH, "rb") as f:
            st.download_button(
                label="📥 STÁHNOUT EXCEL",
                data=f,
                file_name=f"benchmark_{datetime.datetime.now().strftime('%d_%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.warning("⚠️ Databáze zatím neexistuje. Spusťte Discovery.")

# --- ZOBRAZENÍ DAT ---
st.divider()

if os.path.exists(EXCEL_PATH):
    try:
        # Vynucení dtype=str při čtení pro Streamlit zobrazení
        df_display = pd.read_excel(EXCEL_PATH, sheet_name="Products_Tech", dtype=str)
        df_display = df_display.replace(['nan', 'None'], '')
        
        st.subheader("📋 Přehled nalezených technických dat")
        st.dataframe(df_display, use_container_width=True)
        
        # Pokud existují i ceny
        with pd.ExcelFile(EXCEL_PATH) as xls:
            if "Market_Prices" in xls.sheet_names:
                df_prices = pd.read_excel(xls, sheet_name="Market_Prices", dtype=str)
                st.subheader("💰 Aktuální trhové ceny")
                st.dataframe(df_prices, use_container_width=True)
    except Exception:
        st.info("Tabulka se připravuje nebo list 'Products_Tech' ještě není vyplněn.")