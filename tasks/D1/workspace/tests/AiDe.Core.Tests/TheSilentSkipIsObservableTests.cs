using System.Diagnostics;
using System.Runtime.Versioning;
using AiDe.Core.Facts;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// The two content paths say what happened, in the telemetry, on every outcome — including the ones
/// that return an empty answer.
/// </summary>
/// <remarks>
/// <para><b>INV-0014 P4 (Ruling 132, Stream X).</b> Both extractors wrote a scope id into
/// <c>Provenance.ArtifactPathId</c> (DC-229, repaired at P2). <c>NodeContent</c> told the operator —
/// <i>"the source for this node could not be located (typescript:src/frontend)"</i>. <c>SearchContent</c>
/// resolves through the same call and did not: every TypeScript and Python file in every workspace
/// was counted into a bare <c>skipped</c> integer, so a content search over a React codebase returned
/// "no matches" rather than "I could not open 1,100 files". Nothing recorded for how long, because
/// there was nothing to read the number against.</para>
///
/// <para><b>A count with no reason is not a signal.</b> The repair is not a bigger reply — it is a
/// span that carries the outcome and, for the search, a per-reason breakdown, so the defect's shape
/// is a spike in one named bucket. The reply stays opaque on purpose
/// (<c>ProjectionService.ResolveWithinWorkspace</c>: "answering it in the reply would describe the
/// filesystem to whoever asked"), and
/// <see cref="TheReplyStillDescribesNoFilesystemToTheCaller"/> is what keeps it that way.</para>
///
/// <para><b>Seeded, not indexed.</b> These commit provenance shapes directly rather than running an
/// extractor, because the shape under test is one no extractor emits any more — P2 removed it. A
/// fixture that could only produce correct paths could not red this test.</para>
/// </remarks>
public sealed class TheSilentSkipIsObservableTests : IDisposable
{
    private static readonly DateTimeOffset Observed = new(2026, 9, 17, 0, 0, 0, TimeSpan.Zero);

    private const string Scope = "csharp:fixture";

    /// <summary>The value DC-229 wrote into the field that is supposed to name a file.</summary>
    private const string ScopeIdInThePathField = "typescript:src/frontend";

    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-content-telemetry", Guid.NewGuid().ToString("N"));

    private readonly TestWorkspace _workspace = TestWorkspace.Create();
    private readonly List<Activity> _captured = [];
    private readonly ActivityListener _listener;

    public TheSilentSkipIsObservableTests()
    {
        Directory.CreateDirectory(Path.Combine(_root, "src"));
        File.WriteAllText(Path.Combine(_root, "src", "Order.cs"), "// the marker is here\n");
        File.WriteAllText(Path.Combine(_root, "src", "Locked.cs"), "// the marker is here too\n");
        File.WriteAllBytes(Path.Combine(_root, "src", "notes.bin"), [0x00, 0x01, 0x02]);

        _listener = new ActivityListener
        {
            ShouldListenTo = source => source.Name == "aide.projection.query",
            Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
            ActivityStopped = activity =>
            {
                lock (_captured)
                {
                    _captured.Add(activity);
                }
            },
        };

        ActivitySource.AddActivityListener(_listener);

        _workspace.CommitSnapshot(Scope, 1, "rev-1",
            // The scope's own location. `declared_at` is outside the corpus predicates, so this row
            // is never itself a file to search.
            Fact(Scope, "declared_at", "", "scope.md"),
            Fact("node:order", "has_type", "Class", "src/Order.cs"),
            Fact("node:locked", "has_type", "Class", "src/Locked.cs"),
            Fact("node:binary", "has_type", "Class", "src/notes.bin"),
            Fact("node:ghost", "has_type", "Class", "src/Gone.cs"),
            Fact("node:scoped", "has_type", "Class", ScopeIdInThePathField));
    }

    public void Dispose()
    {
        _listener.Dispose();
        _workspace.Dispose();
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { }
    }

    private static EvidenceAssertion Fact(
        string subject, string predicate, string @object, string artifactPath) =>
        new(Scope, "rev-1", subject, predicate, @object, EvidenceOrigin.Static,
            VerificationStatus.Verified,
            new Provenance(artifactPath, null, "fixture-extractor", "1.0.0", Observed));

    private ProjectionService Projections => new(_workspace.Store, _root);

    private Activity LastSpan(string projection)
    {
        lock (_captured)
        {
            var span = _captured.LastOrDefault(a => a.GetTagItem("projection") as string == projection);
            Assert.True(span is not null, $"no '{projection}' span was recorded at all");
            return span!;
        }
    }

    private static string? Tag(Activity span, string name) => span.GetTagItem(name) as string;

    /// <summary>
    /// A bucket that is absent reads as "not recorded" and fails here; it must never be read as
    /// zero, which is a plausible wrong number (IO9).
    /// </summary>
    private static int Bucket(Activity span, string name)
    {
        var value = span.GetTagItem(name);

        Assert.True(
            value is int,
            $"'{name}' is {(value is null ? "not recorded" : $"a {value.GetType().Name}")} — "
            + "a skip reason that is not counted cannot be read as a defect signal");

        return (int)value!;
    }

    // ---- NodeContent: the five outcomes, each with a stable error code -------

    /// <remarks>
    /// The five values and the codes are written as literals, not as the constants under test: a
    /// stable error code whose test reads it from the same constant proves only that the constant
    /// equals itself, and would let a rename travel silently to every operator's saved search.
    /// </remarks>
    [Theory]
    [InlineData("node:order", "located", null)]
    [InlineData("node:absent", "no-declaration", "AIDE-PROJECTION-CONTENT-NO-DECLARATION")]
    [InlineData("node:ghost", "unresolvable", "AIDE-PROJECTION-CONTENT-UNRESOLVABLE")]
    [InlineData("node:scoped", "unresolvable", "AIDE-PROJECTION-CONTENT-UNRESOLVABLE")]
    [InlineData("node:binary", "not-rendered", "AIDE-PROJECTION-CONTENT-NOT-RENDERED")]
    public void TheContentSpanSaysWhichOfTheFiveOutcomesItWas(
        string nodeId, string outcome, string? errorCode)
    {
        Projections.NodeContent(nodeId);

        var span = LastSpan("node-content");

        Assert.Equal(outcome, Tag(span, "content.outcome"));
        Assert.Equal(errorCode, Tag(span, "error.code"));
    }

    /// <summary>
    /// The fifth outcome. An exclusive handle is the only way to make a real file unreadable without
    /// asserting against a mock of the filesystem.
    /// </summary>
    [Fact]
    [SupportedOSPlatform("windows")]
    [Trait("Platform", "Windows")]
    public void AFileTheReaderCannotOpenIsTaggedUnreadableRatherThanLocated()
    {
        using var exclusive = new FileStream(
            Path.Combine(_root, "src", "Locked.cs"), FileMode.Open, FileAccess.Read, FileShare.None);

        Projections.NodeContent("node:locked");

        var span = LastSpan("node-content");

        Assert.Equal("unreadable", Tag(span, "content.outcome"));
        Assert.Equal("AIDE-PROJECTION-CONTENT-UNREADABLE", Tag(span, "error.code"));
    }

    // ---- SearchContent: the skip count, by reason ----------------------------

    /// <summary>
    /// The DC-229 shape lands in its own bucket, and does not hide among files that are merely
    /// missing.
    /// </summary>
    [Fact]
    public void TheSkipCountIsBrokenDownByReason()
    {
        var result = Projections.SearchContent("marker", 50);

        Assert.Equal(2, result.FilesSkipped);

        var span = LastSpan("content-search");

        Assert.Equal(1, Bucket(span, "search.skipped.no_artifact_path"));
        Assert.Equal(1, Bucket(span, "search.skipped.unresolved_path"));
        Assert.Equal(0, Bucket(span, "search.skipped.unreadable"));
        Assert.Equal(0, Bucket(span, "search.skipped.too_large"));
    }

    [Fact]
    [SupportedOSPlatform("windows")]
    [Trait("Platform", "Windows")]
    public void AFileTheSearchCannotOpenLandsInTheUnreadableBucket()
    {
        using var exclusive = new FileStream(
            Path.Combine(_root, "src", "Locked.cs"), FileMode.Open, FileAccess.Read, FileShare.None);

        Projections.SearchContent("marker", 50);

        Assert.Equal(1, Bucket(LastSpan("content-search"), "search.skipped.unreadable"));
    }

    /// <summary>
    /// The control that keeps the breakdown whole: a skip site added without a bucket makes the
    /// buckets disagree with the number the reply already carries, and that is a failing test rather
    /// than a quietly under-counted signal.
    /// </summary>
    [Fact]
    public void EverySkipIsAccountedForByExactlyOneBucket()
    {
        var result = Projections.SearchContent("marker", 50);

        var span = LastSpan("content-search");

        var accounted =
            Bucket(span, "search.skipped.no_artifact_path")
            + Bucket(span, "search.skipped.unresolved_path")
            + Bucket(span, "search.skipped.unreadable")
            + Bucket(span, "search.skipped.too_large");

        Assert.Equal(result.FilesSkipped, accounted);
    }

    // ---- and the reply is not where any of this goes -------------------------

    /// <summary>
    /// P4 is telemetry, not a wider contract. The breakdown names why a file could not be opened,
    /// which is a statement about the filesystem — an operator question, deliberately not answered
    /// to whoever asked (<c>ProjectionService.ResolveWithinWorkspace</c>).
    /// </summary>
    [Fact]
    public void TheReplyStillDescribesNoFilesystemToTheCaller()
    {
        var members = typeof(ContentSearchResult)
            .GetProperties()
            .Select(p => p.Name)
            .Order(StringComparer.Ordinal)
            .ToArray();

        Assert.Equal(
            ["Bounds", "FilesSearched", "FilesSkipped", "Matches", "SourceRevision", "Truncated"],
            members);
    }
}
