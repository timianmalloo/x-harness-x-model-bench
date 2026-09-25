// Auto-generated xUnit tests ported 1:1 from upstream MultiPL-E HumanEval-C# test harness.
using System;
using System.Collections.Generic;
using Xunit;

public class ProblemTests
{
    // ==========================================
    // HumanEval/0: HasCloseElements
    // ==========================================

    [Fact]
    public void Test_0_1_HasCloseElements()
    {
        Assert.True(Problem.HasCloseElements(new List<float> { 1.0f, 2.0f, 3.9f, 4.0f, 5.0f, 2.2f }, 0.3f));
    }

    [Fact]
    public void Test_0_2_HasCloseElements()
    {
        Assert.False(Problem.HasCloseElements(new List<float> { 1.0f, 2.0f, 3.9f, 4.0f, 5.0f, 2.2f }, 0.05f));
    }

    [Fact]
    public void Test_0_3_HasCloseElements()
    {
        Assert.True(Problem.HasCloseElements(new List<float> { 1.0f, 2.0f, 5.9f, 4.0f, 5.0f }, 0.95f));
    }

    [Fact]
    public void Test_0_4_HasCloseElements()
    {
        Assert.False(Problem.HasCloseElements(new List<float> { 1.0f, 2.0f, 5.9f, 4.0f, 5.0f }, 0.8f));
    }

    [Fact]
    public void Test_0_5_HasCloseElements()
    {
        Assert.True(Problem.HasCloseElements(new List<float> { 1.0f, 2.0f, 3.0f, 4.0f, 5.0f, 2.0f }, 0.1f));
    }

    [Fact]
    public void Test_0_6_HasCloseElements()
    {
        Assert.True(Problem.HasCloseElements(new List<float> { 1.1f, 2.2f, 3.1f, 4.1f, 5.1f }, 1.0f));
    }

    [Fact]
    public void Test_0_7_HasCloseElements()
    {
        Assert.False(Problem.HasCloseElements(new List<float> { 1.1f, 2.2f, 3.1f, 4.1f, 5.1f }, 0.5f));
    }

    // ==========================================
    // HumanEval/1: SeparateParenGroups
    // ==========================================

    [Fact]
    public void Test_1_1_SeparateParenGroups()
    {
        Assert.Equal(new List<string> { "(()())", "((()))", "()", "((())()())" }, Problem.SeparateParenGroups("(()()) ((())) () ((())()())"));
    }

    [Fact]
    public void Test_1_2_SeparateParenGroups()
    {
        Assert.Equal(new List<string> { "()", "(())", "((()))", "(((())))" }, Problem.SeparateParenGroups("() (()) ((())) (((())))"));
    }

    [Fact]
    public void Test_1_3_SeparateParenGroups()
    {
        Assert.Equal(new List<string> { "(()(())((())))" }, Problem.SeparateParenGroups("(()(())((())))"));
    }

    [Fact]
    public void Test_1_4_SeparateParenGroups()
    {
        Assert.Equal(new List<string> { "()", "(())", "(()())" }, Problem.SeparateParenGroups("( ) (( )) (( )( ))"));
    }

    // ==========================================
    // HumanEval/2: TruncateNumber
    // ==========================================

    [Fact]
    public void Test_2_1_TruncateNumber()
    {
        Assert.Equal(0.5f, Problem.TruncateNumber(3.5f), 5);
    }

    [Fact]
    public void Test_2_2_TruncateNumber()
    {
        Assert.Equal(0.25f, Problem.TruncateNumber(1.25f), 5);
    }

    [Fact]
    public void Test_2_3_TruncateNumber()
    {
        Assert.Equal(0.0f, Problem.TruncateNumber(123.0f), 5);
    }

    // ==========================================
    // HumanEval/3: BelowZero
    // ==========================================

    [Fact]
    public void Test_3_1_BelowZero()
    {
        Assert.False(Problem.BelowZero(new List<long>()));
    }

    [Fact]
    public void Test_3_2_BelowZero()
    {
        Assert.False(Problem.BelowZero(new List<long> { 1L, 2L, -3L, 1L, 2L, -3L }));
    }

    [Fact]
    public void Test_3_3_BelowZero()
    {
        Assert.True(Problem.BelowZero(new List<long> { 1L, 2L, -4L, 5L, 6L }));
    }

    [Fact]
    public void Test_3_4_BelowZero()
    {
        Assert.False(Problem.BelowZero(new List<long> { 1L, -1L, 2L, -2L, 5L, -5L, 4L, -4L }));
    }

    [Fact]
    public void Test_3_5_BelowZero()
    {
        Assert.True(Problem.BelowZero(new List<long> { 1L, -1L, 2L, -2L, 5L, -5L, 4L, -5L }));
    }

    [Fact]
    public void Test_3_6_BelowZero()
    {
        Assert.True(Problem.BelowZero(new List<long> { 1L, -2L, 2L, -2L, 5L, -5L, 4L, -4L }));
    }

    // ==========================================
    // HumanEval/4: MeanAbsoluteDeviation
    // ==========================================

    [Fact]
    public void Test_4_1_MeanAbsoluteDeviation()
    {
        Assert.Equal(0.5f, Problem.MeanAbsoluteDeviation(new List<float> { 1.0f, 2.0f }), 5);
    }

    [Fact]
    public void Test_4_2_MeanAbsoluteDeviation()
    {
        Assert.Equal(1.0f, Problem.MeanAbsoluteDeviation(new List<float> { 1.0f, 2.0f, 3.0f, 4.0f }), 5);
    }

    [Fact]
    public void Test_4_3_MeanAbsoluteDeviation()
    {
        Assert.Equal(1.2f, Problem.MeanAbsoluteDeviation(new List<float> { 1.0f, 2.0f, 3.0f, 4.0f, 5.0f }), 5);
    }

    // ==========================================
    // HumanEval/5: Intersperse
    // ==========================================

    [Fact]
    public void Test_5_1_Intersperse()
    {
        Assert.Equal(new List<long>(), Problem.Intersperse(new List<long>(), 7L));
    }

    [Fact]
    public void Test_5_2_Intersperse()
    {
        Assert.Equal(new List<long> { 5L, 8L, 6L, 8L, 3L, 8L, 2L }, Problem.Intersperse(new List<long> { 5L, 6L, 3L, 2L }, 8L));
    }

    [Fact]
    public void Test_5_3_Intersperse()
    {
        Assert.Equal(new List<long> { 2L, 2L, 2L, 2L, 2L }, Problem.Intersperse(new List<long> { 2L, 2L, 2L }, 2L));
    }

    // ==========================================
    // HumanEval/6: ParseNestedParens
    // ==========================================

    [Fact]
    public void Test_6_1_ParseNestedParens()
    {
        Assert.Equal(new List<long> { 2L, 3L, 1L, 3L }, Problem.ParseNestedParens("(()()) ((())) () ((())()())"));
    }

    [Fact]
    public void Test_6_2_ParseNestedParens()
    {
        Assert.Equal(new List<long> { 1L, 2L, 3L, 4L }, Problem.ParseNestedParens("() (()) ((())) (((())))"));
    }

    [Fact]
    public void Test_6_3_ParseNestedParens()
    {
        Assert.Equal(new List<long> { 4L }, Problem.ParseNestedParens("(()(())((())))"));
    }

    // ==========================================
    // HumanEval/7: FilterBySubstring
    // ==========================================

    [Fact]
    public void Test_7_1_FilterBySubstring()
    {
        Assert.Equal(new List<string>(), Problem.FilterBySubstring(new List<string>(), "john"));
    }

    [Fact]
    public void Test_7_2_FilterBySubstring()
    {
        Assert.Equal(new List<string> { "xxx", "xxxAAA", "xxx" }, Problem.FilterBySubstring(new List<string> { "xxx", "asd", "xxy", "john doe", "xxxAAA", "xxx" }, "xxx"));
    }

    [Fact]
    public void Test_7_3_FilterBySubstring()
    {
        Assert.Equal(new List<string> { "xxx", "aaaxxy", "xxxAAA", "xxx" }, Problem.FilterBySubstring(new List<string> { "xxx", "asd", "aaaxxy", "john doe", "xxxAAA", "xxx" }, "xx"));
    }

    [Fact]
    public void Test_7_4_FilterBySubstring()
    {
        Assert.Equal(new List<string> { "grunt", "prune" }, Problem.FilterBySubstring(new List<string> { "grunt", "trumpet", "prune", "gruesome" }, "run"));
    }

    // ==========================================
    // HumanEval/8: SumProduct
    // ==========================================

    [Fact]
    public void Test_8_1_SumProduct()
    {
        Assert.Equal(Tuple.Create(0L, 1L), Problem.SumProduct(new List<long>()));
    }

    [Fact]
    public void Test_8_2_SumProduct()
    {
        Assert.Equal(Tuple.Create(3L, 1L), Problem.SumProduct(new List<long> { 1L, 1L, 1L }));
    }

    [Fact]
    public void Test_8_3_SumProduct()
    {
        Assert.Equal(Tuple.Create(100L, 0L), Problem.SumProduct(new List<long> { 100L, 0L }));
    }

    [Fact]
    public void Test_8_4_SumProduct()
    {
        Assert.Equal(Tuple.Create(15L, 105L), Problem.SumProduct(new List<long> { 3L, 5L, 7L }));
    }

    [Fact]
    public void Test_8_5_SumProduct()
    {
        Assert.Equal(Tuple.Create(10L, 10L), Problem.SumProduct(new List<long> { 10L }));
    }

    // ==========================================
    // HumanEval/9: RollingMax
    // ==========================================

    [Fact]
    public void Test_9_1_RollingMax()
    {
        Assert.Equal(new List<long>(), Problem.RollingMax(new List<long>()));
    }

    [Fact]
    public void Test_9_2_RollingMax()
    {
        Assert.Equal(new List<long> { 1L, 2L, 3L, 4L }, Problem.RollingMax(new List<long> { 1L, 2L, 3L, 4L }));
    }

    [Fact]
    public void Test_9_3_RollingMax()
    {
        Assert.Equal(new List<long> { 4L, 4L, 4L, 4L }, Problem.RollingMax(new List<long> { 4L, 3L, 2L, 1L }));
    }

    [Fact]
    public void Test_9_4_RollingMax()
    {
        Assert.Equal(new List<long> { 3L, 3L, 3L, 100L, 100L }, Problem.RollingMax(new List<long> { 3L, 2L, 3L, 100L, 3L }));
    }
}
