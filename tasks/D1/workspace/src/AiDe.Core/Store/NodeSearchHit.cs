namespace AiDe.Core.Store;

/// <summary>Why a node came back from a search.</summary>
/// <remarks>
/// A result whose relevance is invisible reads as a wrong result. Searching <c>addEventListener</c>
/// and being shown a class called <c>Element</c> is correct and looks like a bug until the row says
/// <c>has_member = addEventListener</c>.
/// </remarks>
public enum NodeMatchKind
{
    /// <summary>The node's own identity contains the term.</summary>
    Identity,

    /// <summary>One of the node's attribute values contains the term.</summary>
    Attribute,
}

/// <summary>One search hit: the node, why it matched, and the text that matched.</summary>
/// <param name="Evidence">
/// <c>predicate = value</c>, truncated. Null for an identity match, where the id is the evidence and
/// repeating it would be noise.
/// </param>
public sealed record NodeSearchHit(string NodeId, NodeMatchKind Kind, string? Evidence);
