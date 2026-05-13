namespace LogQueryParser;

public sealed class QueryParseError
{
    public QueryParseError(string message, int position)
    {
        Message = message;
        Position = position;
    }

    public string Message { get; }
    public int Position { get; }
}
