namespace AiDe.Core.Projections;

/// <summary>
/// What a <see cref="NodeContent"/> query actually did — the value of the <c>content.outcome</c>
/// span tag.
/// </summary>
/// <remarks>
/// <para><b>INV-0014 P4.</b> <see cref="NodeContent.Shortfall"/> tells one reader what to show;
/// this tells an operator what happened, and it is the only one of the two that can be aggregated
/// across a workspace. The span carried no outcome at all, which is why "wrong for two whole
/// languages" was a screenshot rather than a signal.</para>
///
/// <para>Constants rather than literals at the call site: these names travel into saved searches
/// and dashboards, so renaming one is a breaking change and should read like one.</para>
/// </remarks>
public static class NodeContentOutcome
{
    /// <summary>The file was found, opened and returned. The only outcome with no error code.</summary>
    public const string Located = "located";

    /// <summary>No assertion names a source artifact for this node.</summary>
    public const string NoDeclaration = "no-declaration";

    /// <summary>A recorded artifact path that does not name a file inside the workspace.</summary>
    public const string Unresolvable = "unresolvable";

    /// <summary>The file is there and could not be opened.</summary>
    public const string Unreadable = "unreadable";

    /// <summary>A real file whose extension this reader does not render inline.</summary>
    public const string NotRendered = "not-rendered";
}

/// <summary>
/// How a node's content should be rendered — the authority's call, not the reader's guess.
/// </summary>
/// <remarks>
/// ADR-0018 node-content-reader-contract. The reader branches on this rather than inspecting the content or the node id, so a
/// diagram, a proof or a binary comes back as <see cref="None"/> and gets the metadata-and-edges
/// fallback instead of being mis-rendered as text that happens not to be text.
/// </remarks>
public enum NodeContentKind
{
    /// <summary>Source code. Render read-only, highlighted by <see cref="NodeContent.Language"/>.</summary>
    Code,

    /// <summary>Prose — markdown or plain text.</summary>
    Text,

    /// <summary>No inline content. The reader shows metadata and edges instead.</summary>
    None,

    /// <summary>
    /// An HTML document (Ruling 93 — an Owner extension of this enum, admitted because ADR-0018's
    /// text names html among the render kinds). The Explorer reader renders it in a sandbox: script
    /// disabled, no navigation, no network. On the wire the name travels, so an older reader
    /// meets a new name rather than a renumbered value.
    /// </summary>
    Html,
}

/// <summary>
/// One node's content, for a reader that has the node and wants what is behind it.
/// </summary>
/// <param name="NodeId">The node asked for, echoed so a late reply can be matched or discarded.</param>
/// <param name="RenderKind">How to render it.</param>
/// <param name="Language">A highlighting tag — <c>csharp</c>, <c>python</c> — or null.</param>
/// <param name="Content">The text, possibly truncated. Empty when <see cref="RenderKind"/> is None.</param>
/// <param name="Shortfall">
/// What was left out, in words a reader can show. Null when nothing was.
/// </param>
/// <remarks>
/// <para><b>Bounded like every other response.</b> A large file returns the first N bytes and says so,
/// never an oversized frame — the same rule that INV-0003 established for the graph, applied to the
/// one artifact a reader asked for rather than to 1,500 it did not.</para>
///
/// <para><b>Why the authority reads the file and the client does not.</b> The App reading files itself
/// would make two authorities on what a node's content is, and they would disagree the moment one
/// resolved a path differently (DC-022). It would also put file access on the wrong side of the trust
/// boundary: the daemon confines every read to the workspace root, and a client doing its own reading
/// answers to nothing.</para>
/// </remarks>
public sealed record NodeContent(
    string NodeId,
    NodeContentKind RenderKind,
    string? Language,
    string Content,
    string? Shortfall = null);
