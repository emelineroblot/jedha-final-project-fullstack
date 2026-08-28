# Déploiement — AWS RDS PostgreSQL

> Procédure de création de la base de production et de migration des données
> depuis l'instance Docker locale.
>
> **Cible :** AWS RDS PostgreSQL · `db.t4g.micro` · région `eu-north-1` (Stockholm)
> **Instance en service :** `food-impact-db` · PostgreSQL 18.3 · option A retenue (§2)
> **Durée :** ~20 min de configuration + ~10 min d'attente + ~10 min de migration

---

## 0. Avant de commencer

### Ce dont tu as besoin

- Un compte AWS actif
- Ton **adresse IP publique** — récupère-la avec :
  ```bash
  curl -s https://checkip.amazonaws.com
  ```
- La base locale peuplée et démarrée :
  ```bash
  docker compose -f docker/docker-compose.yml up -d
  python scripts/etl_pipeline.py --validate-only
  ```

### ⚠️ Coûts — à vérifier avant de cliquer

AWS a modifié son modèle de free tier en 2025. Selon la date de création de ton
compte, tu es dans l'un des deux régimes :

| Régime | Ce que tu obtiens |
|---|---|
| Ancien free tier (comptes créés avant le changement) | 750 h/mois de `db.t4g.micro` + 20 Go, **pendant 12 mois** |
| Nouveau modèle | Un **crédit initial** à consommer librement |

**La console te l'indique** au moment de la création (mention « Free tier » sur
le modèle, ou solde de crédits dans *Billing*). Hors free tier, cette instance
coûte environ **15 $/mois** (calcul en §7).

👉 **Configure une alerte de budget avant tout** — voir §7. C'est deux minutes,
et ça évite la mauvaise surprise.

---

## 1. Créer l'instance RDS

Console AWS → service **RDS** → vérifie que la région en haut à droite est bien
**Europe (Stockholm) eu-north-1** → **Create database**.

> Les libellés de la console AWS évoluent régulièrement. Si un intitulé diffère
> légèrement, la logique reste la même.

### 1.1 Méthode et moteur

| Champ | Valeur |
|---|---|
| Choose a database creation method | **Standard create** |
| Engine type | **PostgreSQL** |
| Engine version | **PostgreSQL 18.x** (version de l'instance en service) |

> ⚠️ **L'instance tourne en PostgreSQL 18.3 alors que le conteneur local est en
> 16.15.** Ce n'est pas bloquant, mais impose une règle : les outils `pg_dump` et
> `pg_restore` doivent être **au moins aussi récents que le serveur**. D'où
> l'usage d'un conteneur `postgres:18` au §5, et non des binaires du conteneur
> local. Pour rétablir la parité, passer `docker/docker-compose.yml` sur
> `postgres:18` et relancer l'ETL.

### 1.2 Modèle

| Champ | Valeur |
|---|---|
| Templates | **Free tier** si l'option apparaît, sinon **Dev/Test** |

Le modèle *Free tier* verrouille automatiquement les bons choix (mono-AZ, pas de
réplica). S'il n'apparaît pas, ton compte n'y est plus éligible : prends
*Dev/Test* et applique les valeurs ci-dessous à la main.

### 1.3 Identifiants

| Champ | Valeur |
|---|---|
| DB instance identifier | `food-impact-db` |
| Master username | `food_admin` |
| Credentials management | **Self managed** |
| Master password | **Génère un mot de passe fort** (20+ caractères) |

🔑 **Note ce mot de passe immédiatement dans un gestionnaire de mots de passe.**
AWS ne le réaffichera jamais. Il ira ensuite dans `.env`, qui n'est pas versionné.

> Évite les caractères `/`, `@`, `"` et l'espace : ils cassent les URL de
> connexion PostgreSQL si tu construis une chaîne `postgresql://...`.

### 1.4 Configuration de l'instance

| Champ | Valeur |
|---|---|
| DB instance class | **Burstable classes (includes t classes)** → **db.t4g.micro** |

`db.t4g.micro` = 2 vCPU ARM, 1 Go de RAM. Suffisant : la base pèse ~250 Mo et
l'application ne sert qu'un utilisateur à la fois en démonstration.

### 1.5 Stockage

| Champ | Valeur |
|---|---|
| Storage type | **General Purpose SSD (gp3)** |
| Allocated storage | **20** GiB |
| Enable storage autoscaling | ❌ **Décoché** |

> ❌ **Décoche bien l'autoscaling.** C'est la première source de facture
> inattendue : le stockage grandit tout seul et ne redescend jamais. 20 Go
> couvrent très largement les 250 Mo de données.

### 1.6 Connectivité — la section qui compte

| Champ | Valeur |
|---|---|
| Compute resource | **Don't connect to an EC2 compute resource** |
| Network type | **IPv4** |
| VPC | VPC par défaut |
| DB subnet group | default |
| **Public access** | **Yes** |
| VPC security group | **Create new** → nom : `food-impact-sg` |
| Availability Zone | No preference |
| Database port | `5432` |

> **Pourquoi `Public access = Yes` ?** L'application tournera sur Streamlit
> Community Cloud, hors de ton VPC, et tu dois pouvoir lancer la migration
> depuis ton poste. Sans accès public, il faudrait un bastion ou un VPN —
> disproportionné ici. L'accès reste filtré par le security group (§2) et
> chiffré par TLS (§3).

### 1.7 Authentification

| Champ | Valeur |
|---|---|
| Database authentication | **Password authentication** |

### 1.8 Configuration additionnelle

Déplie **Additional configuration** — c'est ici que se jouent les coûts.

| Champ | Valeur | Pourquoi |
|---|---|---|
| **Initial database name** | **`food_impact`** | ⚠️ **Champ critique.** Laissé vide, RDS ne crée **aucune** base et tu ne pourras pas te connecter |
| Automated backups | ✅ Activé, rétention **1 jour** | Le minimum ; les données sont régénérables par l'ETL |
| Backup window | No preference | |
| Encryption | ✅ Activé (clé par défaut) | Gratuit, et bon argument RGPD |
| Performance Insights | ❌ **Désactivé** | Facturé au-delà du niveau gratuit |
| Enhanced monitoring | ❌ **Désactivé** | Facturé (CloudWatch) |
| Log exports | ❌ Tout décoché | Facturé (CloudWatch Logs) |
| Auto minor version upgrade | ✅ Activé | |
| Deletion protection | ❌ Décoché | Tu voudras pouvoir supprimer l'instance après la soutenance |

Clique **Create database**.

⏳ **L'instance met 5 à 10 minutes** à passer de `Creating` à `Available`.
Profites-en pour faire l'étape 2.

---

## 2. Ouvrir le pare-feu (security group)

Console → **EC2** → **Security Groups** → sélectionne `food-impact-sg` →
onglet **Inbound rules** → **Edit inbound rules**.

### Règle 1 — ton poste (migration et développement)

| Champ | Valeur |
|---|---|
| Type | **PostgreSQL** |
| Protocol / Port | TCP / 5432 (auto-rempli) |
| Source | **My IP** |
| Description | `Poste local - migration et dev` |

### Règle 2 — Streamlit Community Cloud

Streamlit Cloud **ne publie pas de plage d'IP fixe**. Deux options, à choisir en
connaissance de cause :

| Option | Règle | Analyse |
|---|---|---|
| **A — Ouvrir** | Source `0.0.0.0/0` | Fonctionne immédiatement. La base est alors joignable depuis Internet : la sécurité repose entièrement sur le mot de passe fort et le TLS |
| **B — Fermer** | Pas de règle | La démonstration se fait en local (`streamlit run`), sur la base locale ou en tunnel. Aucune exposition |

**Recommandation :** option **B pour la soutenance**, option A seulement si tu
tiens à une URL publique partageable.

> ✅ **Option A retenue.** Les contreparties du paragraphe suivant sont donc
> obligatoires, et la suppression de l'instance après la soutenance n'est pas
> optionnelle.

Si tu prends l'option A, alors **impérativement** :
- mot de passe maître de 20+ caractères aléatoires
- créer l'utilisateur applicatif **en lecture seule** (§4)
- **supprimer l'instance après la soutenance** (§7)

> ⚠️ Ton IP publique change si ta box redémarre. Si la connexion échoue plus
> tard, reviens ici et refais **My IP**.

---

## 3. Forcer le chiffrement TLS

Console **RDS** → **Parameter groups** → **Create parameter group**.

| Champ | Valeur |
|---|---|
| Parameter group family | `postgres16` |
| Type | DB Parameter Group |
| Group name | `food-impact-params` |

Crée-le, ouvre-le, cherche le paramètre **`rds.force_ssl`** → **Edit** → valeur
**`1`** → Save.

Puis applique-le à l'instance : **Databases** → `food-impact-db` → **Modify** →
section *Additional configuration* → **DB parameter group** =
`food-impact-params` → **Continue** → **Apply immediately** → **Modify DB
instance**.

> `rds.force_ssl = 1` est un **paramètre statique** : l'instance redémarre pour
> le prendre en compte (~2 min). Toute connexion non chiffrée sera ensuite
> refusée — d'où le `sslmode=require` dans les chaînes de connexion.

---

## 4. Récupérer l'endpoint et configurer `.env`

Console **RDS** → **Databases** → `food-impact-db` → onglet **Connectivity &
security** → copie l'**Endpoint**. Il ressemble à :

```
food-impact-db.cta2iqgqyibu.eu-north-1.rds.amazonaws.com
```

Reporte-le dans `.env` **à la racine du projet** (ce fichier n'est pas versionné) :

```bash
# ── PostgreSQL local (développement) ─────────────────────────
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=food_impact
POSTGRES_USER=food_user
POSTGRES_PASSWORD=food_pass

# ── PostgreSQL AWS RDS (production) ──────────────────────────
# Décommenter pour basculer sur la production.
# POSTGRES_HOST=food-impact-db.cta2iqgqyibu.eu-north-1.rds.amazonaws.com
# POSTGRES_PORT=5432
# POSTGRES_DB=food_impact
# POSTGRES_USER=food_admin
# POSTGRES_PASSWORD=<ton-mot-de-passe-maitre>
# POSTGRES_SSLMODE=require
```

Aucun code n'est à modifier : l'application, l'ETL et l'entraînement dérivent
tous leur connexion de ces variables.

---

## 5. Migrer les données

### 5.1 Exporter depuis le conteneur local

Lance `pg_dump` **depuis le conteneur**, pas depuis ton poste : la version de
l'outil correspond ainsi exactement à celle du serveur.

```bash
docker exec food_impact_db pg_dump \
    -U food_user -d food_impact \
    --format=custom --no-owner --no-acl \
    --file=/tmp/food_impact.dump

docker cp food_impact_db:/tmp/food_impact.dump ./food_impact.dump
```

Contrôle la taille (attendu : ~50 à 150 Mo) :

```bash
ls -lh food_impact.dump
```

> `--no-owner` et `--no-acl` évitent que la restauration tente de recréer le
> rôle `food_user`, qui n'existe pas sur RDS.

### 5.2 Restaurer vers RDS

Toujours depuis le conteneur, qui embarque `pg_restore` :

```bash
docker cp ./food_impact.dump food_impact_db:/tmp/restore.dump

docker exec -e PGPASSWORD='<ton-mot-de-passe-maitre>' food_impact_db \
    pg_restore \
    -h food-impact-db.cta2iqgqyibu.eu-north-1.rds.amazonaws.com \
    -U food_admin -d food_impact \
    --no-owner --no-acl --clean --if-exists \
    /tmp/restore.dump
```

**Compte 5 à 15 minutes** — l'essentiel du volume est `fait_production`
(1,2 million de lignes).

> Des avertissements du type `must be owner of extension plpgsql` sont
> **normaux** sur RDS et sans conséquence : le compte maître n'est pas
> superutilisateur. Seules les erreurs sur les tables `dim_*` / `fait_*`
> justifient de s'inquiéter.

### 5.3 Valider

Bascule `.env` sur le bloc RDS (décommente), puis :

```bash
python scripts/etl_pipeline.py --validate-only
```

Attendu :

```
✓ dim_pays                          172 lignes
✓ dim_temps                          63 lignes
✓ dim_produits                      121 lignes
✓ dim_socio_economique           10 269 lignes
✓ fait_impact                        47 lignes
✓ fait_production             1 204 119 lignes
✓ fait_impact_pays_annee        973 227 lignes
✓ Intégrité référentielle : aucun orphelin
✓ Grain respecté : 1 ligne par (pays, année, produit)
Validation RÉUSSIE
```

Puis l'application :

```bash
streamlit run app/streamlit_app.py
```

Enfin, supprime le dump — il contient toutes les données :

```bash
rm food_impact.dump
docker exec food_impact_db rm -f /tmp/food_impact.dump /tmp/restore.dump
```

---

## 6. Créer un utilisateur applicatif en lecture seule

L'application ne fait que lire. Lui donner le compte maître serait un privilège
excessif — et c'est un point que le jury peut relever.

```sql
-- À exécuter sur RDS, connecté en food_admin
CREATE USER food_app WITH PASSWORD '<un-autre-mot-de-passe-fort>';

GRANT CONNECT ON DATABASE food_impact TO food_app;
GRANT USAGE ON SCHEMA public TO food_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO food_app;

-- Pour que les tables créées plus tard soient couvertes aussi
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO food_app;
```

Depuis le conteneur :

```bash
docker exec -it -e PGPASSWORD='<mot-de-passe-maitre>' food_impact_db \
    psql -h food-impact-db.cta2iqgqyibu.eu-north-1.rds.amazonaws.com \
         -U food_admin -d food_impact
```

Utilise ensuite `food_app` dans le `.env` de l'application et sur Streamlit
Cloud. Garde `food_admin` pour l'ETL et les migrations.

---

## 7. Maîtriser les coûts

### Alerte de budget — à faire en premier

Console → **Billing and Cost Management** → **Budgets** → **Create budget** :

| Champ | Valeur |
|---|---|
| Budget type | Cost budget |
| Period | Monthly |
| Budgeted amount | **5 USD** |
| Alert threshold | 80 % of budgeted amount |
| Email | ton adresse |

### Estimation hors free tier

| Poste | Calcul | Mensuel |
|---|---|---|
| Instance `db.t4g.micro` | ~0,018 $/h × 730 h | ~13 $ |
| Stockage gp3 20 Go | ~0,115 $/Go | ~2,3 $ |
| Sauvegardes | ≤ taille de la base : gratuit | 0 $ |
| Transfert sortant | quelques Mo | ~0 $ |
| **Total** | | **~15 $/mois** |

Les tarifs exacts sont sur la page *AWS Pricing* de la région `eu-west-3` —
vérifie-les, ils évoluent.

### Après la soutenance

**Suspendre** (jusqu'à 7 jours, redémarrage automatique ensuite) :
RDS → `food-impact-db` → **Actions** → **Stop temporarily**.
Le calcul n'est plus facturé, le stockage reste.

**Supprimer définitivement** :
**Actions** → **Delete** → décoche *Create final snapshot* → tape `delete me`.

> C'est l'action à privilégier une fois la soutenance passée. Une instance
> oubliée coûte ~180 $/an.

---

## 8. Déployer l'application sur Streamlit Cloud

Uniquement si tu as retenu l'**option A** au §2 (security group ouvert).

1. <https://share.streamlit.io> → connexion avec ton compte GitHub
2. **New app** → dépôt `emelineroblot/jedha-final-project-fullstack`,
   branche `main`, fichier `app/streamlit_app.py`
3. **Advanced settings** → **Secrets**, au format TOML :

```toml
POSTGRES_HOST = "food-impact-db.cta2iqgqyibu.eu-north-1.rds.amazonaws.com"
POSTGRES_PORT = "5432"
POSTGRES_DB = "food_impact"
POSTGRES_USER = "food_app"
POSTGRES_PASSWORD = "<mot-de-passe-food_app>"
POSTGRES_SSLMODE = "require"
```

⚠️ **Les modèles ne sont pas versionnés** (`models/` est dans `.gitignore`).
Trois options :
- laisser l'application en **mode dégradé** — les pages Prédiction et Clusters
  s'auto-désactivent proprement, c'est prévu ;
- versionner les artefacts avec **Git LFS** (26,7 Mo au total, ça passe) ;
- ajouter une étape de régénération au démarrage (lent, déconseillé).

---

## 9. En cas de problème

| Symptôme | Cause probable | Correctif |
|---|---|---|
| `could not connect to server: Connection timed out` | Security group | §2 — refais **My IP**, ton IP a changé |
| `no pg_hba.conf entry ... no encryption` | `rds.force_ssl=1` actif | Ajoute `?sslmode=require` ou `POSTGRES_SSLMODE=require` |
| `FATAL: database "food_impact" does not exist` | *Initial database name* laissé vide (§1.8) | Connecte-toi à `postgres` et `CREATE DATABASE food_impact;` |
| `password authentication failed` | Caractère spécial dans le mot de passe | Encode-le en URL, ou change-le pour un mot de passe alphanumérique |
| `pg_restore: unsupported version` | Versions divergentes | Lance `pg_dump`/`pg_restore` **depuis le conteneur** (§5) |
| `permission denied for schema public` | Droits de `food_app` | Rejoue les `GRANT` du §6 |
| L'instance reste en `Creating` | Normal | Compte 5 à 10 min |

---

## 10. Checklist

```
□ Alerte de budget configurée (5 $)
□ Instance créée — Available, eu-west-3, db.t4g.micro
□ Initial database name = food_impact
□ Storage autoscaling DÉSACTIVÉ
□ Performance Insights et Enhanced monitoring DÉSACTIVÉS
□ Security group : règle My IP
□ rds.force_ssl = 1 appliqué, instance redémarrée
□ Endpoint reporté dans .env
□ Dump exporté et restauré
□ scripts/etl_pipeline.py --validate-only  → RÉUSSIE
□ Utilisateur food_app en lecture seule créé
□ Dumps supprimés du poste et du conteneur
□ Application testée sur RDS
□ Rappel agenda : supprimer l'instance après la soutenance
```

---

## Ce dont j'ai besoin pour prendre la suite

Une fois l'instance disponible, communique-moi :

1. **L'endpoint** — `food-impact-db.xxxx.eu-west-3.rds.amazonaws.com`
2. **L'option retenue au §2** — A (ouvert) ou B (fermé)

**Ne me transmets aucun mot de passe.** Tu les places toi-même dans `.env`, qui
n'est pas versionné. Je peux ensuite piloter la migration et la validation.
