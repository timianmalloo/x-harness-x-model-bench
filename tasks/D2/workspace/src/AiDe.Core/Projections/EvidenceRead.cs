using AiDe.Core.Facts;

namespace AiDe.Core.Projections;

/// <summary>
/// A read of the evidence, and how much of it the read actually saw.
/// </summary>
/// <remarks>
/// <para><b>Every number the panes show is computed from a bounded read.</b> The shell searches with
/// a result cap, describes a bounded number of those matches, and takes a bounded number of
/// neighbours from each. On a repository the size of the ones measured so far all three caps are
/// slack, and nothing about the output would change if they were not — the crossing counts, the join
/// counts and the coverage percentage would simply be smaller, and still be presented as facts.</para>
///
/// <para><b>This is the same defect this project keeps finding, one layer up.</b> A cap that
/// silently truncates turns a correct count into a confident wrong one: the member cap on a crossing
/// keeps its true weight beside the listed members for exactly this reason, and the coverage
/// denominator was fixed twice for counting the wrong population. A bound the user cannot see is a
/// bound they cannot allow for.</para>
///
/// <para><b>It degrades to "not known", never to a plausible wrong number.</b> When the read is
/// complete <see cref="Shortfall"/> is null and nothing is said; when it is not, it names which cap
/// bit and by how much.</para>
/// </remarks>
public sealed record EvidenceRead(
    IReadOnlyList<EvidenceAssertion> Assertions,
    int NodesMatched,
    int NodesRead,
    int NeighbourLimit,
    int NodesAtNeighbourLimit)
{
    public static EvidenceRead Empty { get; } = new([], 0, 0, 0, 0);

    /// <summary>True when every matched node was read and none hit the neighbour limit.</summary>
    public bool IsComplete => NodesRead >= NodesMatched && NodesAtNeighbourLimit == 0;

    /// <summary>
    /// What the read did not see, in words, or null when it saw everything.
    /// </summary>
    /// <remarks>
    /// Both causes are reported, not just the first. They are different problems with different
    /// fixes — one is "this workspace is bigger than the search cap", the other is "these particular
    /// nodes are unusually connected" — and collapsing them into one sentence would leave the reader
    /// guessing which they have.
    /// </remarks>
    public string? Shortfall
    {
        get
        {
            var parts = new List<string>();

            if (NodesRead < NodesMatched)
            {
                parts.Add($"{NodesMatched - NodesRead:N0} of {NodesMatched:N0} matching node(s) were " +
                          "not read");
            }

            if (NodesAtNeighbourLimit > 0)
            {
                parts.Add($"{NodesAtNeighbourLimit:N0} node(s) had more than {NeighbourLimit} " +
                          "neighbour(s) and were truncated");
            }

            return parts.Count == 0
                ? null
                : string.Join(", and ", parts) +
                  ". Counts below are computed from what was read, and are lower bounds.";
        }
    }
}
