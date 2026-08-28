#!/usr/bin/env python
"""Pipeline ETL — Data Lake (raw) + Data Warehouse en étoile (public).

Version industrialisée de `notebooks/02_etl_pipeline.ipynb` : même logique,
exécutable sans Jupyter, idempotente, et pilotable étape par étape.

Usage
-----
    python scripts/etl_pipeline.py                  # pipeline complet
    python scripts/etl_pipeline.py --steps dwh      # à partir des dimensions
    python scripts/etl_pipeline.py --steps facts    # faits uniquement
    python scripts/etl_pipeline.py --validate-only  # contrôles, aucune écriture

Idempotence
-----------
Chaque étape recrée ou vide ses tables avant écriture : le script peut être
relancé autant de fois que nécessaire sans dupliquer de lignes.

Migration vers AWS RDS : modifier `.env`, rien d'autre. La connexion est
entièrement dérivée des variables d'environnement (cf. docs/deploiement_aws.md).
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent))
from _mappings import FAO_TO_ISO3, REGION_MAP, categorize  # noqa: E402

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW = BASE_DIR / "data" / "raw"

load_dotenv(BASE_DIR / ".env")

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DB = os.getenv("POSTGRES_DB", "food_impact")
PG_USER = os.getenv("POSTGRES_USER", "food_user")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "food_pass")
PG_SSLMODE = os.getenv("POSTGRES_SSLMODE", "prefer")

# Le mot de passe transite par connect_args, pas par l'URL : pas d'encodage à
# gérer, et il n'apparaît dans aucune trace d'erreur SQLAlchemy.
CONNECT_ARGS = {
    "host": PG_HOST,
    "port": int(PG_PORT),
    "dbname": PG_DB,
    "user": PG_USER,
    "password": PG_PASS,
    "sslmode": PG_SSLMODE,
    "connect_timeout": 30,
}
DB_URL = "postgresql+psycopg2://"

SOURCES = {
    "raw_fao_historique": DATA_RAW / "FAO.csv",
    "raw_fao_complet": DATA_RAW / "FAO_complet_1961_2023.csv",
    "raw_food_production": DATA_RAW / "Food_Production.csv",
    "raw_worldbank": DATA_RAW / "worldbank_socioeco_interp.csv",
    "raw_owid_meat": DATA_RAW / "owid_meat_consumption.csv",
}

# `FAO.csv` est le seul fichier en latin-1 (cf. CLAUDE.md).
ENCODINGS = {"raw_fao_historique": "latin-1"}

TABLES_DWH = [
    "fait_impact_pays_annee",
    "dim_socio_economique",
    "fait_production",
    "fait_impact",
    "dim_produits",
    "dim_temps",
    "dim_pays",
]

ANNEE_MIN, ANNEE_MAX = 1961, 2023

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("etl")

engine = create_engine(DB_URL, connect_args=CONNECT_ARGS,
                       pool_pre_ping=True, echo=False)


# ──────────────────────────────────────────────────────────────
# Helpers d'accès base
# ──────────────────────────────────────────────────────────────
def run_sql(sql: str, params: dict | None = None) -> None:
    with engine.connect() as con:
        con.execute(text(sql), params or {})
        con.commit()


def query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    return pd.read_sql(text(sql), engine, params=params or {})


def ingest_df(df: pd.DataFrame, schema: str, table: str, chunksize: int = 5000) -> None:
    """Insère un DataFrame. COPY FROM STDIN au-delà de 50k lignes (~10× plus rapide).

    Les colonnes sont TOUJOURS nommées explicitement dans le COPY : sans cela,
    PostgreSQL aligne les colonnes du CSV sur l'ordre physique de la table et
    décale tout d'un cran à cause de la colonne SERIAL (cf. CLAUDE.md).
    """
    if df.empty:
        log.warning("  %s.%s : DataFrame vide, rien à insérer", schema, table)
        return

    if len(df) > 50_000:
        conn = engine.raw_connection()
        try:
            cur = conn.cursor()
            buf = io.StringIO()
            df.to_csv(buf, index=False, header=False, na_rep="\\N")
            buf.seek(0)
            cols = ", ".join(df.columns)
            cur.copy_expert(
                f"COPY {schema}.{table} ({cols}) FROM STDIN WITH CSV NULL '\\N'", buf
            )
            conn.commit()
            cur.close()
        finally:
            conn.close()
    else:
        df.to_sql(
            table, engine, schema=schema, if_exists="append",
            index=False, method="multi", chunksize=chunksize,
        )


def check_connection() -> None:
    try:
        with engine.connect() as con:
            version = con.execute(text("SELECT version()")).scalar()
    except Exception as exc:  # noqa: BLE001
        log.error("Connexion PostgreSQL impossible : %s", exc)
        log.error("→ base locale : docker compose -f docker/docker-compose.yml up -d")
        log.error("→ base RDS    : python scripts/check_db.py")
        raise SystemExit(1) from exc
    log.info("PostgreSQL connecté — %s", version[:60])
    log.info("Cible : %s:%s/%s", PG_HOST, PG_PORT, PG_DB)


# ──────────────────────────────────────────────────────────────
# Étape 1 — Schéma
# ──────────────────────────────────────────────────────────────
def create_schema() -> None:
    log.info("[1/8] Création des schémas et tables")
    run_sql("CREATE SCHEMA IF NOT EXISTS raw")

    for table in TABLES_DWH:
        run_sql(f"DROP TABLE IF EXISTS public.{table} CASCADE")

    run_sql("""
    CREATE TABLE dim_pays (
        pays_id   SERIAL PRIMARY KEY,
        nom_pays  VARCHAR(100) NOT NULL,
        code_fao  VARCHAR(10),
        code_iso2 VARCHAR(2),
        code_iso3 VARCHAR(3),
        region    VARCHAR(100),
        latitude  DOUBLE PRECISION,
        longitude DOUBLE PRECISION
    )""")

    run_sql("""
    CREATE TABLE dim_produits (
        produit_id     SERIAL PRIMARY KEY,
        nom_fao        VARCHAR(200),
        nom_impact     VARCHAR(200),
        categorie      VARCHAR(100) NOT NULL,
        sous_categorie VARCHAR(100),
        match_quality  VARCHAR(20)
    )""")

    run_sql("""
    CREATE TABLE dim_temps (
        annee_id SERIAL PRIMARY KEY,
        annee    INTEGER NOT NULL,
        decennie INTEGER,
        periode  VARCHAR(10)
    )""")

    run_sql("""
    CREATE TABLE dim_socio_economique (
        socio_id          SERIAL PRIMARY KEY,
        pays_id           INTEGER NOT NULL REFERENCES dim_pays(pays_id),
        annee_id          INTEGER NOT NULL REFERENCES dim_temps(annee_id),
        pib_per_capita    DOUBLE PRECISION,
        taux_urbanisation DOUBLE PRECISION,
        population        BIGINT,
        surface_agricole  DOUBLE PRECISION
    )""")

    run_sql("""
    CREATE TABLE fait_production (
        production_id  SERIAL PRIMARY KEY,
        pays_id        INTEGER NOT NULL REFERENCES dim_pays(pays_id),
        produit_id     INTEGER NOT NULL REFERENCES dim_produits(produit_id),
        annee_id       INTEGER NOT NULL REFERENCES dim_temps(annee_id),
        element        VARCHAR(10) NOT NULL,
        quantite_1000t DOUBLE PRECISION
    )""")

    run_sql("""
    CREATE TABLE fait_impact (
        impact_id              SERIAL PRIMARY KEY,
        produit_id             INTEGER NOT NULL REFERENCES dim_produits(produit_id),
        co2_land_use_per_kg    DOUBLE PRECISION,
        co2_animal_feed_per_kg DOUBLE PRECISION,
        co2_farm_per_kg        DOUBLE PRECISION,
        co2_processing_per_kg  DOUBLE PRECISION,
        co2_transport_per_kg   DOUBLE PRECISION,
        co2_packaging_per_kg   DOUBLE PRECISION,
        co2_retail_per_kg      DOUBLE PRECISION,
        co2_total_per_kg       DOUBLE PRECISION,
        freshwater_per_kg      DOUBLE PRECISION,
        scarcity_water_per_kg  DOUBLE PRECISION,
        land_use_per_kg        DOUBLE PRECISION,
        eutrophying_per_kg     DOUBLE PRECISION
    )""")

    run_sql("""
    CREATE TABLE fait_impact_pays_annee (
        impact_pays_id          SERIAL PRIMARY KEY,
        pays_id                 INTEGER NOT NULL REFERENCES dim_pays(pays_id),
        annee_id                INTEGER NOT NULL REFERENCES dim_temps(annee_id),
        produit_id              INTEGER NOT NULL REFERENCES dim_produits(produit_id),
        quantite_1000t          DOUBLE PRECISION,
        quantite_kg             DOUBLE PRECISION,
        co2_total_kg            DOUBLE PRECISION,
        freshwater_total_litres DOUBLE PRECISION,
        land_use_total_m2       DOUBLE PRECISION
    )""")

    log.info("  7 tables DWH créées (schéma public) + schéma raw")


# ──────────────────────────────────────────────────────────────
# Étape 2 — Data Lake
# ──────────────────────────────────────────────────────────────
def load_datalake() -> None:
    log.info("[2/8] Ingestion du Data Lake (schéma raw)")
    missing = [p.name for p in SOURCES.values() if not p.exists()]
    if missing:
        log.error("Fichiers sources manquants : %s", missing)
        log.error("→ Les CSV doivent être présents dans %s", DATA_RAW)
        raise SystemExit(1)

    total = 0
    for table_name, csv_path in SOURCES.items():
        t0 = time.time()
        df = pd.read_csv(
            csv_path, encoding=ENCODINGS.get(table_name, "utf-8"), low_memory=False
        )
        df.columns = (
            df.columns.str.strip()
            .str.lower()
            .str.replace(r"[^a-z0-9]+", "_", regex=True)
            .str.strip("_")
        )
        df.to_sql(
            table_name, engine, schema="raw", if_exists="replace",
            index=False, method="multi", chunksize=5000,
        )
        total += len(df)
        log.info(
            "  raw.%-22s %9s lignes × %2d cols (%.1fs)",
            table_name, f"{len(df):,}", len(df.columns), time.time() - t0,
        )
    log.info("  Data Lake : %s lignes au total", f"{total:,}")


# ──────────────────────────────────────────────────────────────
# Étape 3-6 — Dimensions
# ──────────────────────────────────────────────────────────────
def build_dim_pays() -> None:
    log.info("[3/8] dim_pays")
    import pycountry

    def get_iso3(name):
        if name in FAO_TO_ISO3:
            return FAO_TO_ISO3[name]
        try:
            return pycountry.countries.lookup(name).alpha_3
        except LookupError:
            pass
        try:
            matches = pycountry.countries.search_fuzzy(name)
            if matches:
                return matches[0].alpha_3
        except Exception:  # noqa: BLE001
            pass
        return None

    areas = query_df("SELECT DISTINCT area FROM raw.raw_fao_complet ORDER BY area")["area"].tolist()

    rows, unmapped = [], []
    for area in areas:
        iso3 = get_iso3(area)
        if iso3 is None:
            unmapped.append(area)
            continue
        c = pycountry.countries.get(alpha_3=iso3)
        iso2 = c.alpha_2 if c else None
        rows.append({
            "nom_pays": area, "code_fao": None, "code_iso2": iso2,
            "code_iso3": iso3, "region": REGION_MAP.get(iso2),
            "latitude": None, "longitude": None,
        })

    df_pays = pd.DataFrame(rows)
    ingest_df(df_pays, "public", "dim_pays")
    log.info(
        "  %d pays insérés (%d avec région, %d agrégats FAO exclus)",
        len(df_pays), int(df_pays["region"].notna().sum()), len(unmapped),
    )


def build_dim_temps() -> None:
    log.info("[4/8] dim_temps")
    annees = list(range(ANNEE_MIN, ANNEE_MAX + 1))
    df = pd.DataFrame({
        "annee": annees,
        "decennie": [(a // 10) * 10 for a in annees],
        "periode": [f"{(a // 10) * 10}s" for a in annees],
    })
    ingest_df(df, "public", "dim_temps")
    log.info("  %d années insérées (%d–%d)", len(df), ANNEE_MIN, ANNEE_MAX)


def build_dim_produits() -> None:
    log.info("[5/8] dim_produits")
    try:
        from rapidfuzz import fuzz
        from rapidfuzz import process as rfprocess
        use_rapidfuzz = True
    except ImportError:
        from difflib import get_close_matches
        use_rapidfuzz = False
        log.warning("  rapidfuzz absent → repli sur difflib (matching moins précis)")

    def fuzzy_match(name, candidates):
        if use_rapidfuzz:
            res = rfprocess.extractOne(name, candidates, scorer=fuzz.token_sort_ratio)
            if res and res[1] >= 55:
                return res[0], int(res[1])
            return None, 0
        lowered = [c.lower() for c in candidates]
        m = get_close_matches(name.lower(), lowered, n=1, cutoff=0.45)
        if m:
            return candidates[lowered.index(m[0])], 65
        return None, 0

    fp_cols = query_df("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'raw' AND table_name = 'raw_food_production'
        ORDER BY ordinal_position
    """)["column_name"].tolist()
    col_fp_produit = fp_cols[0]
    fp_names = query_df(
        f'SELECT DISTINCT "{col_fp_produit}" FROM raw.raw_food_production'
    )[col_fp_produit].dropna().tolist()

    fao_items = query_df(
        "SELECT DISTINCT item FROM raw.raw_fao_complet ORDER BY item"
    )["item"].tolist()

    rows = []
    for item in fao_items:
        cat, sub = categorize(item)
        nom_impact, score = fuzzy_match(item, fp_names)
        quality = None
        if nom_impact:
            quality = "high" if score >= 80 else "medium" if score >= 55 else "low"
            if quality == "low":
                nom_impact, quality = None, None
        rows.append({
            "nom_fao": item, "nom_impact": nom_impact, "categorie": cat,
            "sous_categorie": sub, "match_quality": quality,
        })

    df = pd.DataFrame(rows)
    ingest_df(df, "public", "dim_produits")
    log.info(
        "  %d produits insérés (%d matchés Food_Production, dont %d 'high')",
        len(df), int(df["nom_impact"].notna().sum()),
        int((df["match_quality"] == "high").sum()),
    )


def build_dim_socio() -> None:
    log.info("[6/8] dim_socio_economique")

    def find_col(cols, candidates):
        for cand in candidates:
            m = [c for c in cols if cand.lower() in c.lower()]
            if m:
                return m[0]
        return None

    wb_cols = query_df("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'raw' AND table_name = 'raw_worldbank'
        ORDER BY ordinal_position
    """)["column_name"].tolist()

    rename = {}
    for target, cands in [
        ("code_iso3", ["iso3", "alpha_3", "iso_3", "code_iso3", "code"]),
        ("annee", ["year", "annee"]),
        ("pib_per_capita", ["gdp", "pib", "ny_gdp"]),
        ("taux_urbanisation", ["urb", "urban"]),
        ("population", ["pop", "population", "sp_pop"]),
        ("surface_agricole", ["agri", "ag_lnd", "land"]),
    ]:
        col = find_col(wb_cols, cands)
        if col:
            rename[col] = target

    df_wb = query_df("SELECT * FROM raw.raw_worldbank").rename(columns=rename)
    df_wb["annee"] = pd.to_numeric(df_wb["annee"], errors="coerce").astype("Int64")

    num_cols = ["pib_per_capita", "taux_urbanisation", "population", "surface_agricole"]
    for c in num_cols:
        if c not in df_wb.columns:
            df_wb[c] = np.nan

    df_dim_pays = query_df(
        "SELECT pays_id, code_iso3 FROM public.dim_pays WHERE code_iso3 IS NOT NULL"
    )
    df_dim_temps = query_df("SELECT annee_id, annee FROM public.dim_temps")
    df_dim_temps["annee"] = df_dim_temps["annee"].astype("Int64")

    df = (
        df_wb.merge(df_dim_pays, on="code_iso3", how="inner")
        .merge(df_dim_temps, on="annee", how="inner")
    )[["pays_id", "annee_id"] + num_cols]

    for c in ["pib_per_capita", "taux_urbanisation", "surface_agricole"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["population"] = pd.to_numeric(df["population"], errors="coerce").astype("Int64")
    df = df.drop_duplicates(subset=["pays_id", "annee_id"])

    ingest_df(df, "public", "dim_socio_economique")
    log.info(
        "  %s lignes (%d pays × %d années, PIB non-null : %s)",
        f"{len(df):,}", df["pays_id"].nunique(), df["annee_id"].nunique(),
        f"{int(df['pib_per_capita'].notna().sum()):,}",
    )


# ──────────────────────────────────────────────────────────────
# Étape 7-8 — Faits
# ──────────────────────────────────────────────────────────────
def build_fait_impact() -> None:
    log.info("[7/8] fait_impact + fait_production")
    run_sql("TRUNCATE TABLE public.fait_impact CASCADE")

    fp_cols = query_df("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'raw' AND table_name = 'raw_food_production'
        ORDER BY ordinal_position
    """)["column_name"].tolist()
    col_fp_produit = fp_cols[0]

    def find_fp_col(candidates):
        for cand in candidates:
            m = [c for c in fp_cols if cand.lower() in c.lower()]
            if m:
                return m[0]
        return None

    # ⚠️ Les colonnes eau / land / eutrophisation existent en deux variantes dans
    # Food_Production.csv : per_kilogram et per_1000kcal. Une recherche sur
    # 'freshwater' seul renvoie la variante per_1000kcal en premier (cf. CLAUDE.md).
    col_map_src = {
        find_fp_col(["land_use_change"]): "co2_land_use_per_kg",
        find_fp_col(["animal_feed"]): "co2_animal_feed_per_kg",
        find_fp_col(["farm"]): "co2_farm_per_kg",
        find_fp_col(["processing"]): "co2_processing_per_kg",
        find_fp_col(["transport"]): "co2_transport_per_kg",
        find_fp_col(["packging", "packaging"]): "co2_packaging_per_kg",
        find_fp_col(["retail"]): "co2_retail_per_kg",
        find_fp_col(["total_emission", "total_ghg"]): "co2_total_per_kg",
        find_fp_col(["freshwater_withdrawals_per_kilogram"]): "freshwater_per_kg",
        find_fp_col(["scarcity_weighted_water_use_per_kilogram"]): "scarcity_water_per_kg",
        find_fp_col(["land_use_per_kilogram"]): "land_use_per_kg",
        find_fp_col(["eutrophying_emissions_per_kilogram"]): "eutrophying_per_kg",
    }
    col_map = {"produit_id": "produit_id"}
    col_map.update({k: v for k, v in col_map_src.items() if k})

    df_fp = query_df("SELECT * FROM raw.raw_food_production")
    df_dim_prod = query_df(
        "SELECT produit_id, nom_impact FROM public.dim_produits WHERE nom_impact IS NOT NULL"
    )
    df_fp["_key"] = df_fp[col_fp_produit].str.strip()
    df_dim_prod["_key"] = df_dim_prod["nom_impact"].str.strip()
    df_fi = df_fp.merge(df_dim_prod, on="_key", how="inner")

    df = df_fi[list(col_map.keys())].rename(columns=col_map)
    for c in df.columns:
        if c != "produit_id":
            df[c] = pd.to_numeric(df[c], errors="coerce")

    ingest_df(df, "public", "fait_impact")
    log.info(
        "  fait_impact : %d produits (CO₂ non-null : %d)",
        len(df), int(df["co2_total_per_kg"].notna().sum()),
    )

    # ── fait_production ──
    run_sql("TRUNCATE TABLE public.fait_production CASCADE")
    df_fao = query_df("""
        SELECT area, item, element, year::INTEGER AS year, value
        FROM raw.raw_fao_complet
        WHERE element IN ('Food', 'Feed') AND value IS NOT NULL
    """)

    df_dp = query_df("SELECT pays_id, nom_pays FROM public.dim_pays")
    df_dpr = query_df("SELECT produit_id, nom_fao FROM public.dim_produits")
    df_dt = query_df("SELECT annee_id, annee FROM public.dim_temps")
    df_dt["annee"] = df_dt["annee"].astype(int)
    df_fao["year"] = df_fao["year"].astype(int)

    df_prod = (
        df_fao.merge(df_dp, left_on="area", right_on="nom_pays", how="inner")
        .merge(df_dpr, left_on="item", right_on="nom_fao", how="inner")
        .merge(df_dt, left_on="year", right_on="annee", how="inner")
    )[["pays_id", "produit_id", "annee_id", "element", "value"]]

    df_prod = df_prod.rename(columns={"value": "quantite_1000t"})
    df_prod["element"] = df_prod["element"].str[:10]
    df_prod["quantite_1000t"] = pd.to_numeric(df_prod["quantite_1000t"], errors="coerce")
    df_prod = df_prod.drop_duplicates(
        subset=["pays_id", "produit_id", "annee_id", "element"]
    )

    ingest_df(df_prod, "public", "fait_production")
    log.info("  fait_production : %s lignes", f"{len(df_prod):,}")


def build_fait_impact_pays_annee() -> None:
    log.info("[8/8] fait_impact_pays_annee (table ML principale)")
    run_sql("TRUNCATE TABLE public.fait_impact_pays_annee")

    df_fprod = query_df("""
        SELECT pays_id, annee_id, produit_id, SUM(quantite_1000t) AS quantite_1000t
        FROM public.fait_production
        WHERE element = 'Food'
        GROUP BY pays_id, annee_id, produit_id
    """)
    df_fimpact = query_df("""
        SELECT produit_id, co2_total_per_kg, freshwater_per_kg,
               land_use_per_kg, eutrophying_per_kg
        FROM public.fait_impact
    """)

    df = df_fprod.merge(df_fimpact, on="produit_id", how="left")

    # 1000 t → kg (× 1e6), puis application des facteurs unitaires.
    df["quantite_kg"] = df["quantite_1000t"] * 1e6
    df["co2_total_kg"] = df["quantite_kg"] * df["co2_total_per_kg"]
    df["freshwater_total_litres"] = df["quantite_kg"] * df["freshwater_per_kg"]
    df["land_use_total_m2"] = df["quantite_kg"] * df["land_use_per_kg"]

    df = df[[
        "pays_id", "annee_id", "produit_id", "quantite_1000t", "quantite_kg",
        "co2_total_kg", "freshwater_total_litres", "land_use_total_m2",
    ]].drop_duplicates(subset=["pays_id", "annee_id", "produit_id"])

    ingest_df(df, "public", "fait_impact_pays_annee")
    log.info(
        "  %s lignes (%d pays × %d années × %d produits · CO₂ non-null : %.0f%%)",
        f"{len(df):,}", df["pays_id"].nunique(), df["annee_id"].nunique(),
        df["produit_id"].nunique(), df["co2_total_kg"].notna().mean() * 100,
    )


def create_indexes() -> None:
    """Index sur les clés de jointure — l'app fait des agrégats à chaque interaction."""
    log.info("Création des index")
    for stmt in [
        "CREATE INDEX IF NOT EXISTS idx_fipa_pays  ON fait_impact_pays_annee(pays_id)",
        "CREATE INDEX IF NOT EXISTS idx_fipa_annee ON fait_impact_pays_annee(annee_id)",
        "CREATE INDEX IF NOT EXISTS idx_fipa_prod  ON fait_impact_pays_annee(produit_id)",
        "CREATE INDEX IF NOT EXISTS idx_socio_pk   ON dim_socio_economique(pays_id, annee_id)",
        "CREATE INDEX IF NOT EXISTS idx_pays_iso3  ON dim_pays(code_iso3)",
        "CREATE INDEX IF NOT EXISTS idx_temps_an   ON dim_temps(annee)",
    ]:
        run_sql(stmt)
    log.info("  6 index créés")


# ──────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────
EXPECTATIONS = {
    "dim_pays": (100, 250),
    "dim_temps": (63, 63),
    "dim_produits": (50, 200),
    "dim_socio_economique": (5_000, 20_000),
    "fait_impact": (10, 100),
    "fait_production": (500_000, 3_000_000),
    "fait_impact_pays_annee": (200_000, 1_500_000),
}


def validate() -> bool:
    """Contrôles de cohérence. Retourne False si un contrôle échoue."""
    log.info("Validation du Data Warehouse")
    ok = True

    for table, (lo, hi) in EXPECTATIONS.items():
        try:
            n = int(query_df(f"SELECT COUNT(*) AS n FROM public.{table}")["n"].iloc[0])
        except Exception as exc:  # noqa: BLE001
            log.error("  ✗ %-24s illisible (%s)", table, type(exc).__name__)
            ok = False
            continue
        status = "✓" if lo <= n <= hi else "✗"
        if status == "✗":
            ok = False
        log.info("  %s %-24s %12s lignes (attendu %s–%s)",
                 status, table, f"{n:,}", f"{lo:,}", f"{hi:,}")

    # Intégrité référentielle : aucun orphelin
    orphans = query_df("""
        SELECT COUNT(*) AS n FROM fait_impact_pays_annee f
        LEFT JOIN dim_pays p ON f.pays_id = p.pays_id
        WHERE p.pays_id IS NULL
    """)["n"].iloc[0]
    if orphans:
        log.error("  ✗ %s faits orphelins (pays_id inconnu)", f"{orphans:,}")
        ok = False
    else:
        log.info("  ✓ Intégrité référentielle : aucun orphelin")

    # Cohérence du grain : une seule ligne par (pays, année, produit)
    dupes = query_df("""
        SELECT COUNT(*) AS n FROM (
            SELECT pays_id, annee_id, produit_id
            FROM fait_impact_pays_annee
            GROUP BY 1,2,3 HAVING COUNT(*) > 1
        ) t
    """)["n"].iloc[0]
    if dupes:
        log.error("  ✗ %s combinaisons (pays, année, produit) dupliquées", f"{dupes:,}")
        ok = False
    else:
        log.info("  ✓ Grain respecté : 1 ligne par (pays, année, produit)")

    # Plage d'années réellement couverte par les faits
    plage = query_df("""
        SELECT MIN(t.annee) AS amin, MAX(t.annee) AS amax
        FROM fait_impact_pays_annee f JOIN dim_temps t ON f.annee_id = t.annee_id
    """)
    log.info("  ℹ Années couvertes par les faits : %s–%s",
             plage["amin"].iloc[0], plage["amax"].iloc[0])

    # Catégories réellement présentes (contrat avec l'app et le modèle)
    cats = query_df("""
        SELECT DISTINCT categorie FROM dim_produits ORDER BY categorie
    """)["categorie"].tolist()
    log.info("  ℹ Catégories en base (%d) : %s", len(cats), ", ".join(cats))

    log.info("Validation %s", "RÉUSSIE" if ok else "ÉCHOUÉE")
    return ok


# ──────────────────────────────────────────────────────────────
# Orchestration
# ──────────────────────────────────────────────────────────────
STEPS = {
    "schema": create_schema,
    "datalake": load_datalake,
    "dim_pays": build_dim_pays,
    "dim_temps": build_dim_temps,
    "dim_produits": build_dim_produits,
    "dim_socio": build_dim_socio,
    "faits": build_fait_impact,
    "faits_ml": build_fait_impact_pays_annee,
    "index": create_indexes,
}

GROUPS = {
    "all": list(STEPS),
    "dwh": ["schema", "dim_pays", "dim_temps", "dim_produits", "dim_socio",
            "faits", "faits_ml", "index"],
    "facts": ["faits", "faits_ml", "index"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--steps", default="all", choices=list(GROUPS),
                        help="groupe d'étapes à exécuter (défaut : all)")
    parser.add_argument("--validate-only", action="store_true",
                        help="ne lance que les contrôles, aucune écriture")
    args = parser.parse_args()

    check_connection()

    if args.validate_only:
        return 0 if validate() else 1

    t0 = time.time()
    for name in GROUPS[args.steps]:
        STEPS[name]()

    ok = validate()
    log.info("Pipeline terminé en %.0f s", time.time() - t0)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
