# SMARTROSE: IoT and ML Decision Support for Greenhouse Rose Cultivation

SMARTROSE is an enterprise-grade, multi-component decision support system designed to monitor and optimize greenhouse rose cultivation. By integrating Internet of Things (IoT) sensor networks with Machine Learning (ML) orchestration and a cross-platform mobile application, the system bridges the gap between raw environmental telemetry and actionable agricultural management.

### Organization Directory
**[View the complete SMARTROSE GitHub Organization](https://github.com/25-26J-299)**

### Research Portfolio
**[View the SMARTROSE Research Portfolio](https://smartrose-portfolio.vercel.app/)**
*Comprehensive documentation, research methodology, and academic artifacts.*

---

## 1. System Architecture

The SMARTROSE platform utilizes a distributed micro-architecture, comprising a centralized Application Programming Interface (API) gateway, a presentation layer, and decoupled machine learning service modules.

**Data Pipeline:**
`Hardware Sensors` -> `ESP32/LoRa Gateway` -> `FastAPI Backend` -> `MongoDB` -> `ML Inference Engine` -> `Flutter Client`

**System Diagram:**
[View Full Architecture Diagram](https://mysliit-my.sharepoint.com/:i:/g/personal/it22326522_my_sliit_lk/IQBiADF5Sib5T6ZpUIdtIAokAeALnCUDy57DtLRrc1P23lo?e=3xmeR7)

    ┌────────────────────────────────────────────────────────────────────────────┐
    │                           Field / Lab Environment                          │
    │  IoT Sensors (NPK, EC, pH, soil temp/moisture, air temp/humidity, etc.)    │
    └───────────────────────────────┬────────────────────────────────────────────┘
                                    │ HTTP/JSON Payload
                                    ▼
    ┌────────────────────────────────────────────────────────────────────────────┐
    │                     smartrose_backend (FastAPI + MongoDB)                  │
    │                                                                            │
    │  API Routing Layer (v1)                                                    │
    │   - INM  : /api/v1/inm/* │
    │   - EOSM : /api/v1/eosm/* │
    │   - EDAS : /api/v1/edas/* │
    │   - FM   : /api/v1/fm/* │
    │                                                                            │
    │  ML Inference Service Layer                                                │
    │   - INM  : app/ml/inm/inm_inference.py                                     │
    │   - EOSM : app/ml/eosm/eosm_inference.py                                   │
    │   - FM   : app/ml/fm/fm_inference.py                                       │
    │   - EDAS : app/services/edas_ml_service.py                                 │
    │                                                                            │
    │  Persistence Layer: MongoDB Collections (telemetry, predictions, history)  │
    └────────────────────────────────────────────────────────────────────────────┘
                                    │ RESTful JSON / WebSockets
                                    ▼
    ┌────────────────────────────────────────────────────────────────────────────┐
    │                  smartrose_frontend (Flutter Client)                       │
    │  - Data visualization, module management, and actionable alerts            │
    └────────────────────────────────────────────────────────────────────────────┘

---

## 2. Repository Structure

The workspace is organized into two system-level repositories and four independent subsystem repositories.

### System Repositories
| Component | Repository Link | Description |
| :--- | :--- | :--- |
| **Backend Gateway** | [`smartrose_backend`](https://github.com/25-26J-299/smartrose_backend.git) | Unified FastAPI + MongoDB backend gateway. Entry point: `app/main.py`. |
| **Mobile Client** | [`smartrose_frontend`](https://github.com/25-26J-299/smartrose_frontend.git) | Flutter-based presentation layer and API client. Entry point: `lib/main.dart`. |

### Subsystem Repositories (ML Artifacts, Training Data, Documentation)
| Module | Repository Link | Focus Area |
| :--- | :--- | :--- |
| **INM** | [`smartrose-inm`](https://github.com/25-26J-299/smartrose-inm.git) | Intelligent Nutrient Management |
| **EOSM** | [`smartrose-eosm`](https://github.com/25-26J-299/smartrose-eosm.git) | Energy-Optimized Stress Monitoring |
| **EDAS** | [`smartrose-edas`](https://github.com/25-26J-299/smartrose-edas.git) | Early Disease Alerting System |
| **FM** | [`smartrose-fm`](https://github.com/25-26J-299/smartrose-fm.git) | Freshness Monitoring |

---

## 3. Subsystem Specifications

### Intelligent Nutrient Management (INM)
* **Objective:** Automate nutrient management utilizing real-time sensor data and a 24-hour Electrical Conductivity (EC) forecasting model.
* **Telemetry Inputs:** N, P, K, EC, pH, soil temperature, soil moisture, air temperature, air humidity.
* **System Outputs:** 24h EC ML prediction, rule-based recommendations (EC status, pH action, NPK recommendations), and action logging.
* **Backend Integration:**
    * Routes: `GET /api/v1/inm/status`, `POST /api/v1/inm/sensor-data`, `POST /api/v1/inm/action`
    * Inference Pipeline: `app/ml/inm/inm_inference.py`

### Energy-Optimized Stress Monitoring (EOSM)
* **Objective:** Classify plant stress states dynamically using environmental telemetry and persist historical inference data.
* **Telemetry Inputs:** Temperature, humidity, UV voltage, soil moisture voltage, MQ gas voltage.
* **System Outputs:** Categorical stress label and statistical probabilities.
* **Backend Integration:**
    * Orchestration: `app/services/eosm_ml_service.py`
    * Inference Pipeline: `app/ml/eosm/eosm_inference.py`

### Early Disease Alerting System (EDAS)
* **Objective:** Execute early detection of disease risks based on localized environmental thresholds and temporal patterns.
* **Telemetry Inputs:** Plant temperature, ambient air temperature, relative humidity, timestamp variables.
* **System Outputs:** Disease risk severity level, statistical confidence, and management recommendations.
* **Backend Integration:**
    * REST Ingestion: `POST /api/v1/edas-data/`
    * WebSocket Updates: `ws://localhost:8000/api/v1/edas-data/ws/edas/live`
    * Services: `app/services/edas_service.py`

### Freshness Monitoring (FM)
* **Objective:** Estimate post-harvest vase life and current freshness degradation using environmental variables.
* **Telemetry Inputs:** Air temperature, water temperature, humidity, volatile gas concentration, water level.
* **System Outputs:** Freshness index score, vase life estimation (days), and environmental alerts.
* **Backend Integration:**
    * Routes: `app/api/v1/endpoints/fm.py`
    * Inference Pipeline: `app/ml/fm/fm_inference.py`

---

## 4. Technology Stack

**Backend Infrastructure (`smartrose_backend`)**
* **Framework:** Python 3, FastAPI, Uvicorn (ASGI)
* **Database:** MongoDB (Motor asynchronous I/O driver)
* **Data Science:** `scikit-learn`, `pandas`, `numpy`, `joblib`
* **Security & Validation:** Pydantic, Python-JOSE (JWT authentication), Passlib (Bcrypt)

**Frontend Infrastructure (`smartrose_frontend`)**
* **Framework:** Flutter (Dart)
* **Networking & State:** `dio`, `http`, `provider`
* **Visualization:** `syncfusion_flutter_charts`
* **Security:** `flutter_secure_storage`

---

## 5. Local Development Initialization

### Backend Setup
Execute the following from the root directory of `smartrose_backend`:

```bash
# Clone the repository
git clone [https://github.com/25-26J-299/smartrose_backend.git](https://github.com/25-26J-299/smartrose_backend.git)
cd smartrose_backend

# Configure environment variables
cp env.example .env

# Install dependencies
pip install -r requirements.txt

# Initialize the ASGI server
uvicorn app.main:app --reload
