// Exercises the generated component's private static helpers through reflection.
// Each case mirrors a defect that string-level Python tests cannot catch.
using System;
using System.Collections.Generic;
using System.Reflection;

public static class Program
{
    private static int failures;

    private static MethodInfo Method(string name)
    {
        var method = typeof(Script_Instance).GetMethod(name, BindingFlags.NonPublic | BindingFlags.Static);
        if (method == null) throw new Exception("missing helper " + name);
        return method;
    }

    private static string Extract(string json, string property) =>
        (string)Method("ExtractRawProperty").Invoke(null, new object[] { json, property });

    private static string ReadString(string json, string property) =>
        (string)Method("ReadString").Invoke(null, new object[] { json, property });

    private static int ReadInt(string json, string property) =>
        (int)Method("ReadInt").Invoke(null, new object[] { json, property });

    private static string BuildEntry(string hash, string body) =>
        (string)Method("BuildEntry").Invoke(null, new object[] { hash, body });

    private static string BuildStore(string store, int index, string entry) =>
        (string)Method("BuildStore").Invoke(null, new object[] { store, index, entry });

    private static string FindEntry(string store, string slot, string hash, out bool matches)
    {
        var args = new object[] { store, slot, hash, false };
        var result = (string)Method("FindEntry").Invoke(null, args);
        matches = (bool)args[3];
        return result;
    }

    private static string Hash(string text) =>
        (string)Method("HashText").Invoke(null, new object[] { text });

    private static void Check(string name, bool ok, string detail = "")
    {
        Console.WriteLine((ok ? "PASS " : "FAIL ") + name + (ok || detail == "" ? "" : "  -> " + detail));
        if (!ok) failures++;
    }

    private static string Body(string outputs, string reasoning) =>
        "{\"outputs\": " + outputs + ", \"reasoning\": \"" + reasoning + "\", \"usage\": {\"input_tokens\": 1, \"output_tokens\": 1}, \"cached\": false, \"latency_ms\": 1.0, \"model\": \"fake/model\"}";

    public static int Main()
    {
        // 1. Top-level lookup ignores nested keys with the same name.
        Check("nested key does not shadow top-level", Extract("{\"a\":{\"x\":1},\"x\":2}", "x") == "2");
        Check("missing top-level key is empty even when nested", Extract("{\"a\":{\"x\":1}}", "x") == "");
        Check("body inside outputs does not shadow entry body",
            ReadString(Extract("{\"inputs\":\"h\",\"body\":{\"outputs\":{\"body\":\"nested\"},\"reasoning\":\"r\"}}", "body"), "reasoning") == "r");
        Check("arrays and strings with braces are skipped",
            Extract("{\"a\":[1,{\"x\":\"}\"},2],\"x\":\"v{\"}", "x") == "\"v{\"");
        Check("escaped quotes inside keys and values", ReadString("{\"k\\\"q\":\"a\\\"b\"}", "k\"q") == "a\"b");
        Check("count read at top level only", ReadInt("{\"items\":{\"count\":9},\"count\":2}", "count") == 2);

        // 2. Duplicate inputs keep distinct per-item results.
        var h = Hash("same inputs");
        var e0 = BuildEntry(h, Body("{\"span\": 1.0}", "one"));
        var e1 = BuildEntry(h, Body("{\"span\": 2.0}", "two"));
        var store = BuildStore("", 0, e0);
        store = BuildStore(store, 1, e1);
        bool m0, m1;
        var f0 = FindEntry(store, "i0", h, out m0);
        var f1 = FindEntry(store, "i1", h, out m1);
        Check("duplicate inputs: item 0 replays its own result", m0 && ReadString(f0, "body") != "" && Extract(Extract(f0, "body"), "outputs").Contains("1.0"), f0);
        Check("duplicate inputs: item 1 replays its own result", m1 && Extract(Extract(f1, "body"), "outputs").Contains("2.0"), f1);
        bool mOther;
        var reordered = FindEntry(store, "i5", h, out mOther);
        Check("unknown slot still finds a hash match elsewhere", mOther && reordered != null);

        // 3. An output named i1 inside a body cannot corrupt the store keys.
        var nested0 = BuildEntry(Hash("a"), Body("{\"i1\": 7, \"span\": 1.0}", "first"));
        var nested1 = BuildEntry(Hash("b"), Body("{\"i1\": 8, \"span\": 2.0}", "second"));
        var s = BuildStore("", 0, nested0);
        s = BuildStore(s, 1, nested1);
        bool mm;
        var got1 = FindEntry(s, "i1", Hash("b"), out mm);
        Check("output named i1: second item found", mm && got1 != null && ReadString(Extract(got1, "body"), "reasoning") == "second", got1 ?? "null");
        var replaced = BuildStore(s, 0, BuildEntry(Hash("a2"), Body("{\"i1\": 9, \"span\": 3.0}", "first-v2")));
        bool mk;
        var keep1 = FindEntry(replaced, "i1", Hash("b"), out mk);
        Check("output named i1: updating item 0 keeps item 1", mk && keep1 != null && ReadString(Extract(keep1, "body"), "reasoning") == "second", replaced);
        Check("store count survives", ReadInt(replaced, "count") == 2);

        // 4. Legacy single snapshot (v1) is item 0 and is preserved on upgrade.
        var legacy = "{\"v\":1,\"captured\":\"t\",\"inputs\":\"" + Hash("L") + "\",\"body\":" + Body("{\"span\": 5.0}", "legacy") + "}";
        bool lm;
        var l0 = FindEntry(legacy, "i0", Hash("L"), out lm);
        Check("legacy snapshot replays as item 0", lm && l0 != null && ReadString(Extract(l0, "body"), "reasoning") == "legacy");
        var upgraded = BuildStore(legacy, 1, BuildEntry(Hash("M"), Body("{\"span\": 6.0}", "second")));
        bool um;
        Check("legacy snapshot survives store upgrade", FindEntry(upgraded, "i0", Hash("L"), out um) != null && um && ReadInt(upgraded, "count") == 2, upgraded);

        // 5. Hash is stable and does not overflow under checked arithmetic.
        Check("hash stable", Hash("abc") == Hash("abc") && Hash("abc") != Hash("abd") && Hash("").Length == 8);

        Console.WriteLine(failures == 0 ? "ALL PASSED" : failures + " FAILED");
        return failures == 0 ? 0 : 1;
    }
}
