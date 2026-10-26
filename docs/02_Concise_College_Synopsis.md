# Project Synopsis: VoteIT — Smart Polling Booth & Time-Slot Allocation Platform for One Nation One Election
## B.Tech Computer Science & Engineering (AI & ML) Capstone Prototype

---

## 1. Project Title & Metadata
- **Project Title:** VoteIT — Smart Polling Booth & Time-Slot Allocation Platform for One Nation One Election (ONOE)
- **Domain:** Artificial Intelligence & Machine Learning, Operating Systems, Relational DBMS, Full-Stack Web Development
- **Course / Degree:** B.Tech Computer Science and Engineering (Specialization: AI & ML)
- **Academic Term:** 2026 Academic Year
- **Simulation Region:** Uttarakhand Electoral Wards (Dehradun, Haridwar, Haldwani, Nainital)

---

## 2. Problem Statement
Simultaneous Parliamentary (Lok Sabha) and Assembly (Vidhan Sabha) elections ("One Nation, One Election") approximately double voter dwell time at polling compartments due to dual-ballot casting. Uncoordinated voter arrivals cause acute queue spikes, prolonged wait times, and extreme physical congestion during peak morning and evening hours. Furthermore, high-concurrency digital booking systems face severe race-condition vulnerabilities that risk overbooking booth capacities if unmanaged.

---

## 3. Project Objectives
1. **Relational 3NF Persistence:** Model a 3NF normalized 11-table schema in MySQL 8.4 InnoDB capturing dual-jurisdiction Lok Sabha (PC) and Vidhan Sabha (AC) relationships, views, triggers, and stored procedures.
2. **OS Concurrency & Process Scheduling:** Implement an in-memory OS engine with Process Control Blocks (`RequestPCB`), priority queue scheduling with dynamic aging, per-slot mutual exclusion locks, and hierarchical resource ordering to prevent deadlocks.
3. **Database Concurrency & Row Locks:** Construct stored procedures (`sp_allocate_slot_atomic`) executing `SELECT ... FOR UPDATE` row locks to guarantee zero overbooking during concurrent allocation bursts.
4. **Machine Learning Crowd Forecasting:** Train a Scikit-Learn `RandomForestRegressor` against historical arrival telemetry to forecast slot-level voter arrivals with explainable feature importance.
5. **Deterministic Heuristic Optimization:** Formulate deterministic Haversine spatial ranking and multi-criteria scoring algorithms that rank booths and slots by physical proximity, accessibility ramps, and predicted congestion.
6. **Robust Rule-Based Fallback:** Ensure continuous server uptime through an automatic rule-based fallback if ML artifacts are missing.
7. **Responsive & Accessible Web UI:** Build an accessible, high-contrast Voter Portal and an Administrative Telemetry Dashboard with Leaflet map visualization and Chart.js analytics.
8. **Automated End-to-End Testing:** Achieve a 100% passing automated test suite (`pytest`) across database, OS engine, ML models, and integration routes.

---

## 4. Strict Academic & Legal Guardrails
- **Logistics Only, Not Voting:** The platform is an election logistics and queue-management prototype, **NOT** an electronic voting machine (EVM). It never implements vote casting, candidate selection, campaigning, or election outcome tabulations.
- **Inviolable Constitutional Rights:** Time-slot bookings are strictly **advisory**. Any registered voter arriving at their polling booth without an appointment retains their full constitutional right to vote in the general walk-in line.
- **100% Synthetic Demo Data:** The system exclusively uses synthetic voter records (`DEM-UK-2026-XXXX`) and simulated verification. No real government IDs or biometric samples are ever collected or stored.
- **Prototype Benchmarks:** All reported quantitative figures (e.g., Random Forest MAE = 1.5724, $R^2 = 0.9491$) represent measured synthetic-dataset prototype benchmarks rather than live field election data.

---

## 5. System Architecture & 5-Tier Pipeline
```
[Tier 1: Client UI]         --> Voter Portal (index.html) & Admin Dashboard (admin.html)
                                    | (RESTful JSON / JWT Auth)
[Tier 2: API Gateway]       --> Flask 3.0 Backend (12 REST Endpoints + Health + Viva Simulator)
                                    |
[Tier 3: Auth & Verification]--> Simulated ECI Verifier & HMAC-SHA256 JWT Generator
                                    |
[Tier 4: Engine Layer]      --> OS Concurrency Engine (RequestPCB, Scheduler, Mutex)
                                + Geo & AI Recommendation Engine (Haversine, Random Forest)
                                    | (Connection Pool / Transactions / Row Locks)
[Tier 5: Persistence Layer] --> MySQL 8.4 InnoDB Database (11 Tables, 3 Views, 3 SPs, 2 Triggers)
```

---

## 6. 11-Table Relational Schema Overview (3NF)

| # | Table Name | Primary Key | Key Attributes / Foreign Keys | Function |
| :-: | :--- | :--- | :--- | :--- |
| 1 | `states` | `state_id` | `state_code`, `state_name` | Federal state catalog. |
| 2 | `constituencies` | `constituency_id` | `state_id`, `parent_pc_id`, `constituency_type` | Recursive PC $\to$ AC mapping. |
| 3 | `polling_stations` | `station_id` | `latitude`, `longitude`, `has_wheelchair_ramp` | Physical school/campus facilities. |
| 4 | `polling_booths` | `booth_id` | `station_id`, `pc_id`, `ac_id`, `room_number` | Dual PC/AC voting rooms. |
| 5 | `voters` | `voter_id` | `demo_epic_no`, `priority_level`, `assigned_booth_id`| Registered synthetic voters. |
| 6 | `election_events` | `event_id` | `event_type`, `election_date`, `status` | ONOE simultaneous election cycles. |
| 7 | `time_slots` | `slot_id` | `booth_id`, `start_time`, `max_capacity`, `allocated_count` | Discretized 2-hour voting windows. |
| 8 | `slot_allocations` | `allocation_id` | `booking_reference_token`, `voter_id`, `slot_id` | Confirmed voter reservations. |
| 9 | `simulated_verifications` | `verification_id`| `voter_id`, `simulated_token`, `status` | Audit trail of mock verifications. |
| 10 | `crowd_telemetry` | `telemetry_id` | `booth_id`, `slot_id`, `congestion_index` | Sensor arrival telemetry for ML. |
| 11 | `os_concurrency_audit` | `audit_id` | `thread_name`, `voter_id`, `execution_latency_ms` | Thread-level lock and aging audit. |

- **3 Views:** `vw_booth_live_status`, `vw_voter_appointment_slip`, `vw_constituency_logistics_summary`.
- **3 Stored Procedures:** `sp_allocate_slot_atomic`, `sp_cancel_slot_atomic`, `sp_log_os_concurrency_event`.
- **2 Triggers:** `trg_after_allocation_insert`, `trg_after_allocation_cancel`.

---

## 7. Operating Systems & AI/ML Highlights

### Operating Systems Core Implementations
- **Process Management:** Tracks every reservation as a `RequestPCB` through states `NEW` $\to$ `READY` $\to$ `RUNNING` $\to$ `WAITING` $\to$ `TERMINATED`.
- **CPU Scheduling with Aging:** Evaluates priority queues (Senior Citizens & PwD = Priority 1, General = Priority 2). Automatically promotes waiting general requests by 1 tier every 30 seconds to prevent starvation.
- **Dual-Layer Synchronization:** Combines in-process reentrant mutex locks (`threading.Lock`) with MySQL InnoDB `SELECT ... FOR UPDATE` row locks, guaranteeing **Zero Overbooking**.
- **Deadlock Prevention:** Enforces **Hierarchical Resource Lock Ordering** during reallocations, acquiring locks in strictly ascending numerical order of `slot_id` to break Coffman's circular wait condition.
- **Memory & File Management:** Employs a thread-safe `BoundedLRUCache` for booth metadata and a size-bounded `RotatingFileHandler` for concurrency audit logging.

### AI/ML Demand Forecaster & Heuristics
- **Algorithms Partition:**
  - *Conventional Deterministic:* Haversine distance, accessibility filtering, multi-criteria slot ranking, rule-based fallback.
  - *Machine Learning:* Scikit-Learn `RandomForestRegressor` (100 estimators, max depth 12).
- **Synthetic-Dataset Prototype Benchmarks:**
  - **Random Forest MAE:** `1.5724 voters/slot` (vs. Baseline MAE `6.5712`, **76.1% improvement**).
  - **Random Forest RMSE:** `1.9154 voters/slot` (vs. Baseline RMSE `8.1887`, **76.6% improvement**).
  - **Random Forest $R^2$ Score:** `0.9491` (vs. Baseline $R^2 = -0.0634$).
  - **Concurrency Race Benchmark:** 10 threads competing for 1 seat $\to$ exactly 1 `SUCCESS`, 9 `REJECTED`, **0 Overbookings** in `0.21s`.

---

## 8. 10-Week Implementation Schedule

| Week | Phase | Key Milestone | Deliverable |
| :---: | :--- | :--- | :--- |
| **1** | Requirements & Scope | Problem formulation, ONOE constraint analysis. | Requirements Specification |
| **2** | Architectural Design | 5-tier architecture, OS & ML module contracts. | Architectural Diagrams |
| **3** | Relational Database | 3NF schema, tables, seed data, triggers, SPs. | `database/schema.sql` (8/8 tests pass) |
| **4** | OS Concurrency Engine | RequestPCB, FCFS/Priority schedulers, aging. | `os_engine/` (7/7 tests pass) |
| **5** | Memory & Deadlocks | Resource lock ordering, LRU cache, logger. | Deadlock prevention & caching |
| **6** | Machine Learning | Synthetic dataset, Random Forest training & export. | `rf_crowd_model.joblib` ($R^2 = 0.9491$) |
| **7** | Flask REST API | 12 REST endpoints, JWT authentication, CORS. | `backend/app/routes/` (14/14 tests pass) |
| **8** | Frontend Web Portal | High-contrast UI, Leaflet map, Chart.js graphs. | `frontend/index.html`, `styles.css` |
| **9** | Admin & Live Simulator | Admin dashboard, live 10-thread race simulator. | `frontend/admin.html`, `/api/admin/simulate-race` |
| **10**| Testing & Documentation| E2E test suite, 29-section academic synopsis. | `tests/`, `docs/` (39/39 tests pass) |

---

## 9. Final Prototype Implementation Verification Checklist

| Requirement / Module | Implemented File Path | Status | Verification Mechanism |
| :--- | :--- | :---: | :--- |
| **11 3NF Database Tables** | `database/schema.sql` | **VERIFIED** | `tests/test_stage1_db.py::test_all_11_tables_exist_and_have_seeded_rows` |
| **3 Relational Views** | `database/schema.sql` | **VERIFIED** | `tests/test_stage1_db.py::test_all_3_views_exist_and_return_rows` |
| **3 Stored Procedures** | `database/schema.sql` | **VERIFIED** | `tests/test_stage1_db.py::test_all_3_stored_procedures_exist` |
| **2 Database Triggers** | `database/schema.sql` | **VERIFIED** | `tests/test_stage1_db.py::test_all_2_triggers_exist` |
| **Pessimistic Row Lock (`SELECT FOR UPDATE`)** | `database/schema.sql` (`sp_allocate_slot_atomic`) | **VERIFIED** | `tests/test_stage1_db.py::test_sp_allocate_slot_atomic_and_trigger_increment` |
| **Process Control Block (`RequestPCB`)** | `backend/app/os_engine/process_lifecycle.py` | **VERIFIED** | `tests/test_os_engine.py::test_process_lifecycle_transitions` |
| **Priority Scheduling with Dynamic Aging** | `backend/app/os_engine/request_scheduler.py` | **VERIFIED** | `tests/test_os_engine.py::test_priority_scheduling_with_aging` |
| **Mutual Exclusion & Critical Section** | `backend/app/os_engine/synchronization.py` | **VERIFIED** | `tests/test_os_engine.py::test_synchronization_critical_section` |
| **Deadlock Prevention (Lock Ordering)** | `backend/app/os_engine/deadlock_prevention.py`| **VERIFIED** | `tests/test_os_engine.py::test_deadlock_prevention_resource_ordering` |
| **Thread-Safe Bounded LRU Cache** | `backend/app/os_engine/lru_cache.py` | **VERIFIED** | `tests/test_os_engine.py::test_lru_memory_cache` |
| **Size-Bounded Rotating Logger** | `backend/app/os_engine/rotating_logger.py` | **VERIFIED** | `tests/test_os_engine.py::test_rotating_file_logger` |
| **Random Forest Demand Forecaster** | `backend/app/services/crowd_prediction_service.py`| **VERIFIED** | `tests/test_stage3_ml_and_api.py::test_ml_artifacts_exist_and_rf_outperforms_baseline` |
| **Rule-Based Automatic Fallback** | `backend/app/services/crowd_prediction_service.py`| **VERIFIED** | `tests/test_stage3_ml_and_api.py::test_automatic_rule_based_fallback_and_guardrails` |
| **Haversine Geo-Ranking Algorithm** | `backend/app/services/booth_service.py` | **VERIFIED** | `tests/test_stage3_ml_and_api.py::test_endpoint_4_booths_nearby` |
| **Simulated ECI Mock Verification** | `backend/app/services/verification_service.py` | **VERIFIED** | `tests/test_stage3_ml_and_api.py::test_endpoint_3_verification_mock` |
| **12 Core REST API Endpoints** | `backend/app/routes/` | **VERIFIED** | `tests/test_stage3_ml_and_api.py` (Endpoints 1 through 12) |
| **Live 10-Thread Barrier Race Simulation**| `backend/app/routes/admin_routes.py` (`simulate-race`)| **VERIFIED** | `tests/test_stage4_frontend_and_e2e.py::test_simulate_race_10_threads_zero_overbooking` |
| **Flask Static File Serving** | `backend/app/__init__.py` | **VERIFIED** | `tests/test_stage4_frontend_and_e2e.py::test_frontend_static_serving` |
| **Voter Web Portal (Guided 4-Step Flow)**| `frontend/index.html` & `frontend/js/voter_portal.js`| **VERIFIED** | Manually validated & tested via HTTP GET `/` |
| **Admin Telemetry & Race Dashboard** | `frontend/admin.html` & `frontend/js/admin_dashboard.js`| **VERIFIED** | Manually validated & tested via HTTP GET `/admin` |
| **Responsive High-Contrast Styling** | `frontend/css/styles.css` | **VERIFIED** | Verified responsive rules & `.high-contrast-mode` |

---

## 10. References
1. Silberschatz, A., Galvin, P. B., & Gagne, G. (2018). *Operating System Concepts* (10th ed.). John Wiley & Sons.
2. Elmasri, R., & Navathe, S. B. (2015). *Fundamentals of Database Systems* (7th ed.). Pearson.
3. Breiman, L. (2001). "Random Forests." *Machine Learning*, 45(1), 5–32.
4. Sinnott, R. W. (1984). "Virtues of the Haversine." *Sky and Telescope*, 68(2), 159.
5. Election Commission of India (ECI). (2023). *Manual on Polling Stations and Queue Management*. Nirvachan Sadan, New Delhi.
