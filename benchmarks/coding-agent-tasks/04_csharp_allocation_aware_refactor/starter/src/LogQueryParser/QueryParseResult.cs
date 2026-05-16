namespace LogQueryParser;

public sealed class QueryParseResult
{
    public QueryParseResult(
        bool success,
        IReadOnlyList<QueryToken> tokens,
        IReadOnlyList<QueryParseError> errors)
    {
        Success = success;
        Tokens = tokens;
        Errors = errors;
    }

    public bool Success { get; }
    public IReadOnlyList<QueryToken> Tokens { get; }
    public IReadOnlyList<QueryParseError> Errors { get; }
}
