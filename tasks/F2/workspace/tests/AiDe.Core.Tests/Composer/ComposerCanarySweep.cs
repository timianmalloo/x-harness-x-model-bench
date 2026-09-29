namespace AiDe.Core.Tests.Composer;

/// <summary>
/// Reads every byte of every channel a send could possibly write, looking for a canary.
/// </summary>
/// <remarks>
/// <para><b>A grep that greps nothing passes forever.</b> That is why this helper is shared by the
/// clause tests and by their falsifiers: the same sweep that must find nothing after a real send
/// must find the canary when one is deliberately written, and both assertions run against this one
/// implementation. A sweep with a typo in its root would otherwise be a permanently green control.
/// </para>
///
/// <para><b>It walks the file system, not a list of files it expects.</b> The failure being caught is
/// "something wrote the content somewhere nobody enumerated", so enumerating is the one thing it must
/// not do.</para>
/// </remarks>
internal static class ComposerCanarySweep
{
    /// <summary>Every file under <paramref name="root"/> whose text contains <paramref name="canary"/>.</summary>
    public static IReadOnlyList<string> Hits(string root, string canary)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(root);
        ArgumentException.ThrowIfNullOrWhiteSpace(canary);

        if (!Directory.Exists(root))
        {
            return [];
        }

        var hits = new List<string>();

        foreach (var file in Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories))
        {
            string text;
            try
            {
                text = File.ReadAllText(file);
            }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException)
            {
                // An unreadable file is reported as a hit rather than skipped: "I could not look" must
                // never read as "there was nothing there" (DC-016).
                hits.Add(file + " (unreadable — not proven clean)");
                continue;
            }

            if (text.Contains(canary, StringComparison.Ordinal))
            {
                hits.Add(file);
            }
        }

        return hits;
    }

    /// <summary>Every hit across several roots at once, with missing roots simply contributing none.</summary>
    public static IReadOnlyList<string> Hits(IReadOnlyList<string> roots, string canary) =>
        [.. roots.SelectMany(root => Hits(root, canary))];
}
