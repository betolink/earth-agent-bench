import pytest

from earth_agent_bench.oracles.virtualizability import VirtualizabilityOracle
from earth_agent_bench.oracles.services import ServiceCatalog
from earth_agent_bench.oracles.service_matrix import build_matrix

PARQUET = "benchmark/data/virtualizability.parquet"
SERVICES = "benchmark/oracles/services.yaml"


@pytest.fixture(scope="module")
def oracle():
    return VirtualizabilityOracle(PARQUET)


@pytest.fixture(scope="module")
def catalog():
    return ServiceCatalog(SERVICES)


def test_parquet_has_collections(oracle):
    assert len(oracle.collections()) >= 80


def test_known_grades(oracle):
    assert oracle.grade("TEMPO_NO2_L3") == "B"
    assert oracle.virtualizable("TEMPO_NO2_L3")
    assert oracle.grade("MODISA_L3m_CHL") == "D"
    assert not oracle.virtualizable("MODISA_L3m_CHL")


def test_unknown_collection(oracle):
    assert oracle.grade("NOT_A_COLLECTION") is None
    assert not oracle.virtualizable("NOT_A_COLLECTION")
    outlook = oracle.virtualization_outlook("NOT_A_COLLECTION")
    assert outlook["in_oracle"] is False
    assert outlook["c1_available"] is False


def test_criterion_recorded(oracle):
    criterion = oracle.criterion("MODISA_L3m_CHL")
    assert criterion and "chunk shape differs" in criterion


def test_dmrpp_flag(oracle):
    assert oracle.dmrpp("TEMPO_NO2_L3")


def test_matrix_blocks_c1_for_grade_d(catalog, oracle):
    matrix = build_matrix("MODISA_L3m_CHL", oracle, catalog)
    assert matrix["patterns"]["C1"]["available"] is False
    assert matrix["virtualization_outlook"]["grade"] == "D"


def test_matrix_recommends_c1_for_grade_b(catalog, oracle):
    matrix = build_matrix("AU_SI12", oracle, catalog)
    assert matrix["patterns"]["C1"]["available"] is True
    assert matrix["best_pattern"] == "C1"


def test_matrix_prefers_c1_over_opendap(catalog, oracle):
    matrix = build_matrix("MUR-JPL-L4-GLOB-v4.1", oracle, catalog)
    assert matrix["best_pattern"] == "C1"
    assert "S3" in matrix["recommended_patterns"]
    assert matrix["recommended_patterns"].index("C1") < matrix["recommended_patterns"].index("S2")


def test_matrix_unknown_collection_falls_back(catalog, oracle):
    matrix = build_matrix("VNP46A2", oracle, catalog)
    assert matrix["patterns"]["C1"]["available"] is False
    assert matrix["best_pattern"] in {"S3", "S2", "S1"}
