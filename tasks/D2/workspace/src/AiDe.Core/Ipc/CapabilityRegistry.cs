using System.Security.Cryptography;

namespace AiDe.Core.Ipc;

/// <summary>A capability the daemon issued, and everything it is bound to.</summary>
public sealed record Capability(
    string Token,
    string ConnectionId,
    int ProcessId,
    string WorkspaceId,
    long Epoch,
    DateTimeOffset IssuedAt);

/// <summary>Why a capability check failed, or that it passed.</summary>
public sealed record CapabilityCheck(bool Ok, string? ErrorCode, string? Reason)
{
    public static readonly CapabilityCheck Valid = new(true, null, null);

    public static CapabilityCheck Fail(string code, string reason) => new(false, code, reason);
}

/// <summary>
/// Issues, validates and revokes the capabilities that authorize commands on the IPC boundary.
/// </summary>
/// <remarks>
/// <para><b>In memory only, and deliberately so.</b> A capability that outlived the daemon would
/// authorize a caller against a process that no longer exists, and persisting it would create a
/// file whose theft is equivalent to the authority itself. Restarting the daemon revokes
/// everything, which is the correct blast radius.</para>
///
/// <para><b>Bound to four things, checked in a fixed order</b> — connection, process, workspace,
/// epoch. Each closes a distinct attack: replaying a token on a second connection; a different
/// process on the same connection; reaching another workspace's daemon; and acting against state
/// that has since been replaced. Binding to fewer would make the token a bearer secret, which is
/// what capability-based authorization exists to avoid.</para>
///
/// <para>Comparison is <b>constant-time</b>. Token lookup by dictionary is not, so the token is
/// found by key and then verified by <see cref="CryptographicOperations.FixedTimeEquals"/> — the
/// dictionary hit only says a record exists, never that the caller's bytes matched it.</para>
/// </remarks>
public sealed class CapabilityRegistry(TimeProvider? timeProvider = null)
{
    private readonly Dictionary<string, Capability> _issued = new(StringComparer.Ordinal);
    private readonly System.Threading.Lock _gate = new();
    private readonly TimeProvider _time = timeProvider ?? TimeProvider.System;

    /// <summary>How many capabilities are live — for the health surface, not for authorization.</summary>
    public int Count
    {
        get
        {
            lock (_gate)
            {
                return _issued.Count;
            }
        }
    }

    /// <summary>Issues a capability bound to this peer, workspace and epoch.</summary>
    public Capability Issue(IpcPeer peer, string workspaceId, long epoch)
    {
        ArgumentNullException.ThrowIfNull(peer);
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceId);

        // 256 bits from a CSPRNG. Base64url so it survives an envelope without escaping, which is
        // one fewer place for an encoding bug to become a comparison bug.
        var token = Base64Url(RandomNumberGenerator.GetBytes(32));

        var capability = new Capability(
            token, peer.ConnectionId, peer.ProcessId, workspaceId, epoch, _time.GetUtcNow());

        lock (_gate)
        {
            _issued[token] = capability;
        }

        return capability;
    }

    /// <summary>
    /// Validates a presented token against the live connection and the command it accompanies.
    /// </summary>
    /// <remarks>
    /// Returns a typed reason rather than a bool. Which check failed is the difference between "your
    /// session ended" and "that token belongs to another workspace", and an operator who only sees
    /// "denied" cannot tell an expired shell from an attack.
    /// </remarks>
    public CapabilityCheck Validate(
        string? presented, IpcPeer peer, string workspaceId, long currentEpoch)
    {
        ArgumentNullException.ThrowIfNull(peer);

        if (string.IsNullOrEmpty(presented))
        {
            return CapabilityCheck.Fail(
                IpcErrorCodes.NotAuthorized, "the command carried no capability");
        }

        Capability? found;
        lock (_gate)
        {
            _issued.TryGetValue(presented, out found);
        }

        if (found is null)
        {
            // Unknown and revoked are the same observable outcome for an attacker and different for
            // an operator; the daemon knows which because a revoked token is removed, and says so
            // only in its own logs.
            return CapabilityCheck.Fail(
                IpcErrorCodes.CapabilityUnknown, "no such capability is live on this daemon");
        }

        if (!FixedTimeEquals(found.Token, presented))
        {
            return CapabilityCheck.Fail(
                IpcErrorCodes.CapabilityUnknown, "no such capability is live on this daemon");
        }

        if (!string.Equals(found.ConnectionId, peer.ConnectionId, StringComparison.Ordinal))
        {
            return CapabilityCheck.Fail(
                IpcErrorCodes.CapabilityWrongConnection,
                "the capability was issued to a different connection");
        }

        if (found.ProcessId != peer.ProcessId)
        {
            return CapabilityCheck.Fail(
                IpcErrorCodes.CapabilityWrongProcess,
                "the capability was issued to a different process");
        }

        if (!string.Equals(found.WorkspaceId, workspaceId, StringComparison.Ordinal))
        {
            return CapabilityCheck.Fail(
                IpcErrorCodes.WorkspaceMismatch,
                "the capability was issued for a different workspace");
        }

        if (found.Epoch != currentEpoch)
        {
            return CapabilityCheck.Fail(
                IpcErrorCodes.EpochStale,
                "the capability predates the workspace's current epoch");
        }

        return CapabilityCheck.Valid;
    }

    /// <summary>Revokes one capability. Idempotent: revoking twice is not an error.</summary>
    public bool Revoke(string token)
    {
        lock (_gate)
        {
            return _issued.Remove(token);
        }
    }

    /// <summary>Revokes everything issued to a connection — what a disconnect must trigger.</summary>
    public int RevokeConnection(string connectionId)
    {
        lock (_gate)
        {
            var doomed = _issued
                .Where(kv => string.Equals(kv.Value.ConnectionId, connectionId, StringComparison.Ordinal))
                .Select(kv => kv.Key)
                .ToList();

            foreach (var token in doomed)
            {
                _issued.Remove(token);
            }

            return doomed.Count;
        }
    }

    private static bool FixedTimeEquals(string a, string b) =>
        CryptographicOperations.FixedTimeEquals(
            System.Text.Encoding.UTF8.GetBytes(a), System.Text.Encoding.UTF8.GetBytes(b));

    private static string Base64Url(byte[] bytes) =>
        Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_');
}
