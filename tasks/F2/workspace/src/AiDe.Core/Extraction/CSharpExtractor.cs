using System.Text.RegularExpressions;
using System.Diagnostics;
using AiDe.Core.Facts;
using Microsoft.CodeAnalysis;

namespace AiDe.Core.Extraction;

/// <summary>
/// The C# semantic extractor — real symbols, without ever running the repository's build.
/// </summary>
/// <remarks>
/// <para><b>Named for the language, not the library.</b> Roslyn is still the semantic engine, but
/// "RoslynExtractor" implied the Roslyn <i>workspace</i> layer, and that is precisely the part not
/// used: <c>MSBuildWorkspace</c> loads projects by evaluating MSBuild, which spike D3 measured
/// executing repository-supplied code by four vectors, two of which need nothing but a checked-in
/// <c>.csproj</c>.</para>
///
/// <para><b>One scope is one (project, target framework).</b> Declared here rather than left
/// implicit, because it is the grain of every row this emits.</para>
///
/// <para><b>An edge that did not resolve is not emitted.</b> Emitting it as <c>Inferred</c> would be
/// worse than silence: the name is whatever the source typed, unresolved by anything, so the edge
/// would point at a node that may not exist. What the user gets instead is a disclosure on the scope
/// saying the picture is incomplete and why.</para>
/// </remarks>
public sealed class CSharpExtractor(string extractorVersion = "1.0.0") : IExtractor
{
    public const string ExtractorId = "csharp-extractor";

    /// <summary>The predicate a scope uses to declare what it could not see.</summary>
    public const string DisclosurePredicate = "discloses";

    private readonly CSharpProjectReader _reader = new();

    public string ScopeKind => "csharp";

    /// <summary>Every target framework the project at <paramref name="projectPath"/> declares.</summary>
    /// <remarks>The caller creates one scope per entry — see the grain note on the class.</remarks>
    public IReadOnlyList<string> TargetFrameworks(string projectPath) => _reader.TargetFrameworks(projectPath);

    public Task<ExtractionResult> ExtractAsync(ExtractionRequest request, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);

        var projectPath = Path.GetFullPath(request.RootPath);
        if (!File.Exists(projectPath))
        {
            return Task.FromResult(new ExtractionResult(
                [], Complete: false,
                [new ExtractionDiagnostic("AIDE-EXT-PROJECT-MISSING", request.RootPath, "no project file at this path")]));
        }

        // The framework is carried on the scope id's suffix when the caller made one scope per
        // framework; otherwise the project's first declared framework is used.
        var frameworks = _reader.TargetFrameworks(projectPath);
        if (frameworks.Count == 0)
        {
            // Discovery still produced a scope for this project so it would be counted rather than
            // vanish; this is where that scope becomes a reported failure.
            return Task.FromResult(new ExtractionResult(
                [], Complete: false,
                [new ExtractionDiagnostic(
                    "AIDE-EXT-PROJECT-UNREADABLE", request.ScopeId,
                    "the project file could not be read as XML")]));
        }

        var tfm = frameworks.FirstOrDefault(f =>
            request.ScopeId.EndsWith(f, StringComparison.OrdinalIgnoreCase)) ?? frameworks[0];

        // Where a scope's time goes, emitted on the normal path. "Extraction is the cost" was true and
        // useless: it did not say whether the cost is reading the project, building the compilation,
        // or walking the symbols, and those have opposite fixes.
        var readStarted = System.Diagnostics.Stopwatch.StartNew();

        CSharpCompilationResult compiled;
        try
        {
            compiled = _reader.Compile(projectPath, tfm, cancellationToken);
        }
        catch (OperationCanceledException)
        {
            // The scope budget expired. Reported as an incomplete extraction rather than rethrown,
            // because a scope that timed out must quarantine itself and leave the other scopes'
            // evidence alone (P2-EXT-04) — not fail the whole refresh.
            return Task.FromResult(new ExtractionResult(
                [], Complete: false,
                [new ExtractionDiagnostic("AIDE-EXT-TIMEOUT", request.ScopeId, $"extraction exceeded its budget for {tfm}")]));
        }

        var diagnostics = new List<ExtractionDiagnostic>();
        var assertions = new List<EvidenceAssertion>();
        var observedAt = DateTimeOffset.UtcNow;

        if (compiled.Compilation is null)
        {
            diagnostics.Add(new ExtractionDiagnostic(
                "AIDE-EXT-LOAD-FAILED", request.ScopeId, $"the project could not be compiled for {tfm}"));
            return Task.FromResult(new ExtractionResult(assertions, Complete: false, diagnostics));
        }

        var readMs = readStarted.ElapsedMilliseconds;
        var walkStarted = System.Diagnostics.Stopwatch.StartNew();

        // Disclosures FIRST, so a scope whose extraction is later truncated still carries the
        // reasons it is incomplete. A truncated list that lost its caveats is worse than a short one.
        foreach (var disclosure in compiled.Disclosures)
        {
            assertions.Add(Assertion(
                request, ScopeNodeId(request.ScopeId), DisclosurePredicate, disclosure,
                VerificationStatus.Verified, new Provenance(
                    Path.GetFileName(projectPath), "1:1", ExtractorId, extractorVersion, observedAt)));
        }

        foreach (var note in compiled.Notes)
        {
            diagnostics.Add(new ExtractionDiagnostic("AIDE-EXT-NOTE", request.ScopeId, note));
        }

        // The walk is the largest real cost — 1,167ms of a 2s scope on a real repository — and it
        // has never been broken down. Enumerating the namespace tree and asking each type for its
        // members are different operations with different remedies.
        var enumerateWatch = System.Diagnostics.Stopwatch.StartNew();
        var discovered = new List<INamedTypeSymbol>();
        Walk(compiled.Compilation.Assembly.GlobalNamespace, discovered);

        // GENERATED types are not part of the codebase anybody can navigate or change. TheTerrace
        // declares 1,027 types, of which roughly six hundred are EF migration model snapshots —
        // classes written by a tool, describing the schema AS IT STOOD at a past migration. Left in,
        // they are indistinguishable from the user's own code in the graph, they crowd the centre
        // the way the BCL did before nodes carried IsExternal, and they cost the largest single
        // measurement in extraction: reading every member's type is 597ms of a 809ms walk, and most
        // of those members belong to files nobody wrote.
        var types = new List<INamedTypeSymbol>(discovered.Count);
        var generatedTypes = 0;

        foreach (var type in discovered)
        {
            if (IsGeneratedType(type, cancellationToken))
            {
                generatedTypes++;
                continue;
            }

            types.Add(type);
        }

        enumerateWatch.Stop();

        var memberWatch = System.Diagnostics.Stopwatch.StartNew();

        // The walk's interior, split by OPERATION rather than by type. `members 1,074ms` named the
        // loop, not the cost inside it, and the loop does four different things: name a symbol, find
        // where it was written, read its attributes, and traverse its members. Accumulated ticks
        // rather than nested stopwatches — a Stopwatch per type per operation would be four
        // allocations a thousand times over, measuring the measurement.
        long displayTicks = 0, provenanceTicks = 0, attributeTicks = 0, dependsTicks = 0;
        long dependsGatherTicks = 0, dependsDedupeTicks = 0;
        var displayCalls = 0;
        var dependsRaw = 0;

        foreach (var type in types)
        {
            cancellationToken.ThrowIfCancellationRequested();

            var mark = System.Diagnostics.Stopwatch.GetTimestamp();
            var subject = type.ToDisplayString();
            displayTicks += System.Diagnostics.Stopwatch.GetTimestamp() - mark;
            displayCalls++;

            mark = System.Diagnostics.Stopwatch.GetTimestamp();
            var provenance = ProvenanceFor(type, projectPath, observedAt);
            provenanceTicks += System.Diagnostics.Stopwatch.GetTimestamp() - mark;

            assertions.Add(Assertion(request, subject, "has_type", KindOf(type), VerificationStatus.Verified, provenance));
            assertions.Add(Assertion(request, subject, "declared_in", request.ScopeId, VerificationStatus.Verified, provenance));

            if (type.BaseType is { SpecialType: not SpecialType.System_Object } baseType && Resolved(baseType))
            {
                mark = System.Diagnostics.Stopwatch.GetTimestamp();
                var baseName = baseType.ToDisplayString();
                displayTicks += System.Diagnostics.Stopwatch.GetTimestamp() - mark;
                displayCalls++;

                assertions.Add(Assertion(
                    request, subject, "inherits", baseName, VerificationStatus.Verified, provenance));
            }

            // MEMBERS, for the class diagram's compartments (ADR-0026 class-diagram-architecture).
            //
            // Declared on this type only — inherited members belong to the type that declares them,
            // and repeating them would make every subclass look like it redefined its parent. The
            // compiler's own generated members are skipped for the same reason `IsGeneratedType`
            // exists: a record's `<Clone>$` and a property's backing field are artifacts of
            // compilation, not things anybody wrote.
            var members = Members(type).ToList();

            foreach (var member in members)
            {
                assertions.Add(Assertion(
                    request, subject, "has_member", member, VerificationStatus.Verified, provenance));
            }

            // A truncated compartment says so. Without this a class with 300 members renders exactly
            // like one with 40, and the reader cannot tell a complete list from the top of a long
            // one — the shape of defect this codebase calls "absence rendered as success" (DC-025).
            // MEASURED on a real repository: 7 types of 1,428 reach the cap.
            if (members.Count == MaxMembersPerType)
            {
                assertions.Add(Assertion(
                    request, subject, "members_truncated", DeclaredMemberCount(type).ToString(
                        System.Globalization.CultureInfo.InvariantCulture),
                    VerificationStatus.Verified, provenance));
            }

            foreach (var contract in type.Interfaces.Where(Resolved))
            {
                mark = System.Diagnostics.Stopwatch.GetTimestamp();
                var contractName = contract.ToDisplayString();
                displayTicks += System.Diagnostics.Stopwatch.GetTimestamp() - mark;
                displayCalls++;

                assertions.Add(Assertion(
                    request, subject, "implements", contractName, VerificationStatus.Verified, provenance));
            }

            // A [Table("orders")] attribute is a DECLARATION, so the code-to-schema join it produces
            // is Verified rather than a naming-convention guess. This is the one join in the phase
            // that a repository states outright, and it is worth reading precisely because every
            // other one is inferred.
            mark = System.Diagnostics.Stopwatch.GetTimestamp();
            var declaredTable = type.GetAttributes()
                .FirstOrDefault(a => a.AttributeClass?.Name is "TableAttribute" or "Table")
                ?.ConstructorArguments.FirstOrDefault().Value as string;

            if (!string.IsNullOrEmpty(declaredTable))
            {
                assertions.Add(Assertion(
                    request, subject, "declares_table", declaredTable, VerificationStatus.Verified, provenance));
            }

            attributeTicks += System.Diagnostics.Stopwatch.GetTimestamp() - mark;

            // Split, because "depends-on 613ms" names the call and not the cost inside it. Walking
            // the members and de-duplicating the result are different operations with different
            // remedies, and SymbolEqualityComparer is the untested suspect: symbol hashing is not
            // free, and this runs it over every field, property, parameter and return type in the
            // repository.
            mark = System.Diagnostics.Stopwatch.GetTimestamp();
            var raw = DependsOn(type).ToList();
            var gathered = System.Diagnostics.Stopwatch.GetTimestamp() - mark;
            dependsGatherTicks += gathered;
            dependsRaw += raw.Count;

            mark = System.Diagnostics.Stopwatch.GetTimestamp();
            var targets = raw.Distinct(SymbolEqualityComparer.Default).OfType<ITypeSymbol>().ToList();
            dependsDedupeTicks += System.Diagnostics.Stopwatch.GetTimestamp() - mark;
            dependsTicks += gathered + (System.Diagnostics.Stopwatch.GetTimestamp() - mark);

            foreach (var target in targets)
            {
                mark = System.Diagnostics.Stopwatch.GetTimestamp();
                var targetName = target.ToDisplayString();
                displayTicks += System.Diagnostics.Stopwatch.GetTimestamp() - mark;
                displayCalls++;

                assertions.Add(Assertion(
                    request, subject, "depends_on", targetName, VerificationStatus.Verified, provenance));
            }
        }

        memberWatch.Stop();

        // A Fluent `builder.Entity<Order>().ToTable("orders")` is as much a declaration as the
        // attribute, and it is the MORE common style — without it the commonest way of stating the
        // mapping fell back to a name-matching guess. Scanned once over the compilation's trees
        // rather than once per type; provenance is now the CALL SITE, which is where a reader
        // looking for the mapping actually needs to go.
        var fluentWatch = System.Diagnostics.Stopwatch.StartNew();

        var unresolvedMappings = 0;
        var generatedSkipped = 0;

        foreach (var (entity, table, where) in FluentTableMappings(
            compiled.Compilation,
            (unresolvedCount, generatedCount) =>
            {
                unresolvedMappings = unresolvedCount;
                generatedSkipped = generatedCount;
            },
            cancellationToken))
        {
            assertions.Add(Assertion(
                request, entity, "declares_table", table, VerificationStatus.Verified,
                ProvenanceAt(where, projectPath, observedAt)));
        }

        if (generatedTypes > 0)
        {
            // A count, not a silence. "This repository declares 427 types" and "this repository
            // declares 1,027 types, 600 of them generated" are different statements about the graph,
            // and only one of them lets a reader judge whether the picture is complete.
            assertions.Add(Assertion(
                request, ScopeNodeId(request.ScopeId), DisclosurePredicate,
                $"generated-types-not-indexed ({generatedTypes:N0} type(s) declared only in " +
                "auto-generated source)", VerificationStatus.Verified,
                new Provenance(Path.GetFileName(projectPath), "1:1", ExtractorId, extractorVersion, observedAt)));
        }

        if (generatedSkipped > 0)
        {
            // Skipped is not the same as absent. A reader who knows the mapping is written down
            // somewhere needs to be told that this is where it was declined, and why.
            assertions.Add(Assertion(
                request, ScopeNodeId(request.ScopeId), DisclosurePredicate,
                $"generated-source-not-read-for-mappings ({generatedSkipped:N0} auto-generated " +
                "file(s) mention ToTable; their mappings describe a past migration, not the model)",
                VerificationStatus.Verified,
                new Provenance(Path.GetFileName(projectPath), "1:1", ExtractorId, extractorVersion, observedAt)));
        }

        if (unresolvedMappings > 0)
        {
            // Counted, because "some mappings were not read" and "17 of 60 were not read" are
            // different statements about how much of the code-to-schema join is still a guess.
            assertions.Add(Assertion(
                request, ScopeNodeId(request.ScopeId), DisclosurePredicate,
                $"fluent-table-mappings-unresolved ({unresolvedMappings:N0} ToTable call(s) whose " +
                "entity type did not resolve)", VerificationStatus.Verified,
                new Provenance(Path.GetFileName(projectPath), "1:1", ExtractorId, extractorVersion, observedAt)));
        }

        fluentWatch.Stop();

        // WHICH TYPE TALKS TO WHICH TABLE, for repositories with no ORM at all. Measured: BioHacker
        // has zero DbContext files, zero [Table] attributes and 191 SQL literals naming tables from
        // inside store classes, so every join it had was a NAME GUESS. This is the declaration it
        // actually makes.
        //
        // Deliberately `uses_table` and NOT `maps_to`. A store class that issues four statements
        // against three tables is not MAPPED to any of them, and reusing the mapping predicate would
        // put a confident wrong answer where an honest one belongs — the same laundering the
        // `depends_on` join once did (DC-022).
        foreach (var (type, table, where) in SqlTableUsage(compiled.Compilation, cancellationToken))
        {
            assertions.Add(Assertion(
                request, type, "uses_table", $"table:{table}", VerificationStatus.Verified,
                ProvenanceAt(where, projectPath, observedAt)));
        }

        // WHICH TYPE CALLS WHICH, which `depends_on` does not say and was never able to.
        //
        // MEASURED on TheTerrace before any of this was written, because the volume decides the
        // design: 35,364 invocations in hand-written source, of which 10,451 resolve to a type
        // declared in this repository. Deduplicated that is 1,989 type pairs, 1,492 once a type
        // calling itself is set aside — and only 415 of those 1,492 already exist as `depends_on`.
        // **1,077 of them, 72%, are relationships the graph could not show**: a static helper, an
        // extension method, a factory, a service resolved from a container and used once. A type
        // depends on what it DECLARES; it calls plenty it never declares.
        var callWatch = System.Diagnostics.Stopwatch.StartNew();
        var calls = new CallCensus();

        // `TypeCalls` is not an iterator — the walk runs and both results are ready before the
        // enumerable is touched — so the sites are populated by the time the loop below reads them.
        var edges = TypeCalls(compiled.Compilation, calls, out var callSites, cancellationToken);

        foreach (var (caller, callee, where) in edges)
        {
            assertions.Add(Assertion(
                request, caller, "calls", callee, VerificationStatus.Verified,
                ProvenanceAt(where, projectPath, observedAt)));
        }

        // EVERY CALL SITE, in order — the interaction, as opposed to the relationship.
        //
        // `calls` is deduplicated to one row per pair, which is right for a graph and wrong for a
        // sequence diagram: `A -> B, A -> C, A -> B` collapses to two messages and the repeat is
        // gone. An interaction that silently drops a repeated call is confidently incomplete, which
        // is worse than an empty diagram.
        //
        // It is an ATTRIBUTE (see EvidencePredicates), so it is never drawn: the graph keeps its
        // deduplicated edges and its payload, and these rows are read only by a query that asks for
        // ONE caller. The object encodes `Type#Member` because a message needs a name — `Order ->
        // Customer` is an arrow, `Order -> Customer.Save()` is the thing the diagram was opened to
        // find out — and `#` cannot occur in a C# display string, so the two parts always split.
        foreach (var (caller, callee, member, where) in callSites)
        {
            var at = ProvenanceAt(where, projectPath, observedAt);

            // THE CALL SITE IS PART OF THE VALUE, not just of the provenance.
            //
            // The store's natural key is (scope, generation, subject, predicate, object) — P1-STORE-05
            // — so two rows saying `Order calls Customer#Save` are ONE fact however many times the
            // call is written, and the second is rejected on insert. That is correct for a fact; it
            // is fatal for an interaction, and it defeated the first version of this silently: ten
            // identical call sites arrived as one message and the sequence was quietly short.
            //
            // So the position goes in the object, where it makes the fact distinct as well as
            // locatable. `Order -> Customer.Save at 12:9` and `at 14:9` are genuinely two different
            // things that happened, which is exactly what a sequence diagram draws.
            assertions.Add(Assertion(
                request, caller, "calls_at", $"{callee}#{member}@{at.SourceLocation}",
                VerificationStatus.Verified, at));
        }

        callWatch.Stop();

        // Each of these fires only on a non-zero count, and each says a DIFFERENT thing — a boundary
        // this product declines to index, a gap it meant to read and could not, and three limits on
        // what a compiler can tell you about where a call actually lands. DC-050 is the reason they
        // are not one number: 246 "unresolved imports" that were all the standard library became the
        // top of a priority list for work that did not exist.
        foreach (var disclosure in calls.Disclosures())
        {
            assertions.Add(Assertion(
                request, ScopeNodeId(request.ScopeId), DisclosurePredicate, disclosure,
                VerificationStatus.Verified,
                new Provenance(Path.GetFileName(projectPath), "1:1", ExtractorId, extractorVersion, observedAt)));
        }

        // Complete means "this is the whole snapshot for this scope", which it is: the disclosures
        // are IN the snapshot rather than missing from it. Marking it incomplete would quarantine
        // every unrestored project, which is most of them on a fresh clone.

        if (Environment.GetEnvironmentVariable("AIDE_EXTRACTION_TIMING") is not null)
        {
            Console.Error.WriteLine(
                $"[timing]   call-scan {callWatch.ElapsedMilliseconds}ms over {calls.Sites:N0} " +
                $"invocation(s), {calls.InThisRepository:N0} in-repository");
            Console.Error.WriteLine(
                $"[timing]   enumerate-types {enumerateWatch.ElapsedMilliseconds}ms for {types.Count} type(s), " +
                $"members {memberWatch.ElapsedMilliseconds}ms " +
                $"(display {Ms(displayTicks)}ms/{displayCalls:N0} calls, provenance {Ms(provenanceTicks)}ms, " +
                $"attributes {Ms(attributeTicks)}ms, depends-on {Ms(dependsTicks)}ms " +
                $"[gather {Ms(dependsGatherTicks)}ms over {dependsRaw:N0} raw, " +
                $"dedupe {Ms(dependsDedupeTicks)}ms]), " +
                $"fluent-scan {fluentWatch.ElapsedMilliseconds}ms");
        }

        // Emitted on the NORMAL path, no flag to remember: an operator asking "why is indexing slow"
        // gets the split rather than a total they have to guess at.
        Activity.Current?.SetTag("extraction.read_ms", readMs);
        Activity.Current?.SetTag("extraction.walk_ms", walkStarted.ElapsedMilliseconds);
        Activity.Current?.SetTag("extraction.assertions", assertions.Count);

        // The call scan is the largest single addition to a scope's cost — MEASURED at 4.6s of the
        // main TheTerrace scope, against 1.2s for everything the extractor did before it — so it is
        // emitted on the normal path rather than behind the timing flag. An operator asking "why did
        // indexing get slower" should not have to re-run with an environment variable set (IO1).
        Activity.Current?.SetTag("extraction.call_ms", callWatch.ElapsedMilliseconds);
        Activity.Current?.SetTag("extraction.call_sites", calls.Sites);

        if (Environment.GetEnvironmentVariable("AIDE_EXTRACTION_TIMING") is not null)
        {
            Console.Error.WriteLine(
                $"[timing] {request.ScopeId}: read {readMs}ms, walk {walkStarted.ElapsedMilliseconds}ms, " +
                $"{assertions.Count:N0} assertion(s)");
        }

        // Identical facts are ONE fact. A store class naming the same table in four statements
        // emits the same `uses_table` triple four times, and the store's natural key rejects that —
        // correctly, and as a raw SQLite error from the middle of an index. Third extractor to need
        // this, which is why the rule now lives in one place.
        return Task.FromResult(new ExtractionResult(
            ExtractionFacts.Distinct(assertions), Complete: true, diagnostics));
    }

    /// <summary>Accumulated stopwatch ticks as milliseconds.</summary>
    private static long Ms(long ticks) => ticks * 1000 / System.Diagnostics.Stopwatch.Frequency;

    /// <summary>The node a scope's own facts hang off.</summary>
    public static string ScopeNodeId(string scopeId) => $"scope:{scopeId}";

    private EvidenceAssertion Assertion(
        ExtractionRequest request, string subject, string predicate, string @object,
        VerificationStatus status, Provenance provenance) =>
        new(request.ScopeId, request.ArtifactRevision, subject, predicate, @object,
            EvidenceOrigin.Static, status, provenance);

    private Provenance ProvenanceFor(ISymbol symbol, string projectPath, DateTimeOffset observedAt) =>
        ProvenanceAt(symbol.Locations.FirstOrDefault(l => l.IsInSource), projectPath, observedAt);

    /// <summary>Where a fact was written, or the project file when that is not in source.</summary>
    private Provenance ProvenanceAt(Location? location, string projectPath, DateTimeOffset observedAt)
    {
        if (location is null || !location.IsInSource || location.SourceTree is null)
        {
            return new Provenance(Path.GetFileName(projectPath), "1:1", ExtractorId, extractorVersion, observedAt);
        }

        var line = location.GetLineSpan().StartLinePosition;
        var dir = Path.GetDirectoryName(Path.GetFullPath(projectPath))!;
        var relative = Path.GetRelativePath(dir, location.SourceTree.FilePath).Replace((char)92, '/');
        return new Provenance(relative, $"{line.Line + 1}:{line.Character + 1}", ExtractorId, extractorVersion, observedAt);
    }

    /// <summary>
    /// A type's own members, rendered for a UML compartment.
    /// </summary>
    /// <remarks>
    /// <para><b>Formatted, not structured</b> — <c>+ Name : string</c>, <c>+ Save(int) : Task</c> —
    /// because the consumer is a compartment of text and a structured payload would be parsed back
    /// into one. The leading glyph is UML's visibility marker: <c>+</c> public, <c>#</c> protected,
    /// <c>-</c> private, <c>~</c> internal.</para>
    ///
    /// <para><b>What is skipped, and why each.</b> Compiler-generated members (a record's
    /// <c>&lt;Clone&gt;$</c>, a property's backing field, an event's add/remove pair) are artifacts of
    /// compilation rather than anything a person wrote. Property accessors are skipped because the
    /// property itself is already listed and <c>get_Name</c> beside <c>Name</c> is noise. Constructors
    /// are kept: which constructors a type offers is part of how it is used.</para>
    ///
    /// <para><b>Capped per type.</b> A generated or god-class type with hundreds of members would
    /// dominate a payload sized for a card. The cap is disclosed by count on the type itself, so a
    /// truncated compartment says so rather than looking complete.</para>
    /// </remarks>
    private static IEnumerable<string> Members(INamedTypeSymbol type)
    {
        var emitted = 0;

        foreach (var member in type.GetMembers())
        {
            if (member.IsImplicitlyDeclared || member.Kind == SymbolKind.NamedType) continue;

            // An accessor is reachable through its property; listing both says the same thing twice.
            if (member is IMethodSymbol { AssociatedSymbol: not null }) continue;

            var text = member switch
            {
                IPropertySymbol property =>
                    $"{Visibility(property)} {property.Name} : {Short(property.Type)}",

                IFieldSymbol field =>
                    $"{Visibility(field)} {field.Name} : {Short(field.Type)}",

                IMethodSymbol method =>
                    $"{Visibility(method)} {method.Name}({string.Join(", ", method.Parameters.Select(p => Short(p.Type)))})"
                    + (method.ReturnsVoid ? string.Empty : $" : {Short(method.ReturnType)}"),

                IEventSymbol declaredEvent =>
                    $"{Visibility(declaredEvent)} {declaredEvent.Name} : {Short(declaredEvent.Type)}",

                _ => null,
            };

            if (text is null) continue;

            yield return text;

            if (++emitted == MaxMembersPerType) yield break;
        }
    }

    /// <summary>How many members the type actually declares, for the truncation disclosure.</summary>
    /// <remarks>
    /// Counted with the same filter the listing uses, because a total that counted compiler-generated
    /// members would report a shortfall that is not there — "40 of 312" where 312 includes 200
    /// backing fields nobody wrote is a worse answer than no number.
    /// </remarks>
    private static int DeclaredMemberCount(INamedTypeSymbol type) => type.GetMembers().Count(
        m => !m.IsImplicitlyDeclared
            && m.Kind != SymbolKind.NamedType
            && m is not IMethodSymbol { AssociatedSymbol: not null });

    /// <summary>Members carried per type before the compartment is truncated.</summary>
    /// <remarks>
    /// Enough for any type a person reads at once. A class with more than this has a problem the
    /// diagram cannot fix, and carrying all of them would cost every other type on the canvas.
    /// </remarks>
    public const int MaxMembersPerType = 40;

    /// <summary>UML's visibility markers, so a compartment reads as a compartment.</summary>
    private static string Visibility(ISymbol member) => member.DeclaredAccessibility switch
    {
        Accessibility.Public => "+",
        Accessibility.Protected or Accessibility.ProtectedOrInternal => "#",
        Accessibility.Private => "-",
        _ => "~",
    };

    /// <summary>
    /// A type name short enough for a card.
    /// </summary>
    /// <remarks>
    /// <c>MinimallyQualifiedFormat</c> rather than the full display string: a compartment reading
    /// <c>System.Collections.Generic.IReadOnlyList&lt;TheTerrace.Features.Fixtures.Fixture&gt;</c> is
    /// a compartment nobody can read. The full name is still on the node itself.
    /// </remarks>
    private static string Short(ITypeSymbol type) =>
        type.ToDisplayString(SymbolDisplayFormat.MinimallyQualifiedFormat);

    private static string KindOf(INamedTypeSymbol type) => type.TypeKind switch
    {
        TypeKind.Interface => "interface",
        TypeKind.Struct => "struct",
        TypeKind.Enum => "enum",
        TypeKind.Delegate => "delegate",
        _ => type.IsRecord ? "record" : "class",
    };

    /// <summary>
    /// Whether a symbol actually resolved. An error type is what the compiler produces when a
    /// reference could not be bound — its name is whatever the source typed, so an edge to it points
    /// at a node that may not exist.
    /// </summary>
    private static bool Resolved(ITypeSymbol type) => type switch
    {
        { TypeKind: TypeKind.Error } => false,
        IArrayTypeSymbol array => Resolved(array.ElementType),
        INamedTypeSymbol { IsGenericType: true } generic => generic.TypeArguments.All(Resolved),
        _ => true,
    };

    /// <summary>
    /// The types this type's own declarations point at — field and property types, method returns
    /// and parameters. Generic arguments are unwrapped, so <c>Task&lt;Order&gt;</c> yields an edge to
    /// <c>Order</c> rather than only to <c>Task</c>.
    /// </summary>
    private static IEnumerable<ITypeSymbol> DependsOn(INamedTypeSymbol type)
    {
        foreach (var member in type.GetMembers())
        {
            if (member.IsImplicitlyDeclared) continue;

            switch (member)
            {
                case IFieldSymbol field:
                    foreach (var t in Unwrap(field.Type)) yield return t;
                    break;

                case IPropertySymbol property:
                    foreach (var t in Unwrap(property.Type)) yield return t;
                    break;

                case IMethodSymbol { MethodKind: MethodKind.Ordinary or MethodKind.Constructor } method:
                    if (method.MethodKind == MethodKind.Ordinary)
                    {
                        foreach (var t in Unwrap(method.ReturnType)) yield return t;
                    }

                    foreach (var parameter in method.Parameters)
                    {
                        foreach (var t in Unwrap(parameter.Type)) yield return t;
                    }

                    break;
            }
        }

        static IEnumerable<ITypeSymbol> Unwrap(ITypeSymbol type)
        {
            switch (type)
            {
                case IArrayTypeSymbol array:
                    foreach (var t in Unwrap(array.ElementType)) yield return t;
                    break;

                case INamedTypeSymbol { IsGenericType: true } generic:
                    // A tuple is unwrapped into its ELEMENTS and never emitted itself. Indexing a
                    // real repository put "(T1, T2)" and "(T1, T2, T3)" among the most-connected
                    // nodes in the graph — the unbound display form of ValueTuple, which is a
                    // language construct rather than anything a user would navigate to.
                    if (!generic.IsTupleType && !IsNoise(generic))
                    {
                        yield return generic.ConstructedFrom;
                    }

                    foreach (var argument in generic.TypeArguments)
                    {
                        foreach (var t in Unwrap(argument)) yield return t;
                    }

                    break;

                default:
                    if (IsNoise(type)) break;
                    yield return type;
                    break;
            }
        }
    }

    /// <summary>
    /// Types that are language machinery rather than anything a user would navigate to.
    /// </summary>
    /// <remarks>
    /// Found by indexing someone else's repository: <c>void</c>, type parameters and tuples are
    /// everywhere, so as nodes they become the highest-degree things in the graph while meaning
    /// nothing. Their type ARGUMENTS still produce edges — a method returning
    /// <c>(Order, Customer)</c> depends on both.
    /// </remarks>
    private static bool IsNoise(ITypeSymbol type) =>
        !Resolved(type) ||
        type.SpecialType == SpecialType.System_Void ||
        type.TypeKind == TypeKind.TypeParameter ||
        type.TypeKind == TypeKind.Dynamic ||
        type is INamedTypeSymbol { IsTupleType: true } ||
        string.IsNullOrEmpty(type.Name);

    /// <summary>
    /// Entity-to-table mappings stated with the Fluent API, across the whole compilation.
    /// </summary>
    /// <remarks>
    /// <para><b>Resolved SEMANTICALLY, because the syntax chain only ever saw one of the styles.</b>
    /// The previous reader matched <c>Entity&lt;T&gt;()...ToTable("x")</c> as a single expression, so
    /// it found nothing whenever the builder was bound to a local first — which is the commonest way
    /// the API is actually used:</para>
    /// <code>
    /// var terrace = modelBuilder.Entity&lt;Terrace&gt;();
    /// terrace.ToTable("Terrace", "setup");
    /// </code>
    /// <para>MEASURED on a real repository: <b>1 verified join against 123 inferred</b>, on a
    /// codebase that declares its mappings outright. Every one of those guesses had a stated answer
    /// sitting in <c>OnModelCreating</c>. Asking the semantic model for the RECEIVER's type answers
    /// all the styles with one rule — chained, local-variable, lambda-configuration, and
    /// <c>IEntityTypeConfiguration&lt;T&gt;</c> — because in every one of them the receiver is an
    /// <c>EntityTypeBuilder&lt;TEntity&gt;</c>.</para>
    ///
    /// <para><b>It also fixes the name the edge is keyed on.</b> The syntax path took the type
    /// argument AS WRITTEN, so it produced <c>Order</c> where every other assertion about that type
    /// says <c>Shop.Order</c> — an edge whose subject matches no node in the graph. A symbol's
    /// display string is the same name the rest of this extractor emits.</para>
    ///
    /// <para><b>And it excludes the migration snapshots for free.</b> EF's generated
    /// <c>*.Designer.cs</c> files call <c>ToTable</c> through the NON-generic builder
    /// (<c>modelBuilder.Entity("Some.Type.Name")</c>), so there is no type argument to resolve and
    /// they yield nothing — correct twice over, because they are historical snapshots and a table
    /// renamed three migrations ago would otherwise be asserted as current fact.</para>
    ///
    /// <para><b>Only literal names.</b> A table name built from a variable or a constant is not
    /// resolved — the same rule the Bicep reader follows, and for the same reason: a guessed name
    /// produces a confident wrong join between a class and a table.</para>
    /// </remarks>
    private static IEnumerable<(string Entity, string Table, Location Where)> FluentTableMappings(
        Compilation compilation, Action<int, int> counts, CancellationToken cancellationToken)
    {
        var unresolvedCount = 0;
        var generatedCount = 0;

        foreach (var tree in compilation.SyntaxTrees)
        {
            // The prefilter, and the reason this is affordable. A `ToTable` invocation cannot exist
            // in a file whose text does not contain "ToTable", so a substring scan over source
            // already in memory rules out every file that has none — MEASURED at 1ms across 465
            // files, against 217ms to walk the 66 that survive. A false positive (the word in a
            // comment) falls through to the walk below and finds nothing, so the prefilter can cost
            // time but never correctness.
            if (!tree.GetText().ToString().Contains("ToTable", StringComparison.Ordinal)) continue;

            // GENERATED files are skipped, on correctness grounds before performance ones. EF writes
            // a `*.Designer.cs` model snapshot per migration, and each one calls ToTable for every
            // entity AS IT STOOD AT THAT MIGRATION. Reading them asserts a table renamed three
            // migrations ago as current fact, with the same Verified badge as the live mapping — the
            // shape of DC-022, two producers of one predicate where one of them is describing the
            // past. MEASURED on a real repository: 63 of the 66 files that mention ToTable are
            // generated snapshots, they hold ~125,000 of the lines, and binding them cost 1.2s to
            // produce nothing that should be believed.
            if (IsGenerated(tree, cancellationToken))
            {
                generatedCount++;
                continue;
            }

            // Built lazily and once per tree: a semantic model is expensive to create and useless on
            // a file whose ToTable turns out to be a comment.
            SemanticModel? model = null;

            foreach (var call in tree.GetRoot().DescendantNodes()
                .OfType<Microsoft.CodeAnalysis.CSharp.Syntax.InvocationExpressionSyntax>())
            {
                if (call.Expression is not Microsoft.CodeAnalysis.CSharp.Syntax.MemberAccessExpressionSyntax member) continue;
                if (member.Name.Identifier.ValueText != "ToTable") continue;

                // The first string literal is the table name in every overload — ToTable(name),
                // ToTable(name, schema), ToTable(name, buildAction), ToTable(name, schema, action).
                var table = call.ArgumentList.Arguments
                    .Select(a => a.Expression)
                    .OfType<Microsoft.CodeAnalysis.CSharp.Syntax.LiteralExpressionSyntax>()
                    .FirstOrDefault(l => l.IsKind(Microsoft.CodeAnalysis.CSharp.SyntaxKind.StringLiteralExpression))
                    ?.Token.ValueText;

                if (string.IsNullOrEmpty(table)) continue;

                model ??= compilation.GetSemanticModel(tree);

                if (model.GetTypeInfo(member.Expression).Type is not INamedTypeSymbol receiver
                    || receiver.TypeKind == TypeKind.Error)
                {
                    // Packages not restored, most often. Counted and disclosed rather than guessed
                    // at from the syntax: a mapping recovered without the type is keyed on a name
                    // that matches no node, which is a dangling edge wearing a Verified badge.
                    unresolvedCount++;
                    continue;
                }

                if (!IsEntityBuilder(receiver)) continue;

                // EntityTypeBuilder<TEntity> has one argument; OwnedNavigationBuilder<TOwner,
                // TDependent> has two and the table belongs to the DEPENDENT. Last covers both.
                if (receiver.TypeArguments.LastOrDefault() is not { } entity || !Resolved(entity))
                {
                    unresolvedCount++;
                    continue;
                }

                yield return (entity.ToDisplayString(), table, call.GetLocation());
            }
        }

        counts(unresolvedCount, generatedCount);
    }

    /// <summary>
    /// What the call scan saw, split by what each outcome MEANS rather than by whether an edge came
    /// out of it.
    /// </summary>
    /// <remarks>
    /// <para><b>A boundary and a gap are different statements.</b> A call into the base class library
    /// is a thing this product declines to index; a call that did not resolve is a thing it meant to
    /// read and could not. Adding them together gives an arithmetically correct number that describes
    /// nothing, and DC-050 is the entry for what that costs — a session spent on a coverage hole that
    /// was 1% of what its number said.</para>
    ///
    /// <para><b>The three dispatch limits are counted separately for the same reason.</b> "The edge
    /// points at the declaring type, not at the override that runs", "something was assigned to this
    /// delegate and I cannot see what", and "this target is a runtime string" are three different
    /// admissions, and a reader deciding whether to trust a call path needs to know which one applies.</para>
    /// </remarks>
    internal sealed class CallCensus
    {
        /// <summary>Invocation expressions considered, in hand-written source.</summary>
        public int Sites { get; set; }

        /// <summary>Files skipped because they declare themselves generated.</summary>
        public int GeneratedFiles { get; set; }

        /// <summary>Calls whose target is not declared in any source this compilation can see.</summary>
        public int OutsideThisRepository { get; set; }

        /// <summary>Calls whose target the compiler could not bind at all.</summary>
        public int NotResolved { get; set; }

        /// <summary>Calls bound at runtime through <c>dynamic</c>.</summary>
        public int DynamicallyBound { get; set; }

        /// <summary>Calls that invoke a delegate; whatever was assigned to it is not visible.</summary>
        public int ThroughADelegate { get; set; }

        /// <summary>Calls that hand the target to the reflection APIs as a runtime value.</summary>
        public int ThroughReflection { get; set; }

        /// <summary>Calls written outside any type declaration, so nothing owns them.</summary>
        public int OutsideAnyType { get; set; }

        /// <summary>Calls whose target is declared in source. The raw candidate population.</summary>
        public int InThisRepository { get; set; }

        /// <summary>Of those, the ones whose implementation is chosen at runtime.</summary>
        public int DispatchedAtRuntime { get; set; }

        /// <summary>Of those, the ones where the caller and the callee are the same type.</summary>
        public int WithinOneType { get; set; }

        /// <summary>Distinct type pairs that became an edge.</summary>
        public int Edges { get; set; }

        /// <summary>
        /// What this scope could not see, one sentence each, only where there was something to say.
        /// </summary>
        /// <remarks>
        /// Every one is guarded on its own count. A disclosure that fires when nothing was hidden is
        /// how a reader learns to skip the disclosure list, which costs the honest ones too.
        /// </remarks>
        /// <summary>Folds another census into this one.</summary>
        /// <remarks>
        /// The walk runs one tree at a time on several threads, each counting into its own census —
        /// incrementing shared counters from several threads would lose counts silently, and a
        /// disclosure that under-reports is worse than none. Summing at the end is exact and needs
        /// no lock.
        /// </remarks>
        public void Add(CallCensus other)
        {
            ArgumentNullException.ThrowIfNull(other);

            Sites += other.Sites;
            GeneratedFiles += other.GeneratedFiles;
            OutsideThisRepository += other.OutsideThisRepository;
            NotResolved += other.NotResolved;
            DynamicallyBound += other.DynamicallyBound;
            ThroughADelegate += other.ThroughADelegate;
            ThroughReflection += other.ThroughReflection;
            OutsideAnyType += other.OutsideAnyType;
            InThisRepository += other.InThisRepository;
            DispatchedAtRuntime += other.DispatchedAtRuntime;
            WithinOneType += other.WithinOneType;
            Edges += other.Edges;
        }

        public IEnumerable<string> Disclosures()
        {
            // THE BOUNDARY, named as one. The C# reader has always declined to draw the runtime, and
            // the largest number here is the count of times it did so — 23,872 on TheTerrace, against
            // 10,451 calls that stayed inside the repository. A reader who sees no in-repository
            // edges from a wrapper class should be able to tell "it calls nothing" from "everything
            // it calls is somebody else's library".
            if (OutsideThisRepository > 0)
            {
                yield return $"calls-outside-this-repository ({OutsideThisRepository:N0} call(s) " +
                    "reach a type this product does not index, such as the base class library or a package)";
            }

            // THE GAP. Unlike the line above, this is something the reader meant to read and failed
            // to: packages not restored is the usual cause, and every one of these is an edge that
            // should exist and does not.
            if (NotResolved > 0)
            {
                yield return $"calls-not-resolved ({NotResolved:N0} invocation(s) whose target the " +
                    "compiler could not bind; packages not restored is the usual cause)";
            }

            // THE LIMITS — three of them, each a different thing a compiler cannot tell you.
            if (DispatchedAtRuntime > 0)
            {
                yield return $"calls-dispatched-at-runtime ({DispatchedAtRuntime:N0} call(s) name a " +
                    "virtual, abstract or interface member; the edge is to the type that DECLARES it, " +
                    "not to the implementation that runs)";
            }

            if (ThroughADelegate > 0)
            {
                yield return $"calls-through-a-delegate ({ThroughADelegate:N0} invocation(s) call a " +
                    "delegate; what was assigned to it is not determined here and no edge is drawn)";
            }

            if (ThroughReflection > 0)
            {
                yield return $"calls-through-reflection ({ThroughReflection:N0} invocation(s) dispatch " +
                    "through the reflection APIs; the target is a runtime value and no edge is drawn)";
            }

            if (DynamicallyBound > 0)
            {
                yield return $"calls-dynamically-bound ({DynamicallyBound:N0} invocation(s) bind " +
                    "through `dynamic`; there is no compile-time target and no edge is drawn)";
            }

            // Top-level statements, most often. The call is real and there is no type to attribute it
            // to, which is a different thing from there being no call.
            if (OutsideAnyType > 0)
            {
                yield return $"calls-outside-a-type ({OutsideAnyType:N0} invocation(s) are written " +
                    "outside any type declaration, so there is no caller to attribute them to)";
            }

            // A type calling its own members is a true relation whose two ends are one node. It is
            // not drawn, and it is counted rather than passed over: MEASURED on TheTerrace it is
            // 5,484 of the 10,451 in-repository calls — the majority — so a silent drop here would
            // make "this graph shows the calls" a much smaller claim than it sounds.
            if (WithinOneType > 0)
            {
                yield return $"calls-within-one-type ({WithinOneType:N0} call(s) stay inside the type " +
                    "that made them; a self-edge is not drawn)";
            }

        }
    }

    /// <summary>
    /// The reflection entry points whose target is a runtime value rather than a symbol.
    /// </summary>
    /// <remarks>
    /// Named explicitly, and matched on the FULL name of the declaring type, because this is the
    /// over-matching direction of DC-033: a repository's own <c>Invoke</c> or <c>CreateInstance</c>
    /// is an ordinary method and must stay an ordinary edge. Deliberately a small list of the forms
    /// that actually appear — it is a count, not a security control, and a name missing from it is
    /// counted as an ordinary call to the runtime rather than lost.
    /// </remarks>
    private static readonly string[] ReflectionDispatch =
    [
        "System.Reflection.MethodBase.Invoke",
        "System.Reflection.MethodInfo.Invoke",
        "System.Reflection.ConstructorInfo.Invoke",
        "System.Type.InvokeMember",
        "System.Type.GetMethod",
        "System.Activator.CreateInstance",
        "System.Reflection.PropertyInfo.GetValue",
        "System.Reflection.PropertyInfo.SetValue",
    ];

    /// <summary>
    /// Which type calls which, across the whole compilation.
    /// </summary>
    /// <remarks>
    /// <para><b>Type-level, and the raw count is the reason.</b> The literal answer to "what calls
    /// this" is method-to-method, and it was measured before anything was built: TheTerrace's 10,451
    /// in-repository call sites deduplicate to <b>8,476 method pairs over 5,054 method nodes</b>.
    /// The graph payload for that workspace is already <b>969,323 bytes against a 1,048,576-byte
    /// frame</b>, and its bounded default view is 795,979 of the 917,504 a response may carry — so
    /// method nodes would roughly quadruple a payload with 8% of headroom, and the shrink-to-fit that
    /// caught INV-0003 and DC-047 would answer by omitting most of the workspace. Worse, the ranking
    /// that decides what survives is degree, and the highest-degree method in that repository is a
    /// test helper with 304 callers. A smaller true answer beats a larger unusable one.</para>
    ///
    /// <para><b>What type-level still buys, measured rather than assumed.</b> `depends_on` already
    /// exists at this granularity, so the honest question is whether this adds anything: of the 1,492
    /// type pairs, <b>only 415 are already `depends_on` and 1,077 are not</b>. A type depends on what
    /// it declares — fields, parameters, returns — and calls a great deal it never declares: static
    /// helpers, extension methods, factories, and services obtained from a container.</para>
    ///
    /// <para><b>Resolved semantically, never by name.</b> <c>GetSymbolInfo</c> gives the target the
    /// compiler bound, so an edge is Verified in the sense this codebase means it. An invocation that
    /// did not bind is not an edge — it is a count on the scope, for the same reason an unresolved
    /// type is not a <c>depends_on</c>.</para>
    ///
    /// <para><b>The runtime is not drawn.</b> A call whose target is declared in metadata rather than
    /// in source is counted as a boundary and never emitted, so the graph does not fill with
    /// <c>string</c>, <c>List&lt;T&gt;</c> and <c>ILogger</c>. Python and TypeScript were both
    /// corrected to this rule after the fact; it is applied here from the start.</para>
    ///
    /// <para><b>Generated files are skipped before they are bound.</b> They were 79,042 of
    /// TheTerrace's 114,406 invocations — 69% — and every one of them is EF describing a schema as it
    /// stood at a past migration. Skipping them is a correctness decision first and a 3x saving
    /// second.</para>
    /// </remarks>
    private static IEnumerable<(string Caller, string Callee, Location Where)> TypeCalls(
        Compilation compilation, CallCensus census,
        out List<(string Caller, string Callee, string Member, Location Where)> sites,
        CancellationToken cancellationToken)
    {
        // ONE TREE AT A TIME, ON SEVERAL THREADS.
        //
        // MEASURED on TheTerrace: indexing takes 5.8s with this walk removed and 15.5s with it, so
        // 9.7s is binding method bodies — the compiler doing the only work that can answer "what
        // calls this". There is no prefilter that avoids it honestly: skipping by name would fold
        // the boundary (calls into the runtime) into the gap (calls that did not bind), which is the
        // one distinction the disclosures exist to keep (DC-050).
        //
        // So the work is not reduced, it is overlapped. `Compilation.GetSemanticModel` is safe to
        // call from several threads and each model is then used by exactly one; the shared state
        // (the census counters, the emitted set) becomes per-thread and is folded afterwards.
        //
        // Determinism is the thing to be careful about, not correctness. The edges are a SET, so the
        // membership is identical however the trees are ordered — but the PROVENANCE is "the first
        // call site", and "first" in a parallel walk is whichever thread arrived first. So the merge
        // picks the smallest location by file path and then position, which is the same answer every
        // run and, on a single-threaded walk, the same answer as before.
        var perTree = new (CallCensus Census, List<(string Caller, string Callee, string Member, Location Where)> Found)[
            compilation.SyntaxTrees.Count()];

        var trees = compilation.SyntaxTrees.ToArray();

        Parallel.For(0, trees.Length, new ParallelOptions { CancellationToken = cancellationToken }, i =>
        {
            var local = new CallCensus();
            var found = new List<(string Caller, string Callee, string Member, Location Where)>();
            perTree[i] = (local, found);

            WalkOneTree(compilation, trees[i], local, found, cancellationToken);
        });

        foreach (var (local, _) in perTree) census.Add(local);

        // Deduplicated HERE rather than by ExtractionFacts.Distinct at the end, because the raw
        // population is 10,451 call sites for 1,492 edges: building seven times more assertions than
        // survive is measurable waste in the hot path of the largest scope.
        //
        // `Edges` is re-derived from the merged set rather than summed: two trees can each be the
        // first to see the same pair, and summing would count that edge twice in a disclosure.
        var emitted = new Dictionary<(string, string), Location>();

        foreach (var (caller, callee, _, where) in perTree.SelectMany(t => t.Found))
        {
            if (!emitted.TryGetValue((caller, callee), out var existing) || Earlier(where, existing))
            {
                emitted[(caller, callee)] = where;
            }
        }

        census.Edges = emitted.Count;

        // EVERY SITE, ordered, alongside the deduplicated edges.
        //
        // The dedup is right for the GRAPH: `Order -> Customer` is one relationship however many
        // times it is written, and drawing it seven times is seven identical arrows. It is wrong for
        // an INTERACTION: `A -> B, A -> C, A -> B` collapses to two messages, and a sequence diagram
        // that silently drops a repeated call is worse than no diagram, because it is confidently
        // incomplete.
        //
        // Ordered by location here, once, rather than by every reader: a call sequence has exactly
        // one correct order and it is the order it is written in.
        sites = [.. perTree
            .SelectMany(t => t.Found)
            .OrderBy(f => f.Caller, StringComparer.Ordinal)
            .ThenBy(f => f.Where.SourceTree?.FilePath ?? string.Empty, StringComparer.Ordinal)
            .ThenBy(f => f.Where.SourceSpan.Start)];

        return emitted
            .OrderBy(e => e.Key.Item1, StringComparer.Ordinal)
            .ThenBy(e => e.Key.Item2, StringComparer.Ordinal)
            .Select(e => (e.Key.Item1, e.Key.Item2, e.Value));
    }

    /// <summary>Which of two call sites a reader should be sent to — the same one on every run.</summary>
    private static bool Earlier(Location candidate, Location incumbent)
    {
        var byFile = string.CompareOrdinal(
            candidate.SourceTree?.FilePath ?? string.Empty,
            incumbent.SourceTree?.FilePath ?? string.Empty);

        return byFile != 0
            ? byFile < 0
            : candidate.SourceSpan.Start < incumbent.SourceSpan.Start;
    }

    /// <summary>The call sites in one file, counted and collected into this thread's own state.</summary>
    private static void WalkOneTree(
        Compilation compilation,
        SyntaxTree tree,
        CallCensus census,
        List<(string Caller, string Callee, string Member, Location Where)> found,
        CancellationToken cancellationToken)
    {
        {
            cancellationToken.ThrowIfCancellationRequested();

            if (IsGenerated(tree, cancellationToken))
            {
                census.GeneratedFiles++;
                return;
            }

            // Built lazily: a file with no invocation at all never needs a semantic model, and
            // creating one binds every method body in it.
            SemanticModel? model = null;

            // One `GetDeclaredSymbol` per type declaration rather than per call site. A file with a
            // thousand calls in one class asked the same question a thousand times.
            var owners = new Dictionary<Microsoft.CodeAnalysis.CSharp.Syntax.TypeDeclarationSyntax,
                INamedTypeSymbol?>();

            foreach (var call in tree.GetRoot(cancellationToken).DescendantNodes()
                .OfType<Microsoft.CodeAnalysis.CSharp.Syntax.InvocationExpressionSyntax>())
            {
                census.Sites++;

                // The INNERMOST enclosing type, matching what `SqlTableUsage` already attributes to.
                // A call inside a lambda, a local function or a field initializer belongs to the type
                // the lambda was written in, which is the thing the graph can show.
                var declaration = call.Ancestors()
                    .OfType<Microsoft.CodeAnalysis.CSharp.Syntax.TypeDeclarationSyntax>()
                    .FirstOrDefault();

                if (declaration is null)
                {
                    census.OutsideAnyType++;
                    continue;
                }

                model ??= compilation.GetSemanticModel(tree);

                var info = model.GetSymbolInfo(call, cancellationToken);

                if (info.Symbol is not IMethodSymbol target)
                {
                    // `dynamic` is a different admission from "this did not compile": one is a
                    // language feature working as designed, the other is a picture with holes in it.
                    if (info.CandidateReason == CandidateReason.LateBound) census.DynamicallyBound++;
                    else census.NotResolved++;
                    continue;
                }

                // The ORIGINAL definition, so `Repository<Order>.Find` and `Repository<Customer>.Find`
                // are the same callee and the name matches the one `has_type` emits for the type —
                // `Repository<T>`. The alternative is edges whose object matches no node, which is
                // the half of DC-033 that got through review.
                var definition = target.OriginalDefinition;

                if (definition.MethodKind == MethodKind.DelegateInvoke)
                {
                    // The delegate's own Invoke is a real symbol and a useless edge: it names the
                    // delegate TYPE, not whatever method was assigned to it, which is the thing a
                    // reader asking "what calls this" wants and nothing here can see.
                    census.ThroughADelegate++;
                    continue;
                }

                if (IsReflectionDispatch(definition))
                {
                    census.ThroughReflection++;
                    continue;
                }

                if (definition.ContainingType is not { } calleeType
                    || !Resolved(calleeType)
                    || calleeType.DeclaringSyntaxReferences.Length == 0)
                {
                    // Declared in metadata, so it is the runtime or a package. A boundary, counted.
                    census.OutsideThisRepository++;
                    continue;
                }

                census.InThisRepository++;

                if (calleeType.TypeKind == TypeKind.Interface
                    || definition.IsVirtual || definition.IsAbstract || definition.IsOverride)
                {
                    // The edge is still drawn and still true — the call names this member. What is
                    // not knowable here is which override answers it, and that is what is disclosed.
                    census.DispatchedAtRuntime++;
                }

                if (!owners.TryGetValue(declaration, out var callerType))
                {
                    owners[declaration] = callerType =
                        model.GetDeclaredSymbol(declaration, cancellationToken) as INamedTypeSymbol;
                }

                if (callerType is null)
                {
                    // Not counted and not disclosed, deliberately. `GetDeclaredSymbol` on a type
                    // declaration is nullable by signature, and no input this codebase could
                    // construct makes it return null — two classes of the same name in one namespace
                    // both resolve, which was the likeliest candidate and was tried. A disclosure
                    // whose branch cannot be reached certifies rather than checks (DC-016), so the
                    // guard stays and the machinery around it does not.
                    continue;
                }

                var caller = callerType.ToDisplayString();
                var callee = calleeType.ToDisplayString();

                // The called MEMBER, which this walk used to compute and discard. A sequence diagram
                // draws messages, and a message with no name is an arrow: `Order -> Customer` says
                // almost nothing where `Order -> Customer.Save()` says the thing you opened the
                // diagram to find out. It costs one property read on a symbol already in hand.
                var member = definition.Name;

                if (string.Equals(caller, callee, StringComparison.Ordinal))
                {
                    // A self-edge answers no question: "what calls this type" is asked to find the
                    // OTHER things, and a type's own members are already listed on it. Counted, not
                    // silently dropped — on TheTerrace it is the majority of in-repository calls.
                    census.WithinOneType++;
                    continue;
                }

                // Collected, not yet deduplicated: which pair a thread sees first is a property of
                // the scheduler, so the choice of call site is made once, afterwards, in the merge.
                found.Add((caller, callee, member, call.GetLocation()));
            }
        }
    }

    /// <summary>Whether a method hands its real target to the runtime as a value.</summary>
    private static bool IsReflectionDispatch(IMethodSymbol method)
    {
        if (method.ContainingType is not { } type) return false;

        var name = type.ToDisplayString() + "." + method.Name;

        foreach (var known in ReflectionDispatch)
        {
            if (string.Equals(name, known, StringComparison.Ordinal)) return true;
        }

        return false;
    }

    /// <summary>The verbs a SQL statement can begin with.</summary>
    private static readonly string[] SqlVerbs =
        ["SELECT", "INSERT", "UPDATE", "DELETE", "MERGE", "WITH"];

    /// <summary>
    /// Whether a string literal is a SQL statement rather than a sentence that mentions one.
    /// </summary>
    /// <remarks>
    /// <para><b>The gate the first version of this reader did not have.</b> Without it,
    /// <c>UPDATE\s+(\w+)</c> matches the sentence "update the record" and emits an edge to a table
    /// called <c>the</c>. MEASURED on a real repository: 63 prose strings would have produced a
    /// confident wrong edge alongside the genuine ones.</para>
    ///
    /// <para><b>Written as a loop rather than a regex, deliberately.</b> The regex form of this test
    /// — <c>(?:^|;)\s*(?:SELECT|INSERT\s+INTO|…)</c> — silently returned false for
    /// <c>"INSERT INTO dbo.AssessmentJob (…)"</c>, a string that plainly begins with one of its own
    /// alternatives, and cost more to diagnose than the check is worth. A statement begins after the
    /// start of the string or after a semicolon; that is three lines of code that can be read and
    /// believed.</para>
    /// </remarks>
    internal static bool LooksLikeSql(string text)
    {
        foreach (var start in Starts(text))
        {
            var rest = text[start..].TrimStart();

            foreach (var verb in SqlVerbs)
            {
                if (rest.StartsWith(verb, StringComparison.OrdinalIgnoreCase)
                    && (rest.Length == verb.Length || char.IsWhiteSpace(rest[verb.Length])))
                {
                    return true;
                }
            }
        }

        return false;

        // The start of the string, and after every statement separator in it: one literal often
        // carries several statements, and only the first would otherwise be considered.
        static IEnumerable<int> Starts(string text)
        {
            yield return 0;

            for (var i = 0; i < text.Length; i++)
            {
                if (text[i] == ';') yield return i + 1;
            }
        }
    }

    // The table a statement names. Only the forms whose next token IS a table: a FROM, a JOIN, an
    // INSERT INTO or an UPDATE. `SELECT x FROM (SELECT ...)` yields nothing rather than a guess.
    private static readonly Regex SqlTableReference = new(
        @"\b(?:FROM|JOIN|INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+"
        + @"(?<table>(?:\[[^\]]+\]|[A-Za-z_][\w$]*)(?:\s*\.\s*(?:\[[^\]]+\]|[A-Za-z_][\w$]*))*)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    /// <summary>
    /// Types that issue SQL naming a table, and which table.
    /// </summary>
    /// <remarks>
    /// <para><b>Usage, not mapping.</b> This answers "which code talks to this table", which is the
    /// question a reader of an ORM-free repository actually has and the only one its source
    /// declares. It is <c>uses_table</c> rather than <c>maps_to</c> on purpose: a store class
    /// issuing four statements against three tables is mapped to none of them.</para>
    ///
    /// <para><b>Literals only, and the same prefilter as the fluent scan.</b> A table name built at
    /// runtime is not resolved, because a guessed name produces a confident wrong edge; a file whose
    /// text contains none of the SQL keywords is skipped without materialising its syntax.</para>
    /// </remarks>
    private static IEnumerable<(string Type, string Table, Location Where)> SqlTableUsage(
        Compilation compilation, CancellationToken cancellationToken)
    {
        foreach (var tree in compilation.SyntaxTrees)
        {
            var text = tree.GetText().ToString();

            if (text.IndexOf("FROM", StringComparison.OrdinalIgnoreCase) < 0
                && text.IndexOf("INSERT", StringComparison.OrdinalIgnoreCase) < 0
                && text.IndexOf("UPDATE", StringComparison.OrdinalIgnoreCase) < 0)
            {
                continue;
            }

            if (IsGenerated(tree, cancellationToken)) continue;

            SemanticModel? model = null;

            foreach (var literal in tree.GetRoot(cancellationToken).DescendantNodes()
                .OfType<Microsoft.CodeAnalysis.CSharp.Syntax.LiteralExpressionSyntax>())
            {
                if (!literal.IsKind(Microsoft.CodeAnalysis.CSharp.SyntaxKind.StringLiteralExpression)) continue;

                // THE WHOLE STATEMENT, not the fragment. Real code splits SQL across concatenated
                // literals — `"SELECT ... " + "FROM dbo.AssessmentJob;"` — and the piece holding the
                // table does not begin with a verb. Reading fragments individually is how the first
                // version of this reader matched the sentence "update the record" and emitted an
                // edge to a table called `the`; reading them individually and THEN demanding a verb
                // found nothing at all on the repository that motivated it. The concatenation is one
                // constant, so it is read as one.
                var expression = Outermost(literal);

                // Only once per concatenation: every literal in the chain has the same outermost.
                if (!ReferenceEquals(expression, literal)
                    && !literal.Equals(FirstLiteralIn(expression)))
                {
                    continue;
                }

                // Joined from the literals themselves rather than through the semantic model. The
                // model's constant folding needs a resolved compilation, and it returns nothing on a
                // project whose packages are not restored — which is most projects on a fresh clone,
                // and was every fixture in this file's own tests. A chain of string literals is a
                // constant by inspection.
                if (Concatenated(expression) is not { } value) continue;

                // Shape first, keywords second. The other order is how prose becomes a schema.
                if (!LooksLikeSql(value)) continue;

                var matches = SqlTableReference.Matches(value);
                if (matches.Count == 0) continue;

                // The type this literal is written inside. A statement outside any type — a
                // top-level program — has nothing to attribute the usage to and is skipped.
                var declaration = literal.Ancestors()
                    .OfType<Microsoft.CodeAnalysis.CSharp.Syntax.TypeDeclarationSyntax>()
                    .FirstOrDefault();

                if (declaration is null) continue;

                // The model is needed only to name the OWNING TYPE, and only once the literal has
                // already proved itself SQL — so it is built for a file that has some, and never for
                // one that merely mentions the word FROM.
                model ??= compilation.GetSemanticModel(tree);

                if (model.GetDeclaredSymbol(declaration, cancellationToken) is not INamedTypeSymbol owner) continue;

                var subject = owner.ToDisplayString();

                foreach (Match match in matches)
                {
                    var table = TableName(match.Groups["table"].Value);

                    // An alias, a table variable or a CTE is not a table in the schema graph.
                    if (table.Length == 0 || table.StartsWith('@') || table.StartsWith('#')) continue;

                    // A real table reference ENDS somewhere a clause can begin. "delete from your
                    // account to remove it" begins with a verb, so the statement-shape test passes
                    // it, and `your` became a table — found by the shared invent-rate control. In
                    // SQL the token after a table is a clause keyword, a punctuation mark, or
                    // nothing; in prose it is another ordinary word.
                    if (!EndsLikeATableReference(value, match.Index + match.Length)) continue;

                    yield return (subject, table, literal.GetLocation());
                }
            }
        }
    }

    /// <summary>
    /// The text of a chain of string literals, or null when anything else is in it.
    /// </summary>
    /// <remarks>
    /// A chain containing an identifier or a call cannot be read here, and is not guessed at: a name
    /// assembled at runtime is exactly the case the literal-only rule exists to exclude. Returning
    /// null for it means the statement is skipped whole rather than half-read into a wrong table.
    /// </remarks>
    private static string? Concatenated(Microsoft.CodeAnalysis.CSharp.Syntax.ExpressionSyntax expression)
    {
        if (expression is Microsoft.CodeAnalysis.CSharp.Syntax.LiteralExpressionSyntax single)
        {
            return single.IsKind(Microsoft.CodeAnalysis.CSharp.SyntaxKind.StringLiteralExpression)
                ? single.Token.ValueText
                : null;
        }

        if (expression is not Microsoft.CodeAnalysis.CSharp.Syntax.BinaryExpressionSyntax binary
            || !binary.IsKind(Microsoft.CodeAnalysis.CSharp.SyntaxKind.AddExpression))
        {
            return null;
        }

        return Concatenated(binary.Left) is { } left && Concatenated(binary.Right) is { } right
            ? left + right
            : null;
    }

    /// <summary>What may legitimately follow a table name in a statement.</summary>
    private static readonly string[] ClauseKeywords =
    [
        "WHERE", "SET", "VALUES", "ORDER", "GROUP", "HAVING", "JOIN", "ON", "INNER", "LEFT",
        "RIGHT", "OUTER", "CROSS", "UNION", "AS", "SELECT", "OPTION", "OUTPUT", "OFFSET", "OOOO",
    ];

    /// <summary>
    /// Whether what follows a matched table name looks like SQL rather than the next word of a
    /// sentence.
    /// </summary>
    /// <remarks>
    /// The second half of the prose gate. Beginning with a verb is not enough — <c>"delete from your
    /// account to remove it"</c> does. But a table name is the end of a phrase: what follows is a
    /// clause keyword, punctuation, or the end of the statement. Another bare word is prose.
    /// </remarks>
    private static bool EndsLikeATableReference(string text, int after)
    {
        var rest = text[Math.Min(after, text.Length)..].TrimStart();

        if (rest.Length == 0) return true;

        // Punctuation ends the reference: `;`, `(`, `)`, `,` — and an alias-free statement often
        // ends at one of them.
        if (!char.IsLetter(rest[0])) return true;

        foreach (var keyword in ClauseKeywords)
        {
            if (rest.StartsWith(keyword, StringComparison.OrdinalIgnoreCase)
                && (rest.Length == keyword.Length || !char.IsLetterOrDigit(rest[keyword.Length])))
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>The whole constant expression a literal belongs to, following `+` chains upward.</summary>
    private static Microsoft.CodeAnalysis.CSharp.Syntax.ExpressionSyntax Outermost(
        Microsoft.CodeAnalysis.CSharp.Syntax.ExpressionSyntax expression)
    {
        while (expression.Parent is Microsoft.CodeAnalysis.CSharp.Syntax.BinaryExpressionSyntax binary
            && binary.IsKind(Microsoft.CodeAnalysis.CSharp.SyntaxKind.AddExpression))
        {
            expression = binary;
        }

        return expression;
    }

    /// <summary>The first string literal inside an expression, so a chain is handled exactly once.</summary>
    private static Microsoft.CodeAnalysis.CSharp.Syntax.LiteralExpressionSyntax? FirstLiteralIn(
        Microsoft.CodeAnalysis.CSharp.Syntax.ExpressionSyntax expression) =>
        expression.DescendantNodesAndSelf()
            .OfType<Microsoft.CodeAnalysis.CSharp.Syntax.LiteralExpressionSyntax>()
            .FirstOrDefault(l => l.IsKind(Microsoft.CodeAnalysis.CSharp.SyntaxKind.StringLiteralExpression));

    /// <summary>
    /// The bare table name, matching the spelling the schema readers emit.
    /// </summary>
    /// <remarks>
    /// The schema qualifier is dropped so <c>dbo.Workspace</c> and <c>Workspace</c> are one node —
    /// the EF and SQL readers both emit unqualified names, and a third spelling would leave these
    /// edges pointing at nodes that do not exist while looking perfectly correct.
    /// </remarks>
    private static string TableName(string raw) =>
        raw.Split('.')[^1].Trim().Trim('[', ']', ' ');

    /// <summary>
    /// Whether every file that declares this type is generated.
    /// </summary>
    /// <remarks>
    /// <para><b>EVERY file, not any.</b> A partial class split across a generated part and a
    /// hand-written one is real code that a person maintains — a WPF window is
    /// <c>MainWindow.g.cs</c> plus <c>MainWindow.xaml.cs</c>, and dropping it because half of it was
    /// generated would delete the window from the graph. The type is excluded only when there is no
    /// hand-written declaration of it anywhere.</para>
    ///
    /// <para>A type with no declaring syntax at all is kept: that is a symbol from metadata, and
    /// absence of evidence is not evidence of generation.</para>
    /// </remarks>
    private static bool IsGeneratedType(INamedTypeSymbol type, CancellationToken cancellationToken)
    {
        var references = type.DeclaringSyntaxReferences;
        if (references.Length == 0) return false;

        foreach (var reference in references)
        {
            if (!IsGenerated(reference.SyntaxTree, cancellationToken)) return false;
        }

        return true;
    }

    /// <summary>
    /// Whether a file declares itself generated, by the standard .NET convention.
    /// </summary>
    /// <remarks>
    /// The rule Roslyn's own analyzers use: an <c>&lt;auto-generated&gt;</c> marker in the file's
    /// FIRST comment block. Deliberately not an EF-specific test — a designer file, a protobuf stub
    /// and a source-generator output are all code nobody wrote and nobody can fix, and a fact read
    /// out of one describes the generator rather than the codebase.
    /// </remarks>
    private static bool IsGenerated(SyntaxTree tree, CancellationToken cancellationToken)
    {
        foreach (var trivia in tree.GetRoot(cancellationToken).GetLeadingTrivia())
        {
            if (!trivia.IsKind(Microsoft.CodeAnalysis.CSharp.SyntaxKind.SingleLineCommentTrivia)
                && !trivia.IsKind(Microsoft.CodeAnalysis.CSharp.SyntaxKind.MultiLineCommentTrivia))
            {
                continue;
            }

            var text = trivia.ToString();

            if (text.Contains("<auto-generated", StringComparison.OrdinalIgnoreCase)) return true;

            // Only the leading comment block counts. A file that MENTIONS auto-generation further
            // down — a comment about a generator, this very rule quoted in a test — is not itself
            // generated, and treating it as such would silently drop real declarations.
            return false;
        }

        return false;
    }

    /// <summary>
    /// Whether a receiver is one of EF's entity builders.
    /// </summary>
    /// <remarks>
    /// Named explicitly rather than accepting any generic type carrying a <c>ToTable</c> member:
    /// this reads a specific library's declaration, and an unrelated <c>ToTable</c> — a DataTable
    /// helper, a report formatter — is not a statement about persistence.
    /// </remarks>
    private static bool IsEntityBuilder(INamedTypeSymbol type) =>
        type.IsGenericType && type.Name is "EntityTypeBuilder" or "OwnedNavigationBuilder";

    private static void Walk(INamespaceSymbol ns, List<INamedTypeSymbol> into)
    {
        foreach (var type in ns.GetTypeMembers()) into.Add(type);
        foreach (var child in ns.GetNamespaceMembers()) Walk(child, into);
    }
}
