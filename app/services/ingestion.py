from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


@dataclass
class FileProfile:
    filename: str
    file_type: str
    row_count: int
    column_count: int
    columns: list[str]
    missing_by_column: dict[str, int]
    duplicate_rows: int
    sample_rows: list[dict] = field(default_factory=list)


@dataclass
class IngestedFile:
    filename: str
    dataframe: pd.DataFrame
    profile: FileProfile


class IngestionError(Exception):
    """Raised when a source file cannot be safely ingested."""


class DataIngestionService:

    def ingest(self, file_path: str | Path) -> IngestedFile:
        path = Path(file_path)

        self._validate_file(path)

        try:
            dataframe = self._read_file(path)
        except Exception as exc:
            raise IngestionError(
                f"Failed to read '{path.name}': {exc}"
            ) from exc

        dataframe = self._normalize_column_names(dataframe)

        profile = self._profile(path, dataframe)

        return IngestedFile(
            filename=path.name,
            dataframe=dataframe,
            profile=profile,
        )

    def ingest_multiple(
        self,
        file_paths: list[str | Path],
    ) -> list[IngestedFile]:

        if not file_paths:
            raise IngestionError("No source files were provided.")

        return [self.ingest(path) for path in file_paths]

    @staticmethod
    def _validate_file(path: Path) -> None:
        if not path.exists():
            raise IngestionError(
                f"File does not exist: {path}"
            )

        if not path.is_file():
            raise IngestionError(
                f"Path is not a file: {path}"
            )

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise IngestionError(
                f"Unsupported file type: {path.suffix}. "
                f"Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

    @staticmethod
    def _read_file(path: Path) -> pd.DataFrame:

        extension = path.suffix.lower()

        if extension == ".csv":
            return pd.read_csv(path)

        if extension in {".xlsx", ".xls"}:
            return pd.read_excel(path)

        raise IngestionError(
            f"Unsupported file extension: {extension}"
        )

    @staticmethod
    def _normalize_column_names(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()

        dataframe.columns = [
            str(column).strip()
            for column in dataframe.columns
        ]

        return dataframe

    @staticmethod
    def _profile(
        path: Path,
        dataframe: pd.DataFrame,
    ) -> FileProfile:

        missing = (
            dataframe.isna()
            .sum()
            .astype(int)
            .to_dict()
        )

        sample = (
            dataframe.head(5)
            .where(dataframe.notna(), None)
            .to_dict(orient="records")
        )

        return FileProfile(
            filename=path.name,
            file_type=path.suffix.lower().replace(".", ""),
            row_count=len(dataframe),
            column_count=len(dataframe.columns),
            columns=list(dataframe.columns),
            missing_by_column=missing,
            duplicate_rows=int(
                dataframe.duplicated().sum()
            ),
            sample_rows=sample,
        )