namespace LogQueryParser;

public sealed class QueryToken
{
    public QueryToken(string key, string value)
    {
        Key = key;
        Value = value;
    }

    public string Key { get; }
    public string Value { get; }
}
