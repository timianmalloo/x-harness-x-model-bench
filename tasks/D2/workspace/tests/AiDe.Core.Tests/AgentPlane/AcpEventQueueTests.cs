using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The run-event queue: overflow applies <b>backpressure</b>, and any drop is counted and surfaced.
/// </summary>
/// <remarks>
/// <para><b>Why this is not the terminal idiom.</b> <c>ConPtyTerminalSession</c> uses
/// <c>DropOldest</c>, which is correct there: <c>ITerminalSession</c> states terminal bytes are
/// ephemeral by contract and must never reach the fact store, so the freshest bytes are the only
/// ones worth keeping. ACP events are the opposite — spec §7.1 calls the run log "the truth", and a
/// dropped event is data loss in the durable record. So the queue blocks the reader instead, which
/// backs the pressure up the pipe to the engine.</para>
///
/// <para><b>Why a drop is still modelled at all.</b> "Cannot drop" is not a property a bounded queue
/// can have: the peer stops, the queue closes, and whatever was waiting to be written is lost. The
/// requirement is that when it happens it is <i>counted and surfaced</i> — never silent. The idiom
/// reused from <c>IngestHost.cs</c> is exactly that: the count is the coverage-gap signal.</para>
/// </remarks>
public sealed class AcpEventQueueTests
{
    private static ObservedRunEvent Event(long seq)
        => new(
            new RunEvent("run-1", "lane-1", null, seq, DateTimeOffset.UnixEpoch, "acp.frame", null, [], []),
            DateTimeOffset.UnixEpoch,
            TimeSpan.Zero);

    /// <summary>Inside capacity nothing waits and nothing is lost.</summary>
    [Fact]
    public async Task WithinCapacityEveryEventIsPublishedWithoutWaiting()
    {
        var queue = new AcpEventQueue(capacity: 2);

        await queue.PublishAsync(Event(1));
        await queue.PublishAsync(Event(2));

        Assert.Equal(2, queue.Published);
        Assert.Equal(0, queue.BackpressureWaits);
        Assert.Equal(0, queue.Dropped);
    }

    /// <summary>
    /// A full queue does not drop: the publish is still pending, which is what backpressure looks
    /// like from the writer's side.
    /// </summary>
    [Fact]
    public void AFullQueueBlocksTheReaderInsteadOfDroppingTheEvent()
    {
        var diagnostics = new List<string>();
        var queue = new AcpEventQueue(capacity: 1, diagnostics.Add);

        Assert.True(queue.PublishAsync(Event(1)).IsCompletedSuccessfully);
        var blocked = queue.PublishAsync(Event(2));

        Assert.False(blocked.IsCompleted);
        Assert.Equal(1, queue.BackpressureWaits);
        Assert.Equal(0, queue.Dropped);
        Assert.Contains(diagnostics, d => d.Contains("backpressure", StringComparison.Ordinal));
    }

    /// <summary>Draining one slot releases the waiting publish — the pressure was pressure, not a stall.</summary>
    [Fact]
    public async Task DrainingOneSlotReleasesTheWaitingPublish()
    {
        var queue = new AcpEventQueue(capacity: 1);

        await queue.PublishAsync(Event(1));
        var blocked = queue.PublishAsync(Event(2));

        Assert.True(queue.Reader.TryRead(out var first));
        Assert.Equal(1, first!.Event.Seq);

        await blocked;
        Assert.Equal(2, queue.Published);
        Assert.Equal(0, queue.Dropped);
    }

    /// <summary>
    /// A publish abandoned because the peer is stopping is <b>counted and named</b>, never silent.
    /// </summary>
    [Fact]
    public async Task AnAbandonedPublishIsCountedAndNamedRatherThanLostSilently()
    {
        var diagnostics = new List<string>();
        var queue = new AcpEventQueue(capacity: 1, diagnostics.Add);
        using var stopping = new CancellationTokenSource();

        await queue.PublishAsync(Event(1));
        var blocked = queue.PublishAsync(Event(2), stopping.Token);

        await stopping.CancelAsync();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(async () => await blocked);

        Assert.Equal(1, queue.Dropped);
        Assert.Contains(diagnostics, d => d.Contains("DROPPED", StringComparison.Ordinal) && d.Contains("seq 2", StringComparison.Ordinal));
    }

    /// <summary>A closed queue stops the reader rather than leaving it waiting for an engine that has gone.</summary>
    [Fact]
    public async Task CompletingTheQueueEndsTheReader()
    {
        var queue = new AcpEventQueue(capacity: 4);
        await queue.PublishAsync(Event(1));
        queue.Complete();

        var drained = new List<long>();
        await foreach (var observed in queue.Reader.ReadAllAsync())
        {
            drained.Add(observed.Event.Seq);
        }

        Assert.Equal([1L], drained);
    }
}
