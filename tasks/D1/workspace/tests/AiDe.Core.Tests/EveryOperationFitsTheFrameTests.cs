using System.Reflection;
using AiDe.Core.Facts;
using AiDe.Core.Ipc;
using AiDe.Core.Projections;
using AiDe.Core.Store;

namespace AiDe.Core.Tests;

/// <summary>
/// No read operation can build a response the transport will refuse — including one added tomorrow.
/// </summary>
/// <remarks>
/// <para><b>Why this is reflective rather than a list.</b> INV-0003 was found by a user opening a
/// repository. The follow-up audit was run BY HAND against one repository and found two more
/// (<c>evidence</c> at 95.8% of the frame, <c>find</c> returning 461,750 bytes while reporting a
/// 64 KiB cap). Hand-auditing found them once; nothing would find the next one, because the next one
/// will be an operation nobody has added yet.</para>
///
/// <para>So the operation list comes from <see cref="IWorkspaceQueries"/> itself. Writing the list
/// out would be a fixture restating the product's own list (DC-021) and would go stale in exactly
/// the case that matters — a new method with no byte bound, which is precisely how the last three
/// got in.</para>
///
/// <para><b>The fixture is deliberately hostile</b>: long identifiers, because every ceiling in the
/// read surface counts ITEMS while the transport limit is in BYTES, and item size comes from
/// repository content.</para>
/// </remarks>
public sealed class EveryOperationFitsTheFrameTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-frame", Guid.NewGuid().ToString("N"));

    public EveryOperationFitsTheFrameTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    /// <remarks>
    /// <para><b>Members are part of the row universe, so they are part of the fixture.</b>
    /// <c>EntryPointsListing.FromHasType</c> appends one row per <c>has_member</c> fact beside the
    /// one row per <c>has_type</c> subject. A fixture that writes only <c>has_type</c> under-counts
    /// the rows the operation can build, which is the same defect shape as weighing an operation at
    /// its default: the number is real, and it is not the worst case.</para>
    /// </remarks>
    private ProjectionService Hostile()
    {
        var store = WorkspaceStore.Open(Path.Combine(_dir, "facts.db"));
        var padding = new string('N', 300);
        var member = new string('M', 300);
        var facts = new List<EvidenceAssertion>();

        for (var i = 0; i < 3_000; i++)
        {
            var subject = $"Long.Namespace.{padding}.Type{i}";

            facts.Add(new EvidenceAssertion(
                "scope", "rev-1", subject, "has_type", "class",
                EvidenceOrigin.Static, VerificationStatus.Verified,
                new Provenance($"src/{padding}/File{i}.cs", "1:1", "test", "1.0.0", DateTimeOffset.UnixEpoch)));

            // A hub, so Describe and Impact have a worst case worth measuring.
            facts.Add(new EvidenceAssertion(
                "scope", "rev-1", subject, "depends_on", $"Long.Namespace.{padding}.Hub",
                EvidenceOrigin.Static, VerificationStatus.Verified,
                new Provenance($"src/{padding}/File{i}.cs", "1:1", "test", "1.0.0", DateTimeOffset.UnixEpoch)));

            // One member per type: a listing row the has_type-only fixture never counted.
            facts.Add(new EvidenceAssertion(
                "scope", "rev-1", subject, "has_member", $"{member}{i}",
                EvidenceOrigin.Static, VerificationStatus.Verified,
                new Provenance($"src/{padding}/File{i}.cs", "1:1", "test", "1.0.0", DateTimeOffset.UnixEpoch)));
        }

        facts.Add(new EvidenceAssertion(
            "scope", "rev-1", $"Long.Namespace.{padding}.Hub", "has_type", "class",
            EvidenceOrigin.Static, VerificationStatus.Verified,
            new Provenance("src/Hub.cs", "1:1", "test", "1.0.0", DateTimeOffset.UnixEpoch)));

        facts.Add(new EvidenceAssertion(
            "scope", "rev-1", $"Long.Namespace.{padding}.Hub", "has_member", $"{member}Hub",
            EvidenceOrigin.Static, VerificationStatus.Verified,
            new Provenance("src/Hub.cs", "1:1", "test", "1.0.0", DateTimeOffset.UnixEpoch)));

        using (var writer = store.BeginWrite())
        {
            writer.DesireScopeGeneration("scope", 1, "rev-1");
            writer.CommitSnapshot("scope", 1, "rev-1", facts, complete: true);
            writer.Commit();
        }

        return new ProjectionService(store);
    }

    private static int WireBytes(object payload) =>
        System.Text.Encoding.UTF8.GetByteCount(
            System.Text.Json.JsonSerializer.Serialize(
                payload, payload.GetType(),
                new System.Text.Json.JsonSerializerOptions(
                    System.Text.Json.JsonSerializerDefaults.Web)));

    /// <summary>
    /// Each operation invoked ABOVE every count it declares — <see cref="int.MaxValue"/> everywhere.
    /// </summary>
    /// <remarks>
    /// <para><b>Why not the named ceiling.</b> Invoking at the ceiling constant proves the ceiling
    /// fits; invoking at the DEFAULT proves only that the default fits. Neither proves a clamp
    /// exists, because neither asks for more than the operation was already going to give. This
    /// table asked <c>EntryPoints</c> and <c>Graph</c> at their defaults and so could not see that
    /// <c>EntryPoints</c> passed <c>MaxRows</c> straight through to the listing, which floors at 1
    /// and ceils at nothing (INV-0003's shape, one operation later). Passing
    /// <see cref="int.MaxValue"/> is the only request that proves a caller cannot exceed the bound.</para>
    /// </remarks>
    private static Dictionary<string, Func<ProjectionService, string, object>> AtCeiling() => new(StringComparer.Ordinal)
    {
        [nameof(IWorkspaceQueries.EvidenceAsync)] =
            (p, _) => p.Evidence(null, int.MaxValue),

        [nameof(IWorkspaceQueries.FindAsync)] =
            (p, _) => p.Find("Type", int.MaxValue),

        [nameof(IWorkspaceQueries.KnowledgeAsync)] =
            (p, _) => p.Knowledge(new KnowledgeQuery(null, null, int.MaxValue)),

        [nameof(IWorkspaceQueries.DescribeAsync)] =
            (p, hub) => p.Describe(hub, int.MaxValue),

        [nameof(IWorkspaceQueries.ImpactAsync)] =
            (p, hub) => p.Impact(hub, int.MaxValue, int.MaxValue),

        [nameof(IWorkspaceQueries.GraphAsync)] =
            (p, _) => p.Graph(new GraphQuery(int.MaxValue)),

        // The two operations here whose size comes from FILES rather than from the fact table, which
        // is exactly why they need weighing: repository content is unbounded and a frame is not.
        [nameof(IWorkspaceQueries.NodeContentAsync)] =
            (p, hub) => p.NodeContent(hub),

        // Worse than NodeContent on paper — that reads one file, this reads up to MaxContentFiles of
        // them and may match every line of each. Weighed at both ceilings at once, because a bound
        // that is only ever exercised one at a time is not the shape that overflows a frame.
        [nameof(IWorkspaceQueries.SearchContentAsync)] =
            (p, _) => p.SearchContent("e", int.MaxValue),

        // A caller's whole outgoing sequence. Weighed at the ceiling because the bound is on
        // MESSAGES, and a message carries two type ids — the widest rows in the store.
        [nameof(IWorkspaceQueries.InteractionAsync)] =
            (p, hub) => p.Interaction(hub, int.MaxValue),

        [nameof(IWorkspaceQueries.PathsAsync)] =
            (p, hub) => p.Paths(new PathQuery(hub, hub, int.MaxValue, int.MaxValue)),

        // Depth stays 1 — it is a grouping GRAIN, not a count of returned things, and the count
        // beside it is the one that bounds the response.
        [nameof(IWorkspaceQueries.OverviewAsync)] =
            (p, _) => p.Overview(new OverviewQuery(1, int.MaxValue)),

        [nameof(IWorkspaceQueries.SolutionTreeAsync)] =
            (p, _) => p.SolutionTree(new SolutionTreeQuery(int.MaxValue, int.MaxValue)),

        [nameof(IWorkspaceQueries.EntryPointsAsync)] =
            (p, _) => p.EntryPoints(new EntryPointsQuery(int.MaxValue)),
    };

    [Fact]
    public void EveryReadOperationIsCoveredByThisTest()
    {
        // THE CONTROL ON THE CONTROL. A new method on the read surface with no entry here is a new
        // way to overflow the frame that nobody is watching — which is how the last three got in.
        var declared = typeof(IWorkspaceQueries)
            .GetMethods(BindingFlags.Public | BindingFlags.Instance)
            .Select(m => m.Name)
            .ToHashSet(StringComparer.Ordinal);

        var covered = AtCeiling().Keys.ToHashSet(StringComparer.Ordinal);

        var missing = declared.Except(covered).Order(StringComparer.Ordinal).ToList();

        Assert.True(missing.Count == 0,
            $"IWorkspaceQueries gained {string.Join(", ", missing)} with no frame-size check. " +
            "Add it to AtCeiling() — an operation whose response nobody has weighed is INV-0003 " +
            "waiting for a big enough repository.");
    }

    [Fact]
    public void NoOperationCanBuildAResponseTheTransportWouldRefuse()
    {
        var projections = Hostile();
        var hub = $"Long.Namespace.{new string('N', 300)}.Hub";

        var oversized = new List<string>();

        foreach (var (operation, invoke) in AtCeiling())
        {
            var bytes = WireBytes(invoke(projections, hub));

            if (bytes > IpcFraming.MaxFrameBytes)
            {
                oversized.Add($"{operation} = {bytes:N0} bytes");
            }
        }

        Assert.True(oversized.Count == 0,
            $"these responses cannot cross the {IpcFraming.MaxFrameBytes:N0}-byte frame: " +
            string.Join("; ", oversized));
    }
}
