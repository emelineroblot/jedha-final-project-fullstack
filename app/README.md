# 🌐 Application Streamlit

Application web interactive pour visualiser et interagir avec les résultats.

## Lancement

```bash
streamlit run app/streamlit_app.py
```

L'application sera accessible à : http://localhost:8501

## Structure

### `streamlit_app.py`
Fichier principal de l'application.

### `components/` (à créer si nécessaire)
Composants réutilisables :
- `sidebar.py` : Barre latérale avec filtres
- `charts.py` : Graphiques personnalisés
- `simulator.py` : Simulateur d'impact

## Fonctionnalités

- 🏠 **Accueil** : Vue d'ensemble, métriques clés
- 🥗 **Simulateur Menu** : Calcul impact d'une assiette
- 🌍 **Comparateur Pays** : Visualisation par pays/région
- 📈 **Prédictions** : Scénarios "What-if"
- 🎯 **Clustering** : Profils de pays

## Déploiement

### Streamlit Cloud (gratuit)
1. Push le code sur GitHub
2. Connecter sur [share.streamlit.io](https://share.streamlit.io)
3. Sélectionner le repository et le fichier `app/streamlit_app.py`

### Heroku / Render
Voir documentation dédiée.
