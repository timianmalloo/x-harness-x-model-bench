using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// Which type calls which — the question `depends_on` was never able to answer.
/// </summary>
/// <remarks>
/// <para><b>The granularity was decided by a measurement, and these tests pin the decision.</b>
/// TheTerrace has 35,364 invocations in hand-written source; 10,451 of them resolve to a type
/// declared in the repository. Method-to-method would be 8,476 edges over 5,054 new method nodes,
/// against a graph payload already at 969,323 bytes of a 1,048,576-byte frame. Type-to-type is 1,492
/// edges over nodes that already exist, and <b>1,077 of them are relationships `depends_on` does not
/// carry</b> — a static helper, an extension method, a factory, a service used once.</para>
///
/// <para><b>Both directions of every disclosure.</b> A disclosure that never fires is decoration and
/// one that always fires is noise (DC-016, DC-025), so each limit here is asserted present on input
/// that triggers it and absent on input that does not.</para>
/// </remarks>
public sealed class CallEdgeTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-calls", Guid.NewGuid().ToString("N"));

    public CallEdgeTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    /// <summary>Extract one project made of the named source files.</summary>
    private async Task<IReadOnlyList<EvidenceAssertion>> ReadAsync(params (string Name, string Body)[] files)
    {
        File.WriteAllText(Path.Combine(_dir, "Calls.csproj"), """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>
            </Project>
            """);

        foreach (var (name, body) in files)
        {
            File.WriteAllText(Path.Combine(_dir, name), body);
        }

        var result = await new CSharpExtractor().ExtractAsync(
            new ExtractionRequest("csharp:Calls:net10.0", Path.Combine(_dir, "Calls.csproj"), "rev-1", 1),
            CancellationToken.None);

        return result.Assertions;
    }

    private Task<IReadOnlyList<EvidenceAssertion>> ReadAsync(string source) =>
        ReadAsync(("Source.cs", source));

    private static IEnumerable<string> Calls(IEnumerable<EvidenceAssertion> facts) =>
        facts.Where(a => a.Predicate == "calls").Select(a => $"{a.Subject} -> {a.Object}");

    private static IEnumerable<string> Disclosures(IEnumerable<EvidenceAssertion> facts) =>
        facts.Where(a => a.Predicate == "discloses").Select(a => a.Object);

    private static bool Discloses(IEnumerable<EvidenceAssertion> facts, string prefix) =>
        Disclosures(facts).Any(d => d.StartsWith(prefix, StringComparison.Ordinal));

    // ---------------------------------------------------------------------------------------------
    // What is drawn.
    // ---------------------------------------------------------------------------------------------

    [Fact]
    public async Task OneTypeCallingAnotherIsAnEdge()
    {
        var facts = await ReadAsync("""
            namespace Shop;

            public static class Pricing
            {
                public static decimal Total(decimal net) => net * 1.2m;
            }

            public class Checkout
            {
                public decimal Charge(decimal net) => Pricing.Total(net);
            }
            """);

        Assert.Contains("Shop.Checkout -> Shop.Pricing", Calls(facts));
    }

    [Fact]
    public async Task ACallIsNotADeclaredDependency()
    {
        // THE WHOLE REASON THIS EXISTS. `Checkout` names `Pricing` nowhere in a field, a parameter
        // or a return type, so `depends_on` has nothing to say about it. MEASURED on TheTerrace:
        // 1,077 of 1,492 call pairs are in exactly this position — 72% of the answer was invisible.
        var facts = await ReadAsync("""
            namespace Shop;

            public static class Pricing
            {
                public static decimal Total(decimal net) => net * 1.2m;
            }

            public class Checkout
            {
                public decimal Charge(decimal net) => Pricing.Total(net);
            }
            """);

        Assert.Contains("Shop.Checkout -> Shop.Pricing", Calls(facts));

        Assert.DoesNotContain(facts, a =>
            a.Predicate == "depends_on" && a.Subject == "Shop.Checkout" && a.Object == "Shop.Pricing");
    }

    [Fact]
    public async Task TheEdgeCarriesTheCallSite()
    {
        // Provenance is the line the call is written on, not the project file. A reader following
        // "who calls this" wants to arrive at the call, and the type-level edge is the only place
        // the member is still recoverable.
        var facts = await ReadAsync("""
            namespace Shop;

            public static class Pricing
            {
                public static decimal Total(decimal net) => net;
            }

            public class Checkout
            {
                public decimal Charge(decimal net) => Pricing.Total(net);
            }
            """);

        var edge = Assert.Single(facts, a => a.Predicate == "calls");

        Assert.Equal("Source.cs", edge.Provenance.ArtifactPathId);
        Assert.Equal("10:43", edge.Provenance.SourceLocation);
        Assert.Equal(VerificationStatus.Verified, edge.Status);
    }

    [Fact]
    public async Task AnExtensionMethodIsAnEdgeToTheClassThatDeclaresIt()
    {
        var facts = await ReadAsync("""
            namespace Shop;

            public class Order { }

            public static class OrderExtensions
            {
                public static string Describe(this Order order) => "order";
            }

            public class Report
            {
                public string Line(Order order) => order.Describe();
            }
            """);

        Assert.Contains("Shop.Report -> Shop.OrderExtensions", Calls(facts));
    }

    [Fact]
    public async Task ACallInsideALambdaBelongsToTheTypeItIsWrittenIn()
    {
        // A lambda is not a node in this graph and never has been. Attributing its calls to the type
        // the lambda was written in is the only answer that names something a reader can navigate to.
        var facts = await ReadAsync("""
            using System;
            using System.Collections.Generic;

            namespace Shop;

            public static class Pricing
            {
                public static decimal Total(decimal net) => net;
            }

            public class Checkout
            {
                public Func<decimal, decimal> Charge() => net => Pricing.Total(net);

                public decimal Local(decimal net)
                {
                    decimal Inner(decimal x) => Pricing.Total(x);
                    return Inner(net);
                }
            }
            """);

        Assert.Contains("Shop.Checkout -> Shop.Pricing", Calls(facts));
    }

    [Fact]
    public async Task AGenericCalleeIsNamedTheWayTheGraphNamesIt()
    {
        // The unbound name, matching what `has_type` emits — `Shop.Repository<T>`. Taking the
        // CONSTRUCTED name would produce `Shop.Repository<Shop.Order>`, an edge whose object matches
        // no node in the graph while looking perfectly correct. That is the half of DC-033 that got
        // through review the first time.
        var facts = await ReadAsync("""
            namespace Shop;

            public class Order { }

            public static class Repository<T>
            {
                public static T? Find(int id) => default;
            }

            public class Lookup
            {
                public Order? ById(int id) => Repository<Order>.Find(id);
            }
            """);

        var declared = facts
            .Where(a => a.Predicate == "has_type")
            .Select(a => a.Subject)
            .ToHashSet(StringComparer.Ordinal);

        var edge = Assert.Single(Calls(facts), c => c.StartsWith("Shop.Lookup ->", StringComparison.Ordinal));

        Assert.Equal("Shop.Lookup -> Shop.Repository<T>", edge);
        Assert.Contains("Shop.Repository<T>", declared);
    }

    [Fact]
    public async Task ACallThroughAnInterfaceIsAnEdgeToTheInterface()
    {
        var facts = await ReadAsync("""
            namespace Shop;

            public interface IClock { int Now(); }

            public class Stamp
            {
                public int At(IClock clock) => clock.Now();
            }
            """);

        Assert.Contains("Shop.Stamp -> Shop.IClock", Calls(facts));

        // And it says so: the edge names what DECLARES the member, not the implementation that runs.
        Assert.True(Discloses(facts, "calls-dispatched-at-runtime ("));
    }

    // ---------------------------------------------------------------------------------------------
    // What is NOT drawn, and is counted instead.
    // ---------------------------------------------------------------------------------------------

    [Fact]
    public async Task TheRuntimeIsCountedAndNotDrawn()
    {
        // The rule the C# reader has always held for types, applied to calls from the start: a first
        // view centred on `string`, `List<T>` and `Console` is not a picture of anybody's domain.
        // Python and TypeScript were both corrected for exactly this after shipping.
        var facts = await ReadAsync("""
            using System;

            namespace Shop;

            public class Greeter
            {
                public void Greet() => Console.WriteLine("hello".ToUpperInvariant());
            }
            """);

        Assert.DoesNotContain(Calls(facts), c => c.Contains("System.", StringComparison.Ordinal));
        Assert.True(Discloses(facts, "calls-outside-this-repository ("));
    }

    [Fact]
    public async Task ACallThatDidNotBindIsNotAnEdge()
    {
        // An unresolved invocation is a gap, not a relationship. Emitting it would point an edge at
        // whatever the source happened to type.
        var facts = await ReadAsync("""
            namespace Shop;

            public class Checkout
            {
                public void Charge() => Missing.Thing();
            }
            """);

        Assert.Empty(Calls(facts));
        Assert.True(Discloses(facts, "calls-not-resolved ("));
    }

    [Fact]
    public async Task AnOverloadThatDidNotResolveIsNotAnEdge()
    {
        // The compiler has candidates and could not choose. "Some method on Pricing" is not a fact —
        // the call as written does not compile, so nothing about it is known.
        var facts = await ReadAsync("""
            namespace Shop;

            public static class Pricing
            {
                public static decimal Total(decimal net) => net;
            }

            public class Checkout
            {
                public void Charge() => Pricing.Total(1m, 2m, 3m);
            }
            """);

        Assert.Empty(Calls(facts));
        Assert.True(Discloses(facts, "calls-not-resolved ("));
    }

    [Fact]
    public async Task ADelegateInvocationIsNotAnEdge()
    {
        // The symbol the compiler binds is the delegate's own `Invoke`, which names the delegate
        // TYPE and not the method somebody assigned to it — the one thing a reader asking "what
        // calls this" wants, and the one thing nothing here can see.
        var facts = await ReadAsync("""
            using System;

            namespace Shop;

            public class Pipeline
            {
                public int Run(Func<int> step) => step();
            }
            """);

        Assert.Empty(Calls(facts));
        Assert.True(Discloses(facts, "calls-through-a-delegate ("));
    }

    [Fact]
    public async Task ReflectionIsCountedAndNotDrawn()
    {
        var facts = await ReadAsync("""
            using System;

            namespace Shop;

            public class Loader
            {
                public object? Make(Type type) => Activator.CreateInstance(type);
            }
            """);

        Assert.Empty(Calls(facts));
        Assert.True(Discloses(facts, "calls-through-reflection ("));
    }

    [Fact]
    public async Task ADynamicCallIsNotAnEdge()
    {
        // There is no compile-time target at all. `dynamic` is the language working as designed, so
        // it is a different sentence from "this did not compile".
        var facts = await ReadAsync("""
            namespace Shop;

            public class Bridge
            {
                public void Send(dynamic target) => target.Handle();
            }
            """);

        Assert.Empty(Calls(facts));
        Assert.True(Discloses(facts, "calls-dynamically-bound ("));
    }

    [Fact]
    public async Task ATypeCallingItselfIsNotAnEdgeAndIsCounted()
    {
        // MEASURED on TheTerrace: 5,484 of 10,451 in-repository calls stay inside one type. A
        // self-edge answers no question — but dropping the majority of what was read without saying
        // so would make "this graph shows the calls" a much smaller claim than it sounds (DC-025).
        var facts = await ReadAsync("""
            namespace Shop;

            public class Checkout
            {
                public decimal Charge(decimal net) => Apply(net);

                private decimal Apply(decimal net) => net;
            }
            """);

        Assert.Empty(Calls(facts));
        Assert.True(Discloses(facts, "calls-within-one-type ("));
    }

    [Fact]
    public async Task ACallOutsideAnyTypeIsCounted()
    {
        var facts = await ReadAsync(
            ("Program.cs", """
                Shop.Pricing.Total(1m);
                """),
            ("Pricing.cs", """
                namespace Shop;

                public static class Pricing
                {
                    public static decimal Total(decimal net) => net;
                }
                """));

        Assert.Empty(Calls(facts));
        Assert.True(Discloses(facts, "calls-outside-a-type ("));
    }

    [Fact]
    public async Task GeneratedSourceIsNotReadForCalls()
    {
        // 79,042 of TheTerrace's 114,406 invocations — 69% — are in EF migration snapshots, which
        // describe a schema as it stood at a past migration. Reading them asserts the past as fact
        // and costs three quarters of the scan.
        var facts = await ReadAsync(
            ("Generated.cs", """
                // <auto-generated />
                namespace Shop;

                public class Snapshot
                {
                    public decimal Charge() => Pricing.Total(1m);
                }
                """),
            ("Pricing.cs", """
                namespace Shop;

                public static class Pricing
                {
                    public static decimal Total(decimal net) => net;
                }

                public class Checkout
                {
                    public decimal Charge() => Pricing.Total(1m);
                }
                """));

        // The hand-written caller IS read, so the skip above is a skip and not a dead reader
        // (DC-016: a control whose failing branch cannot be reached certifies rather than checks).
        Assert.Contains("Shop.Checkout -> Shop.Pricing", Calls(facts));
        Assert.DoesNotContain("Shop.Snapshot -> Shop.Pricing", Calls(facts));
    }

    [Fact]
    public async Task TextThatMerelyLooksLikeACallIsNotAnEdge()
    {
        // The invent direction. This reader asks the compiler rather than matching a shape, so a
        // call in a comment or a string cannot become an edge — asserted rather than assumed,
        // because three readers in this codebase have now been caught inventing.
        var facts = await ReadAsync("""
            namespace Shop;

            public static class Pricing
            {
                public static decimal Total(decimal net) => net;
            }

            public class Checkout
            {
                // Charge used to call Pricing.Total(net) before the rewrite.
                public string Doc => "call Pricing.Total(net) to price an order";
            }
            """);

        Assert.Empty(Calls(facts));
    }

    // ---------------------------------------------------------------------------------------------
    // The other direction: a disclosure that fires when nothing was hidden is noise.
    // ---------------------------------------------------------------------------------------------

    [Fact]
    public async Task EachDisclosureIsSilentWhenThereIsNothingToDisclose()
    {
        // DC-016 and DC-025 together. Every limit above is asserted PRESENT on input that triggers
        // it; this asserts it ABSENT on input that does not, so none of them is a constant.
        var facts = await ReadAsync("""
            namespace Shop;

            public static class Pricing
            {
                public static decimal Total(decimal net) => net;
            }

            public class Checkout
            {
                public decimal Charge(decimal net) => Pricing.Total(net);
            }
            """);

        Assert.Contains("Shop.Checkout -> Shop.Pricing", Calls(facts));

        Assert.False(Discloses(facts, "calls-not-resolved ("), string.Join(" | ", Disclosures(facts)));
        Assert.False(Discloses(facts, "calls-through-a-delegate ("));
        Assert.False(Discloses(facts, "calls-through-reflection ("));
        Assert.False(Discloses(facts, "calls-dynamically-bound ("));
        Assert.False(Discloses(facts, "calls-within-one-type ("));
        Assert.False(Discloses(facts, "calls-outside-a-type ("));
        Assert.False(Discloses(facts, "calls-dispatched-at-runtime ("));
    }

    [Fact]
    public async Task ABoundaryAndAGapAreDifferentSentences()
    {
        // DC-050, applied before it could happen again. A call into the base class library is
        // something this product declines to index; a call that did not bind is something it meant
        // to read and could not. One count for both would be arithmetically right and useless for
        // deciding what to build next.
        var facts = await ReadAsync("""
            using System;

            namespace Shop;

            public class Checkout
            {
                public void Charge()
                {
                    Console.WriteLine("charging");
                    Missing.Thing();
                }
            }
            """);

        var boundary = Disclosures(facts)
            .Single(d => d.StartsWith("calls-outside-this-repository (", StringComparison.Ordinal));

        var gap = Disclosures(facts)
            .Single(d => d.StartsWith("calls-not-resolved (", StringComparison.Ordinal));

        Assert.Contains("does not index", boundary, StringComparison.Ordinal);
        Assert.Contains("could not bind", gap, StringComparison.Ordinal);
    }

    [Fact]
    public async Task CallsIsARelationAndNotAnAttribute()
    {
        // A call between two things is a relation: both ends are nodes a reader navigates to.
        // Registering it as an attribute would put the callee's name in the graph as a value rather
        // than a node, which is the mistake `has_member` exists to avoid in the other direction.
        Assert.DoesNotContain("calls", EvidencePredicates.Attributes);

        var facts = await ReadAsync("""
            namespace Shop;

            public static class Pricing
            {
                public static decimal Total(decimal net) => net;
            }

            public class Checkout
            {
                public decimal Charge(decimal net) => Pricing.Total(net);
            }
            """);

        // And the object of a `calls` edge is a node this workspace declares, not a formatted value.
        var declared = facts
            .Where(a => a.Predicate == "has_type")
            .Select(a => a.Subject)
            .ToHashSet(StringComparer.Ordinal);

        Assert.Contains(facts, a => a.Predicate == "calls");

        foreach (var edge in facts.Where(a => a.Predicate == "calls"))
        {
            Assert.Contains(edge.Subject, declared);
            Assert.Contains(edge.Object, declared);
        }
    }

}
