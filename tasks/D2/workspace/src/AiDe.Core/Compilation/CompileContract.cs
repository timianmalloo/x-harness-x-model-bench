using System.Text;

namespace AiDe.Core.PromptCompilation;

/// <summary>
/// The versioned pair the agentic rung calls (ADR-0033 rule 1): <c>compile-prompt/1</c> in,
/// <c>compile-output/1</c> out — the contract's constants, its allow-list and the
/// two host-embedded texts. <b>Shipped inert in this slice</b>: no model call exists here (the
/// agentic rung is CV-3's, behind PD-5 and the eval gate); the validator and the assembler are
/// tested red-first over authored fixtures so the rung has a typed boundary to call.
/// </summary>
/// <remarks>
/// <para><b>The header and the template are host-compiled bytes</b> — never read from the workspace
/// or <c>.claude/</c> (§A8.3; P-D3's falsifier: a workspace file named like the template changes no
/// byte). They are string constants — the ladder's lower rung (host-compiled bytes need no resource
/// pipeline) and the shape a <c>const</c> keeps deterministic; ADR-0033's "embedded resources" named
/// the property (host-embedded, never read from disk), which a constant satisfies. <c>simplify:</c>
/// ceiling — a template over ~200 lines, or a second family's profile shipped as text, moves the
/// texts to <c>Compilation/Resources/</c> under an <c>EmbeddedResource</c> glob;
/// <see cref="CompilePromptAssembler.PromptSha"/> is unchanged as long as the bytes are.</para>
///
/// <para><b>X-3 (the Shell-lane seam slice): the glob landed, the move did not.</b> The csproj now
/// carries <c>&lt;EmbeddedResource Include="Compilation\Resources\*" /&gt;</c>, so a future profile
/// dropped there needs no build-file edit. <see cref="HostHeader"/> and <see cref="Template"/> are
/// ~15 lines together today — under this remark's own ceiling and under the item's 20-line floor —
/// and no file exists yet under <c>Compilation/Resources/</c>, so moving them now would be motion
/// with no ceiling crossed. Left as this constant pair; move when either trigger fires.</para>
/// </remarks>
public static class CompileContract
{
    /// <summary>The prompt contract's version — <c>called.contract_version</c>; names the pair.</summary>
    public const string Version = "compile-prompt/1";

    /// <summary>The output contract the model must answer with.</summary>
    public const string OutputContract = "compile-output/1";

    /// <summary>A proposal's value bound (§A8.3): ≤ 2000 chars, no control characters.</summary>
    public const int MaxValueChars = 2000;

    /// <summary>The <c>notes</c> bound: ≤ 500 chars, shown as provenance, never applied.</summary>
    public const int MaxNotesChars = 500;

    /// <summary>The allow-list (v1): the three structure lines, and only the ones the prompt named as open. Case-sensitive.</summary>
    public static readonly IReadOnlyList<string> AllowList = DecorationNames.StructureLines;

    /// <summary>
    /// The fixed host header — <b>the prompt's first bytes, always</b>: a prompt whose first bytes
    /// are <c>/…</c> is executed by the CLI as a local command (adapter 0.75.1 <c>acp-agent.js:6035</c>),
    /// so the compile prompt never begins with operator text.
    /// </summary>
    public const string HostHeader =
        "AI-DE compile step (compile-prompt/1). You are the compile stage of a prompt composer.\n"
        + "Read the fenced source text below and propose values for the OPEN structure lines only,\n"
        + "answering with exactly one compile-output/1 JSON object and nothing else. You may not\n"
        + "contradict the mechanical facts, propose a lease, a tier, a task class, a budget or any\n"
        + "name outside the open lines, and you have no tools: do not read, write, or run anything.\n";

    /// <summary>The <c>compile-prompt/1</c> template — the blocks in order, each named; <c>{{…}}</c> slots the assembler fills.</summary>
    public const string Template =
        "## source_text\n\n{{source_text}}\n\n"
        + "## mechanical_facts\n\n{{mechanical_facts}}\n\n"
        + "## open_lines\n\n{{open_lines}}\n\n"
        + "## family_profile\n\n{{family_profile}}\n\n"
        + "## history_window\n\n{{history_window}}\n\n"
        + "## constitution\n\n{{constitution}}\n\n"
        + "## output_contract\n\n"
        + "Answer with one JSON object: {\"contract\": \"compile-output/1\", \"decorations\": [{\"name\": \"<an open line>\", "
        + "\"value\": \"<a string, at most 2000 characters, no control characters>\", \"confidence\": <0.0-1.0>, "
        + "\"grounded_in\": [{\"input\": \"source_text\", \"span\": [start, end]}]}], \"notes\": \"<at most 500 characters>\"}\n";

    /// <summary>The header's and the template's bytes, as hashed and as sent.</summary>
    public static ReadOnlySpan<byte> TemplateBytes => Encoding.UTF8.GetBytes(HostHeader + Template);
}
