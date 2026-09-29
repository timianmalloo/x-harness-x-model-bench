using System.Globalization;
using System.Text.RegularExpressions;

namespace AiDe.Core.Sessions;

/// <summary>
/// Load-time validation of one template file: every refusal B7 names, reported at once.
/// </summary>
/// <remarks>
/// <para><b><c>when_to_use</c> and <c>why</c> are load-blocking (Ruling 26(e)).</b> A template that
/// cannot say when to pick it and why it earns its place does not load — and does not vanish either:
/// <see cref="TemplateCatalog"/> lists it as a disabled entry carrying these errors.</para>
///
/// <para><b>All the errors, not the first.</b> Someone repairing a template file should learn
/// everything wrong with it in one pass; one-at-a-time validation turns a four-line fix into four
/// edit-and-reload cycles.</para>
///
/// <para><b>Every type decision is made here, from the schema.</b> The reader hands over strings;
/// this file decides what is a version, a field type, a flag and a minimum. That is the whole of
/// "deserialize into the schema type only" — the document has no say.</para>
/// </remarks>
public static partial class TemplateLoader
{
    /// <summary>Reads one template file's text.</summary>
    public static TemplateLoadResult Load(string text)
    {
        ArgumentNullException.ThrowIfNull(text);

        var errors = new List<TemplateError>();

        if (!TemplateFrontmatterReader.TrySplit(text, out var frontmatter, out var body))
        {
            errors.Add(new TemplateError(
                TemplateErrorCodes.MissingFrontmatter,
                $"the file has no '---' frontmatter block, so it declares no {TemplateContract.SchemaVersion} template"));
            return new TemplateLoadResult(null, errors);
        }

        var raw = TemplateFrontmatterReader.Read(frontmatter, errors);
        if (raw is null)
        {
            return new TemplateLoadResult(null, errors);
        }

        var id = Required(raw.Id);
        if (id is null)
        {
            errors.Add(new TemplateError(
                TemplateErrorCodes.MissingId,
                "the template declares no 'id', so the catalog has nothing to key it on"));
        }

        var version = Integer(raw.Version);
        if (version is not > 0)
        {
            errors.Add(new TemplateError(
                TemplateErrorCodes.InvalidVersion,
                "the template declares no positive integer 'version'; the block recipe records a version, "
                + "and a recipe that recorded nothing could not re-render"));
        }

        var intent = Required(raw.Intent);
        var audience = Required(raw.Audience);
        if (intent is null || audience is null)
        {
            errors.Add(new TemplateError(
                TemplateErrorCodes.MissingIntentOrAudience,
                "the template declares no 'intent' and 'audience'; the catalog browses by intent and the "
                + "compiled prompt is addressed to the audience"));
        }

        var whenToUse = Required(raw.WhenToUse);
        if (whenToUse is null)
        {
            errors.Add(new TemplateError(
                TemplateErrorCodes.MissingWhenToUse,
                "the template declares no 'when_to_use'; a template that cannot say when to pick it does "
                + "not load (Addendum B §B7)"));
        }

        var why = Required(raw.Why);
        if (why is null)
        {
            errors.Add(new TemplateError(
                TemplateErrorCodes.MissingWhy,
                "the template declares no 'why'; a template that cannot say why it earns its place does "
                + "not load (Addendum B §B7)"));
        }

        var fields = ReadFields(raw, errors);
        CheckSlots(body, fields, errors);

        if (errors.Count > 0)
        {
            return new TemplateLoadResult(null, errors, id);
        }

        var template = new PromptTemplate(
            id!,
            version!.Value,
            intent!,
            audience!,
            whenToUse!,
            why!,
            raw.TierDefault,
            fields,
            body,
            raw.Unknown);

        return new TemplateLoadResult(template, errors, id);
    }

    /// <summary>A required value, or null when it is absent or blank. Blank and absent want one answer.</summary>
    private static string? Required(string? value)
        => string.IsNullOrWhiteSpace(value) ? null : value;

    /// <summary>An integer the schema asked for, read invariantly. Null when the text is not one.</summary>
    private static int? Integer(string? text)
        => int.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var value) ? value : null;

    private static IReadOnlyList<TemplateField> ReadFields(RawTemplate raw, List<TemplateError> errors)
    {
        if (raw.FieldsMalformed)
        {
            errors.Add(new TemplateError(
                TemplateErrorCodes.MalformedField,
                "'fields' is not a sequence of field declarations"));
            return [];
        }

        if (raw.Fields is null)
        {
            // A template with no fields is a fixed prompt, which is a legitimate shape.
            return [];
        }

        var fields = new List<TemplateField>();
        var seen = new HashSet<string>(StringComparer.Ordinal);

        foreach (var entry in raw.Fields)
        {
            var name = Required(entry.Name);
            if (name is null)
            {
                errors.Add(new TemplateError(
                    TemplateErrorCodes.MalformedField,
                    $"a 'fields' entry declares no 'name', so no body slot could reach it: {entry.Description}"));
                continue;
            }

            if (!seen.Add(name))
            {
                errors.Add(new TemplateError(
                    TemplateErrorCodes.DuplicateFieldName,
                    $"two fields are named '{name}'; a body slot naming it would be ambiguous"));
                continue;
            }

            if (!TryReadType(entry.Type, out var type))
            {
                errors.Add(new TemplateError(
                    TemplateErrorCodes.UnknownFieldType,
                    $"field '{name}' declares type '{entry.Type ?? "(none)"}', which {TemplateContract.SchemaVersion} "
                    + "does not name; the types are text, list and mentions"));
                continue;
            }

            fields.Add(new TemplateField(
                name,
                type,
                string.Equals(entry.Required, "true", StringComparison.OrdinalIgnoreCase),
                Required(entry.Hint),
                ReadMin(entry, name, type, errors)));
        }

        return fields;
    }

    /// <summary>
    /// The declared minimum item count — validated as well-formed, and NOT compared against anything.
    /// </summary>
    /// <remarks>
    /// A minimum is a constraint on values, and the values arrive in the form engine (F4). Phase 1
    /// carries the number so a later gate can read it; nothing counts items against it here, and this
    /// must not be read as though it did.
    /// </remarks>
    private static int? ReadMin(RawTemplateField entry, string name, TemplateFieldType type, List<TemplateError> errors)
    {
        if (entry.Min is null)
        {
            return null;
        }

        var min = Integer(entry.Min);
        if (min is not > 0)
        {
            errors.Add(new TemplateError(
                TemplateErrorCodes.InvalidMin,
                $"field '{name}' declares min '{entry.Min}'; a minimum item count is a positive integer"));
            return null;
        }

        if (type != TemplateFieldType.List)
        {
            errors.Add(new TemplateError(
                TemplateErrorCodes.InvalidMin,
                $"field '{name}' is type {type.ToString().ToLowerInvariant()} and declares 'min'; a minimum "
                + "item count only means something for a list"));
            return null;
        }

        return min;
    }

    private static bool TryReadType(string? text, out TemplateFieldType type)
    {
        switch (text)
        {
            case "text":
                type = TemplateFieldType.Text;
                return true;
            case "list":
                type = TemplateFieldType.List;
                return true;
            case "mentions":
                type = TemplateFieldType.Mentions;
                return true;
            default:
                type = TemplateFieldType.Text;
                return false;
        }
    }

    /// <summary>Every body slot must name a declared field — B7's "bad slot reference".</summary>
    private static void CheckSlots(string body, IReadOnlyList<TemplateField> fields, List<TemplateError> errors)
    {
        var declared = fields.Select(f => f.Name).ToHashSet(StringComparer.Ordinal);

        foreach (Match match in SlotPattern().Matches(body))
        {
            var token = match.Groups[1].Value.Trim();
            if (token == ".")
            {
                continue;
            }

            var name = token.TrimStart('#', '/');
            if (name.Length > 0 && declared.Contains(name))
            {
                continue;
            }

            errors.Add(new TemplateError(
                TemplateErrorCodes.UnresolvedSlot,
                $"the body has a slot '{{{{{token}}}}}' naming no declared field"));
        }
    }

    [GeneratedRegex(@"\{\{(.*?)\}\}", RegexOptions.Singleline)]
    private static partial Regex SlotPattern();
}
