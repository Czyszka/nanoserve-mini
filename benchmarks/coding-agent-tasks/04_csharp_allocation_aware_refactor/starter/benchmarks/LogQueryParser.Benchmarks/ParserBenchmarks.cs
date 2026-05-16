using BenchmarkDotNet.Attributes;
using BenchmarkDotNet.Running;
using LogQueryParser;

public class ParserBenchmarks
{
    [Benchmark]
    public QueryParseResult Simple() => QueryParser.Parse("level:error service:api");

    [Benchmark]
    public QueryParseResult Quoted() =>
        QueryParser.Parse("level:error text:\"timeout while reading\"");
}

public class Program
{
    public static void Main(string[] args) =>
        BenchmarkRunner.Run<ParserBenchmarks>();
}
