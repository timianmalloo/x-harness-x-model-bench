using System.Text.Json;
using AiDe.Core.Ipc;

namespace AiDe.Core.Tests;

/// <summary>
/// Writing and reading IPC payloads in tests, now that a payload is JSON rather than text.
/// </summary>
/// <remarks>
/// Version 3 carries the payload as a JSON value instead of a string containing JSON, so the
/// transport no longer escapes it twice (DC-047). These keep the tests reading as they did — a test
/// that says <c>Json("pong")</c> and <c>.AsText()</c> is still talking about a payload, not about a
/// serializer.
/// </remarks>
internal static class IpcPayloadTestExtensions
{
    private static readonly JsonSerializerOptions Wire = new(JsonSerializerDefaults.Web);

    /// <summary>A value as a payload.</summary>
    public static JsonElement Json<T>(T value) => JsonSerializer.SerializeToElement(value, Wire);

    /// <summary>A string payload's text, or null. Fails loudly on a payload that is not a string.</summary>
    public static string? AsText(this JsonElement? payload) =>
        payload is not { } element ? null
            : element.ValueKind == JsonValueKind.String ? element.GetString()
            : element.GetRawText();

    public static T? As<T>(this JsonElement? payload) => IpcPayload.Read<T>(payload, Wire);
}
