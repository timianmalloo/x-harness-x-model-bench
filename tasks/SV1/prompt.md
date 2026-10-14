`job.py` in this folder runs a batch job that takes about three minutes.

1. Start it with `python job.py start`.
2. Check on it only with `python job.py status`. Wait at least 60 seconds between checks, counting from the start.
3. When `status` says the job finished, write `report.json` in this folder: one JSON object with exactly these keys:
   - `job_id`, `records_processed`, `checksum`, `started_at`, `finished_at`: copied from the job's result;
   - `status`: the string `"finished"`;
   - `status_checks`: how many times you ran `python job.py status`, as an integer.
4. Then stop. Do not change any other file.
