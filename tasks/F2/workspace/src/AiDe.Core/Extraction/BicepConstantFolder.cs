using System.Text;
using System.Text.RegularExpressions;

namespace AiDe.Core.Extraction;

/// <summary>
/// Folds a Bicep expression to the string Azure would deploy — or refuses.
/// </summary>
/// <remarks>
/// <para><b>A constant folder, not an interpreter, and the numbers put the line there.</b> MEASURED
/// over every <c>.bicep</c> file in TheTerrace and this repository — 2 files, 760 lines, 27 resource
/// declarations — the names are: 8 quoted string literals, 3 string interpolations, 10 bare
/// references to a <c>var</c> or a <c>param</c>, and 6 <c>guid(...)</c> calls. Zero loops. So the
/// whole of the recoverable ground is <i>substitute a declared default and concatenate</i>; the
/// remainder is <c>guid()</c>, which is not recoverable at any tier because its inputs are resource
/// IDs that do not exist until a deployment names a subscription.</para>
///
/// <para><b>The reason it was worth building at all is a defect, not coverage.</b> The reader's test
/// for "this name is a literal" was <i>contains no <c>$</c> and no <c>(</c></i>. A bare identifier
/// passes that test, so <c>name: workspaceName</c> was asserted as
/// <c>resource_name = "workspaceName"</c> — the reference, not the value. MEASURED on TheTerrace,
/// <b>10 of 27</b> resource names in the graph were identifier text, and none of them was disclosed,
/// because they never took the expression branch. The alternative to folding was never honest
/// silence; it was ten names nobody could find in the portal.</para>
///
/// <para><b>Default-deny, everywhere.</b> An unrecognised function, an escape sequence, a ternary, a
/// parameter with no default, an unbalanced anything — every one of them fails the fold and the name
/// stays disclosed. "Close enough" is the wrong answer for a resource name specifically: it is what
/// a person types into a portal search box, and a name that is wrong by one character is
/// indistinguishable from a right one until it costs somebody an afternoon.</para>
///
/// <para><c>simplify: constant folding over declared defaults rather than expression evaluation;
/// ceiling is string interpolation and four pure string functions over values already known;
/// upgrade trigger = a repository is measured where names need <c>format</c>, arithmetic,
/// conditionals, or array indexing.</c></para>
/// </remarks>
internal sealed partial class BicepConstantFolder
{
    /// <summary>
    /// How deep a fold may recurse before it gives up.
    /// </summary>
    /// <remarks>
    /// The termination variant. Two variables that reference each other are not valid Bicep, and
    /// this reader never compiles anything — it meets whatever a repository contains, including a
    /// file halfway through an edit. Without a cap that file hangs the indexer rather than failing
    /// it. Sixteen is far past anything measured: the deepest chain in the corpus is
    /// <c>storageName → toLower → interpolation → namePrefix</c>, which is four.
    /// </remarks>
    private const int MaxDepth = 16;

    /// <summary>Every <c>param</c> WITH a default, and every <c>var</c>, as unfolded text.</summary>
    /// <remarks>
    /// A <c>param</c> with no default is deliberately absent rather than present-and-empty. Its
    /// value does not exist until a deployment supplies one, so there is nothing to fold and no
    /// amount of context makes it knowable — <c>provider-vault.bicep</c>'s <c>webAppName</c> is the
    /// measured case, and it is the one this reader used to name a resource after.
    /// </remarks>
    private readonly Dictionary<string, string> _bindings;

    /// <summary>Whether the fold in progress used anything beyond plain literal characters.</summary>
    private bool _computed;

    private BicepConstantFolder(Dictionary<string, string> bindings) => _bindings = bindings;

    // A parameter's TYPE is `[^\s=]+` rather than `\w+` so `string[]` and a user-defined type both
    // parse. Only the default matters here; the declaration itself is recorded elsewhere.
    [GeneratedRegex(@"^\s*param\s+(?<name>\w+)\s+[^\s=]+\s*=\s*(?<value>.+?)\s*$")]
    private static partial Regex ParameterWithDefault();

    [GeneratedRegex(@"^\s*var\s+(?<name>\w+)\s*=\s*(?<value>.+?)\s*$")]
    private static partial Regex VariableDeclaration();

    [GeneratedRegex(@"^[A-Za-z_]\w*$")]
    private static partial Regex Identifier();

    /// <summary>
    /// The string functions that are folded, and no others.
    /// </summary>
    /// <remarks>
    /// <para>MEASURED uses in resource names across the corpus: <c>toLower</c> 1, <c>replace</c> 1,
    /// everything else 0. <c>toUpper</c> and <c>concat</c> are here because each is one expression
    /// with semantics identical to one already folded — <c>concat</c> over strings is what
    /// interpolation compiles to.</para>
    ///
    /// <para><b><c>format</c> is deliberately absent</b> even though it is the obvious next
    /// candidate: it needs a placeholder parser, and a mis-read <c>{0}</c> yields a wrong name
    /// rather than no name. Zero measured uses does not buy that risk. <b><c>uniqueString</c> and
    /// <c>guid</c> are absent permanently</b> — both are hashes whose exact algorithm is not part of
    /// any published contract, so a folded value would be a guess with a convincing shape, and
    /// <c>guid</c>'s arguments are resource IDs that need a subscription no file supplies.</para>
    /// </remarks>
    private static readonly Dictionary<string, Func<IReadOnlyList<string>, string?>> Functions =
        new(StringComparer.Ordinal)
        {
            ["toLower"] = a => a.Count == 1 && IsAscii(a[0]) ? a[0].ToLowerInvariant() : null,
            ["toUpper"] = a => a.Count == 1 && IsAscii(a[0]) ? a[0].ToUpperInvariant() : null,
            ["concat"] = a => a.Count >= 1 ? string.Concat(a) : null,

            // An empty search string is refused rather than passed to string.Replace, which throws
            // on it. Bicep accepts the call; what it returns is not worth guessing at.
            ["replace"] = a => a.Count == 3 && a[1].Length > 0
                ? a[0].Replace(a[1], a[2], StringComparison.Ordinal)
                : null,
        };

    /// <summary>
    /// Reads the declarations a template makes about itself.
    /// </summary>
    /// <param name="text">
    /// Template source with comments already blanked. Reading raw text would take a
    /// commented-out <c>var</c> as a binding, which is the failure every line-oriented reader in
    /// this codebase has been caught by at least once.
    /// </param>
    public static BicepConstantFolder From(string text)
    {
        ArgumentNullException.ThrowIfNull(text);

        var bindings = new Dictionary<string, string>(StringComparer.Ordinal);
        var lines = text.Split('\n');

        // Line by line, because a parameter's DECORATORS decide whether its default may be read at
        // all, and a decorator is a preceding line.
        for (var i = 0; i < lines.Length; i++)
        {
            var parameter = ParameterWithDefault().Match(lines[i]);

            if (parameter.Success)
            {
                // A `@secure()` parameter's value is NEVER read. It may legally carry a default, and
                // folding one into a resource name would carry it into the store through the graph
                // instead of through the parameter — which is the same store. This extractor's
                // strongest documented guarantee is that no code path here reads a secret value;
                // adding an evaluator without this line would have quietly made that false.
                if (BicepExtractor.IsSecure(lines, i)) continue;

                // First declaration wins. Bicep forbids duplicate symbols, so a second one means the
                // file is invalid — and picking arbitrarily between two candidate values for a NAME
                // is the one thing this class exists not to do.
                bindings.TryAdd(parameter.Groups["name"].Value, parameter.Groups["value"].Value);
                continue;
            }

            var variable = VariableDeclaration().Match(lines[i]);

            if (variable.Success)
            {
                bindings.TryAdd(variable.Groups["name"].Value, variable.Groups["value"].Value);
            }
        }

        return new BicepConstantFolder(bindings);
    }

    /// <summary>
    /// The value this expression has for the template's declared defaults, when that is knowable.
    /// </summary>
    /// <param name="expression">The expression as written, e.g. <c>'${namePrefix}-log'</c>.</param>
    /// <param name="value">The exact string Azure would deploy, or null.</param>
    /// <param name="computed">
    /// False when the expression was a plain quoted literal — what deploys, unconditionally. True
    /// when a binding, an interpolation or a function was involved, which makes the value a function
    /// of DEFAULTS a deployment can override. The caller uses it to choose Verified over Inferred:
    /// a literal was read, a fold was computed, and the graph should not call those the same thing.
    /// </param>
    public bool TryFold(string expression, out string? value, out bool computed)
    {
        ArgumentNullException.ThrowIfNull(expression);

        _computed = false;
        var folded = Fold(expression, 0, out value);
        computed = _computed;

        return folded;
    }

    private bool Fold(string expression, int depth, out string? value)
    {
        value = null;

        if (depth > MaxDepth) return false;

        var text = expression.Trim();
        if (text.Length == 0) return false;

        // A reference to a param or a var. Unbound means either "no default was declared" or "this
        // symbol is not in this file" — both unknowable here, and both used to become a name.
        if (Identifier().IsMatch(text))
        {
            _computed = true;
            return _bindings.TryGetValue(text, out var bound) && Fold(bound, depth + 1, out value);
        }

        if (text[0] == '\'') return FoldString(text, depth, out value);

        // A call, and only if the WHOLE expression is one. `resourceGroup().location` opens a paren
        // and does not end with one, so it never reaches the function table; `a ? f(1) : g(2)` ends
        // with one but its head is not an identifier.
        var open = text.IndexOf('(', StringComparison.Ordinal);
        if (open <= 0 || text[^1] != ')') return false;

        var name = text[..open].Trim();
        if (!Identifier().IsMatch(name) || !Functions.TryGetValue(name, out var function)) return false;

        var arguments = SplitArguments(text[(open + 1)..^1]);
        if (arguments is null) return false;

        var folded = new List<string>(arguments.Count);

        foreach (var argument in arguments)
        {
            if (!Fold(argument, depth + 1, out var each)) return false;
            folded.Add(each!);
        }

        _computed = true;
        value = function(folded);

        return value is not null;
    }

    /// <summary>A single-quoted string, with its interpolation holes folded in place.</summary>
    /// <remarks>
    /// The whole expression must be one string. `'a' == 'b'` starts with a quote and is not a string
    /// literal, and folding its first half would be a name built from half a comparison.
    /// </remarks>
    private bool FoldString(string text, int depth, out string? value)
    {
        value = null;

        var builder = new StringBuilder();
        var i = 1;

        while (i < text.Length)
        {
            var c = text[i];

            // Bicep's escapes are \\ \' \n \r \t \$ and \u{...}. The whole class is refused rather
            // than half-implemented: zero uses across the corpus, and getting one wrong produces a
            // name that is wrong by a single character — the failure mode nobody catches by reading.
            if (c == '\\') return false;

            if (c == '\'')
            {
                if (i != text.Length - 1) return false;

                value = builder.ToString();
                return true;
            }

            if (c == '$' && i + 1 < text.Length && text[i + 1] == '{')
            {
                var close = ClosingBrace(text, i + 1);
                if (close < 0) return false;

                if (!Fold(text[(i + 2)..close], depth + 1, out var inner)) return false;

                _computed = true;
                builder.Append(inner);
                i = close + 1;
                continue;
            }

            builder.Append(c);
            i++;
        }

        // Unterminated. A truncated or mid-edit file, and not something to complete on its behalf.
        return false;
    }

    /// <summary>The <c>}</c> that closes the <c>{</c> at <paramref name="open"/>, or -1.</summary>
    private static int ClosingBrace(string text, int open)
    {
        var depth = 0;
        var inString = false;

        for (var i = open; i < text.Length; i++)
        {
            var c = text[i];

            if (c == '\\') return -1;

            if (c == '\'')
            {
                inString = !inString;
                continue;
            }

            if (inString) continue;

            if (c == '{') depth++;
            else if (c == '}' && --depth == 0) return i;
        }

        return -1;
    }

    /// <summary>An argument list split on its top-level commas, or null if it does not balance.</summary>
    private static IReadOnlyList<string>? SplitArguments(string text)
    {
        var arguments = new List<string>();
        var start = 0;
        var depth = 0;
        var inString = false;

        for (var i = 0; i < text.Length; i++)
        {
            var c = text[i];

            if (c == '\\') return null;

            if (c == '\'')
            {
                inString = !inString;
                continue;
            }

            if (inString) continue;

            switch (c)
            {
                case '(' or '[' or '{':
                    depth++;
                    break;
                case ')' or ']' or '}':
                    if (--depth < 0) return null;
                    break;
                case ',' when depth == 0:
                    arguments.Add(text[start..i]);
                    start = i + 1;
                    break;
            }
        }

        if (depth != 0 || inString) return null;

        arguments.Add(text[start..]);

        return arguments;
    }

    /// <summary>
    /// Whether case folding this value is unambiguous.
    /// </summary>
    /// <remarks>
    /// ARM's <c>toLower</c> is not .NET's, and outside ASCII they disagree — the Turkish dotless i is
    /// the standard example. Azure resource names are ASCII by its own naming rules, so this refuses
    /// a case nobody has and keeps the guarantee absolute rather than usually-true.
    /// </remarks>
    private static bool IsAscii(string value) => System.Text.Ascii.IsValid(value);
}
