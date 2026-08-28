# Impact réel & proposition de valeur

> Projet « Score d'Impact Environnemental de l'Assiette Mondiale » — Jedha Bloc 6

---

## 1. Le problème, formulé simplement

Le système alimentaire mondial pèse **26 % des émissions de gaz à effet de
serre** et **70 % des prélèvements d'eau douce** (Poore & Nemecek, *Science*,
2018). C'est le premier levier d'action climatique après l'énergie.

Pourtant, la donnée qui permettrait d'agir est **techniquement disponible mais
pratiquement inutilisable** :

- la FAO publie les quantités produites, sans aucune donnée environnementale ;
- Our World in Data publie les facteurs d'émission, sans aucune quantité ;
- la Banque mondiale publie le contexte socio-économique, sans lien avec
  l'alimentation ;
- les trois utilisent des **nomenclatures de pays et de produits différentes**.

Croiser ces sources demande un travail de réconciliation que personne ne refait
volontiers : 172 pays aux noms divergents, 121 produits à apparier sur un
référentiel de 43.

**Ce que fait ce projet :** ce travail, une fois, de manière rejouable, et il en
expose le résultat.

---

## 2. Le rôle de la data science

| Étape | Sans data science | Avec |
|---|---|---|
| Réconcilier les référentiels | Tableur manuel, non reproductible | Appariement flou automatisé, rejouable en 285 s |
| Comprendre les déterminants | Intuition | Tests statistiques : H1 et H2 validées, p < 0,001 |
| Classer les pays | Seuils arbitraires | Clustering non supervisé, 5 profils émergents |
| Explorer des scénarios | Impossible | Modèle de simulation interactif |

---

## 3. À qui cela sert

### 3.1 Enseignement supérieur et médiation scientifique — usage prioritaire

**Le besoin.** Un enseignant en développement durable ou en géographie n'a pas
d'outil pour montrer, en direct, pourquoi l'Océanie émet 3 703 kg CO₂/hab quand
l'Asie en émet 1 785.

**Ce que l'application apporte.** Une carte manipulable, une chronologie sur
60 ans, un simulateur qui rend l'abstraction personnelle. L'étudiant compare sa
propre assiette à la moyenne de son pays.

**Pourquoi c'est le meilleur point d'entrée :** aucune contrainte réglementaire,
la clause non commerciale de la FAO n'est pas un obstacle, et le besoin est réel.

### 3.2 ONG et journalisme de données

**Le besoin.** Étayer un argumentaire par des chiffres traçables, avec une
méthode auditable.

**Ce que l'application apporte.** Chaque chiffre remonte à sa source ; le
pipeline est rejouable ; les limites sont documentées dans l'onglet
Méthodologie. Un journaliste peut citer sans risque.

### 3.3 Restauration collective — piste exploratoire

**Le besoin.** La loi EGalim impose aux cantines publiques des objectifs de
durabilité, mais les gestionnaires manquent d'outils de comparaison.

**Ce que l'application apporte.** Le simulateur transposé à l'échelle d'un menu
donne un ordre de grandeur de l'effet d'un changement de composition.

⚠️ **Honnêteté nécessaire.** Nos facteurs sont des **moyennes mondiales**. Pour
un usage opérationnel réel, il faudrait des facteurs régionalisés et des données
d'approvisionnement. Nous décrivons un cas d'usage plausible, pas un produit
prêt à l'emploi.

---

## 4. Ce que les données montrent

Chiffres issus de `notebooks/03_eda.ipynb`, reproductibles.

| Constat | Mesure | Lecture |
|---|---|---|
| **L'urbanisation prédit la consommation de viande** | 26,5 kg/hab en milieu rural → 150,5 kg/hab en milieu urbain (Kruskal-Wallis H=4387, p≈0) | Facteur ×5,7 — le déterminant le plus net de l'étude |
| **La richesse déplace la structure du régime** | Part animale : 15,3 % (quartile 1 de PIB) → 46,3 % (quartile 4), H=3163, p≈0 | Ce n'est pas le volume qui change, c'est la composition |
| **L'écart régional est majeur** | Océanie 3 703 kg/hab · Europe 3 401 · Afrique 2 248 · Asie 1 785 | Rapport de 1 à 2 entre les extrêmes |
| **La quantité domine la corrélation** | r = 0,867 entre quantité produite et CO₂ total | Attendu — le CO₂ est calculé depuis la quantité (cf. Méthodologie) |

**L'implication opérationnelle.** L'urbanisation étant le déterminant le plus
net, et l'essentiel de la croissance urbaine mondiale des trente prochaines
années se concentrant en Asie et en Afrique, la trajectoire d'émissions
alimentaires de ces régions est **prévisible et donc actionnable**. C'est là que
les politiques publiques ont le plus de rendement.

---

## 5. Modèle de valorisation

⚠️ **Verrou juridique préalable.** Les données FAOSTAT sont sous licence
**CC BY-NC-SA** : toute exploitation commerciale est interdite en l'état. Une
valorisation payante supposerait une autorisation de la FAO ou une source de
substitution. Cette contrainte est structurante et documentée dans
`docs/rgpd.md` §4.

| Scénario | Modèle | Faisabilité |
|---|---|---|
| **Plateforme pédagogique ouverte** | Gratuit, financement institutionnel | ✅ Immédiate — compatible NC |
| **API de données consolidées** | Freemium (quota gratuit, abonnement au-delà) | ⚠️ Requiert la levée du verrou FAO |
| **Conseil et études sur mesure** | Prestation | ✅ La méthode est valorisable, pas la donnée brute |
| **Brique dans un outil bilan carbone** | Licence B2B | ⚠️ Requiert la levée du verrou FAO |

**Recommandation.** Viser d'abord la **plateforme pédagogique ouverte** : c'est
le seul scénario immédiatement praticable, il correspond au besoin le mieux
établi, et il construit la crédibilité qui rendrait les autres scénarios
négociables.

Coût d'exploitation : **≈ 52 €/mois** (cf. `docs/gestion_projet.md` §4.2). Un
budget de mécénat ou une subvention de médiation scientifique suffit.

---

## 6. Limites à énoncer soi-même

Un jury pardonne une limite identifiée ; il sanctionne une limite qu'il
découvre. Les quatre à connaître :

1. **Production ≠ consommation.** Les données FAO mesurent ce qu'un pays produit
   et rend disponible, exportations et alimentation animale incluses. Un pays
   exportateur agricole paraît plus émetteur qu'il ne l'est pour ses habitants.
2. **Facteurs d'émission moyens et statiques.** Un kg de bœuf reçoit le même
   facteur au Brésil et en Irlande, sur toute la période 1961–2023.
3. **Le modèle de régression principal est un calculateur, pas un prédicteur.**
   Sa cible est construite à partir de sa variable d'entrée. Le modèle B, fondé
   sur les seules variables socio-économiques, constitue la vraie démonstration
   prédictive. Cf. onglet **Méthodologie** de l'application.
4. **Corrélation, pas causalité.** Le lien urbanisation ↔ consommation de viande
   est statistiquement robuste, mais ces variables sont co-déterminées par le
   développement économique.

---

## 7. Formulation pour une audience non technique

> Nourrir huit milliards d'êtres humains représente **un quart des émissions
> mondiales de gaz à effet de serre**. Les données pour comprendre ce phénomène
> existent — mais dispersées dans trois institutions qui ne parlent pas la même
> langue.
>
> Nous les avons réconciliées : **60 ans d'histoire, 172 pays, 121 produits
> alimentaires**, dans une base unique et une application où chacun peut
> explorer.
>
> Ce qu'on y découvre : **quand un pays s'urbanise, sa consommation de viande
> est multipliée par près de six**. Ce n'est pas d'abord une question de
> richesse — c'est une question de mode de vie. Et comme on sait où se produira
> l'urbanisation des trente prochaines années, on sait où agir.
>
> L'application permet aussi de comparer sa propre assiette à la moyenne de son
> pays. Pas pour culpabiliser : pour rendre concret un chiffre qui, sinon, reste
> abstrait.
