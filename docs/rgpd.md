# Conformité RGPD

> Projet « Score d'Impact Environnemental de l'Assiette Mondiale » — Jedha Bloc 6
> Dernière revue : 27/08/2026

---

## 1. Conclusion

**Le projet ne traite aucune donnée à caractère personnel.** Le RGPD (règlement
UE 2016/679) ne s'applique donc pas au traitement mis en œuvre, au sens de son
article 2.

Ce document justifie cette conclusion plutôt que de l'affirmer : l'absence de
données personnelles est une propriété qu'il faut démontrer, pas postuler.

---

## 2. Qualification des données traitées

L'article 4.1 du RGPD définit une donnée à caractère personnel comme toute
information se rapportant à une **personne physique identifiée ou identifiable**.

| Jeu de données | Granularité la plus fine | Personne identifiable ? |
|---|---|---|
| FAOSTAT — bilans alimentaires | Pays × produit × année | Non — agrégat national |
| Food_Production (Poore & Nemecek) | Produit alimentaire | Non — moyenne de 38 700 exploitations |
| World Bank — indicateurs socio-éco | Pays × année | Non — agrégat national |
| OWID — consommation de viande | Pays × année | Non — agrégat national |

Aucun jeu ne descend sous la maille **pays × année**. Aucun identifiant direct
(nom, adresse, e-mail, identifiant national) ni indirect (date de naissance,
localisation fine, identifiant d'appareil) n'est présent. La ré-identification
par croisement est exclue : la plus petite population décrite par une ligne est
celle d'un État.

Les données sont par ailleurs des **statistiques publiques officielles**,
publiées en accès ouvert par des organisations internationales.

---

## 3. Le simulateur de menu

C'est le seul point de l'application où un utilisateur saisit quelque chose. Il
mérite un examen distinct.

**Ce que l'utilisateur renseigne** : une fréquence de consommation par aliment
et une taille de portion.

**Ce qu'il en advient** :

- le calcul est effectué **en mémoire**, dans la session Streamlit ;
- le résultat n'est **jamais écrit en base** — aucune table de l'entrepôt n'est
  accessible en écriture depuis l'application ;
- la « référence » sauvegardable vit dans `st.session_state`, c'est-à-dire en
  mémoire volatile, et **disparaît à la fermeture de l'onglet** ;
- aucun cookie de suivi, aucune télémétrie : `gatherUsageStats = false` dans
  `.streamlit/config.toml` ;
- aucun compte, aucune authentification, aucun formulaire d'identification.

**Ces données sont-elles personnelles ?** Des habitudes alimentaires *rattachées
à une personne identifiée* seraient des données personnelles, et un régime
révélant une pratique religieuse relèverait même de l'article 9 (catégories
particulières). Ici, rien ne rattache la saisie à une personne : pas de compte,
pas d'identifiant, pas de conservation. La donnée n'existe que le temps du
calcul.

> **Règle de conception à préserver.** Toute évolution qui persisterait les
> saisies utilisateur — historique de simulations, comptes, export nominatif —
> ferait basculer le projet dans le champ du RGPD et imposerait alors : base
> légale, information des personnes, durée de conservation, droits d'accès et
> d'effacement. Voir §6.

---

## 4. Licences et conditions de réutilisation

Le RGPD ne s'applique pas, mais le droit des bases de données, si.

| Source | Licence | Conditions |
|---|---|---|
| FAOSTAT | CC BY-NC-SA 3.0 IGO | Attribution · **non commercial** · partage à l'identique |
| Our World in Data | CC BY 4.0 | Attribution |
| World Bank Open Data | CC BY 4.0 | Attribution |
| Poore & Nemecek (2018), *Science* | CC BY 4.0 (données OWID) | Attribution |

⚠️ **La clause NC de la FAO est contraignante.** Elle interdit toute exploitation
commerciale des données FAOSTAT. Le projet reste dans le cadre pédagogique et
non commercial. Une valorisation commerciale ultérieure (voir `docs/impact.md`)
supposerait de renégocier ce point avec la FAO ou de substituer une source
équivalente.

Les attributions figurent dans le `README.md`, dans l'onglet **Méthodologie**
de l'application et dans le support de présentation.

---

## 5. Sécurité et gouvernance technique

Bien qu'aucune donnée personnelle ne soit en jeu, les mesures de l'article 32
(sécurité du traitement) sont appliquées par principe :

| Mesure | Mise en œuvre |
|---|---|
| Secrets hors du code | `.env` exclu de git ; templates `.env.example` sans valeur |
| Secrets hors de l'application | `.streamlit/secrets.toml` exclu de git |
| Moindre privilège en base | Utilisateur applicatif en lecture seule (à appliquer en production) |
| Chiffrement en transit | `sslmode=require` sur la connexion PostgreSQL AWS |
| Restriction réseau | ACL AWS à restreindre aux IP autorisées avant la mise en ligne |
| Traçabilité | Historique git ; pipeline ETL rejouable et journalisé |
| Hébergement UE | AWS, région `fr-par` (France) — pas de transfert hors UE |

⚠️ **Point de vigilance ouvert.** `config/.env.common` est versionné sur un dépôt
public et expose l'identifiant de projet AWS ainsi que le nom d'hôte de la
base. Ce ne sont pas des secrets (aucun mot de passe), mais l'endpoint est
découvrable. **Action requise avant la soutenance : restreindre l'accès réseau
par ACL AWS.**

---

## 6. Ce qui déclencherait une mise en conformité

Trois évolutions feraient entrer le projet dans le champ du RGPD. Elles sont
listées ici pour que la décision soit consciente si elle se pose.

| Évolution | Conséquence | Obligations déclenchées |
|---|---|---|
| Comptes utilisateurs, historique de simulations | Données personnelles | Base légale (consentement ou intérêt légitime), information des personnes, durée de conservation, droits d'accès/rectification/effacement, registre des traitements |
| Analytics comportemental (Matomo, GA) | Traceurs | Consentement préalable (directive ePrivacy, art. 82 loi Informatique et Libertés) + bandeau conforme |
| Données de santé ou de régime rattachées à une personne | Article 9 — catégorie particulière | Consentement explicite, AIPD probablement requise |

En l'état, **aucune de ces évolutions n'est engagée**, et le registre des
activités de traitement (article 30) n'est pas requis.

---

## 7. Synthèse pour la soutenance

> Les données traitées sont exclusivement des **statistiques publiques agrégées
> au niveau pays × année**, publiées sous licences ouvertes par la FAO, la
> Banque mondiale et Our World in Data. **Aucune personne physique n'est
> identifiée ni identifiable** : le RGPD ne s'applique pas.
>
> Le simulateur, seul point de saisie, calcule **en mémoire** et ne persiste
> rien : ni base, ni cookie, ni télémétrie.
>
> Les mesures de sécurité usuelles sont néanmoins appliquées — secrets hors du
> code, chiffrement en transit, hébergement en France. La principale contrainte
> juridique du projet n'est pas le RGPD mais la **clause non-commerciale de la
> licence FAOSTAT**, qui encadrerait toute valorisation ultérieure.
