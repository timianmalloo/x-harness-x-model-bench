using AiDe.Core.Mcp;
using AiDe.Core.Presentation;

namespace AiDe.Core.Tests;

/// <summary>
/// The advertised MCP tool list is the gateway's, not a copy of it.
/// </summary>
/// <remarks>
/// <para><b>What it said and what was true.</b> <c>McpToolGatewayNames</c> was a hand-written
/// <c>["describe", "impact", "find", "knowledge"]</c>. <c>impact</c> and <c>knowledge</c> are daemon
/// IPC operations and have never been gateway tools; <c>standing</c>, added for US-16, was missing.
/// Three of five entries were wrong, and the surface reading it told an operator about two tools
/// that do not exist.</para>
///
/// <para><b>The shape, not the typo.</b> A second authority on what a component exposes drifts from
/// it — that is DC-021, and the fix is derivation rather than correction. Correcting the literal
/// would have made it right today and wrong at the next tool.</para>
/// </remarks>
public sealed class McpToolNamesAreDerivedTests
{
    private static IReadOnlyList<string> GatewayMethods() =>
        [.. typeof(McpToolGateway)
            .GetMethods(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance)
            .Where(m => m.ReturnType == typeof(McpToolResult))
            .Select(m => m.Name.ToLowerInvariant())];

    [Fact]
    public void EveryAdvertisedToolIsAGatewayMethod()
    {
        // The direction that misled an operator: names advertised that nothing implements.
        var invented = WorkspaceDiagnosticsViewModel.McpToolGatewayNames
            .Except(GatewayMethods(), StringComparer.Ordinal)
            .ToList();

        Assert.True(invented.Count == 0,
            "these tools are advertised in diagnostics and are not methods on the gateway, so an "
            + "operator is told about a capability that does not exist: " + string.Join(", ", invented));
    }

    [Fact]
    public void EveryGatewayMethodIsAdvertised()
    {
        // The other direction, and the one a hand-written list fails silently: a tool that exists
        // and is never mentioned. `standing` was in exactly this state.
        var hidden = GatewayMethods()
            .Except(WorkspaceDiagnosticsViewModel.McpToolGatewayNames, StringComparer.Ordinal)
            .ToList();

        Assert.True(hidden.Count == 0,
            "these gateway tools exist and are not advertised anywhere an operator can see: "
            + string.Join(", ", hidden));
    }

    [Fact]
    public void TheListIsNotEmpty()
    {
        // The DC-016 guard. Both assertions above are satisfied by two empty sets, which is exactly
        // what a reflection query that stopped matching would produce.
        Assert.NotEmpty(WorkspaceDiagnosticsViewModel.McpToolGatewayNames);
        Assert.Contains("standing", WorkspaceDiagnosticsViewModel.McpToolGatewayNames);
    }
}
