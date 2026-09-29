namespace AiDe.Core.Watcher;

/// <summary>Whether an egress path may be used.</summary>
public enum EgressDecision
{
    /// <summary>The default: no opt-in enabled this path (LK-0003).</summary>
    Blocked,

    /// <summary>An explicit, per-path opt-in enabled this path.</summary>
    Allowed,
}

/// <summary>
/// The default-deny egress gateway (ADR-0024 credential-backed-grading-egress, extends ADR-0011). Outbound is blocked until an explicit
/// per-path opt-in enables exactly that path; every other path stays blocked. The gate ships in Phase 1,
/// before any component that could egress, so the local-only default is enforced from the start.
/// </summary>
public sealed class EgressGate
{
    private readonly object _gate = new();
    private readonly HashSet<string> _allowed = new(StringComparer.Ordinal);

    /// <summary>Blocked unless this exact path was opted in.</summary>
    public EgressDecision Decide(string pathId)
    {
        ArgumentException.ThrowIfNullOrEmpty(pathId);
        lock (_gate)
        {
            return _allowed.Contains(pathId) ? EgressDecision.Allowed : EgressDecision.Blocked;
        }
    }

    /// <summary>Enables exactly one path. Every other path remains blocked.</summary>
    public void OptIn(string pathId)
    {
        ArgumentException.ThrowIfNullOrEmpty(pathId);
        lock (_gate)
        {
            _allowed.Add(pathId);
        }
    }

    /// <summary>Revokes a previously opted-in path; it returns to blocked.</summary>
    public void Revoke(string pathId)
    {
        ArgumentException.ThrowIfNullOrEmpty(pathId);
        lock (_gate)
        {
            _allowed.Remove(pathId);
        }
    }
}
