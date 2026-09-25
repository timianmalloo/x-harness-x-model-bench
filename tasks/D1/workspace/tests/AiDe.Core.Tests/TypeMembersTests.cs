using AiDe.Core;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// A type carries its own members, formatted for a UML compartment (ADR-0026 class-diagram-architecture, Phase 2).
/// </summary>
/// <remarks>
/// <para>The class diagram was member-less by construction because no extractor emitted members.
/// These pin what a compartment actually receives: the type's OWN members, in UML notation, without
/// the compiler's inventions, and with a truncated list saying it was truncated.</para>
///
/// <para><b>Members are attributes, not nodes.</b> `has_member` sits in
/// <see cref="EvidencePredicates.Attributes"/> beside `has_column` — <c>Id : int</c> is a property OF
/// a class, not a peer of it. Emitting it as a relation would have added roughly ten thousand nodes
/// to a real workspace's graph to serve a card layout.</para>
/// </remarks>
public sealed class TypeMembersTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-members", Guid.NewGuid().ToString("N"));

    public TypeMembersTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<EvidenceAssertion>> ExtractAsync(string code)
    {
        File.WriteAllText(Path.Combine(_dir, "Shop.csproj"), """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>
            </Project>
            """);

        File.WriteAllText(Path.Combine(_dir, "Types.cs"), code);

        var scope = CSharpScopeDiscovery.DiscoverAll(_dir, new CSharpProjectReader())
            .Single(s => s.ScopeId.StartsWith("csharp:", StringComparison.Ordinal));

        var result = await WorkspaceExtractors.Default().ExtractAsync(
            new ExtractionRequest(scope.ScopeId, scope.ProjectPath, "rev-1", 1), CancellationToken.None);

        return result.Assertions;
    }

    private static IReadOnlyList<string> MembersOf(IEnumerable<EvidenceAssertion> assertions, string type) =>
        [.. assertions
            .Where(a => a.Subject == type && a.Predicate == "has_member")
            .Select(a => a.Object)];

    [Fact]
    public async Task PropertiesMethodsAndFieldsArriveInUmlNotation()
    {
        var members = MembersOf(await ExtractAsync("""
            namespace Shop;

            public class Order
            {
                public int Id { get; set; }
                private string _note = "";
                public void Cancel() { }
                protected string Describe(int depth) => "";
            }
            """), "Shop.Order");

        Assert.Contains("+ Id : int", members);
        Assert.Contains("- _note : string", members);
        Assert.Contains("+ Cancel()", members);
        Assert.Contains("# Describe(int) : string", members);
    }

    [Fact]
    public async Task WhatTheCompilerWroteIsNotListed()
    {
        // A record's generated members — <Clone>$, EqualityContract, the copy constructor — are
        // artifacts of compilation. A compartment listing them describes the C# language rather than
        // the model, and the reader cannot tell which lines somebody chose to write.
        var members = MembersOf(await ExtractAsync("""
            namespace Shop;

            public record Money(decimal Amount, string Currency);
            """), "Shop.Money");

        Assert.Contains("+ Amount : decimal", members);
        Assert.Contains("+ Currency : string", members);

        Assert.DoesNotContain(members, m => m.Contains("Clone", StringComparison.Ordinal));
        Assert.DoesNotContain(members, m => m.Contains("EqualityContract", StringComparison.Ordinal));
        Assert.DoesNotContain(members, m => m.Contains("<", StringComparison.Ordinal));
    }

    [Fact]
    public async Task AnAccessorIsNotListedBesideItsProperty()
    {
        // get_Name next to Name is the same fact twice, and doubles every compartment.
        var members = MembersOf(await ExtractAsync("""
            namespace Shop;

            public class Customer
            {
                public string Name { get; set; } = "";
            }
            """), "Shop.Customer");

        Assert.Contains("+ Name : string", members);
        Assert.DoesNotContain(members, m => m.Contains("get_", StringComparison.Ordinal));
        Assert.DoesNotContain(members, m => m.Contains("set_", StringComparison.Ordinal));
    }

    [Fact]
    public async Task InheritedMembersBelongToTheTypeThatDeclaresThem()
    {
        // Repeating a base's members on every subclass makes each one look like it redefined its
        // parent — the diagram would show an override that is not there.
        var assertions = await ExtractAsync("""
            namespace Shop;

            public class Animal
            {
                public string Name { get; set; } = "";
            }

            public class Dog : Animal
            {
                public string Breed { get; set; } = "";
            }
            """);

        Assert.Contains("+ Name : string", MembersOf(assertions, "Shop.Animal"));

        var dog = MembersOf(assertions, "Shop.Dog");
        Assert.Contains("+ Breed : string", dog);
        Assert.DoesNotContain("+ Name : string", dog);
    }

    [Fact]
    public async Task ATypeNameInACompartmentIsShortEnoughToRead()
    {
        // The full display string of a generic of a namespaced type is longer than the card it goes
        // on. The fully-qualified name is still on the node itself.
        var members = MembersOf(await ExtractAsync("""
            namespace Shop;

            public class Basket
            {
                public System.Collections.Generic.IReadOnlyList<Shop.Order> Lines { get; } = [];
            }

            public class Order { }
            """), "Shop.Basket");

        Assert.Contains("+ Lines : IReadOnlyList<Order>", members);
    }

    [Fact]
    public async Task ATruncatedCompartmentSaysHowManyThereReallyAre()
    {
        // Absence rendered as success (DC-025): a class with 300 members must not look like one with
        // 40. MEASURED on a real repository, 7 types of 1,428 reach the cap — rare, and invisible
        // exactly where it matters most.
        var many = string.Join(
            Environment.NewLine,
            Enumerable.Range(0, CSharpExtractor.MaxMembersPerType + 12)
                .Select(i => $"    public int Field{i:D3} {{ get; set; }}"));

        var assertions = await ExtractAsync("""
            namespace Shop;

            public class Wide
            {

            """ + many + """

            }
            """);

        Assert.Equal(CSharpExtractor.MaxMembersPerType, MembersOf(assertions, "Shop.Wide").Count);

        var disclosure = assertions.SingleOrDefault(
            a => a.Subject == "Shop.Wide" && a.Predicate == "members_truncated");

        Assert.NotNull(disclosure);
        Assert.Equal(
            (CSharpExtractor.MaxMembersPerType + 12).ToString(System.Globalization.CultureInfo.InvariantCulture),
            disclosure.Object);
    }

    [Fact]
    public async Task ACompleteCompartmentSaysNothingAboutTruncation()
    {
        // A disclosure that fires when nothing was hidden trains a reader to ignore it.
        var assertions = await ExtractAsync("""
            namespace Shop;

            public class Small
            {
                public int Id { get; set; }
            }
            """);

        Assert.DoesNotContain(assertions, a => a.Predicate == "members_truncated");
    }

    [Fact]
    public async Task MembersAreAnAttributeSoTheyNeverBecomeGraphNodes()
    {
        // The whole reason this is `has_member` and not an edge. On a real workspace it is the
        // difference between 9,854 facts about types and 9,854 new things to navigate to.
        Assert.Contains("has_member", EvidencePredicates.Attributes);
        Assert.Contains("members_truncated", EvidencePredicates.Attributes);

        var assertions = await ExtractAsync("""
            namespace Shop;

            public class Order
            {
                public int Id { get; set; }
            }
            """);

        var graph = new Projections.GraphProjection(assertions, "rev-1").Compute();

        Assert.DoesNotContain(graph.Nodes, n => n.Id.Contains(" : ", StringComparison.Ordinal));
    }
}
