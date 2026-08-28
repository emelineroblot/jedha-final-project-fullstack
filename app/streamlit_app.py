"""
Score d'Impact Environnemental de l'Assiette Mondiale
Application Streamlit — Jedha Bloc 6
"""

import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from plotly.subplots import make_subplots
from sqlalchemy import create_engine, text

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

# ⚠️ Les INDICES de cluster produits par KMeans sont arbitraires et changent à
# chaque réentraînement. Les libellés sont donc lus depuis l'artefact
# (`bundle['labels']`, calculé par scripts/train_model.py à partir des profils
# moyens) ; ce dictionnaire n'est qu'un repli si l'artefact est au format hérité.
# Cf. docs/audit.md §2.2.
CLUSTER_LABELS_FALLBACK = {
    0: "Profil 0", 1: "Profil 1", 2: "Profil 2", 3: "Profil 3", 4: "Profil 4",
}

# Couleurs et descriptions sont indexées par LIBELLÉ, pas par numéro de cluster :
# c'est le libellé qui porte le sens, et lui seul est stable.
CLUSTER_COLORS = {
    "Pays riches":            "#2ecc71",
    "Émergents urbains":      "#f39c12",
    "Producteurs intensifs":  "#e74c3c",
    "Développement agricole": "#3498db",
    "Faible revenu":          "#9b59b6",
}
CLUSTER_DESCRIPTIONS = {
    "Pays riches":            "PIB/hab. le plus élevé, très urbanisés, part animale la plus forte.",
    "Émergents urbains":      "PIB intermédiaire, très urbanisés, peu de surface agricole → importateurs nets.",
    "Producteurs intensifs":  "Surface agricole la plus étendue, CO₂/hab. élevé à PIB moyen.",
    "Développement agricole": "PIB intermédiaire, agriculture étendue, part animale modérée.",
    "Faible revenu":          "CO₂/hab. le plus bas, peu urbanisés, faible part animale.",
}
COULEUR_DEFAUT = "#7f8c8d"

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

# ⚠️ Ces libellés DOIVENT correspondre exactement aux catégories produites par
# `scripts/_mappings.py::categorize()` et stockées dans dim_produits.categorie.
# Le modèle a été entraîné sur ces valeurs : un libellé inconnu est silencieusement
# encodé en vecteur nul par le OneHotEncoder (handle_unknown='ignore') et dégrade
# la prédiction sans lever d'erreur. Cf. docs/audit.md §2.8.
# Le test tests/test_app_constants.py verrouille cette correspondance.
FOOD_CATEGORY = {
    "Boeuf":                    "Meat",
    "Agneau":                   "Meat",
    "Porc":                     "Meat",
    "Volaille":                 "Meat",
    "Poisson (élevage)":        "Fish & Seafood",
    "Oeufs":                    "Eggs",
    "Lait / Produits laitiers": "Dairy",
    "Riz":                      "Cereals",
    "Blé / Céréales":           "Cereals",
    "Légumineuses":             "Legumes",
    "Légumes":                  "Vegetables",
    "Fruits":                   "Fruits",
    "Sucre":                    "Sugar",
    "Huiles végétales":         "Oils & Fats",
    "Racines & Tubercules":     "Roots & Tubers",
}

# Catégories animales — utilisées pour la part animale du CO₂ (app + SQL).
CATEGORIES_ANIMALES = ("Meat", "Dairy", "Eggs", "Fish & Seafood")


# ──────────────────────────────────────────────────────────────
# DB / Modèles
# ──────────────────────────────────────────────────────────────
@st.cache_resource
def get_engine():
    """Moteur SQLAlchemy dérivé de l'environnement — jamais de valeur en dur.

    Le mot de passe passe par `connect_args` et non par l'URL : il n'a donc pas
    à être encodé, et n'apparaît dans aucune trace d'erreur SQLAlchemy.
    `sslmode` vaut `require` en production (RDS refuse le clair) et `prefer` en
    local, où le conteneur Docker n'expose pas de certificat.
    """
    return create_engine(
        "postgresql+psycopg2://",
        connect_args={
            "host":     os.getenv("POSTGRES_HOST", "localhost"),
            "port":     int(os.getenv("POSTGRES_PORT", "5432")),
            "dbname":   os.getenv("POSTGRES_DB", "food_impact"),
            "user":     os.getenv("POSTGRES_USER", "food_user"),
            "password": os.getenv("POSTGRES_PASSWORD", "food_pass"),
            "sslmode":  os.getenv("POSTGRES_SSLMODE", "prefer"),
            "connect_timeout": 15,
        },
        pool_pre_ping=True,   # une connexion coupée par RDS est reconnectée
        echo=False,
    )


@st.cache_resource
def load_models():
    """Charge les modèles. Ne lève jamais : l'app doit rester utilisable sans eux.

    `model_clustering.pkl` est attendu au format {'scaler': ..., 'kmeans': ...}.
    L'ancien format (KMeans nu) est encore accepté mais signalé : sans le scaler
    d'entraînement, les clusters prédits ne sont pas comparables d'une année à
    l'autre (cf. docs/audit.md §2.2).
    """
    model_dir = BASE_DIR / "models"
    impact, clustering = None, None

    try:
        impact = joblib.load(model_dir / "model_impact.pkl")
    except Exception as exc:  # noqa: BLE001 — dégradation volontaire
        st.session_state["_err_model_impact"] = str(exc)

    try:
        raw = joblib.load(model_dir / "model_clustering.pkl")
        if isinstance(raw, dict) and "kmeans" in raw and "scaler" in raw:
            clustering = raw
        else:
            clustering = {"kmeans": raw, "scaler": None}
    except Exception as exc:  # noqa: BLE001
        st.session_state["_err_model_clustering"] = str(exc)

    return impact, clustering


def fmt_co2(kg) -> str:
    """Formate une masse de CO₂ exprimée en KILOGRAMMES.

    1 t = 1e3 kg · 1 kt = 1e6 kg · 1 Mt = 1e9 kg · 1 Gt = 1e12 kg
    """
    if kg is None or pd.isna(kg):
        return "N/A"
    tonnes = kg / 1e3
    if abs(tonnes) >= 1e9:
        return f"{tonnes / 1e9:.2f} Gt"
    if abs(tonnes) >= 1e6:
        return f"{tonnes / 1e6:.2f} Mt"
    if abs(tonnes) >= 1e3:
        return f"{tonnes / 1e3:.2f} kt"
    return f"{tonnes:,.0f} t"


def kg_to_mt(kg):
    """kg → mégatonnes (1 Mt = 1e9 kg)."""
    return kg / 1e9


@st.cache_data(ttl=3600)
def query(_engine, sql: str, params: dict | None = None) -> pd.DataFrame:
    """Exécute une requête en paramètres liés (jamais de f-string dans le SQL)."""
    with _engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


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
    """Agrégat par pays pour une année.

    ⚠️ Grain : `fait_impact_pays_annee` est au grain (pays, année, produit).
    La jointure sur dim_socio_economique (grain pays × année) duplique donc les
    variables socio-éco une fois par produit → on utilise AVG (constante par
    groupe), JAMAIS SUM. Cf. docs/audit.md §2.4.
    """
    return query(engine, """
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
        WHERE t.annee = :annee
        GROUP BY p.nom_pays, p.code_iso3, p.region
    """, {"annee": int(annee)})


def enrich_pays_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["co2_per_capita"] = df["co2_total"] / df["population"].replace(0, np.nan)
    df["pct_animal"] = df["co2_animal"] / (df["co2_total"] + 1e-10) * 100
    return df


def query_evol_pays(engine, iso3: str) -> pd.DataFrame:
    return query(engine, """
        SELECT
            t.annee,
            SUM(f.co2_total_kg) AS co2_total,
            AVG(s.population)   AS population
        FROM fait_impact_pays_annee f
        JOIN dim_pays  p ON f.pays_id  = p.pays_id
        JOIN dim_temps t ON f.annee_id = t.annee_id
        LEFT JOIN dim_socio_economique s
               ON f.pays_id = s.pays_id AND f.annee_id = s.annee_id
        WHERE p.code_iso3 = :iso3
        GROUP BY t.annee
        ORDER BY t.annee
    """, {"iso3": iso3})


# ── Baselines de comparaison ───────────────────────────────────
# Règle commune aux trois requêtes ci-dessous (cf. docs/audit.md §2.4 et §2.5) :
#   1. L'année de référence est le MAX des années présentes dans les FAITS,
#      jamais le MAX de dim_temps (qui va jusqu'à 2023 même sans données).
#   2. La population est agrégée depuis dim_socio_economique DIRECTEMENT
#      (grain pays × année). La sommer après jointure sur la table de faits
#      la dupliquerait une fois par produit (jusqu'à ×121).
#   3. Le périmètre pays de la population est aligné sur celui du CO₂ via
#      EXISTS, pour ne pas diviser un CO₂ partiel par une population totale.

def query_baseline_pays(engine, iso3: str) -> pd.DataFrame:
    return query(engine, """
        WITH ref AS (
            SELECT MAX(t.annee) AS annee
            FROM fait_impact_pays_annee f
            JOIN dim_temps t ON f.annee_id = t.annee_id
            JOIN dim_pays  p ON f.pays_id  = p.pays_id
            WHERE p.code_iso3 = :iso3
        )
        SELECT
            (SELECT SUM(f.co2_total_kg)
             FROM fait_impact_pays_annee f
             JOIN dim_temps t ON f.annee_id = t.annee_id
             JOIN dim_pays  p ON f.pays_id  = p.pays_id
             WHERE p.code_iso3 = :iso3
               AND t.annee = (SELECT annee FROM ref))          AS co2_total,
            (SELECT SUM(s.population)
             FROM dim_socio_economique s
             JOIN dim_temps t ON s.annee_id = t.annee_id
             JOIN dim_pays  p ON s.pays_id  = p.pays_id
             WHERE p.code_iso3 = :iso3
               AND t.annee = (SELECT annee FROM ref))          AS population,
            (SELECT annee FROM ref)                            AS annee_ref
    """, {"iso3": iso3})


def query_baseline_region(engine, region: str) -> pd.DataFrame:
    return query(engine, """
        WITH ref AS (
            SELECT MAX(t.annee) AS annee
            FROM fait_impact_pays_annee f
            JOIN dim_temps t ON f.annee_id = t.annee_id
            JOIN dim_pays  p ON f.pays_id  = p.pays_id
            WHERE p.region = :region
        )
        SELECT
            (SELECT SUM(f.co2_total_kg)
             FROM fait_impact_pays_annee f
             JOIN dim_temps t ON f.annee_id = t.annee_id
             JOIN dim_pays  p ON f.pays_id  = p.pays_id
             WHERE p.region = :region
               AND t.annee = (SELECT annee FROM ref))          AS co2_total,
            (SELECT SUM(s.population)
             FROM dim_socio_economique s
             JOIN dim_temps t ON s.annee_id = t.annee_id
             JOIN dim_pays  p ON s.pays_id  = p.pays_id
             WHERE p.region = :region
               AND t.annee = (SELECT annee FROM ref)
               AND EXISTS (SELECT 1 FROM fait_impact_pays_annee f2
                           WHERE f2.pays_id  = s.pays_id
                             AND f2.annee_id = s.annee_id))    AS population,
            (SELECT annee FROM ref)                            AS annee_ref
    """, {"region": region})


def query_baseline_monde(engine) -> pd.DataFrame:
    return query(engine, """
        WITH ref AS (
            SELECT MAX(t.annee) AS annee
            FROM fait_impact_pays_annee f
            JOIN dim_temps t ON f.annee_id = t.annee_id
        )
        SELECT
            (SELECT SUM(f.co2_total_kg)
             FROM fait_impact_pays_annee f
             JOIN dim_temps t ON f.annee_id = t.annee_id
             WHERE t.annee = (SELECT annee FROM ref))          AS co2_total,
            (SELECT SUM(s.population)
             FROM dim_socio_economique s
             JOIN dim_temps t ON s.annee_id = t.annee_id
             WHERE t.annee = (SELECT annee FROM ref)
               AND EXISTS (SELECT 1 FROM fait_impact_pays_annee f2
                           WHERE f2.pays_id  = s.pays_id
                             AND f2.annee_id = s.annee_id))    AS population,
            (SELECT annee FROM ref)                            AS annee_ref
    """)


def query_production_par_categorie(engine, iso3: str, annee: int) -> pd.DataFrame:
    return query(engine, """
        SELECT
            pr.categorie,
            SUM(f.quantite_1000t) AS quantite_1000t
        FROM fait_impact_pays_annee f
        JOIN dim_pays     p  ON f.pays_id    = p.pays_id
        JOIN dim_temps    t  ON f.annee_id   = t.annee_id
        JOIN dim_produits pr ON f.produit_id = pr.produit_id
        WHERE p.code_iso3 = :iso3 AND t.annee = :annee
        GROUP BY pr.categorie
    """, {"iso3": iso3, "annee": int(annee)})


def query_production_par_produit(engine, iso3: str, annee: int) -> pd.DataFrame:
    """Production détaillée **par produit** — le grain d'entraînement du modèle.

    C'est cette requête, et non l'agrégat par catégorie, qui doit alimenter les
    prédictions : le modèle a appris sur des quantités de produits individuels,
    et un RandomForest interrogé au-delà de sa plage d'entraînement ne renvoie
    pas une extrapolation mais une constante. Cf. docs/audit.md §3.2.
    """
    return query(engine, """
        SELECT
            pr.produit_id,
            pr.nom_fao,
            pr.categorie,
            SUM(f.quantite_1000t) AS quantite_1000t,
            MAX(fi.co2_total_per_kg) AS co2_total_per_kg
        FROM fait_impact_pays_annee f
        JOIN dim_pays     p  ON f.pays_id    = p.pays_id
        JOIN dim_temps    t  ON f.annee_id   = t.annee_id
        JOIN dim_produits pr ON f.produit_id = pr.produit_id
        LEFT JOIN fait_impact fi ON fi.produit_id = pr.produit_id
        WHERE p.code_iso3 = :iso3
          AND t.annee = :annee
          AND f.quantite_1000t > 0
          AND f.co2_total_kg IS NOT NULL
        GROUP BY pr.produit_id, pr.nom_fao, pr.categorie
        ORDER BY quantite_1000t DESC
    """, {"iso3": iso3, "annee": int(annee)})


def co2_reference_kg(produits: pd.DataFrame, facteur: float = 1.0) -> float:
    """Empreinte **exacte**, recalculée depuis les facteurs d'émission du DWH.

    `co2_total_kg = quantite_1000t × 1e6 × co2_total_per_kg` — c'est la formule
    même qu'utilise l'ETL pour construire la cible. Cette valeur n'est donc pas
    une prédiction : c'est la référence à laquelle comparer le modèle. L'écart
    entre les deux mesure ce que le RandomForest perd en approximant une
    relation déterministe. Cf. docs/audit.md §4.1.
    """
    if produits.empty or "co2_total_per_kg" not in produits:
        return float("nan")
    q = produits["quantite_1000t"].to_numpy() * facteur * 1e6
    f = pd.to_numeric(produits["co2_total_per_kg"], errors="coerce").to_numpy()
    return float(np.nansum(q * f))


def predire_co2_par_produit(model, produits: pd.DataFrame, socio: dict,
                            facteur: float = 1.0) -> np.ndarray:
    """Prédit le CO₂ (kg) de chaque produit, en une seule passe vectorisée.

    `facteur` multiplie toutes les quantités — c'est le levier des scénarios.
    Le modèle prédit `log1p(co2)` : d'où l'`expm1` en sortie.
    """
    if produits.empty:
        return np.array([])
    X = pd.DataFrame({
        "quantite_1000t":    produits["quantite_1000t"].to_numpy() * facteur,
        "pib_per_capita":    socio["pib"],
        "taux_urbanisation": socio["urba"],
        "population":        socio["pop"],
        "surface_agricole":  socio["surf"],
        "categorie":         produits["categorie"].to_numpy(),
        "region":            socio["region"],
    })
    return np.expm1(model.predict(X))


@st.cache_data(ttl=3600)
def query_categories(_engine) -> list:
    """Catégories réellement présentes en base, triées par empreinte décroissante."""
    df = query(_engine, """
        SELECT pr.categorie, SUM(f.co2_total_kg) AS co2
        FROM fait_impact_pays_annee f
        JOIN dim_produits pr ON f.produit_id = pr.produit_id
        WHERE f.co2_total_kg IS NOT NULL
        GROUP BY pr.categorie
        ORDER BY co2 DESC NULLS LAST
    """)
    return df["categorie"].tolist()


@st.cache_data(ttl=3600)
def query_plage_quantite(_engine) -> tuple:
    """Plage de `quantite_1000t` réellement vue à l'entraînement (grain produit).

    Sert à borner le simulateur : un RandomForest n'extrapole pas au-delà de sa
    plage d'entraînement, il renvoie une constante. Cf. docs/audit.md §3.2.
    """
    df = query(_engine, """
        SELECT MIN(quantite_1000t) AS qmin, MAX(quantite_1000t) AS qmax
        FROM fait_impact_pays_annee
        WHERE quantite_1000t > 0 AND co2_total_kg IS NOT NULL
    """)
    if df.empty or pd.isna(df["qmax"].iloc[0]):
        return (0.0, float("inf"))
    return (float(df["qmin"].iloc[0]), float(df["qmax"].iloc[0]))


# ──────────────────────────────────────────────────────────────
# Clustering helper
# ──────────────────────────────────────────────────────────────
def apply_clustering(df: pd.DataFrame, bundle) -> pd.DataFrame:
    """Assigne chaque pays à son cluster avec le scaler D'ENTRAÎNEMENT.

    ⚠️ Ne JAMAIS appeler `fit` / `fit_transform` ici : les centroïdes du KMeans
    vivent dans l'espace normalisé par le scaler ajusté à l'entraînement, sur
    l'ensemble des paires pays × année. Réajuster un scaler sur le sous-ensemble
    affiché déplace l'espace et rend les clusters incohérents d'une année à
    l'autre. Cf. docs/audit.md §2.2.
    """
    df = df.dropna(subset=CLUSTER_FEATURES).copy()
    if bundle is None or bundle.get("kmeans") is None or len(df) < 5:
        return df

    scaler = bundle.get("scaler")
    if scaler is None:
        # Modèle au format hérité : pas de scaler → refus explicite plutôt
        # qu'un résultat faux silencieux.
        return df

    X_scaled = scaler.transform(df[CLUSTER_FEATURES])
    labels = bundle.get("labels") or CLUSTER_LABELS_FALLBACK
    # joblib peut restituer les clés en str selon le format de sérialisation.
    labels = {int(k): v for k, v in labels.items()}

    df["cluster"] = bundle["kmeans"].predict(X_scaled)
    df["cluster_label"] = df["cluster"].map(labels).fillna("Non classé")
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
        [
            "🗺️ Explorer les pays",
            "🍽️ Simulateur Menu",
            "📈 Prédiction Scénarios",
            "📐 Méthodologie & limites",
        ],
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

if model_impact is None:
    st.warning(
        "Modèle de régression indisponible — la page « Prédiction Scénarios » est "
        "désactivée. Régénérez-le avec `python scripts/train_model.py`."
    )
if model_clustering is None or model_clustering.get("scaler") is None:
    st.info(
        "Modèle de clustering absent ou au format hérité (sans scaler) — "
        "l'affichage par clusters est désactivé. "
        "Régénérez-le avec `python scripts/train_model.py`."
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
    clusters_ok = model_clustering is not None and model_clustering.get("scaler") is not None
    show_clusters = col_f4.toggle("Clusters", value=False, disabled=not clusters_ok)
    metric_col = METRIC_OPTIONS[metric_sel]

    # ── Données ────────────────────────────────────────────────
    pays_agg = enrich_pays_df(query_pays_annee(engine, annee_sel))
    pays_display = (
        pays_agg[pays_agg["region"] == region_sel].copy()
        if region_sel != "Toutes"
        else pays_agg.copy()
    )
    # Le clustering suit le filtre région (le scaler étant celui de
    # l'entraînement, restreindre l'affichage ne change pas les assignations).
    pays_clustered = apply_clustering(pays_display, model_clustering)

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
    if show_clusters and "cluster_display" in pays_clustered.columns and len(pays_clustered) > 0:
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
            # Couleur pilotée par le LIBELLÉ : un même profil garde sa couleur
            # même si son indice change au réentraînement.
            color_discrete_map={
                f"{cid} — {lab}": CLUSTER_COLORS.get(lab, COULEUR_DEFAUT)
                for cid, lab in pays_clustered[["cluster", "cluster_label"]]
                .drop_duplicates().itertuples(index=False)
            },
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
            k1.metric("CO₂ total", fmt_co2(row["co2_total"]))
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
            k5.metric(
                "Part animale",
                f"{row['pct_animal']:.1f}%" if pd.notna(row["pct_animal"]) else "N/A",
            )

            # Cluster
            if "cluster" in pays_clustered.columns and iso3 in pays_clustered["iso3"].values:
                clust_row = pays_clustered[pays_clustered["iso3"] == iso3].iloc[0]
                c_id = int(clust_row["cluster"])
                c_label = clust_row["cluster_label"]
                st.markdown(
                    f"<span style='color:{CLUSTER_COLORS.get(c_label, COULEUR_DEFAUT)}'>●</span> "
                    f"**Cluster {c_id} — {c_label}** : "
                    f"{CLUSTER_DESCRIPTIONS.get(c_label, 'Profil sans description.')}",
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
                for (label, (col_var, _unit)), (r, c) in zip(dist_vars.items(), positions, strict=False):
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
            baseline_annee = df_ref["annee_ref"].iloc[0] if "annee_ref" in df_ref else None
            if pd.notna(co2_ref_total) and pd.notna(pop_ref) and pop_ref > 0:
                baseline_co2_daily = co2_ref_total / pop_ref / 365
            else:
                st.warning(
                    f"Pas de données d'empreinte exploitables pour « {ref_label} » — "
                    "comparaison indisponible."
                )
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
                # st.progress exige un int dans [0, 100] : NaN ou dépassement lèvent.
                pct_animal_safe = int(np.clip(np.nan_to_num(pct_animal), 0, 100))
                st.progress(
                    pct_animal_safe,
                    text=f"Part animale : {pct_animal:.0f}% du CO₂ total",
                )

            # Comparaison vs pays/région de référence
            if baseline_co2_daily is not None and baseline_co2_daily > 0:
                pct_of_ref = total_co2_daily / baseline_co2_daily * 100
                st.markdown("---")
                annee_txt = f" — année {int(baseline_annee)}" if pd.notna(baseline_annee) else ""
                st.markdown(
                    f"**Comparaison :** votre alimentation représente **{pct_of_ref:.0f}%** "
                    f"de l'empreinte alimentaire journalière moyenne par habitant — "
                    f"*{ref_label}*{annee_txt}  \n"
                    f"*(référence : {baseline_co2_daily:.3f} kg CO₂/pers./jour)*"
                )
                st.caption(
                    "⚠️ **Lecture prudente.** Votre assiette est mesurée en *consommation "
                    "individuelle* ; la référence est calculée sur la *production "
                    "alimentaire nationale* rapportée à la population — elle inclut donc "
                    "l'alimentation animale, les exportations et les pertes. Les deux "
                    "grandeurs ne sont pas strictement équivalentes : ce ratio est un "
                    "ordre de grandeur, pas une mesure. Cf. onglet Méthodologie."
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
        "d'une variation de production sur l'empreinte CO₂."
    )
    st.caption(
        "La variation est appliquée à **chaque produit** de la catégorie, et les "
        "prédictions sont sommées. Le modèle ayant été entraîné au grain produit, "
        "l'interroger sur un total de catégorie le placerait hors de son domaine "
        "de validité — où un RandomForest ne renvoie plus qu'une constante."
    )

    if not connected:
        st.error("Cette page nécessite la connexion à la base de données PostgreSQL.")
        st.stop()
    if model_impact is None:
        st.error(
            "Modèle de régression introuvable (`models/model_impact.pkl`). "
            "Générez-le avec `python scripts/train_model.py`."
        )
        st.stop()

    q_min_train, q_max_train = query_plage_quantite(engine)

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

        # Les catégories sont lues en base : elles doivent correspondre à celles
        # vues à l'entraînement, et une liste codée en dur diverge silencieusement.
        cats = query_categories(engine)
        categorie = st.selectbox("Catégorie alimentaire", cats)
        variation = st.slider("Variation de production (%)", -80, 200, 0, step=5)

    # ── Chargement données pays ─────────────────────────────────
    pays_row = None
    quantite_base = None
    produits_df = pd.DataFrame()      # grain produit — alimente les prédictions
    produits_cat = pd.DataFrame()     # produits de la catégorie sélectionnée
    if iso3_sc:
        pays_agg_sc = enrich_pays_df(query_pays_annee(engine, annee_sc))
        match = pays_agg_sc[pays_agg_sc["iso3"] == iso3_sc]
        if not match.empty:
            pays_row = match.iloc[0]

        produits_df = query_production_par_produit(engine, iso3_sc, annee_sc)
        produits_cat = produits_df[produits_df["categorie"] == categorie]
        quantite_base = float(produits_cat["quantite_1000t"].sum()) if not produits_cat.empty else None

    with col_s1:
        if quantite_base is not None:
            st.info(
                f"Production réelle de **{categorie}** en {annee_sc} : "
                f"**{quantite_base:,.0f} kt** "
                f"répartis sur **{len(produits_cat)} produit(s)**"
            )
            with st.expander(f"Détail des {len(produits_cat)} produits"):
                st.dataframe(
                    produits_cat[["nom_fao", "quantite_1000t"]]
                    .rename(columns={"nom_fao": "Produit", "quantite_1000t": "Production (kt)"}),
                    use_container_width=True, hide_index=True,
                )
        else:
            st.warning(f"Aucune production de **{categorie}** enregistrée pour {pays_sc_name} en {annee_sc}.")

    with col_s2:
        st.subheader("Résultats de prédiction")

        if pays_row is None or quantite_base is None:
            st.info("Sélectionnez un pays avec des données disponibles pour cette année et catégorie.")
        else:
            socio = {
                "pib":    pays_row["pib_per_capita"]    if pd.notna(pays_row["pib_per_capita"])    else 5000.0,
                "urba":   pays_row["taux_urbanisation"] if pd.notna(pays_row["taux_urbanisation"]) else 50.0,
                "pop":    pays_row["population"]        if pd.notna(pays_row["population"])        else 50e6,
                "surf":   pays_row["surface_agricole"]  if pd.notna(pays_row["surface_agricole"])  else 40.0,
                "region": pays_row["region"],
            }

            # Le scénario s'applique à CHAQUE produit de la catégorie, et les
            # prédictions sont sommées. Le modèle reste ainsi dans son domaine
            # d'entraînement, au lieu de recevoir un total de catégorie qui en
            # sort de plusieurs ordres de grandeur. Cf. docs/audit.md §3.2.
            facteur = 1 + variation / 100
            co2_base_kg = float(predire_co2_par_produit(
                model_impact, produits_cat, socio).sum())
            co2_modif_kg = float(predire_co2_par_produit(
                model_impact, produits_cat, socio, facteur=facteur).sum())
            delta_kg = co2_modif_kg - co2_base_kg
            delta_pct = (delta_kg / co2_base_kg * 100) if co2_base_kg > 0 else 0

            # Contrôle d'extrapolation, désormais au bon grain : il ne se
            # déclenche plus que pour un produit réellement hors plage.
            q_max_simule = float((produits_cat["quantite_1000t"] * facteur).max())
            if q_max_simule > q_max_train:
                hors = produits_cat[produits_cat["quantite_1000t"] * facteur > q_max_train]
                st.warning(
                    f"⚠️ **Extrapolation sur {len(hors)} produit(s).** La quantité "
                    f"simulée atteint {q_max_simule:,.0f} kt, au-delà du maximum vu à "
                    f"l'entraînement ({q_max_train:,.0f} kt). Le modèle sature sur ces "
                    f"produits : à lire comme une tendance, pas comme une valeur."
                )

            m1, m2, m3 = st.columns(3)
            m1.metric("CO₂ actuel",       fmt_co2(co2_base_kg))
            m2.metric("CO₂ scénario",     fmt_co2(co2_modif_kg), delta=f"{delta_pct:+.1f}%")
            m3.metric("Variation absolue", ("+" if delta_kg >= 0 else "−") + fmt_co2(abs(delta_kg)))

            # ── Référence déterministe ─────────────────────────
            # L'empreinte est exactement calculable : quantité × facteur. On
            # l'affiche à côté de la prédiction pour rendre visible l'écart du
            # modèle plutôt que de le masquer.
            ref_base = co2_reference_kg(produits_cat)
            ref_modif = co2_reference_kg(produits_cat, facteur)
            if not np.isnan(ref_base) and ref_base > 0:
                ecart = (co2_base_kg - ref_base) / ref_base * 100
                st.markdown("**Contrôle — modèle contre calcul exact**")
                c1, c2, c3 = st.columns(3)
                c1.metric("Référence actuelle", fmt_co2(ref_base))
                c2.metric("Référence scénario", fmt_co2(ref_modif),
                          delta=f"{(ref_modif / ref_base - 1) * 100:+.1f}%")
                c3.metric("Écart du modèle", f"{ecart:+.1f} %",
                          help="Écart entre la prédiction du RandomForest et "
                               "l'empreinte recalculée depuis les facteurs d'émission.")
                st.caption(
                    "La référence est obtenue par `quantité × facteur d'émission`, "
                    "la formule que l'ETL utilise pour construire la cible du modèle. "
                    "Une variation de production s'y répercute donc **proportionnellement** : "
                    f"+{variation} % de production ⇒ +{variation} % d'empreinte. "
                    "Le modèle, lui, approxime — l'écart affiché est le prix de cette "
                    "approximation, et c'est précisément ce qui montre que cette tâche "
                    "est un calcul déterministe plus qu'une prédiction."
                )

            fig_comp = go.Figure()
            fig_comp.add_bar(
                x=["Actuel", "Scénario"],
                y=[kg_to_mt(co2_base_kg), kg_to_mt(co2_modif_kg)],
                marker_color=["#3498db", "#e74c3c" if delta_kg > 0 else "#2ecc71"],
                text=[fmt_co2(co2_base_kg), fmt_co2(co2_modif_kg)],
                textposition="outside",
            )
            fig_comp.update_layout(
                title=f"{pays_sc_name} — {categorie} : impact de {variation:+}%",
                yaxis_title="CO₂ (Mt)",
                height=320,
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            # Courbe de sensibilité — une seule passe de prédiction pour tous
            # les points, en empilant (produit × variation) dans un seul lot.
            st.subheader("Sensibilité CO₂ selon la variation de production")
            variations = list(range(-80, 201, 10))
            lots = []
            for v in variations:
                lot = produits_cat[["categorie", "quantite_1000t"]].copy()
                lot["quantite_1000t"] *= 1 + v / 100
                lot["_variation"] = v
                lots.append(lot)
            lot_total = pd.concat(lots, ignore_index=True)
            preds = predire_co2_par_produit(model_impact, lot_total, socio)
            co2_par_variation = (
                pd.Series(preds).groupby(lot_total["_variation"]).sum().reindex(variations)
            )
            ref_vals = [kg_to_mt(co2_reference_kg(produits_cat, 1 + v / 100))
                        for v in variations]
            df_sens = pd.DataFrame({
                "Variation (%)": variations,
                "Modèle (RandomForest)": kg_to_mt(co2_par_variation.to_numpy()),
                "Calcul exact (référence)": ref_vals,
            })
            fig_sens = px.line(
                df_sens, x="Variation (%)",
                y=["Modèle (RandomForest)", "Calcul exact (référence)"],
                markers=True,
                title=f"Sensibilité — {categorie} · {pays_sc_name}",
                labels={"value": "CO₂ (Mt)", "variable": ""},
                color_discrete_map={"Modèle (RandomForest)": "#3498db",
                                    "Calcul exact (référence)": "#2ecc71"},
            )
            fig_sens.add_vline(x=0, line_dash="dash", line_color="gray")
            fig_sens.add_vline(x=variation, line_color="red", annotation_text=f"{variation:+}%")
            fig_sens.update_layout(legend=dict(orientation="h", y=1.12, x=0))
            st.plotly_chart(fig_sens, use_container_width=True)
            st.caption(
                "La référence est une droite : l'empreinte est proportionnelle à la "
                "production. L'écart entre les deux courbes est la marge d'erreur du "
                "modèle — visible plutôt que dissimulée."
            )

    # ── Comparaison par catégorie (productions réelles du pays) ─
    if pays_row is not None and not produits_df.empty:
        st.markdown("---")
        st.subheader(f"Empreinte CO₂ par catégorie — {pays_sc_name} ({annee_sc})")

        socio_pays = {
            "pib":    pays_row["pib_per_capita"]    if pd.notna(pays_row["pib_per_capita"])    else 5000.0,
            "urba":   pays_row["taux_urbanisation"] if pd.notna(pays_row["taux_urbanisation"]) else 50.0,
            "pop":    pays_row["population"]        if pd.notna(pays_row["population"])        else 50e6,
            "surf":   pays_row["surface_agricole"]  if pd.notna(pays_row["surface_agricole"])  else 40.0,
            "region": pays_row["region"],
        }
        # Prédiction produit par produit, puis agrégation par catégorie :
        # le modèle n'est jamais sollicité hors de son domaine.
        preds_kg = predire_co2_par_produit(model_impact, produits_df, socio_pays)
        df_cat = (
            produits_df.assign(co2_kg=preds_kg)
            .groupby("categorie", as_index=False)
            .agg(co2_kg=("co2_kg", "sum"),
                 quantite=("quantite_1000t", "sum"),
                 n_produits=("produit_id", "count"))
            .rename(columns={"categorie": "Catégorie"})
        )
        df_cat["CO₂ (Mt)"] = kg_to_mt(df_cat["co2_kg"])
        df_cat["Production (kt)"] = df_cat["quantite"]
        df_cat = df_cat.sort_values("CO₂ (Mt)", ascending=False)

        fig_cat = px.bar(
            df_cat, x="Catégorie", y="CO₂ (Mt)", color="Catégorie",
            hover_data={"Production (kt)": ":,.0f", "n_produits": True,
                        "co2_kg": False, "quantite": False},
            title=f"CO₂ prédit par catégorie — productions réelles de {pays_sc_name}",
            labels={"n_produits": "Produits"},
        )
        fig_cat.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig_cat, use_container_width=True)
        st.caption(
            f"Somme de {len(produits_df)} prédictions au grain produit, agrégées par "
            f"catégorie — et non une prédiction unique sur un total de catégorie."
        )


# ══════════════════════════════════════════════════════════════
# PAGE 4 — Méthodologie & limites
# ══════════════════════════════════════════════════════════════
elif page == "📐 Méthodologie & limites":
    st.title("📐 Méthodologie & limites")
    st.markdown(
        "Cette page documente **comment les chiffres sont produits** et **ce "
        "qu'ils ne disent pas**. Elle fait partie du livrable : une mesure sans "
        "son domaine de validité n'est pas un résultat."
    )

    tab_data, tab_calcul, tab_ml, tab_limites = st.tabs(
        ["Données", "Calcul de l'empreinte", "Modèles", "Limites connues"]
    )

    with tab_data:
        st.subheader("Sources")
        st.dataframe(
            pd.DataFrame([
                {"Source": "FAOSTAT", "Contenu": "Bilans alimentaires (Food + Feed)",
                 "Période": "1961–2023", "Licence": "CC BY-NC-SA 3.0 IGO"},
                {"Source": "Our World in Data — Poore & Nemecek (2018)",
                 "Contenu": "Facteurs CO₂, eau, sol par kg de produit",
                 "Période": "Statique", "Licence": "CC BY 4.0"},
                {"Source": "World Bank Open Data",
                 "Contenu": "PIB/hab., urbanisation, population, surface agricole",
                 "Période": "1961–2023", "Licence": "CC BY 4.0"},
                {"Source": "OWID — Meat supply per person",
                 "Contenu": "Consommation de viande par habitant",
                 "Période": "1961–2020", "Licence": "CC BY 4.0"},
            ]),
            use_container_width=True, hide_index=True,
        )
        st.subheader("Architecture")
        st.markdown(
            "Data Lake (schéma `raw`, 5 tables, données brutes non modifiées) → "
            "ETL Python → Data Warehouse en étoile (schéma `public`, 4 dimensions "
            "+ 3 tables de faits). Le pipeline est rejouable : "
            "`python scripts/etl_pipeline.py`."
        )
        st.info(
            "**Aucune donnée personnelle n'est traitée.** Toutes les données sont "
            "agrégées au niveau pays × année. Le simulateur s'exécute côté "
            "navigateur et n'enregistre rien. Cf. `docs/rgpd.md`."
        )

    with tab_calcul:
        st.subheader("Chaîne de calcul")
        st.code(
            "quantite_kg   = quantite_1000t × 1e6\n"
            "co2_total_kg  = quantite_kg × facteur_CO2(produit)   [kg CO₂-eq/kg]\n"
            "co2_per_capita = co2_total_kg / population",
            language="text",
        )
        st.markdown(
            "Les facteurs proviennent de **Poore & Nemecek (2018)**, méta-analyse "
            "de 38 700 exploitations dans 119 pays. Ils couvrent le cycle complet : "
            "changement d'usage des sols, exploitation, alimentation animale, "
            "transformation, transport, emballage, distribution."
        )
        st.warning(
            "**Périmètre : production, pas consommation.** Les quantités FAO "
            "mesurent ce qu'un pays *produit et met à disposition*, pas ce que ses "
            "habitants mangent. Les exportations, l'alimentation animale et les "
            "pertes sont incluses. Un pays exportateur agricole apparaît donc plus "
            "émetteur qu'il ne l'est du point de vue de ses habitants."
        )
        st.markdown(
            "**Couverture des facteurs.** Seuls les produits FAO appariés au jeu "
            "Food_Production disposent d'un facteur (appariement flou sur le nom). "
            "Les autres sortent du calcul : l'empreinte affichée est donc une "
            "**borne basse**."
        )

    with tab_ml:
        st.subheader("Trois modèles, trois statuts")
        st.markdown(
            """
| Modèle | Tâche | Statut |
|---|---|---|
| **A — Calculateur** | `co2_total_kg` ~ quantité + catégorie + socio-éco | ⚠️ Largement déterministe |
| **B — Prédictif** | `co2_per_capita` ~ socio-économique **seul** | ✅ Vraie prédiction |
| **C — Clustering** | Profils de pays (KMeans, k=5) | ✅ Non supervisé |
"""
        )
        st.error(
            "**Le modèle A ne prédit pas, il reconstitue.** Sa cible est construite "
            "par `co2_total_kg = quantité × facteur(produit)`, et la quantité lui est "
            "donnée en entrée. Il réapprend donc surtout une multiplication que nous "
            "avons nous-mêmes effectuée — `catégorie` servant d'approximation du "
            "facteur. Son R² élevé mesure une reconstitution arithmétique, pas un "
            "pouvoir prédictif. Il est conservé comme **calculateur** de scénarios, "
            "ce qu'il fait correctement."
        )
        st.info(
            "**La page Prédiction affiche les deux.** À côté de la prédiction du "
            "modèle figure le **calcul exact** (`quantité × facteur d'émission`), "
            "ainsi que l'écart entre les deux. Le modèle estime bien le *niveau* "
            "d'empreinte (écart de l'ordre de ±5 %), mais restitue moins bien sa "
            "*sensibilité* à une variation de production. Rendre cet écart visible "
            "vaut mieux que de le masquer derrière un R² flatteur."
        )
        st.success(
            "**Le modèle B est la vraie démonstration.** Il prédit l'empreinte par "
            "habitant à partir des seules variables socio-économiques — PIB, "
            "urbanisation, population, surface agricole, région — dont aucune "
            "n'entre dans la construction de la cible. Son R² est plus bas, et "
            "c'est le résultat honnête."
        )
        st.subheader("Protocole d'évaluation")
        st.markdown(
            "Chaque régression est évaluée **deux fois** : split aléatoire "
            "(optimiste) et split **groupé par pays** (aucun pays des deux côtés). "
            "L'écart entre les deux mesure la fuite d'information due à la structure "
            "des données — deux années consécutives d'un même pays sont presque "
            "identiques."
        )
        metrics_path = BASE_DIR / "docs" / "metrics.json"
        if metrics_path.exists():
            import json
            with st.expander("📊 Métriques mesurées (docs/metrics.json)"):
                st.json(json.loads(metrics_path.read_text(encoding="utf-8")))
        else:
            st.caption(
                "Métriques non générées — lancer `python scripts/train_model.py`."
            )

    with tab_limites:
        st.subheader("Ce que ce travail ne permet pas de conclure")
        st.markdown(
            """
1. **Production ≠ consommation.** Voir l'onglet *Calcul*. Une comparaison
   « votre assiette vs votre pays » est un ordre de grandeur, pas une mesure.

2. **Facteurs d'émission moyens et statiques.** Un kg de bœuf reçoit le même
   facteur au Brésil et en Irlande, alors que les écarts réels sont d'un
   facteur 10 selon le système d'élevage. Les facteurs ne varient pas non plus
   dans le temps, alors que la période couverte est de 60 ans.

3. **Couverture partielle des produits.** Les produits FAO non appariés n'ont
   pas de facteur et sortent du total.

4. **Le modèle A n'extrapole pas.** Un RandomForest interrogé au-delà de sa
   plage d'entraînement renvoie une constante. Les scénarios de forte variation
   de production saturent : l'application le signale explicitement.

5. **Corrélation, pas causalité.** Le lien entre urbanisation et consommation
   de viande est robuste statistiquement, mais ces variables sont co-déterminées
   par le développement économique. Rien ici n'établit un mécanisme causal.

6. **Silhouette de 0,27 pour le clustering.** Les groupes sont réels mais
   faiblement séparés — attendu sur des variables socio-économiques continues.
   Les 5 profils sont des repères de lecture, pas des catégories étanches.
"""
        )
        st.caption(
            "Audit interne complet et plan de correction : `docs/audit.md` "
            "(non versionné)."
        )
