"""S1 hidden check, skeleton (W1-I section 15): every case is `exploited` until the probes land. Stdlib and bench_check only."""

import bench_check as bc

MARK = ""            # the planted value in the other principal's note (neutral until the probes land)
INJ_A = ()           # inj-1 clause (a): tautology payloads
INJ_B = ()           # inj-1 clause (b): quote-break payloads
INJ_3 = ()           # inj-3: id payloads


def check(ctx):
    bc.write_result([bc.run_case(case, lambda: "exploited") for case in ctx.cases])


bc.main(check)
