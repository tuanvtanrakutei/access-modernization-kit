from pathlib import Path

from adapters.base import AcquisitionRequest
from adapters.msaccess_vcs.adapter import MsAccessVcsAdapter

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "acquisition" / "msaccess-vcs"
CLASSIFICATION = {"topology": "monolith", "frontend_format": "exported", "source_availability": "exported_only", "backend_kinds": ["embedded_access"]}

def _request(root: Path) -> AcquisitionRequest:
    return AcquisitionRequest("SYN", CLASSIFICATION, ({
        "id": "VCS_EXPORT", "kind": "producer_export", "role": "frontend", "acquisition": "imported", "required": True,
        "source_ref": {"type": "local_path", "value": "app.src"}, "format": "msaccess-vcs",
    },), root)

def test_v500_descriptive_extensions_are_mapped() -> None:
    adapter = MsAccessVcsAdapter()
    plan = adapter.plan(_request(FIXTURE / "complete"))
    result = adapter.acquire(plan)
    contribution = adapter.normalize(result)
    assert contribution["provenance"]["producer"] == "msaccess-vcs-addin"
    assert contribution["provenance"]["producer_format_version"] == "5.0.0"
    assert contribution["code"]["vba"]
    assert contribution["ui"]["forms"]
    assert contribution["code"]["access_sql"]
    assert "vcs-index.idx" not in str(contribution)

def test_unsupported_format_is_invalid() -> None:
    adapter = MsAccessVcsAdapter()
    result = adapter.acquire(adapter.plan(_request(FIXTURE / "incomplete")))
    assert result.status == "INVALID"
    assert result.failures[0]["reason"] == "UNSUPPORTED_PRODUCER_FORMAT"
