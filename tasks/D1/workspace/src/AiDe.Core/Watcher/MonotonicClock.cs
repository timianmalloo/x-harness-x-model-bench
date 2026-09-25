using System.Diagnostics;

namespace AiDe.Core.Watcher;

/// <summary>
/// A monotonic time source. Liveness uses elapsed monotonic duration, never the wall clock, so a
/// wall-clock change (NTP step, timezone, manual set) cannot flip a session's state (spec US-2;
/// defect class TEST-CLOCK). Abstracted so a test can drive time deterministically.
/// </summary>
public interface IMonotonicClock
{
    /// <summary>A monotonically non-decreasing tick count. Only differences are meaningful.</summary>
    long Ticks { get; }

    /// <summary>Ticks per second, for converting a tick delta to a duration.</summary>
    long TicksPerSecond { get; }
}

/// <summary>The production clock, backed by the high-resolution monotonic <see cref="Stopwatch"/>.</summary>
public sealed class SystemMonotonicClock : IMonotonicClock
{
    public long Ticks => Stopwatch.GetTimestamp();

    public long TicksPerSecond => Stopwatch.Frequency;
}
