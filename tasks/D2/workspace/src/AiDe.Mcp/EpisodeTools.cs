using AiDe.Core.Watcher;

namespace AiDe.Mcp;

/// <summary>
/// Declaring a Work Episode — the unit scoring attaches to.
/// </summary>
/// <remarks>
/// <para><b>Why an agent declares this and the product cannot.</b> The workbench knows a terminal
/// exists; it does not know what the agent inside it is trying to do. Opening an episode with a
/// placeholder goal would fabricate one, and the scorer already treats a missing goal honestly — Not
/// Scored, with the reason — so the declaration comes from the only party that has it.</para>
///
/// <para><b>The one thing an agent may say about its own quality is a POINTER.</b>
/// <c>episode.artifacts</c> names files; the product goes and looks. There is no
/// <c>acceptance_met</c> and there never will be: a verdict an agent asserts about itself is what
/// the scoring design exists to refuse, while a path is something anyone can check. An agent cannot
/// make a file exist by asserting it harder.</para>
///
/// <para>Measured 2026-09-03: of 292 skill entries in this repository's own audit log, 33 carried a
/// goal. The other 259 could never become episodes at all — which is why these tools state what will
/// happen rather than accepting silence.</para>
/// </remarks>
public static class EpisodeTools
{
    /// <summary>The four outcomes the contract admits. Nothing is defaulted.</summary>
    public static IReadOnlyList<string> Outcomes { get; } =
        [.. Enum.GetNames<EpisodeOutcome>().Select(n => n.ToLowerInvariant())];

    /// <summary>
    /// Opens an episode by appending an <c>episode-open</c> line.
    /// </summary>
    /// <remarks>
    /// A second open while one is live <b>supersedes</b> it: the first closes <c>Superseded</c> and a
    /// new generation opens. That is deliberate rather than a fallback — changing the goal starts a
    /// new episode — and it is said here so an agent reframing its work knows it did not lose the
    /// first one.
    /// </remarks>
    public static string Open(
        CoordContractWriter writer, string externalSessionId, string? goal, string? doneWhen, string? notInScope)
    {
        ArgumentNullException.ThrowIfNull(writer);
        ArgumentException.ThrowIfNullOrEmpty(externalSessionId);

        if (string.IsNullOrWhiteSpace(goal) || string.IsNullOrWhiteSpace(doneWhen))
        {
            // Neither is defaulted, and the reason is worth giving: an invented goal would be scored
            // against something the agent never declared.
            return "An episode needs both a goal and a done condition. Neither is defaulted — an "
                 + "invented goal would be scored against something you never declared.";
        }

        var attributes = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [CoordContract.EpisodeAttributes.Goal] = goal,
            [CoordContract.EpisodeAttributes.DoneWhen] = doneWhen,
        };

        if (!string.IsNullOrWhiteSpace(notInScope))
        {
            attributes[CoordContract.EpisodeAttributes.NotInScope] = notInScope;
        }

        writer.Write("episode-open", externalSessionId, attributes);

        return "Episode declared. If one was already open it closes as Superseded and this starts a "
             + "new generation — changing the goal starts a new episode, deliberately.";
    }

    /// <summary>
    /// Closes an episode, optionally naming the evidence.
    /// </summary>
    /// <remarks>
    /// <b>Ending your session leaves an open episode open.</b> The watcher will not invent an
    /// outcome, so an episode nobody closes is never scored — said at call time because an agent that
    /// does not know this simply stops, and the silence looks like the product losing its work.
    /// </remarks>
    public static string Close(
        CoordContractWriter writer, string externalSessionId, string? outcome, IReadOnlyList<string>? artifacts)
    {
        ArgumentNullException.ThrowIfNull(writer);
        ArgumentException.ThrowIfNullOrEmpty(externalSessionId);

        if (string.IsNullOrWhiteSpace(outcome)
            || !Enum.TryParse<EpisodeOutcome>(outcome, ignoreCase: true, out _))
        {
            return $"'{outcome}' is not an outcome. Use one of: {string.Join(", ", Outcomes)}. "
                 + "It is never defaulted to Completed.";
        }

        var attributes = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [CoordContract.EpisodeAttributes.Outcome] = outcome,
        };

        var declared = artifacts?.Where(a => !string.IsNullOrWhiteSpace(a)).ToList() ?? [];
        if (declared.Count > 0)
        {
            if (declared.Count > DeclaredArtifactBounds.MaxPaths)
            {
                return $"At most {DeclaredArtifactBounds.MaxPaths} paths. The whole close is refused "
                     + "rather than truncated: a shortened evidence list reads as a complete one.";
            }

            if (declared.Any(a => a.Length > DeclaredArtifactBounds.MaxPathLength))
            {
                return $"A path exceeds {DeclaredArtifactBounds.MaxPathLength} characters. The whole "
                     + "close is refused rather than truncated.";
            }

            attributes[CoordContract.EpisodeAttributes.Artifacts] = string.Join("\n", declared);
        }

        writer.Write("episode-close", externalSessionId, attributes);

        return declared.Count == 0
            ? "Episode closed with no evidence, so it will score Not Scored — no verification path. "
              + "That is honest and worth nothing to you; if you verified something, name the file."
            : $"Episode closed, naming {declared.Count} path(s). The product checks whether each is "
              + "there — you named files, it goes and looks.";
    }
}
