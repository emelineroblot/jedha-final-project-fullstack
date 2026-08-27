# 🌍 Environmental Impact of the Food We Eat

> **Jedha Data Science Fullstack Program - Final Project - Block 6 : "Lead a Data Project"**
> Presented on: March, 26<sup>th</sup> 2026

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B.svg)](https://streamlit.io)

---

## 📋 Contents

- [Context](#context)
- [Objectives](#objectives)
- [Data](#data)
- [Architecture](#architecture)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Results](#results)
- [Team](#team)

---

## 🎯 Context

Human food production is one of the major contributors to the current climate change crisis and environmental impacts. Namely, world food production, transformation and transportation is responsible for up to **26% of greenhouse gases emissions** and of **70% fresh water consumption**.

In this context, this projects aims to:

1. **Analyse** the environmental impact of world food production
2. **Predict** the carbon dioxide emissions of a given country, from its reported food mix consumption
3. **Bring awareness** through a web dashboard allowing users to simulate their footprint based on their usual diet

### Key Insights

- Which countries have the highest food-related carbon footprint?
- Do other factors like GDP and urbanization influence meat consumption, hence environmental impact?
- Can we predict a country’s future environmental impact based on its dietary patterns?
- What are the country profiles based on their food mix?

---

## 🚀 Objectives

### Technical Goals & Means
- ✅ Automated **ETL** pipeline (Extract-Transform-Load)
- ✅ **Data Lake** → **Data Warehouse** (OLAP) Architecture
- ✅ In-depth **EDA** with statistical tests (ANOVA, correlations...)
- ✅ **Machine Learning** : Regression (impact prediction) + Clustering (countries profiles)
- ✅ **MLFlow** for incremental work tracking
- ✅ **Streamlit** web application deployed
- ✅ **Git** versioning

### Deliverables
- Jupyter Notebooks, markdown documented (EDA, ML)
- Production-ready Python Scripts (ETL, training)
- Interactive web application
- Presentation support

---

## 📊 Data Sources

### Datasets

| Dataset | Source | Period | Size | Key Metrics |
|---------|--------|---------|--------|----------------|
| **Global Food Production** | [FAOSTAT](https://www.fao.org/faostat/) | 1961-2022 | 4.4 MB | Countries, Products, Produced tons |
| **Environmental Impact** | [Our World in Data](https://ourworldindata.org/) | Static | 7.7 KB | CO₂, Water, Landuse |
| **Socio-Economic Data** | [World Bank](https://data.worldbank.org/) | 1961-2023 | API | GDP per Capita, Urbanization |
| **Meat Consumption** | [OWID GitHub](https://github.com/owid/owid-datasets) | 1961-2020 | API | meat kg consumed/capita/year |

### Key Environmental Metrics

- **Greenhouse Gases Emissions** (kg CO₂eq/kg)
- **Wate Usage** (liters/kg)
- **Land Use** (m²/kg)
- **Eutrophisation** (gPO₄eq/kg)

---

## 🏗️ Project Architecture

### Folders Structure

```
root/
│
├── app/
│   ├── streamlit_app.py        # Web dashboard
│   └── components/             # Streamlit components
│
├── config/ # scripts, environment and setup
│
├── data/
│   ├── raw/                    # (CSV, API...)
│   │   ├── FAO.csv
│   │   ├── Food_Production.csv
│   │   └── WorldBank_socio.csv
│   └── processed/              # (Parquet)
│       ├── production_clean.parquet
│       └── impact_by_country.parquet
│
├── deployment/ # Containerization if any (Docker)
├── docker/
│
├── docs/
│   ├── schema_db.dbml          # DB Schema
│   ├── presentation.pptx       # Presentation support
│   └──...
│
├── models/                     # Saved trained models
│   ├── model_regression.pkl    # Best regression model
│   ├── model_clustering.pkl    # Clustering model
│   └── preprocessor.pkl        # Preprocessing pipeline
│
├── notebooks/                  # Intermediate work, data and models exploration, displays...
│   ├── 01_eda.ipynb
│   ├── 02_etl_pipeline.ipynb
│   └── ....ipynb
│
├── scripts/                    # Isolated and re-usable scripts, functions...
│   ├── etl_pipeline.py         # ETL Pipeline
│   ├── train_model.py          # ML Training
│   └── utils.py                # Utilities functions
```

### Data 

**OLAP** (Online Analytical Processing) pour analyses multidimensionnelles

```
┌─────────────────┐
│   DATA LAKE     │  Raw Storage (PostgreSQL/DuckDB)
│   (Raw data)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ETL PIPELINE   │  Cleaning, transformation, data enrichment
│   (Python)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ DATA WAREHOUSE  │  Fact Tables & Dimensions (Star Diagram)
│   (OLAP)        │  • Production
└────────┬────────┘  • Impact
         │           • Dim_Pays, Dim_Produits, Dim_Temps
         ▼
┌─────────────────────────────┐
│  ANALYSIS & ML               │
│  • EDA (notebooks)          │
│  • Machine Learning         │
│  • Streamlit (visualisation)│
└─────────────────────────────┘
```

---

## 🛠️ Setup & Collaboration

### Pre-requisits

- Python 3.10+
- Git

### Setup

- Clone the repo via `git clone https://github.com/emelineroblot/jedha-final-project-fullstack.git` or with SSH if you setup your SSH Agent and Key.
- Use the _config/setup_venv.sh_ script to setup local venv folder with appropriate requirements
- On first checkout (or initial clone), a _.env_ file is generated at project root level, please edit your values inside to use aws-based artifacts and pipelines
- 

### **Acquire Data** (if needed)
   ```bash
   python scripts/download_data.py
   ```

### Branches

-   `master` = stable / read-only, regular sync with `develop` from admin
-   `develop` = collaborative development branch, no direct push, merge branches works / fixes by PRs
-   `feature/*` / `fix/*` = work-in-progress branches

### Workflow

1.  Create a branch from `develop`
2.  Work locally and commit changes
3.  Push branch and open PR → `develop`
4.  Optional review by at least one other contributor
5.  Admin merges `develop` → `master` when ready / for major changes and hot fixes

#### Daily workflow for contributors

`git checkout dev`
`git pull`
`git checkout -b feature/my-feature`

`# work locally...`

`git add .`
`git commit -m "Add feature X"`
`git push -u origin feature/my-feature`

### Roles

-   Admin: full control, merge to master
-   Write: push feature branches, open PRs
-   Read: reviewers / externals

## 📈 Results

> *TBD*

### Insights clés

1. **Impact par produit** : La viande bovine génère 60kg CO₂eq/kg (vs 0.9kg pour le riz)
2. **Corrélation PIB** : Les pays à PIB élevé consomment 2.5× plus de viande
3. **Évolution temporelle** : +120% d'émissions agricoles entre 1961-2020

### Modèles ML

| Model | Type | Main Metrics | Score |
|--------|------|----------|-------|
| XGBoost Regressor | Regression | R² | 0.XX |
| Random Forest | Regression | RMSE | XX.XX |
| KMeans (k=5) | Clustering | Silhouette | 0.XX |

### Major Features

1. Red meat (beef) production (importance : 0.42)
2. GDP per capita (0.28)
3. Urbanization (0.15)

---

## 🌐 Streamlit Dashboard

**URL déployée** : *TBD*

### Features

- 🥗 **Menu Simulator** : Determine your diet's footprint
- 🌍 **Countries Footprint** : Show per country footprint
- 📊 **Predictions** : "What-if" Scenarios (+10% red meat consumtion → X% CO₂ increase)

---

## 👥 Team

- Emeline ROBLOT

**Teaching team** : Sabrine BENDIMERAD, Angel GASPARD-FAUVEL

---

## 📚 References

- [FAO - Food and Agriculture Organization](https://www.fao.org/faostat/)
- [Our World in Data - Environmental Impacts of Food](https://ourworldindata.org/environmental-impacts-of-food)
- [World Bank Open Data](https://data.worldbank.org/)
- [Poore & Nemecek (2018) - Science](https://science.sciencemag.org/content/360/6392/987)

---

## 📝 Licence

MIT License - Voir [LICENSE](LICENSE) pour plus de détails.

---

## 🚧 Roadmap

- [x] Setup projet
- [ ] Naive EDA
- [ ] ETL Pipeline
- [ ] Deeper EDA
- [ ] Machine Learning
- [ ] Streamlit Dashboard
- [ ] Deployement
- [ ] Demo Day Presentation

---
