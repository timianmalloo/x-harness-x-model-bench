using CfdBench.Core.Units;

namespace CfdBench.Core.Domain;

/// <summary>
/// One station of a half-wing: its distance from the centreline, its leading-edge x (positive aft), its chord and its
/// twist (incidence, positive nose-up). A value object; the wing's invariants are checked by <see cref="Wing.Create"/>.
/// </summary>
public readonly record struct Station(Length SpanPosition, Length LeadingEdgeX, Length Chord, Angle Twist);
