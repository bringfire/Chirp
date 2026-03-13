// Chirp-enabled GH Script Component — Reference Template
//
// NOTE: This is a reference document showing the structure of generated scripts.
// chirp_create() generates scripts programmatically — it does NOT use this file.
// See src/chirp/rook_tool.py for the actual generator.
//
// The adapter handles: format → LLM call → parse → validate → cache → trace.
//
// Placeholders shown as {{NAME}} for readability:
//   {{SIGNATURE}}           — DSPy signature string
//   {{SCHEMA_JSON}}         — JSON dict of output field → type string
//   {{INPUT_SERIALIZATION}} — code lines that build the inputs JSON object
//   {{OUTPUT_ASSIGNMENT}}   — code lines that read outputs into public fields

using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using Rhino.Geometry;

public class Script_Instance
{
    // === INPUTS (public fields, set by GH from upstream pins) ===
    // {{INPUT_FIELDS}}

    // === OUTPUTS (public fields, read by GH for downstream pins) ===
    // {{OUTPUT_FIELDS}}

    private static readonly HttpClient _client = new HttpClient()
    {
        Timeout = TimeSpan.FromSeconds(30)
    };

    public void RunScript()
    {
        try
        {
            // Build inputs JSON
            var inputs = new Dictionary<string, object>
            {
                // {{INPUT_SERIALIZATION}}
            };

            // Build request
            var request = new Dictionary<string, object>
            {
                { "signature", "{{SIGNATURE}}" },
                { "inputs", inputs },
                { "schema", JsonSerializer.Deserialize<Dictionary<string, string>>("{{SCHEMA_JSON}}") }
            };

            var json = JsonSerializer.Serialize(request);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            // Call Chirp adapter (synchronous — blocks until response)
            var response = _client.PostAsync("http://localhost:9900/chirp/call", content).Result;
            var body = response.Content.ReadAsStringAsync().Result;

            if (!response.IsSuccessStatusCode)
                throw new Exception($"Chirp error ({response.StatusCode}): {body}");

            // Parse response
            using var doc = JsonDocument.Parse(body);
            var outputs = doc.RootElement.GetProperty("outputs");

            // {{OUTPUT_ASSIGNMENT}}
        }
        catch (HttpRequestException)
        {
            // Adapter service not running — leave defaults, don't crash
        }
        catch (Exception ex)
        {
            throw new Exception($"Chirp: {ex.Message}");
        }
    }
}
