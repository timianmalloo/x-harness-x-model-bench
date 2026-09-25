using System;
using System.IO;
using System.Threading;

if (!File.Exists("marker.txt") || !File.Exists("hidden.txt"))
    return 3;
if (Environment.GetEnvironmentVariable("MSBUILDDISABLENODEREUSE") != "1" ||
    Environment.GetEnvironmentVariable("UseSharedCompilation") != "false" ||
    Environment.GetEnvironmentVariable("DOTNET_CLI_TELEMETRY_OPTOUT") != "1" ||
    Environment.GetEnvironmentVariable("GIT_CONFIG_KEY_0") != "core.fsmonitor" ||
    Environment.GetEnvironmentVariable("GIT_CONFIG_VALUE_0") != "false")
    return 4;

var mode = args[0];
if (mode == "hang")
{
    File.WriteAllText(args[1], Environment.ProcessId.ToString());
    Thread.Sleep(Timeout.Infinite);
}

var folder = mode is "nested" or "duplicate" ? Path.Combine("subproject", "TestResults") : "TestResults";
Directory.CreateDirectory(folder);
var path = Path.Combine(folder, mode == "wrong-file" ? "decoy.trx" : "results.trx");
if (mode != "missing")
{
    var total = mode == "zero" ? 0 : 2;
    var passed = mode == "partial" ? 1 : total;
    var body = mode == "malformed" ? "not xml" :
        $"<TestRun xmlns=\"http://microsoft.com/schemas/VisualStudio/TeamTest/2010\"><ResultSummary outcome=\"Completed\"><Counters total=\"{total}\" passed=\"{passed}\" /></ResultSummary></TestRun>";
    File.WriteAllText(path, body);
    if (mode == "duplicate")
    {
        Directory.CreateDirectory("TestResults");
        File.WriteAllText(Path.Combine("TestResults", "results.trx"), body);
    }
}
return mode is "partial" or "exit-one" ? 1 : 0;
