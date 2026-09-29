namespace AiDe.Core.Watcher;

/// <summary>
/// One evidence path an agent named when it closed an episode — as declared, not as verified.
/// </summary>
/// <remarks>
/// <para><b>Why this exists.</b> <c>ClosedEpisodeScoring</c> passed <c>HasProofPack: false</c> as a
/// literal, which collapsed two states that want opposite responses: <i>we looked for evidence and
/// there was none</i> (a fact about this episode) and <i>there is nowhere to look</i> (a fact about
/// the product). It was always the second, spelled as the first — so a scorecard made a statement
/// about an agent when the true statement was about a missing channel. This is the channel.</para>
///
/// <para><b>The agent names a file; the product checks whether the file is there.</b> That is what
/// keeps this observation rather than testimony, and it is why an <c>episode.acceptance_met</c>
/// attribute stays refused while this one is admitted: an agent cannot make a path exist by
/// asserting it harder. ADR-0019 advisory-evaluator-calibration's anti-Goodhart concern is about accepting a claim; this accepts a
/// pointer and then goes and looks.</para>
///
/// <para><b>Nothing here is verified.</b> The path is stored exactly as sent, including one that is
/// absolute, escapes the repository, or does not exist. Verification is a separate step with a
/// separate answer, and merging the two would destroy the only evidence that distinguishes an agent
/// that lied from a file that moved.</para>
/// </remarks>
/// <param name="EpisodeId">The episode the claim is about.</param>
/// <param name="Path">The path as the agent sent it — untrusted text.</param>
/// <param name="DeclaredAt">When the declaration was ingested.</param>
/// <param name="Sequence">Ingest order, so replay is deterministic across a union merge.</param>
public sealed record DeclaredEpisodeArtifact(
    string EpisodeId,
    string Path,
    DateTimeOffset DeclaredAt,
    long Sequence);

/// <summary>The bounds an <c>episode.artifacts</c> attribute must respect to be ingested.</summary>
/// <remarks>
/// <para>The contract log is written by agents, so an unbounded list is an unbounded write into the
/// product's store from outside it. Both bounds are <b>declared</b> rather than implicit, and a line
/// that exceeds either is quarantined rather than truncated — a silently shortened evidence list is
/// a partial record rendered as a whole one, which is the shape this whole vertical keeps being
/// corrected for.</para>
///
/// <para>The numbers are safety floors with no statistical basis: <b>not recorded</b>. A Proof Pack
/// per episode is the expected shape and 32 is far above it, so the cap is a resource bound rather
/// than a modelling claim. It may tighten; it must never silently relax.</para>
/// </remarks>
public static class DeclaredArtifactBounds
{
    /// <summary>Most paths one episode-close may declare.</summary>
    public const int MaxPaths = 32;

    /// <summary>Longest single path, in characters.</summary>
    public const int MaxPathLength = 512;

    /// <summary>
    /// Splits the wire value into paths, or reports that it cannot be ingested.
    /// </summary>
    /// <remarks>
    /// <para>Newline-separated, because a coordination attribute is a JSON string and a path may
    /// contain spaces, commas and semicolons on a real filesystem but never a newline. A separator
    /// that can appear inside a value is a parser that silently splits one path into two.</para>
    ///
    /// <para><b>An absent attribute is not a malformed one.</b> Most agents will never send this,
    /// and that must cost them nothing — so absence returns an empty list and succeeds, while
    /// present-and-unusable fails. Those are different facts and the caller renders them
    /// differently.</para>
    /// </remarks>
    /// <returns><c>true</c> when the value is usable; <c>paths</c> holds what it declared.</returns>
    public static bool TryParse(string? value, out IReadOnlyList<string> paths)
    {
        if (value is null)
        {
            paths = [];
            return true;
        }

        // Present but empty is NOT the same as absent. An agent that sent the key meant to say
        // something, and accepting a blank as "no evidence" would let a lost value read as a
        // deliberate silence.
        if (string.IsNullOrWhiteSpace(value))
        {
            paths = [];
            return false;
        }

        var declared = value
            .Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .ToList();

        if (declared.Count == 0
            || declared.Count > MaxPaths
            || declared.Any(p => p.Length > MaxPathLength))
        {
            paths = [];
            return false;
        }

        paths = declared;
        return true;
    }
}
