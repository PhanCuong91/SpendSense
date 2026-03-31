Below is a **complete, implementation‑ready Design Document** for your Gmail‑based transaction extraction service, tailored to your tech stack, time zone, and training data.

***

# **DESIGN DOCUMENT — Gmail‑Based Transaction Extraction Service**

Principal Solution Architect — *Python 3.11, FastAPI, PostgreSQL, SQLAlchemy, Docker*

Timezone: **Asia/Singapore (SGT)**  
Default currency: **SGD**

***

# **1. REQUIREMENTS & SCOPE**

## **1.1 Functional Requirements**

### **1. Gmail Polling Loop**

*   Poll Gmail API using `messages.list` with search filters:
    *   Label‑based: e.g., `label:finance OR label:notifications`
    *   Time-based: store checkpoint `last_history_id` or latest `internalDate`
*   Fetch:
    *   `message id` (Gmail API unique), `internalDate`, `payload.headers.subject`, and decoded body.
*   Store each email into `EmailRaw`, **idempotently** keyed by `gmail_message_id`.

### **2. Parsing**

*   Extract fields:
    *   Amount
    *   Date + Time
    *   Currency
    *   Sender and Receiver account names
    *   Type cue: debit / credit / spend / top‑up / update
    *   Reference number (optional)
*   Normalization:
    *   Trim whitespace, collapse line-break artefacts, decode HTML entities.
    *   Convert date to **SGT timezone**.
    *   Convert currency to **SGD** where relevant (if multi‑currency support is added later).

### **3. Classification**

*   Use deterministic rule table derived from your training data:
    *   Keyed by: `(email sender domain → inferred financial sender)` + keyword patterns.
    *   Outcome: `Spend`, `Earn`, `InternalTransfer`, etc.
    *   Also determines **event sender** and **event receiver**.

### **4. Correlation**

For 2‑email event types:

*   Match debit and credit emails via:
    *   Amount equality
    *   Timestamp proximity (± 5 minutes default window)
    *   Reference substring match (optional)
    *   Matching sender/receiver pair
*   Produces a single `Event` record.

### **5. Storage**

*   PostgreSQL (SQLAlchemy ORM models):
    *   `EmailRaw`
    *   `ParsedTransactionCandidate`
    *   `Event`
    *   `CorrelationLink`
    *   `ErrorLog`
    *   `AuditLog`

### **6. API**

*   FastAPI endpoints:
    *   `GET /events`
    *   `POST /reprocess/email/{id}`
    *   `POST /rebuild/all`
    *   `GET /health`
    *   `GET /metrics` (Prometheus format)

### **7. Reprocessing**

*   Reparse one or more `EmailRaw` records.
*   Purge and rebuild:
    *   Parsed candidates
    *   Correlation links
    *   Events (with audit entry)

***

## **1.2 Non‑Functional Requirements**

### **Latency**

*   Polling interval: configurable (e.g. 60 seconds).
*   Parsing + classification latency < 300 ms/email.

### **Throughput**

*   Expected < 100 emails/day, low volume.
*   Must handle spikes up to 1000 emails/min.

### **Observability**

*   Metrics:
    *   Polling success
    *   Emails parsed
    *   Emails classified
    *   Correlator match rate
*   Structured logs (JSON) with request ID.

### **Security**

*   Gmail OAuth2 with restricted scopes:
    *   `https://www.googleapis.com/auth/gmail.readonly`
*   Secrets stored in Docker secrets / K8s secrets.
*   PII redaction in logs.
*   PDPA:
    *   Raw email retention limit = 3 years (configurable).
    *   Ability to purge per-user data.

### **Idempotency**

*   `gmail_message_id` is the **primary uniqueness key**.
*   Reprocessing does not create duplicates.

***

# **2. ARCHITECTURE**

## **2.1 Components**

    Gmail → Poller → Raw Store → Parser → ParsedTransactionCandidate
            → Classifier → (1-email → Event)
                         → (2-email → Correlator → Event)
    FastAPI → Event Query → PostgreSQL
    Metrics → Prometheus/Grafana

### **Component Responsibilities**

| Component      | Responsibility                                                              |
| -------------- | --------------------------------------------------------------------------- |
| **Poller**     | Fetch Gmail messages, store raw emails, schedule parsing.                   |
| **Parser**     | Convert email subject/body into structured fields via regex and heuristics. |
| **Classifier** | Map parsed candidate to event type using deterministic rules.               |
| **Correlator** | Merge debit+credit emails for 2-email events.                               |
| **PostgreSQL** | Persistent storage.                                                         |
| **FastAPI**    | Query & reprocessing API.                                                   |
| **Metrics**    | Prometheus counters, histograms.                                            |

***

## **2.2 Sequence Flow**

### **a) One‑email events (Spend/Earn/InternalTransfer single)**

    Poller → EmailRaw
           → Parser → ParsedTransactionCandidate
           → Classifier (emailCountRequired=1)
           → Event

### **b) Two‑email InternalTransfer (e.g., DBS → Trust)**

    Poller → EmailRaw
           → Parser → ParsedTransactionCandidate (debit)
           → Classifier → Pending Correlation

    Poller → EmailRaw
           → Parser → ParsedTransactionCandidate (credit)
           → Classifier → Pending Correlation

    Correlator:
           → Match debit+credit
           → Create Event
           → Store CorrelationLink

### **c) Reprocessing & rebuild flow**

    API /reprocess → purge ParsedTransactionCandidate/Event (related)
                   → re-parse → re-classify → re-correlate

***

## **2.3 Config Strategy**

| Config                       | Purpose                             |
| ---------------------------- | ----------------------------------- |
| `CORRELATION_WINDOW_MINUTES` | e.g. 5–30 mins                      |
| `REGEX_SETS`                 | Amount, date, reference patterns    |
| `ACCOUNT_ALIAS_MAP`          | Maps variations of account names    |
| `FEATURE_FLAGS`              | Enable advanced rules / new senders |

***

# **3. DATA MODEL**

## **3.1 SQL Tables**

### **EmailRaw**

| Field              | Type      | Notes              |
| ------------------ | --------- | ------------------ |
| id                 | UUID      | PK                 |
| gmail\_message\_id | TEXT      | Unique, indexed    |
| subject            | TEXT      |                    |
| body               | TEXT      |                    |
| internal\_date     | TIMESTAMP | Gmail internalDate |
| received\_at       | TIMESTAMP | System timestamp   |

### **ParsedTransactionCandidate**

| Field                | Type                             | Notes                             |
| -------------------- | -------------------------------- | --------------------------------- |
| id                   | UUID                             | PK                                |
| email\_id            | FK → EmailRaw\.id                | Unique                            |
| amount               | NUMERIC(18,2)                    |                                   |
| currency             | TEXT                             | Default SGD                       |
| datetime\_sgt        | TIMESTAMP                        | Normalized                        |
| inferred\_sender     | TEXT                             | e.g. “DBS”, “Trust”, “ACB Online” |
| inferred\_receiver   | TEXT                             |                                   |
| raw\_reference       | TEXT                             |                                   |
| debit\_credit        | ENUM(debit, credit, spend, earn) |                                   |
| classification\_hint | TEXT                             |                                   |

### **Event**

| Field           | Type          |
| --------------- | ------------- |
| id              | UUID          |
| event\_type     | TEXT          |
| sender          | TEXT          |
| receiver        | TEXT          |
| amount          | NUMERIC(18,2) |
| currency        | TEXT          |
| datetime\_sgt   | TIMESTAMP     |
| raw\_email\_ids | JSONB         |
| description     | TEXT          |

### **CorrelationLink**

\| debit\_candidate\_id | UUID |
\| credit\_candidate\_id | UUID |
\| event\_id | UUID |

### **ErrorLog**

\| id | UUID |
\| email\_id | UUID |
\| error\_type | TEXT |
\| stack | TEXT |

### **AuditLog**

\| id | UUID |
\| action | TEXT |
\| target\_id | UUID |
\| timestamp | TIMESTAMP |
\| metadata | JSONB |

***

## **3.2 JSON Schema for Event**

```json
{
  "type": "object",
  "properties": {
    "eventType": { "type": "string" },
    "sender": { "type": "string" },
    "receiver": { "type": "string" },
    "amount": { "type": "number" },
    "currency": { "type": "string" },
    "datetime": { "type": "string", "format": "date-time" },
    "emails": {
      "type": "array",
      "items": { "type": "string" }
    },
    "metadata": { "type": "object" }
  },
  "required": ["eventType", "sender", "receiver", "amount", "datetime"]
}
```

***

# **4. PARSING SPEC**

Derived from your training data.

## **4.1 Amount Formats & Regex**

Observed formats:

*   `SGD50.00`
*   `SGD7.40`
*   `SGD$ 100.00`
*   `+101,341,000.00 VND`
*   `Debit -6,000,000.00 VND`
*   `Credit +200,000.00 VND`

**Regex:**

    (?P<currency>SGD|VND|USD)?\s?\$?\s?(?P<amount>[+-]?[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)

Normalization rule:

*   Remove commas.
*   Convert string → Decimal.

***

## **4.2 Date/Time Formats & Regex**

Observed:

*   `02 Mar 23:08 (SGT)`
*   `02 Mar 2026 23:08 SGT`
*   `27 Jan 19:12 (SGT)`
*   `030326-11:54:07`

Regex set:

    (?P<date1>\d{2}\s\w{3}\s\d{2}:\d{2})
    (?P<date2>\d{2}\s\w{3}\s\d{4}\s\d{2}:\d{2})
    (?P<date3>\d{6}-\d{2}:\d{2}:\d{2})

Rule:

*   Assume SGT unless explicitly stated otherwise.
*   Convert DMY to ISO.

***

## **4.3 Account Name Variations (Alias Map)**

From examples:

| Bank           | Variants                                                                        |
| -------------- | ------------------------------------------------------------------------------- |
| **DBS**        | “DBS”, “DBS Multiplier Account”, “POSB”, “digibank”, “PayLah Wallet”, “PayLah!” |
| **Trust**      | “Trust”, “Trust App”, “Trust Link Card”                                         |
| **ACB Online** | “ACB Online”, “<ACB Online Account>”                                            |
| **ACB**        | “ACB”, “<ACB Account>”                                                          |

Alias map:

```json
{
  "DBS": ["DBS", "POSB", "DBS Multiplier Account", "digibank", "PayLah", "PayLah! Wallet"],
  "Trust": ["Trust", "Trust App", "Trust Link"],
  "ACB Online": ["ACB Online", "<ACB Online Account>"],
  "ACB": ["ACB", "<ACB Account>"]
}
```

***

## **4.4 Debit/Credit Heuristics**

**Debit indicators:**

*   `Debit -`
*   `You've spent`
*   `Scan & Pay`
*   `Top-up`
*   `Transfer From: ... To: ...`
*   `Latest transaction: Debit -`

**Credit indicators:**

*   `You've received`
*   `Credit +`
*   `received SGD`
*   `Latest transaction: Credit +`

***

## **4.5 Reference Parsing**

Patterns:

*   `6061BIDVE24MGJC9`
*   `6062ASCB022MP4Y8`
*   `IB PHAN CUONG CHUYEN KHOAN`
*   `FINFAN 1481213826`

Regex:

    (?P<ref>[A-Z0-9]{8,20})

***

## **4.6 Structural Cues**

Indicators used for classification:

*   Subject prefixes:
    *   “iBanking Alerts” → DBS debit/credit
    *   “Yay! You've received…” → Trust credit
    *   “ACB-Dich vu bao so du tu dong” → ACB debit/credit
*   Body structure (DbS formatted blocks, ACB summary format, Trust single-line).

***

# **5. CLASSIFICATION SPEC**

## **5.1 Classification Rule Table**

Derived directly from training examples.

| Sender     | Receiver   | emailCountRequired | EventType        |
| ---------- | ---------- | ------------------ | ---------------- |
| DBS        | Trust      | 2                  | InternalTransfer |
| DBS        | ACB Online | 2                  | InternalTransfer |
| ACB Online | ACB        | 2                  | InternalTransfer |
| DBS        | Paylah     | 1                  | InternalTransfer |
| ACB Online | Other      | 1                  | Spend            |
| ACB        | Other      | 1                  | Spend            |
| Trust      | Other      | 1                  | Spend            |
| Paylah     | Other      | 1                  | Spend            |
| Other      | DBS        | 1                  | Earn             |

***

## **5.2 Determination of Sender/Receiver**

*   Based on alias map tagging inside the parsed structured fields (from “From:” / “To:” lines).
*   For single-email Spend/Earn:
    *   Debit → sender is financial institution, receiver = merchant.
    *   Credit → sender = payor, receiver = institution (your account).

***

# **6. CORRELATION SPEC**

## **6.1 Correlation Rules for 2-email events**

Match debit candidate D and credit candidate C when:

### **1. Amount Equality**

    abs(D.amount - C.amount) <= 0.01

### **2. Date Proximity**

    abs(D.datetime - C.datetime) <= CORRELATION_WINDOW_MINUTES (default 15)

### **3. Sender/Receiver Affirmation**

*   D.inferred\_sender = Rule.sender
*   C.inferred\_receiver = Rule.receiver

### **4. Debit/Credit Complement**

*   D is debit
*   C is credit

### **5. Reference (Optional Soft Match)**

*   Fuzzy match score>0.5 between reference strings.

***

## **6.2 Pending State Machine**

    ParsedTransactionCandidate (debit/credit)
          ↓ classify
    PendingCorrelation (bucketed by event rule)
          ↓ match (scheduled job or real-time)
    Matched Pair → Event
          ↓
    Archived / Marked Complete

Candidates not matched after expiry window → `expired`.

***

## **6.3 Conflict Resolution & Tie-Breakers**

1.  **Amount match priority**
2.  **Closest timestamp**
3.  **Highest reference match score**
4.  **If tie remains → log error & require manual review**

***

# **END OF DESIGN DOCUMENT**

If you'd like, I can also generate:

✅ Complete SQLAlchemy ORM models  
✅ Full FastAPI project skeleton with directories  
✅ Regex test suite  
✅ End-to-end sequence diagram  
✅ Docker Compose for FastAPI + Worker + PostgreSQL

Just tell me **“Generate code”** or specify the part you want first.



sequenceDiagram
    autonumber

    participant Gmail as Gmail API
    participant Poller as Poller Worker
    participant DB as PostgreSQL
    participant Parser as Parser Worker
    participant Classifier as Classifier
    participant Builder as Event Builder
    participant Correlator as Correlator Worker
    participant API as FastAPI
    participant User as User Client

    %% POLLING PHASE
    Poller->>Gmail: messages.list(query="newer_than:3d")
    Gmail-->>Poller: message IDs

    loop for each message
        Poller->>Gmail: messages.get(id)
        Gmail-->>Poller: full message

        Poller->>DB: INSERT EmailRaw (idempotent on gmail_message_id)
        Poller->>Parser: enqueue_for_parsing(email_raw_id)
    end

    %% PARSING PHASE
    Parser->>DB: fetch EmailRaw
    Parser->>Parser: apply regex parsing\n(amount, date, sender, receiver,…)
    Parser->>DB: INSERT ParsedTransactionCandidate

    %% CLASSIFICATION
    Parser->>Classifier: classify(parsed_candidate)
    Classifier-->>Parser: eventType + emailCountRequired

    %% 1-EMAIL EVENTS → EventBuilder
    alt emailCountRequired == 1
        Parser->>Builder: process_candidate(candidate_id)
        Builder->>DB: INSERT Event\n(type: Spend/Earn/InternalTransfer)
        Builder->>DB: INSERT AuditLog
    end

    %% 2-EMAIL EVENTS → Correlator
    Note over Parser: For 2-email InternalTransfer, do NOT create Event.
    Note over Correlator: Runs in loop every 10s

    Correlator->>DB: Query pending debit candidates
    Correlator->>DB: Query pending credit candidates
    Correlator->>Correlator: Match by amount, date proximity, ref similarity
    alt match found
        Correlator->>DB: INSERT Event
        Correlator->>DB: INSERT CorrelationLink
        Correlator->>DB: INSERT AuditLog
    end

    %% QUERY EVENTS API
    User->>API: GET /events?page=&filters=
    API->>DB: SELECT events with filters + pagination
    DB-->>API: event list
    API-->>User: JSON response

SYSTEM ARCHITECTURE DIAGRAM

flowchart TD

    subgraph Gmail["Gmail API"]
        MG[Email Messages]
    end

    subgraph Workers["Workers Layer"]
        PW[Poller Worker]
        PAR[Parser Worker]
        EB[Event Builder]
        COR[Correlator Worker]
    end

    subgraph API["FastAPI Service"]
        EVAPI[Events API<br/>/events /health /reprocess]
    end

    subgraph DB["PostgreSQL Database"]
        ER[EmailRaw]
        PC[ParsedTransactionCandidate]
        EV[Event]
        CL[CorrelationLink]
        EL[ErrorLog]
        AL[AuditLog]
    end

    MG --> PW

    PW -->|Insert raw email| ER
    PW -->|Enqueue| PAR

    PAR -->|Insert parsed candidate| PC
    PAR -->|Classify + 1-email events| EB
    EB -->|Insert Event| EV

    PC -->|Unmatched 2-email| COR
    COR -->|Match debit+credit| EV
    COR -->|Insert correlation links| CL

    EVAPI -->|Query Events| EV
    EVAPI -->|Return JSON| User["(User Client)"]


CLASS DIAGRAM for ORM Models
classDiagram

    class EmailRaw {
        UUID id
        string gmail_message_id
        string subject
        string body
        datetime internal_date
        datetime received_at
    }

    class ParsedTransactionCandidate {
        UUID id
        UUID email_id
        decimal amount
        string currency
        datetime datetime_sgt
        string inferred_sender
        string inferred_receiver
        string raw_reference
        enum debit_credit
        string classification_hint
    }

    class Event {
        UUID id
        string event_type
        string sender
        string receiver
        decimal amount
        string currency
        datetime datetime_sgt
        JSON raw_email_ids
        string description
    }

    class CorrelationLink {
        UUID id
        UUID debit_candidate_id
        UUID credit_candidate_id
        UUID event_id
    }

    class ErrorLog {
        UUID id
        UUID email_id
        string error_type
        string stack
        datetime created_at
    }

    class AuditLog {
        UUID id
        string action
        UUID target_id
        JSON metadata
        datetime timestamp
    }

    %% Relationships
    EmailRaw --> ParsedTransactionCandidate : one-to-one
    ParsedTransactionCandidate --> CorrelationLink : debit side
    ParsedTransactionCandidate --> CorrelationLink : credit side
    Event --> CorrelationLink : one-to-many

ERD (Entity Relationship Diagram)

erDiagram

    EmailRaw {
        UUID id PK
        string gmail_message_id
        string subject
        string body
        datetime internal_date
        datetime received_at
    }

    ParsedTransactionCandidate {
        UUID id PK
        UUID email_id FK
        decimal amount
        string currency
        datetime datetime_sgt
        string inferred_sender
        string inferred_receiver
        string raw_reference
        string debit_credit
        string classification_hint
    }

    Event {
        UUID id PK
        string event_type
        string sender
        string receiver
        decimal amount
        string currency
        datetime datetime_sgt
        json raw_email_ids
        string description
    }

    CorrelationLink {
        UUID id PK
        UUID debit_candidate_id FK
        UUID credit_candidate_id FK
        UUID event_id FK
    }

    ErrorLog {
        UUID id PK
        UUID email_id FK
        string error_type
        string stack
        datetime created_at
    }

    AuditLog {
        UUID id PK
        string action
        UUID target_id
        json metadata
        datetime timestamp
    }

    %% Relationships
    EmailRaw ||--o| ParsedTransactionCandidate : "parsed from"
    ParsedTransactionCandidate ||--o{ CorrelationLink : "debit side"
    ParsedTransactionCandidate ||--o{ CorrelationLink : "credit side"
    Event ||--o{ CorrelationLink : "links"
    EmailRaw ||--o{ ErrorLog : "errors"
    Event ||--o{ AuditLog : "audit entries"


Run Locally:
install Docker desktop
docker compose up -d db

Python -m pip install -r requirements
PYTHONPATH="$(pwd)" alembic upgrade head
uvicorn app.main:app --reload --port 8000
python -m app.workers.poller_worker
python -m app.workers.parser_worker
python -m app.workers.correlator_worker

reset db
bash scripts/dev_reset.sh

update db
D:\02_work\playground\email\app\db\migrations\versions\25e3615898c8_initial_migration.py

docker exec -it tx-postgres psql -U user -d txdb

get sgp timezone:
SELECT datetime_sgt AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Singapore' AS datetime_sgt_sgt
FROM event;
SELECT * FROM parsed_transaction_candidate;
select gmail_message_id, subject, from_email, internal_date from email_raw;

export:
docker exec -it tx-postgres pg_dump -U user -d txdb > db_backup.sql
import:
docker exec -i tx-postgres psql -U user -d txdb < db_backup.sql