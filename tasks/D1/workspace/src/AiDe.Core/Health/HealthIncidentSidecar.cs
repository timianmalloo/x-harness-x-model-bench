using System.Globalization;
using System.Text;
using System.Text.Json;

namespace AiDe.Core.Health;

public sealed record HealthIncident(
    string IncidentClass,
    string ScopeId,
    string Message,
    int OccurrenceCount,
    DateTimeOffset FirstSeen,
    DateTimeOffset LastSeen,
    bool Acknowledged);

/// <summary>
/// The durable incident channel, deliberately a small file **outside** the workspace database.
/// </summary>
/// <remarks>
/// The SRE review found the original design circular: disk-full, WAL-full and corruption move the
/// store to read-only, yet those are exactly the failures that must be recorded — an incident store
/// inside the database cannot record the failure that broke the database. Incidents therefore live
/// here, deduplicated by {class, scope} with an occurrence count so a flapping condition cannot
/// flood out the one incident that mattered, and unacknowledged incidents are evicted last.
/// </remarks>
public sealed class HealthIncidentSidecar(string filePath, int capacity = 128)
{
    private readonly Lock _gate = new();

    /// <summary>Records an occurrence, collapsing onto an existing incident of the same class+scope.</summary>
    public void Record(string incidentClass, string scopeId, string message, DateTimeOffset now)
    {
        lock (_gate)
        {
            var incidents = ReadAllUnsafe().ToList();
            var index = incidents.FindIndex(i =>
                i.IncidentClass == incidentClass && i.ScopeId == scopeId && !i.Acknowledged);

            if (index >= 0)
            {
                var existing = incidents[index];
                incidents[index] = existing with
                {
                    OccurrenceCount = existing.OccurrenceCount + 1,
                    LastSeen = now,
                    Message = message,
                };
            }
            else
            {
                incidents.Add(new HealthIncident(incidentClass, scopeId, message, 1, now, now, false));
            }

            if (incidents.Count > capacity)
            {
                // Acknowledged first, then oldest. An unacknowledged incident survives longest
                // because it is the one nobody has seen yet.
                incidents = [.. incidents
                    .OrderBy(i => i.Acknowledged ? 0 : 1)
                    .ThenBy(i => i.LastSeen)
                    .Skip(incidents.Count - capacity)];
            }

            WriteAllUnsafe(incidents);
        }
    }

    public void Acknowledge(string incidentClass, string scopeId)
    {
        lock (_gate)
        {
            var incidents = ReadAllUnsafe()
                .Select(i => i.IncidentClass == incidentClass && i.ScopeId == scopeId
                    ? i with { Acknowledged = true }
                    : i)
                .ToList();
            WriteAllUnsafe(incidents);
        }
    }

    public IReadOnlyList<HealthIncident> Read()
    {
        lock (_gate)
        {
            return ReadAllUnsafe();
        }
    }

    public IReadOnlyList<HealthIncident> Unacknowledged()
        => [.. Read().Where(i => !i.Acknowledged)];

    private List<HealthIncident> ReadAllUnsafe()
    {
        if (!File.Exists(filePath))
        {
            return [];
        }

        var incidents = new List<HealthIncident>();
        foreach (var line in File.ReadAllLines(filePath))
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            try
            {
                var incident = JsonSerializer.Deserialize<HealthIncident>(line);
                if (incident is not null)
                {
                    incidents.Add(incident);
                }
            }
            catch (JsonException)
            {
                // A torn final line from an interrupted write is skipped rather than throwing:
                // the incident channel must survive the crash it exists to report.
            }
        }

        return incidents;
    }

    private void WriteAllUnsafe(IEnumerable<HealthIncident> incidents)
    {
        var directory = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrEmpty(directory))
        {
            Directory.CreateDirectory(directory);
        }

        var builder = new StringBuilder();
        foreach (var incident in incidents)
        {
            builder.AppendLine(JsonSerializer.Serialize(incident));
        }

        File.WriteAllText(filePath, builder.ToString(), Encoding.UTF8);
    }

    public string Describe()
    {
        var open = Unacknowledged();
        return open.Count == 0
            ? "All scopes current"
            : string.Create(CultureInfo.InvariantCulture, $"{open.Count} open incident(s)");
    }
}
