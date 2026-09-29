using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>A monotonic clock the test drives by hand, so liveness tests are deterministic (D0).</summary>
internal sealed class FakeMonotonicClock : IMonotonicClock
{
    // 1000 ticks == 1 second; a comfortable base avoids the zero edge.
    public long Ticks { get; private set; } = 1_000_000;

    public long TicksPerSecond => 1000;

    public void Advance(TimeSpan by) => Ticks += (long)(by.TotalSeconds * TicksPerSecond);
}

/// <summary>Issues distinct, deterministic capabilities so a test can compare and forge them.</summary>
internal sealed class SequentialCapabilityFactory : ICapabilityFactory
{
    // A per-instance salt so two independent factories never produce a colliding token.
    private readonly byte[] _salt = Guid.NewGuid().ToByteArray();
    private int _counter;

    public SessionCapability Create()
    {
        var token = new byte[32];
        _salt.CopyTo(token, 0);                          // 16 bytes of instance identity
        BitConverter.GetBytes(++_counter).CopyTo(token, 16); // then the per-instance sequence
        return new SessionCapability(token);
    }
}

internal static class WatcherFixtures
{
    /// <summary>A capability no registrar ever issued - the forgery under test.</summary>
    public static SessionCapability ForgedCapability() =>
        new(Enumerable.Repeat((byte)0xEE, 32).ToArray());

    public static SessionBinding Binding(
        string repoPath = "C:/repos/ai-de",
        string terminal = "term-1",
        string agent = "agent-1",
        HarnessIdentity? harness = null,
        ModelIdentity? model = null,
        TrustClassification trust = TrustClassification.Verified)
    {
        var repo = new RepositoryIdentity(repoPath, "ai-de");
        return new SessionBinding(
            repo,
            new WorktreeIdentity(repo, "main", repoPath),
            new TerminalIdentity(terminal),
            new AgentIdentity(agent),
            harness,
            model,
            trust);
    }

    /// <summary>A registration event (attribute bag) for the ingest host / mapper.</summary>
    public static HarnessRegistration HarnessRegistration(
        string? harnessName = null, string? modelName = null)
    {
        var attrs = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [OtelAttributes.RepoPath] = "C:/repos/ai-de",
            [OtelAttributes.RepoDisplay] = "ai-de",
            [OtelAttributes.WorktreeBranch] = "main",
            [OtelAttributes.WorktreePath] = "C:/repos/ai-de",
            [OtelAttributes.TerminalId] = "term-1",
            [OtelAttributes.AgentName] = "agent-1",
        };
        if (harnessName is not null)
        {
            attrs[OtelAttributes.ServiceName] = harnessName;
            attrs[OtelAttributes.ServiceVersion] = "1.0.0";
        }
        if (modelName is not null)
        {
            attrs[OtelAttributes.GenAiModel] = modelName;
            attrs[OtelAttributes.GenAiModelVersion] = "2026-08";
        }

        return new HarnessRegistration(attrs);
    }
}

/// <summary>A fixed wall clock, so a span's RecordedAt is deterministic in tests (D0).</summary>
internal sealed class FixedTimeProvider(DateTimeOffset now) : TimeProvider
{
    public override DateTimeOffset GetUtcNow() => now;
}
