import streamlit as st
import pandas as pd
import sys
import os
import datetime
import threading

# --- GLOBÁLNÍ ZÁMEK (Zabraňuje kolizi při více uživatelích) ---
@st.cache_resource
def get_global_lock():
    return threading.Lock()

lock = get_global_lock()

# --- CHYTRÁ NAVIGACE (Oprava importů pro Cloud) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
# Přidáme hlavní složku i složku se skripty do systémové cesty
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Pokud máš skripty ve složce 'scrapers', odkomentuj toto:
# script_dir = os.path.join(current_dir, "scrapers", "tech")
# if script_dir not in sys.path:
#     sys.path.insert(0, script_dir)

EXCEL_PATH = "benchmark_master_v3_fixed.xlsx"

# --- AUTOMATICKÁ KONTROLA / VYTVOŘENÍ SOUBORU ---
def check_or_create_excel():
    if not os.path.exists(EXCEL_PATH):
        # Pokud soubor chybí, vytvoříme ho s prázdnými listy, aby appka nepadala
        with pd.ExcelWriter(EXCEL_PATH, engine='openpyxl') as writer:
            # List pro technická data
            pd.DataFrame(columns=[
                "Article_Number_SKU", "Brand", "Product_Name", "Product_URL", 
                "Flow_Rate_ls", "Is_V4A", "Color", "Cert_DIN_EN1253", "Cert_DIN_18534"
            ]).to_excel(writer, sheet_name="Products_Tech", index=False)
            
            # List pro ceny
            pd.DataFrame(columns=[
                "Component_SKU", "Found_Price_EUR", "Eshop_Source", "Timestamp"
            ]).to_excel(writer, sheet_name="Market_Prices", index=False)
        return True
    return False

# Spustíme kontrolu hned při startu aplikace
check_or_create_excel()

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="Goro BOM Builder", layout="wide", page_icon="🛀")

# --- UI STYLY ---
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .stDownloadButton>button { background-color: #28a745 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛀 Goro: Master Benchmark Dashboard")
st.info("Automatizovaný sběr technických dat a cen: Viega & Geberit.")

# --- BOČNÍ PANEL ---
st.sidebar.header("⚙️ Nastavení benchmarku")
use_viega = st.sidebar.checkbox("Zahrnout Viega", value=True)
use_geberit = st.sidebar.checkbox("Zahrnout Geberit", value=True)

st.sidebar.divider()
st.sidebar.subheader("🚀 Fáze ke spuštění")
run_disc = st.sidebar.checkbox("Discovery (Hledání SKU)", value=True)
run_specs = st.sidebar.checkbox("Specs / BOM (Detaily)", value=True)
run_price = st.sidebar.checkbox("Pricing (Ceny)", value=True)

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
                    # --- 🔵 VIEGA ---
                    if use_viega:
                        st.markdown("### 🔵 Zpracovávám: Viega")
                        
                        if run_disc:
                            status.info("Viega: Spouštím Discovery...")
                            from viega_master_discovery import ViegaMasterDiscovery
                            ViegaMasterDiscovery(EXCEL_PATH).run()
                            st.toast("Viega Discovery Hotovo!")

                        if run_specs:
                            status.info("Viega: Spouštím BOM Builder...")
                            from viega_bom_builder import ViegaBOMBuilder
                            # Testovací URL pro Viegu
                            test_urls = ["https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Einbauhoehe-ab-95-mm/Advantix-Cleviva-Duschrinne-4981-10.html"]
                            ViegaBOMBuilder(EXCEL_PATH).run(test_urls)
                            st.toast("Viega BOM Builder Hotovo!")

                    # --- 🟢 GEBERIT ---
                    if use_geberit:
                        st.markdown("### 🟢 Zpracovávám: Geberit")
                        
                        if run_disc:
                            status.info("Geberit: Spouštím Discovery...")
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

                        # Výpočet systémů spustíme vždy po Geberitu
                        from geberit_calculator import GeberitSystemCalculatorFinal
                        GeberitSystemCalculatorFinal(EXCEL_PATH).run()

                    st.balloons()
                    st.success("✅ Všechny operace byly dokončeny!")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Neočekávaná chyba: {e}")

with col_info:
    st.subheader("📊 Stav databáze")
    if os.path.exists(EXCEL_PATH):
        st.success(f"Soubor nalezen: {EXCEL_PATH}")
        with open(EXCEL_PATH, "rb") as f:
            st.download_button(
                label="📥 STÁHNOUT EXCEL",
                data=f,
                file_name=f"benchmark_{datetime.datetime.now().strftime('%d_%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    else:
        st.warning("⚠️ Databáze se připravuje (automatický restart)...")
        st.rerun()

# --- ZOBRAZENÍ TABULEK ---
st.divider()
if os.path.exists(EXCEL_PATH):
    try:
        df_display = pd.read_excel(EXCEL_PATH, sheet_name="Products_Tech", dtype=str).replace(['nan', 'None'], '')
        st.subheader("📋 Přehled nalezených technických dat")
        st.dataframe(df_display, use_container_width=True)
    except:
        st.info("Tabulka se připravuje (čekám na první data).")