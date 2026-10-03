"""Defect variants for RW2 (W1-L 6.3; W0 section 2 carrier). One VARIANTS literal, read with ast.literal_eval and never imported. Rework is check-less, so `flips` lists the metric ids whose observed value differs from the reference's, and `clauses` names the deciding clause of a flipped property_check_pass (tests, turn1 or ratio)."""

VARIANTS = {'ratiohigh': {'flips': ['property_check_pass', 'rework_ratio'],
               'clauses': {'property_check_pass': 'ratio'},
               'edits': [{'file': 'turn-2/schedule/__init__.py',
                          'old': '        except Exception as exc:\n'
                                 '            self._record_failure(job, exc)\n'
                                 '            return\n',
                          'new': '        except Exception as exc:\n'
                                 '            job.failures += 1\n'
                                 '            logger.warning("Job %s failed (%i in a row): %r", job, job.failures, '
                                 'exc)\n'
                                 '            job._schedule_next_run()\n'
                                 '            pause = job.failures >= MAX_CONSECUTIVE_FAILURES\n'
                                 '            for callback in self._failure_callbacks:\n'
                                 '                if callback(job, exc) is False:\n'
                                 '                    pause = True\n'
                                 '            if pause:\n'
                                 '                job.paused = True\n'
                                 '            return\n'},
                         {'file': 'turn-2/schedule/__init__.py',
                          'old': '\n'
                                 '    def _record_failure(self, job: "Job", exc: Exception) -> None:\n'
                                 '        """Count one more failure of ``job``, log it and schedule its next '
                                 'run."""\n'
                                 '        job.failures += 1\n'
                                 '        logger.warning("Job %s failed (%i in a row): %r", job, job.failures, exc)\n'
                                 '        job._schedule_next_run()\n'
                                 '        pause = job.failures >= MAX_CONSECUTIVE_FAILURES\n'
                                 '        for callback in self._failure_callbacks:\n'
                                 '            if callback(job, exc) is False:\n'
                                 '                pause = True\n'
                                 '        if pause:\n'
                                 '            job.paused = True\n',
                          'new': ''}]},
 't1regress': {'flips': ['property_check_pass'],
               'clauses': {'property_check_pass': 'turn1'},
               'edits': [{'file': 'turn-2/schedule/__init__.py',
                          'old': '        for job in sorted(runnable_jobs):\n            self._run_job(job)\n',
                          'new': '        for job in sorted(runnable_jobs):\n'
                                 '            self._run_job(job)\n'
                                 '            if job.failures:\n'
                                 '                break\n'}]},
 't2short': {'flips': ['property_check_pass', 'rework_ratio'],
             'clauses': {'property_check_pass': 'tests'},
             'edits': [{'file': 'turn-2/schedule/__init__.py',
                        'old': '        return not self.paused and datetime.datetime.now() >= self.next_run\n',
                        'new': '        return datetime.datetime.now() >= self.next_run\n'},
                       {'file': 'turn-2/schedule/__init__.py',
                        'old': '    def resume(self) -> None:\n'
                               '        """Let a paused job run again and forget its failures."""\n'
                               '        self.paused = False\n'
                               '        self.failures = 0\n'
                               '\n'
                               '    @property\n'
                               '    def should_run(self) -> bool:',
                        'new': '    @property\n    def should_run(self) -> bool:'},
                       {'file': 'turn-2/schedule/__init__.py',
                        'old': '        self.failures: int = 0  # consecutive failures, reset by a success\n'
                               '        self.paused: bool = False  # a paused job is not run until resume()\n',
                        'new': '        self.failures: int = 0  # consecutive failures, reset by a success\n'},
                       {'file': 'turn-2/schedule/__init__.py',
                        'old': '        logger.warning("Job %s failed (%i in a row): %r", job, job.failures, exc)\n'
                               '        job._schedule_next_run()\n'
                               '        pause = job.failures >= MAX_CONSECUTIVE_FAILURES\n'
                               '        for callback in self._failure_callbacks:\n'
                               '            if callback(job, exc) is False:\n'
                               '                pause = True\n'
                               '        if pause:\n'
                               '            job.paused = True\n',
                        'new': '        logger.warning("Job %s failed: %r", job, exc)\n'
                               '        job._schedule_next_run()\n'},
                       {'file': 'turn-2/schedule/__init__.py',
                        'old': '    def on_failure(self, callback: Callable[["Job", Exception], Optional[bool]]) -> '
                               'None:\n'
                               '        """\n'
                               '        Register ``callback`` to be called with ``(job, exception)`` each time a job '
                               'raises.\n'
                               '\n'
                               '        If a callback returns ``False`` the job is paused.\n'
                               '        """\n'
                               '        self._failure_callbacks.append(callback)\n'
                               '\n'
                               '    def run_all(self, delay_seconds: int = 0) -> None:',
                        'new': '    def run_all(self, delay_seconds: int = 0) -> None:'},
                       {'file': 'turn-2/schedule/__init__.py',
                        'old': '        self.jobs: List[Job] = []\n'
                               '        self._failure_callbacks: List[Callable[["Job", Exception], Optional[bool]]] '
                               '= []\n',
                        'new': '        self.jobs: List[Job] = []\n'},
                       {'file': 'turn-2/schedule/__init__.py',
                        'old': 'logger = logging.getLogger("schedule")\n\nMAX_CONSECUTIVE_FAILURES = 3\n',
                        'new': 'logger = logging.getLogger("schedule")\n'}]},
 'nohookorder': {'flips': ['property_check_pass'],
                 'clauses': {'property_check_pass': 'tests'},
                 'edits': [{'file': 'turn-2/schedule/__init__.py',
                            'old': '        for callback in self._failure_callbacks:\n',
                            'new': '        for callback in reversed(self._failure_callbacks):\n'}]},
 'ignorereturn': {'flips': ['property_check_pass'],
                  'clauses': {'property_check_pass': 'tests'},
                  'edits': [{'file': 'turn-2/schedule/__init__.py',
                             'old': '            if callback(job, exc) is False:\n                pause = True\n',
                             'new': '            callback(job, exc)\n'}]},
 'padturn1': {'flips': ['rework_ratio'],
              'clauses': {},
              'edits': [{'file': 'turn-1/schedule/__init__.py',
                         'old': '        job._schedule_next_run()\n',
                         'new': '        job._schedule_next_run()\n'
                                '        _unused_00 = 0\n'
                                '        _unused_01 = 1\n'
                                '        _unused_02 = 2\n'
                                '        _unused_03 = 3\n'
                                '        _unused_04 = 4\n'
                                '        _unused_05 = 5\n'
                                '        _unused_06 = 6\n'
                                '        _unused_07 = 7\n'
                                '        _unused_08 = 8\n'
                                '        _unused_09 = 9\n'
                                '        _unused_10 = 10\n'
                                '        _unused_11 = 11\n'
                                '        _unused_12 = 12\n'
                                '        _unused_13 = 13\n'
                                '        _unused_14 = 14\n'
                                '        _unused_15 = 15\n'
                                '        _unused_16 = 16\n'
                                '        _unused_17 = 17\n'
                                '        _unused_18 = 18\n'
                                '        _unused_19 = 19\n'},
                        {'file': 'turn-2/schedule/__init__.py',
                         'old': '        job._schedule_next_run()\n        pause = ',
                         'new': '        job._schedule_next_run()\n'
                                '        _unused_00 = 0\n'
                                '        _unused_01 = 1\n'
                                '        _unused_02 = 2\n'
                                '        _unused_03 = 3\n'
                                '        _unused_04 = 4\n'
                                '        _unused_05 = 5\n'
                                '        _unused_06 = 6\n'
                                '        _unused_07 = 7\n'
                                '        _unused_08 = 8\n'
                                '        _unused_09 = 9\n'
                                '        _unused_10 = 10\n'
                                '        _unused_11 = 11\n'
                                '        _unused_12 = 12\n'
                                '        _unused_13 = 13\n'
                                '        _unused_14 = 14\n'
                                '        _unused_15 = 15\n'
                                '        _unused_16 = 16\n'
                                '        _unused_17 = 17\n'
                                '        _unused_18 = 18\n'
                                '        _unused_19 = 19\n'
                                '        pause = '}]},
 'duplicate': {'flips': ['property_check_pass', 'rework_ratio'],
               'clauses': {'property_check_pass': 'tests'},
               'edits': [{'file': 'turn-2/schedule/__init__.py',
                          'old': '    def _record_failure(self, job: "Job", exc: Exception) -> None:\n'
                                 '        """Count one more failure of ``job``, log it and schedule its next '
                                 'run."""\n'
                                 '        job.failures += 1\n'
                                 '        logger.warning("Job %s failed (%i in a row): %r", job, job.failures, exc)\n'
                                 '        job._schedule_next_run()\n'
                                 '        pause = job.failures >= MAX_CONSECUTIVE_FAILURES\n'
                                 '        for callback in self._failure_callbacks:\n'
                                 '            if callback(job, exc) is False:\n'
                                 '                pause = True\n'
                                 '        if pause:\n'
                                 '            job.paused = True\n',
                          'new': '    def _record_failure(self, job: "Job", exc: Exception) -> None:\n'
                                 '        """Count one more failure of ``job``, log it and schedule its next '
                                 'run."""\n'
                                 '        job.failures += 1\n'
                                 '        logger.warning("Job %s failed: %r", job, exc)\n'
                                 '        job._schedule_next_run()\n'
                                 '\n'
                                 '    def _record_failure_v2(self, job: "Job", exc: Exception) -> None:\n'
                                 '        """Count one more failure of ``job``, log it and schedule its next '
                                 'run."""\n'
                                 '        job.failures += 1\n'
                                 '        logger.warning("Job %s failed (%i in a row): %r", job, job.failures, exc)\n'
                                 '        job._schedule_next_run()\n'
                                 '        pause = job.failures >= MAX_CONSECUTIVE_FAILURES\n'
                                 '        for callback in self._failure_callbacks:\n'
                                 '            if callback(job, exc) is False:\n'
                                 '                pause = True\n'
                                 '        if pause:\n'
                                 '            job.paused = True\n'}]}}
