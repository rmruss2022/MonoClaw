# Autofill Agent (ASCII)

This is a high-detail, end-to-end system diagram of how PayMe's autofill agent service
claims settlement forms on behalf of users — from job enqueue through browser automation,
step recording, artifact capture, and retry/failure handling.

```
                              +------------------------------------------+
                              |             USER / FRONTEND              |
                              |------------------------------------------|
                              | User reviews a settlement match and      |
                              | clicks "Auto-Fill Claim" on detail page  |
                              +--------------------+---------------------+
                                                   |
                                                   v
                              +------------------------------------------+
                              | POST /autofill/jobs                      |
                              |------------------------------------------|
                              | body: { user_id, settlement_id,          |
                              |         claim_url }                      |
                              +--------------------+---------------------+
                                                   |
                                                   v
                              +------------------------------------------+
                              | autofill_jobs row inserted               |
                              |------------------------------------------|
                              | status         = queued                  |
                              | attempt_count  = 0                       |
                              | next_retry_at  = NULL                    |
                              | claim_url      = <settlement claim URL>  |
                              | started_at     = NULL                    |
                              | completed_at   = NULL                    |
                              +------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                                  WORKER POLLING LOOP                                    |
|                                   (worker.py: run_worker)                               |
+-----------------------------------------------------------------------------------------+

  +------------------------------------------+
  | Infinite async loop begins               |
  | Open DB session                          |
  +-------------------+----------------------+
                      |
                      v
  +------------------------------------------+
  | _claim_next_job(db)                      |
  |------------------------------------------|
  | SELECT * FROM autofill_jobs              |
  |   WHERE status = 'queued'                |
  |     AND (next_retry_at IS NULL           |
  |          OR next_retry_at <= now())      |
  |   ORDER BY created_at ASC               |
  |   LIMIT 1                               |
  |   FOR UPDATE SKIP LOCKED               |
  +-------------------+----------------------+
                      |
          +-----------+------------+
          |                        |
     [no row]                 [row found]
          |                        |
          v                        v
  +---------------+   +------------------------------+
  | sleep         |   | SET status = 'running'       |
  | POLL_INTERVAL |   | INCREMENT attempt_count      |
  | seconds       |   | COMMIT                       |
  | -> loop again |   | return job                   |
  +---------------+   +-------------+----------------+
                                    |
                                    v
                      +------------------------------+
                      | _process_job(job, db)        |
                      | (wrapped in try/except)      |
                      +-------------+----------------+
                                    |
                                    v
                      +------------------------------+
                      | Close DB session             |
                      | -> loop again                |
                      +------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                            JOB EXECUTION (_execute_job)                                 |
+-----------------------------------------------------------------------------------------+

  +------------------------------------------+
  | _execute_job(job, db)                    |
  +-------------------+----------------------+
                      |
                      v
  +------------------------------------------+
  | Fetch user profile from internal API     |
  |------------------------------------------|
  | GET /admin/users/{user_id}               |
  | extracts: first_name, last_name, email,  |
  |   address, state, dob, phone             |
  | (fetched at execution time — always      |
  |  uses latest profile, not enqueue-time   |
  |  snapshot)                               |
  +-------------------+----------------------+
                      |
                      v
  +------------------------------------------+
  | Lookup Settlement row in DB              |
  |------------------------------------------|
  | reads: settlement_title, claim_url       |
  +-------------------+----------------------+
                      |
                      v
  +------------------------------------------+
  | Emit event: autofill_job_started         |
  +-------------------+----------------------+
                      |
                      v
  +------------------------------------------+
  | run_autofill_job(job_data, user_data)    |
  | (browser.py — see BROWSER STEPS below)  |
  | returns: list of step_results            |
  +-------------------+----------------------+
                      |
                      v
  +------------------------------------------+
  | For each step_result in step_results:    |
  |------------------------------------------|
  |                                          |
  |  1. INSERT autofill_job_steps row        |
  |     - step_name                          |
  |     - status (done | failed | skipped)   |
  |     - output_json                        |
  |     - error_message                      |
  |     - started_at / completed_at          |
  |                                          |
  |  2. Emit event: autofill_step_completed  |
  |     metadata: { step_name, status }      |
  |                                          |
  |  3. If step_name == 'screenshot'         |
  |     AND status == 'done':                |
  |     INSERT autofill_artifacts row        |
  |     - artifact_type = screenshot         |
  |     - storage_key (from output_json)     |
  |     - size_bytes (from output_json)      |
  |     - content_type = image/png           |
  |                                          |
  +------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                          BROWSER AUTOMATION STEPS (browser.py)                          |
|                              run_autofill_job(job_data, user_data)                      |
+-----------------------------------------------------------------------------------------+

  +-----------------------------------------------+
  | Step 1: navigate                              |
  |-----------------------------------------------|
  | Open chromium via Playwright (headless)       |
  | page.goto(claim_url)                          |
  | output_json: { url, status_code, page_title } |
  +---------------------+-------------------------+
                        |
                        v
  +-----------------------------------------------+
  | Step 2: detect_form                           |
  |-----------------------------------------------|
  | Search DOM for <form> elements                |
  |                                               |
  |   [forms found]          [no forms found]     |
  |       |                        |              |
  |       v                        v              |
  |  output_json:           raise BlockedError    |
  |  { form_count,          reason: "no_form"     |
  |    field_names[] }      -> job blocked,       |
  |                           no retry            |
  +---------------------+-------------------------+
                        |
                [forms found]
                        |
                        v
  +-----------------------------------------------+
  | Step 3: fill_fields                           |
  |-----------------------------------------------|
  | Map detected input fields to user profile:   |
  |   first_name, last_name -> name fields        |
  |   email                 -> email fields       |
  |   address               -> address fields     |
  |   state                 -> state fields       |
  |   dob                   -> date-of-birth      |
  |   phone                 -> phone fields       |
  | page.fill() for each matched field           |
  | output_json: { fields_filled, fields_skipped }|
  +---------------------+-------------------------+
                        |
                        v
  +-----------------------------------------------+
  | Step 4: submit                                |
  |-----------------------------------------------|
  | Locate submit button in DOM                   |
  |                                               |
  |  [button found]       [no button found]       |
  |       |                      |                |
  |       v                      v                |
  |  page.click(button)   raise BlockedError      |
  |  wait for navigation  reason: "no_submit"     |
  |  output_json:         -> job blocked,         |
  |  { final_url }          no retry              |
  +---------------------+-------------------------+
                        |
               [button found + clicked]
                        |
                        v
  +-----------------------------------------------+
  | Step 5: screenshot                            |
  |-----------------------------------------------|
  | page.screenshot(full_page=True)               |
  | Save PNG to artifacts directory               |
  | storage_key = artifacts/{job_id}/{timestamp}  |
  | output_json: { storage_key, size_bytes }      |
  | -> triggers AutofillArtifact row insert       |
  |    in _execute_job (see above)                |
  +---------------------+-------------------------+
                        |
                        v
  +-----------------------------------------------+
  | Step 6: done                                  |
  |-----------------------------------------------|
  | Mark completion, close browser context        |
  | output_json: { steps_completed }             |
  +-----------------------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                        SUCCESS / FAILURE BRANCHING (_process_job)                       |
+-----------------------------------------------------------------------------------------+

  +------------------------------------------+
  | _process_job(job, db) dispatches         |
  | _execute_job and catches all exceptions  |
  +-------------------+----------------------+
                      |
          +-----------+-----------+-----------+
          |                       |           |
     [success]            [BlockedError]  [generic exception]
          |                       |           |
          v                       v           v
  +---------------+  +------------------+  +--------------------------------------+
  | job.status    |  | job.status       |  | job.attempt_count < max_retries?    |
  |   = 'done'    |  |   = 'blocked'    |  +----------+-----------+--------------+
  | completed_at  |  | error_message    |             |           |
  |   = now()     |  |   = reason       |         [yes]          [no]
  | Emit:         |  | Emit:            |             |           |
  | autofill_     |  | autofill_job_    |             v           v
  | job_done      |  | blocked          |  +----------------+  +------------------+
  +---------------+  +------------------+  | Re-queue job   |  | job.status       |
                                           | status='queued'|  |   = 'failed'     |
                                           | next_retry_at  |  | Emit:            |
                                           |  = now() +     |  | autofill_job_    |
                                           |    retry_delay |  | failed           |
                                           | (no retry cap  |  +------------------+
                                           |  on delay —    |
                                           |  flat backoff) |
                                           +----------------+
```

```
+-----------------------------------------------------------------------------------------+
|                                 JOB LIFECYCLE STATES                                    |
+-----------------------------------------------------------------------------------------+

                               +----------+
                               |  queued  |<--------------------------+
                               +----+-----+                           |
                                    |                                 |
                            (worker claims)                           |
                                    |                           (retry < max,
                                    v                            next_retry_at set)
                               +----------+                           |
                               | running  +---(generic exception)-----+
                               +----+-----+
                                    |
                    +---------------+------------------+
                    |               |                  |
               [success]     [BlockedError]   [generic exception,
                    |               |           attempt_count >= max]
                    v               v                  v
               +--------+     +---------+        +--------+
               |  done  |     | blocked |        | failed |
               +--------+     +---------+        +--------+

  NOTE: blocked jobs do NOT retry. A human must inspect and re-enqueue
  or mark as resolved. blocked and failed are terminal unless re-enqueued
  by an operator.
```

```
+-----------------------------------------------------------------------------------------+
|                                   DATABASE TABLES                                       |
+-----------------------------------------------------------------------------------------+

  autofill_jobs
  +--------------------+----------------------------------+
  | Column             | Notes                            |
  |--------------------|----------------------------------|
  | id                 | PK                               |
  | user_id            | FK -> users                      |
  | settlement_id      | FK -> settlements                |
  | status             | queued|running|blocked|done|fail |
  | attempt_count      | incremented on each claim        |
  | next_retry_at      | NULL or future timestamp         |
  | claim_url          | target form URL                  |
  | started_at         | set when status -> running       |
  | completed_at       | set when status -> done          |
  | error_message      | populated on blocked/failed      |
  +--------------------+----------------------------------+

  autofill_job_steps
  +--------------------+----------------------------------+
  | Column             | Notes                            |
  |--------------------|----------------------------------|
  | id                 | PK                               |
  | job_id             | FK -> autofill_jobs (cascade)    |
  | step_name          | navigate|detect_form|fill_fields |
  |                    |   submit|screenshot|done          |
  | status             | pending|running|done|failed|skip  |
  | input_json         | step inputs (url, field map, etc)|
  | output_json        | step outputs (storage_key, etc)  |
  | error_message      | populated on failure             |
  | started_at         |                                  |
  | completed_at       |                                  |
  +--------------------+----------------------------------+

  autofill_artifacts
  +--------------------+----------------------------------+
  | Column             | Notes                            |
  |--------------------|----------------------------------|
  | id                 | PK                               |
  | job_id             | FK -> autofill_jobs              |
  | step_id            | FK -> autofill_job_steps         |
  |                    |   (SET NULL on step delete)      |
  | artifact_type      | screenshot | html | log          |
  | content_type       | e.g. image/png, text/html        |
  | storage_key        | path/key in artifact storage     |
  | size_bytes         | file size at capture time        |
  +--------------------+----------------------------------+
```

```
+-----------------------------------------------------------------------------------------+
|                                   API SURFACE                                           |
|                              (/autofill/* in FastAPI app)                               |
+-----------------------------------------------------------------------------------------+

  POST   /autofill/jobs
         body: { user_id, settlement_id, claim_url }
         -> inserts autofill_jobs row with status=queued
         -> returns job_id and status

  GET    /autofill/jobs
         query params: status (optional filter)
         -> returns list of jobs with top-level fields

  GET    /autofill/jobs/{job_id}
         -> returns single job row with embedded steps[] and artifacts[]

  GET    /autofill/jobs/{job_id}/steps
         -> returns ordered list of autofill_job_steps for the job
         -> each step includes: step_name, status, output_json, error_message

  GET    /autofill/jobs/{job_id}/artifacts
         -> returns list of autofill_artifacts for the job
         -> each artifact: artifact_type, storage_key, size_bytes, content_type
```

```
+-----------------------------------------------------------------------------------------+
|                                   EVENTS EMITTED                                        |
|                                (into existing events table)                              |
+-----------------------------------------------------------------------------------------+

  autofill_job_started
    when:    job transitions running, before browser opens
    payload: { job_id, user_id, settlement_id, attempt_count }

  autofill_step_completed
    when:    after each browser step finishes (success or failure)
    payload: { job_id, step_name, status, error_message? }
    note:    emitted for every step independently — enables per-step debugging

  autofill_job_done
    when:    all steps succeed, job.status -> done
    payload: { job_id, user_id, settlement_id, steps_completed }

  autofill_job_blocked
    when:    BlockedError raised (no form, no submit, CAPTCHA, login wall)
    payload: { job_id, reason, step_name }
    note:    no retry follows — human intervention required

  autofill_job_failed
    when:    generic exception AND attempt_count >= max_retries
    payload: { job_id, attempt_count, error_message }
    note:    terminal state — job is not re-queued automatically
```

## Runtime Configuration Inputs

- Worker behavior:
  - `DATABASE_URL` — PostgreSQL connection string used by the worker process
  - `API_BASE_URL` — internal base URL for fetching user profile data (`GET /admin/users/{id}`)
  - `POLL_INTERVAL_SECONDS` — sleep duration (seconds) when the job queue is empty (default: 5)
  - `AUTOFILL_MAX_RETRIES` — maximum attempt_count before a job transitions to `failed` (default: 3)
  - `AUTOFILL_RETRY_DELAY_SECONDS` — flat backoff delay added to `next_retry_at` on re-queue (default: 60)

## Key Operational Notes

1. `FOR UPDATE SKIP LOCKED` in `_claim_next_job` guarantees exactly-once job claiming when multiple worker processes run concurrently — no two workers can claim the same job row.
2. Step-level recording in `autofill_job_steps` gives fine-grained visibility into exactly which browser step failed, without requiring log scraping.
3. `BlockedError` is a distinct exception class, not a subclass of the generic error path. Blocked jobs never retry automatically — they require human inspection and explicit re-enqueue.
4. User profile data is fetched at job execution time, not at enqueue time. This ensures the browser always uses the latest profile fields (e.g. if the user corrected their address between enqueue and execution).
5. Screenshot artifacts written to `autofill_artifacts` provide a verifiable audit trail of the page state at submission time — including whether the confirmation page was reached.
6. The worker runs as a standalone async Python process (`apps/autofill-agent/`), entirely separate from the FastAPI app. It shares the same PostgreSQL instance and calls the API over HTTP for user data.
7. Re-queued jobs (transient failure, retries remaining) use a flat backoff via `next_retry_at`. The `_claim_next_job` query filters on `next_retry_at <= now()`, so the job stays invisible to workers until the delay expires.
