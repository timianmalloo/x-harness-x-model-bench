namespace AiDe.Core;

/// <summary>
/// How two filesystem paths compare on the machine this is running on.
/// </summary>
/// <remarks>
/// <para><b>One rule, named once, because spelling it inline is how it keeps going wrong.</b> The
/// same defect has now been fixed four times — INV-0005, <c>RepositoryIdentity.ToFileSystemPath</c>,
/// <c>RepositoryCorrection</c>/<see cref="Watcher.ProofPackVerifier"/>, and the three containment
/// checks in <c>Extraction/</c> and <c>Projections/</c> — and every instance was the same line
/// written from memory at a new call site. <c>WatcherIdentity</c> states the rule in prose
/// (<i>"THIS IS NOT A FILESYSTEM PATH"</i>) and prose is a memoir, so this is the member every
/// path comparison consults and <c>tools/verify-containment-comparisons.py</c> is the gate that
/// refuses a fifth hand-written copy.</para>
///
/// <para><b>Case-insensitive ONLY on Windows.</b> POSIX paths are case-sensitive:
/// <c>/repo/Secrets</c> and <c>/repo/secrets</c> are two different directories, and folding the
/// case there admits a path the rest of the system would never write. On Windows they are one
/// directory, so folding is what the filesystem itself does and refusing it would be a claim about
/// the caller's typing rather than about the file.</para>
///
/// <para><b>Not a <c>FileSystemPath</c> type.</b> That distinction was considered and rejected:
/// the defects it was proposed for all operate on strings that genuinely ARE filesystem paths, so
/// a wrapper type would not have caught any of them, and it would leave a permanent <c>.Value</c>
/// escape hatch for the next one to live in. The bug is the comparison rule, so the fix is a
/// comparison rule.</para>
/// </remarks>
public static class PathComparison
{
    /// <summary>
    /// The <see cref="StringComparison"/> that matches this machine's filesystem: ordinal
    /// everywhere, and case-insensitive additionally on Windows.
    /// </summary>
    /// <remarks>
    /// A property rather than a <c>static readonly</c> field so it is evaluated per call rather
    /// than at type-initialisation. Nothing in this process changes operating system mid-run, but a
    /// cached platform answer is the shape that survives into a context where it is wrong, and the
    /// ternary costs nothing next to the string comparison it qualifies.
    /// </remarks>
    public static StringComparison ForThisFileSystem => OperatingSystem.IsWindows()
        ? StringComparison.OrdinalIgnoreCase
        : StringComparison.Ordinal;
}
