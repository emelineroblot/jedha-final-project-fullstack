# 🌍 Score d'Impact Environnemental de l'Assiette Mondiale

> **Jedha — Data Science Fullstack · Projet final, Bloc 6 « Lead a Data Project »**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Nourrir huit milliards d'êtres humains représente **26 % des émissions mondiales
de gaz à effet de serre** et **70 % des prélèvements d'eau douce**. Les données
pour l'analyser existent — dispersées entre trois institutions aux nomenclatures
incompatibles.

Ce projet les réconcilie : **60 ans, 172 pays, 121 produits alimentaires**, dans
un entrepôt unique de **973 227 lignes**, exposé par une application web.

---

## Sommaire

- [Résultats](#résultats)
- [Ce que le projet fait](#ce-que-le-projet-fait)
- [Données](#données)
- [Architecture](#architecture)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Modèles](#modèles)
- [Limites connues](#limites-connues)
- [Documentation](#documentation)
- [Équipe](#équipe)

---

## Résultats

### Ce que les données montrent

| Constat | Mesure | Test |
|---|---|---|
| **L'urbanisation multiplie la consommation de viande par ~6** | 26,5 kg/hab. (rural) → 150,5 kg/hab. (urbain) | Kruskal-Wallis H=4387, p≈0 |
| **La richesse change la structure du régime, pas seulement le volume** | Part animale : 15,3 % (Q1 de PIB) → 46,3 % (Q4) | Kruskal-Wallis H=3163, p≈0 |
| **Écart régional du simple au double** | Océanie 3 703 · Europe 3 401 · Afrique 2 248 · Asie 1 785 kg CO₂/hab. | 2000–2023 |
| **PIB et empreinte par habitant : lien réel mais modéré** | ρ = 0,304 | Spearman |

### Performance des modèles

Chaque régression est évaluée **deux fois** : split aléatoire, et split **groupé
par pays** (aucun pays des deux côtés). L'écart mesure la fuite d'information.

| Modèle | Tâche | R² (aléatoire) | R² (groupé par pays) |
|---|---|---|---|
| **A — Calculateur** · RandomForest | `co2_total_kg` ~ quantité + catégorie + socio-éco | 0,945 | 0,896 |
| A — Ridge (référence) | idem | 0,296 | 0,213 |
| **B — Prédictif** · RandomForest | `co2_per_capita` ~ **socio-économique seul** | 0,945 | **0,729** |
| B — Ridge | idem | 0,634 | 0,637 |
| B — Baseline (moyenne) | idem | −0,000 | −0,006 |
| **C — Clustering** · KMeans k=5 | Profils de pays | Silhouette = 0,254 | — |

> ⚠️ **Le R² du modèle A ne mesure pas un pouvoir prédictif.** Sa cible est
> construite par `co2_total_kg = quantité × facteur(produit)`, et la quantité lui
> est fournie en entrée : il reconstitue une multiplication. C'est visible dans
> les importances — **`quantite_1000t` en porte 82,7 %**, la deuxième variable
> n'en portant que 5,7 %. Le **modèle B** est la vraie démonstration prédictive :
> il n'utilise aucune variable entrant dans la construction de la cible, et bat
> largement la baseline (**0,729 contre −0,006**) même sur un split où aucun pays
> de test n'a été vu à l'entraînement.
> Détail dans l'onglet *Méthodologie* de l'application.

L'écart entre les deux colonnes est lui-même un résultat : sur le modèle B, le
R² passe de 0,945 à 0,729 dès qu'on interdit à un même pays d'apparaître des
deux côtés du split. Un protocole aléatoire seul aurait surestimé la performance
de 30 %.

Métriques complètes reproductibles : [`docs/metrics.json`](docs/metrics.json) ·
runs MLFlow : [`docs/mlflow_runs.csv`](docs/mlflow_runs.csv).

---

## Ce que le projet fait

1. **Consolide** 4 sources publiques hétérogènes en un entrepôt en étoile
   (appariement de 172 pays sur ISO3, de 121 produits FAO sur 43 références).
2. **Analyse** les déterminants de l'empreinte par des tests statistiques.
3. **Modélise** l'empreinte par habitant et regroupe les pays en profils.
4. **Expose** le tout dans une application manipulable par un non-technicien.

### L'application — 4 pages

| Page | Contenu |
|---|---|
| 🗺️ **Explorer les pays** | Carte choroplèthe (5 métriques ou profils de clusters), chronologie 1961–2023, position du pays dans la distribution mondiale |
| 🍽️ **Simulateur Menu** | Empreinte d'un régime alimentaire, comparaison pays/région/monde, delta avant/après |
| 📈 **Prédiction Scénarios** | Effet d'une variation de production sur l'empreinte, courbe de sensibilité, alerte d'extrapolation |
| 📐 **Méthodologie & limites** | Sources, chaîne de calcul, statut de chaque modèle, limites assumées |

---

## Données

| Source | Contenu | Période | Volume | Licence |
|---|---|---|---|---|
| [FAOSTAT](https://www.fao.org/faostat/) | Bilans alimentaires (Food + Feed) | 1961–2023 | 1 216 786 lignes | CC BY-NC-SA 3.0 IGO |
| [Our World in Data](https://ourworldindata.org/environmental-impacts-of-food) — Poore & Nemecek (2018) | Facteurs CO₂ / eau / sol par kg | Statique | 43 produits | CC BY 4.0 |
| [World Bank](https://data.worldbank.org/) | PIB/hab., urbanisation, population, surface agricole | 1961–2023 | 10 269 lignes | CC BY 4.0 |
| [OWID](https://ourworldindata.org/meat-production) | Consommation de viande par habitant | 1961–2020 | 10 949 lignes | CC BY 4.0 |

⚠️ **La licence FAOSTAT est non commerciale.** Toute valorisation payante
supposerait de lever ce point. Cf. [`docs/rgpd.md`](docs/rgpd.md) §4.

**Aucune donnée personnelle n'est traitée** — tout est agrégé au niveau
pays × année. Cf. [`docs/rgpd.md`](docs/rgpd.md).

---

## Architecture

```
CSV / API  ─→  Data Lake (raw)  ─→  ETL Python  ─→  Data Warehouse (public)  ─→  ML  ─→  Streamlit
               5 tables brutes       idempotent      étoile, 7 tables
```

### Entrepôt en étoile — schéma `public`

| Table | Lignes | Rôle |
|---|---|---|
| `dim_pays` | 172 | Pays, codes ISO2/ISO3, région |
| `dim_temps` | 63 | 1961–2023, décennie, période |
| `dim_produits` | 121 | Produits FAO, catégorie, appariement Food_Production |
| `dim_socio_economique` | 10 269 | PIB/hab., urbanisation, population, surface agricole |
| `fait_production` | 1 204 119 | Quantités FAO (Food + Feed), en milliers de tonnes |
| `fait_impact` | 47 | Facteurs CO₂ / eau / sol par kg de produit |
| `fait_impact_pays_annee` | **973 227** | Table principale : production × facteurs |

Schéma détaillé : [`docs/schema_db.dbml`](docs/schema_db.dbml) (visualisable sur
[dbdiagram.io](https://dbdiagram.io/)).

### Arborescence

```
.
├── app/
│   └── streamlit_app.py          # Application, 4 pages
├── config/
│   ├── setup_venv.sh             # Installation de l'environnement
│   └── requirements.txt          # → délègue à ../requirements.txt
├── data/raw/                     # CSV sources (non versionnés)
├── deployment/
│   └── Dockerfile                # Image de l'application
├── docker/
│   └── docker-compose.yml        # PostgreSQL 16 local
├── docs/
│   ├── schema_db.dbml            # Schéma de l'entrepôt
│   ├── rgpd.md                   # Conformité RGPD & licences
│   ├── gestion_projet.md         # Objectifs, planning, budget
│   ├── impact.md                 # Valeur métier & pitch
│   ├── metrics.json              # Métriques mesurées
│   └── mlflow_runs.csv           # Export du suivi d'expériences
├── models/                       # Artefacts entraînés (non versionnés)
├── notebooks/
│   ├── 01_exploration_naive.ipynb
│   ├── 01b_enrichissement_faostat.ipynb
│   ├── 01c_enrichissement_worldbank.ipynb
│   ├── 01d_enrichissement_owid.ipynb
│   ├── 02_etl_pipeline.ipynb     # Exploration de l'ETL
│   ├── 03_eda.ipynb              # Analyse exploratoire
│   └── 04_machine_learning.ipynb # Exploration de la modélisation
├── scripts/
│   ├── etl_pipeline.py           # ETL industrialisé, rejouable
│   ├── train_model.py            # Entraînement des 3 modèles
│   ├── _mappings.py              # Tables de correspondance FAO ↔ ISO3
│   └── aws.py               # Configuration S3 + PostgreSQL AWS
└── tests/
    └── test_app_constants.py     # 25 tests de non-régression
```

> Les notebooks documentent la **démarche exploratoire**. Les scripts de
> `scripts/` en sont la version industrialisée : ce sont eux qui font foi.

---

## Installation

### Prérequis

- Python 3.11+
- Docker (pour PostgreSQL en local)

### Mise en route

```bash
git clone https://github.com/emelineroblot/jedha-final-project-fullstack.git
cd jedha-final-project-fullstack

# 1. Environnement virtuel + dépendances
bash config/setup_venv.sh
source .venv/bin/activate          # .venv/Scripts/activate sous Windows

# 2. Credentials
cp docker/.env.example .env        # valeurs par défaut fonctionnelles en local

# 3. Base de données
docker compose -f docker/docker-compose.yml up -d

# 4. Construction de l'entrepôt (~5 min)
python scripts/etl_pipeline.py

# 5. Entraînement des modèles (~3 min)
python scripts/train_model.py --skip-tuning

# 6. Lancement
streamlit run app/streamlit_app.py
```

L'application est servie sur <http://localhost:8501>.

> Les CSV sources doivent être présents dans `data/raw/`. Ils sont exclus du
> dépôt (94 Mo pour le seul export FAOSTAT) et régénérables via les notebooks
> `01b`, `01c` et `01d`.

### Docker

```bash
docker build -f deployment/Dockerfile -t food-impact-app .
docker run --rm -p 8501:8501 --env-file .env food-impact-app
```

---

## Utilisation

```bash
# ETL — idempotent, rejouable sans risque de doublon
python scripts/etl_pipeline.py                  # pipeline complet
python scripts/etl_pipeline.py --steps facts    # faits uniquement
python scripts/etl_pipeline.py --validate-only  # contrôles seuls

# Entraînement
python scripts/train_model.py                   # avec optimisation
python scripts/train_model.py --skip-tuning     # rapide
python scripts/train_model.py --only clustering

# Qualité
pytest -q
ruff check app scripts tests

# Suivi d'expériences
mlflow ui                                       # → http://localhost:5000
```

### Migration vers AWS

Modifier les variables `POSTGRES_*` de `.env`. **Aucun changement de code** :
la chaîne de connexion est entièrement dérivée de l'environnement.

---

## Modèles

| Artefact | Modèle | Taille | Rôle |
|---|---|---|---|
| `model_impact.pkl` | RandomForest (120 arbres, profondeur 14) | 23,5 Mo | Calculateur de scénarios |
| `model_co2_per_capita.pkl` | RandomForest | 3,1 Mo | Prédiction de l'empreinte/hab. |
| `model_clustering.pkl` | `{scaler, kmeans, labels, profils}` | 10 Ko | Profils de pays |

> **Le clustering est sauvegardé avec son scaler.** Sans lui, les prédictions ne
> sont pas reproductibles : les centroïdes vivent dans l'espace normalisé à
> l'entraînement. Les libellés de profils sont dérivés des profils moyens et
> embarqués dans l'artefact, les indices KMeans étant arbitraires.

### Profils de pays identifiés (k=5)

| Profil | CO₂/hab. | PIB/hab. | Urbanisation | Part animale | Surface agricole |
|---|---|---|---|---|---|
| Faible revenu | 356 kg | 686 $ | 29 % | 34 % | 41 % |
| Développement agricole | 464 kg | 1 244 $ | 37 % | 62 % | 37 % |
| Émergents urbains | 949 kg | 8 604 $ | 68 % | 69 % | 17 % |
| Producteurs intensifs | 1 154 kg | 7 986 $ | 68 % | 69 % | 60 % |
| Pays riches | 1 381 kg | 47 904 $ | 82 % | 71 % | 29 % |

> Les **indices** de cluster changent à chaque entraînement (KMeans les attribue
> arbitrairement) ; les **libellés** sont dérivés des profils moyens par une règle
> explicite et embarqués dans l'artefact. C'est ce qui garantit qu'un pays ne
> change pas de profil sans raison entre deux exécutions.

---

## Limites connues

À énoncer avant qu'on les découvre.

1. **Production ≠ consommation.** Les données FAO mesurent ce qu'un pays produit
   et rend disponible — exportations, alimentation animale et pertes incluses.
   Un pays exportateur agricole paraît plus émetteur qu'il ne l'est pour ses
   habitants.
2. **Facteurs d'émission moyens et statiques.** Un kg de bœuf reçoit le même
   facteur au Brésil et en Irlande, sur toute la période.
3. **Couverture partielle.** 47 produits FAO sur 121 sont appariés à un facteur.
   L'empreinte calculée est une **borne basse**.
4. **Le modèle A ne prédit pas, il reconstitue.** Cf. [Résultats](#résultats).
5. **Pas d'extrapolation.** Un RandomForest interrogé hors de sa plage
   d'entraînement renvoie une constante — l'application le signale.
6. **Corrélation, pas causalité.**

---

## Documentation

| Document | Contenu |
|---|---|
| [`docs/gestion_projet.md`](docs/gestion_projet.md) | Objectifs, planning, budget, risques |
| [`docs/rgpd.md`](docs/rgpd.md) | Conformité RGPD, licences, sécurité |
| [`docs/impact.md`](docs/impact.md) | Valeur métier, utilisateurs cibles, valorisation |
| [`docs/schema_db.dbml`](docs/schema_db.dbml) | Schéma de l'entrepôt |
| [`docs/metrics.json`](docs/metrics.json) | Métriques mesurées, reproductibles |

---

## Équipe

- **Emeline ROBLOT** — Data engineering & MLOps
- **Emeline ROBLOT** — Analyse & modélisation
- **Emeline ROBLOT** — Infrastructure & coordination

Encadrement : Sabrine BENDIMERAD, Angel GASPARD-FAUVEL

---

## Références

- Poore, J. & Nemecek, T. (2018). *Reducing food's environmental impacts through
  producers and consumers*. **Science**, 360(6392), 987-992.
  [DOI](https://doi.org/10.1126/science.aaq0216)
- [FAOSTAT — Food Balance Sheets](https://www.fao.org/faostat/)
- [Our World in Data — Environmental impacts of food](https://ourworldindata.org/environmental-impacts-of-food)
- [World Bank Open Data](https://data.worldbank.org/)

---

## Licence

[MIT](LICENSE) pour le code. Les données restent soumises aux licences de leurs
sources respectives (cf. [Données](#données)).
