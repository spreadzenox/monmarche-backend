import pytest

from app.services.normalization_service import NormalizationService


@pytest.fixture
def service() -> NormalizationService:
    return NormalizationService()


def test_normalize_tomates(service: NormalizationService):
    assert service.normalize("Tomates") == "tomate"


def test_normalize_tomate_cerise(service: NormalizationService):
    assert service.normalize("tomate cerise") == "tomate cerise"


def test_normalize_huile_olive(service: NormalizationService):
    assert service.normalize("Huile d’olive") == "huile olive"


def test_normalize_pommes_de_terre(service: NormalizationService):
    assert service.normalize("Pommes de terre") == "pomme de terre"


def test_normalize_gousses_ail(service: NormalizationService):
    assert service.normalize("Gousses d'ail") == "ail"


def test_normalize_oignons_jaunes(service: NormalizationService):
    assert service.normalize("Oignons jaunes") == "oignon jaune"


def test_normalize_sel_fin(service: NormalizationService):
    assert service.normalize("Sel fin") == "sel"


def test_normalize_poivre_noir(service: NormalizationService):
    assert service.normalize("Poivre noir") == "poivre"
