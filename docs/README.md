# 📚 Documentation

| Fichier | Contenu |
|---|---|
| `gestion_projet.md` | Objectifs, planning, budget, risques, suites |
| `rgpd.md` | Conformité RGPD, licences des sources, sécurité |
| `impact.md` | Valeur métier, utilisateurs cibles, valorisation |
| `schema_db.dbml` | Schéma de l'entrepôt — visualisable sur [dbdiagram.io](https://dbdiagram.io/) |
| `metrics.json` | Métriques des 3 modèles, générées par `scripts/train_model.py` |
| `mlflow_runs.csv` | Export des runs MLFlow (`mlruns/` étant trop volumineux pour git) |
| `exploration_summary.json` | Sortie de l'exploration initiale |
| `audit.md` | Audit qualité interne — **non versionné**, local uniquement |

## Sources & licences

| Source | Licence |
|---|---|
| FAOSTAT | CC BY-NC-SA 3.0 IGO — ⚠️ non commercial |
| Our World in Data / Poore & Nemecek (2018) | CC BY 4.0 |
| World Bank Open Data | CC BY 4.0 |

## Convention

- Tout chiffre cité renvoie au notebook ou au script qui le produit.
- Aucune valeur n'est écrite à la main : `metrics.json` fait foi.
- Les limites méthodologiques sont documentées, pas dissimulées.
