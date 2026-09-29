using AiDe.Core;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// One caller's outgoing calls, in call order — the feed a UML sequence diagram draws.
/// </summary>
/// <remarks>
/// <para><b>Why <c>calls</c> could not serve this.</b> Design asked for ordered call data (§4k) and
/// built <c>SequenceModel</c> against a stub. The `calls` edges are deduplicated to one row per
/// <c>(caller, callee)</c> pair — MEASURED on TheTerrace, 870 pairs and 870 distinct
/// <c>(pair, location)</c>, so <b>zero</b> pairs carry a second call site. That is right for a graph,
/// where one relationship written seven times is one arrow, and it destroys an interaction:
/// <c>A→B, A→C, A→B</c> collapses to two messages and the repeat is gone. A diagram that silently
/// drops a repeated call is confidently incomplete, which is worse than an empty one.</para>
///
/// <para><b>No ordinal column was added.</b> Every assertion already carries <c>source_location</c>,
/// and a call sequence has exactly one correct order — the order it is written in.</para>
///
/// <para><b>Type-level, deliberately.</b> The caller and callee are types; the member is the message
/// name. A lifeline-per-method diagram needs method-level callers, which the C# reader does not
/// emit. A true smaller thing beats a plausible larger one.</para>
/// </remarks>
public sealed class InteractionTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-interaction", Guid.NewGuid().ToString("N"));

    public InteractionTests() => Directory.CreateDirectory(Path.Combine(_root, "src"));

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { }
    }

    private async Task<WorkspaceCore> IndexedAsync(string body)
    {
        File.WriteAllText(Path.Combine(_root, "src", "Shop.csproj"), """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>
            </Project>
            """);

        File.WriteAllText(Path.Combine(_root, "src", "Shop.cs"), $$"""
            namespace Shop;

            public class Customer { public void Save() { } public void Load() { } }
            public class Audit { public void Write() { } }

            public class Order
            {
                private readonly Customer _customer = new();
                private readonly Audit _audit = new();

                public void Run()
                {
            {{body}}
                }
            }
            """);

        var core = WorkspaceCore.Open(
            "ws", _root, Path.Combine(_root, ".data"), WorkspaceExtractors.Default());

        await core.IndexCSharpAsync("rev-1");
        return core;
    }

    [Fact]
    public async Task ARepeatedCallStaysARepeatedMessage()
    {
        // THE REASON THIS EXISTS. `calls` would collapse the two Customer calls into one edge and
        // the diagram would show two messages where the code has three.
        using var core = await IndexedAsync("""
                    _customer.Save();
                    _audit.Write();
                    _customer.Load();
            """);

        var messages = core.Projections.Interaction("Shop.Order", 50).Messages;

        Assert.Equal(3, messages.Count);
        Assert.Equal(["Save", "Write", "Load"], messages.Select(m => m.Member));
    }

    [Fact]
    public async Task MessagesComeBackInTheOrderTheyAreWritten()
    {
        // Ordered by source position, and ordered NUMERICALLY — sorted as text, line 10 would come
        // before line 9 and the sequence would be quietly wrong on any method longer than nine lines.
        var body = string.Join("\n", Enumerable.Range(0, 12).Select(
            i => i % 2 == 0 ? "            _customer.Save();" : "            _audit.Write();"));

        using var core = await IndexedAsync(body);

        var messages = core.Projections.Interaction("Shop.Order", 50).Messages;

        Assert.Equal(12, messages.Count);
        Assert.Equal(Enumerable.Range(1, 12), messages.Select(m => m.Ordinal));
        Assert.Equal("Save", messages[0].Member);
        Assert.Equal("Write", messages[11].Member);
    }

    [Fact]
    public async Task EachMessageNamesTheMemberThatWasCalled()
    {
        // `Order -> Customer` is an arrow; `Order -> Customer.Save()` is the thing the diagram was
        // opened to find out. The member is read from the symbol the walk already had in hand.
        using var core = await IndexedAsync("            _customer.Save();");

        var message = Assert.Single(core.Projections.Interaction("Shop.Order", 50).Messages);

        Assert.Equal("Shop.Order", message.From);
        Assert.Equal("Shop.Customer", message.To);
        Assert.Equal("Save", message.Member);
        Assert.False(string.IsNullOrEmpty(message.Location), "a message with no call site cannot be navigated to");
    }

    [Fact]
    public async Task ACallerWithNoOutgoingCallsGetsAnEmptyInteractionRatherThanAnError()
    {
        // The surface shows its empty state. An exception here would make "this type calls nothing"
        // indistinguishable from "the query is broken".
        using var core = await IndexedAsync("            var x = 1;");

        var result = core.Projections.Interaction("Shop.Customer", 50);

        Assert.Empty(result.Messages);
        Assert.False(result.Truncated);
    }

    [Fact]
    public async Task TheMessageCapIsEnforcedAndSaidOutLoud()
    {
        // A declared limit that cannot fire is the defect it was written to prevent (DC-016), and a
        // sequence that stops early without saying so is confidently incomplete.
        var body = string.Join("\n", Enumerable.Repeat("            _customer.Save();", 10));

        using var core = await IndexedAsync(body);

        var result = core.Projections.Interaction("Shop.Order", 4);

        Assert.Equal(4, result.Messages.Count);
        Assert.True(result.Truncated, "the cap fired and the result did not say so");
    }

    [Fact]
    public async Task TheGraphIsNotGivenAnEdgePerCallSite()
    {
        // calls_at is an ATTRIBUTE. Ten call sites between two types must stay ONE drawn edge, or
        // the graph pays for the sequence diagram — and the payload is the binding constraint on
        // this product (INV-0003).
        var body = string.Join("\n", Enumerable.Repeat("            _customer.Save();", 10));

        using var core = await IndexedAsync(body);

        Assert.Contains("calls_at", EvidencePredicates.Attributes);

        var graph = core.Projections.Graph(new GraphQuery(500));

        Assert.DoesNotContain(graph.Edges, e => e.Predicate == "calls_at");
    }

    [Fact]
    public async Task ASelfCallIsNotAMessageToAnotherLifeline()
    {
        // The walk excludes calls a type makes to itself, and that exclusion must survive: a
        // self-message drawn as a call to another participant invents a lifeline.
        using var core = await IndexedAsync("            Helper();");

        var messages = core.Projections.Interaction("Shop.Order", 50).Messages;

        Assert.DoesNotContain(messages, m => m.To == "Shop.Order");
    }
}
