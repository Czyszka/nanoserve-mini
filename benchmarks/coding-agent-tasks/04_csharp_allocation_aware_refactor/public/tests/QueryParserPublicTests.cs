using System;
using LogQueryParser;
using Xunit;

namespace LogQueryParser.PublicTests;

public class QueryParserPublicTests
{
    [Fact]
    public void Empty_Query_Succeeds_With_Zero_Tokens()
    {
        var result = QueryParser.Parse("");
        Assert.True(result.Success);
        Assert.Empty(result.Tokens);
    }

    [Fact]
    public void Whitespace_Only_Query_Succeeds_With_Zero_Tokens()
    {
        var result = QueryParser.Parse("   ");
        Assert.True(result.Success);
        Assert.Empty(result.Tokens);
    }

    [Fact]
    public void Null_Input_Throws_ArgumentNullException()
    {
        Assert.Throws<ArgumentNullException>(() => QueryParser.Parse(null!));
    }

    [Fact]
    public void Basic_Key_Value()
    {
        var result = QueryParser.Parse("level:error");
        Assert.True(result.Success);
        Assert.Single(result.Tokens);
        Assert.Equal("level", result.Tokens[0].Key);
        Assert.Equal("error", result.Tokens[0].Value);
    }

    [Fact]
    public void Multiple_Pairs()
    {
        var result = QueryParser.Parse("level:error service:api");
        Assert.True(result.Success);
        Assert.Equal(2, result.Tokens.Count);
        Assert.Equal("level", result.Tokens[0].Key);
        Assert.Equal("error", result.Tokens[0].Value);
        Assert.Equal("service", result.Tokens[1].Key);
        Assert.Equal("api", result.Tokens[1].Value);
    }

    [Fact]
    public void Quoted_Value_With_Spaces()
    {
        var result = QueryParser.Parse("text:\"timeout while reading\"");
        Assert.True(result.Success);
        Assert.Single(result.Tokens);
        Assert.Equal("text", result.Tokens[0].Key);
        Assert.Equal("timeout while reading", result.Tokens[0].Value);
    }

    [Fact]
    public void Escaped_Quote_Inside_Quoted_Value()
    {
        // text:"he said \"hello\"" -> he said "hello"
        var result = QueryParser.Parse("text:\"he said \\\"hello\\\"\"");
        Assert.True(result.Success);
        Assert.Single(result.Tokens);
        Assert.Equal("text", result.Tokens[0].Key);
        Assert.Equal("he said \"hello\"", result.Tokens[0].Value);
    }

    [Fact]
    public void Escaped_Backslash_Inside_Quoted_Value()
    {
        // path:"C:\\Temp" -> C:\Temp
        var result = QueryParser.Parse("path:\"C:\\\\Temp\"");
        Assert.True(result.Success);
        Assert.Single(result.Tokens);
        Assert.Equal("path", result.Tokens[0].Key);
        Assert.Equal("C:\\Temp", result.Tokens[0].Value);
    }

    [Fact]
    public void Duplicate_Keys_Preserved_In_Order()
    {
        var result = QueryParser.Parse("tag:api tag:slow");
        Assert.True(result.Success);
        Assert.Equal(2, result.Tokens.Count);
        Assert.Equal("tag", result.Tokens[0].Key);
        Assert.Equal("api", result.Tokens[0].Value);
        Assert.Equal("tag", result.Tokens[1].Key);
        Assert.Equal("slow", result.Tokens[1].Value);
    }

    [Fact]
    public void Unclosed_Quote_Returns_Failure()
    {
        var result = QueryParser.Parse("text:\"unterminated");
        Assert.False(result.Success);
        Assert.NotEmpty(result.Errors);
    }

    [Fact]
    public void Missing_Colon_Returns_Failure_Not_Throw()
    {
        // "level error" — no colon. Must return Success=false, not throw.
        var result = QueryParser.Parse("level error");
        Assert.False(result.Success);
        Assert.NotEmpty(result.Errors);
    }
}
