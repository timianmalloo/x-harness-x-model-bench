namespace AiDe.Core.Terminal;

/// <summary>
/// Whether the environment a terminal hands its children can actually be carried by them.
/// </summary>
/// <remarks>
/// <para><b>Reported as "the agent sessions do not have my profile or my environment variables".</b>
/// The measurement found something the product did not cause and could not see: this machine's PATH
/// is <b>22,297 characters</b>, and <c>cmd.exe</c> silently drops a variable that large. Any child
/// that runs through cmd — which is every <c>.cmd</c> shim, and therefore every npm-installed CLI —
/// starts with an <b>empty PATH</b> and cannot find node, git, or itself.</para>
///
/// <para><b>Proven necessary and sufficient, and proven not to be ours.</b> The same shim run from a
/// plain PowerShell with no part of this product involved also received an empty PATH; trimming PATH
/// to 1,799 characters made it arrive intact. AI-DE passes the environment correctly — PowerShell
/// started from the same inherited block reads all 22,297 characters and resolves <c>claude</c>.</para>
///
/// <para><b>What was ours is that it was invisible.</b> The terminal opened, looked healthy, and the
/// user's tools were simply absent — a clean surface over a broken environment, which is DC-025
/// wearing a different hat. This states it, with the number and the remedy, so the failure is
/// attributable instead of mysterious.</para>
///
/// <para>It never edits the user's PATH. A tool that silently rewrites the environment to make
/// itself work is a tool that has hidden the problem from the person who has to fix it, and PATH is
/// theirs — the entries causing this belong to another program's build.</para>
/// </remarks>
public static class EnvironmentHealth
{
    /// <summary>
    /// The size past which <c>cmd.exe</c> stops carrying a variable.
    /// </summary>
    /// <remarks>
    /// <b>Bisected, not quoted.</b> On the reporting machine <c>cmd.exe</c> carried a variable of
    /// 8,151 characters and dropped one of 8,152 — printing "The input line is too long" and then
    /// losing the value. The documented figure is 8,191; the ~40-character difference is the
    /// variable's own name and the block overhead, so the exact cut-off shifts slightly with the
    /// name. The message still says "may be dropped" because of that, not because the number is
    /// unmeasured.
    /// </remarks>
    public const int CmdVariableLimit = 8151;

    /// <summary>
    /// The measured cut-off, on <c>NAME=VALUE</c> as a whole — not on the value.
    /// </summary>
    /// <remarks>
    /// <para><b>Bisected 2026-09-01</b>, by handing a child a controlled environment and asking the
    /// CHILD what it received (the parent's copy is not evidence — DC-027's own rule). The boundary
    /// is exact and identical at four name lengths:</para>
    /// <code>
    /// name len   max value   name + 1 + value
    ///        3       8,186              8,190
    ///       13       8,176              8,190
    ///       40       8,149              8,190
    ///      120       8,069              8,190
    /// </code>
    /// <para><b>So the limit is on the PAIR</b>, and comparing the value alone is wrong for any name
    /// longer than 39 characters: an 8,150-char value under a 40-char name passes a value-only check
    /// and is dropped by cmd.exe. Latent here — the longest name on the measured machine is 34 — and
    /// it stops being latent the moment something adds longer names, which is exactly what §3 of the
    /// session-registration spec proposes.</para>
    /// <para><see cref="CmdVariableLimit"/> is kept for the PATH message, where it reads as the
    /// budget a user has to get under.</para>
    /// </remarks>
    public const int CmdPairLimit = 8190;

    /// <summary>
    /// Findings about the whole environment, in words a user can act on. Empty when healthy.
    /// </summary>
    /// <remarks>
    /// PATH is checked in detail because it is the one whose loss stops tools resolving, but ANY
    /// oversized variable is dropped the same way and by the same mechanism — so every variable is
    /// measured and the others are named together. Checking only the variable that happened to bite
    /// is how the second instance of a class gets found by a user rather than by the tool.
    /// </remarks>
    public static IReadOnlyList<string> Inspect(string? path = null)
    {
        var findings = new List<string>();
        findings.AddRange(InspectPath(path ?? Environment.GetEnvironmentVariable("PATH") ?? string.Empty));

        if (path is not null) return findings;          // an explicit PATH is a PATH-only question

        var oversized = Environment.GetEnvironmentVariables()
            .Cast<System.Collections.DictionaryEntry>()
            .Select(e => (Name: e.Key?.ToString() ?? string.Empty, Length: e.Value?.ToString()?.Length ?? 0))
            .Where(v => v.Name.Length + 1 + v.Length > CmdPairLimit
                && !string.Equals(v.Name, "PATH", StringComparison.OrdinalIgnoreCase))
            .OrderByDescending(v => v.Length)
            .ToList();

        if (oversized.Count > 0)
        {
            findings.Add(
                $"{oversized.Count:N0} other environment variable(s) are past the same limit and " +
                "will be dropped for the same reason: " +
                string.Join(", ", oversized.Take(5).Select(v => $"{v.Name} ({v.Length:N0} chars)")) +
                (oversized.Count > 5 ? ", …" : string.Empty) + ".");
        }

        return findings;
    }

    /// <summary>
    /// PATH entries that point at directories which do not exist.
    /// </summary>
    /// <remarks>
    /// <para><b>Caught at twenty, not at a hundred and eighty-seven.</b> The oversize check only
    /// fires once PATH is past cmd's limit — which is to say, after the damage. This one fires on
    /// the SHAPE: something appended 187 throwaway build directories to a persisted PATH and never
    /// removed them, and every one of them was already gone from disk. Regrowth looks identical and
    /// starts small.</para>
    ///
    /// <para>A handful of dead entries is normal — an uninstalled tool, a moved SDK — so this stays
    /// quiet below a threshold. It is looking for a pattern of accumulation, not for tidiness.</para>
    /// </remarks>
    public const int DeadEntryThreshold = 10;

    private static IReadOnlyList<string> InspectPath(string value)
    {
        var findings = new List<string>();
        var entries = value.Split(';', StringSplitOptions.RemoveEmptyEntries);

        var dead = entries.Where(DoesNotExist).ToList();
        if (dead.Count >= DeadEntryThreshold)
        {
            var family = dead
                .Select(Family)
                .GroupBy(f => f, StringComparer.OrdinalIgnoreCase)
                .OrderByDescending(g => g.Count())
                .First();

            findings.Add(
                $"{dead.Count:N0} of {entries.Length:N0} PATH entries point at directories that do " +
                "not exist. They cost only length, and length is what stops cmd.exe carrying PATH " +
                $"at all. The largest group is {family.Count():N0} under '{family.Key}'.");
        }

        if (value.Length <= CmdVariableLimit)
        {
            return findings;
        }


        // The biggest repeated shape in the list, so the message names what to remove rather than
        // leaving the user to read two hundred paths. A count alone is a number, not a lead.
        var culprit = entries
            .Select(Family)
            .GroupBy(f => f, StringComparer.OrdinalIgnoreCase)
            .Where(g => g.Count() > 1)
            .OrderByDescending(g => g.Count())
            .FirstOrDefault();

        var message =
            $"PATH is {value.Length:N0} characters across {entries.Length:N0} entries, past the " +
            $"{CmdVariableLimit:N0} that cmd.exe carries. Any tool launched through a .cmd or .bat " +
            "shim — most npm-installed CLIs — may be dropped and will start with no PATH at all. " +
            "This affects every terminal on this machine, not only this one.";

        if (culprit is not null)
        {
            message += $" The largest repeated group is {culprit.Count():N0} entries under " +
                       $"'{culprit.Key}'.";
        }

        findings.Add(message);
        return findings;
    }

    /// <summary>Whether a PATH entry names a directory that is not there.</summary>
    /// <remarks>
    /// An unreadable or malformed entry counts as PRESENT. Reporting a path as dead because it could
    /// not be checked would send the user deleting something that may be doing its job.
    /// </remarks>
    private static bool DoesNotExist(string entry)
    {
        try
        {
            return !Directory.Exists(entry);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or ArgumentException)
        {
            return false;
        }
    }

    /// <summary>
    /// The shape of a PATH entry with its variable part removed, so repeats can be counted.
    /// </summary>
    /// <remarks>
    /// A directory whose name carries a GUID or a temp id is unique by construction, so grouping on
    /// the literal path finds nothing. Grouping on the PARENT of the varying segment is what turns
    /// two hundred unique strings into "these all came from one program".
    /// </remarks>
    private static string Family(string entry)
    {
        var parts = entry.Split(['\\', '/'], StringSplitOptions.RemoveEmptyEntries);

        for (var index = 0; index < parts.Length; index++)
        {
            if (!LooksGenerated(parts[index])) continue;

            // Keep the segment up to and including the generated one's PARENT, then a marker, so
            // "…\Temp\thing-<guid>\tools" and "…\Temp\thing-<other>\tools" land in one group.
            var prefix = string.Join('\\', parts[..index]);
            return prefix.Length == 0 ? "(generated)" : prefix + "\\…";
        }

        return entry;
    }

    /// <summary>A segment that carries a generated id: a long hex run, or many digits.</summary>
    private static bool LooksGenerated(string segment)
    {
        var hex = segment.Count(Uri.IsHexDigit);
        return segment.Length >= 12 && hex >= 12;
    }
}
