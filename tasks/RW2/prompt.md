When a job raises an exception, `Scheduler.run_pending()` must not stop. It keeps running the other jobs that are due, and it keeps the failed job in the schedule.

Count the failures: `job.failures` starts at 0, grows by 1 each time that job raises, and goes back to 0 the next time the job runs without raising.

Add tests for this to `test_schedule.py`, and keep the existing tests passing.
