namespace AiDe.Core.Sessions;

/// <summary>
/// The pinned frontmatter contract every prompt template is read under (Addendum B §B7).
/// </summary>
/// <remarks>
/// <para><b>Pinned from birth, not once it settles.</b> The validator ships in Phase 1 and enforces a
/// shape; a contract enforced in code with no documented shape is a shape asserted from code. The
/// registry entry is <c>docs/architecture/pinned-contracts.md</c> (Ruling 29), which names this
/// version, its home document, and its evolution rule.</para>
///
/// <para><b>Evolution is additive within schema 1.</b> An unknown frontmatter field is PRESERVED —
/// see <see cref="PromptTemplate.UnknownFrontmatter"/> — never rejected, so a template written for a
/// later reader still loads here with the part this reader understands. A breaking change means
/// <c>template-schema/2</c> loading side by side, the discipline <c>weave/1</c> and
/// <c>loomkeeper/1</c> already follow.</para>
///
/// <para><b><c>min</c> and <c>tier_default</c> are schema-1 CONSTRAINTS, not preserved unknowns.</b>
/// Both appear in B3.1's own specimen, which is the document the schema was pinned from; treating
/// them as unknown would mean the schema's own example carries fields the schema has never heard of,
/// and <c>min</c> would be silently dropped from a template that declared it. They are typed members
/// — <see cref="TemplateField.Min"/> and <see cref="PromptTemplate.TierDefault"/>.</para>
/// </remarks>
public static class TemplateContract
{
    /// <summary>The pinned contract id. A change here is a contract change, not a re-parse.</summary>
    public const string SchemaVersion = "template-schema/1";
}

/// <summary>The field types <c>template-schema/1</c> knows (B3.1).</summary>
public enum TemplateFieldType
{
    /// <summary>Free text — one value.</summary>
    Text,

    /// <summary>An ordered list of values, rendered through a body section.</summary>
    List,

    /// <summary>Mention chips — references to workspace things. A list of ids, to this contract.</summary>
    Mentions,
}

/// <summary>One typed field a template declares.</summary>
/// <param name="Name">The wire name. Body slots and recorded values both key on it.</param>
/// <param name="Type">Its declared <see cref="TemplateFieldType"/>.</param>
/// <param name="Required">Whether the form engine must block send without it (F4 gates it, not this).</param>
/// <param name="Hint">Inline guidance shown beside the field, or null.</param>
/// <param name="Min">
/// The declared minimum item count for a <see cref="TemplateFieldType.List"/> field.
/// <b>Carried and validated as well-formed here; compared against real values by the form engine
/// (F4).</b> Phase 1 does not count items against it, and this member must not be read as though it
/// did.
/// </param>
public sealed record TemplateField(string Name, TemplateFieldType Type, bool Required, string? Hint, int? Min);

/// <summary>A template that loaded — frontmatter under <see cref="TemplateContract.SchemaVersion"/>, plus its body.</summary>
/// <param name="Id">The catalog identity. Same-id templates from different sources resolve by precedence.</param>
/// <param name="Version">The template's own version, independent of the schema's.</param>
/// <param name="Intent">B4's intent — what the prompt is for.</param>
/// <param name="Audience">B4's audience — who reads the compiled prompt.</param>
/// <param name="WhenToUse">The picker tooltip headline. Load-blocking: a template without it does not load.</param>
/// <param name="Why">The tooltip detail. Load-blocking for the same reason.</param>
/// <param name="TierDefault">The ceremony tier the template suggests, or null. A suggestion, never a gate.</param>
/// <param name="Fields">The declared fields, in declaration order — which is also compile order.</param>
/// <param name="Body">The slot body, normalised to line feeds and ending in exactly one.</param>
/// <param name="UnknownFrontmatter">
/// Every frontmatter key this schema version does not name, in the order the file declared them.
/// Preserved rather than rejected, so an additive evolution is not a load failure here.
/// </param>
public sealed record PromptTemplate(
    string Id,
    int Version,
    string Intent,
    string Audience,
    string WhenToUse,
    string Why,
    string? TierDefault,
    IReadOnlyList<TemplateField> Fields,
    string Body,
    IReadOnlyDictionary<string, string> UnknownFrontmatter);

/// <summary>One reason a template did not load. The code is stable; the message is for a person.</summary>
/// <param name="Code">A <see cref="TemplateErrorCodes"/> value.</param>
/// <param name="Message">What is wrong, naming the field or slot it is about.</param>
public sealed record TemplateError(string Code, string Message);

/// <summary>Stable codes for every load refusal, so a catalog entry's error survives a reword.</summary>
public static class TemplateErrorCodes
{
    /// <summary>The file has no frontmatter block at all.</summary>
    public const string MissingFrontmatter = "TS-0001";

    /// <summary>The frontmatter block is not well-formed YAML.</summary>
    public const string MalformedFrontmatter = "TS-0002";

    /// <summary>A node carries an explicit YAML tag, which would let the document choose a type.</summary>
    public const string ExplicitYamlTag = "TS-0003";

    /// <summary>No <c>id</c>. There is nothing to key the catalog on.</summary>
    public const string MissingId = "TS-0004";

    /// <summary>No <c>when_to_use</c>, or a blank one. Load-blocking by B7 and Ruling 26(e).</summary>
    public const string MissingWhenToUse = "TS-0005";

    /// <summary>No <c>why</c>, or a blank one. Load-blocking for the same reason.</summary>
    public const string MissingWhy = "TS-0006";

    /// <summary>A <c>version</c> that is absent, unparseable, or below 1.</summary>
    public const string InvalidVersion = "TS-0007";

    /// <summary>A field <c>type</c> outside <see cref="TemplateFieldType"/>.</summary>
    public const string UnknownFieldType = "TS-0008";

    /// <summary>A malformed <c>fields</c> block — not a sequence, or an entry that is not a mapping.</summary>
    public const string MalformedField = "TS-0009";

    /// <summary>Two fields with one name, so a slot would be ambiguous.</summary>
    public const string DuplicateFieldName = "TS-0010";

    /// <summary>A body slot naming no declared field.</summary>
    public const string UnresolvedSlot = "TS-0011";

    /// <summary>A <c>min</c> that is not a positive integer, or is declared on a non-list field.</summary>
    public const string InvalidMin = "TS-0012";

    /// <summary>Two templates in ONE source claiming one id (B7).</summary>
    public const string DuplicateIdInSource = "TS-0013";

    /// <summary>An <c>intent</c> or <c>audience</c> that is absent or blank.</summary>
    public const string MissingIntentOrAudience = "TS-0014";
}

/// <summary>What one load attempt produced: a template, or the reasons there is none.</summary>
/// <param name="Template">The template, or null when it did not load.</param>
/// <param name="Errors">Every refusal at once — a caller fixing a file should see them all.</param>
/// <param name="DeclaredId">
/// The <c>id</c> the file claimed, even when the load failed on something else. A failed template is
/// listed under the id it meant to have; without this it could only be listed under its path, and a
/// broken override would not line up with the built-in it shadows.
/// </param>
public sealed record TemplateLoadResult(PromptTemplate? Template, IReadOnlyList<TemplateError> Errors, string? DeclaredId = null)
{
    /// <summary>Whether this is a template the catalog may offer.</summary>
    public bool Loaded => Template is not null && Errors.Count == 0;
}
