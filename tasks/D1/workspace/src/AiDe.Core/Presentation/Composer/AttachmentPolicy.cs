using System.Text;

namespace AiDe.Core.Presentation.Composer;

/// <summary>
/// The rules an attachment is held to: the caps, the categorical refusal set, the resolved-path
/// containment test, and strict decoding.
/// </summary>
/// <remarks>
/// <para><b>The caps bound what a human can read, not what a file can hold (Ruling 43).</b> The only
/// Phase-1 control is a human reading the compiled text. 32 KiB is roughly 800 lines; this
/// repository's larger source files are ~300 lines, so real files fit, while 64 KiB is ~1,600 lines
/// — scrolled past rather than read. <b>Confidence: Inferred</b>, and the gap is named rather than
/// hidden: no measurement exists of how much compiled text an operator reads before skimming, which
/// is why the metrics kind records per-send attachment count and bytes on the normal path, so these
/// numbers are revisited on data at Phase 2 instead of re-argued.</para>
///
/// <para><b>These caps bound the ATTACH path only, never what a RUN sends.</b> The agent's own file
/// reads are unbounded by them. Describing 32 KiB / 128 KiB / 5 files anywhere as a ceiling on a
/// run's egress would be a wrong ceiling, which is worse than a named absence.</para>
///
/// <para><b>The refusal set is a FLOOR, not a guarantee.</b> Recording it as "secrets cannot be
/// attached" would be exactly the security-shaped lie this programme keeps catching. Content
/// scanning is Security's and is deferred.</para>
/// </remarks>
public static class AttachmentPolicy
{
    /// <summary>Per file (Ruling 43). Compared in <see cref="AttachmentGate"/>, never reported alone.</summary>
    public const int MaxAttachmentBytes = 32 * 1024;

    /// <summary>Per send, across every attachment (Ruling 43).</summary>
    public const int MaxSendAttachmentBytes = 128 * 1024;

    /// <summary>How many files one send may carry (Ruling 43).</summary>
    public const int MaxAttachmentsPerSend = 5;

    /// <summary>Path segments that are never attachable, whatever the human picked.</summary>
    private static readonly string[] RefusedSegments =
    [
        ".git", ".ssh", ".aws", ".azure", ".gnupg", ".kube",
    ];

    /// <summary>Segment pairs that are never attachable — a parent plus the child it must contain.</summary>
    private static readonly (string Parent, string Child)[] RefusedSegmentPairs =
    [
        (".config", "gh"),
        (".vscode", "mcp.json"),
        (".cursor", "mcp.json"),
        (".devcontainer", "devcontainer.json"),
    ];

    /// <summary>
    /// Browser profile roots. A floor rather than an enumeration: a profile directory holds session
    /// cookies and saved credentials, and the families below are the ones on this platform.
    /// </summary>
    private static readonly string[] BrowserProfileSegments = ["User Data", "Mozilla", "Firefox"];

    /// <summary>Exact file names that are never attachable.</summary>
    private static readonly string[] RefusedNames =
    [
        ".npmrc", ".netrc", ".git-credentials", "credentials",
        ".mcp.json", ".mcp.json.tmp", "local.settings.json",
    ];

    /// <summary>Extensions that are never attachable.</summary>
    private static readonly string[] RefusedExtensions = [".pem", ".key", ".p12", ".pfx", ".kdbx", ".tfvars"];

    /// <summary>Name prefixes that are never attachable.</summary>
    private static readonly string[] RefusedPrefixes = [".env", "id_rsa", "id_ed25519"];

    /// <summary>Archive extensions. Refused as a gesture (C14(e)(i)), before decoding decides.</summary>
    private static readonly string[] ArchiveExtensions = [".zip", ".tar", ".gz", ".7z", ".rar", ".tgz"];

    /// <summary>
    /// Why this resolved path may never be attached, or <c>null</c> when nothing refuses it.
    /// </summary>
    /// <remarks>
    /// Applied to the <b>resolved</b> path, not the pick: a link is how a refused file arrives
    /// wearing an allowed name. The second class in this set — an in-repo config file carrying a
    /// third party's credentials in an env or settings block — was invisible to the list's original
    /// organising idea (well-known secret filenames), which is why the set grew by a class rather
    /// than by a name.
    /// </remarks>
    public static string? RefusalFor(string resolvedPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(resolvedPath);

        var normalised = resolvedPath.Replace('\\', '/');
        var segments = normalised.Split('/', StringSplitOptions.RemoveEmptyEntries);
        var name = segments.Length == 0 ? normalised : segments[^1];

        foreach (var segment in segments)
        {
            if (RefusedSegments.Contains(segment, StringComparer.OrdinalIgnoreCase))
            {
                return $"the categorical refusal set: nothing under a '{segment}' directory is attachable";
            }

            if (BrowserProfileSegments.Contains(segment, StringComparer.OrdinalIgnoreCase))
            {
                return "the categorical refusal set: nothing under a browser profile directory is attachable";
            }
        }

        for (var i = 0; i + 1 < segments.Length; i++)
        {
            foreach (var (parent, child) in RefusedSegmentPairs)
            {
                if (string.Equals(segments[i], parent, StringComparison.OrdinalIgnoreCase)
                    && string.Equals(segments[i + 1], child, StringComparison.OrdinalIgnoreCase))
                {
                    return $"the categorical refusal set: '{parent}/{child}' carries third-party credentials";
                }
            }
        }

        if (RefusedNames.Contains(name, StringComparer.OrdinalIgnoreCase))
        {
            return $"the categorical refusal set: a file named '{name}' is never attachable";
        }

        foreach (var prefix in RefusedPrefixes)
        {
            if (name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            {
                return $"the categorical refusal set: a file whose name begins '{prefix}' is never attachable";
            }
        }

        var extension = Path.GetExtension(name);
        if (RefusedExtensions.Contains(extension, StringComparer.OrdinalIgnoreCase))
        {
            return $"the categorical refusal set: a '{extension}' file is never attachable";
        }

        // `appsettings.<environment>.json`, and deliberately NOT the plain `appsettings.json`: the
        // class Privacy named is the ENVIRONMENT-SPECIFIC file, which is where the connection strings
        // live. A deny-list that also denies the neighbours is a different defect.
        if (name.StartsWith("appsettings.", StringComparison.OrdinalIgnoreCase)
            && name.EndsWith(".json", StringComparison.OrdinalIgnoreCase)
            && name.Length > "appsettings..json".Length)
        {
            return "the categorical refusal set: an environment-specific appsettings file carries credentials";
        }

        if (name.StartsWith("docker-compose", StringComparison.OrdinalIgnoreCase)
            && (name.EndsWith(".yml", StringComparison.OrdinalIgnoreCase)
                || name.EndsWith(".yaml", StringComparison.OrdinalIgnoreCase)))
        {
            return "the categorical refusal set: a compose file carries third-party credentials in its env block";
        }

        return null;
    }

    /// <summary>Whether this name reads as an archive, which one human act may never expand.</summary>
    public static bool IsArchive(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        return ArchiveExtensions.Contains(Path.GetExtension(path), StringComparer.OrdinalIgnoreCase);
    }

    /// <summary>
    /// The fully resolved real path: symlinks, junctions and reparse points followed, on the file
    /// <b>and on every directory in its prefix</b> (C14(e)(ii)).
    /// </summary>
    /// <remarks>
    /// <b>Resolving only the leaf is the hole this method exists to close.</b> A junction in the
    /// prefix moves a file outside the workspace without the leaf being a link at all, so the
    /// inside/outside label would read "inside" while the bytes came from anywhere — a bypass with
    /// nobody lying.
    /// </remarks>
    public static string RealPath(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        return Resolve(Path.GetFullPath(path), depth: 0);
    }

    private static string Resolve(string path, int depth)
    {
        // A link chain is followed by ResolveLinkTarget itself; this guard is for a prefix that
        // resolves into a cycle, where the honest answer is the path we last had rather than a hang.
        const int MaximumDepth = 64;
        if (depth > MaximumDepth)
        {
            return path;
        }

        var parent = Path.GetDirectoryName(path);
        if (string.IsNullOrEmpty(parent))
        {
            return path;
        }

        var candidate = Path.Combine(Resolve(parent, depth + 1), Path.GetFileName(path));

        FileSystemInfo? info =
            Directory.Exists(candidate) ? new DirectoryInfo(candidate)
            : File.Exists(candidate) ? new FileInfo(candidate)
            : null;

        try
        {
            var target = info?.ResolveLinkTarget(returnFinalTarget: true);
            return target is null ? candidate : Path.GetFullPath(target.FullName);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            // Unresolvable is not "inside". The unresolved path is returned and the containment test
            // below decides on it, which is the conservative direction.
            return candidate;
        }
    }

    /// <summary>Whether a resolved path is inside a resolved workspace root.</summary>
    /// <remarks>
    /// Separator-terminated so a sibling root is not admitted, and the case rule is the file
    /// system's own rather than a hardcoded one — see <see cref="AiDe.Core.PathComparison"/>.
    /// </remarks>
    public static bool IsInsideWorkspace(string resolvedPath, string resolvedWorkspaceRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(resolvedPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(resolvedWorkspaceRoot);

        var root = resolvedWorkspaceRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;

        return resolvedPath.StartsWith(root, PathComparison.ForThisFileSystem);
    }

    /// <summary>
    /// Decodes strictly as UTF-8, or refuses and names what it found instead.
    /// </summary>
    /// <remarks>
    /// <para><b>Strict, because a lossy decode is worse than a refusal.</b> Substituting U+FFFD
    /// silently mangles the artifact while still carrying recognisable fragments of it, so the human
    /// reads something that looks like the file and is not.</para>
    ///
    /// <para><b>The refusal names the detected encoding</b>, because UTF-16LE-with-BOM is common on
    /// Windows and a bare "file refused" routes the operator into the uncapped paste path.</para>
    ///
    /// <para><b>UTF-8-text-only is a SAFETY filter, not a minimization one</b>, and that is recorded
    /// here so nobody "fixes" it later: it excludes images, archives, SQLite stores and key
    /// containers. The class it passes is where the highest risk-per-byte lives — an env file, a
    /// private key and a credentials file are all UTF-8 text — and
    /// <see cref="RefusalFor"/> is the compensating control.</para>
    /// </remarks>
    public static bool TryDecodeUtf8(ReadOnlySpan<byte> bytes, out string text, out string detectedEncoding)
    {
        text = string.Empty;
        detectedEncoding = "UTF-8";

        if (bytes.Length >= 2 && bytes[0] == 0xFF && bytes[1] == 0xFE)
        {
            detectedEncoding = "UTF-16LE with a byte-order mark";
            return false;
        }

        if (bytes.Length >= 2 && bytes[0] == 0xFE && bytes[1] == 0xFF)
        {
            detectedEncoding = "UTF-16BE with a byte-order mark";
            return false;
        }

        var body = bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF
            ? bytes[3..]
            : bytes;

        try
        {
            text = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true)
                .GetString(body);
            return true;
        }
        catch (DecoderFallbackException)
        {
            detectedEncoding = "bytes that are not valid UTF-8";
            return false;
        }
    }
}
