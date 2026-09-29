namespace AiDe.Core.Projections;

/// <summary>How many listing rows a query asks for.</summary>
/// <remarks>
/// The default is the ceiling: one constant in two roles, so a caller who asks for nothing and a
/// caller who asks for everything land on the same bound. <c>GraphQuery.MaxNodes</c> is shaped the
/// same way against <c>GraphProjection.DefaultMaxNodes</c>.
/// </remarks>
public sealed record EntryPointsQuery(int MaxRows = EntryPointsProjection.MaxRowsCeiling);

public enum EntryPointKind { Api, Ux, Cli, Unclassified }

/// <summary>One row is one entry-point candidate occurrence in the current snapshot.</summary>
/// <param name="NodeId"><c>node_dim.node_id</c> when the occurrence is already a graph node; otherwise null.</param>
public sealed record EntryPointRow(
    EntryPointKind Kind,
    string? NodeId,
    string Display,
    string? UnclassifiedReason);

public sealed record EntryPointsResult(
    IReadOnlyList<EntryPointRow> Rows,
    int OmittedByCap,
    IReadOnlyList<string> Disclosures,
    string SourceRevision);

/// <summary>
/// UV-0 listing: every latest-generation <c>has_type</c> source node is a row.
/// Name heuristics classify api/ux/cli; otherwise unclassified (never silent-drop).
/// Open Sequence is not this query (mapper r5: authorship only, Sequence still disabled).
/// </summary>
public static class EntryPointsProjection
{
    /// <summary>
    /// The most rows a listing may return, so the response still crosses one IPC frame — the
    /// query's default and the ceiling <c>ProjectionService.EntryPoints</c> clamps to.
    /// </summary>
    /// <remarks>
    /// <para><b>MEASURED, not chosen.</b> The first value here was 5_000 — "inferred until measured,
    /// same order as graph node default" — and it was the arithmetic of INV-0003:
    /// <c>EveryOperationFitsTheFrameTests</c> built a 2,191,570-byte response, 2.09x the
    /// 1,048,576-byte frame, so <c>EntryPointsAsync</c> could not be answered over the wire at all.
    /// A count borrowed from another projection is not a byte bound; rows carry node ids, and node
    /// ids come from repository content.</para>
    ///
    /// <para><b>The measurement.</b> That test's own <c>WireBytes</c> over its hostile fixture
    /// (300-character identifiers), at two caps so the per-row cost separates from the envelope:
    /// 1,000 rows = 730,850 bytes, 2,000 rows = 1,461,628 bytes, so one row costs
    /// (1,461,628 - 730,850) / 1,000 = <b>730.78 bytes</b>. Confirmed on a second pair: 1,100 rows =
    /// 803,928 and 2,100 rows = 1,534,704, the same 730.78. A row serialised alone is 720-730 bytes,
    /// so <b>731</b> bounds it from above once the array's separating comma is counted. The envelope
    /// around the rows measured 72-78 bytes; <b>512</b> is allowed for it, which covers a real
    /// 40-character source revision and the <c>Omitted (n)</c> disclosure with room over.</para>
    ///
    /// <para><b>The arithmetic.</b> The budget is <c>ProjectionService.MaxResponseBytes</c> =
    /// 896 KiB = 917,504 bytes — the frame less 128 KiB, which is the margin every other operation
    /// is weighed against, and the one INV-0003 settled on. So
    /// <c>floor((917,504 - 512) / 731) = floor(916,992 / 731) = 1,254</c>. It is the largest cap that
    /// fits: 1,254 x 731 + 512 = 917,186 (inside), 1,255 x 731 + 512 = 917,917 (outside).</para>
    ///
    /// <para><b>What this bound is not.</b> It is a count, and the transport limit is in bytes, so it
    /// holds only while a row stays under 731 bytes — an identifier twice the fixture's length
    /// overflows the frame at this cap too. The durable fix is the byte budget every other
    /// projection carries; this is the cap the evidence supports today, and the listing's
    /// <c>Omitted (n)</c> disclosure keeps it honest on the surface rather than silent.</para>
    ///
    /// <para><b>A count is only a bound where something clamps it.</b> Until this was renamed it was
    /// <c>DefaultMaxRows</c> and it was only a default: <c>ProjectionService.EntryPoints</c> passed
    /// <c>query.MaxRows</c> straight through, and <c>EntryPointsListing.FromHasType</c> floors
    /// at 1 and ceils at nothing — so any caller naming a number owned the frame. The frame test
    /// could not see it, because it invoked the operation at its DEFAULT, which is the one request
    /// that can never exceed the bound. It now invokes every operation at
    /// <c>int.MaxValue</c>, and the service clamps.</para>
    ///
    /// <para><b>Re-derived against a fixture that counts members.</b> The measuring fixture wrote
    /// only <c>has_type</c> facts while <c>EntryPointsListing.FromHasType</c> also appends one
    /// row per <c>has_member</c>, so it under-counted the row universe; it now writes one
    /// 300-character member per type, making that universe 3,001 types + 3,001 members = 6,002 rows.
    /// MEASURED on the widened fixture: at <c>int.MaxValue</c> the response is
    /// <b>4,332,058</b> bytes (2,191,570 before the widening), 4.13x the frame. The arithmetic above
    /// did not move: the widened fixture measures 730,850 bytes at 1,000 rows and 1,461,628 at 2,000
    /// — byte for byte what the has_type-only fixture measured — because rows are taken types-first
    /// and the first 3,001 are the same rows. A member row measures
    /// <c>(2,905,355 - 2,191,589) / 1,000</c> = <b>713.77</b> bytes, NARROWER than a type row's
    /// 730.78, so counting members cannot loosen a cap derived from the wider row. 1,254 stands,
    /// measured rather than assumed.</para>
    /// </remarks>
    public const int MaxRowsCeiling = 1_254;

    public const string UnclassifiedReasonPendingClassifier = "classifier-not-admitted";
}

/// <summary>Store-facing listing. Lives next to the DTO so tests can name the query without IPC.</summary>
public static class EntryPointsListing
{
    public static EntryPointsResult FromHasType(
        IReadOnlyList<(string NodeId, string TypeKind)> candidates,
        int maxRows,
        string sourceRevision,
        IReadOnlyList<(string TypeNodeId, string Member)>? members = null)
    {
        var built = new List<EntryPointRow>();
        foreach (var c in candidates)
        {
            built.Add(Classify(c.NodeId, nodeId: c.NodeId));
        }

        if (members is not null)
        {
            foreach (var (typeId, member) in members)
            {
                var display = $"{typeId}.{member}";
                var kind = KindFromDisplay(display);
                if (kind == EntryPointKind.Unclassified)
                {
                    kind = KindFromDisplay(member);
                }

                built.Add(new EntryPointRow(
                    kind,
                    NodeId: null,
                    display,
                    kind == EntryPointKind.Unclassified
                        ? EntryPointsProjection.UnclassifiedReasonPendingClassifier
                        : null));
            }
        }

        var cap = maxRows < 1 ? 1 : maxRows;
        var omitted = Math.Max(0, built.Count - cap);
        var rows = built.Take(cap).ToList();

        IReadOnlyList<string> disclosures = omitted > 0
            ? [$"Omitted ({omitted})"]
            : [];

        return new EntryPointsResult(rows, omitted, disclosures, sourceRevision);
    }

    /// <summary>
    /// Listing-kind heuristics on the type display name. Not Core method-observation identity
    /// (r5: has_member/call facts are not observation ids).
    /// </summary>
    internal static EntryPointRow Classify(string display, string? nodeId)
    {
        var kind = KindFromDisplay(display);
        return new EntryPointRow(
            kind,
            nodeId,
            display,
            kind == EntryPointKind.Unclassified
                ? EntryPointsProjection.UnclassifiedReasonPendingClassifier
                : null);
    }

    internal static EntryPointKind KindFromDisplay(string display)
    {
        if (display.EndsWith(".Program", StringComparison.Ordinal)
            || display.Equals("Program", StringComparison.Ordinal)
            || display.EndsWith(".Main", StringComparison.Ordinal)
            || display.Equals("Main", StringComparison.Ordinal)
            || display.Contains("CommandLine", StringComparison.Ordinal))
        {
            return EntryPointKind.Cli;
        }

        if (display.Contains("Controller", StringComparison.Ordinal)
            || display.Contains("Endpoint", StringComparison.Ordinal)
            || display.Contains(".Api.", StringComparison.Ordinal)
            || display.StartsWith("Api.", StringComparison.Ordinal)
            || display.EndsWith("Api", StringComparison.Ordinal))
        {
            return EntryPointKind.Api;
        }

        if (display.Contains("Window", StringComparison.Ordinal)
            || display.Contains("UserControl", StringComparison.Ordinal)
            || display.Contains("Page", StringComparison.Ordinal))
        {
            return EntryPointKind.Ux;
        }

        return EntryPointKind.Unclassified;
    }
}
