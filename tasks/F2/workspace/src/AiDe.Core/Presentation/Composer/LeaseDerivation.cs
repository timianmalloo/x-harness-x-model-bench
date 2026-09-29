using System.Text.RegularExpressions;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Presentation.Composer;

/// <summary>
/// Derives the lane's exclusive write scope from what the operator referenced — never from a lease
/// editor (Ruling 42, Security C17).
/// </summary>
/// <remarks>
/// <para><b>Why this exists at all.</b> R19 said the lease is "derived and displayed". At sheet time
/// there is nothing to derive <i>from</i>, so Ruling 42 deleted the lease from the sheet and made it
/// a <b>sibling of the goal block</b>, which is this node. The derivation input is the compiled
/// prompt the operator just read: the paths they referenced with a mention are the paths they mean
/// the lane to work in.</para>
///
/// <para><b>No operator-typed lease editor, and that is refusal (d).</b> A mention is written as a
/// reference; the glob is computed. What the operator types is never a pattern.</para>
///
/// <para><b>A universal lease is refused in the product, not only in a test.</b>
/// <c>LeaseAndSeams</c> already records why: a lease that covers everything never seams, and "looks
/// like it is working". <see cref="Derive"/> re-runs C17's own oracle against the lease it just
/// built and refuses rather than returning one that cannot discriminate.</para>
///
/// <para><b>Nothing derivable means no lease, and no lease means no write capability</b>
/// (Ruling 73, narrowing the earlier <i>no lease means no run</i>). A turn whose source text
/// derives nothing runs <b>read-only</b> — its lane opened with every write-capable tool
/// disallowed, no lease derived and none required — and the send gate decides that shape from
/// <see cref="Patterns"/> before ever calling <see cref="Derive"/>. For a write-shaped turn the
/// empty case is still returned as an empty pattern list so the caller constructs
/// <see cref="Lease"/> with it and the constructor's own refusal fires. <b>That exception failing
/// closed is the control</b>, and catching it into a default is how the control is switched off
/// while looking present.</para>
/// </remarks>
public static class LeaseDerivation
{
    /// <summary>
    /// The probe C17 fixed: no spelling of "everything" can leave this uncovered, unlike a
    /// comparison against the literal pattern.
    /// </summary>
    public const string UncoveredProbePath = "/no-lease-covers-this";

    /// <summary>
    /// A mention runs to the next whitespace, deliberately — <b>including characters a path may not
    /// contain</b>.
    /// </summary>
    /// <remarks>
    /// <b>A narrower capture is a widening bug, and it was one.</b> An earlier pattern stopped at the
    /// first character outside a path alphabet, so <c>@src/*.cs</c> captured <c>src/</c> and became
    /// the directory scope <c>src/**</c> — a broader lease than the operator wrote, produced by the
    /// validation refusing to look at the thing that made it invalid. Capturing everything and
    /// rejecting afterwards is the only order in which the rejection can see its own input.
    /// </remarks>
    private static readonly Regex Mention = new(
        @"@(\S+)", RegexOptions.Compiled | RegexOptions.CultureInvariant);

    /// <summary>
    /// Whether the text carries a mention token anywhere — <b>the one shared member</b> the compile
    /// step's typed boundary scans model output and <c>notes</c> with (Addendum D §A8.3 C-Lease;
    /// ADR-0033 rule 1). The same <see cref="Regex"/> instance <see cref="Patterns"/> matches, so the
    /// scan and the derivation cannot drift: a copied pattern would be two definitions of the
    /// mention grammar, and drift between them is the bypass class. <c>internal</c>, so
    /// <see cref="LeaseDerivation"/>'s public signatures stay byte-identical (US-D12).
    /// </summary>
    internal static bool HasMention(string text)
    {
        ArgumentNullException.ThrowIfNull(text);
        return Mention.IsMatch(text);
    }

    /// <summary>The one regex, for the test that asserts the validator and <see cref="Patterns"/> share it.</summary>
    internal static Regex MentionRegex => Mention;

    /// <summary>Sentence punctuation a mention picks up by sitting at the end of a clause.</summary>
    private static readonly char[] TrailingPunctuation = [',', ';', ':', '!', '?', ')', ']', '}', '"', '\'', '.'];

    /// <summary>
    /// Every lease pattern the compiled text implies, de-duplicated, in first-appearance order.
    /// </summary>
    /// <remarks>
    /// Order is first appearance rather than sorted so the displayed lease reads in the order the
    /// operator wrote it — the same reason the compiler walks declared fields rather than a
    /// dictionary.
    /// </remarks>
    public static IReadOnlyList<string> Patterns(string compiledText)
    {
        ArgumentNullException.ThrowIfNull(compiledText);

        var seen = new List<string>();

        foreach (Match match in Mention.Matches(compiledText))
        {
            var pattern = ToPattern(match.Groups[1].Value);
            if (pattern is not null && !seen.Contains(pattern, StringComparer.Ordinal))
            {
                seen.Add(pattern);
            }
        }

        return seen;
    }

    /// <summary>
    /// The lease for this compiled text.
    /// </summary>
    /// <exception cref="ArgumentException">
    /// Nothing was derivable, so there is no scope to write within. Raised by <see cref="Lease"/>
    /// itself — deliberately not caught here, and deliberately not softened into a default.
    /// </exception>
    /// <exception cref="InvalidOperationException">
    /// The derivation produced a lease that covers everything. Unreachable by the rules below, and
    /// checked anyway: a seam control that cannot discriminate is worse than none.
    /// </exception>
    public static Lease Derive(string compiledText)
    {
        var lease = new Lease(Patterns(compiledText));

        if (lease.Covers(UncoveredProbePath))
        {
            throw new InvalidOperationException(
                "the derived lease covers everything, so no edit could ever raise a seam; a lease "
                + "that cannot discriminate looks like it is working and is refused here");
        }

        return lease;
    }

    /// <summary>
    /// One mention as a repository-relative glob, or <c>null</c> when it is not a path at all.
    /// </summary>
    /// <remarks>
    /// A trailing slash or a segment with no dot in it reads as a directory and takes <c>/**</c>; a
    /// name with an extension is taken literally. A mention that normalises to nothing, or to a bare
    /// wildcard, is dropped rather than widened — widening is how a scope becomes universal one
    /// convenience at a time.
    /// </remarks>
    private static string? ToPattern(string mention)
    {
        var path = mention.Replace('\\', '/').Trim().TrimEnd(TrailingPunctuation);

        while (path.StartsWith("./", StringComparison.Ordinal))
        {
            path = path[2..];
        }

        path = path.TrimStart('/');

        if (path.Length == 0
            || !char.IsLetterOrDigit(path[0])
            || path.Contains("..", StringComparison.Ordinal)
            || path.Contains('*')
            || path.Contains('?'))
        {
            return null;
        }

        if (path.EndsWith('/'))
        {
            return path + "**";
        }

        var leaf = path[(path.LastIndexOf('/') + 1)..];
        return leaf.Contains('.', StringComparison.Ordinal) ? path : path + "/**";
    }
}
