using CfdBench.Core.Units;

namespace CfdBench.Core.Domain;

/// <summary>One station of a half-wing: its distance from the centreline and its chord. A value object; the wing's
/// invariants are checked by <see cref="Wing.Create"/>.
/// Given: part of the fixed architecture (docs/architecture-note.md). Do not change its public contract.</summary>
public readonly record struct Station(Length SpanPosition, Length Chord);
