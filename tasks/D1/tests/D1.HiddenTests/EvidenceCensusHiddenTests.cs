using System.Collections;
using System.Reflection;
using AiDe.Core.Facts;

public sealed class EvidenceCensusHiddenTests
{
    private static readonly Assembly Core = typeof(EvidenceAssertion).Assembly;

    private static EvidenceAssertion Fact(string predicate, EvidenceOrigin origin, VerificationStatus status) =>
        new("scope", "revision", "Subject", predicate, "Object", origin, status,
            new Provenance("artifact", null, "test", "1", DateTimeOffset.UnixEpoch));

    private static Type RequiredType(string name)
    {
        var type = Core.GetType($"AiDe.Core.Projections.{name}");
        Assert.NotNull(type);
        return type!;
    }

    private static object Compute(IReadOnlyList<EvidenceAssertion> assertions, int maxRows = 50, string revision = "r1")
    {
        var query = Activator.CreateInstance(RequiredType("EvidenceCensusQuery"), maxRows);
        Assert.NotNull(query);
        var method = RequiredType("EvidenceCensusProjection").GetMethod("Compute", BindingFlags.Public | BindingFlags.Static);
        Assert.NotNull(method);
        var result = method!.Invoke(null, [assertions, query, revision]);
        Assert.NotNull(result);
        Assert.Equal(RequiredType("EvidenceCensusResult"), result!.GetType());
        return result;
    }

    private static object Get(object target, string name)
    {
        var property = target.GetType().GetProperty(name, BindingFlags.Public | BindingFlags.Instance);
        Assert.NotNull(property);
        var value = property!.GetValue(target);
        Assert.NotNull(value);
        return value!;
    }

    private static List<(string Predicate, EvidenceOrigin Origin, VerificationStatus Status, int Count)> Rows(object result) =>
        ((IEnumerable)Get(result, "Rows")).Cast<object>()
            .Select(row => (
                (string)Get(row, "Predicate"),
                (EvidenceOrigin)Get(row, "Origin"),
                (VerificationStatus)Get(row, "Status"),
                (int)Get(row, "Count")))
            .ToList();

    [Fact]
    public void CountsEveryInputWithoutCollapsingOriginOrVerificationStatus()
    {
        var repeated = Fact("calls", EvidenceOrigin.Static, VerificationStatus.Verified);
        var result = Compute([
            repeated,
            repeated,
            Fact("calls", EvidenceOrigin.Static, VerificationStatus.Inferred),
            Fact("calls", EvidenceOrigin.Runtime, VerificationStatus.Verified),
        ]);

        Assert.Equal(4, Get(result, "TotalAssertions"));
        Assert.Equal([
            ("calls", EvidenceOrigin.Static, VerificationStatus.Verified, 2),
            ("calls", EvidenceOrigin.Static, VerificationStatus.Inferred, 1),
            ("calls", EvidenceOrigin.Runtime, VerificationStatus.Verified, 1),
        ], Rows(result));
        Assert.Equal(0, Get(result, "OmittedRows"));
    }

    [Fact]
    public void SortsByCountThenOrdinalPredicateThenEnumValues()
    {
        var result = Compute([
            Fact("a", EvidenceOrigin.Runtime, VerificationStatus.Verified),
            Fact("b", EvidenceOrigin.Static, VerificationStatus.Verified),
            Fact("A", EvidenceOrigin.Static, VerificationStatus.Verified),
            Fact("a", EvidenceOrigin.Static, VerificationStatus.Verified),
            Fact("b", EvidenceOrigin.Static, VerificationStatus.Verified),
        ]);

        Assert.Equal([
            ("b", EvidenceOrigin.Static, VerificationStatus.Verified, 2),
            ("A", EvidenceOrigin.Static, VerificationStatus.Verified, 1),
            ("a", EvidenceOrigin.Static, VerificationStatus.Verified, 1),
            ("a", EvidenceOrigin.Runtime, VerificationStatus.Verified, 1),
        ], Rows(result));
    }

    [Fact]
    public void CapsBucketsButKeepsFullTotalsAndDisclosesOmissions()
    {
        var facts = Enumerable.Range(0, 103)
            .Select(i => Fact($"p{i:000}", EvidenceOrigin.Static, VerificationStatus.Verified))
            .ToList();

        var floor = Compute(facts, 0);
        Assert.Single(Rows(floor));
        Assert.Equal(103, Get(floor, "TotalAssertions"));
        Assert.Equal(102, Get(floor, "OmittedRows"));
        Assert.Equal(["Omitted (102)"], ((IEnumerable)Get(floor, "Disclosures")).Cast<string>());

        var ceiling = Compute(facts, int.MaxValue);
        Assert.Equal(100, Rows(ceiling).Count);
        Assert.Equal(3, Get(ceiling, "OmittedRows"));
        Assert.Equal(["Omitted (3)"], ((IEnumerable)Get(ceiling, "Disclosures")).Cast<string>());
    }

    [Fact]
    public void EmptySnapshotStillCarriesItsRevision()
    {
        var result = Compute([], revision: "empty-revision");
        Assert.Empty(Rows(result));
        Assert.Equal(0, Get(result, "TotalAssertions"));
        Assert.Equal(0, Get(result, "OmittedRows"));
        Assert.Empty(((IEnumerable)Get(result, "Disclosures")).Cast<string>());
        Assert.Equal("empty-revision", Get(result, "SourceRevision"));
    }

    [Fact]
    public void RejectsNullInputs()
    {
        var query = Activator.CreateInstance(RequiredType("EvidenceCensusQuery"), 50);
        var method = RequiredType("EvidenceCensusProjection").GetMethod("Compute", BindingFlags.Public | BindingFlags.Static);
        Assert.NotNull(method);
        Assert.IsType<ArgumentNullException>(Assert.Throws<TargetInvocationException>(
            () => method!.Invoke(null, [null, query, "r1"])).InnerException);
        Assert.IsType<ArgumentNullException>(Assert.Throws<TargetInvocationException>(
            () => method!.Invoke(null, [Array.Empty<EvidenceAssertion>(), null, "r1"])).InnerException);
        Assert.IsType<ArgumentNullException>(Assert.Throws<TargetInvocationException>(
            () => method!.Invoke(null, [Array.Empty<EvidenceAssertion>(), query, null])).InnerException);
    }
}
