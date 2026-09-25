using System.Diagnostics;
using AiDe.Core.Extraction;
using AiDe.Core.Store;

namespace AiDe.Core.Health;

/// <summary>Reads the repository's current revision for a scope, independent of the watcher.</summary>
public interface IRevisionProbe
{
    string? ObservedRevision(string scopeId);
}

public sealed record FreshnessDrift(string ScopeId, string? ObservedRevision, string? IndexedRevision);

/// <summary>
/// Detects silent watcher loss by comparing what the repository says to what the store indexed.
/// </summary>
/// <remarks>
/// The SRE review found the staleness metric self-referential: it measured against the daemon's own
/// last known event, so a dead watcher reads as perfectly fresh while the graph rots. Staleness has
/// to be measured against the repository, which is what this does — an independent probe, not a
/// second opinion from the same source.
/// </remarks>
public sealed class FreshnessProber(
    WorkspaceStore store,
    IRevisionProbe probe,
    HealthIncidentSidecar incidents)
{
    public const string DriftIncidentClass = "freshness.drift";

    private static readonly ActivitySource Activity = new("aide.freshness.probe");

    /// <summary>Probes each scope and raises an incident for every divergence found.</summary>
    public IReadOnlyList<FreshnessDrift> Probe(IEnumerable<string> scopeIds, DateTimeOffset now)
    {
        using var activity = Activity.StartActivity("aide.freshness.probe");

        var drifts = new List<FreshnessDrift>();
        using var reader = store.BeginRead();

        foreach (var scopeId in scopeIds)
        {
            var observed = probe.ObservedRevision(scopeId);
            // Base, not stamped. The stored revision also carries the extractor generation that
            // produced it (SourceRevision); comparing that against a repository revision would
            // report permanent drift on every workspace, which is a prober that means nothing.
            var indexed = SourceRevision.Base(reader.LatestCommittedSnapshot(scopeId)?.ArtifactRevision ?? string.Empty);
            if (indexed.Length == 0) indexed = null;

            if (string.Equals(observed, indexed, StringComparison.Ordinal))
            {
                continue;
            }

            var drift = new FreshnessDrift(scopeId, observed, indexed);
            drifts.Add(drift);
            incidents.Record(DriftIncidentClass, scopeId,
                $"repository revision '{observed ?? "none"}' does not match indexed '{indexed ?? "none"}'", now);
        }

        activity?.SetTag("freshness.drift_count", drifts.Count);
        return drifts;
    }
}
