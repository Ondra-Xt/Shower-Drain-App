import streamlit as st
import pandas as pd
import sys
import os
import datetime
import threading

# --- GLOBÁLNÍ ZÁMEK ---
@st.cache_resource
def get_global_lock():
    return threading.Lock()

lock = get_global_lock()

# --- CESTY A IMPORTY ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Přidání cesty ke složce se skripty
script_dir = os.path.join(current_dir, "scrapers", "tech")
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

EXCEL_PATH = "benchmark_master_v3_fixed.xlsx"

# --- SAMOLÉČBA EXCELU (Opravené názvy sloupců) ---
def check_or_create_excel():
    if not os.path.exists(EXCEL_PATH):
        with pd.ExcelWriter(EXCEL_PATH, engine='openpyxl') as writer:
            # GEBERIT i VIEGA potřebují 'Component_SKU'
            cols = ["Component_SKU", "Manufacturer", "Product_Name", "Tech_Source_URL", "Material_V4A", "Color", "Length_mm"]
            pd.DataFrame(columns=cols).to_excel(writer, sheet_name="Products_Tech", index=False)
            pd.DataFrame(columns=["Component_SKU", "Found_Price_EUR", "Eshop_Source"]).to_excel(writer, sheet_name="Market_Prices", index=False)
        return True
    return False

check_or_create_excel()

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="Goro BOM Builder", layout="wide", page_icon="🛀")

st.title("🛀 Goro: Master Benchmark Dashboard")

# --- BOČNÍ PANEL ---
st.sidebar.header("⚙️ Nastavení")
use_viega = st.sidebar.checkbox("Zahrnout Viega", value=True)
use_geberit = st.sidebar.checkbox("Zahrnout Geberit", value=True)

st.sidebar.divider()
run_disc = st.sidebar.checkbox("Discovery", value=True)
run_specs = st.sidebar.checkbox("Specs / BOM", value=True)
run_price = st.sidebar.checkbox("Pricing", value=True)

# --- OVLÁDACÍ PANEL ---
run_btn = st.button("🚀 SPUSTIT AGENTY", type="primary")

if run_btn:
    if lock.locked():
        st.warning("⚠️ Agenti právě pracují. Počkejte prosím.")
    else:
        with lock:
            status = st.empty()
            try:
                # --- 🔵 VIEGA ---
                if use_viega:
                    st.markdown("### 🔵 Zpracovávám: Viega")
                    from viega_master_discovery import ViegaGreedyMaster
                    if run_disc:
                        status.info("Viega: Discovery...")
                        ViegaGreedyMaster(EXCEL_PATH).run()
                    if run_specs:
                        status.info("Viega: BOM Builder...")
                        from viega_bom_builder import ViegaBOMBuilder
                        ViegaBOMBuilder(EXCEL_PATH).run(["https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Einbauhoehe-ab-95-mm/Advantix-Cleviva-Duschrinne-4981-10.html"])

                # --- 🟢 GEBERIT ---
                if use_geberit:
                    st.markdown("### 🟢 Zpracovávám: Geberit")
                    if run_disc:
                        status.info("Geberit: Discovery...")
                        from geberit_master_discovery import GeberitMasterDiscovery
                        GeberitMasterDiscovery(EXCEL_PATH).run()
                    if run_specs:
                        status.info("Geberit: Specs...")
                        from geberit_official_specs import GeberitOfficialSpecsBot
                        GeberitOfficialSpecsBot(EXCEL_PATH).run()
                    if run_price:
                        status.info("Geberit: Pricing...")
                        from geberit_pricing import GeberitPricingV11_EdgeCase
                        GeberitPricingV11_EdgeCase(EXCEL_PATH).run()
                        from geberit_calculator import GeberitSystemCalculatorFinal
                        GeberitSystemCalculatorFinal(EXCEL_PATH).run()

                st.balloons()
                st.success("✅ Hotovo!")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Neočekávaná chyba: {e}")

# --- ZOBRAZENÍ DAT ---
st.divider()
if os.path.exists(EXCEL_PATH):
    try:
        # Oprava use_container_width na width='stretch' pro rok 2026
        df_display = pd.read_excel(EXCEL_PATH, sheet_name="Products_Tech", dtype=str).replace(['nan', 'None'], '')
        st.subheader("📋 Technická data")
        st.dataframe(df_display, width='stretch')
        
        with open(EXCEL_PATH, "rb") as f:
            st.download_button("📥 STÁHNOUT EXCEL", f, file_name=EXCEL_PATH)
    except:
        st.info("Tabulka se připravuje...")