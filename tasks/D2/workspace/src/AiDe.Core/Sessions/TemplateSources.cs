using System.Reflection;

namespace AiDe.Core.Sessions;

/// <summary>One template file a source offers, with wherever it came from.</summary>
/// <param name="Origin">A path or resource name. It is what an error message points a person at.</param>
/// <param name="Text">The file's whole text, frontmatter and body.</param>
public sealed record TemplateDocument(string Origin, string Text);

/// <summary>A place templates come from (B3.2).</summary>
/// <remarks>
/// Deliberately an interface over a list of documents rather than a directory: the built-in source is
/// inside the assembly, a workspace source is a directory, and a later pack or personal source is
/// another directory somewhere else. The catalog only needs "here are the files".
/// </remarks>
public interface ITemplateSource
{
    /// <summary>One of <see cref="TemplateSources.PrecedenceOrder"/>.</summary>
    string SourceId { get; }

    /// <summary>Every template document this source currently offers.</summary>
    IReadOnlyList<TemplateDocument> Read();
}

/// <summary>
/// The source names, their fixed precedence, and the set Phase 1 actually registers.
/// </summary>
/// <remarks>
/// <para><b>The full order is pinned NOW, though Phase 1 ships two of the four (Ruling 26 cut i).</b>
/// Pack's lifecycle is <c>/updatepack</c>'s, which is Phase 3, and personal has no settings surface
/// yet. Fixing <c>personal &gt; workspace &gt; pack &gt; built-in</c> here means registering either of
/// them later is DATA — constructing a source — rather than a renegotiation of which one wins.</para>
///
/// <para><b>Sources are an ordered descriptor list.</b> The catalog sorts what it is handed by
/// <see cref="RankOf"/>, so a new source joins by being passed in; nothing in the loader enumerates
/// the sources it knows about.</para>
/// </remarks>
public static class TemplateSources
{
    /// <summary>The private, per-person source — <c>~/.aide/templates/</c>. Not registered in Phase 1.</summary>
    public const string Personal = "personal";

    /// <summary>The committed, repository-shared source — <c>.aide/templates/</c>.</summary>
    public const string Workspace = "workspace";

    /// <summary>The pack source, arriving via <c>/updatepack</c>. Not registered in Phase 1.</summary>
    public const string Pack = "pack";

    /// <summary>The twelve shipped with AI-DE. Always last, so anything can override it.</summary>
    public const string BuiltIn = "built-in";

    /// <summary>Highest precedence first. Same-id templates resolve by this order and only this order.</summary>
    public static readonly IReadOnlyList<string> PrecedenceOrder = [Personal, Workspace, Pack, BuiltIn];

    /// <summary>Where a source sits in <see cref="PrecedenceOrder"/>. Lower wins.</summary>
    /// <exception cref="ArgumentException">The source id is not one this contract names.</exception>
    public static int RankOf(string sourceId)
    {
        var rank = PrecedenceOrder.ToList().IndexOf(sourceId);
        return rank >= 0
            ? rank
            : throw new ArgumentException(
                $"'{sourceId}' is not a template source; the contract names {string.Join(", ", PrecedenceOrder)}",
                nameof(sourceId));
    }

    /// <summary>
    /// The sources Phase 1 registers: workspace over built-in.
    /// </summary>
    /// <param name="workspaceRoot">The open workspace, or null when there is none.</param>
    public static IReadOnlyList<ITemplateSource> Phase1(string? workspaceRoot)
    {
        var sources = new List<ITemplateSource>();
        if (workspaceRoot is not null)
        {
            sources.Add(new WorkspaceTemplateSource(workspaceRoot));
        }

        sources.Add(new BuiltInTemplateSource());
        return sources;
    }
}

/// <summary>
/// The twelve built-in templates, transcribed from Addendum B §B4 and shipped inside the assembly.
/// </summary>
/// <remarks>
/// <b>Real template files, not a table of C# constants.</b> They are embedded resources read through
/// the same loader every other source uses, so a mistake in one of them fails the same way a
/// workspace author's would — and the built-in catalog is evidence that the loader works rather than
/// a path around it.
/// </remarks>
public sealed class BuiltInTemplateSource : ITemplateSource
{
    private const string ResourcePrefix = "AiDe.Core.Sessions.BuiltIn.";

    /// <inheritdoc />
    public string SourceId => TemplateSources.BuiltIn;

    /// <inheritdoc />
    public IReadOnlyList<TemplateDocument> Read()
    {
        var assembly = typeof(BuiltInTemplateSource).GetTypeInfo().Assembly;
        var documents = new List<TemplateDocument>();

        foreach (var name in assembly.GetManifestResourceNames().Order(StringComparer.Ordinal))
        {
            if (!name.EndsWith(".template.md", StringComparison.Ordinal))
            {
                continue;
            }

            using var stream = assembly.GetManifestResourceStream(name);
            if (stream is null)
            {
                continue;
            }

            using var reader = new StreamReader(stream);
            var origin = name.StartsWith(ResourcePrefix, StringComparison.Ordinal)
                ? name[ResourcePrefix.Length..]
                : name;

            documents.Add(new TemplateDocument(origin, reader.ReadToEnd()));
        }

        return documents;
    }
}

/// <summary>The workspace's own templates — <c>.aide/templates/</c>, committed beside the code they serve.</summary>
/// <param name="workspaceRoot">The workspace directory.</param>
public sealed class WorkspaceTemplateSource(string workspaceRoot) : ITemplateSource
{
    /// <summary>Where a workspace keeps its templates, relative to the workspace root (B3.2).</summary>
    public static readonly string RelativeDirectory = Path.Combine(".aide", "templates");

    /// <inheritdoc />
    public string SourceId => TemplateSources.Workspace;

    /// <inheritdoc />
    /// <remarks>
    /// A workspace with no templates directory reads EMPTY, not broken. Most workspaces will never
    /// have one, and a missing optional directory that threw would make the built-in catalog
    /// unreachable for them.
    /// </remarks>
    public IReadOnlyList<TemplateDocument> Read()
    {
        var directory = Path.Combine(workspaceRoot, RelativeDirectory);
        if (!Directory.Exists(directory))
        {
            return [];
        }

        return Directory
            .GetFiles(directory, "*.template.md", SearchOption.TopDirectoryOnly)
            .Order(StringComparer.Ordinal)
            .Select(path => new TemplateDocument(Path.GetFileName(path), File.ReadAllText(path)))
            .ToList();
    }
}
