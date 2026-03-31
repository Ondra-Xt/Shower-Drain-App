import streamlit as st
import json
import os

# --- Configuration Loading ---
def load_config():
    """Loads configuration from JSON files."""
    scoring_path = os.path.join("config", "scoring_settings.json")
    rules_path = os.path.join("config", "reference_rules.json")
    
    scoring_settings = {}
    reference_rules = {}
    
    if os.path.exists(scoring_path):
        with open(scoring_path, "r") as f:
            scoring_settings = json.load(f)
            
    if os.path.exists(rules_path):
        with open(rules_path, "r") as f:
            reference_rules = json.load(f)
            
    return scoring_settings, reference_rules

def save_config(scoring_settings):
    """Saves scoring settings to JSON file."""
    scoring_path = os.path.join("config", "scoring_settings.json")
    with open(scoring_path, "w") as f:
        json.dump(scoring_settings, f, indent=4)

# --- Main App ---
def main():
    st.set_page_config(page_title="Shower Drain Benchmark Agent", layout="wide")
    
    st.title("🚿 Shower Drain Benchmark Agent")
    st.markdown("Automatizovaný benchmarking liniových sprchových žlabů.")

    # --- Sidebar: Configuration ---
    st.sidebar.header("Nastavení Scoringu")
    
    scoring_settings, reference_rules = load_config()
    weights = scoring_settings.get("weights", {})
    
    # Weight Sliders
    new_weights = {}
    new_weights["price"] = st.sidebar.slider("Váha: Cena", 0.0, 1.0, weights.get("price", 0.5))
    new_weights["material_quality"] = st.sidebar.slider("Váha: Materiál", 0.0, 1.0, weights.get("material_quality", 0.2))
    new_weights["installation_height"] = st.sidebar.slider("Váha: Výška instalace", 0.0, 1.0, weights.get("installation_height", 0.15))
    new_weights["flow_rate"] = st.sidebar.slider("Váha: Průtok", 0.0, 1.0, weights.get("flow_rate", 0.15))
    
    scoring_settings["weights"] = new_weights
    
    # Filters
    show_failed = st.sidebar.checkbox("Zobrazit i nevyhovující produkty", value=scoring_settings.get("show_failed_products", False))
    scoring_settings["show_failed_products"] = show_failed
    
    # Save Settings Button
    if st.sidebar.button("Uložit nastavení"):
        save_config(scoring_settings)
        st.sidebar.success("Nastavení uloženo!")
        
    st.sidebar.markdown("---")
    st.sidebar.header("Referenční Produkt")
    ref_prod = reference_rules.get("reference_product", {})
    st.sidebar.info(f"**{ref_prod.get('name', 'N/A')}**\n\n"
                    f"Délka: {ref_prod.get('target_length_mm')} ± {ref_prod.get('tolerance_mm')} mm\n"
                    f"Rozsah: {ref_prod.get('min_length_mm')} - {ref_prod.get('max_length_mm')} mm")

    # --- Main Content ---
    st.header("Přehled Benchmarku")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Spustit Scraping")
        if st.button("Spustit Benchmark (Vše)"):
            st.warning("Funkce scrapingu zatím není implementována.")
            # TODO: Call scrapers here
            
    with col2:
        st.subheader("Výsledky")
        st.info("Zatím žádná data. Spusťte scraping pro získání výsledků.")

if __name__ == "__main__":
    main()
