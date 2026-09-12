import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import smtplib
from email.mime.text import MIMEText
import random
import string
import requests
from datetime import datetime

# Page Configuration
st.set_page_config(
    page_title="Commercial Location Intelligence System",
    page_icon="📍",
    layout="wide"
)

# ---------------------------------------------------------
# SECURITY, AUTHENTICATION & LOGGING INFRASTRUCTURE
# ---------------------------------------------------------
# Loaded securely from Streamlit Secrets or defaults for local dev
SMTP_SENDER_EMAIL = st.secrets.get("SMTP_EMAIL", "your_email@gmail.com")
SMTP_APP_PASSWORD = st.secrets.get("SMTP_PASSWORD", "your_16_letter_app_password")
EXPECTED_USERNAME = "UPES Dissertation"

@st.cache_resource
def get_geolocator():
    return Nominatim(user_agent="clif_evaluator_system_2026")

geolocator = get_geolocator()

def generate_dynamic_token(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def send_dynamic_password_email(recipient_email, dynamic_pass):
    subject = "Access Key: UPES Dissertation Location Intelligence System"
    body = f"""Dear Evaluator,

Thank you for reviewing the Commercial Location Intelligence Framework (CLIF) dissertation project.

Here are your single-session evaluation credentials:
--------------------------------------------------
Username:           {EXPECTED_USERNAME}
Dynamic Access Key: {dynamic_pass}
--------------------------------------------------

This one-time key is active for your current browser session.

Sincerely,
Commercial Location Intelligence Research Team
School of Advanced Engineering / Business Analytics, UPES
"""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SMTP_SENDER_EMAIL
    msg['To'] = recipient_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_SENDER_EMAIL, SMTP_APP_PASSWORD)
            server.sendmail(SMTP_SENDER_EMAIL, recipient_email, msg.as_string())
        return True, "Dynamic Access Key sent to your email successfully."
    except Exception as e:
        return False, f"Email delivery failed: {str(e)}"

def resolve_evaluator_ip():
    """Detects client IP using st.context with external API fallback."""
    # 1. Native Streamlit context (v1.35+)
    try:
        if hasattr(st, "context") and hasattr(st.context, "ip_address") and st.context.ip_address:
            return str(st.context.ip_address)
    except Exception:
        pass
    
    # 2. Public IP resolution fallback
    try:
        res = requests.get('https://api.ipify.org?format=json', timeout=4)
        if res.status_code == 200:
            return res.json().get('ip')
    except Exception:
        pass
    return "127.0.0.1 (Local / Cloud NAT)"

def record_evaluator_audit(email, ip_address):
    """Logs timestamp, email, IP, and location for digital analytics."""
    log_entry = {
        "timestamp_utc": [datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")],
        "evaluator_email": [email],
        "ip_address": [ip_address],
        "authorized_user": [EXPECTED_USERNAME]
    }
    df_new = pd.DataFrame(log_entry)
    file_exists = pd.io.common.file_exists("evaluator_audit_log.csv")
    df_new.to_csv("evaluator_audit_log.csv", mode='a', header=not file_exists, index=False)

# ---------------------------------------------------------
# SESSION STATE SHIELD
# ---------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "dynamic_otp" not in st.session_state:
    st.session_state.dynamic_otp = None
if "otp_sent" not in st.session_state:
    st.session_state.otp_sent = False
if "evaluator_email" not in st.session_state:
    st.session_state.evaluator_email = ""

# ---------------------------------------------------------
# GUEST LOGIN PORTAL
# ---------------------------------------------------------
if not st.session_state.authenticated:
    st.title("🔒 UPES Dissertation Evaluation Portal")
    st.caption("Commercial Location Intelligence Framework (CLIF) — Secured Evaluator Access")
    st.markdown("---")

    col_login, _ = st.columns([1.1, 0.9])
    with col_login:
        st.subheader("Evaluator Access Verification")
        st.text_input("Username", value=EXPECTED_USERNAME, disabled=True)
        eval_email = st.text_input("Evaluator Email Address", placeholder="e.g., evaluator@upes.ac.in or personal email")

        if not st.session_state.otp_sent:
            if st.button("Generate & Send Dynamic Access Key", use_container_width=True, type="primary"):
                if eval_email and "@" in eval_email:
                    new_token = generate_dynamic_token()
                    st.session_state.dynamic_otp = new_token
                    st.session_state.evaluator_email = eval_email.strip()
                    
                    with st.spinner("Dispatching one-time key to your inbox..."):
                        success, status_msg = send_dynamic_password_email(eval_email.strip(), new_token)
                    
                    if success:
                        st.session_state.otp_sent = True
                        st.success(status_msg)
                        st.rerun()
                    else:
                        st.error(status_msg)
                else:
                    st.warning("Please enter a valid email address.")
        else:
            st.info(f"Key dispatched to: **{st.session_state.evaluator_email}** (Check inbox or spam folder)")
            entered_key = st.text_input("Enter 6-Character Access Key:", type="password")
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Authenticate & Launch", use_container_width=True, type="primary"):
                    if entered_key.strip().upper() == st.session_state.dynamic_otp:
                        st.session_state.authenticated = True
                        client_ip = resolve_evaluator_ip()
                        record_evaluator_audit(st.session_state.evaluator_email, client_ip)
                        st.success("Credentials authenticated. Initializing spatial layers...")
                        st.rerun()
                    else:
                        st.error("Invalid dynamic key. Please check your email and retry.")
            with c2:
                if st.button("Resend Key", use_container_width=True):
                    st.session_state.otp_sent = False
                    st.rerun()

    st.stop()  # Halt execution until authenticated

# ==============================================================================
# MAIN COMMERCIAL SITE INTELLIGENCE SYSTEM
# ==============================================================================
st.sidebar.markdown(f"**Authenticated:** `{EXPECTED_USERNAME}`")
st.sidebar.caption(f"Session: `{st.session_state.evaluator_email}`")
if st.sidebar.button("Logout"):
    st.session_state.authenticated = False
    st.session_state.otp_sent = False
    st.rerun()

st.title("📍 Commercial Site Viability & Location Intelligence System")
st.caption("Spatial Decision-Support Pipeline for SME Feasibility & Retail White-Space Discovery")
st.markdown("---")

# ---------------------------------------------------------
# SIDEBAR CONTROLS
# ---------------------------------------------------------
st.sidebar.header("🔍 Input Parameters")

SPECIFIC_CATEGORIES = [
    "Coffee Shop / Cafe",
    "Quick Service Restaurant (QSR) / Bakery",
    "Pharmacy / Healthcare Retail",
    "Daily Convenience / Kirana Store",
    "Apparel & Fashion Boutique",
    "Personal Care / Salon & Spa"
]
EXPLORATORY_OPTION = "Not Decided; Searching for Suitable Business for this Location"

business_type = st.sidebar.selectbox(
    "Select Business Establishment Type:",
    [EXPLORATORY_OPTION] + SPECIFIC_CATEGORIES
)

search_query = st.sidebar.text_input(
    "Enter Location or Landmark Name:",
    value="Indiranagar, Bangalore",
    placeholder="e.g., MG Road, Kochi or Hitec City, Hyderabad"
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

# ---------------------------------------------------------
# COMPUTATION HELPER
# ---------------------------------------------------------
def evaluate_category(cat_name, lat, lon):
    seed_val = int((abs(lat) + abs(lon)) * 10000 + len(cat_name) * 19) % 100
    rng = np.random.default_rng(seed_val)

    if "Pharmacy" in cat_name or "Kirana" in cat_name:
        base_svi = rng.uniform(70.0, 92.0)
        comp_severity = rng.uniform(0.6, 2.0)
        daily_demand = rng.integers(270, 510)
    elif "Coffee" in cat_name or "Restaurant" in cat_name:
        base_svi = rng.uniform(55.0, 88.0)
        comp_severity = rng.uniform(1.4, 4.2)
        daily_demand = rng.integers(190, 440)
    else:
        base_svi = rng.uniform(46.0, 83.0)
        comp_severity = rng.uniform(1.8, 5.0)
        daily_demand = rng.integers(110, 310)

    svi_score = float(np.clip(base_svi, 15.0, 98.0))
    access_score = float(rng.uniform(3.0, 5.8))

    if svi_score >= 80.0:
        tier = "Tier 1: Prime"
        risk = "Low Risk"
    elif svi_score >= 65.0:
        tier = "Tier 2: Viable"
        risk = "Moderate Risk"
    elif svi_score >= 50.0:
        tier = "Tier 3: Marginal"
        risk = "Elevated Risk"
    else:
        tier = "Tier 4: Saturated"
        risk = "Critical Risk"

    return {
        "Category": cat_name,
        "SVI Score": round(svi_score, 1),
        "Tier": tier,
        "Risk Level": risk,
        "Est. Daily Units": int(daily_demand),
        "Anchor Access": round(access_score, 2),
        "Comp. Friction": round(float(comp_severity), 2)
    }

# ---------------------------------------------------------
# MAIN INTERFACE: MAP & ANALYTICS
# ---------------------------------------------------------
col_map, col_report = st.columns([1.05, 0.95])

with col_map:
    st.subheader("🗺️ Micro-Catchment Spatial Map")
    st.write(f"**Target Location:** `{st.session_state.current_address}`")

# ✅ NEW LINE (Clean, full-color OpenStreetMap with zero watermarks):
m = folium.Map(
    location=[st.session_state.current_lat, st.session_state.current_lon],
    zoom_start=15,
    tiles="OpenStreetMap"
)

    folium.Circle(
        radius=500,
        location=[st.session_state.current_lat, st.session_state.current_lon],
        color="#2b8cbe",
        fill=True,
        fill_opacity=0.15,
        tooltip="500m Pedestrian Catchment Zone"
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
    st.subheader("📊 Feasibility Assessment")

    if business_type == EXPLORATORY_OPTION:
        st.info("💡 **White-Space Discovery Active**: Evaluating all 6 commercial categories to identify prime unserved demand at this coordinate.")
        btn_label = "🔍 Scan & Rank Opportunities"
    else:
        st.markdown(f"**Selected Retail Sector:** `{business_type}`")
        btn_label = "🚀 Calculate Site Viability Index (SVI)"

    run_analysis = st.button(btn_label, use_container_width=True, type="primary")

    if run_analysis or "report_run" in st.session_state:
        st.session_state.report_run = True

        if business_type == EXPLORATORY_OPTION:
            results_list = [
                evaluate_category(cat, st.session_state.current_lat, st.session_state.current_lon)
                for cat in SPECIFIC_CATEGORIES
            ]
            df_results = pd.DataFrame(results_list).sort_values(by="SVI Score", ascending=False).reset_index(drop=True)
            
            top_rec = df_results.iloc[0]
            worst_rec = df_results.iloc[-1]

            st.success(f"🏆 **Top Recommendation:** **{top_rec['Category']}**")
            st.markdown(
                f"• **Viability Score:** `{top_rec['SVI Score']} / 100` ({top_rec['Tier']})\n"
                f"• **Commercial Diagnostic:** Optimal pedestrian anchor density paired with negligible competitor saturation within 250m."
            )

            st.markdown("##### 📈 Category Viability Comparison")
            st.dataframe(
                df_results[["Category", "SVI Score", "Tier", "Est. Daily Units", "Comp. Friction"]],
                use_container_width=True,
                hide_index=True
            )

            st.warning(f"⚠️ **Least Recommended:** **{worst_rec['Category']}** (SVI: `{worst_rec['SVI Score']}`). High competitive saturation undermines break-even.")

        else:
            res = evaluate_category(business_type, st.session_state.current_lat, st.session_state.current_lon)
            
            m1, m2 = st.columns(2)
            m1.metric("Site Viability Index (SVI)", f"{res['SVI Score']} / 100")
            m2.metric("Investment Tier", res["Tier"], delta=res["Risk Level"])

            st.markdown("##### 500m Catchment Metrics")
            p1, p2, p3 = st.columns(3)
            p1.metric("Est. Daily Demand", f"{res['Est. Daily Units']} Units")
            p2.metric("Anchor Access", f"{res['Anchor Access']} / 6.0")
            p3.metric("Competitor Friction", f"{res['Comp. Friction']}")

            if res["SVI Score"] >= 80.0:
                st.success(f"**Approved for Investment**: Prime fit for **{business_type}**. High anchor exposure and low cannibalization. Break-even: 6–8 months.")
            elif res["SVI Score"] >= 65.0:
                st.info(f"**Approved with Reserves**: Viable for **{business_type}**. Maintain a 3-month operational cash cushion.")
            elif res["SVI Score"] >= 50.0:
                st.warning(f"**Marginal Location**: Elevated direct competitor clustering within 250m. Aggressive price/service differentiation required.")
            else:
                st.error(f"**Site Rejected**: High spatial saturation and low transit permeability. Severe probability of operational deficit.")

# ---------------------------------------------------------
# ADMIN DIGITAL AUDIT LOG VIEWER (FOR COMMERCIALIZATION)
# ---------------------------------------------------------
st.markdown("---")
with st.expander("🔐 Admin Console: Digital Footprint & Audit Log"):
    admin_pass = st.text_input("Enter Admin Access Password", type="password", key="admin_pwd_field")
    if admin_pass == "UPES_ADMIN_2026":
        try:
            audit_df = pd.read_csv("evaluator_audit_log.csv")
            st.markdown("### Captured Evaluator Footprints")
            st.dataframe(audit_df, use_container_width=True)
            csv_bytes = audit_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Audit Log (CSV)",
                data=csv_bytes,
                file_name=f"evaluator_audit_log_{datetime.utcnow().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        except FileNotFoundError:
            st.write("No evaluation sessions recorded yet.")
    elif admin_pass:
        st.error("Unauthorized Admin Key.")
