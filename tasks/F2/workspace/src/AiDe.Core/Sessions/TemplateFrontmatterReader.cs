using System.Globalization;
using System.Text;
using YamlDotNet.Core;
using YamlDotNet.Core.Events;
using YamlDotNet.RepresentationModel;

namespace AiDe.Core.Sessions;

/// <summary>One <c>fields[]</c> entry as it was written, before the schema gives it a type.</summary>
/// <param name="Name">The declared name, or null when the entry declared none.</param>
/// <param name="Type">The declared type, verbatim. The loader decides whether it is one.</param>
/// <param name="Required">The declared flag, verbatim.</param>
/// <param name="Hint">The declared hint.</param>
/// <param name="Min">The declared minimum, verbatim. The loader decides whether it is a number.</param>
/// <param name="Description">A short rendering of the entry, for an error message about a malformed one.</param>
internal sealed record RawTemplateField(
    string? Name,
    string? Type,
    string? Required,
    string? Hint,
    string? Min,
    string Description);

/// <summary>A template's frontmatter as text — every value a string, so the SCHEMA picks every type.</summary>
/// <param name="Fields">The declared fields, or null when <c>fields</c> was absent.</param>
/// <param name="FieldsMalformed">Whether <c>fields</c> was present but not a sequence.</param>
/// <param name="Unknown">Every key this schema version does not name, preserved.</param>
internal sealed record RawTemplate(
    string? Id,
    string? Version,
    string? Intent,
    string? Audience,
    string? WhenToUse,
    string? Why,
    string? TierDefault,
    IReadOnlyList<RawTemplateField>? Fields,
    bool FieldsMalformed,
    IReadOnlyDictionary<string, string> Unknown);

/// <summary>
/// Reads a <c>template-schema/1</c> frontmatter block into text, and is the ONLY file that knows YAML.
/// </summary>
/// <remarks>
/// <para><b>An installed YAML dependency, and the only one in the repository (Ruling 35).</b> §B3.1's
/// frontmatter uses multi-line plain scalars and flow mappings inside a block sequence — which is
/// word-for-word the upgrade trigger both existing subset readers record for themselves
/// (<c>KnowledgeFrontmatter.cs</c>: "a consumer needs nested or multi-line values";
/// <c>BoundedContextMap.cs</c>: "a real map needs anchors, nested maps or multi-line scalars"). A
/// third hand-rolled reader is refused on the grounds <c>KnowledgeFrontmatter.cs</c> already records:
/// two copies of a format parser is two things to drift. Migrating those two onto this dependency is
/// a recorded next step, not this slice.</para>
///
/// <para><b>The document never chooses a CLR type.</b> Two mechanisms, and the first makes the second
/// unnecessary rather than merely unlikely. Every node is scanned for an EXPLICIT TAG before anything
/// is built, and a tagged node is refused outright — verified against YamlDotNet 18.1.0, whose parser
/// reports <c>Tag.IsEmpty</c> for an untagged node and the tag's value for <c>!!str</c> and for an
/// application tag. Then the block is read through the representation model into
/// <see cref="RawTemplate"/>, where every value is a string; <see cref="TemplateLoader"/> converts
/// each one according to the schema. There is no deserializer to configure, so no later setting can
/// turn a tag into a type.</para>
///
/// <para><b>The dependency stops here.</b> Nothing else in <c>src/</c> — including the loader that
/// calls this — references YamlDotNet, and a test asserts exactly that.</para>
/// </remarks>
internal static class TemplateFrontmatterReader
{
    /// <summary>The frontmatter fence, and the line that closes it.</summary>
    private const string Fence = "---";

    /// <summary>Keys <c>template-schema/1</c> names. Everything else is preserved as unknown.</summary>
    private static readonly HashSet<string> KnownKeys = new(StringComparer.Ordinal)
    {
        "id", "version", "intent", "audience", "when_to_use", "why", "tier_default", "fields",
    };

    /// <summary>Splits a template file into its frontmatter block and its body.</summary>
    /// <returns>False when there is no frontmatter block, which is a load failure, not an empty one.</returns>
    internal static bool TrySplit(string text, out string frontmatter, out string body)
    {
        frontmatter = string.Empty;
        body = string.Empty;

        var lines = text.ReplaceLineEndings("\n").Split('\n');
        if (lines.Length == 0 || lines[0].TrimEnd() != Fence)
        {
            return false;
        }

        for (var i = 1; i < lines.Length; i++)
        {
            if (lines[i].TrimEnd() != Fence)
            {
                continue;
            }

            frontmatter = string.Join('\n', lines[1..i]);
            body = NormaliseBody(string.Join('\n', lines[(i + 1)..]));
            return true;
        }

        return false;
    }

    /// <summary>
    /// The body as it will compile: line feeds only, and exactly one trailing newline.
    /// </summary>
    /// <remarks>
    /// Determinism starts here. Two files differing only in trailing blank lines or in line endings
    /// are the same template, and a compile that reproduced the difference would break the
    /// byte-identical guarantee for a reason that has nothing to do with the values.
    /// </remarks>
    private static string NormaliseBody(string body)
    {
        var trimmed = body.TrimEnd('\n', '\r', ' ', '\t');
        return trimmed.Length == 0 ? string.Empty : trimmed + "\n";
    }

    /// <summary>
    /// Reads the frontmatter block, or records why it could not be read.
    /// </summary>
    /// <param name="frontmatter">The YAML between the fences.</param>
    /// <param name="errors">Appended to; never replaced.</param>
    /// <returns>The frontmatter as text values, or null when nothing usable was read.</returns>
    internal static RawTemplate? Read(string frontmatter, List<TemplateError> errors)
    {
        if (!NoExplicitTags(frontmatter, errors))
        {
            return null;
        }

        YamlMappingNode mapping;
        try
        {
            var stream = new YamlStream();
            stream.Load(new StringReader(frontmatter));

            if (stream.Documents.Count == 0)
            {
                errors.Add(new TemplateError(
                    TemplateErrorCodes.MissingFrontmatter,
                    "the frontmatter block is empty, so the template declares nothing about itself"));
                return null;
            }

            if (stream.Documents[0].RootNode is not YamlMappingNode root)
            {
                errors.Add(new TemplateError(
                    TemplateErrorCodes.MalformedFrontmatter,
                    "the frontmatter is not a mapping of keys to values"));
                return null;
            }

            mapping = root;
        }
        catch (YamlException exception)
        {
            errors.Add(new TemplateError(
                TemplateErrorCodes.MalformedFrontmatter,
                $"the frontmatter is not well-formed YAML: {exception.Message}"));
            return null;
        }

        var fieldsNode = Node(mapping, "fields");
        var malformed = fieldsNode is not null and not YamlSequenceNode;

        return new RawTemplate(
            Scalar(mapping, "id"),
            Scalar(mapping, "version"),
            Scalar(mapping, "intent"),
            Scalar(mapping, "audience"),
            Scalar(mapping, "when_to_use"),
            Scalar(mapping, "why"),
            Scalar(mapping, "tier_default"),
            fieldsNode is YamlSequenceNode sequence ? ReadFields(sequence) : null,
            malformed,
            UnknownKeys(mapping));
    }

    private static IReadOnlyList<RawTemplateField> ReadFields(YamlSequenceNode sequence)
        => sequence
            .Select(item => item is YamlMappingNode entry
                ? new RawTemplateField(
                    Scalar(entry, "name"),
                    Scalar(entry, "type"),
                    Scalar(entry, "required"),
                    Scalar(entry, "hint"),
                    Scalar(entry, "min"),
                    Describe(entry))
                : new RawTemplateField(null, null, null, null, null, Describe(item)))
            .ToList();

    /// <summary>
    /// Refuses a frontmatter block in which any node carries an explicit tag.
    /// </summary>
    /// <remarks>
    /// This runs on the raw event stream, BEFORE a node exists, so the refusal cannot be reached
    /// around. It is what makes "no tag-driven type resolution" a property of the loader rather than
    /// a property of how a serializer happens to be configured today.
    /// </remarks>
    private static bool NoExplicitTags(string frontmatter, List<TemplateError> errors)
    {
        try
        {
            var parser = new Parser(new StringReader(frontmatter));
            while (parser.MoveNext())
            {
                if (parser.Current is not NodeEvent node || node.Tag.IsEmpty)
                {
                    continue;
                }

                errors.Add(new TemplateError(
                    TemplateErrorCodes.ExplicitYamlTag,
                    $"the frontmatter carries the explicit YAML tag '{TagText(node.Tag)}'; a template "
                    + "file does not choose a type, the schema does"));
                return false;
            }

            return true;
        }
        catch (YamlException exception)
        {
            errors.Add(new TemplateError(
                TemplateErrorCodes.MalformedFrontmatter,
                $"the frontmatter is not well-formed YAML: {exception.Message}"));
            return false;
        }
    }

    private static string TagText(TagName tag) => tag.IsNonSpecific ? "!" : tag.Value;

    private static string? Scalar(YamlMappingNode mapping, string key)
        => mapping.Children.TryGetValue(new YamlScalarNode(key), out var node) && node is YamlScalarNode scalar
            ? scalar.Value
            : null;

    private static YamlNode? Node(YamlMappingNode mapping, string key)
        => mapping.Children.TryGetValue(new YamlScalarNode(key), out var node) ? node : null;

    /// <summary>
    /// Every key the schema does not name, in declaration order, rendered back to text.
    /// </summary>
    /// <remarks>
    /// Rendered to text rather than handed over as a YAML node on purpose: the dependency is scoped
    /// to this file, and a preserved unknown that leaked a <c>YamlNode</c> into the public model
    /// would take the package with it.
    /// </remarks>
    private static IReadOnlyDictionary<string, string> UnknownKeys(YamlMappingNode mapping)
    {
        var unknown = new Dictionary<string, string>(StringComparer.Ordinal);

        foreach (var (key, value) in mapping.Children)
        {
            if (key is not YamlScalarNode { Value: { } name } || KnownKeys.Contains(name))
            {
                continue;
            }

            unknown[name] = value is YamlScalarNode scalar ? scalar.Value ?? string.Empty : Render(value);
        }

        return unknown;
    }

    /// <summary>A non-scalar node written back out, so an unknown structure survives as text.</summary>
    private static string Render(YamlNode node)
    {
        var stream = new YamlStream(new YamlDocument(node));
        var writer = new StringWriter(CultureInfo.InvariantCulture);
        stream.Save(writer, assignAnchors: false);

        var text = writer.ToString().ReplaceLineEndings("\n");
        var end = text.IndexOf("...", StringComparison.Ordinal);
        return (end < 0 ? text : text[..end]).Trim();
    }

    /// <summary>A short rendering of a node, for an error message about a malformed field entry.</summary>
    private static string Describe(YamlNode node)
    {
        var text = new StringBuilder();
        foreach (var child in node.AllNodes)
        {
            if (child is YamlScalarNode { Value: { } value } && text.Length < 60)
            {
                text.Append(value).Append(' ');
            }
        }

        return text.ToString().Trim();
    }
}
