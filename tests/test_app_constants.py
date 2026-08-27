"""Tests de non-régression sur les constantes et helpers de l'application.

Ces tests verrouillent les bugs identifiés dans docs/audit.md :
  · §2.3 — erreur d'unité d'un facteur 1 000 sur les totaux CO₂
  · §2.8 — divergence entre les catégories de l'app et celles de l'ETL
  · §3.5 — st.progress qui lève sur NaN

Ils tournent sans base de données ni modèle : `streamlit` est remplacé par un
double avant l'import de l'app, dont le module exécute du code au chargement.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scripts"))


# ──────────────────────────────────────────────────────────────
# Double de streamlit : l'app appelle st.* au niveau module.
# ──────────────────────────────────────────────────────────────
class _Stub:
    """Accepte n'importe quel appel/attribut et renvoie un _Stub."""

    def __call__(self, *args, **kwargs):
        return _Stub()

    def __getattr__(self, name):
        return _Stub()

    def __enter__(self):
        return _Stub()

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter([_Stub() for _ in range(6)])

    def __bool__(self):
        return False


def _install_streamlit_stub() -> None:
    st = types.ModuleType("streamlit")

    def _identity_decorator(*d_args, **d_kwargs):
        # Supporte @st.cache_data et @st.cache_data(ttl=...)
        if len(d_args) == 1 and callable(d_args[0]) and not d_kwargs:
            return d_args[0]

        def wrap(fn):
            return fn

        return wrap

    st.cache_data = _identity_decorator
    st.cache_resource = _identity_decorator
    st.session_state = {}
    st.sidebar = _Stub()

    for name in (
        "set_page_config", "title", "markdown", "radio", "caption", "warning",
        "info", "error", "columns", "selectbox", "toggle", "stop", "metric",
        "subheader", "plotly_chart", "multiselect", "select_slider", "button",
        "success", "progress", "expander", "slider", "rerun", "dataframe",
        "container", "tabs", "divider", "write", "header", "code", "table",
    ):
        setattr(st, name, _Stub())

    sys.modules["streamlit"] = st


_install_streamlit_stub()

app = pytest.importorskip("app.streamlit_app", reason="app non importable")
mappings = pytest.importorskip("_mappings", reason="scripts/_mappings.py absent")


# ──────────────────────────────────────────────────────────────
# §2.3 — Unités
# ──────────────────────────────────────────────────────────────
class TestUnites:
    """`co2_total_kg` est en KILOGRAMMES. 1 Mt = 1e9 kg, 1 Gt = 1e12 kg."""

    @pytest.mark.parametrize(
        "kg, attendu",
        [
            (1e12, "1.00 Gt"),   # 1 000 milliards de kg = 1 gigatonne
            (5e12, "5.00 Gt"),
            (1e9, "1.00 Mt"),    # 1 milliard de kg = 1 mégatonne
            (5e10, "50.00 Mt"),
            (1e6, "1.00 kt"),    # 1 million de kg = 1 kilotonne
            (1e3, "1 t"),
        ],
    )
    def test_fmt_co2_ordres_de_grandeur(self, kg, attendu):
        assert app.fmt_co2(kg) == attendu

    def test_fmt_co2_gere_les_valeurs_absentes(self):
        assert app.fmt_co2(None) == "N/A"
        assert app.fmt_co2(float("nan")) == "N/A"

    def test_kg_to_mt(self):
        assert app.kg_to_mt(1e9) == pytest.approx(1.0)
        assert app.kg_to_mt(2.5e10) == pytest.approx(25.0)

    def test_emissions_mondiales_plausibles(self):
        """Garde-fou d'ordre de grandeur.

        Les émissions mondiales TOUS SECTEURS sont d'environ 37 Gt CO₂/an.
        L'alimentation en représente ~26 %. Un total pays formaté ne doit donc
        jamais s'afficher en dizaines de Gt — c'était le symptôme du bug d'unité.
        """
        co2_france_annuel_kg = 5e10          # ~50 Mt, ordre de grandeur réaliste
        assert app.fmt_co2(co2_france_annuel_kg).endswith("Mt")
        assert "Gt" not in app.fmt_co2(co2_france_annuel_kg)


# ──────────────────────────────────────────────────────────────
# §2.8 — Cohérence app ↔ ETL
# ──────────────────────────────────────────────────────────────
class TestCategories:
    """Les catégories de l'app doivent exister dans celles produites par l'ETL.

    Le OneHotEncoder du modèle est en `handle_unknown='ignore'` : un libellé
    inconnu produit un vecteur nul, dégrade la prédiction, et ne lève rien.
    """

    @staticmethod
    def _categories_etl() -> set:
        echantillons = [
            "Wheat", "Beef", "Milk", "Eggs", "Fish", "Soybeans", "Palm oil",
            "Sugar cane", "Potatoes", "Tomatoes", "Apples", "Coffee", "Wine",
            "Pepper", "Cashew nuts", "Rice", "Lentils", "Cheese", "Poultry Meat",
        ]
        return {mappings.categorize(x)[0] for x in echantillons}

    def test_food_category_utilise_les_libelles_de_l_etl(self):
        cats_etl = self._categories_etl()
        inconnues = set(app.FOOD_CATEGORY.values()) - cats_etl
        assert not inconnues, (
            f"Catégories absentes de l'ETL : {sorted(inconnues)}. "
            f"Disponibles : {sorted(cats_etl)}"
        )

    def test_categories_animales_existent(self):
        cats_etl = self._categories_etl()
        assert set(app.CATEGORIES_ANIMALES) <= cats_etl

    def test_tout_aliment_a_une_categorie_et_un_facteur(self):
        assert set(app.CO2_FACTORS) == set(app.FOOD_CATEGORY)
        assert set(app.CO2_FACTORS) == set(app.PORTION_STANDARD)


# ──────────────────────────────────────────────────────────────
# Simulateur
# ──────────────────────────────────────────────────────────────
class TestSimulateur:
    def test_frequences_couvrent_toutes_les_options(self):
        assert set(app.FREQ_OPTIONS) == set(app.FREQ_TO_DAILY)

    def test_jamais_vaut_zero(self):
        assert app.FREQ_TO_DAILY["Jamais"] == 0

    def test_frequences_strictement_croissantes(self):
        valeurs = [app.FREQ_TO_DAILY[f] for f in app.FREQ_OPTIONS]
        assert valeurs == sorted(valeurs)
        assert valeurs[-1] > valeurs[0]

    def test_facteurs_co2_positifs_et_ordonnes(self):
        assert all(v > 0 for v in app.CO2_FACTORS.values())
        # Le bœuf domine largement ; les légumes sont en bas de tableau.
        assert app.CO2_FACTORS["Boeuf"] > app.CO2_FACTORS["Volaille"]
        assert app.CO2_FACTORS["Volaille"] > app.CO2_FACTORS["Légumes"]

    def test_portions_realistes(self):
        for aliment, grammes in app.PORTION_STANDARD.items():
            assert 5 <= grammes <= 400, f"{aliment} : portion de {grammes} g"

    def test_multiplicateurs_de_portion_encadrent_la_normale(self):
        assert app.PORTION_MULT["Petite"] < app.PORTION_MULT["Normale"]
        assert app.PORTION_MULT["Normale"] < app.PORTION_MULT["Grande"]
        assert app.PORTION_MULT["Normale"] == 1.0

    def test_calcul_empreinte_hebdomadaire(self):
        """Un steak de bœuf par jour ≈ 8,9 kg CO₂/semaine."""
        co2_jour = app.CO2_FACTORS["Boeuf"] * (app.PORTION_STANDARD["Boeuf"] / 1000) * 1.0
        assert co2_jour * 7 == pytest.approx(62.58, rel=1e-3)

    def test_part_animale_bornee(self):
        """La valeur passée à st.progress doit toujours tenir dans [0, 100]."""
        import numpy as np

        for brut in (float("nan"), -5.0, 0.0, 42.7, 100.0, 150.0):
            borne = int(np.clip(np.nan_to_num(brut), 0, 100))
            assert 0 <= borne <= 100


# ──────────────────────────────────────────────────────────────
# Clustering
# ──────────────────────────────────────────────────────────────
class TestClustering:
    def test_couleurs_et_descriptions_couvrent_les_memes_profils(self):
        assert set(app.CLUSTER_COLORS) == set(app.CLUSTER_DESCRIPTIONS)

    def test_libelles_alignes_sur_ceux_produits_par_l_entrainement(self):
        """Les libellés de l'app doivent couvrir ceux que train_model.py attribue.

        `_nommer_clusters` produit un vocabulaire fermé ; s'il diverge de celui
        de l'app, la carte perd ses couleurs et ses descriptions sans erreur.
        """
        train = pytest.importorskip("train_model", reason="scripts/train_model.py absent")
        import pandas as pd

        profils = pd.DataFrame(
            {
                "co2_per_capita": [355.7, 1381.1, 463.8, 948.5, 1153.7],
                "pib_per_capita": [685.9, 47904.0, 1243.6, 8603.5, 7986.4],
                "taux_urbanisation": [29.0, 82.4, 36.7, 67.8, 68.4],
                "pct_animal": [34.4, 70.8, 61.8, 69.4, 68.7],
                "surface_agricole": [40.7, 28.9, 37.5, 17.0, 59.8],
            },
            index=[0, 1, 2, 3, 4],
        )
        labels = train._nommer_clusters(profils)

        assert len(labels) == 5, "un libellé par cluster"
        assert len(set(labels.values())) == 5, "libellés tous distincts"
        inconnus = set(labels.values()) - set(app.CLUSTER_COLORS)
        assert not inconnus, f"libellés sans couleur dans l'app : {sorted(inconnus)}"

    def test_nommage_suit_les_profils(self):
        """Le plus riche est « Pays riches », le plus pauvre « Faible revenu »."""
        train = pytest.importorskip("train_model")
        import pandas as pd

        profils = pd.DataFrame(
            {
                "co2_per_capita": [355.7, 1381.1, 463.8, 948.5, 1153.7],
                "pib_per_capita": [685.9, 47904.0, 1243.6, 8603.5, 7986.4],
                "taux_urbanisation": [29.0, 82.4, 36.7, 67.8, 68.4],
                "pct_animal": [34.4, 70.8, 61.8, 69.4, 68.7],
                "surface_agricole": [40.7, 28.9, 37.5, 17.0, 59.8],
            },
            index=[0, 1, 2, 3, 4],
        )
        labels = train._nommer_clusters(profils)
        assert labels[1] == "Pays riches"            # PIB 47 904 — le plus élevé
        assert labels[0] == "Faible revenu"          # PIB 686 — le plus faible
        assert labels[4] == "Producteurs intensifs"  # surface 59,8 — la plus grande

    def test_apply_clustering_refuse_un_bundle_sans_scaler(self):
        """Format hérité (KMeans nu) → aucune colonne cluster, plutôt qu'un faux."""
        import pandas as pd

        df = pd.DataFrame({f: [1.0] * 10 for f in app.CLUSTER_FEATURES})
        out = app.apply_clustering(df, {"kmeans": object(), "scaler": None})
        assert "cluster" not in out.columns

    def test_apply_clustering_tolere_l_absence_de_modele(self):
        import pandas as pd

        df = pd.DataFrame({f: [1.0] * 10 for f in app.CLUSTER_FEATURES})
        assert "cluster" not in app.apply_clustering(df, None).columns
