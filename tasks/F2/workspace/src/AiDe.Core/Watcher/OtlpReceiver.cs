using System.Net;
using System.Text;
using System.Text.Json;

namespace AiDe.Core.Watcher;

/// <summary>
/// Parses an OTLP/HTTP export in JSON encoding into <see cref="HarnessSpan"/>s, stdlib only (no protobuf
/// dependency - the harness is configured <c>OTEL_EXPORTER_OTLP_PROTOCOL=http/json</c>; slice-1b spike).
/// Resource and span attributes are merged per span. Malformed JSON yields an empty list, never throws.
/// </summary>
public static class OtlpJsonParser
{
    public static IReadOnlyList<HarnessSpan> Parse(string otlpJson)
    {
        if (string.IsNullOrWhiteSpace(otlpJson))
        {
            return [];
        }

        JsonDocument doc;
        try
        {
            doc = JsonDocument.Parse(otlpJson);
        }
        catch (JsonException)
        {
            return [];
        }

        using (doc)
        {
            var result = new List<HarnessSpan>();
            if (!doc.RootElement.TryGetProperty("resourceSpans", out var resourceSpans)
                || resourceSpans.ValueKind != JsonValueKind.Array)
            {
                return result;
            }

            foreach (var rs in resourceSpans.EnumerateArray())
            {
                var resourceAttrs = rs.TryGetProperty("resource", out var resource)
                    ? ReadAttributes(resource)
                    : new Dictionary<string, string?>(StringComparer.Ordinal);

                if (!rs.TryGetProperty("scopeSpans", out var scopeSpans) || scopeSpans.ValueKind != JsonValueKind.Array)
                {
                    continue;
                }

                foreach (var ss in scopeSpans.EnumerateArray())
                {
                    if (!ss.TryGetProperty("spans", out var spans) || spans.ValueKind != JsonValueKind.Array)
                    {
                        continue;
                    }

                    foreach (var span in spans.EnumerateArray())
                    {
                        var attrs = new Dictionary<string, string?>(resourceAttrs, StringComparer.Ordinal);
                        foreach (var (k, v) in ReadAttributeArray(span))
                        {
                            attrs[k] = v;
                        }

                        result.Add(new HarnessSpan(
                            GetString(span, "traceId") ?? "",
                            GetString(span, "spanId") ?? "",
                            GetString(span, "name") ?? "",
                            attrs));
                    }
                }
            }

            return result;
        }
    }

    private static Dictionary<string, string?> ReadAttributes(JsonElement element)
    {
        var attrs = new Dictionary<string, string?>(StringComparer.Ordinal);
        foreach (var (k, v) in ReadAttributeArray(element))
        {
            attrs[k] = v;
        }

        return attrs;
    }

    private static IEnumerable<(string Key, string? Value)> ReadAttributeArray(JsonElement element)
    {
        if (!element.TryGetProperty("attributes", out var attributes) || attributes.ValueKind != JsonValueKind.Array)
        {
            yield break;
        }

        foreach (var attr in attributes.EnumerateArray())
        {
            var key = GetString(attr, "key");
            if (key is null)
            {
                continue;
            }

            string? value = null;
            if (attr.TryGetProperty("value", out var v) && v.TryGetProperty("stringValue", out var s)
                && s.ValueKind == JsonValueKind.String)
            {
                value = s.GetString();
            }

            yield return (key, value);
        }
    }

    private static string? GetString(JsonElement element, string property)
        => element.TryGetProperty(property, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;
}

/// <summary>Resolves a per-session bearer token to the session's capability. Unknown token => null.</summary>
public interface ISessionTokenResolver
{
    SessionCapability? Resolve(string token);
}

/// <summary>An in-memory token->capability registry the registration flow populates.</summary>
public sealed class SessionTokenRegistry : ISessionTokenResolver
{
    private readonly Dictionary<string, SessionCapability> _byToken = new(StringComparer.Ordinal);
    private readonly object _gate = new();

    public void Register(string token, SessionCapability capability)
    {
        ArgumentException.ThrowIfNullOrEmpty(token);
        ArgumentNullException.ThrowIfNull(capability);
        lock (_gate)
        {
            _byToken[token] = capability;
        }
    }

    public SessionCapability? Resolve(string token)
    {
        lock (_gate)
        {
            return _byToken.TryGetValue(token, out var cap) ? cap : null;
        }
    }
}

/// <summary>A snapshot of the receiver counters (IO1 operator questions).</summary>
public sealed record OtlpReceiverStats(long Received, long Unauthenticated, long Rejected);

/// <summary>
/// A loopback-only OTLP/HTTP receiver: it accepts OTLP/JSON exports at <c>/v1/traces</c>, resolves the
/// per-session bearer token to a capability, parses spans, and enqueues them into the ingest host. A
/// bad body, oversize body, or unknown token is counted and dropped - never enqueued, never fatal
/// (the exporter is answered 200 so it does not retry a permanent error).
///
/// Pattern: Adapter over the ingest host's port. The capability never travels; only the opaque token does.
/// </summary>
public sealed class OtlpHttpReceiver : IDisposable
{
    private const string TokenHeader = "x-loomkeeper-session-token";

    private readonly IngestHost _host;
    private readonly ISessionTokenResolver _tokens;
    private readonly HttpListener _listener;
    private readonly int _maxBodyBytes;

    private long _received;
    private long _unauthenticated;
    private long _rejected;
    private bool _disposed;

    public OtlpHttpReceiver(IngestHost host, ISessionTokenResolver tokens, string loopbackPrefix, int maxBodyBytes = 4 * 1024 * 1024)
    {
        ArgumentNullException.ThrowIfNull(host);
        ArgumentNullException.ThrowIfNull(tokens);
        ArgumentException.ThrowIfNullOrEmpty(loopbackPrefix);
        ArgumentOutOfRangeException.ThrowIfLessThan(maxBodyBytes, 1);

        _host = host;
        _tokens = tokens;
        _maxBodyBytes = maxBodyBytes;
        _listener = new HttpListener();
        _listener.Prefixes.Add(loopbackPrefix);
    }

    public OtlpReceiverStats Stats => new(
        Interlocked.Read(ref _received),
        Interlocked.Read(ref _unauthenticated),
        Interlocked.Read(ref _rejected));

    /// <summary>Accepts exports until cancelled. One export per POST; one bad request never stops the loop.</summary>
    public async Task RunAsync(CancellationToken ct)
    {
        _listener.Start();
        using var registration = ct.Register(() => { try { _listener.Stop(); } catch (ObjectDisposedException) { } });

        while (!ct.IsCancellationRequested)
        {
            HttpListenerContext ctx;
            try
            {
                ctx = await _listener.GetContextAsync().ConfigureAwait(false);
            }
            catch (Exception) when (ct.IsCancellationRequested)
            {
                break; // Stop() during cancellation surfaces as HttpListenerException/ObjectDisposed
            }

            try
            {
                var token = ctx.Request.Headers[TokenHeader];
                var body = ReadCapped(ctx.Request.InputStream, ctx.Request.ContentLength64, _maxBodyBytes);
                if (body is null)
                {
                    Interlocked.Increment(ref _rejected); // oversize
                }
                else
                {
                    HandleExport(token, body);
                }
            }
            catch (Exception)
            {
                Interlocked.Increment(ref _rejected); // any handler fault is counted, not fatal
            }
            finally
            {
                Respond200(ctx);
            }
        }
    }

    /// <summary>Resolve token -> capability, parse, enqueue. Testable without a network.</summary>
    internal void HandleExport(string? token, string body)
    {
        if (string.IsNullOrEmpty(token) || _tokens.Resolve(token) is not { } capability)
        {
            Interlocked.Increment(ref _unauthenticated);
            return;
        }

        var spans = OtlpJsonParser.Parse(body);
        foreach (var span in spans)
        {
            _host.Enqueue(new HarnessSpanEvent(capability, span));
            Interlocked.Increment(ref _received);
        }
    }

    /// <summary>Reads at most <paramref name="maxBytes"/>; returns null when the body exceeds the cap.</summary>
    internal static string? ReadCapped(Stream input, long declaredLength, int maxBytes)
    {
        if (declaredLength > maxBytes)
        {
            return null;
        }

        using var buffer = new MemoryStream();
        var chunk = new byte[8192];
        int read;
        while ((read = input.Read(chunk, 0, chunk.Length)) > 0)
        {
            if (buffer.Length + read > maxBytes)
            {
                return null;
            }

            buffer.Write(chunk, 0, read);
        }

        return Encoding.UTF8.GetString(buffer.GetBuffer(), 0, (int)buffer.Length);
    }

    private static void Respond200(HttpListenerContext ctx)
    {
        try
        {
            ctx.Response.StatusCode = 200;
            ctx.Response.ContentType = "application/json";
            var ok = "{}"u8.ToArray(); // empty ExportTraceServiceResponse
            ctx.Response.OutputStream.Write(ok, 0, ok.Length);
            ctx.Response.Close();
        }
        catch (Exception)
        {
            // The client may already be gone; a failed response must not stop the accept loop.
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        ((IDisposable)_listener).Dispose();
    }
}
