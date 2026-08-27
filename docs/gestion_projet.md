# Gestion de projet — objectifs, planning, budget

> Projet « Score d'Impact Environnemental de l'Assiette Mondiale » — Jedha Bloc 6
> Équipe : Emeline ROBLOT

---

## 1. Objectifs

### 1.1 Objectif métier

Rendre **lisible et comparable** l'empreinte environnementale du système
alimentaire, à une maille (pays × année × produit) qui n'est aujourd'hui
accessible qu'en croisant manuellement plusieurs bases institutionnelles
hétérogènes.

La question de départ : *la structure alimentaire d'un pays — ce qu'il produit,
sa richesse, son urbanisation — détermine-t-elle son empreinte environnementale,
et peut-on en tirer des profils exploitables ?*

### 1.2 Objectifs opérationnels

| # | Objectif | Critère de réussite | Statut |
|---|---|---|---|
| O1 | Consolider 4 sources hétérogènes en un entrepôt requêtable | Entrepôt en étoile, pipeline rejouable en une commande | ✅ 973 227 lignes, ETL en 285 s |
| O2 | Établir statistiquement les déterminants de l'empreinte | ≥ 2 hypothèses testées, p < 0,05 | ✅ H1 et H2 validées (Kruskal-Wallis) |
| O3 | Prédire l'empreinte par habitant à partir du socio-économique | Modèle battant significativement une baseline naïve | ✅ Modèle B |
| O4 | Identifier des profils de pays | Clustering interprétable métier | ✅ KMeans k=5 |
| O5 | Rendre le tout manipulable par un non-technicien | Application web, 3 parcours d'usage | ✅ 4 pages Streamlit |
| O6 | Garantir la reproductibilité | Installation et exécution documentées, tests automatisés | ✅ scripts + 23 tests |

### 1.3 Hors périmètre (décisions assumées)

- **Empreinte de consommation réelle** — les données FAO mesurent la production
  disponible, pas ce qui est ingéré. Reconstituer la consommation demanderait
  des matrices d'échanges commerciaux, hors budget temps.
- **Facteurs d'émission régionalisés** — un kg de bœuf reçoit un facteur mondial
  moyen. Les facteurs par pays existent mais ne couvrent pas 60 ans d'historique.
- **Prévision à horizon** — aucun modèle de série temporelle n'est livré.
  Identifié comme suite prioritaire (§5).

---

## 2. Organisation de l'équipe

| Membre | Rôle principal | Livrables |
|---|---|---|
| Emeline ROBLOT | Data engineering & MLOps | ETL, entrepôt, pipeline ML, application |
| Emeline ROBLOT | Analyse & modélisation | EDA, tests statistiques, clustering |
| Emeline ROBLOT | Infrastructure & coordination | Dépôt, environnements, AWS, intégration |

**Méthode** : itérations courtes, dépôt git partagé, branches `feature/*`
fusionnées après revue croisée.

> ⚠️ Le dépôt de référence portant l'historique de collaboration à trois est
> hébergé sur GitHub. Le dépôt GitHub est un miroir de publication.

---

## 3. Planning réalisé

| Phase | Contenu | Charge | Statut |
|---|---|---|---|
| **1. Cadrage & sourcing** | Choix du sujet, identification des sources, faisabilité | 12 h | ✅ |
| **2. Acquisition** | FAOSTAT API, World Bank API, OWID, nettoyage initial | 20 h | ✅ |
| **3. ETL & entrepôt** | Modèle en étoile, mapping FAO↔ISO3, appariement produits | 32 h | ✅ |
| **4. EDA** | Univarié, bivarié, tests d'hypothèses, sélection de variables | 24 h | ✅ |
| **5. Modélisation** | Régression, clustering, suivi MLFlow | 28 h | ✅ |
| **6. Application** | Streamlit, 4 pages, cartographie, simulateur | 30 h | ✅ |
| **7. Audit & durcissement** | Audit qualité, correction de 8 bloquants, tests, industrialisation | 16 h | ✅ |
| **8. Déploiement & soutenance** | Migration AWS, support, répétition | 12 h | 🔄 En cours |
| | **Total** | **174 h** | |

### Rétroplanning de la dernière semaine

| Jour | Objet | Responsable |
|---|---|---|
| J-7 → J-6 | Documents de conformité (RGPD, gestion de projet, impact), support de présentation | Toute l'équipe |
| J-5 | Correction des bugs visibles en démonstration | Emeline |
| J-4 | Consolidation méthodologique, mise à jour du README avec les chiffres réels | Emeline |
| J-3 | Industrialisation, unification des dépendances | Emeline |
| J-2 | Déploiement, capture vidéo de secours, ACL AWS | Emeline |
| J-1 | Répétition chronométrée (6 min), questions/réponses | Toute l'équipe |
| J | Demoday | Toute l'équipe |

---

## 4. Budget

### 4.1 Budget réalisé — contexte pédagogique

| Poste | Détail | Coût |
|---|---|---|
| Sources de données | FAOSTAT, World Bank, OWID — API publiques | **0 €** |
| Base de données (dév.) | PostgreSQL 16 en conteneur local | **0 €** |
| Base de données (prod.) | AWS Serverless PostgreSQL, offre découverte | **~5 €/mois** |
| Stockage objet | AWS Object Storage, < 5 Go | **~0,50 €/mois** |
| Hébergement application | Streamlit Community Cloud | **0 €** |
| Suivi d'expériences | MLFlow auto-hébergé (fichiers locaux) | **0 €** |
| Outillage | Python, PostgreSQL, Docker — tous open source | **0 €** |
| **Total infrastructure** | | **≈ 5,50 €/mois** |
| Charge humaine | 174 h × 3 personnes (valorisation indicative à 350 €/j) | **≈ 7 600 €** |

### 4.2 Budget d'industrialisation — hypothèse de mise en production

Estimation pour un service ouvert au public, ~10 000 visites/mois.

| Poste | Solution | Coût mensuel |
|---|---|---|
| Base de données managée | AWS PostgreSQL DB-DEV-S (2 vCPU, 2 Go) | 25 € |
| Hébergement application | AWS Serverless Container (1 vCPU, 2 Go) | 20 € |
| Stockage objet | Object Storage, 50 Go | 1 € |
| Orchestration ETL | Serverless Job mensuel (rafraîchissement FAO/WB) | 2 € |
| Nom de domaine + TLS | Domaine .org + Let's Encrypt | 1 € |
| Supervision | Sentry, offre gratuite | 0 € |
| **Total récurrent** | | **≈ 49 €/mois** |
| Développement initial | 15 j·h (durcissement, CI/CD, supervision) | ≈ 5 250 € (ponctuel) |
| Maintenance | 1 j·h/mois | ≈ 350 €/mois |

**Coût total de possession, première année :** ≈ 5 250 € (ponctuel) + 12 × 399 €
= **≈ 10 000 €**.

### 4.3 Ce que le budget révèle

Le coût d'infrastructure est **négligeable** (≈ 600 €/an) : la valeur du projet
est presque entièrement dans le travail de consolidation et de modélisation.
C'est cohérent avec la nature du problème — la difficulté n'est pas de calculer,
elle est de **réconcilier des référentiels hétérogènes** (172 pays aux
nomenclatures divergentes, 121 produits à apparier sur un référentiel de 43).

---

## 5. Risques identifiés et traitement

| Risque | Probabilité | Impact | Traitement |
|---|---|---|---|
| Démonstration dépendante d'une base locale | Élevée | Bloquant | Capture vidéo de secours + migration AWS |
| Artefact de modèle trop volumineux pour l'hébergement | Avérée | Bloquant | Profondeur bornée + compression → passé de 1,8 Go à quelques Mo |
| Rupture d'API amont (FAOSTAT, OWID) | Moyenne | Modéré | CSV mis en cache dans `data/raw/` ; ETL rejouable hors ligne |
| Clause non commerciale FAOSTAT | Faible | Élevé si valorisation | Documenté dans `docs/rgpd.md` §4 |
| Question du jury sur la tautologie du modèle A | **Certaine** | Modéré | Anticipée : modèle B ajouté, onglet Méthodologie, §4.1 de l'audit |

---

## 6. Suites envisagées

Par ordre de valeur ajoutée décroissante.

1. **Prévision temporelle** — prédire l'empreinte à `t+1` à partir de
   l'historique. Vraie tâche prédictive, répond à la question posée en
   introduction, et à laquelle le projet actuel ne répond pas.
2. **Empreinte de consommation** — intégrer les matrices d'échanges FAO pour
   passer de la production disponible à la consommation apparente.
3. **Eau et usage des sols dans l'application** — les colonnes existent déjà
   dans l'entrepôt et ne sont pas exposées. Coût quasi nul, valeur perçue triplée.
4. **Facteurs d'émission régionalisés** — remplacer le facteur mondial moyen par
   un facteur par région de production.
5. **Rafraîchissement automatisé** — job mensuel déclenchant l'ETL sur les
   nouvelles publications FAOSTAT et World Bank.
