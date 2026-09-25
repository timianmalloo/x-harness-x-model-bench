using System;
using System.IO;
using System.Threading;

if (!File.Exists("marker.txt") || !File.Exists("hidden.txt"))
    return 3;

var mode = args[0];
if (mode == "hang")
{
    File.WriteAllText(args[1], Environment.ProcessId.ToString());
    Thread.Sleep(Timeout.Infinite);
}

Directory.CreateDirectory("TestResults");
var path = Path.Combine("TestResults", mode == "wrong-file" ? "decoy.trx" : "results.trx");
if (mode != "missing")
{
    var total = mode == "zero" ? 0 : 2;
    var passed = mode == "partial" ? 1 : total;
    var body = mode == "malformed" ? "not xml" :
        $"<TestRun xmlns=\"http://microsoft.com/schemas/VisualStudio/TeamTest/2010\"><ResultSummary outcome=\"Completed\"><Counters total=\"{total}\" passed=\"{passed}\" /></ResultSummary></TestRun>";
    File.WriteAllText(path, body);
}
return mode == "partial" ? 1 : 0;
