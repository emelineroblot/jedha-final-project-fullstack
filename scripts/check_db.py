#!/usr/bin/env python
"""Diagnostic de la connexion à la base — local ou AWS RDS.

Fournisseur-agnostique : la cible est entièrement dérivée des variables
`POSTGRES_*` du fichier `.env`, donc ce script teste indifféremment le conteneur
Docker local ou l'instance AWS RDS de production.

Usage
-----
    python scripts/check_db.py           # cible du .env (POSTGRES_*)
    python scripts/check_db.py --master  # cible le compte maître (RDS_*)

Sortie : code 0 si tout est vert, 1 sinon — utilisable en CI ou en pré-démo.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TABLES_ATTENDUES = {
    "dim_pays": 100,
    "dim_temps": 60,
    "dim_produits": 50,
    "dim_socio_economique": 5_000,
    "fait_impact": 10,
    "fait_production": 500_000,
    "fait_impact_pays_annee": 200_000,
}

OK, KO, INFO = "\u2713", "\u2717", "\u2139"


def connect_args(master: bool) -> dict:
    prefix = "RDS" if master else "POSTGRES"
    fallback = {
        "HOST": "localhost", "PORT": "5432", "DB": "food_impact",
        "USER": "food_user", "PASSWORD": "food_pass", "SSLMODE": "prefer",
    }
    get = lambda k: os.getenv(f"{prefix}_{k}", fallback[k])  # noqa: E731
    return {
        "host": get("HOST"), "port": int(get("PORT")), "dbname": get("DB"),
        "user": get("USER"), "password": get("PASSWORD"),
        "sslmode": get("SSLMODE"), "connect_timeout": 15,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--master", action="store_true",
                        help="utiliser le compte maître RDS_* au lieu de POSTGRES_*")
    args = parser.parse_args()

    ca = connect_args(args.master)
    print(f"Cible : {ca['user']}@{ca['host']}:{ca['port']}/{ca['dbname']}")
    print(f"        sslmode={ca['sslmode']}\n")

    try:
        engine = create_engine("postgresql+psycopg2://", connect_args=ca,
                               pool_pre_ping=True)
        conn = engine.connect()
    except Exception as exc:  # noqa: BLE001
        print(f"{KO} Connexion impossible : {str(exc).splitlines()[0][:140]}")
        print("\n  Pistes :")
        print("   · base locale éteinte  → docker compose -f docker/docker-compose.yml up -d")
        print("   · RDS injoignable      → security group : ton IP publique a-t-elle changé ?")
        print("   · base inexistante     → cf. docs/deploiement_aws.md §9")
        return 1

    tout_ok = True
    with conn:
        version = conn.execute(text("SELECT version()")).scalar()
        print(f"{OK} Connecté — {version.split(',')[0]}")

        ssl_actif = conn.execute(text("SHOW ssl")).scalar()
        if ssl_actif == "on":
            print(f"{OK} Chiffrement TLS actif")
        elif ca["host"] in ("localhost", "127.0.0.1"):
            print(f"{INFO} TLS inactif — normal en local")
        else:
            print(f"{KO} TLS INACTIF sur une base distante")
            tout_ok = False

        print()
        for table, minimum in TABLES_ATTENDUES.items():
            try:
                n = conn.execute(text(f"SELECT COUNT(*) FROM public.{table}")).scalar()
            except Exception:  # noqa: BLE001
                print(f"{KO} {table:24s} absente")
                tout_ok = False
                continue
            marque = OK if n >= minimum else KO
            tout_ok &= n >= minimum
            print(f"{marque} {table:24s} {n:>10,} lignes (min {minimum:,})")

        print()
        annees = conn.execute(text("""
            SELECT MIN(t.annee), MAX(t.annee)
            FROM fait_impact_pays_annee f JOIN dim_temps t ON f.annee_id = t.annee_id
        """)).fetchone()
        print(f"{INFO} Années couvertes : {annees[0]}–{annees[1]}")

        taille = conn.execute(text(
            "SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar()
        print(f"{INFO} Taille de la base : {taille}")

        droits = conn.execute(text("""
            SELECT has_table_privilege(current_user, 'public.dim_pays', 'INSERT')
        """)).scalar()
        if droits:
            print(f"{INFO} Compte en ÉCRITURE — réservé à l'ETL et aux migrations")
        else:
            print(f"{OK} Compte en lecture seule — adapté à l'application")

    engine.dispose()
    print("\n" + ("Diagnostic RÉUSSI" if tout_ok else "Diagnostic ÉCHOUÉ"))
    return 0 if tout_ok else 1


if __name__ == "__main__":
    sys.exit(main())
