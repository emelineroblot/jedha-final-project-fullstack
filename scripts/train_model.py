#!/usr/bin/env python
"""Entraînement des modèles — version industrialisée de 04_machine_learning.ipynb.

Trois modèles sont produits :

A. `model_impact.pkl` — **calculateur d'empreinte** (régression)
   Cible : log1p(co2_total_kg) au grain (pays, année, produit).
   ⚠️ Cette tâche est en grande partie DÉTERMINISTE : l'ETL construit la cible
   par `co2_total_kg = quantite_1000t × 1e6 × facteur(produit)`. Le modèle
   reconstitue donc surtout cette multiplication, `categorie` servant de proxy
   du facteur. Son R² élevé ne mesure PAS une capacité prédictive.
   Il est conservé parce que l'application s'en sert comme calculateur, et
   parce que l'écart au produit exact est instructif — mais il doit être
   présenté comme tel. Cf. docs/audit.md §4.1.

B. `model_co2_per_capita.pkl` — **vraie tâche prédictive** (régression)
   Cible : log1p(co2_per_capita) au grain (pays, année), à partir des SEULES
   variables socio-économiques. `quantite_1000t` est volontairement exclue :
   elle n'entre pas dans la construction de la cible, donc rien n'est
   tautologique ici. Le R² est plus bas, et c'est le résultat honnête.

C. `model_clustering.pkl` — **profils de pays** (KMeans)
   Sauvegardé sous forme de dict {'scaler', 'kmeans', 'features'} : sans le
   scaler d'entraînement, les prédictions ne sont pas reproductibles.

Chaque régression est évaluée selon DEUX protocoles :
  · split aléatoire        → optimiste, comparable au notebook d'origine
  · split groupé par pays  → honnête, aucun pays n'est vu des deux côtés

Usage
-----
    python scripts/train_model.py                 # tout
    python scripts/train_model.py --skip-tuning   # rapide, sans RandomizedSearchCV
    python scripts/train_model.py --only clustering
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, silhouette_score
from sklearn.model_selection import GroupShuffleSplit, RandomizedSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
DOCS_DIR = BASE_DIR / "docs"
MODELS_DIR.mkdir(exist_ok=True)
DOCS_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

DB_URL = "postgresql+psycopg2://"
CONNECT_ARGS = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "dbname": os.getenv("POSTGRES_DB", "food_impact"),
    "user": os.getenv("POSTGRES_USER", "food_user"),
    "password": os.getenv("POSTGRES_PASSWORD", "food_pass"),
    "sslmode": os.getenv("POSTGRES_SSLMODE", "prefer"),
    "connect_timeout": 30,
}

RANDOM_STATE = 42

# ⚠️ Bornes de complexité : sans max_depth, un RandomForest de 200 arbres sur
# ~300k lignes produit un artefact de ~1,8 Go — au-delà de la limite de GitHub
# (100 Mo/fichier) et de la RAM de Streamlit Cloud (~1 Go). La perte de R² est
# marginale. Cf. docs/audit.md §2.1.
# Mesuré : depth=20 / 200 arbres → 99 Mo, R²=0.959 (split aléatoire).
#          depth=14 / 120 arbres → ~20 Mo, R² quasi identique.
# 81 % de l'importance porte sur une seule variable (`quantite_1000t`, dont la
# cible est dérivée) : un modèle profond n'apporte rien, il mémorise.
RF_MAX_DEPTH = 14
RF_MIN_SAMPLES_LEAF = 5
RF_N_ESTIMATORS = 120
JOBLIB_COMPRESS = 3

FEATURES_NUM = ["quantite_1000t", "pib_per_capita", "taux_urbanisation",
                "population", "surface_agricole"]
FEATURES_CAT = ["categorie", "region"]

FEATURES_SOCIO_NUM = ["pib_per_capita", "taux_urbanisation", "population",
                      "surface_agricole"]
FEATURES_SOCIO_CAT = ["region"]

CLUSTER_FEATURES = ["co2_per_capita", "pib_per_capita", "taux_urbanisation",
                    "pct_animal", "surface_agricole"]
CATEGORIES_ANIMALES = ("Meat", "Dairy", "Eggs", "Fish & Seafood")
K_FINAL = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("train")

engine = create_engine(DB_URL, connect_args=CONNECT_ARGS,
                       pool_pre_ping=True, echo=False)
METRICS: dict = {}


def query_df(sql: str) -> pd.DataFrame:
    return pd.read_sql(text(sql), engine)


# ──────────────────────────────────────────────────────────────
# Évaluation
# ──────────────────────────────────────────────────────────────
def evaluate(pipeline, X_tr, y_tr, X_te, y_te) -> dict:
    pipeline.fit(X_tr, y_tr)
    pred = pipeline.predict(X_te)
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_te, pred))),
        "mae": float(mean_absolute_error(y_te, pred)),
        "r2": float(r2_score(y_te, pred)),
        "n_train": int(len(X_tr)),
        "n_test": int(len(X_te)),
    }


def split_random(X, y, groups=None):
    return train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)


def split_grouped(X, y, groups):
    """Split groupé : aucun pays ne se retrouve à la fois en train et en test.

    Sans cela, les lignes d'un même (pays, année) partagent toutes leurs variables
    socio-économiques et deux années consécutives sont quasi identiques : presque
    chaque ligne de test a un jumeau dans le train. Cf. docs/audit.md §4.2.
    """
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=RANDOM_STATE)
    tr, te = next(gss.split(X, y, groups=groups))
    return X.iloc[tr], X.iloc[te], y.iloc[tr], y.iloc[te]


def make_preprocessor(num_cols, cat_cols):
    return ColumnTransformer([
        ("num", StandardScaler(), num_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
    ])


# ──────────────────────────────────────────────────────────────
# A — Calculateur d'empreinte
# ──────────────────────────────────────────────────────────────
def train_calculateur(skip_tuning: bool = False) -> None:
    log.info("=" * 62)
    log.info("MODÈLE A — Calculateur d'empreinte (grain pays × année × produit)")
    log.info("=" * 62)

    df = query_df("""
        SELECT f.quantite_1000t, f.co2_total_kg, pr.categorie, p.region,
               s.pib_per_capita, s.taux_urbanisation, s.population,
               s.surface_agricole, p.code_iso3 AS iso3, t.annee
        FROM fait_impact_pays_annee f
        JOIN dim_pays     p  ON f.pays_id    = p.pays_id
        JOIN dim_temps    t  ON f.annee_id   = t.annee_id
        JOIN dim_produits pr ON f.produit_id = pr.produit_id
        LEFT JOIN dim_socio_economique s
               ON f.pays_id = s.pays_id AND f.annee_id = s.annee_id
        WHERE f.co2_total_kg IS NOT NULL AND f.quantite_1000t > 0
    """)

    feats = FEATURES_NUM + FEATURES_CAT
    df = df.dropna(subset=feats + ["co2_total_kg"]).copy()
    df["log_co2"] = np.log1p(df["co2_total_kg"])
    log.info("Dataset : %s lignes × %d features", f"{len(df):,}", len(feats))

    X, y, groups = df[feats], df["log_co2"], df["iso3"]
    prep = make_preprocessor(FEATURES_NUM, FEATURES_CAT)

    results = {}
    for label, splitter in [("aleatoire", split_random), ("groupe_pays", split_grouped)]:
        X_tr, X_te, y_tr, y_te = splitter(X, y, groups)
        for name, model in [
            ("ridge", Ridge(alpha=1.0)),
            ("random_forest", RandomForestRegressor(
                n_estimators=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH,
                min_samples_leaf=RF_MIN_SAMPLES_LEAF,
                random_state=RANDOM_STATE, n_jobs=-1)),
        ]:
            t0 = time.time()
            pipe = Pipeline([("prep", prep), ("model", model)])
            res = evaluate(pipe, X_tr, y_tr, X_te, y_te)
            res["fit_seconds"] = round(time.time() - t0, 1)
            results[f"{name}__{label}"] = res
            log.info("  %-16s %-12s R²=%.4f  RMSE=%.4f  (%.0fs)",
                     name, label, res["r2"], res["rmse"], res["fit_seconds"])

    # Modèle final : entraîné sur le split aléatoire (l'app s'en sert comme
    # calculateur sur des pays tous vus à l'entraînement).
    X_tr, X_te, y_tr, y_te = split_random(X, y)
    final = Pipeline([("prep", prep), ("model", RandomForestRegressor(
        n_estimators=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH,
        min_samples_leaf=RF_MIN_SAMPLES_LEAF,
        random_state=RANDOM_STATE, n_jobs=-1))])

    if not skip_tuning:
        log.info("Tuning (RandomizedSearchCV, 8 itérations, CV=3)…")
        search = RandomizedSearchCV(
            final,
            {
                "model__n_estimators": [100, 200, 300],
                "model__max_depth": [12, 16, 20, 24],
                "model__min_samples_leaf": [2, 5, 10],
                "model__max_features": [0.5, 0.7, 1.0],
            },
            n_iter=8, cv=3, scoring="r2", random_state=RANDOM_STATE, n_jobs=-1,
        )
        search.fit(X_tr, y_tr)
        final = search.best_estimator_
        log.info("  Meilleurs paramètres : %s", search.best_params_)
    else:
        final.fit(X_tr, y_tr)

    pred = final.predict(X_te)
    tuned = {"r2": float(r2_score(y_te, pred)),
             "rmse": float(np.sqrt(mean_squared_error(y_te, pred)))}
    results["random_forest_tuned__aleatoire"] = tuned
    log.info("  Final : R²=%.4f  RMSE=%.4f", tuned["r2"], tuned["rmse"])

    # Importances (chiffres réels — le README en citait d'inventés)
    model_step = final.named_steps["model"]
    ohe = final.named_steps["prep"].named_transformers_["cat"]
    names = FEATURES_NUM + ohe.get_feature_names_out(FEATURES_CAT).tolist()
    imp = pd.Series(model_step.feature_importances_, index=names).sort_values(ascending=False)
    results["feature_importances_top10"] = {k: round(float(v), 4) for k, v in imp.head(10).items()}
    log.info("  Top 5 importances : %s",
             ", ".join(f"{k}={v:.3f}" for k, v in imp.head(5).items()))

    path = MODELS_DIR / "model_impact.pkl"
    joblib.dump(final, path, compress=JOBLIB_COMPRESS)
    size_mb = path.stat().st_size / 1024**2
    log.info("  Sauvegardé : %s (%.1f Mo)", path.name, size_mb)
    results["artifact_mb"] = round(size_mb, 1)

    # Plage d'entraînement — l'app s'en sert pour avertir en cas d'extrapolation
    results["quantite_1000t_range"] = [
        float(df["quantite_1000t"].min()), float(df["quantite_1000t"].max())
    ]
    METRICS["A_calculateur"] = results


# ──────────────────────────────────────────────────────────────
# B — Vraie tâche prédictive
# ──────────────────────────────────────────────────────────────
def train_predictif() -> None:
    log.info("=" * 62)
    log.info("MODÈLE B — Prédiction CO₂/habitant depuis le socio-économique seul")
    log.info("=" * 62)

    df = query_df(f"""
        SELECT p.code_iso3 AS iso3, p.region, t.annee,
               SUM(f.co2_total_kg) AS co2_total,
               SUM(CASE WHEN pr.categorie IN {CATEGORIES_ANIMALES}
                        THEN f.co2_total_kg ELSE 0 END) AS co2_animal,
               AVG(s.pib_per_capita)    AS pib_per_capita,
               AVG(s.taux_urbanisation) AS taux_urbanisation,
               AVG(s.population)        AS population,
               AVG(s.surface_agricole)  AS surface_agricole
        FROM fait_impact_pays_annee f
        JOIN dim_pays     p  ON f.pays_id    = p.pays_id
        JOIN dim_temps    t  ON f.annee_id   = t.annee_id
        JOIN dim_produits pr ON f.produit_id = pr.produit_id
        LEFT JOIN dim_socio_economique s
               ON f.pays_id = s.pays_id AND f.annee_id = s.annee_id
        WHERE f.co2_total_kg IS NOT NULL
        GROUP BY p.code_iso3, p.region, t.annee
    """)

    df = df[df["population"] > 0].copy()
    df["co2_per_capita"] = df["co2_total"] / df["population"]
    feats = FEATURES_SOCIO_NUM + FEATURES_SOCIO_CAT
    df = df.dropna(subset=feats + ["co2_per_capita"]).copy()
    df["target"] = np.log1p(df["co2_per_capita"])
    log.info("Dataset : %s paires (pays, année) × %d features", f"{len(df):,}", len(feats))

    X, y, groups = df[feats], df["target"], df["iso3"]
    prep = make_preprocessor(FEATURES_SOCIO_NUM, FEATURES_SOCIO_CAT)

    results = {}
    for label, splitter in [("aleatoire", split_random), ("groupe_pays", split_grouped)]:
        X_tr, X_te, y_tr, y_te = splitter(X, y, groups)

        # Baseline naïve : prédire la moyenne du train (cadre la performance).
        baseline_pred = np.full(len(y_te), y_tr.mean())
        results[f"baseline_moyenne__{label}"] = {
            "r2": float(r2_score(y_te, baseline_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_te, baseline_pred))),
        }

        for name, model in [
            ("ridge", Ridge(alpha=1.0)),
            ("random_forest", RandomForestRegressor(
                n_estimators=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH,
                min_samples_leaf=RF_MIN_SAMPLES_LEAF,
                random_state=RANDOM_STATE, n_jobs=-1)),
        ]:
            pipe = Pipeline([("prep", prep), ("model", model)])
            res = evaluate(pipe, X_tr, y_tr, X_te, y_te)
            results[f"{name}__{label}"] = res
            log.info("  %-16s %-12s R²=%.4f  RMSE=%.4f",
                     name, label, res["r2"], res["rmse"])
        log.info("  %-16s %-12s R²=%.4f  (référence)", "baseline_moyenne", label,
                 results[f"baseline_moyenne__{label}"]["r2"])

    X_tr, X_te, y_tr, y_te = split_grouped(X, y, groups)
    final = Pipeline([("prep", prep), ("model", RandomForestRegressor(
        n_estimators=RF_N_ESTIMATORS, max_depth=RF_MAX_DEPTH,
        min_samples_leaf=RF_MIN_SAMPLES_LEAF,
        random_state=RANDOM_STATE, n_jobs=-1))])
    final.fit(X_tr, y_tr)

    path = MODELS_DIR / "model_co2_per_capita.pkl"
    joblib.dump(final, path, compress=JOBLIB_COMPRESS)
    log.info("  Sauvegardé : %s (%.1f Mo)", path.name, path.stat().st_size / 1024**2)
    METRICS["B_predictif"] = results


# ──────────────────────────────────────────────────────────────
# C — Clustering
# ──────────────────────────────────────────────────────────────
def _nommer_clusters(profils: pd.DataFrame) -> dict:
    """Attribue un libellé métier à chaque cluster à partir de son profil moyen.

    Règle explicite, appliquée dans l'ordre — le premier cluster non encore
    nommé qui satisfait un critère prend le libellé :

      1. « Pays riches »            → PIB/hab. le plus élevé
      2. « Faible revenu »          → PIB/hab. le plus faible
      3. « Producteurs intensifs »  → plus grande surface agricole parmi le reste
      4. « Émergents urbains »      → plus urbanisé parmi le reste
      5. « Développement agricole » → le dernier

    Les libellés restent donc stables en signification même si les indices
    numériques changent d'un entraînement à l'autre.
    """
    restants = list(profils.index)
    labels: dict = {}

    def prendre(colonne: str, nom: str, maximum: bool = True) -> None:
        if not restants:
            return
        sub = profils.loc[restants, colonne]
        cid = int(sub.idxmax() if maximum else sub.idxmin())
        labels[cid] = nom
        restants.remove(cid)

    prendre("pib_per_capita", "Pays riches", maximum=True)
    prendre("pib_per_capita", "Faible revenu", maximum=False)
    prendre("surface_agricole", "Producteurs intensifs", maximum=True)
    prendre("taux_urbanisation", "Émergents urbains", maximum=True)
    for cid in restants:
        labels[int(cid)] = "Développement agricole"
    return labels


def train_clustering() -> None:
    log.info("=" * 62)
    log.info("MODÈLE C — Clustering des profils pays (KMeans)")
    log.info("=" * 62)

    df = query_df(f"""
        SELECT p.code_iso3 AS iso3, p.nom_pays, p.region, t.annee,
               SUM(f.co2_total_kg) AS co2_total,
               SUM(CASE WHEN pr.categorie IN {CATEGORIES_ANIMALES}
                        THEN f.co2_total_kg ELSE 0 END) AS co2_animal,
               AVG(s.pib_per_capita)    AS pib_per_capita,
               AVG(s.taux_urbanisation) AS taux_urbanisation,
               AVG(s.population)        AS population,
               AVG(s.surface_agricole)  AS surface_agricole
        FROM fait_impact_pays_annee f
        JOIN dim_pays     p  ON f.pays_id    = p.pays_id
        JOIN dim_temps    t  ON f.annee_id   = t.annee_id
        JOIN dim_produits pr ON f.produit_id = pr.produit_id
        LEFT JOIN dim_socio_economique s
               ON f.pays_id = s.pays_id AND f.annee_id = s.annee_id
        WHERE f.co2_total_kg IS NOT NULL
        GROUP BY p.code_iso3, p.nom_pays, p.region, t.annee
    """)

    df = df[df["population"] > 0].copy()
    df["co2_per_capita"] = df["co2_total"] / df["population"]
    df["pct_animal"] = df["co2_animal"] / (df["co2_total"] + 1e-10) * 100
    df = df.dropna(subset=CLUSTER_FEATURES).copy()
    log.info("Dataset : %s paires (pays, année)", f"{len(df):,}")

    # ⚠️ Le scaler est ajusté ICI, sur l'ensemble des paires, puis SAUVEGARDÉ.
    # L'application doit appeler `transform` avec ce scaler, jamais en refitter
    # un nouveau — sinon les centroïdes ne sont plus dans le même espace et les
    # clusters changent d'une année à l'autre. Cf. docs/audit.md §2.2.
    scaler = StandardScaler().fit(df[CLUSTER_FEATURES])
    X = scaler.transform(df[CLUSTER_FEATURES])

    inerties, silhouettes = {}, {}
    for k in range(2, 9):
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10).fit(X)
        inerties[k] = float(km.inertia_)
        sample = min(10_000, len(X))
        idx = np.random.RandomState(RANDOM_STATE).choice(len(X), sample, replace=False)
        silhouettes[k] = float(silhouette_score(X[idx], km.labels_[idx]))
        log.info("  k=%d  inertie=%.0f  silhouette=%.3f", k, inerties[k], silhouettes[k])

    km_final = KMeans(n_clusters=K_FINAL, random_state=RANDOM_STATE, n_init=10).fit(X)
    labels = km_final.labels_
    sample = min(10_000, len(X))
    idx = np.random.RandomState(RANDOM_STATE).choice(len(X), sample, replace=False)
    sil = float(silhouette_score(X[idx], labels[idx]))
    log.info("  Retenu : k=%d, silhouette=%.3f", K_FINAL, sil)

    # Profils moyens — servent à nommer les clusters dans l'app
    df["cluster"] = labels
    profils = df.groupby("cluster")[CLUSTER_FEATURES].mean().round(2)
    log.info("\n%s", profils.to_string())

    # Les indices de cluster produits par KMeans sont ARBITRAIRES et changent
    # d'un entraînement à l'autre. Coder les libellés en dur dans l'application
    # les désynchronise silencieusement au premier réentraînement. On les dérive
    # donc ici, depuis les profils, et on les embarque dans l'artefact.
    labels = _nommer_clusters(profils)
    for cid, nom in sorted(labels.items()):
        log.info("  cluster %d → %s", cid, nom)

    bundle = {
        "scaler": scaler,
        "kmeans": km_final,
        "features": CLUSTER_FEATURES,
        "k": K_FINAL,
        "silhouette": sil,
        "labels": labels,
        "profils": json.loads(profils.to_json(orient="index")),
    }
    path = MODELS_DIR / "model_clustering.pkl"
    joblib.dump(bundle, path, compress=JOBLIB_COMPRESS)
    log.info("  Sauvegardé : %s (%.2f Mo) — format {scaler, kmeans, features}",
             path.name, path.stat().st_size / 1024**2)

    METRICS["C_clustering"] = {
        "k_retenu": K_FINAL,
        "silhouette": round(sil, 4),
        "silhouettes_par_k": {str(k): round(v, 4) for k, v in silhouettes.items()},
        "inerties_par_k": {str(k): round(v, 1) for k, v in inerties.items()},
        "profils_moyens": json.loads(profils.to_json(orient="index")),
        "n_observations": int(len(df)),
    }


# ──────────────────────────────────────────────────────────────
# MLFlow + export
# ──────────────────────────────────────────────────────────────
def log_to_mlflow() -> None:
    """Journalise les métriques et exporte un CSV versionnable.

    `mlruns/` pèse plusieurs Go et est exclu de git : sans cet export, aucune
    trace du suivi d'expériences n'est visible dans le dépôt, alors que
    l'énoncé exige de montrer les résultats dans un outil de monitoring.
    Cf. docs/audit.md §3.3.
    """
    try:
        import mlflow
    except ImportError:
        log.warning("mlflow absent — journalisation ignorée")
        return

    mlflow.set_tracking_uri(f"file:{(BASE_DIR / 'mlruns').as_posix()}")
    mlflow.set_experiment("food_impact")

    for task, results in METRICS.items():
        for run_name, res in results.items():
            if not isinstance(res, dict) or "r2" not in res:
                continue
            with mlflow.start_run(run_name=f"{task}__{run_name}"):
                mlflow.set_tags({"tache": task, "protocole": run_name})
                mlflow.log_metrics({k: v for k, v in res.items()
                                    if isinstance(v, (int, float))})

    try:
        runs = mlflow.search_runs(experiment_names=["food_impact"])
        out = DOCS_DIR / "mlflow_runs.csv"
        runs.to_csv(out, index=False)
        log.info("Runs MLFlow exportés → %s (%d runs)", out.name, len(runs))
    except Exception as exc:  # noqa: BLE001
        log.warning("Export MLFlow impossible : %s", exc)


def export_metrics() -> None:
    out = DOCS_DIR / "metrics.json"
    out.write_text(json.dumps(METRICS, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Métriques exportées → docs/%s", out.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--only", choices=["calculateur", "predictif", "clustering"],
                        help="n'entraîner qu'un seul modèle")
    parser.add_argument("--skip-tuning", action="store_true",
                        help="sauter RandomizedSearchCV (beaucoup plus rapide)")
    args = parser.parse_args()

    try:
        with engine.connect() as con:
            con.execute(text("SELECT 1 FROM fait_impact_pays_annee LIMIT 1"))
    except Exception as exc:  # noqa: BLE001
        log.error("Data warehouse inaccessible : %s", exc)
        log.error("→ python scripts/etl_pipeline.py")
        return 1

    t0 = time.time()
    if args.only in (None, "calculateur"):
        train_calculateur(skip_tuning=args.skip_tuning)
    if args.only in (None, "predictif"):
        train_predictif()
    if args.only in (None, "clustering"):
        train_clustering()

    log_to_mlflow()
    export_metrics()
    log.info("Terminé en %.0f s", time.time() - t0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
