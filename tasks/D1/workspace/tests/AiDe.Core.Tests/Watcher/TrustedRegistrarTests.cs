using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-REG-01..09 — the identity and capability contract (ADR-0020 trusted-registrar-harness-model-identity). The claim under test is not "we
/// record a session" but "a process cannot act as a session it does not hold the capability for, and a
/// restart cannot inherit the prior generation's authority."
/// </summary>
public sealed class TrustedRegistrarTests
{
    private static TrustedRegistrar NewRegistrar(out InMemoryWatcherObservationStore store, out FakeMonotonicClock clock)
    {
        store = new InMemoryWatcherObservationStore();
        clock = new FakeMonotonicClock();
        var seq = 0;
        return new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => $"session-{++seq}");
    }

    [Fact]
    public void Register_ValidBinding_IssuesGenerationOneAndCapability()
    {
        var registrar = NewRegistrar(out _, out _);

        var registered = registrar.Register(WatcherFixtures.Binding());

        Assert.Equal(1, registered.Generation.Value);
        Assert.True(registrar.Verify(registered.SessionId, registered.Capability));
    }

    [Fact]
    public void Register_UnknownHarnessAndModel_StillRegisters()
    {
        var registrar = NewRegistrar(out _, out _);

        var registered = registrar.Register(WatcherFixtures.Binding(harness: null, model: null));

        Assert.Null(registered.Binding.Harness);
        Assert.Null(registered.Binding.Model);
        Assert.True(registrar.Verify(registered.SessionId, registered.Capability));
    }

    [Theory]
    [InlineData("", "term-1", "agent-1")]
    [InlineData("C:/repos/ai-de", "", "agent-1")]
    [InlineData("C:/repos/ai-de", "term-1", "")]
    public void Register_MissingRequiredField_ThrowsInvalidBinding(string repo, string terminal, string agent)
    {
        var registrar = NewRegistrar(out _, out _);

        var ex = Assert.Throws<WatcherException>(
            () => registrar.Register(WatcherFixtures.Binding(repoPath: repo, terminal: terminal, agent: agent)));

        Assert.Equal(WatcherErrorCodes.InvalidBinding, ex.Code);
    }

    [Fact]
    public void Verify_CapabilityFromAnotherSession_IsRejectedAsForgery()
    {
        var registrar = NewRegistrar(out _, out _);
        var a = registrar.Register(WatcherFixtures.Binding(terminal: "term-a"));
        var b = registrar.Register(WatcherFixtures.Binding(terminal: "term-b"));

        // Presenting session A's capability for session B is the forgery case.
        Assert.False(registrar.Verify(b.SessionId, a.Capability));
        Assert.True(registrar.Verify(b.SessionId, b.Capability));
    }

    [Fact]
    public void Verify_UnknownSession_IsFalse()
    {
        var registrar = NewRegistrar(out _, out _);
        var real = registrar.Register(WatcherFixtures.Binding());

        Assert.False(registrar.Verify("session-does-not-exist", real.Capability));
    }

    [Fact]
    public void Register_TwoSessions_HaveDistinctCapabilities()
    {
        var registrar = NewRegistrar(out _, out _);
        var a = registrar.Register(WatcherFixtures.Binding(terminal: "term-a"));
        var b = registrar.Register(WatcherFixtures.Binding(terminal: "term-b"));

        Assert.False(a.Capability.Matches(b.Capability));
    }

    [Fact]
    public void RegisterNextGeneration_IncrementsGeneration_AndInvalidatesPriorCapability()
    {
        var registrar = NewRegistrar(out _, out _);
        var first = registrar.Register(WatcherFixtures.Binding());

        var second = registrar.RegisterNextGeneration(first.SessionId, WatcherFixtures.Binding());

        Assert.Equal(2, second.Generation.Value);
        // The restart's new capability cannot inherit the prior generation's authority.
        Assert.False(registrar.Verify(first.SessionId, first.Capability));
        Assert.True(registrar.Verify(second.SessionId, second.Capability));
    }

    [Fact]
    public void Heartbeat_WithForgedCapability_ThrowsForgery()
    {
        var registrar = NewRegistrar(out _, out _);
        var a = registrar.Register(WatcherFixtures.Binding(terminal: "term-a"));
        var b = registrar.Register(WatcherFixtures.Binding(terminal: "term-b"));

        var ex = Assert.Throws<WatcherException>(() => registrar.Heartbeat(b.SessionId, a.Capability));

        Assert.Equal(WatcherErrorCodes.ForgeryRejected, ex.Code);
    }

    [Fact]
    public void RegisterNextGeneration_ClearsEndedState()
    {
        var registrar = NewRegistrar(out var store, out _);
        var first = registrar.Register(WatcherFixtures.Binding());
        registrar.End(first.SessionId, first.Capability);
        Assert.True(store.IsEnded(first.SessionId));

        registrar.RegisterNextGeneration(first.SessionId, WatcherFixtures.Binding());

        Assert.False(store.IsEnded(first.SessionId));
    }
}
