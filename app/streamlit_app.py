"""
Score d'Impact Environnemental de l'Assiette Mondiale
Application Streamlit — Jedha Bloc 6
"""

import os
import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sklearn.preprocessing import StandardScaler

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Impact Environnemental Alimentaire",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

CLUSTER_LABELS = {
    0: "Producteurs intensifs",
    1: "Développement agricole",
    2: "Pays riches",
    3: "Émergents urbains",
    4: "Faible revenu",
}
CLUSTER_COLORS = {
    0: "#e74c3c",
    1: "#3498db",
    2: "#2ecc71",
    3: "#f39c12",
    4: "#9b59b6",
}
CLUSTER_DESCRIPTIONS = {
    0: "CO₂/hab élevé malgré faible PIB. Production massive de tubercules/racines.",
    1: "PIB intermédiaire, agriculture étendue, part animale modérée.",
    2: "PIB très élevé, très urbanisés, part animale la plus forte.",
    3: "PIB moyen, très urbanisés, peu de surface agricole → importateurs nets.",
    4: "CO₂/hab le plus bas, peu urbanisés, faible part animale.",
}

FEATURES_NUM = ["quantite_1000t", "pib_per_capita", "taux_urbanisation", "population", "surface_agricole"]
FEATURES_CAT = ["categorie", "region"]
CLUSTER_FEATURES = ["co2_per_capita", "pib_per_capita", "taux_urbanisation", "pct_animal", "surface_agricole"]

REGIONS = ["Asia", "Europe", "Americas", "Africa", "Oceania"]

# Portions standard par aliment (grammes)
PORTION_STANDARD = {
    "Boeuf":                    150,
    "Agneau":                   150,
    "Porc":                     150,
    "Volaille":                 130,
    "Poisson (élevage)":        130,
    "Oeufs":                     60,
    "Lait / Produits laitiers": 200,
    "Riz":                      180,
    "Blé / Céréales":            80,
    "Légumineuses":             150,
    "Légumes":                  150,
    "Fruits":                   150,
    "Sucre":                     20,
    "Huiles végétales":          15,
    "Racines & Tubercules":     150,
}

# Fréquences de consommation → facteur journalier
FREQ_OPTIONS = [
    "Jamais",
    "1×/mois",
    "1×/semaine",
    "2-3×/semaine",
    "1×/jour",
    "2×/jour",
]
FREQ_TO_DAILY = {
    "Jamais":         0,
    "1×/mois":        1 / 30,
    "1×/semaine":     1 / 7,
    "2-3×/semaine":   2.5 / 7,
    "1×/jour":        1,
    "2×/jour":        2,
}

# Multiplicateurs de portion
PORTION_MULT = {"Petite": 0.7, "Normale": 1.0, "Grande": 1.4}

METRIC_OPTIONS = {
    "CO₂ total (kg)":            "co2_total",
    "CO₂ par habitant (kg/hab)": "co2_per_capita",
    "PIB / habitant ($)":        "pib_per_capita",
    "Taux d'urbanisation (%)":   "taux_urbanisation",
    "Part animale (% CO₂)":      "pct_animal",
}

CO2_FACTORS = {
    "Boeuf":                    59.6,
    "Agneau":                   24.5,
    "Porc":                      7.6,
    "Volaille":                  6.1,
    "Poisson (élevage)":        13.6,
    "Oeufs":                     4.5,
    "Lait / Produits laitiers":  3.2,
    "Riz":                       2.7,
    "Blé / Céréales":            1.4,
    "Légumineuses":              0.9,
    "Légumes":                   0.4,
    "Fruits":                    0.4,
    "Sucre":                     1.5,
    "Huiles végétales":          3.8,
    "Racines & Tubercules":      0.3,
}

FOOD_CATEGORY = {
    "Boeuf":                    "Meat",
    "Agneau":                   "Meat",
    "Porc":                     "Meat",
    "Volaille":                 "Meat",
    "Poisson (élevage)":        "Fish & Seafood",
    "Oeufs":                    "Eggs",
    "Lait / Produits laitiers": "Dairy",
    "Riz":                      "Cereals & Grains",
    "Blé / Céréales":           "Cereals & Grains",
    "Légumineuses":             "Pulses",
    "Légumes":                  "Vegetables",
    "Fruits":                   "Fruits",
    "Sucre":                    "Sugar & Sweeteners",
    "Huiles végétales":         "Vegetable Oils",
    "Racines & Tubercules":     "Roots & Tubers",
}


# ──────────────────────────────────────────────────────────────
# DB / Modèles
# ──────────────────────────────────────────────────────────────
@st.cache_resource
def get_engine():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db   = os.getenv("POSTGRES_DB",   "food_impact")
    user = os.getenv("POSTGRES_USER", "food_user")
    pwd  = os.getenv("POSTGRES_PASSWORD", "food_pass")
    return create_engine(f"postgresql://{user}:{pwd}@{host}:{port}/{db}", echo=False)


@st.cache_resource
def load_models():
    model_dir = BASE_DIR / "models"
    return (
        joblib.load(model_dir / "model_impact.pkl"),
        joblib.load(model_dir / "model_clustering.pkl"),
    )


@st.cache_data(ttl=3600)
def query(_engine, sql: str) -> pd.DataFrame:
    with _engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def db_available(engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@st.cache_data(ttl=3600)
def load_ref_data(_engine, connected: bool):
    if not connected:
        return None, None
    pays_df = query(_engine, "SELECT pays_id, nom_pays, code_iso3, region FROM dim_pays ORDER BY nom_pays")
    annees_df = query(_engine, "SELECT DISTINCT annee FROM dim_temps ORDER BY annee")
    return pays_df, annees_df


# ──────────────────────────────────────────────────────────────
# Queries métier
# ──────────────────────────────────────────────────────────────
def query_pays_annee(engine, annee: int) -> pd.DataFrame:
    return query(engine, f"""
        SELECT
            p.nom_pays,
            p.code_iso3 AS iso3,
            p.region,
            SUM(f.co2_total_kg)    AS co2_total,
            SUM(f.quantite_1000t)  AS quantite_total,
            AVG(s.population)      AS population,
            AVG(s.pib_per_capita)  AS pib_per_capita,
            AVG(s.taux_urbanisation) AS taux_urbanisation,
            AVG(s.surface_agricole)  AS surface_agricole,
            SUM(CASE WHEN pr.categorie IN ('Meat','Dairy','Eggs','Fish & Seafood')
                     THEN f.co2_total_kg ELSE 0 END) AS co2_animal
        FROM fait_impact_pays_annee f
        JOIN dim_pays     p  ON f.pays_id    = p.pays_id
        JOIN dim_temps    t  ON f.annee_id   = t.annee_id
        JOIN dim_produits pr ON f.produit_id = pr.produit_id
        LEFT JOIN dim_socio_economique s
               ON f.pays_id = s.pays_id AND f.annee_id = s.annee_id
        WHERE t.annee = {annee}
        GROUP BY p.nom_pays, p.code_iso3, p.region
    """)


def enrich_pays_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["co2_per_capita"] = df["co2_total"] / df["population"].replace(0, np.nan)
    df["pct_animal"] = df["co2_animal"] / (df["co2_total"] + 1e-10) * 100
    return df


def query_evol_pays(engine, iso3: str) -> pd.DataFrame:
    return query(engine, f"""
        SELECT
            t.annee,
            SUM(f.co2_total_kg) AS co2_total,
            AVG(s.population)   AS population
        FROM fait_impact_pays_annee f
        JOIN dim_pays  p ON f.pays_id  = p.pays_id
        JOIN dim_temps t ON f.annee_id = t.annee_id
        LEFT JOIN dim_socio_economique s
               ON f.pays_id = s.pays_id AND f.annee_id = s.annee_id
        WHERE p.code_iso3 = '{iso3}'
        GROUP BY t.annee
        ORDER BY t.annee
    """)


def query_baseline_pays(engine, iso3: str) -> pd.DataFrame:
    return query(engine, f"""
        SELECT SUM(f.co2_total_kg) AS co2_total, AVG(s.population) AS population
        FROM fait_impact_pays_annee f
        JOIN dim_pays  p ON f.pays_id  = p.pays_id
        JOIN dim_temps t ON f.annee_id = t.annee_id
        LEFT JOIN dim_socio_economique s
               ON f.pays_id = s.pays_id AND f.annee_id = s.annee_id
        WHERE p.code_iso3 = '{iso3}'
          AND t.annee = (
              SELECT MAX(t2.annee) FROM dim_temps t2
              JOIN fait_impact_pays_annee f2 ON f2.annee_id = t2.annee_id
              JOIN dim_pays p2 ON f2.pays_id = p2.pays_id
              WHERE p2.code_iso3 = '{iso3}'
          )
    """)


def query_baseline_region(engine, region: str) -> pd.DataFrame:
    return query(engine, f"""
        SELECT SUM(f.co2_total_kg) AS co2_total, SUM(s.population) AS population
        FROM fait_impact_pays_annee f
        JOIN dim_pays  p ON f.pays_id  = p.pays_id
        JOIN dim_temps t ON f.annee_id = t.annee_id
        LEFT JOIN dim_socio_economique s
               ON f.pays_id = s.pays_id AND f.annee_id = s.annee_id
        WHERE p.region = '{region}'
          AND t.annee = (SELECT MAX(annee) FROM dim_temps)
    """)


def query_production_par_categorie(engine, iso3: str, annee: int) -> pd.DataFrame:
    return query(engine, f"""
        SELECT
            pr.categorie,
            SUM(f.quantite_1000t) AS quantite_1000t
        FROM fait_impact_pays_annee f
        JOIN dim_pays     p  ON f.pays_id    = p.pays_id
        JOIN dim_temps    t  ON f.annee_id   = t.annee_id
        JOIN dim_produits pr ON f.produit_id = pr.produit_id
        WHERE p.code_iso3 = '{iso3}' AND t.annee = {annee}
        GROUP BY pr.categorie
    """)


def query_baseline_monde(engine) -> pd.DataFrame:
    return query(engine, """
        SELECT SUM(f.co2_total_kg) AS co2_total, SUM(s.population) AS population
        FROM fait_impact_pays_annee f
        JOIN dim_temps t ON f.annee_id = t.annee_id
        LEFT JOIN dim_socio_economique s
               ON f.pays_id = s.pays_id AND f.annee_id = s.annee_id
        WHERE t.annee = (SELECT MAX(annee) FROM dim_temps)
    """)


# ──────────────────────────────────────────────────────────────
# Clustering helper
# ──────────────────────────────────────────────────────────────
def apply_clustering(df: pd.DataFrame, model) -> pd.DataFrame:
    df = df.dropna(subset=CLUSTER_FEATURES).copy()
    if len(df) < 5:
        return df
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[CLUSTER_FEATURES])
    df["cluster"] = model.predict(X_scaled)
    df["cluster_label"] = df["cluster"].map(CLUSTER_LABELS)
    df["cluster_display"] = df["cluster"].astype(str) + " — " + df["cluster_label"]
    return df


# ──────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🌍 Impact Alimentaire")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        ["🗺️ Explorer les pays", "🍽️ Simulateur Menu", "📈 Prédiction Scénarios"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("Projet Jedha Bloc 6 · 2025-2026")

engine = get_engine()
connected = db_available(engine)
model_impact, model_clustering = load_models()
pays_df, annees_df = load_ref_data(engine, connected)

if not connected:
    st.warning(
        "Base de données non disponible. "
        "Démarrez PostgreSQL avec `docker compose -f docker/docker-compose.yml up -d`."
    )


# ══════════════════════════════════════════════════════════════
# PAGE 1 — Explorer les pays
# ══════════════════════════════════════════════════════════════
if page == "🗺️ Explorer les pays":
    st.title("🗺️ Explorer les pays")

    if not connected:
        st.error("Cette page nécessite la connexion à la base de données PostgreSQL.")
        st.stop()

    # ── Filtres ────────────────────────────────────────────────
    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 1])
    annees = sorted(annees_df["annee"].tolist())
    annee_sel = col_f1.selectbox("Année", annees, index=len(annees) - 1)
    region_sel = col_f2.selectbox("Région", ["Toutes"] + REGIONS)
    metric_sel = col_f3.selectbox("Métrique", list(METRIC_OPTIONS.keys()))
    show_clusters = col_f4.toggle("Clusters", value=False)
    metric_col = METRIC_OPTIONS[metric_sel]

    # ── Données ────────────────────────────────────────────────
    pays_agg = enrich_pays_df(query_pays_annee(engine, annee_sel))
    pays_display = (
        pays_agg[pays_agg["region"] == region_sel].copy()
        if region_sel != "Toutes"
        else pays_agg.copy()
    )
    pays_clustered = apply_clustering(pays_agg, model_clustering)

    # ── Sélection pays ─────────────────────────────────────────
    if "selected_iso3" not in st.session_state:
        st.session_state["selected_iso3"] = None

    iso3_to_name = pays_display.dropna(subset=["nom_pays"]).set_index("iso3")["nom_pays"].to_dict()
    name_to_iso3 = {v: k for k, v in iso3_to_name.items()}
    pays_names = sorted(iso3_to_name.values())

    current_iso3 = st.session_state["selected_iso3"]
    current_name = iso3_to_name.get(current_iso3) if current_iso3 in iso3_to_name else None
    select_idx = (pays_names.index(current_name) + 1) if current_name in pays_names else 0

    selected_name = st.selectbox(
        "Sélectionner un pays pour le détail",
        ["— Aucun —"] + pays_names,
        index=select_idx,
        key="country_select",
    )
    st.session_state["selected_iso3"] = (
        name_to_iso3.get(selected_name) if selected_name != "— Aucun —" else None
    )

    # ── Carte ──────────────────────────────────────────────────
    if show_clusters and len(pays_clustered) > 0:
        fig_map = px.choropleth(
            pays_clustered,
            locations="iso3",
            color="cluster_display",
            hover_name="nom_pays",
            hover_data={
                "co2_per_capita":    ":.0f",
                "pib_per_capita":    ":,.0f",
                "taux_urbanisation": ":.1f",
                "pct_animal":        ":.1f",
                "cluster_display":   False,
            },
            color_discrete_sequence=list(CLUSTER_COLORS.values()),
            title=f"Profils pays — KMeans k=5 ({annee_sel})",
            labels={"cluster_display": "Cluster"},
        )
    else:
        fig_map = px.choropleth(
            pays_display.dropna(subset=[metric_col]),
            locations="iso3",
            color=metric_col,
            hover_name="nom_pays",
            hover_data={
                "co2_total":         ":,.0f",
                "co2_per_capita":    ":.0f",
                "pib_per_capita":    ":,.0f",
                "taux_urbanisation": ":.1f",
                "pct_animal":        ":.1f",
            },
            color_continuous_scale="YlOrRd",
            title=f"{metric_sel} — {annee_sel}",
            labels={metric_col: metric_sel},
        )

    # Surligner le pays sélectionné
    if st.session_state["selected_iso3"]:
        fig_map.add_trace(go.Choropleth(
            locations=[st.session_state["selected_iso3"]],
            z=[1],
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
            showscale=False,
            marker_line_color="white",
            marker_line_width=3,
            hoverinfo="skip",
        ))

    fig_map.update_layout(geo=dict(showframe=False), height=500, margin=dict(t=40, b=0))

    map_event = st.plotly_chart(fig_map, use_container_width=True, on_select="rerun", key="map_chart")

    # Sync clic carte → selectbox
    if (
        map_event
        and hasattr(map_event, "selection")
        and map_event.selection.points
    ):
        clicked_loc = map_event.selection.points[0].get("location")
        if clicked_loc and clicked_loc != st.session_state.get("selected_iso3"):
            st.session_state["selected_iso3"] = clicked_loc
            st.rerun()

    # ── Panneau détail pays ────────────────────────────────────
    if st.session_state["selected_iso3"]:
        iso3 = st.session_state["selected_iso3"]
        row = pays_agg[pays_agg["iso3"] == iso3]

        if row.empty:
            st.info("Données non disponibles pour ce pays et cette année.")
        else:
            row = row.iloc[0]
            st.markdown("---")
            st.subheader(f"📍 {row['nom_pays']}")

            # KPIs
            k1, k2, k3, k4, k5 = st.columns(5)
            co2_fmt = (
                f"{row['co2_total']/1e9:.2f} Gt"
                if row["co2_total"] > 1e9
                else f"{row['co2_total']/1e6:.1f} Mt"
            )
            k1.metric("CO₂ total", co2_fmt)
            k2.metric(
                "CO₂ / hab.",
                f"{row['co2_per_capita']:.0f} kg" if pd.notna(row["co2_per_capita"]) else "N/A",
            )
            k3.metric(
                "PIB / hab.",
                f"${row['pib_per_capita']:,.0f}" if pd.notna(row["pib_per_capita"]) else "N/A",
            )
            k4.metric(
                "Urbanisation",
                f"{row['taux_urbanisation']:.1f}%" if pd.notna(row["taux_urbanisation"]) else "N/A",
            )
            k5.metric("Part animale", f"{row['pct_animal']:.1f}%")

            # Cluster
            if iso3 in pays_clustered["iso3"].values:
                clust_row = pays_clustered[pays_clustered["iso3"] == iso3].iloc[0]
                c_id = int(clust_row["cluster"])
                st.markdown(
                    f"<span style='color:{CLUSTER_COLORS[c_id]}'>●</span> "
                    f"**Cluster {c_id} — {CLUSTER_LABELS[c_id]}** : {CLUSTER_DESCRIPTIONS[c_id]}",
                    unsafe_allow_html=True,
                )

            # Évolution + Distributions
            col_evol, col_dist = st.columns([1, 1])

            with col_evol:
                st.subheader("Évolution CO₂")
                evol_df = query_evol_pays(engine, iso3)
                if not evol_df.empty:
                    evol_df["co2_per_capita"] = (
                        evol_df["co2_total"] / evol_df["population"].replace(0, np.nan)
                    )
                    metric_evol = st.radio(
                        "Afficher",
                        ["CO₂ / hab.", "CO₂ total"],
                        horizontal=True,
                        key="evol_metric",
                    )
                    y_col = "co2_per_capita" if metric_evol == "CO₂ / hab." else "co2_total"
                    y_label = "kg CO₂/hab." if metric_evol == "CO₂ / hab." else "kg CO₂"
                    fig_evol = px.line(
                        evol_df, x="annee", y=y_col,
                        markers=True,
                        labels={"annee": "Année", y_col: y_label},
                    )
                    fig_evol.update_layout(height=320, margin=dict(t=10, b=30))
                    st.plotly_chart(fig_evol, use_container_width=True)

            with col_dist:
                st.subheader("Position dans la distribution mondiale")
                dist_vars = {
                    "CO₂/hab.":     ("co2_per_capita",    "kg"),
                    "PIB/hab.":     ("pib_per_capita",    "$"),
                    "Urbanisation": ("taux_urbanisation", "%"),
                    "Part animale": ("pct_animal",        "%"),
                }
                fig_box = make_subplots(rows=2, cols=2, subplot_titles=list(dist_vars.keys()))
                positions = [(1, 1), (1, 2), (2, 1), (2, 2)]
                first_legend = True
                for (label, (col_var, unit)), (r, c) in zip(dist_vars.items(), positions):
                    vals = pays_agg[col_var].dropna()
                    country_val = row[col_var] if pd.notna(row[col_var]) else None
                    fig_box.add_trace(go.Box(
                        y=vals, name=label,
                        marker_color="lightsteelblue",
                        showlegend=False,
                        boxpoints=False,
                    ), row=r, col=c)
                    if country_val is not None:
                        fig_box.add_trace(go.Scatter(
                            y=[country_val],
                            mode="markers",
                            marker=dict(color="crimson", size=10, symbol="diamond"),
                            name=row["nom_pays"],
                            showlegend=first_legend,
                        ), row=r, col=c)
                        first_legend = False
                fig_box.update_layout(height=380, margin=dict(t=40, b=10))
                st.plotly_chart(fig_box, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# PAGE 2 — Simulateur Menu
# ══════════════════════════════════════════════════════════════
elif page == "🍽️ Simulateur Menu":
    st.title("🍽️ Simulateur d'impact environnemental")
    st.markdown(
        "Indiquez la fréquence à laquelle vous consommez chaque aliment "
        "et découvrez votre empreinte carbone alimentaire hebdomadaire."
    )

    # ── Référence de comparaison ───────────────────────────────
    st.subheader("Référence de comparaison")
    ref_type = st.radio(
        "Comparer avec",
        ["🌍 Monde entier", "🌐 Région", "🏳️ Pays"],
        horizontal=True,
    )
    ref_label = "le monde entier"
    baseline_co2_daily = None

    if connected:
        if ref_type == "🌐 Région":
            region_ref = st.selectbox("Région", REGIONS, key="region_ref")
            ref_label = region_ref
            df_ref = query_baseline_region(engine, region_ref)
        elif ref_type == "🏳️ Pays":
            pays_names_all = sorted(pays_df["nom_pays"].tolist()) if pays_df is not None else []
            pays_ref_name = st.selectbox("Pays", pays_names_all, key="pays_ref")
            ref_label = pays_ref_name
            iso3_ref = (
                pays_df[pays_df["nom_pays"] == pays_ref_name]["code_iso3"].values[0]
                if pays_df is not None and len(pays_df[pays_df["nom_pays"] == pays_ref_name]) > 0
                else None
            )
            df_ref = query_baseline_pays(engine, iso3_ref) if iso3_ref else None
        else:
            df_ref = query_baseline_monde(engine)

        if df_ref is not None and not df_ref.empty:
            co2_ref_total = df_ref["co2_total"].iloc[0]
            pop_ref = df_ref["population"].iloc[0]
            if pop_ref and pop_ref > 0:
                baseline_co2_daily = co2_ref_total / pop_ref / 365
    else:
        st.info("Base de données non disponible — comparaison pays/région désactivée.")

    st.markdown("---")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Mes habitudes alimentaires")

        selected_foods = st.multiselect(
            "Choisissez vos aliments",
            options=list(CO2_FACTORS.keys()),
            default=["Boeuf", "Riz", "Légumes"],
        )

        portion_size = st.radio(
            "Taille des portions",
            list(PORTION_MULT.keys()),
            index=1,
            horizontal=True,
        )
        mult = PORTION_MULT[portion_size]

        frequencies = {}
        if selected_foods:
            st.markdown("**Fréquence de consommation**")
            for food in selected_foods:
                portion_g = PORTION_STANDARD[food] * mult
                frequencies[food] = st.select_slider(
                    f"{food} *(portion ~{portion_g:.0f} g)*",
                    options=FREQ_OPTIONS,
                    value="1×/semaine",
                    key=f"freq_{food}",
                )

        if selected_foods:
            st.markdown("---")
            col_btn1, col_btn2 = st.columns(2)
            if col_btn1.button("💾 Sauvegarder comme référence"):
                st.session_state["ref_menu"] = {
                    "frequencies": dict(frequencies),
                    "portion_size": portion_size,
                }
                st.success("Référence sauvegardée !")
            if "ref_menu" in st.session_state:
                if col_btn2.button("🗑️ Effacer la référence"):
                    del st.session_state["ref_menu"]

    with col2:
        st.subheader("Empreinte carbone")

        if selected_foods and any(FREQ_TO_DAILY[frequencies[f]] > 0 for f in selected_foods if f in frequencies):
            results = []
            total_co2_daily = 0.0
            for food in selected_foods:
                freq_daily = FREQ_TO_DAILY[frequencies[food]]
                portion_kg = PORTION_STANDARD[food] * mult / 1000
                co2_daily = CO2_FACTORS[food] * portion_kg * freq_daily
                total_co2_daily += co2_daily
                results.append({
                    "Aliment":          food,
                    "Fréquence":        frequencies[food],
                    "Portion (g)":      round(PORTION_STANDARD[food] * mult),
                    "CO₂/sem. (kg)":    round(co2_daily * 7, 4),
                })

            df_result = pd.DataFrame(results)
            total_co2_weekly = total_co2_daily * 7

            # KPIs
            k1, k2, k3 = st.columns(3)
            k1.metric("CO₂ / semaine", f"{total_co2_weekly:.2f} kg")
            k2.metric("CO₂ / jour",    f"{total_co2_daily:.3f} kg")
            k3.metric("CO₂ / an",      f"{total_co2_daily * 365:.0f} kg")

            # Bar chart (par semaine)
            fig_bar = px.bar(
                df_result, x="Aliment", y="CO₂/sem. (kg)",
                color="Aliment",
                title="Empreinte CO₂ hebdomadaire par aliment",
                text_auto=".3f",
            )
            fig_bar.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig_bar, use_container_width=True)

            # Part animale
            animal_foods = [
                f for f in selected_foods
                if FOOD_CATEGORY[f] in ("Meat", "Fish & Seafood", "Dairy", "Eggs")
            ]
            co2_animal_daily = sum(
                CO2_FACTORS[f] * PORTION_STANDARD[f] * mult / 1000 * FREQ_TO_DAILY[frequencies[f]]
                for f in animal_foods
            )
            if total_co2_daily > 0:
                pct_animal = co2_animal_daily / total_co2_daily * 100
                st.progress(int(pct_animal), text=f"Part animale : {pct_animal:.0f}% du CO₂ total")

            # Comparaison vs pays/région de référence
            if baseline_co2_daily is not None and baseline_co2_daily > 0:
                pct_of_ref = total_co2_daily / baseline_co2_daily * 100
                st.markdown("---")
                st.markdown(
                    f"**Comparaison :** votre alimentation représente **{pct_of_ref:.0f}%** "
                    f"de la consommation CO₂ journalière moyenne par habitant — *{ref_label}*  \n"
                    f"*(baseline : {baseline_co2_daily:.3f} kg CO₂/pers./jour)*"
                )

            # Delta vs menu de référence sauvegardé
            if "ref_menu" in st.session_state:
                ref_data = st.session_state["ref_menu"]
                ref_freqs = ref_data["frequencies"]
                ref_mult = PORTION_MULT[ref_data["portion_size"]]

                co2_ref_daily = sum(
                    CO2_FACTORS[f] * PORTION_STANDARD[f] * ref_mult / 1000 * FREQ_TO_DAILY[ref_freqs[f]]
                    for f in ref_freqs
                    if FREQ_TO_DAILY[ref_freqs[f]] > 0
                )
                delta_daily = total_co2_daily - co2_ref_daily
                delta_pct = (delta_daily / co2_ref_daily * 100) if co2_ref_daily > 0 else 0

                st.markdown("---")
                st.subheader("Variation vs habitudes de référence")
                d1, d2 = st.columns(2)
                d1.metric(
                    "CO₂/jour actuel",
                    f"{total_co2_daily:.3f} kg",
                    delta=f"{delta_pct:+.1f}%",
                    delta_color="inverse",
                )
                d2.metric("CO₂/jour référence", f"{co2_ref_daily:.3f} kg")

                # Before/after par aliment (en hebdomadaire)
                all_foods = sorted(set(list(frequencies.keys()) + list(ref_freqs.keys())))
                before_after = []
                for food in all_foods:
                    co2_avant = (
                        CO2_FACTORS.get(food, 0)
                        * PORTION_STANDARD.get(food, 100) * ref_mult / 1000
                        * FREQ_TO_DAILY.get(ref_freqs.get(food, "Jamais"), 0)
                        * 7
                    )
                    co2_apres = (
                        CO2_FACTORS.get(food, 0)
                        * PORTION_STANDARD.get(food, 100) * mult / 1000
                        * FREQ_TO_DAILY.get(frequencies.get(food, "Jamais"), 0)
                        * 7
                    )
                    if co2_avant > 0 or co2_apres > 0:
                        before_after.append({"Aliment": food, "CO₂/sem. (kg)": co2_avant, "Menu": "Référence"})
                        before_after.append({"Aliment": food, "CO₂/sem. (kg)": co2_apres, "Menu": "Actuel"})

                if before_after:
                    fig_ba = px.bar(
                        pd.DataFrame(before_after),
                        x="Aliment", y="CO₂/sem. (kg)", color="Menu",
                        barmode="group",
                        color_discrete_map={"Référence": "#95a5a6", "Actuel": "#3498db"},
                        title="Référence vs Habitudes actuelles (kg CO₂/semaine)",
                    )
                    fig_ba.update_layout(height=280)
                    st.plotly_chart(fig_ba, use_container_width=True)

        else:
            st.info("Sélectionnez au moins un aliment avec une fréquence de consommation.")

    # Référentiel CO₂
    with st.expander("📊 Référentiel CO₂ par aliment (kg CO₂-eq / kg produit)"):
        ref_df = pd.DataFrame([
            {"Aliment": k, "kg CO₂-eq / kg": v, "Catégorie": FOOD_CATEGORY[k]}
            for k, v in CO2_FACTORS.items()
        ]).sort_values("kg CO₂-eq / kg", ascending=False)
        fig_ref = px.bar(
            ref_df, x="Aliment", y="kg CO₂-eq / kg", color="Catégorie",
            title="Intensité carbone des aliments",
        )
        fig_ref.update_layout(height=400)
        st.plotly_chart(fig_ref, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# PAGE 3 — Prédiction Scénarios
# ══════════════════════════════════════════════════════════════
elif page == "📈 Prédiction Scénarios":
    st.title("📈 Prédiction & Scénarios")
    st.markdown(
        "Sélectionnez un pays et une catégorie alimentaire, puis simulez l'impact "
        "d'une variation de production sur l'empreinte CO₂ — modèle RandomForest (R²=0.930)."
    )

    if not connected:
        st.error("Cette page nécessite la connexion à la base de données PostgreSQL.")
        st.stop()

    # ── Sélection pays / année / catégorie ─────────────────────
    col_s1, col_s2 = st.columns([1, 1])

    with col_s1:
        st.subheader("Scénario")

        pays_names_sc = sorted(pays_df["nom_pays"].tolist()) if pays_df is not None else []
        pays_sc_name = st.selectbox("Pays", pays_names_sc, key="sc_pays")
        iso3_sc = (
            pays_df[pays_df["nom_pays"] == pays_sc_name]["code_iso3"].values[0]
            if pays_df is not None else None
        )

        annees_sc = sorted(annees_df["annee"].tolist())
        annee_sc = st.selectbox("Année de référence", annees_sc, index=len(annees_sc) - 1, key="sc_annee")

        cats = [
            "Meat", "Cereals & Grains", "Dairy", "Vegetables", "Fruits",
            "Fish & Seafood", "Roots & Tubers", "Pulses", "Eggs",
            "Sugar & Sweeteners", "Vegetable Oils",
        ]
        categorie = st.selectbox("Catégorie alimentaire", cats)
        variation = st.slider("Variation de production (%)", -80, 200, 0, step=5)

    # ── Chargement données pays ─────────────────────────────────
    pays_row = None
    quantite_base = None
    if iso3_sc:
        pays_agg_sc = enrich_pays_df(query_pays_annee(engine, annee_sc))
        match = pays_agg_sc[pays_agg_sc["iso3"] == iso3_sc]
        if not match.empty:
            pays_row = match.iloc[0]

        prod_df = query_production_par_categorie(engine, iso3_sc, annee_sc)
        prod_cat = prod_df[prod_df["categorie"] == categorie]
        quantite_base = float(prod_cat["quantite_1000t"].iloc[0]) if not prod_cat.empty else None

    with col_s1:
        if quantite_base is not None:
            st.info(
                f"Production réelle de **{categorie}** en {annee_sc} : "
                f"**{quantite_base:,.0f} kt**"
            )
        else:
            st.warning(f"Aucune production de **{categorie}** enregistrée pour {pays_sc_name} en {annee_sc}.")

    with col_s2:
        st.subheader("Résultats de prédiction")

        if pays_row is None or quantite_base is None:
            st.info("Sélectionnez un pays avec des données disponibles pour cette année et catégorie.")
        else:
            pib      = pays_row["pib_per_capita"]   if pd.notna(pays_row["pib_per_capita"])   else 5000.0
            urba     = pays_row["taux_urbanisation"] if pd.notna(pays_row["taux_urbanisation"]) else 50.0
            pop      = pays_row["population"]        if pd.notna(pays_row["population"])        else 50e6
            surf     = pays_row["surface_agricole"]  if pd.notna(pays_row["surface_agricole"])  else 40.0
            region   = pays_row["region"]

            def make_input(qty_val):
                return pd.DataFrame([{
                    "quantite_1000t":    qty_val,
                    "pib_per_capita":    pib,
                    "taux_urbanisation": urba,
                    "population":        pop,
                    "surface_agricole":  surf,
                    "categorie":         categorie,
                    "region":            region,
                }])

            qty_modif = quantite_base * (1 + variation / 100)

            co2_base_kg  = np.expm1(model_impact.predict(make_input(quantite_base))[0])
            co2_modif_kg = np.expm1(model_impact.predict(make_input(qty_modif))[0])
            delta_kg     = co2_modif_kg - co2_base_kg
            delta_pct    = (delta_kg / co2_base_kg * 100) if co2_base_kg > 0 else 0

            m1, m2, m3 = st.columns(3)
            m1.metric("CO₂ actuel",       f"{co2_base_kg/1e6:.2f} Mt")
            m2.metric("CO₂ scénario",     f"{co2_modif_kg/1e6:.2f} Mt", delta=f"{delta_pct:+.1f}%")
            m3.metric("Variation absolue", f"{delta_kg/1e6:+.2f} Mt")

            fig_comp = go.Figure()
            fig_comp.add_bar(
                x=["Actuel", "Scénario"],
                y=[co2_base_kg / 1e6, co2_modif_kg / 1e6],
                marker_color=["#3498db", "#e74c3c" if delta_kg > 0 else "#2ecc71"],
                text=[f"{co2_base_kg/1e6:.2f} Mt", f"{co2_modif_kg/1e6:.2f} Mt"],
                textposition="outside",
            )
            fig_comp.update_layout(
                title=f"{pays_sc_name} — {categorie} : impact de {variation:+}%",
                yaxis_title="CO₂ (Mt)",
                height=320,
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            # Courbe de sensibilité
            st.subheader("Sensibilité CO₂ selon la variation de production")
            variations = list(range(-80, 201, 10))
            co2_vals = [
                np.expm1(model_impact.predict(make_input(quantite_base * (1 + v / 100)))[0]) / 1e6
                for v in variations
            ]
            df_sens = pd.DataFrame({"Variation (%)": variations, "CO₂ (Mt)": co2_vals})
            fig_sens = px.line(
                df_sens, x="Variation (%)", y="CO₂ (Mt)",
                markers=True,
                title=f"Sensibilité — {categorie} · {pays_sc_name}",
            )
            fig_sens.add_vline(x=0, line_dash="dash", line_color="gray")
            fig_sens.add_vline(x=variation, line_color="red", annotation_text=f"{variation:+}%")
            st.plotly_chart(fig_sens, use_container_width=True)

    # ── Comparaison par catégorie (productions réelles du pays) ─
    if pays_row is not None and not prod_df.empty:
        st.markdown("---")
        st.subheader(f"Empreinte CO₂ par catégorie — {pays_sc_name} ({annee_sc})")
        co2_by_cat = []
        for _, cat_row in prod_df.iterrows():
            x = pd.DataFrame([{
                "quantite_1000t":    cat_row["quantite_1000t"],
                "pib_per_capita":    pays_row["pib_per_capita"]   if pd.notna(pays_row["pib_per_capita"])   else 5000.0,
                "taux_urbanisation": pays_row["taux_urbanisation"] if pd.notna(pays_row["taux_urbanisation"]) else 50.0,
                "population":        pays_row["population"]        if pd.notna(pays_row["population"])        else 50e6,
                "surface_agricole":  pays_row["surface_agricole"]  if pd.notna(pays_row["surface_agricole"])  else 40.0,
                "categorie":         cat_row["categorie"],
                "region":            pays_row["region"],
            }])
            co2_by_cat.append({
                "Catégorie":     cat_row["categorie"],
                "CO₂ (Mt)":     np.expm1(model_impact.predict(x)[0]) / 1e6,
                "Production (kt)": cat_row["quantite_1000t"],
            })

        df_cat = pd.DataFrame(co2_by_cat).sort_values("CO₂ (Mt)", ascending=False)
        fig_cat = px.bar(
            df_cat, x="Catégorie", y="CO₂ (Mt)", color="Catégorie",
            hover_data={"Production (kt)": ":,.0f"},
            title=f"CO₂ prédit par catégorie — productions réelles de {pays_sc_name}",
        )
        fig_cat.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_cat, use_container_width=True)
