# PhishSense

**Multimodal phishing website detection using URL, webpage structure, and visual signals.**

PhishSense builds a fixed-length feature vector from URL patterns, HTML DOM features, and a screenshot embedding, then trains an XGBoost classifier to distinguish phishing URLs from legitimate ones. The repository includes a dataset pipeline and a FastAPI backend with database-backed authentication and scan-record management.

> **Current limitation:** Model training and evaluation are implemented, but live scan prediction is not yet connected to the trained model. The scan-analysis orchestrator currently returns a placeholder result.

## ✨ Features

- Extracts URL and DOM features and captures visual embeddings with Playwright/OpenCLIP.
- Fuses 555 features: 20 URL, 23 DOM, and 512 visual values.
- Builds a balanced dataset from PhishTank and Tranco sources.
- Trains/evaluates XGBoost and saves the model, metrics, classification report, and feature importance.
- Provides a FastAPI backend with health, authentication, and scan-record routes.
- Uses SQLAlchemy, PostgreSQL, and Alembic for persistence and schema migrations.

## 🏗️ System Architecture

```mermaid
flowchart LR
    subgraph Data["Dataset and model training"]
        A[PhishTank URLs]
        B[Tranco domains]
        C[Clean, validate, sample]
        D[Playwright capture]
        E[URL features]
        F[DOM features]
        G[OpenCLIP screenshot embedding]
        H[Feature fusion]
        I[Training dataset]
        J[XGBoost training and evaluation]
        K[Model and reports]
        A --> C
        B --> C
        C --> D
        D --> E
        D --> F
        D --> G
        E --> H
        F --> H
        G --> H
        H --> I --> J --> K
    end

    subgraph API["FastAPI backend"]
        L[API clients]
        M[FastAPI /api/v1]
        N[Auth and scan-record routes]
        O[(PostgreSQL)]
        P[Scan analysis]
        Q[Prediction placeholder]
        L --> M --> N --> O
        N -. analysis flow .-> P --> Q
    end
```

## 🧰 Technology Stack

| Area | Technologies |
|---|---|
| Backend and API | Python, FastAPI, Uvicorn |
| Database | PostgreSQL, SQLAlchemy, Alembic, psycopg |
| Machine learning | XGBoost, scikit-learn, NumPy |
| Webpage analysis | Playwright, Chromium, BeautifulSoup, lxml |
| Visual embeddings | OpenCLIP, PyTorch, Pillow |
| Development | Git, GitHub, VS Code |

## 📁 Project Structure

```text
PhishSense/
├── backend/
│   ├── app/
│   │   ├── api/, core/, db/, middleware/
│   │   ├── dataset/, feature_extraction/, ml/
│   │   └── models/, repositories/, schemas/, services/
│   ├── alembic/                 # Database migrations
│   ├── datasets/raw/            # Downloaded source files
│   ├── datasets/processed/      # URL manifests and model-ready data
│   ├── models/                  # Saved model and feature importance
│   ├── reports/                 # Evaluation outputs
│   ├── requirements/base.txt
│   └── train_model.py
├── deployment/, docs/, extension/, frontend/
├── ml_training/, notebooks/
├── storage/screenshots/
├── tests/
└── README.md
```

## 🚀 Installation

### Prerequisites

- Git and Python.
- PostgreSQL for database-backed API features.
- Internet access for dataset downloads and the initial OpenCLIP model-weight download.

### 1. Clone the repository

```bash
git clone https://github.com/Anonymous12P/PhishSense.git
cd PhishSense
```

### 2. Create and activate a virtual environment

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install requirements and Chromium

Run these commands from the repository root:

```bash
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements/base.txt
python -m playwright install chromium
```

## ⚙️ Configuration (.env)

Create `backend/.env`. The application and Alembic load settings from the current working directory, so run backend commands from `backend/`.

```dotenv
APP_NAME=PhishSense API
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=false
HOST=127.0.0.1
PORT=8000

DATABASE_URL=postgresql+psycopg://phishsense_user:change-me@localhost:5432/phishsense
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

PHISHSENSE_DATASET_WORKERS=20
PHISHSENSE_DATASET_SEED=42
```

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string; needed for migrations and database-backed API routes. |
| `SECRET_KEY` | Private key used to sign and validate access tokens. |
| `PHISHSENSE_DATASET_WORKERS` | Optional positive integer controlling dataset-build concurrency. |
| `PHISHSENSE_DATASET_SEED` | Optional integer controlling URL sampling; defaults to `42`. |
| `APP_NAME`, `APP_VERSION`, `ENVIRONMENT`, `DEBUG`, `HOST`, `PORT` | Application metadata and runtime settings. |
| `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT algorithm and token lifetime. |

Replace the example credentials and secret with secure local values. Do not commit `.env` or use development secrets in a deployed environment.

## ▶️ How to Run

### Database setup

Create a PostgreSQL role and database using your PostgreSQL administration tools. For example, in `psql`:

```sql
CREATE ROLE phishsense_user WITH LOGIN PASSWORD 'change-me';
CREATE DATABASE phishsense OWNER phishsense_user;
```

With `backend/` as the current directory and `.env` configured, apply migrations:

```bash
alembic upgrade head
```

### Build the dataset

```bash
python -m app.ml.build_training_dataset
```

This builds a balanced PhishTank/Tranco URL manifest, captures pages, and writes multimodal features. It may take time and contacts external websites; run it in an isolated environment.

### Train the model

```bash
python train_model.py
```

Expects `backend/datasets/processed/processed_dataset.csv`; writes artifacts under `backend/models/` and `backend/reports/`.

### Start the API

```bash
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Interactive documentation is available at `/docs`, and ReDoc is available at `/redoc`.

Implemented routes include `GET /api/v1/health`, registration and login under `/api/v1/auth`, and authenticated scan-record CRUD under `/api/v1/scans`. Proposed `/predict`, `/scan`, and analytics routes are not implemented. The health endpoint confirms the API process is responding; it does not verify database or model readiness.

## 🧪 Machine Learning Pipeline

| Stage | Description |
|---|---|
| Data selection | Samples phishing URLs from PhishTank and legitimate domains from Tranco. The current target is 25,000 records per class. |
| Feature extraction | Captures webpages and extracts URL, DOM, and screenshot features. |
| Feature fusion | Produces a fixed-order vector of 555 values (20 URL + 23 DOM + 512 visual). |
| Training | Trains an XGBoost binary classifier using an 80/20 stratified train/test split. |
| Evaluation | Calculates accuracy, precision, recall, F1 score, ROC AUC, confusion matrix, and a classification report. |
| Artifacts | Saves `phishing_xgboost.json`, `feature_importance.json`, `metrics.json`, and `classification_report.txt`. |

Labels are `0` for legitimate and `1` for phishing. The dataset builder checkpoints progress to support resuming an interrupted run. SHAP explanations are not currently implemented; saved feature importance is a model-level artifact, not an explanation for an individual prediction.

## 📊 Performance Results

Metrics below are from the current evaluation artifact in `backend/reports/metrics.json`. Results describe that dataset and split; they are not a guarantee of performance on future URLs.

| Metric | Result |
|---|---:|
| Accuracy | **97.71%** |
| Precision | **98.30%** |
| Recall | **97.10%** |
| F1 Score | **97.70%** |
| ROC AUC | **99.60%** |

## 🗺️ Roadmap / Future Improvements

- Connect the trained model to the live scan-analysis workflow and define prediction API contracts.
- Add persisted scan lifecycle status and robust error reporting for partial analysis.
- Add SHAP-based explanations for individual predictions.
- Improve evaluation with time-based and domain-separated test sets.
- Add analytics endpoints and production deployment/monitoring resources.
- Develop the frontend and browser extension workspaces.

## 👥 Contributors

Contributions are welcome. Discuss substantial changes in an issue, add or update tests, and do not commit secrets or private data. See the [GitHub contributors page](https://github.com/Anonymous12P/PhishSense/graphs/contributors) for contributors.

## 📄 License

The FastAPI OpenAPI metadata identifies Apache License 2.0, but the repository currently has no top-level `LICENSE` file. Add the canonical license file before relying on an explicit repository-wide license grant.
