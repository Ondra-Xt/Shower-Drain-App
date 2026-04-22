import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os
import datetime

# --- CHYTRÁ NAVIGACE ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Cesta k Excelu - upraveno, aby hledal v hlavní složce projektu
EXCEL_PATH = "benchmark_master_v3_fixed.xlsx"

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="Kaldewei Benchmark Dashboard", layout="wide", page_icon="🛀")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .stProgress > div > div > div > div { background-color: #007bff; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# UI APLIKACE (Streamlit)
# ==============================================================================

st.title("🛀 Kaldewei: Master Benchmark Dashboard")
st.markdown("---")

# --- SIDEBAR: PŘEPÍNAČE ---
st.sidebar.header("🔌 1. Výběr konektorů (Značek)")
use_viega = st.sidebar.checkbox("Viega", value=True)
use_geberit = st.sidebar.checkbox("Geberit", value=False)
# ... ostatní značky ponechte jak máte ...

st.sidebar.header("⚙️ 2. Výběr fází ke spuštění")
run_disc = st.sidebar.checkbox("🔍 Discovery (Technická data)", value=True)
run_price = st.sidebar.checkbox("💰 Pricing (Ceny)", value=True)
run_bom = st.sidebar.checkbox("🏗️ BOM Builder (Sestavy)", value=True)

st.sidebar.divider()
target_len = st.sidebar.selectbox("Filtrovat délku v grafech (mm)", [700, 800, 900, 1000, 1200], index=4)
ref_price = st.sidebar.number_input("Ref. cena Kaldewei (EUR)", value=450.0)

# --- HLAVNÍ PLOCHA ---
col_cmd, col_stat = st.columns([1, 2])

with col_cmd:
    st.subheader("🚀 Ovládací panel")
    run_btn = st.button("SPUSTIT VYBRANÉ AGENTY", type="primary")
    
    if run_btn:
        progress = st.progress(0)
        status_msg = st.empty()
        
        try:
            # ==========================================
            # 🔵 VIEGA (OPRAVENÁ SEKCE)
            # ==========================================
            if use_viega:
                st.markdown("### 🔵 Zpracovávám: Viega")
                
                if run_disc:
                    status_msg.info("Viega: Spouštím Discovery (BS4 Stable)...")
                    # VOLÁME OPRAVENÝ SOUBOR
                    from viega_master_discovery import ViegaGreedyMaster
                    agent_disc = ViegaGreedyMaster(excel_path=EXCEL_PATH)
                    agent_disc.run()
                    status_msg.success("Viega: Discovery dokončeno.")

                if run_bom:
                    status_msg.info("Viega: Spouštím BOM Builder...")
                    # VOLÁME OPRAVENÝ BOM BUILDER
                    from viega_bom_builder import ViegaBOMBuilder
                    agent_bom = ViegaBOMBuilder(excel_path=EXCEL_PATH)
                    # Předáme mu URL adresy, které má zpracovat (např. Cleviva)
                    test_urls = ["https://www.viega.de/de/produkte/Katalog/Entwaesserungstechnik/Advantix-Duschrinnen/Advantix-Cleviva-Duschrinnen/Einbauhoehe-ab-95-mm/Advantix-Cleviva-Duschrinne-4981-10.html"]
                    agent_bom.run(test_urls)
                    status_msg.success("Viega: BOM Builder dokončen.")

            # ==========================================
            # 🟢 GEBERIT (Příklad opravy pro stabilitu)
            # ==========================================
            if use_geberit:
                st.markdown("### 🟢 Zpracovávám: Geberit")
                # Zde doporučuji stejný postup - volat BS4 verze pokud je máte
                
            st.balloons()
            st.success("✅ Všechny vybrané operace byly dokončeny!")
            st.rerun() # Automaticky obnoví tabulku s novými daty

        except Exception as e:
            st.error(f"❌ Neočekávaná chyba: {e}")

# --- VIZUALIZACE A DATA ---
st.divider()

if os.path.exists(EXCEL_PATH):
    try:
        # Tlačítko pro stažení - KLÍČOVÉ PRO PREZENTACI
        with open(EXCEL_PATH, "rb") as f:
            st.download_button(
                label="📥 STÁHNOUT AKTUÁLNÍ EXCEL (VÝSLEDKY)",
                data=f,
                file_name=f"benchmark_export_{datetime.datetime.now().strftime('%d_%m')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # Zobrazení dat
        df = pd.read_excel(EXCEL_PATH, sheet_name="Products_Tech")
        if not df.empty:
            st.subheader("📋 Přehled nalezených technických dat")
            st.dataframe(df)
    except Exception as e:
        st.info("Tabulka 'Products_Tech' zatím neobsahuje data nebo se ji nepodařilo načíst.")
else:
    st.warning("Databáze (Excel) zatím nebyla vytvořena. Spusťte Discovery agenta.")