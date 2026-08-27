# 🤖 Modèles entraînés

Artefacts produits par `python scripts/train_model.py`.
**Non versionnés** (`.gitignore`) — régénérables en ~3 min depuis l'entrepôt.

## Fichiers

| Fichier | Contenu | Taille |
|---|---|---|
| `model_impact.pkl` | Pipeline sklearn complet (préprocesseur + RandomForest) — calculateur d'empreinte | ~20 Mo |
| `model_co2_per_capita.pkl` | Pipeline sklearn — prédiction CO₂/hab. depuis le socio-économique | ~6 Mo |
| `model_clustering.pkl` | Dict `{scaler, kmeans, features, labels, profils, k, silhouette}` | ~10 Ko |

## Deux règles à ne pas enfreindre

**1. Le clustering se charge avec son scaler.**
```python
bundle = joblib.load("models/model_clustering.pkl")
X = bundle["scaler"].transform(df[bundle["features"]])   # transform, JAMAIS fit_transform
clusters = bundle["kmeans"].predict(X)
```
Les centroïdes KMeans vivent dans l'espace normalisé à l'entraînement.
Réajuster un scaler sur un sous-ensemble déplace cet espace : les clusters
deviennent incohérents d'une année à l'autre, sans aucune erreur levée.

**2. La complexité des forêts est bornée volontairement.**
`max_depth=14`, `n_estimators=120`, `compress=3`. Sans ces bornes, l'artefact
atteignait **1,8 Go** — au-delà de la limite GitHub (100 Mo/fichier) et de la
RAM de Streamlit Cloud (~1 Go). Le gain de R² d'un modèle non borné est
négligeable : 81 % de l'importance porte sur une seule variable.

## Régénération

```bash
python scripts/train_model.py --skip-tuning   # rapide
python scripts/train_model.py                 # avec RandomizedSearchCV
python scripts/train_model.py --only clustering
```

Métriques exportées dans `docs/metrics.json` et `docs/mlflow_runs.csv`.
