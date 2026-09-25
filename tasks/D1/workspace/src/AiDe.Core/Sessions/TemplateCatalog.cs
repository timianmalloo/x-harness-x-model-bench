namespace AiDe.Core.Sessions;

/// <summary>One template as the catalog offers it — or refuses to, with its reasons.</summary>
/// <param name="Id">The template id, or the origin when the file never declared one.</param>
/// <param name="Template">The loaded template, or null when it failed load.</param>
/// <param name="SourceId">Which source won this id.</param>
/// <param name="Origin">The winning file's path or resource name.</param>
/// <param name="Errors">Why it did not load. Empty for an enabled entry.</param>
/// <param name="ShadowedSourceIds">
/// The sources this entry overrides, in precedence order. Non-empty is the override badge: R18 says
/// an override is visibly badged, and the model has to carry the fact for a view to show it.
/// </param>
public sealed record CatalogEntry(
    string Id,
    PromptTemplate? Template,
    string SourceId,
    string Origin,
    IReadOnlyList<TemplateError> Errors,
    IReadOnlyList<string> ShadowedSourceIds)
{
    /// <summary>Whether the picker may offer this entry. A disabled entry still appears, carrying its errors.</summary>
    public bool IsEnabled => Template is not null && Errors.Count == 0;

    /// <summary>Whether this entry shadows a same-id template from a lower-precedence source.</summary>
    public bool IsOverride => ShadowedSourceIds.Count > 0;
}

/// <summary>
/// The template catalog: every source's templates, resolved by precedence (B3.2, R18).
/// </summary>
/// <remarks>
/// <para><b>Nothing is silently dropped.</b> A template that fails load becomes a DISABLED entry
/// carrying its errors (Ruling 26(e)). The catalog view that renders it is Phase 3 (R22); what has to
/// be true now is that the model carries the failure, because a view cannot restore information the
/// model threw away.</para>
///
/// <para><b>A broken override still wins.</b> If a workspace file shadows a built-in and fails to
/// load, the entry is the broken workspace one, disabled and badged — not a quiet fallback to the
/// built-in. Falling back would hide a broken file behind a catalog that looks healthy, which is the
/// silent drop again in another costume.</para>
/// </remarks>
public sealed class TemplateCatalog
{
    private readonly Dictionary<string, CatalogEntry> _byId;

    private TemplateCatalog(IReadOnlyList<CatalogEntry> entries)
    {
        Entries = entries;
        _byId = entries.ToDictionary(e => e.Id, StringComparer.Ordinal);
    }

    /// <summary>Every entry, ordered by id, so two loads of one workspace list identically.</summary>
    public IReadOnlyList<CatalogEntry> Entries { get; }

    /// <summary>The catalog of just the twelve built-ins.</summary>
    public static TemplateCatalog BuiltIn() => Load([new BuiltInTemplateSource()]);

    /// <summary>
    /// Loads every source and resolves same-id collisions by <see cref="TemplateSources.PrecedenceOrder"/>.
    /// </summary>
    /// <param name="sources">
    /// The registered sources, in any order. They are sorted here, so registration order carries no
    /// meaning and adding a source later cannot change what a caller has to pass.
    /// </param>
    public static TemplateCatalog Load(IReadOnlyList<ITemplateSource> sources)
    {
        ArgumentNullException.ThrowIfNull(sources);

        var candidates = new List<CatalogEntry>();

        foreach (var source in sources.OrderBy(s => TemplateSources.RankOf(s.SourceId)))
        {
            candidates.AddRange(ReadOne(source));
        }

        var entries = new List<CatalogEntry>();

        foreach (var group in candidates.GroupBy(c => c.Id, StringComparer.Ordinal))
        {
            var ordered = group.ToList();
            var winner = ordered[0];
            var shadowed = ordered.Skip(1).Select(e => e.SourceId).ToList();

            entries.Add(winner with { ShadowedSourceIds = shadowed });
        }

        return new TemplateCatalog(entries.OrderBy(e => e.Id, StringComparer.Ordinal).ToList());
    }

    /// <summary>The entry for an id, or null when the catalog carries none.</summary>
    public CatalogEntry? Find(string id)
    {
        ArgumentNullException.ThrowIfNull(id);
        return _byId.TryGetValue(id, out var entry) ? entry : null;
    }

    /// <summary>
    /// One source's documents, with an id collision INSIDE the source collapsed into one refusal.
    /// </summary>
    /// <remarks>
    /// B7 makes an id collision within a source a load failure. It cannot be resolved by precedence —
    /// both files are equally authoritative — so both are refused under the one id, and neither is
    /// offered.
    /// </remarks>
    private static IReadOnlyList<CatalogEntry> ReadOne(ITemplateSource source)
    {
        var loaded = new List<CatalogEntry>();

        foreach (var document in source.Read())
        {
            var result = TemplateLoader.Load(document.Text);

            loaded.Add(new CatalogEntry(
                result.DeclaredId ?? document.Origin,
                result.Template,
                source.SourceId,
                document.Origin,
                result.Errors,
                []));
        }

        var entries = new List<CatalogEntry>();

        foreach (var group in loaded.GroupBy(e => e.Id, StringComparer.Ordinal))
        {
            var ordered = group.ToList();
            if (ordered.Count == 1)
            {
                entries.Add(ordered[0]);
                continue;
            }

            var origins = string.Join(", ", ordered.Select(e => e.Origin).Order(StringComparer.Ordinal));

            entries.Add(ordered[0] with
            {
                Template = null,
                Errors =
                [
                    .. ordered[0].Errors,
                    new TemplateError(
                        TemplateErrorCodes.DuplicateIdInSource,
                        $"the {source.SourceId} source declares id '{ordered[0].Id}' {ordered.Count} times "
                        + $"({origins}); one source cannot choose between them"),
                ],
            });
        }

        return entries;
    }
}
