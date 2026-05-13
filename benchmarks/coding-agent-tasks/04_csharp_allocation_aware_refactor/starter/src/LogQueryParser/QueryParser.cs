namespace LogQueryParser;

/// <summary>
/// Parses simple "key:value" log query expressions.
///
/// NOTE: This is a deliberately split-heavy, allocation-heavy starter
/// implementation with several known correctness flaws. The agent's task is
/// to fix correctness and reduce allocations while preserving the public API.
/// </summary>
public static class QueryParser
{
    public static QueryParseResult Parse(string query)
    {
        if (query is null)
        {
            throw new ArgumentNullException(nameof(query));
        }

        var tokens = new List<QueryToken>();
        var errors = new List<QueryParseError>();

        // Empty / whitespace-only query is valid -> zero tokens.
        if (query.Length == 0 || query.Trim().Length == 0)
        {
            return new QueryParseResult(true, tokens, errors);
        }

        // Split-heavy implementation (intentional: agent should refactor to a
        // single-pass parser using indexing / ReadOnlySpan<char>).
        //
        // Known limitation: this only splits on ' ' — tabs/newlines are NOT
        // treated as separators, and repeated spaces produce empty entries.
        string[] parts = query.Split(' ');

        // Walk through "parts", but if we encounter a quoted value that
        // contains spaces, naively glue the next parts together until we hit
        // a closing quote.
        int i = 0;
        while (i < parts.Length)
        {
            string part = parts[i];
            if (part.Length == 0)
            {
                // Empty entry from repeated spaces — skip but advance.
                i++;
                continue;
            }

            int colon = part.IndexOf(':');
            if (colon < 0)
            {
                // Bug 2: malformed pair (no colon) throws instead of returning
                // a failed QueryParseResult.
                throw new FormatException(
                    $"Malformed query pair at position {i}: '{part}'");
            }

            // Bug 3 surface: pair.Split(':') would split a value like "C:\Temp"
            // into too many segments. We use IndexOf+Substring for the first
            // colon only, but we still rely on whitespace=' ' splitting.
            string key = part.Substring(0, colon);
            string value = part.Substring(colon + 1);

            if (key.Length == 0)
            {
                errors.Add(new QueryParseError(
                    "Empty key.", PositionOf(parts, i)));
                return new QueryParseResult(false, tokens, errors);
            }

            // Quoted value handling — Bug 1: NO escape interpretation.
            // We just look for a closing quote naively.
            if (value.StartsWith("\""))
            {
                // Drop the leading quote.
                string acc = value.Substring(1);

                // If there's no closing quote inside `acc`, glue subsequent
                // parts (rejoined with a single space).
                if (!acc.Contains('"'))
                {
                    int j = i + 1;
                    bool closed = false;
                    while (j < parts.Length)
                    {
                        acc = acc + " " + parts[j];
                        if (parts[j].Contains('"'))
                        {
                            closed = true;
                            i = j;
                            break;
                        }
                        j++;
                    }
                    if (!closed)
                    {
                        errors.Add(new QueryParseError(
                            "Unterminated quoted value.",
                            PositionOf(parts, i)));
                        return new QueryParseResult(false, tokens, errors);
                    }
                }

                // Bug 1: truncate at the FIRST inner '"' — escape sequences
                // like \" are not interpreted.
                int closingQuote = acc.IndexOf('"');
                if (closingQuote < 0)
                {
                    errors.Add(new QueryParseError(
                        "Unterminated quoted value.",
                        PositionOf(parts, i)));
                    return new QueryParseResult(false, tokens, errors);
                }

                // Anything after the closing quote on the same part is
                // discarded silently — also a latent issue.
                string raw = acc.Substring(0, closingQuote);
                tokens.Add(new QueryToken(key, raw));
            }
            else
            {
                if (value.Length == 0)
                {
                    errors.Add(new QueryParseError(
                        "Empty value.", PositionOf(parts, i)));
                    return new QueryParseResult(false, tokens, errors);
                }
                tokens.Add(new QueryToken(key, value));
            }

            i++;
        }

        return new QueryParseResult(true, tokens, errors);
    }

    private static int PositionOf(string[] parts, int index)
    {
        int pos = 0;
        for (int k = 0; k < index && k < parts.Length; k++)
        {
            pos += parts[k].Length + 1; // +1 for the space
        }
        return pos;
    }
}
