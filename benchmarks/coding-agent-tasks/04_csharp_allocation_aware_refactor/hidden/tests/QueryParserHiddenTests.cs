using System;
using System.Globalization;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Threading;
using LogQueryParser;
using Xunit;

namespace LogQueryParser.HiddenTests;

public class QueryParserHiddenTests
{
    [Fact]
    public void Tabs_And_Newlines_Are_Separators()
    {
        var result = QueryParser.Parse("key1:v1\tkey2:v2\nkey3:v3");
        Assert.True(result.Success);
        Assert.Equal(3, result.Tokens.Count);
        Assert.Equal("key1", result.Tokens[0].Key);
        Assert.Equal("v1", result.Tokens[0].Value);
        Assert.Equal("key2", result.Tokens[1].Key);
        Assert.Equal("v2", result.Tokens[1].Value);
        Assert.Equal("key3", result.Tokens[2].Key);
        Assert.Equal("v3", result.Tokens[2].Value);
    }

    [Fact]
    public void Repeated_Whitespace_Collapses()
    {
        var result = QueryParser.Parse("a:1     b:2");
        Assert.True(result.Success);
        Assert.Equal(2, result.Tokens.Count);
    }

    [Fact]
    public void Unsupported_Escape_Returns_Failure()
    {
        // text:"bad \q escape" — \q is not a supported escape.
        var result = QueryParser.Parse("text:\"bad \\q escape\"");
        Assert.False(result.Success);
        Assert.NotEmpty(result.Errors);
    }

    [Fact]
    public void Missing_Value_Returns_Failure()
    {
        var result = QueryParser.Parse("level:");
        Assert.False(result.Success);
        Assert.NotEmpty(result.Errors);
    }

    [Fact]
    public void Missing_Key_Returns_Failure()
    {
        var result = QueryParser.Parse(":error");
        Assert.False(result.Success);
        Assert.NotEmpty(result.Errors);
    }

    [Fact]
    public void Culture_Invariance_Under_TrTR()
    {
        var original = Thread.CurrentThread.CurrentCulture;
        try
        {
            Thread.CurrentThread.CurrentCulture = new CultureInfo("tr-TR");
            var result = QueryParser.Parse("LEVEL:ERROR id:I");
            Assert.True(result.Success);
            Assert.Equal(2, result.Tokens.Count);
            Assert.Equal("LEVEL", result.Tokens[0].Key);
            Assert.Equal("ERROR", result.Tokens[0].Value);
            Assert.Equal("id", result.Tokens[1].Key);
            Assert.Equal("I", result.Tokens[1].Value);
        }
        finally
        {
            Thread.CurrentThread.CurrentCulture = original;
        }
    }

    [Fact]
    public void Very_Long_Query_Many_Tokens()
    {
        const int n = 10_000;
        var sb = new StringBuilder(n * 8);
        for (int i = 0; i < n; i++)
        {
            if (i > 0) sb.Append(' ');
            sb.Append('k').Append(i).Append(':').Append('v').Append(i);
        }
        var result = QueryParser.Parse(sb.ToString());
        Assert.True(result.Success);
        Assert.Equal(n, result.Tokens.Count);
        Assert.Equal("k0", result.Tokens[0].Key);
        Assert.Equal("v9999", result.Tokens[n - 1].Value);
    }

    [Fact]
    public void Escaped_Backslash_Yields_Single_Backslash()
    {
        // path:"a\\b" -> a\b
        var result = QueryParser.Parse("path:\"a\\\\b\"");
        Assert.True(result.Success);
        Assert.Single(result.Tokens);
        Assert.Equal("a\\b", result.Tokens[0].Value);
    }

    [Fact]
    public void Public_Api_Surface_Is_Preserved()
    {
        var asm = typeof(QueryParser).Assembly;

        var parser = asm.GetType("LogQueryParser.QueryParser");
        Assert.NotNull(parser);
        var parse = parser!.GetMethod("Parse", BindingFlags.Public | BindingFlags.Static);
        Assert.NotNull(parse);
        Assert.Equal(typeof(string), parse!.GetParameters().Single().ParameterType);

        var result = asm.GetType("LogQueryParser.QueryParseResult");
        Assert.NotNull(result);
        Assert.NotNull(result!.GetProperty("Success"));
        Assert.NotNull(result.GetProperty("Tokens"));
        Assert.NotNull(result.GetProperty("Errors"));
        Assert.Equal(typeof(bool), result.GetProperty("Success")!.PropertyType);

        var token = asm.GetType("LogQueryParser.QueryToken");
        Assert.NotNull(token);
        Assert.Equal(typeof(string), token!.GetProperty("Key")!.PropertyType);
        Assert.Equal(typeof(string), token.GetProperty("Value")!.PropertyType);

        var error = asm.GetType("LogQueryParser.QueryParseError");
        Assert.NotNull(error);
        Assert.Equal(typeof(string), error!.GetProperty("Message")!.PropertyType);
        Assert.Equal(typeof(int), error.GetProperty("Position")!.PropertyType);
    }
}
