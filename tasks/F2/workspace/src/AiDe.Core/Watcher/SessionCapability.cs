using System.Security.Cryptography;

namespace AiDe.Core.Watcher;

/// <summary>
/// The unforgeable per-session secret. A process must present the matching capability on every event
/// (spec US-1). The raw token is never logged or emitted (O11), and comparison is constant-time to
/// deny a timing side-channel.
///
/// Pattern: Capability-based security. The capability is the authority; possessing the session id is
/// not (ADR-0007 / ADR-0020 trusted-registrar-harness-model-identity - terminal output is forgeable).
/// </summary>
public sealed class SessionCapability
{
    private readonly byte[] _token;

    internal SessionCapability(byte[] token)
    {
        // Copy so an external mutation of the source array cannot alter the stored secret.
        _token = (byte[])token.Clone();
    }

    /// <summary>
    /// Constant-time equality. Length is compared first only to size the fixed-time compare; the
    /// comparison itself does not short-circuit on content.
    /// </summary>
    public bool Matches(SessionCapability presented)
    {
        ArgumentNullException.ThrowIfNull(presented);
        return CryptographicOperations.FixedTimeEquals(_token, presented._token);
    }
}

/// <summary>Issues session capabilities. Abstracted so a test can inject a deterministic source.</summary>
public interface ICapabilityFactory
{
    SessionCapability Create();
}

/// <summary>The production factory: a 256-bit token from a cryptographic RNG.</summary>
public sealed class CapabilityFactory : ICapabilityFactory
{
    public SessionCapability Create()
    {
        var token = RandomNumberGenerator.GetBytes(32);
        return new SessionCapability(token);
    }
}
