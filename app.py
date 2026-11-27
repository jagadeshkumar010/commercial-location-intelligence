import numpy as np
import pandas as pd
import streamlit as st
import xgboost as xgb
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import MinMaxScaler

try:
    import plotly.express as px

    HAS_PLOTLY = True
except ModuleNotFoundError:
    px = None
    HAS_PLOTLY = False

STREAMLIT_APP_URL = "https://commercial-location-intelligence-khjt7prif574msk2tvddnf.streamlit.app/"
GITHUB_REPO_URL = "https://github.com/jagadeshkumar010/commercial-location-intelligence"

st.set_page_config(
    page_title="Commercial Location Intelligence & SME Feasibility",
    page_icon="📍",
    layout="wide",
)

# Format-calibrated AHP weights (CR <= 0.021 across retail formats)
AHP_WEIGHTS: dict[str, dict[str, float]] = {
    "Kirana / Daily Needs": {"w1": 0.34, "w2": 0.28, "w3": 0.38},
    "Quick-Service Restaurant (QSR)": {"w1": 0.36, "w2": 0.24, "w3": 0.40},
    "Pharmacy & Personal Care": {"w1": 0.38, "w2": 0.22, "w3": 0.40},
    "Specialty Apparel": {"w1": 0.48, "w2": 0.19, "w3": 0.33},
    "General SME Baseline": {"w1": 0.39, "w2": 0.24, "w3": 0.37},
}

# Dual-use Residential Liveability Index (RLI) weights
RLI_WEIGHTS: dict[str, float] = {
    "healthcare": 0.30,
    "education": 0.25,
    "transit": 0.25,
    "green_space": 0.20,
}


def gaussian_accessibility(distances_m: np.ndarray, sigma_m: float = 500.0) -> float:
    """Compute continuous Gaussian distance-decay accessibility across anchor nodes."""
    d = np.asarray(distances_m, dtype=float)
    return float(np.sum(np.exp(-(d ** 2) / (2.0 * (sigma_m ** 2)))))


@st.cache_data
def generate_candidate_nodes(n_nodes: int = 500, seed: int = 42) -> pd.DataFrame:
    """Generate stratified Tier-2 urban candidate retail nodes across three ward types."""
    rng = np.random.default_rng(seed)
    tiers = rng.choice(
        ["High-Density CBD", "Mixed-Use Residential", "Emerging Peri-Urban"],
        size=n_nodes,
        p=[0.28, 0.42, 0.30],
    )

    pop_density = np.zeros(n_nodes)
    comp_250m = np.zeros(n_nodes)
    comp_500m = np.zeros(n_nodes)
    anchors_500m = np.zeros(n_nodes)
    transit_dist_m = np.zeros(n_nodes)
    betweenness_cb = np.zeros(n_nodes)
    accessibility = np.zeros(n_nodes)
    base_demand = np.zeros(n_nodes)
    monthly_rent_inr = np.zeros(n_nodes)
    lat = np.zeros(n_nodes)
    lon = np.zeros(n_nodes)

    base_lat, base_lon = 12.3051, 76.6551

    for i, tier in enumerate(tiers):
        if tier == "High-Density CBD":
            pop_density[i] = rng.normal(18450, 3120)
            comp_250m[i] = max(1, rng.normal(14.8, 4.6))
            comp_500m[i] = max(3, rng.normal(46.2, 11.3))
            anchors_500m[i] = max(2, rng.normal(18.5, 5.2))
            transit_dist_m[i] = max(35, rng.normal(142, 68))
            betweenness_cb[i] = np.clip(rng.normal(0.084, 0.031), 0.01, 0.22)
            base_demand[i] = rng.normal(480, 95)
            monthly_rent_inr[i] = rng.normal(68000, 14000)
            lat[i] = base_lat + rng.uniform(-0.015, 0.015)
            lon[i] = base_lon + rng.uniform(-0.015, 0.015)
        elif tier == "Mixed-Use Residential":
            pop_density[i] = rng.normal(12840, 2490)
            comp_250m[i] = max(0, rng.normal(6.4, 2.9))
            comp_500m[i] = max(1, rng.normal(19.7, 6.8))
            anchors_500m[i] = max(1, rng.normal(9.2, 3.4))
            transit_dist_m[i] = max(60, rng.normal(285, 115))
            betweenness_cb[i] = np.clip(rng.normal(0.049, 0.022), 0.008, 0.14)
            base_demand[i] = rng.normal(390, 80)
            monthly_rent_inr[i] = rng.normal(36000, 8500)
            lat[i] = base_lat + rng.uniform(-0.035, 0.035)
            lon[i] = base_lon + rng.uniform(-0.035, 0.035)
        else:
            pop_density[i] = rng.normal(5620, 1780)
            comp_250m[i] = max(0, rng.normal(2.1, 1.4))
            comp_500m[i] = max(0, rng.normal(6.8, 3.5))
            anchors_500m[i] = max(0, rng.normal(3.4, 1.9))
            transit_dist_m[i] = max(150, rng.normal(640, 245))
            betweenness_cb[i] = np.clip(rng.normal(0.026, 0.015), 0.004, 0.09)
            base_demand[i] = rng.normal(195, 60)
            monthly_rent_inr[i] = rng.normal(18000, 5000)
            lat[i] = base_lat + rng.uniform(-0.06, 0.06)
            lon[i] = base_lon + rng.uniform(-0.06, 0.06)

        anchor_dists = np.abs(rng.normal(transit_dist_m[i], 180, size=8))
        accessibility[i] = gaussian_accessibility(anchor_dists, sigma_m=500.0)

    df = pd.DataFrame({
        "node_id": [f"NODE_{i + 1:03d}" for i in range(n_nodes)],
        "ward_morphology": tiers,
        "lat": np.round(lat, 6),
        "lon": np.round(lon, 6),
        "pop_density": np.round(np.clip(pop_density, 1500, 30000), 0),
        "competitors_250m": np.round(comp_250m, 1),
        "competitors_500m": np.round(comp_500m, 1),
        "anchors_500m": np.round(anchors_500m, 1),
        "transit_dist_m": np.round(transit_dist_m, 0),
        "betweenness_cb": np.round(betweenness_cb, 3),
        "accessibility_score": np.round(accessibility, 2),
        "pred_daily_demand": np.round(np.clip(base_demand, 50, 900), 1),
        "monthly_rent_inr": np.round(np.clip(monthly_rent_inr, 8000, 150000), 0),
    })

    scaler = MinMaxScaler()
    h_acc = scaler.fit_transform(
        (df["anchors_500m"] * 0.4 + df["accessibility_score"] * 0.6).to_numpy().reshape(-1, 1)
    ).ravel()
    e_acc = scaler.fit_transform(
        (df["pop_density"] * 0.5 + df["anchors_500m"] * 0.5).to_numpy().reshape(-1, 1)
    ).ravel()
    t_acc = scaler.fit_transform(
        df["accessibility_score"].to_numpy().reshape(-1, 1)
    ).ravel()
    g_acc = scaler.fit_transform(
        (1.0 / (1.0 + df["competitors_250m"] / 10.0)).to_numpy().reshape(-1, 1)
    ).ravel()

    rli_raw = (
        RLI_WEIGHTS["healthcare"] * h_acc
        + RLI_WEIGHTS["education"] * e_acc
        + RLI_WEIGHTS["transit"] * t_acc
        + RLI_WEIGHTS["green_space"] * g_acc
    )
    df["rli_score"] = np.round(
        scaler.fit_transform(rli_raw.reshape(-1, 1)).ravel() * 100.0, 1
    )
    return df


def run_clustering(df: pd.DataFrame, n_clusters: int = 4) -> pd.DataFrame:
    """Segment nodes into market archetypes using K-Means and detect white spaces via DBSCAN."""
    out = df.copy()
    features = out[["pred_daily_demand", "competitors_500m", "accessibility_score"]]
    scaled = MinMaxScaler().fit_transform(features)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    raw_labels = kmeans.fit_predict(scaled)

    cluster_map = {
        0: "Cluster 1: High-Potential White Spaces",
        1: "Cluster 2: Hyper-Saturated Red Oceans",
        2: "Cluster 3: Balanced Growth Corridors",
        3: "Cluster 4: Low-Density Peripheral Zones",
    }
    order = (
        out.assign(_lbl=raw_labels)
        .groupby("_lbl")[["pred_daily_demand", "competitors_500m"]]
        .mean()
    )
    white_space_lbl = int((order["pred_daily_demand"] - order["competitors_500m"] * 4).idxmax())
    red_ocean_lbl = int(order["competitors_500m"].idxmax())
    low_dem_lbl = int(order["pred_daily_demand"].idxmin())
    remaining = [c for c in range(n_clusters) if c not in {white_space_lbl, red_ocean_lbl, low_dem_lbl}]
    balanced_lbl = remaining[0] if remaining else 0

    label_lookup = {
        white_space_lbl: cluster_map[0],
        red_ocean_lbl: cluster_map[1],
        balanced_lbl: cluster_map[2],
        low_dem_lbl: cluster_map[3],
    }
    out["market_archetype"] = [label_lookup[c] for c in raw_labels]

    dbscan = DBSCAN(eps=0.25, min_samples=4)
    out["dbscan_cluster"] = dbscan.fit_predict(scaled)
    return out


def compute_svi(
    df: pd.DataFrame,
    weights: dict[str, float],
    rent_shock_pct: float = 0.0,
    demand_shock_pct: float = 0.0,
    extra_competitors_250m: int = 0,
) -> pd.DataFrame:
    """Compute normalized Demand, Competition, Gaussian Accessibility, and SVI (0-100)."""
    out = df.copy()
    scaler = MinMaxScaler()

    adj_demand = out["pred_daily_demand"] * (1.0 + demand_shock_pct / 100.0)
    adj_comp = out["competitors_500m"] + extra_competitors_250m * 2.5
    rent_penalty = np.maximum(0.0, rent_shock_pct / 100.0) * 0.22

    d_norm = scaler.fit_transform(adj_demand.to_numpy().reshape(-1, 1)).ravel()
    c_norm = scaler.fit_transform(adj_comp.to_numpy().reshape(-1, 1)).ravel()
    a_norm = scaler.fit_transform(out["accessibility_score"].to_numpy().reshape(-1, 1)).ravel()

    raw_svi = (
        weights["w1"] * d_norm
        - weights["w2"] * c_norm
        + weights["w3"] * a_norm
        - rent_penalty
    )
    svi_scaled = np.clip(
        scaler.fit_transform(raw_svi.reshape(-1, 1)).ravel() * 100.0, 0.0, 100.0
    )
    out["svi_score"] = np.round(svi_scaled, 1)
    out["risk_tier"] = pd.cut(
        out["svi_score"],
        bins=[-1, 34.9, 54.9, 74.9, 100],
        labels=[
            "Tier 4: Non-Viable",
            "Tier 3: Marginal",
            "Tier 2: Moderate",
            "Tier 1: High Viability",
        ],
    )
    return out


def run_monte_carlo_stress(
    base_df: pd.DataFrame,
    weights: dict[str, float],
    n_iter: int = 1000,
    seed: int = 42,
) -> pd.DataFrame:
    """Simulate compound rent surge (+25%), demand drop (-15%), and new rivals (+2)."""
    rng = np.random.default_rng(seed)
    viable_counts = []
    for _ in range(n_iter):
        r_shock = rng.normal(25.0, 4.0)
        d_shock = rng.normal(-15.0, 3.0)
        c_shock = int(np.clip(rng.poisson(2), 0, 5))
        stressed = compute_svi(
            base_df,
            weights,
            rent_shock_pct=r_shock,
            demand_shock_pct=d_shock,
            extra_competitors_250m=c_shock,
        )
        viable_counts.append(float((stressed["svi_score"] >= 55.0).mean() * 100.0))

    return pd.DataFrame({"pct_remaining_viable": viable_counts})


def run_xgboost_demo(category: str, seed: int = 42) -> tuple[pd.DataFrame, dict[str, float]]:
    """Train a demonstration XGBoost demand regressor on synthetic daily retail series."""
    rng = np.random.default_rng(seed)
    n_days = 180
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    category_scale = {
        "Kirana / Daily Needs": 260.0,
        "Quick-Service Restaurant (QSR)": 340.0,
        "Pharmacy & Personal Care": 190.0,
        "Specialty Apparel": 150.0,
        "General SME Baseline": 240.0,
    }.get(category, 240.0)

    dow = dates.dayofweek.to_numpy()
    weekend_boost = np.where(dow >= 5, 1.22, 1.0)
    seasonal = 1.0 + 0.12 * np.sin(2 * np.pi * np.arange(n_days) / 30.0)
    pop_proxy = np.full(n_days, 12840.0) + rng.normal(0, 400, size=n_days)
    demand = category_scale * weekend_boost * seasonal + rng.normal(0, 14, size=n_days)

    work = pd.DataFrame({
        "date": dates,
        "actual_demand": np.round(demand, 1),
        "dow": dow,
        "pop_proxy": pop_proxy,
    })
    work["lag_1"] = work["actual_demand"].shift(1)
    work["lag_7"] = work["actual_demand"].shift(7)
    work["roll_7"] = work["actual_demand"].rolling(7).mean()
    work = work.dropna().reset_index(drop=True)

    feature_cols = ["lag_1", "lag_7", "roll_7", "dow", "pop_proxy"]
    split = int(len(work) * 0.8)
    X_train, y_train = work[feature_cols].iloc[:split], work["actual_demand"].iloc[:split]
    X_test, y_test = work[feature_cols].iloc[split:], work["actual_demand"].iloc[split:]

    model = xgb.XGBRegressor(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.85,
        random_state=seed,
    )
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    metrics = {
        "RMSE": round(float(np.sqrt(mean_squared_error(y_test, preds))), 2),
        "MAE": round(float(mean_absolute_error(y_test, preds)), 2),
        "MAPE (%)": round(float(np.mean(np.abs((y_test - preds) / np.maximum(y_test, 1.0))) * 100.0), 2),
        "R2": round(float(r2_score(y_test, preds)), 3),
    }
    test_df = pd.DataFrame({
        "Date": work["date"].iloc[split:].dt.strftime("%Y-%m-%d"),
        "Actual Demand": np.round(y_test.to_numpy(), 1),
        "XGBoost Forecast": np.round(preds, 1),
    })
    return test_df, metrics


def main() -> None:
    st.title("Commercial Location Intelligence & SME Feasibility Dashboard")
    st.markdown(
        f"**Live Streamlit App:** [{STREAMLIT_APP_URL}]({STREAMLIT_APP_URL}) &nbsp;|&nbsp; "
        f"**GitHub Repository:** [{GITHUB_REPO_URL}]({GITHUB_REPO_URL})"
    )

    if not HAS_PLOTLY:
        st.warning(
            "`plotly` is not installed in the active environment; rendering built-in Streamlit charts. "
            "Add `plotly>=5.20.0` to `requirements.txt` and reboot for interactive Plotly charts."
        )

    st.sidebar.header("Site & Scenario Controls")
    retail_format = st.sidebar.selectbox("Retail Format (AHP Weights)", list(AHP_WEIGHTS.keys()))
    morphology_filter = st.sidebar.multiselect(
        "Ward Morphology Filter",
        ["High-Density CBD", "Mixed-Use Residential", "Emerging Peri-Urban"],
        default=["High-Density CBD", "Mixed-Use Residential", "Emerging Peri-Urban"],
    )

    st.sidebar.subheader("Stress-Test Perturbations")
    rent_shock = st.sidebar.slider("Commercial Rent Surge (%)", 0, 50, 0, step=5)
    demand_shock = st.sidebar.slider("Catchment Demand Shift (%)", -35, 25, 0, step=5)
    extra_rivals = st.sidebar.slider("New Competitors (<250m)", 0, 6, 0, step=1)

    nodes_df = generate_candidate_nodes(n_nodes=500, seed=42)
    clustered_df = run_clustering(nodes_df, n_clusters=4)
    scored_df = compute_svi(
        clustered_df,
        weights=AHP_WEIGHTS[retail_format],
        rent_shock_pct=rent_shock,
        demand_shock_pct=demand_shock,
        extra_competitors_250m=extra_rivals,
    )

    if morphology_filter:
        view_df = scored_df[scored_df["ward_morphology"].isin(morphology_filter)].copy()
    else:
        view_df = scored_df.copy()

    white_spaces = view_df[view_df["market_archetype"] == "Cluster 1: High-Potential White Spaces"]
    tier1_count = int((view_df["svi_score"] >= 75.0).sum())
    top_row = view_df.sort_values("svi_score", ascending=False).iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Evaluated Candidate Nodes", len(view_df))
    c2.metric("Mean SVI Score", f"{view_df['svi_score'].mean():.1f} / 100")
    c3.metric("Tier 1 High-Viability Sites", tier1_count)
    c4.metric("White-Space Nodes (Cluster 1)",
