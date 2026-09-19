from pathlib import Path

from app.services.ingestion import DataIngestionService


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_csv_ingestion():
    service = DataIngestionService()

    result = service.ingest(DATA_DIR / "source_hr.csv")

    assert result.filename == "source_hr.csv"
    assert result.profile.row_count == 3
    assert result.profile.column_count == 8
    assert "Employee No" in result.profile.columns


def test_excel_ingestion():
    service = DataIngestionService()

    result = service.ingest(DATA_DIR / "source_crm.xlsx")

    assert result.filename == "source_crm.xlsx"
    assert result.profile.row_count == 3
    assert result.profile.column_count == 8
    assert "emp_id" in result.profile.columns


def test_multiple_file_ingestion():
    service = DataIngestionService()

    results = service.ingest_multiple(
        [
            DATA_DIR / "source_hr.csv",
            DATA_DIR / "source_crm.xlsx",
        ]
    )

    assert len(results) == 2
    assert results[0].filename == "source_hr.csv"
    assert results[1].filename == "source_crm.xlsx"