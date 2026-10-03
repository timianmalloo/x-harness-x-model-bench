"""S1 hidden check, skeleton (W1-I section 15): every case is `exploited` until the probes land. Stdlib and bench_check only."""

import bench_check as bc


def check(ctx):
    bc.write_result([bc.run_case(case, lambda: "exploited") for case in ctx.cases])


bc.main(check)
