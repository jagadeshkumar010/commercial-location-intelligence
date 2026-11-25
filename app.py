import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import requests
from datetime import datetime
import os

st.set_page_config(
    page_title="Commercial Location Intelligence System",
    page_icon="📍",
    layout="wide"
)

EXPECTED_USER = "UPES Evaluator"
AUDIT_LOG_FILE = "evaluator_audit_log.csv"
METRICS_FILE = "clif_telemetry_metrics.csv"

@st.cache_resource
def get_geolocator():
    return Nominatim(user_agent="clif_evaluator_system_2026")

geolocator = get_geolocator()

def resolve_evaluator_ip():
    try:
        if hasattr(st, "context") and hasattr(st.context, "ip_address") and st.context.ip_address:
            return str(st.context.ip_address)
    except Exception:
        pass
    try:
        res = requests.get("https://api.ipify.org?format=json", timeout=3)
        if res.status_code == 200:
            return res.json().get("ip", "Unknown")
    except Exception:
        pass
    return "127.0.0.1 (Local / Cloud NAT)"

def load_metrics():
    if os.path.exists(METRICS_FILE):
        try:
            df = pd.read_csv(METRICS_FILE)
            if not df.empty:
                return int(df.loc[0, "total_accesses"]), int(df.loc[0, "reports_downloaded"])
        except Exception:
            pass
    return 0, 0

def save_metrics(access_count, report_count):
    df = pd.DataFrame([{
        "total_accesses": int(access_count),
        "reports_downloaded": int(report_count),
        "last_updated_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }])
    df.to_csv(METRICS_FILE, index=False)

def record_access_event(ip_address):
    log_entry = pd.DataFrame([{
        "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": "APP_ACCESS",
        "ip_address": ip_address,
        "detail": "Evaluator opened workspace"
    }])
    file_exists = os.path.exists(AUDIT_LOG_FILE)
    log_entry.to_csv(AUDIT_LOG_FILE, mode="a", header=not file_exists, index=False)

def record_report_download(report_type, ip_address):
    current_accesses, current_reports = load_metrics()
    new_report_count = current_reports + 1
    st.session_state.reports_downloaded = new_report_count
    save_metrics(current_accesses, new_report_count)

    log_entry = pd.DataFrame([{
        "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": "REPORT_DOWNLOAD",
        "ip_address": ip_address,
        "detail": report_type
    }])
    file_exists = os.path.exists(AUDIT_LOG_FILE)
    log_entry.to_csv(AUDIT_LOG_FILE, mode="a", header=not file_exists, index=False)

# Initialize persistent metrics + single-session tracking
disk_accesses, disk_reports = load_metrics()
if "reports_downloaded" not in st.session_state:
    st.session_state.reports_downloaded = disk_reports

if "session_logged" not in st.session_state:
    client_ip = resolve_evaluator_ip()
    st.session_state.client_ip = client_ip
    new_access_count = disk_accesses + 1
    st.session_state.total_accesses = new_access_count
    save_metrics(new_access_count, st.session_state.reports_downloaded)
    record_access_event(client_ip)
    st.session_state.session_logged = True
else:
    st.session_state.total_accesses = max(disk_accesses, st.session_state.get("total_accesses", disk_accesses))

# ---------------------------------------------------------
# CATEGORY & CONTEXT ASSUMPTION PROFILES (REALISTIC SME BASELINE)
# ---------------------------------------------------------
CATEGORY_PROFILES = {
    "Daily Convenience / Kirana Store": {
        "footfall_range": (85, 155),
        "conv_range": (0.65, 0.75),
        "avg_spend": 125,
        "gross_margin": 0.15,
        "base_opex": 42000,
        "comp_range": (0.8, 2.4),
    },
    "Pharmacy / Healthcare Retail": {
        "footfall_range": (65, 125),
        "conv_range": (0.70, 0.80),
        "avg_spend": 210,
        "gross_margin": 0.19,
        "base_opex": 48000,
        "comp_range": (0.6, 2.0),
    },
    "Coffee Shop / Cafe": {
        "footfall_range": (60, 135),
        "conv_range": (0.55, 0.70),
        "avg_spend": 185,
        "gross_margin": 0.55,
        "base_opex": 78000,
        "comp_range": (1.2, 3.8),
    },
    "Quick Service Restaurant (QSR) / Bakery": {
        "footfall_range": (80, 170),
        "conv_range": (0.60, 0.75),
        "avg_spend": 150,
        "gross_margin": 0.48,
        "base_opex": 72000,
        "comp_range": (1.2, 3.6),
    },
    "Personal Care / Salon & Spa": {
        "footfall_range": (25, 55),
        "conv_range": (0.65, 0.80),
        "avg_spend": 320,
        "gross_margin": 0.60,
        "base_opex": 55000,
        "comp_range": (1.0, 3.2),
    },
    "Apparel & Fashion Boutique": {
        "footfall_range": (30, 75),
        "conv_range": (0.25, 0.40),
        "avg_spend": 650,
        "gross_margin": 0.38,
        "base_opex": 68000,
        "comp_range": (1.0, 3.5),
    },
}

AREA_MULTIPLIERS = {
    "Rural": {"footfall": 0.65, "spend": 0.75, "opex": 0.62, "radius": 800},
    "Hilly Region": {"footfall": 0.58, "spend": 0.85, "opex": 0.78, "radius": 700},
    "Urban": {"footfall": 1.00, "spend": 1.00, "opex": 1.00, "radius": 500},
    "Metro Region": {"footfall": 1.35, "spend": 1.25, "opex": 1.45, "radius": 400},
}

STATE_ECON_MULTIPLIERS = {
    "High-Growth / High-Income State": {"demand": 1.12, "spend": 1.10, "opex": 1.10},
    "Moderate / Developing State": {"demand": 1.00, "spend": 1.00, "opex": 1.00},
    "Lower-Income / Emerging State": {"demand": 0.85, "spend": 0.85, "opex": 0.85},
}

SPECIFIC_CATEGORIES = list(CATEGORY_PROFILES.keys())
EXPLORATORY_OPTION = "Not Decided; Searching for Suitable Business for this Location"

# ---------------------------------------------------------
# HABITABILITY & SITE FEASIBILITY CHECK
# ---------------------------------------------------------
WATER_KEYWORDS = [
    "sea", "ocean", "lake", "river", "reservoir", "dam", "backwater",
    "lagoon", "bay", "gulf", "strait", "canal", "pond", "wetland", "arabian sea", "bay of bengal"
]
UNINHABITED_KEYWORDS = [
    "national park", "wildlife sanctuary", "reserved forest", "forest reserve",
    "tiger reserve", "biosphere", "glacier", "desert", "barren", "uninhabited", "restricted area"
]

def check_site_habitability(lat, lon, address_text, force_mode="Auto-Detect"):
    """
    Checks whether a location is a water body, uninhabited area, or isolated/no-population place.
    Returns (is_possible: bool, status_label: str, reason_detail: str)
    """
    if force_mode == "Force: Water Body":
        return False, "NOT POSSIBLE (Water Body)", "Site falls within or on a water body (sea/lake/river/reservoir); commercial shop construction is not feasible."
    if force_mode == "Force: Uninhabited Area":
        return False, "NOT POSSIBLE (Uninhabited Area)", "Site is located in an uninhabited/restricted/protected zone with no permanent residential catchment."
    if force_mode == "Force: Isolated / No Population":
        return False, "NOT POSSIBLE (Isolated Place)", "Site is an isolated/remote location with negligible or zero nearby population to sustain retail footfall."

    addr_lower = (address_text or "").lower()

    # Check explicit water body keywords
    for kw in WATER_KEYWORDS:
        if kw in addr_lower:
            return False, "NOT POSSIBLE (Water Body)", f"Detected water-body indicator ('{kw}') in location metadata; establishing a conventional retail shop is not feasible."

    # Check explicit uninhabited / protected / non-residential keywords
    for kw in UNINHABITED_KEYWORDS:
        if kw in addr_lower:
            return False, "NOT POSSIBLE (Uninhabited Area)", f"Detected uninhabited/restricted zone indicator ('{kw}'); commercial retail establishment is not feasible."

    # Light reverse-geocode check when coordinates are pinned without a named address
    if addr_lower.startswith("pinned:") or addr_lower.startswith("manual pin:"):
        try:
            rev = geolocator.reverse((lat, lon), timeout=5)
            if rev and rev.address:
                rev_lower = rev.address.lower()
                for kw in WATER_KEYWORDS:
                    if kw in rev_lower:
                        return False, "NOT POSSIBLE (Water Body)", f"Reverse geocoding indicates a water feature ('{kw}') at ({lat:.4f}, {lon:.4f}); shop establishment is not feasible."
                for kw in UNINHABITED_KEYWORDS:
                    if kw in rev_lower:
                        return False, "NOT POSSIBLE (Uninhabited Area)", f"Reverse geocoding indicates an uninhabited/restricted zone ('{kw}') at ({lat:.4f}, {lon:.4f}); shop establishment is not feasible."
            else:
                return False, "NOT POSSIBLE (Isolated Place)", f"No addressable settlement or populated landmark resolved near ({lat:.4f}, {lon:.4f}); location appears isolated/uninhabited."
        except Exception:
            pass

    return True, "FEASIBLE (Populated / Accessible)", "Location appears habitable with a valid settlement/catchment context for retail evaluation."

# ---------------------------------------------------------
# SIDEBAR & TELEMETRY SUMMARY
# ---------------------------------------------------------
st.sidebar.markdown(f"**Workspace:** `{EXPECTED_USER}`")
st.sidebar.caption("Direct access enabled (no login required)")

m_col1, m_col2 = st.sidebar.columns(2)
m_col1.metric("Total Accesses", st.session_state.total_accesses)
m_col2.metric("Reports Downloaded", st.session_state.reports_downloaded)

st.sidebar.markdown("---")
st.sidebar.header("🔍 Location & Economic Context")

business_type = st.sidebar.selectbox(
    "Business / Store Categorization:",
    [EXPLORATORY_OPTION] + SPECIFIC_CATEGORIES
)

area_type = st.sidebar.selectbox(
    "Area / Terrain Type:",
    list(AREA_MULTIPLIERS.keys()),
    index=2
)

state_econ = st.sidebar.selectbox(
    "State Economic Condition:",
    list(STATE_ECON_MULTIPLIERS.keys()),
    index=1
)

search_query = st.sidebar.text_input(
    "Enter Location or Landmark Name:",
    value="Indiranagar, Bangalore",
    placeholder="e.g., MG Road, Kochi or Arabian Sea or Forest Reserve"
)

locate_btn = st.sidebar.button("🔎 Locate & Pin", use_container_width=True)

if "current_lat" not in st.session_state:
    st.session_state.current_lat = 12.9784
    st.session_state.current_lon = 77.6408
    st.session_state.current_address = "Indiranagar, Bengaluru, Karnataka, India"

if locate_btn and search_query:
    try:
        with st.spinner("Geocoding query..."):
            location = geolocator.geocode(search_query, timeout=10)
        if location:
            st.session_state.current_lat = location.latitude
            st.session_state.current_lon = location.longitude
            st.session_state.current_address = location.address
            st.sidebar.success("Location pinned!")
        else:
            st.sidebar.error("Location not resolved. Try adding city or pin-code.")
    except (GeocoderTimedOut, GeocoderServiceError):
        st.sidebar.warning("Geocoding service timed out. Please retry.")

with st.sidebar.expander("⚙️ Manual Coordinate Override"):
    lat_in = st.number_input("Latitude", value=st.session_state.current_lat, format="%.5f")
    lon_in = st.number_input("Longitude", value=st.session_state.current_lon, format="%.5f")
    if st.button("Apply Coordinates"):
        st.session_state.current_lat = lat_in
        st.session_state.current_lon = lon_in
        st.session_state.current_address = f"Manual Pin: ({lat_in:.4f}, {lon_in:.4f})"

with st.sidebar.expander("💰 Optional Cost & Habitability Controls"):
    custom_opex_override = st.number_input(
        "Custom Monthly OpEx Override (₹, 0 = Auto)",
        min_value=0,
        max_value=2000000,
        value=0,
        step=5000
    )
    habitability_mode = st.selectbox(
        "Habitability Check Mode:",
        ["Auto-Detect", "Force: Water Body", "Force: Uninhabited Area", "Force: Isolated / No Population"]
    )

# ---------------------------------------------------------
# HEADER & LIVE COUNTERS
# ---------------------------------------------------------
st.title("📍 Commercial Site Viability & Location Intelligence System")
st.caption("CLIF — Spatial Decision-Support Pipeline with Habitability Guardrails & INR Cashflow Modeling")

top_k1, top_k2, top_k3, top_k4 = st.columns(4)
top_k1.metric("App Access Count", st.session_state.total_accesses)
top_k2.metric("Reports Downloaded", st.session_state.reports_downloaded)
top_k3.metric("Area Archetype", area_type)
top_k4.metric("Catchment Radius", f"{AREA_MULTIPLIERS[area_type]['radius']} m")

st.markdown("---")

# ---------------------------------------------------------
# COMPUTATION HELPER (WITH UNINHABITED / WATER / ISOLATED GUARD)
# ---------------------------------------------------------
def evaluate_category(cat_name, lat, lon, area_key, state_key, address_str, opex_override=0, hab_mode="Auto-Detect"):
    is_feasible, hab_status, hab_reason = check_site_habitability(lat, lon, address_str, hab_mode)

    if not is_feasible:
        return {
            "Category": cat_name,
            "Shop Possible?": "NO",
            "Habitability Status": hab_status,
            "Feasibility Reason": hab_reason,
            "Area Type": area_key,
            "State Economy": state_key,
            "SVI Score": 0.0,
            "Tier": "Tier 4: Non-Feasible",
            "Risk Level": "Not Possible",
            "Est. Daily Footfall": 0,
            "Conversion %": 0.0,
            "Est. Daily Bills": 0,
            "Probable Avg. Spend (₹)": 0,
            "Est. Monthly Revenue (₹)": 0,
            "Gross Margin %": 0.0,
            "Est. Monthly OpEx (₹)": 0,
            "Probable Monthly Cashflow (₹)": 0,
        }

    profile = CATEGORY_PROFILES[cat_name]
    area_cfg = AREA_MULTIPLIERS[area_key]
    state_cfg = STATE_ECON_MULTIPLIERS[state_key]

    seed_val = int((abs(lat) + abs(lon)) * 10000 + len(cat_name) * 19 + len(area_key) * 7 + len(state_key) * 11) % 1000
    rng = np.random.default_rng(seed_val)

    raw_footfall = rng.uniform(profile["footfall_range"][0], profile["footfall_range"][1])
    est_footfall = max(int(round(raw_footfall * area_cfg["footfall"] * state_cfg["demand"])), 8)

    conversion_rate = float(rng.uniform(profile["conv_range"][0], profile["conv_range"][1]))
    est_daily_bills = max(int(round(est_footfall * conversion_rate)), 3)

    probable_avg_spend = int(round(
        profile["avg_spend"] * area_cfg["spend"] * state_cfg["spend"] * rng.uniform(0.92, 1.08)
    ))

    comp_friction = float(rng.uniform(profile["comp_range"][0], profile["comp_range"][1]))
    if area_key == "Rural":
        comp_friction *= 0.65
    elif area_key == "Hilly Region":
        comp_friction *= 0.55
    elif area_key == "Metro Region":
        comp_friction *= 1.20

    access_score = float(rng.uniform(2.6, 5.6))
    if area_key in ["Rural", "Hilly Region"]:
        access_score *= 0.78

    node_centrality = float(rng.uniform(0.015, 0.075))

    norm_demand = float(np.clip(est_daily_bills / 140.0, 0.10, 1.0))
    norm_access = float(np.clip(access_score / 6.0, 0.10, 1.0))
    norm_top = float(np.clip(node_centrality / 0.10, 0.10, 1.0))
    norm_comp = float(np.clip(comp_friction / 4.5, 0.05, 1.0))

    raw_svi = 100.0 * (
        0.442 * norm_demand +
        0.228 * norm_access +
        0.098 * norm_top -
        0.232 * norm_comp +
        0.18
    )
    svi_score = round(float(np.clip(raw_svi, 20.0, 95.0)), 1)

    if svi_score >= 78.0:
        tier = "Tier 1: Prime"
        risk = "Low Risk"
    elif svi_score >= 62.0:
        tier = "Tier 2: Viable"
        risk = "Moderate Risk"
    elif svi_score >= 48.0:
        tier = "Tier 3: Marginal"
        risk = "Elevated Risk"
    else:
        tier = "Tier 4: High Risk"
        risk = "Critical Risk"

    daily_revenue_inr = est_daily_bills * probable_avg_spend
    monthly_revenue_inr = daily_revenue_inr * 30
    gross_margin = profile["gross_margin"]
    monthly_gross_profit_inr = int(round(monthly_revenue_inr * gross_margin))

    if opex_override > 0:
        monthly_opex_inr = int(opex_override)
    else:
        monthly_opex_inr = int(round(
            profile["base_opex"] * area_cfg["opex"] * state_cfg["opex"] * rng.uniform(0.92, 1.08)
        ))

    probable_monthly_cashflow_inr = monthly_gross_profit_inr - monthly_opex_inr

    return {
        "Category": cat_name,
        "Shop Possible?": "YES",
        "Habitability Status": hab_status,
        "Feasibility Reason": hab_reason,
        "Area Type": area_key,
        "State Economy": state_key,
        "SVI Score": svi_score,
        "Tier": tier,
        "Risk Level": risk,
        "Est. Daily Footfall": est_footfall,
        "Conversion %": round(conversion_rate * 100, 1),
        "Est. Daily Bills": est_daily_bills,
        "Probable Avg. Spend (₹)": probable_avg_spend,
        "Est. Monthly Revenue (₹)": int(monthly_revenue_inr),
        "Gross Margin %": round(gross_margin * 100, 1),
        "Est. Monthly OpEx (₹)": monthly_opex_inr,
        "Probable Monthly Cashflow (₹)": int(probable_monthly_cashflow_inr),
    }

# ---------------------------------------------------------
# INTERACTIVE MAP & ASSESSMENT PANEL
# ---------------------------------------------------------
col_map, col_report = st.columns([1.05, 0.95])

with col_map:
    st.subheader("🗺️ Micro-Catchment Spatial Map")
    st.write(f"**Target Location:** `{st.session_state.current_address}`")
    st.caption(f"Context: **{area_type}** | **{state_econ}**")

    m = folium.Map(
        location=[st.session_state.current_lat, st.session_state.current_lon],
        zoom_start=15,
        tiles="OpenStreetMap"
    )

    catchment_radius = AREA_MULTIPLIERS[area_type]["radius"]
    folium.Circle(
        radius=catchment_radius,
        location=[st.session_state.current_lat, st.session_state.current_lon],
        color="#2b8cbe",
        fill=True,
        fill_opacity=0.15,
        tooltip=f"{catchment_radius}m {area_type} Catchment Zone"
    ).add_to(m)

    folium.Marker(
        [st.session_state.current_lat, st.session_state.current_lon],
        popup=f"Selected Site: {business_type}",
        icon=folium.Icon(color="red", icon="briefcase" if business_type != EXPLORATORY_OPTION else "search")
    ).add_to(m)

    map_data = st_folium(m, width="100%", height=430)

    if map_data and map_data.get("last_clicked"):
        clicked_lat = map_data["last_clicked"]["lat"]
        clicked_lon = map_data["last_clicked"]["lng"]
        if round(clicked_lat, 4) != round(st.session_state.current_lat, 4):
            st.session_state.current_lat = clicked_lat
            st.session_state.current_lon = clicked_lon
            st.session_state.current_address = f"Pinned: ({clicked_lat:.4f}, {clicked_lon:.4f})"
            st.rerun()

with col_report:
    st.subheader("📊 Feasibility & INR Cashflow Assessment")

    btn_label = "🔍 Scan & Rank Opportunities" if business_type == EXPLORATORY_OPTION else "🚀 Calculate Viability & INR Cashflow"
    run_analysis = st.button(btn_label, use_container_width=True, type="primary")

    if run_analysis or "report_run" in st.session_state:
        st.session_state.report_run = True

        cats_to_eval = SPECIFIC_CATEGORIES if business_type == EXPLORATORY_OPTION else [business_type]
        results_list = [
            evaluate_category(
                cat,
                st.session_state.current_lat,
                st.session_state.current_lon,
                area_type,
                state_econ,
                st.session_state.current_address,
                custom_opex_override,
                habitability_mode
            )
            for cat in cats_to_eval
        ]
        df_results = pd.DataFrame(results_list)
        if business_type == EXPLORATORY_OPTION:
            df_results = df_results.sort_values(by="SVI Score", ascending=False).reset_index(drop=True)

        st.session_state.current_eval_data = df_results
        first_row = df_results.iloc[0]

        if first_row["Shop Possible?"] == "NO":
            st.error(
                f"🚫 **IT IS NOT POSSIBLE TO ESTABLISH A SHOP AT THIS LOCATION**\n\n"
                f"• **Status:** `{first_row['Habitability Status']}`\n"
                f"• **Reason:** {first_row['Feasibility Reason']}\n"
                f"• **Report Action:** Marked as **Non-Feasible (Shop Not Possible)** with zero projected footfall/revenue in the downloadable report."
            )
        elif business_type == EXPLORATORY_OPTION:
            top_rec = df_results.iloc[0]
            st.success(f"🏆 **Top Fit:** **{top_rec['Category']}** (SVI: `{top_rec['SVI Score']}/100`)")
            st.markdown(
                f"• **Est. Daily Footfall / Bills:** `{top_rec['Est. Daily Footfall']}` $\\rightarrow$ **`{top_rec['Est. Daily Bills']}` bills/day** @ `₹{top_rec['Probable Avg. Spend (₹)']}` avg. spend\n"
                f"• **Probable Monthly INR Cashflow:** **`₹{top_rec['Probable Monthly Cashflow (₹)']:,}`** (Est. Revenue: `₹{top_rec['Est. Monthly Revenue (₹)']:,}` | OpEx: `₹{top_rec['Est. Monthly OpEx (₹)']:,}`)"
            )
            st.dataframe(
                df_results[[
                    "Category", "Shop Possible?", "SVI Score", "Est. Daily Footfall",
                    "Est. Daily Bills", "Probable Avg. Spend (₹)", "Probable Monthly Cashflow (₹)"
                ]],
                use_container_width=True,
                hide_index=True
            )
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Site Viability Index", f"{first_row['SVI Score']} / 100")
            m2.metric("Daily Footfall / Bills", f"{first_row['Est. Daily Footfall']} / {first_row['Est. Daily Bills']}")
            m3.metric("Probable Avg. Spend", f"₹{first_row['Probable Avg. Spend (₹)']}")

            c1, c2, c3 = st.columns(3)
            c1.metric("Est. Monthly Revenue", f"₹{first_row['Est. Monthly Revenue (₹)']:,}")
            c2.metric("Est. Monthly OpEx", f"₹{first_row['Est. Monthly OpEx (₹)']:,}")
            c3.metric("Probable Monthly Cashflow", f"₹{first_row['Probable Monthly Cashflow (₹)']:,}", delta=first_row["Risk Level"])

# ---------------------------------------------------------
# REPORT DOWNLOADS (INCLUDES NON-FEASIBLE / HABITABILITY NOTICE)
# ---------------------------------------------------------
st.markdown("---")
st.subheader("📄 Site Evaluation Report & Data Export")

if "current_eval_data" in st.session_state and not st.session_state.current_eval_data.empty:
    df_out = st.session_state.current_eval_data
    st.dataframe(df_out, use_container_width=True)

    is_shop_possible = (df_out["Shop Possible?"] == "YES").all()
    feasibility_banner = (
        "FEASIBILITY VERDICT: POSSIBLE TO ESTABLISH A SHOP"
        if is_shop_possible else
        f"FEASIBILITY VERDICT: NOT POSSIBLE TO ESTABLISH A SHOP — {df_out.iloc[0]['Habitability Status']} | {df_out.iloc[0]['Feasibility Reason']}"
    )

    report_lines = [
        "CLIF SITE VIABILITY & PROBABLE INR CASHFLOW REPORT",
        f"Generated (UTC): {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Location: {st.session_state.current_address} ({st.session_state.current_lat:.5f}, {st.session_state.current_lon:.5f})",
        f"Area / Terrain Type: {area_type} | State Economic Condition: {state_econ}",
        feasibility_banner,
        "-" * 85,
        df_out.to_string(index=False)
    ]
    report_txt = "\n".join(report_lines).encode("utf-8")

    c_dl1, c_dl2 = st.columns(2)
    with c_dl1:
        st.download_button(
            label="📄 Download Feasibility & INR Cashflow Report (.TXT)",
            data=report_txt,
            file_name=f"clif_feasibility_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            on_click=record_report_download,
            args=("Feasibility & INR Cashflow Report (.TXT)", st.session_state.client_ip)
        )
    with c_dl2:
        st.download_button(
            label="📥 Download Evaluation Table (.CSV)",
            data=df_out.to_csv(index=False).encode("utf-8"),
            file_name=f"clif_evaluation_data_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            on_click=record_report_download,
            args=("Evaluation Table (.CSV)", st.session_state.client_ip)
        )
else:
    st.info("Run an evaluation above to generate and download a site report.")

# ---------------------------------------------------------
# ADMIN TELEMETRY & AUDIT LOG VIEWER
# ---------------------------------------------------------
st.markdown("---")
with st.expander("🔐 Admin Console: Access & Report Download Telemetry"):
    admin_pass = st.text_input("Enter Admin Access Password", type="password", key="admin_pwd_field")
    if admin_pass == "UPES_ADMIN_2026":
        k1, k2 = st.columns(2)
        k1.metric("Total App Accesses", st.session_state.total_accesses)
        k2.metric("Total Reports Downloaded", st.session_state.reports_downloaded)

        if os.path.exists(AUDIT_LOG_FILE):
            audit_df = pd.read_csv(AUDIT_LOG_FILE)
            st.dataframe(audit_df, use_container_width=True)
            st.download_button(
                label="📥 Export Telemetry Audit Log (CSV)",
                data=audit_df.to_csv(index=False).encode("utf-8"),
                file_name=f"clif_telemetry_log_{datetime.utcnow().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                on_click=record_report_download,
                args=("Telemetry Audit Log (.CSV)", st.session_state.client_ip)
            )
        else:
            st.write("No telemetry events recorded yet.")
    elif admin_pass:
        st.error("Unauthorized Admin Key.")
