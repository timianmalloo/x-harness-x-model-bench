using AiDe.Core.Sessions;

namespace AiDe.Core.Presentation.Composer;

/// <summary>One card in the template picker, as the picker renders it.</summary>
/// <param name="Id">The catalog id the composer binds to when this row is chosen.</param>
/// <param name="Headline">
/// The card's first line. For a loaded template this is its <c>when_to_use</c>, verbatim — the
/// sentence that tells an operator whether this is the template they want.
/// </param>
/// <param name="Detail">The card's second line: <c>why</c>, verbatim.</param>
/// <param name="IsEnabled">Whether the row can be chosen. A failed template is shown, not dropped.</param>
/// <param name="IsOverride">Whether this row shadows a same-id template from a lower-precedence source.</param>
/// <param name="OverrideBadge">What the badge says, or empty when there is nothing to badge.</param>
public sealed record TemplatePickerRow(
    string Id, string Headline, string Detail, bool IsEnabled, bool IsOverride, string OverrideBadge);

/// <summary>
/// Projects a catalog into picker cards — headline, detail, badge, and the disabled rows.
/// </summary>
/// <remarks>
/// <para><b>Nothing is silently dropped, and that is the reason this is a projection rather than a
/// filter.</b> A template that failed load becomes a <b>disabled row carrying its error</b>, because
/// a picker that hides a broken file makes the file invisible at exactly the moment somebody is
/// looking for it.</para>
///
/// <para><b>The headline is <c>when_to_use</c> and the detail is <c>why</c>, verbatim.</b> Both are
/// load-blocking in the catalog, so a row that got this far has them; transcribing or paraphrasing
/// them here would be a second copy of text the twelve built-ins are byte-for-byte checked against.
/// </para>
/// </remarks>
public static class ComposerTemplatePicker
{
    /// <summary>Every catalog entry as a card, in the catalog's own order.</summary>
    public static IReadOnlyList<TemplatePickerRow> Rows(TemplateCatalog catalog)
    {
        ArgumentNullException.ThrowIfNull(catalog);

        return
        [
            .. catalog.Entries.Select(entry => entry.IsEnabled
                ? new TemplatePickerRow(
                    entry.Id,
                    entry.Template!.WhenToUse,
                    entry.Template.Why,
                    IsEnabled: true,
                    entry.IsOverride,
                    Badge(entry))
                : new TemplatePickerRow(
                    entry.Id,
                    $"{entry.Id} — this template did not load",
                    string.Join("; ", entry.Errors.Select(e => $"{e.Code}: {e.Message}")),
                    IsEnabled: false,
                    entry.IsOverride,
                    Badge(entry))),
        ];
    }

    private static string Badge(CatalogEntry entry) =>
        entry.IsOverride
            ? $"overrides {string.Join(", ", entry.ShadowedSourceIds)}"
            : string.Empty;
}
