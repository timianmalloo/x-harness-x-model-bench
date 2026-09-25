using AiDe.Core.Health;
using AiDe.Core.Upgrade;

namespace AiDe.Core.Presentation;

/// <summary>What the operator can see about the daemon behind the shell.</summary>
public sealed record WorkspaceDiagnostics(
    string? CurrentVersion,
    IReadOnlyList<string> InstalledVersions,
    string? RollbackTarget,
    IReadOnlyList<string> Incidents,
    IReadOnlyList<string> McpTools)
{
    /// <summary>One paragraph for the announcement channel and the diagnostics pane.</summary>
    public string Describe()
    {
        var lines = new List<string>
        {
            CurrentVersion is null
                ? "Daemon: no side-by-side installation is in use (running in place)."
                : $"Daemon version: {CurrentVersion}.",
        };

        if (InstalledVersions.Count > 0)
        {
            lines.Add($"Installed: {string.Join(", ", InstalledVersions)}.");
        }

        // Whether a rollback is POSSIBLE is the first thing an operator wants to know, and the
        // honest answer is often "no" — keeping the previous build is what makes rollback work, and
        // a fresh install has nothing to go back to.
        lines.Add(RollbackTarget is null
            ? "Rollback: unavailable — there is no previous version installed."
            : $"Rollback would return to {RollbackTarget}.");

        lines.Add(Incidents.Count == 0
            ? "Health: no unacknowledged incidents."
            : $"Health: {Incidents.Count} incident(s) — {string.Join("; ", Incidents.Take(3))}.");

        lines.Add(McpTools.Count == 0
            ? "MCP tools: none registered."
            : $"MCP tools: {string.Join(", ", McpTools)} (read-only, local-only).");

        return string.Join(" ", lines);
    }
}

/// <summary>
/// Reads the daemon's operational state so the shell can show it.
/// </summary>
/// <remarks>
/// <para><b>Read-only, deliberately.</b> Upgrade and rollback are choreographed against a store that
/// a running binary may not be able to read halfway through — the ordering (snapshot, journal,
/// migrate, gate, commit) exists precisely because a half-finished upgrade is worse than one that
/// never started. A button that starts that from inside the app being upgraded is not a convenience;
/// this surfaces the state and names what a rollback would do, and the act itself stays with the
/// Bootstrap.</para>
///
/// <para><b>The MCP tool list is the registered set, not a guess.</b> It is read from the gateway so
/// a tool added without appearing here would be a discrepancy rather than a documentation lag.</para>
/// </remarks>
public sealed class WorkspaceDiagnosticsViewModel(
    DaemonInstallation? installation,
    HealthIncidentSidecar? incidents,
    IReadOnlyList<string>? mcpTools = null)
{
    public WorkspaceDiagnostics Read()
    {
        var installed = installation?.Installed.Select(v => v.Version).ToList() ?? [];
        var current = installation?.Current;

        // "The newest version that is not the current one" — after a rollback the current version is
        // an OLDER one, so "the second newest" would name the build we just rolled away from.
        var rollbackTarget = installed
            .Where(v => !string.Equals(v, current, StringComparison.OrdinalIgnoreCase))
            .OrderByDescending(v => v, StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault();

        var open = incidents?.Unacknowledged() ?? [];

        return new WorkspaceDiagnostics(
            current,
            installed,
            rollbackTarget,
            open.Select(i => $"{i.IncidentClass} ({i.ScopeId})").ToList(),
            mcpTools ?? McpToolGatewayNames);
    }

    /// <summary>The tools the MCP gateway exposes. Local-only and read-only by ADR-0004.</summary>
    /// <remarks>
    /// <para><b>Derived from the gateway, not restated.</b> This was a hand-written
    /// <c>["describe", "impact", "find", "knowledge"]</c> and it was wrong in both directions:
    /// <c>impact</c> and <c>knowledge</c> are daemon IPC operations and have never been gateway
    /// tools, while <c>standing</c> — added for US-16 — was missing. An operator reading the
    /// diagnostics was told about two tools that do not exist and not told about one that
    /// does.</para>
    ///
    /// <para>A second authority on what a component exposes disagrees with it eventually; this one
    /// disagreed on three of five entries. Reflected over the methods that actually return an
    /// <see cref="AiDe.Core.Mcp.McpToolResult"/>, so a tool added tomorrow appears here without
    /// anyone remembering this list exists (DC-021).</para>
    /// </remarks>
    public static IReadOnlyList<string> McpToolGatewayNames { get; } =
        [.. typeof(AiDe.Core.Mcp.McpToolGateway)
            .GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance)
            .Where(m => m.ReturnType == typeof(AiDe.Core.Mcp.McpToolResult))
            .Select(m => m.Name.ToLowerInvariant())
            .OrderBy(n => n, StringComparer.Ordinal)];
}
