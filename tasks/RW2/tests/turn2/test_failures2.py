"""Hidden tests for RW2 turn 2 (W1-L section 6.3). Stdlib only; run with `python -S -m unittest`."""

import datetime
import unittest

import schedule


def rearm(job):
    job.next_run = datetime.datetime.now() - datetime.timedelta(seconds=1)


def run(scheduler):
    """`run_pending()`, with an exception that escapes it reported as a failed assertion."""
    try:
        scheduler.run_pending()
    except Exception as exc:  # noqa: BLE001 - the point of the call
        raise AssertionError("run_pending() let %r escape" % (exc,)) from None


def failing_job(scheduler, error=None):
    """A job that always raises `error`. Returns the job and the list its function appends one item to per call."""
    calls = []

    def bad():
        calls.append(1)
        raise error or RuntimeError("boom")

    return scheduler.every(1).seconds.do(bad), calls


class Failures2Tests(unittest.TestCase):
    def test_t2_1_callbacks_run_in_registration_order(self):
        scheduler = schedule.Scheduler()
        order = []
        scheduler.on_failure(lambda job, exc: order.append("a"))
        scheduler.on_failure(lambda job, exc: order.append("b"))
        scheduler.on_failure(lambda job, exc: order.append("c"))
        job, _ = failing_job(scheduler)
        rearm(job)
        run(scheduler)
        self.assertEqual(order, ["a", "b", "c"])

    def test_t2_2_callbacks_receive_the_job_then_the_exception(self):
        scheduler = schedule.Scheduler()
        seen = []
        scheduler.on_failure(lambda *args: seen.append(args))
        error = ValueError("the one that was raised")
        job, _ = failing_job(scheduler, error)
        rearm(job)
        run(scheduler)
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(seen[0]), 2)
        self.assertIs(seen[0][0], job)
        self.assertIs(seen[0][1], error)

    def test_t2_3_a_job_that_fails_three_times_in_a_row_is_paused(self):
        scheduler = schedule.Scheduler()
        job, calls = failing_job(scheduler)
        for _ in range(6):
            rearm(job)
            run(scheduler)
        self.assertEqual(len(calls), 3)

    def test_t2_4_resume_runs_the_job_again_and_clears_the_count(self):
        scheduler = schedule.Scheduler()
        job, calls = failing_job(scheduler)
        for _ in range(10):
            rearm(job)
            run(scheduler)
        paused_at = len(calls)
        self.assertGreaterEqual(paused_at, 1)
        self.assertLess(paused_at, 10)
        job.resume()
        self.assertEqual(job.failures, 0)
        rearm(job)
        run(scheduler)
        self.assertEqual(len(calls), paused_at + 1)

    def test_t2_5_failures_still_counts_and_resets_with_a_callback_registered(self):
        scheduler = schedule.Scheduler()
        scheduler.on_failure(lambda job, exc: None)
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) <= 2:
                raise RuntimeError("boom")

        job = scheduler.every(1).seconds.do(flaky)
        for expected in (1, 2):
            rearm(job)
            run(scheduler)
            self.assertEqual(job.failures, expected)
        rearm(job)
        run(scheduler)
        self.assertEqual(job.failures, 0)

    def test_t2_6_a_callback_that_returns_false_pauses_the_job_after_one_failure(self):
        scheduler = schedule.Scheduler()
        scheduler.on_failure(lambda job, exc: False)
        job, calls = failing_job(scheduler)
        for _ in range(3):
            rearm(job)
            run(scheduler)
        self.assertEqual(len(calls), 1)
