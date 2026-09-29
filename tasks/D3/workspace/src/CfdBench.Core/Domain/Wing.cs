namespace CfdBench.Core.Domain;

/// <summary>
/// The wing aggregate: a symmetric wing described by the stations of one half, root first.
/// STUB — not yet implemented. Invariants: docs/architecture-note.md, "Wing aggregate invariants".
/// Keep the public shape below; add whatever private state you need.
/// </summary>
public sealed class Wing
{
    public IReadOnlyList<Station> Stations => throw new NotImplementedException();

    public static Wing Create(IReadOnlyList<Station> stations) => throw new NotImplementedException();
}
