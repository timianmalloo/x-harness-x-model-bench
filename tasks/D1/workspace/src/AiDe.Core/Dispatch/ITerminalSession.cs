using System.Threading.Channels;
using AiDe.Core.Facts;

namespace AiDe.Core.Dispatch;

/// <summary>One read of the session's output, and whether anything was dropped to produce it.</summary>
/// <remarks>
/// <see cref="Truncated"/> rides on the chunk rather than being a session-level flag on purpose: it
/// says "bytes were dropped immediately before this chunk", which is where a renderer needs to draw
/// its gap marker. A session-level flag would say only that loss happened at some point, which
/// cannot be rendered anywhere in particular.
/// </remarks>
public readonly record struct TerminalChunk(ReadOnlyMemory<byte> Bytes, bool Truncated);

/// <summary>
/// Advisory session state. Never agent acceptance (ADR-0007) — a terminal cannot tell us an agent
/// agreed to anything, only that a process is or is not producing output.
/// </summary>
public enum SessionActivity
{
    /// <summary>The process is being created; no output has arrived.</summary>
    Starting,

    /// <summary>The process is alive and quiet.</summary>
    Ready,

    /// <summary>The process is alive and producing output.</summary>
    Busy,

    /// <summary>The process has ended.</summary>
    Ended,

    /// <summary>Output exceeded the sustained-rate budget, so bytes are being dropped.</summary>
    OutputOverload,
}

/// <summary>How a session ended. <see cref="ExitCode"/> is null when the process was killed.</summary>
public sealed record SessionExit(int? ExitCode, bool Killed, DateTimeOffset At);

/// <summary>
/// The terminal seam. Phase 1 substitutes a fixture session; Phase 2 substitutes a real ConPTY
/// runtime behind this same contract, so the swap is a substitution rather than a redesign.
/// </summary>
/// <remarks>
/// <para><b>Phase-2 amendment.</b> The Phase-1 shape was <b>write-only</b>, because the fixture
/// recorded bytes and returned and nothing ever needed to read. A real terminal's output is the
/// entire point — the renderer subscribes to it, the OSC parser reads it, and the resource budget is
/// defined over it. <see cref="WriteAsync"/> and the generation fence are unchanged, so the
/// write-ahead dispatch built on them is untouched.</para>
///
/// <para><b>Output is pull-based, not an event.</b> An event would let a fast-producing process drive
/// unbounded work on whatever thread raised it — exactly the sustained-1 MiB/s case the architecture
/// budgets for. A bounded channel makes backpressure representable and truncation a <i>state</i>
/// rather than a crash.</para>
///
/// <para>Every implementation must satisfy the shared conformance suite (D7). With two
/// implementations in play, tests written against the fake prove something about the fake unless
/// that suite exists.</para>
/// </remarks>
public interface ITerminalSession : IAsyncDisposable
{
    string SessionId { get; }

    /// <summary>Advances whenever the underlying process is replaced. A bound dispatch is fenced against it.</summary>
    long Generation { get; }

    SessionProcessingClass ProcessingClass { get; }

    /// <summary>
    /// Bounded, ephemeral output. Terminal text never enters the fact store, an audit entry, a log or
    /// telemetry (spec privacy) — reading this channel is the only way it is ever observed.
    /// </summary>
    ChannelReader<TerminalChunk> Output { get; }

    /// <summary>Advisory prompt/exit state. Never agent acceptance (ADR-0007).</summary>
    SessionActivity Activity { get; }

    /// <summary>
    /// Writes bytes to the session, comparing <paramref name="expectedGeneration"/> to the live
    /// generation <em>atomically with the write</em>, on this session's single owner loop.
    /// </summary>
    /// <remarks>
    /// The atomicity is the point: checking the generation and then writing would leave a window in
    /// which the process is replaced and a confirmed prompt lands in a session state the user never
    /// approved. Implementations must never retarget — a mismatch writes zero bytes.
    /// </remarks>
    Task<PtyWriteResult> WriteAsync(long expectedGeneration, ReadOnlyMemory<byte> bytes, CancellationToken cancellationToken);

    /// <summary>Completes when the process ends, and returns the same result to every caller.</summary>
    Task<SessionExit> WaitForExitAsync(CancellationToken cancellationToken);

    /// <summary>Tells the pseudo console its new dimensions. Never changes the generation.</summary>
    ValueTask ResizeAsync(int columns, int rows, CancellationToken cancellationToken);
}
