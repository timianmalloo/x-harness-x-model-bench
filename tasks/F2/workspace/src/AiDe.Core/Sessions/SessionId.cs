using System.Globalization;
using System.Security.Cryptography;
using System.Text.RegularExpressions;

namespace AiDe.Core.Sessions;

/// <summary>
/// The session id: a filesystem-safe, sortable, collision-resistant token that names a session's
/// directory under <c>.aide/sessions/&lt;session-id&gt;/</c> (Addendum A3).
/// </summary>
/// <remarks>
/// <para><b>Why not <c>AgentWorktree.ShortId</c>.</b> <see cref="Workbench.AgentWorktree.ShortId"/>
/// was read before writing this. It solves a different problem: deriving an eight-character
/// correlation TAG from an EXISTING, possibly hostile, external id (a harness session id feeding a
/// branch/folder name) by sanitizing and truncating. Truncation is the right trade there because the
/// tag is a display convenience alongside the real id.</para>
///
/// <para>Here there is no existing id to derive from — this method MINTS the primary identity of a
/// brand-new object, and it is the only thing distinguishing two sessions on disk. An
/// eight-character truncation of hostile/arbitrary input collides readily (that is <i>why</i>
/// <c>ShortId</c> is only ever used as a secondary tag, never as the sole key); a primary key cannot
/// accept that trade. So this generates its own value instead of sanitizing one: a UTC timestamp
/// (sortable — an operator scanning <c>.aide/sessions/</c> sees creation order for free) plus 32 bits
/// of CSPRNG entropy (collision-resistant independent of anything the caller supplies).</para>
///
/// <para><b>The safe character set is reused.</b> The format below (<c>yyyyMMddTHHmmssZ-hexhexhex</c>)
/// is built entirely from <c>AgentWorktree</c>'s lesson: no <c>.</c>, no path separator, and nothing
/// outside <c>[A-Za-z0-9-]</c> — the same "small safe set" argument, applied to a value this type
/// controls completely rather than to hostile input.</para>
/// </remarks>
public static class SessionId
{
    private const string TimestampFormat = "yyyyMMddTHHmmssZ";

    private static readonly Regex ValidShape = new(
        @"^\d{8}T\d{6}Z-[0-9a-f]{8}$", RegexOptions.Compiled);

    /// <summary>Mints a new session id. Deterministic in its timestamp half for testability.</summary>
    public static string New(DateTimeOffset? now = null)
    {
        var timestamp = (now ?? DateTimeOffset.UtcNow).UtcDateTime
            .ToString(TimestampFormat, CultureInfo.InvariantCulture);
        var entropy = RandomNumberGenerator.GetHexString(8, lowercase: true);
        return $"{timestamp}-{entropy}";
    }

    /// <summary>
    /// True when <paramref name="candidate"/> is this type's own shape — filesystem-safe by
    /// construction, since the character set never leaves <c>[0-9A-Za-z-]</c>.
    /// </summary>
    public static bool IsValid(string? candidate) =>
        candidate is not null && ValidShape.IsMatch(candidate);
}
