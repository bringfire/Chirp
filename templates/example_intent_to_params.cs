// Example: Intent to Subdivision Parameters
// A Chirp-enabled GH script component that takes a surface description
// and design intent, then returns subdivision parameters via LLM.
//
// Inputs:  SurfaceDesc (string), Intent (string)
// Outputs: UCount (int), VCount (int), Grading (double)

using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Rhino.Geometry;

public class Script_Instance
{
    // === INPUTS ===
    public string SurfaceDesc = "";
    public string Intent = "";

    // === OUTPUTS ===
    public int UCount = 0;
    public int VCount = 0;
    public double Grading = 0.0;

    private static readonly HttpClient _client = new HttpClient()
    {
        Timeout = TimeSpan.FromSeconds(1830)
    };

    public void RunScript()
    {
        if (string.IsNullOrEmpty(Intent)) return;

        try
        {
            var inputs = new Dictionary<string, object>
            {
                { "surface_description", SurfaceDesc },
                { "design_intent", Intent }
            };

            var schema = new Dictionary<string, string>
            {
                { "u_count", "int" },
                { "v_count", "int" },
                { "grading", "float" }
            };

            var request = new Dictionary<string, object>
            {
                { "signature", "surface_description, design_intent -> u_count, v_count, grading" },
                { "inputs", inputs },
                { "schema", schema }
            };

            var json = JsonSerializer.Serialize(request);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var response = _client.PostAsync("http://localhost:9900/chirp/call", content).GetAwaiter().GetResult();
            var body = response.Content.ReadAsStringAsync().GetAwaiter().GetResult();

            if (response.StatusCode == HttpStatusCode.GatewayTimeout)
                throw new Exception($"chirp_inference_timeout: {body}");
            if (!response.IsSuccessStatusCode)
            {
                throw new Exception($"Chirp error ({response.StatusCode}): {body}");
            }

            using var doc = JsonDocument.Parse(body);
            var outputs = doc.RootElement.GetProperty("outputs");

            UCount = outputs.GetProperty("u_count").GetInt32();
            VCount = outputs.GetProperty("v_count").GetInt32();
            Grading = outputs.GetProperty("grading").GetDouble();
        }
        catch (TaskCanceledException)
        {
            throw new Exception("chirp_transport_timeout: Chirp transport exceeded its 1830-second safety ceiling.");
        }
        catch (HttpRequestException)
        {
            // Adapter service not running — leave defaults, don't crash
            UCount = 0;
            VCount = 0;
            Grading = 0.0;
        }
        catch (Exception ex)
        {
            throw new Exception($"Chirp call failed: {ex.Message}");
        }
    }
}
