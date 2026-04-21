import streamlit as st
import pandas as pd
import plotly.express as px
import sys
import os
import datetime
import asyncio
import os
os.system("playwright install chromium")

# --- KRITICKÁ OPRAVA PRO WINDOWS ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# --- CHYTRÁ NAVIGACE ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

base_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))
EXCEL_PATH = os.path.join(base_dir, "benchmark_master_v3_fixed.xlsx")

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
use_hansgrohe = st.sidebar.checkbox("Hansgrohe", value=False)
use_kaldewei = st.sidebar.checkbox("Kaldewei", value=False)
use_schluter = st.sidebar.checkbox("Schlüter", value=False)
use_schuette = st.sidebar.checkbox("Schütte", value=False)
use_tece = st.sidebar.checkbox("TECE", value=False)
use_alca = st.sidebar.checkbox("Alcadrain", value=False)
use_dallmer = st.sidebar.checkbox("Dallmer", value=False)
use_easydrain = st.sidebar.checkbox("Easy Drain", value=False)

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
        active_brands = [use_viega, use_geberit, use_hansgrohe, use_kaldewei, use_schluter, use_schuette, use_tece, use_alca, use_dallmer, use_easydrain]
        
        if not any(active_brands):
            st.error("Vyberte vlevo alespoň jeden konektor (značku)!")
            st.stop()
        if not (run_disc or run_price or run_bom):
            st.error("Vyberte vlevo alespoň jednu fázi ke spuštění!")
            st.stop()

        progress = st.progress(0)
        status_msg = st.empty()
        log_box = st.empty()
        
        try:
            # Dynamický výpočet kroků
            total_steps = sum(active_brands) * (run_disc + run_price + run_bom) 
            current_step = 0
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            def update_progress(msg, step_inc=1):
                global current_step
                current_step += step_inc
                status_msg.info(msg)
                log_box.text(f"🕒 {datetime.datetime.now().strftime('%H:%M:%S')} - {msg}")
                progress.progress(min(current_step / max(total_steps, 1), 1.0))

            # ==========================================
            # 🔵 VIEGA
            # ==========================================
            if use_viega:
                st.markdown("### 🔵 Zpracovávám: Viega")
                if run_disc:
                    update_progress("Viega: Zpracovávám Discovery...", 0)
                    from viega_dynamic_master import ViegaUltraDiscovery
                    agent_disc = ViegaUltraDiscovery(excel_path=EXCEL_PATH)
                    agent_disc.run()
                    update_progress("Viega: Discovery dokončeno.")
                if run_price:
                    update_progress("Viega: Zpracovávám Pricing...", 0)
                    from viega_pricing_protected import ViegaPricingBotProtected
                    agent_price = ViegaPricingBotProtected(excel_path=EXCEL_PATH)
                    agent_price.run()
                    update_progress("Viega: Pricing dokončen.")
                if run_bom:
                    update_progress("Viega: Zpracovávám BOM Builder...", 0)
                    from viega_bom_builder import ViegaBOMBuilder
                    agent_bom = ViegaBOMBuilder(excel_path=EXCEL_PATH)
                    agent_bom.run()
                    update_progress("Viega: BOM Builder dokončen.")

            # ==========================================
            # 🟢 GEBERIT
            # ==========================================
            if use_geberit:
                st.markdown("### 🟢 Zpracovávám: Geberit")
                if run_disc:
                    update_progress("Geberit: Zpracovávám Master Discovery...", 0)
                    from geberit_master_discovery import GeberitMasterDiscovery 
                    agent_g_disc = GeberitMasterDiscovery(excel_path=EXCEL_PATH)
                    agent_g_disc.run()
                    update_progress("Geberit: Zpracovávám Official Specs...", 0)
                    from geberit_official_specs import GeberitOfficialSpecsBot 
                    agent_g_specs = GeberitOfficialSpecsBot(excel_path=EXCEL_PATH)
                    agent_g_specs.run()
                    update_progress("Geberit: Discovery fáze dokončeny.")
                if run_price:
                    update_progress("Geberit: Zpracovávám Pricing...", 0)
                    from geberit_pricing import GeberitPricingV11_EdgeCase
                    agent_g_price = GeberitPricingV11_EdgeCase(excel_path=EXCEL_PATH)
                    agent_g_price.run()
                    update_progress("Geberit: Pricing dokončen.")
                if run_bom:
                    update_progress("Geberit: Zpracovávám BOM Calculator...", 0)
                    from geberit_calculator import GeberitSystemCalculatorFinal 
                    agent_g_bom = GeberitSystemCalculatorFinal(excel_path=EXCEL_PATH)
                    agent_g_bom.run()
                    update_progress("Geberit: BOM Builder dokončen.")

            # ==========================================
            # ⚪ OSTATNÍ ZNAČKY (Zatím jen Discovery)
            # ==========================================
            
            def process_new_brand(brand_name, module_name, class_name):
                st.markdown(f"### ⚪ Zpracovávám: {brand_name}")
                if run_disc:
                    update_progress(f"{brand_name}: Zpracovávám Discovery...", 0)
                    module = __import__(module_name)
                    agent_class = getattr(module, class_name)
                    agent = agent_class(excel_path=EXCEL_PATH)
                    
                    # --- CHYTRÉ VOLÁNÍ FUNKCE ---
                    if hasattr(agent, "run"):
                        agent.run()
                    elif hasattr(agent, "discover"):
                        agent.discover()
                    elif hasattr(agent, "scrape"):
                        agent.scrape()
                    else:
                        st.warning(f"⚠️ {brand_name}: Nenašel jsem spouštěcí funkci (run/discover/scrape).")
                    # ----------------------------
                    
                    update_progress(f"{brand_name}: Discovery dokončeno.")
                if run_price:
                    update_progress(f"{brand_name}: Pricing zatím nenapojen (přeskakuji)...")
                if run_bom:
                    update_progress(f"{brand_name}: BOM zatím nenapojen (přeskakuji)...")

            if use_hansgrohe: process_new_brand("Hansgrohe", "hansgrohe_tech", "HansgroheTechScraperV9")
            if use_kaldewei: process_new_brand("Kaldewei", "kaldewei_tech", "KaldeweiTechScraperV38")
            if use_schluter: process_new_brand("Schlüter", "schluter_tech", "SchluterTechScraperV22")
            if use_schuette: process_new_brand("Schütte", "schuette_tech", "SchuetteTechScraperV8")
            if use_tece: process_new_brand("TECE", "tece_discovery", "TeceDiscovery")
            if use_alca: process_new_brand("Alcadrain", "alca_tech", "AlcaTechScraperV8")
            if use_dallmer: process_new_brand("Dallmer", "dallmer_tech", "DallmerTechScraperV4")
            if use_easydrain: process_new_brand("Easy Drain", "easydrain_tech", "EasyDrainTechScraperV12")

            status_msg.success("✅ Všechny vybrané operace byly úspěšně dokončeny!")
            st.balloons()
            st.cache_data.clear()
            
        except ImportError as e:
            st.error(f"❌ Chyba při načítání modulu: {e}. Zkontrolujte, že se soubor jmenuje přesně jak má.")
        except AttributeError as e:
            st.error(f"❌ Chyba ve jménu třídy: {e}. Otevřete soubor a zkontrolujte název po slově 'class'.")
        except Exception as e:
            st.error(f"❌ Neočekávaná chyba během zpracování: {e}")

# --- VIZUALIZACE ---
st.divider()

if os.path.exists(EXCEL_PATH):
    try:
        st.success(f"📂 Připojeno k databázi: {EXCEL_PATH}")
        df = pd.read_excel(EXCEL_PATH, sheet_name="Comparison_Report")
        if not df.empty:
            df_filtered = df[(df['Total_Price_EUR'] > 0)]
            
            t1, t2 = st.tabs(["📊 Grafy", "📋 Data"])
            with t1:
                fig = px.bar(df_filtered, x="Product_Name", y="Total_Price_EUR", color="Brand", text_auto='.2f')
                fig.add_hline(y=ref_price, line_dash="dash", line_color="red", annotation_text="Kaldewei Ref.")
                st.plotly_chart(fig)
            with t2:
                st.dataframe(df_filtered)
    except Exception as e:
        st.info("Čekám na vygenerování kompletního 'Comparison_Report' se všemi daty a cenami.")
else:
    st.error(f"👋 Databáze zatím neexistuje na cestě: {EXCEL_PATH}. Klikněte na tlačítko výše.")