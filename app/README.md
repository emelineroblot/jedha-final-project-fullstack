# 🌐 Application Streamlit

```bash
streamlit run app/streamlit_app.py      # → http://localhost:8501
```

## Prérequis

| Dépendance | Sans elle |
|---|---|
| PostgreSQL peuplé (`scripts/etl_pipeline.py`) | Pages 1 et 3 désactivées ; page 2 sans comparaison |
| `models/model_impact.pkl` | Page 3 désactivée |
| `models/model_clustering.pkl` | Bascule « Clusters » désactivée |

L'application **ne plante jamais** en cas d'artefact manquant : elle dégrade la
fonctionnalité concernée et l'annonce.

## Pages

| Page | Contenu |
|---|---|
| 🗺️ Explorer les pays | Carte choroplèthe (5 métriques ou profils), chronologie 1961–2023, position dans la distribution mondiale |
| 🍽️ Simulateur Menu | Empreinte d'un régime, comparaison pays/région/monde, delta avant/après |
| 📈 Prédiction Scénarios | Variation de production → empreinte, courbe de sensibilité, alerte d'extrapolation |
| 📐 Méthodologie & limites | Sources, chaîne de calcul, statut des modèles, limites |

## Points de vigilance

- **Unités.** `co2_total_kg` est en **kilogrammes**. Toujours passer par
  `fmt_co2()` / `kg_to_mt()` — jamais de division en dur. 1 Mt = 1e9 kg.
- **SQL.** Paramètres liés uniquement (`:iso3`), jamais de f-string.
- **Grain.** `fait_impact_pays_annee` est au grain (pays, année, produit) :
  agréger la population avec `AVG` après jointure, ou la calculer à part.
- **Catégories.** `FOOD_CATEGORY` doit correspondre à `dim_produits.categorie`.
  Verrouillé par `tests/test_app_constants.py`.

## Déploiement

```bash
docker build -f deployment/Dockerfile -t food-impact-app .
docker run --rm -p 8501:8501 --env-file .env food-impact-app
```

Streamlit Community Cloud : connecter le dépôt, pointer sur
`app/streamlit_app.py`, renseigner les `POSTGRES_*` dans les Secrets.
