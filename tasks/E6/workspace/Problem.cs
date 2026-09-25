using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text;

public class Problem
{
    // Check if in given list of numbers, are any two numbers closer to each other than
    // given threshold.
    // >>> HasCloseElements((new List<float>(new float[]{(float)1.0f, (float)2.0f, (float)3.0f})), (0.5f))
    // (false)
    // >>> HasCloseElements((new List<float>(new float[]{(float)1.0f, (float)2.8f, (float)3.0f, (float)4.0f, (float)5.0f, (float)2.0f})), (0.3f))
    // (true)
    public static bool HasCloseElements(List<float> numbers, float threshold)
    {
        throw new NotImplementedException();
    }

    // Input to this function is a string containing multiple groups of nested parentheses. Your goal is to
    // separate those group into separate strings and return the list of those.
    // Separate groups are balanced (each open brace is properly closed) and not nested within each other
    // Ignore any spaces in the input string.
    // >>> SeparateParenGroups(("( ) (( )) (( )( ))"))
    // (new List<string>(new string[]{(string)"()", (string)"(())", (string)"(()())"}))
    public static List<string> SeparateParenGroups(string paren_string)
    {
        throw new NotImplementedException();
    }

    // Given a positive floating point number, it can be decomposed into
    // and integer part (largest integer smaller than given number) and decimals
    // (leftover part always smaller than 1).
    // Return the decimal part of the number.
    // >>> TruncateNumber((3.5f))
    // (0.5f)
    public static float TruncateNumber(float number)
    {
        throw new NotImplementedException();
    }

    // You're given a list of deposit and withdrawal operations on a bank account that starts with
    // zero balance. Your task is to detect if at any point the balance of account falls below zero, and
    // at that point function should return true. Otherwise it should return false.
    // >>> BelowZero((new List<long>(new long[]{(long)1L, (long)2L, (long)3L})))
    // (false)
    // >>> BelowZero((new List<long>(new long[]{(long)1L, (long)2L, (long)-4L, (long)5L})))
    // (true)
    public static bool BelowZero(List<long> operations)
    {
        throw new NotImplementedException();
    }

    // For a given list of input numbers, calculate Mean Absolute Deviation
    // around the mean of this dataset.
    // Mean Absolute Deviation is the average absolute difference between each
    // element and a centerpoint (mean in this case):
    // MAD = average | x - x_mean |
    // >>> MeanAbsoluteDeviation((new List<float>(new float[]{(float)1.0f, (float)2.0f, (float)3.0f, (float)4.0f})))
    // (1.0f)
    public static float MeanAbsoluteDeviation(List<float> numbers)
    {
        throw new NotImplementedException();
    }

    // Insert a number 'delimeter' between every two consecutive elements of input list `numbers'
    // >>> Intersperse((new List<long>()), (4L))
    // (new List<long>())
    // >>> Intersperse((new List<long>(new long[]{(long)1L, (long)2L, (long)3L})), (4L))
    // (new List<long>(new long[]{(long)1L, (long)4L, (long)2L, (long)4L, (long)3L}))
    public static List<long> Intersperse(List<long> numbers, long delimeter)
    {
        throw new NotImplementedException();
    }

    // Input to this function is a string represented multiple groups for nested parentheses separated by spaces.
    // For each of the group, output the deepest level of nesting of parentheses.
    // E.g. (()()) has maximum two levels of nesting while ((())) has three.
    // >>> ParseNestedParens(("(()()) ((())) () ((())()())"))
    // (new List<long>(new long[]{(long)2L, (long)3L, (long)1L, (long)3L}))
    public static List<long> ParseNestedParens(string paren_string)
    {
        throw new NotImplementedException();
    }

    // Filter an input list of strings only for ones that contain given substring
    // >>> FilterBySubstring((new List<string>()), ("a"))
    // (new List<string>())
    // >>> FilterBySubstring((new List<string>(new string[]{(string)"abc", (string)"bacd", (string)"cde", (string)"array"})), ("a"))
    // (new List<string>(new string[]{(string)"abc", (string)"bacd", (string)"array"}))
    public static List<string> FilterBySubstring(List<string> strings, string substring)
    {
        throw new NotImplementedException();
    }

    // For a given list of integers, return a tuple consisting of a sum and a product of all the integers in a list.
    // Empty sum should be equal to 0 and empty product should be equal to 1.
    // >>> SumProduct((new List<long>()))
    // (Tuple.Create(0L, 1L))
    // >>> SumProduct((new List<long>(new long[]{(long)1L, (long)2L, (long)3L, (long)4L})))
    // (Tuple.Create(10L, 24L))
    public static Tuple<long, long> SumProduct(List<long> numbers)
    {
        throw new NotImplementedException();
    }

    // From a given list of integers, generate a list of rolling maximum element found until given moment
    // in the sequence.
    // >>> RollingMax((new List<long>(new long[]{(long)1L, (long)2L, (long)3L, (long)2L, (long)3L, (long)4L, (long)2L})))
    // (new List<long>(new long[]{(long)1L, (long)2L, (long)3L, (long)3L, (long)3L, (long)4L, (long)4L}))
    public static List<long> RollingMax(List<long> numbers)
    {
        throw new NotImplementedException();
    }
}
