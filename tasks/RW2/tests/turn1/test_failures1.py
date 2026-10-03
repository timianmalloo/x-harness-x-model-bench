"""Hidden tests for RW2 turn 1 (W1-L section 6.3). Stdlib only; run with `python -S -m unittest`."""

import datetime
import unittest

import schedule


def rearm(job):
    """Make the job due now. The tests control the clock this way, so they hold for any rescheduling rule."""
    job.next_run = datetime.datetime.now() - datetime.timedelta(seconds=1)


def run(scheduler):
    """`run_pending()`, with an exception that escapes it reported as a failed assertion."""
    try:
        scheduler.run_pending()
    except Exception as exc:  # noqa: BLE001 - the point of the call
        raise AssertionError("run_pending() let %r escape" % (exc,)) from None


class Failures1Tests(unittest.TestCase):
    def test_t1_1_other_jobs_run_after_a_job_raises(self):
        scheduler = schedule.Scheduler()
        ran = []

        def bad():
            raise RuntimeError("boom")

        def good():
            ran.append("good")

        first = scheduler.every(1).seconds.do(bad)
        second = scheduler.every(1).seconds.do(good)
        now = datetime.datetime.now()
        first.next_run = now - datetime.timedelta(seconds=2)
        second.next_run = now - datetime.timedelta(seconds=1)
        run(scheduler)
        self.assertEqual(ran, ["good"])
        self.assertIn(first, scheduler.get_jobs())

    def test_t1_2_failures_counts_consecutive_failures(self):
        scheduler = schedule.Scheduler()

        def bad():
            raise RuntimeError("boom")

        job = scheduler.every(1).seconds.do(bad)
        self.assertEqual(job.failures, 0)
        for expected in (1, 2):
            rearm(job)
            run(scheduler)
            self.assertEqual(job.failures, expected)

    def test_t1_3_a_success_resets_failures_to_zero(self):
        scheduler = schedule.Scheduler()
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) <= 2:
                raise RuntimeError("boom")

        job = scheduler.every(1).seconds.do(flaky)
        for _ in range(2):
            rearm(job)
            run(scheduler)
        self.assertEqual(job.failures, 2)
        rearm(job)
        run(scheduler)
        self.assertEqual(len(calls), 3)
        self.assertEqual(job.failures, 0)
