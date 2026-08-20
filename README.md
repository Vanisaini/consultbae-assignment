# ConsultBae AI Automation Assignment

This project merges messy people data from multiple sources into one SQLite database, adds an n8n duplicate-check automation, and includes a mini audio collection app built with Streamlit.

## Project Structure

```text
consultbae-assignment/
|
|-- app/
|   `-- app.py
|
|-- automation/
|   `-- n8n-flow.json
|
|-- data/
|   |-- source1_naukri_applicants.csv
|   |-- source2_gig_workers.csv
|   `-- source3_cbnexus_contacts.csv
|
|-- scripts/
|   `-- merge_data.py
|
|-- uploads/
|-- api.py
|-- database.db
|-- requirements.txt
`-- README.md
```

## Task 1 - Data Merge

The three CSV files contain overlapping people with inconsistent data.

The merge pipeline:

- Loads all three source files.
- Normalizes names, email addresses and phone numbers.
- Matches people using available identifiers.
- Merges duplicate records into a single person.
- Tracks which source(s) each person appeared in.
- Stores the final result in SQLite.

Run:

```bash
python scripts/merge_data.py
```

The final data is stored in `database.db`.

Main table: `people`

## Matching Strategy

There is no single shared ID across the three sources.

I therefore used normalized identifiers such as:

- Email address
- Phone number
- Normalized name
- Cross-source evidence

Email and phone were treated as stronger identifiers than name alone.

Where multiple source records matched the same person, their information was merged into one database record.

## Task 2 - n8n Automation

A working n8n automation was created to check whether a person already exists in the merged database.

Flow:

```text
Webhook
   |
   v
JavaScript normalization
   |
   v
HTTP Request
   |
   v
FastAPI duplicate-check API
   |
   v
IF
   |-- True  -> Duplicate response
   `-- False -> No duplicate response
```

Production webhook:

```text
POST /webhook/check-duplicate
```

Example request:

```json
{
  "name": "Arjun Mishra",
  "email": "arjun.mishra70@example.com",
  "phone": "9000000106"
}
```

Example duplicate response:

```json
{
  "duplicate": true,
  "message": "Duplicate record found",
  "matched_by": "email"
}
```

The n8n workflow is exported to:

```text
automation/n8n-flow.json
```

## Task 3 - GigVoice Audio Collection App

The Streamlit app allows a gig worker to:

- Enter their full name.
- Enter their phone number.
- Upload a WAV recording.
- Preview the audio.
- Submit the recording.
- Store the audio file.
- Store the submission in SQLite.
- View previous submissions.

For every submitted audio file, the app extracts:

- Duration
- Sample rate in kHz
- Bitrate
- Loudness in dB

The Submissions page provides an audio player and displays the extracted metadata.

Run the app:

```bash
streamlit run app/app.py
```

Then open:

```text
http://localhost:8501
```

## FastAPI Service

The n8n workflow uses a small FastAPI service to query SQLite.

Run:

```bash
python -m uvicorn api:app --reload --port 8000
```

API endpoint:

```text
POST /check-duplicate
```

## Data Quality Issues Found

### 1. Duplicate people across sources

The same person appeared in multiple CSV files.

**Solution:** Records were matched and merged into a single person record.

### 2. No common identifier

The three systems did not share one universal ID.

**Solution:** Email, phone and normalized names were used as matching signals.

### 3. Inconsistent name formatting

Names could contain differences in capitalization or spacing.

**Solution:** Names were trimmed and normalized before comparison.

### 4. Email formatting differences

Email addresses could contain capitalization or extra whitespace.

**Solution:** Emails were stripped and converted to lowercase before matching.

### 5. Phone formatting differences

Phone numbers could contain different formatting or non-digit characters.

**Solution:** Phone numbers were normalized to digits before matching.

### 6. Missing values

Some source records contained incomplete fields.

**Solution:** Missing information did not automatically cause records to be discarded. Available information from matching records was retained.

### 7. Different fields across systems

Each source provided different attributes.

**Solution:** A wider `people` schema was used so useful fields from the source systems could be preserved.

### 8. Source provenance

After merging, it was important to know which systems contained each person.

**Solution:** Source information was preserved in the merged database.

### 9. Similar names

Names alone are not reliable identifiers because different people can share the same name.

**Solution:** Strong identifiers such as normalized email and phone were preferred for duplicate detection.

### 10. SQLite write locking

During development, DB Browser and the Streamlit app sometimes attempted to access SQLite at the same time.

**Solution:** Unnecessary DB Browser write sessions were closed and the application uses SQLite busy timeout, proper connection cleanup and WAL mode.

## Stuck Log

### 1. SQLite could not be used directly from n8n

I initially expected to connect n8n directly to the SQLite database, but the installed n8n setup did not provide the SQLite integration I needed.

Instead of changing the project database, I created a small FastAPI endpoint that queries the existing SQLite database. n8n sends normalized person data to that endpoint using an HTTP Request node.

I rejected migrating the project to another database because it would add unnecessary infrastructure and complexity for the take-home assignment.

### 2. n8n test webhook returned 404

During testing I received:

```text
The requested webhook "check-duplicate" is not registered.
```

The `/webhook-test/` endpoint is available only while the workflow is actively listening for a test event.

I fixed the issue by starting the test listener before sending the request. After publishing the workflow, I used the production webhook:

```text
/webhook/check-duplicate
```

### 3. SQLite database was locked

The audio app initially failed with:

```text
database is locked
```

The SQLite database was also open in DB Browser while Streamlit attempted to write.

I closed the DB Browser write session and used:

- SQLite `busy_timeout`
- WAL journal mode
- Proper connection closing

This resolved the locking issue during normal testing.

## Setup

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the merge pipeline:

```bash
python scripts/merge_data.py
```

Run FastAPI:

```bash
python -m uvicorn api:app --reload --port 8000
```

Run Streamlit in another terminal:

```bash
streamlit run app/app.py
```

Run n8n in another terminal:

```bash
n8n
```

## Demo Checklist

During the demo video:

1. Show the three input CSV files.
2. Run the merge pipeline.
3. Show the merged SQLite `people` data.
4. Open the n8n workflow.
5. Demonstrate a duplicate request.
6. Demonstrate a non-duplicate request.
7. Open GigVoice.
8. Upload a WAV audio sample.
9. Show the extracted metadata.
10. Open the Submissions page and play the stored audio.
11. Briefly explain the matching strategy and the main issues encountered.

## Notes

This project prioritizes working end-to-end behavior, clear matching logic, and explainable implementation decisions.
