// Test parallelization is disabled deliberately, for two reasons that both bite this suite:
//   1. ActivityListener is process-global. With classes running concurrently, one class's spans
//      land in another's capture list and telemetry assertions see phantom activities.
//   2. These are integration tests against real SQLite files and real temp directories, so serial
//      execution keeps failures attributable rather than interleaved.
// The whole suite runs in well under a second, so the wall-clock cost is not worth trading away
// determinism for.
[assembly: CollectionBehavior(DisableTestParallelization = true)]
