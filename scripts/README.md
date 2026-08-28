# ⚙️ Scripts

Version industrialisée des notebooks. **C'est ici que se trouve le code qui fait
foi** ; les notebooks documentent la démarche exploratoire.

| Script | Rôle |
|---|---|
| `etl_pipeline.py` | Data Lake + entrepôt en étoile. Idempotent, validé, journalisé. |
| `train_model.py` | Entraîne les 3 modèles, journalise dans MLFlow, exporte les métriques. |
| `_mappings.py` | Tables de correspondance FAO ↔ ISO3, régions, catégorisation produits. Extraites verbatim du notebook ETL. |
| `check_db.py` | Diagnostic de connexion : joignabilité, TLS, tables, droits. Local ou AWS RDS. |

## Usage

```bash
python scripts/check_db.py                      # vérifier la cible avant tout
python scripts/etl_pipeline.py                  # pipeline complet (~5 min)
python scripts/etl_pipeline.py --steps facts    # faits uniquement
python scripts/etl_pipeline.py --validate-only  # contrôles, aucune écriture

python scripts/train_model.py --skip-tuning     # ~3 min
python scripts/train_model.py --only clustering
```

## Maintenance

Les sources amont sont annuelles (FAOSTAT, World Bank). Rafraîchissement :

1. Régénérer les CSV via les notebooks `01b` / `01c` / `01d`
2. `python scripts/etl_pipeline.py`
3. `python scripts/train_model.py`
4. `pytest -q`

Le pipeline étant idempotent, ces étapes se rejouent sans risque de doublon.
Cible d'automatisation : une règle **EventBridge** mensuelle déclenchant une
fonction **Lambda** (ou une tâche **ECS**), pour un coût négligeable.
