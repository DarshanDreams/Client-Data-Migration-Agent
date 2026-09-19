# Client Data Migration Agent

An autonomous client-data migration agent for migrating inconsistent HR/CRM exports into a clean target employee schema.

The system combines deterministic business rules, local open-source semantic AI, validation, reconciliation, human-in-the-loop escalation, mock target integration, retries, rollback, and audit logging.

## Architecture

```text
CSV / Excel Files
       |
       v
+------------------+
| File Ingestion   |
+------------------+
       |
       v
+------------------+
| Field Mapper     |
| Rules + AI       |
+------------------+
       |
       v
+------------------+
| Decision Engine  |
+------------------+
       |
       +--------------------+
       |                    |
       v                    v
 Auto Approve           Human Review
       |                    |
       +---------+----------+
                 |
                 v
        +------------------+
        | Data Cleaning    |
        +------------------+
                 |
                 v
        +------------------+
        | Validation       |
        +------------------+
                 |
                 v
        +------------------+
        | Reconciliation   |
        +------------------+
                 |
                 v
        +------------------+
        | Mock Target API  |
        +------------------+
                 |
                 v
        +------------------+
        | Audit Trail      |
        +------------------+
```

## Key capabilities

### Multi-file ingestion

Supports:

- CSV
- XLSX
- XLS

Multiple source files can be ingested and reconciled into a single migration.

### Autonomous field mapping

The mapping engine combines:

1. deterministic business synonyms and normalization
2. local semantic similarity using:

```text
sentence-transformers/all-MiniLM-L6-v2
```

The AI model is open-source and runs locally. No external AI API key is required.

Deterministic rules take precedence for obvious mappings.

### Confidence-based decisions

The decision engine uses confidence and candidate margin to determine whether a mapping should be:

- automatically approved
- escalated to a human
- rejected

Unknown fields are not silently guessed.

### Data cleaning

The migration pipeline automatically normalizes:

- names
- email addresses
- phone numbers
- dates
- department names

### Validation

Required target fields and data formats are validated before migration.

Invalid records are escalated rather than silently pushed.

### Reconciliation

Records from multiple source systems are reconciled using:

- employee ID
- email

Duplicate records are merged when values agree.

Conflicting values create human-review escalations.

### Human-in-the-loop

The Streamlit interface provides a review queue for uncertain cases.

A consultant can:

- approve
- correct
- reject

an escalation.

Human decisions are recorded in the audit trail.

### Mock target integration

The target integration supports:

- per-record success/failure
- retry attempts
- failure reporting
- rollback after failed migration batches

### Auditability

Important migration events are stored in SQLite, including:

- migration start
- mapping decisions
- record cleaning
- validation failures
- escalation creation
- human corrections
- target push
- rollback
- migration completion

## Project structure

```text
client-data-migration-agent/
│
├── app/
│   ├── agent/
│   │   ├── cleaner.py
│   │   ├── decision_engine.py
│   │   ├── mapper.py
│   │   ├── orchestrator.py
│   │   ├── reconciler.py
│   │   └── validator.py
│   │
│   ├── api/
│   │   └── routes.py
│   │
│   ├── domain/
│   │   ├── enums.py
│   │   ├── models.py
│   │   └── schemas.py
│   │
│   ├── integrations/
│   │   └── target_api.py
│   │
│   ├── observability/
│   │   ├── logging.py
│   │   └── metrics.py
│   │
│   └── services/
│       ├── audit.py
│       ├── escalation.py
│       ├── ingestion.py
│       └── migration.py
│
├── data/
│   ├── source_crm.xlsx
│   ├── source_hr.csv
│   └── target_schema.json
│
├── evals/
│   ├── expected_decisions.json
│   ├── golden_cases.json
│   └── run_evals.py
│
├── tests/
│   ├── test_api.py
│   ├── test_audit.py
│   ├── test_cleaner_validator.py
│   ├── test_decision_engine.py
│   ├── test_ingestion.py
│   ├── test_mapper.py
│   ├── test_migration_service.py
│   ├── test_orchestrator.py
│   └── test_reconciler.py
│
├── ui/
│   ├── streamlit_app.py
│   └── components/
│       ├── audit_view.py
│       ├── dashboard.py
│       └── review_queue.py
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Local setup

### 1. Create virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure environment

Copy:

```text
.env.example
```

to:

```text
.env
```

The default configuration uses the local open-source semantic model.

No AI API key is required.

### 4. Run tests

```powershell
$env:PYTHONPATH="."
python -m pytest -q
```

### 5. Run evaluations

```powershell
$env:PYTHONPATH="."
python evals/run_evals.py
```

### 6. Start FastAPI

```powershell
$env:PYTHONPATH="."
python -m uvicorn app.main:app --reload
```

API:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

### 7. Start Streamlit

In another terminal:

```powershell
$env:PYTHONPATH="."
python -m streamlit run ui/streamlit_app.py
```

UI:

```text
http://localhost:8501
```

## Demo scenario

The included sample files contain intentionally inconsistent data.

Upload:

```text
data/source_hr.csv
data/source_crm.xlsx
```

The application demonstrates:

1. multi-file ingestion
2. automatic field mapping
3. data cleaning
4. duplicate reconciliation
5. conflict de
