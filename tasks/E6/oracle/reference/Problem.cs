using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Text;

public class Problem
{
    // Check if in given list of numbers, are any two numbers closer to each other than
    // given threshold.
    public static bool HasCloseElements(List<float> numbers, float threshold)
    {
        for (int i = 0; i < numbers.Count; i++)
        {
            for (int j = i + 1; j < numbers.Count; j++)
            {
                if (Math.Abs(numbers[i] - numbers[j]) < threshold)
                    return true;
            }
        }
        return false;
    }

    // Input to this function is a string containing multiple groups of nested parentheses. Your goal is to
    // separate those group into separate strings and return the list of those.
    public static List<string> SeparateParenGroups(string paren_string)
    {
        var result = new List<string>();
        var current = new StringBuilder();
        int depth = 0;
        foreach (char c in paren_string)
        {
            if (c == '(')
            {
                depth++;
                current.Append(c);
            }
            else if (c == ')')
            {
                depth--;
                current.Append(c);
                if (depth == 0)
                {
                    result.Add(current.ToString());
                    current.Clear();
                }
            }
        }
        return result;
    }

    // Given a positive floating point number, it can be decomposed into
    // and integer part (largest integer smaller than given number) and decimals
    // (leftover part always smaller than 1).
    // Return the decimal part of the number.
    public static float TruncateNumber(float number)
    {
        return number % 1.0f;
    }

    // You're given a list of deposit and withdrawal operations on a bank account that starts with
    // zero balance. Your task is to detect if at any point the balance of account falls below zero.
    public static bool BelowZero(List<long> operations)
    {
        long balance = 0;
        foreach (long op in operations)
        {
            balance += op;
            if (balance < 0)
                return true;
        }
        return false;
    }

    // For a given list of input numbers, calculate Mean Absolute Deviation
    // around the mean of this dataset.
    public static float MeanAbsoluteDeviation(List<float> numbers)
    {
        if (numbers.Count == 0)
            return 0.0f;
        float mean = numbers.Average();
        float sumDev = numbers.Sum(x => Math.Abs(x - mean));
        return sumDev / numbers.Count;
    }

    // Insert a number 'delimeter' between every two consecutive elements of input list `numbers'
    public static List<long> Intersperse(List<long> numbers, long delimeter)
    {
        var result = new List<long>();
        for (int i = 0; i < numbers.Count; i++)
        {
            if (i > 0)
                result.Add(delimeter);
            result.Add(numbers[i]);
        }
        return result;
    }

    // Input to this function is a string represented multiple groups for nested parentheses separated by spaces.
    // For each of the group, output the deepest level of nesting of parentheses.
    public static List<long> ParseNestedParens(string paren_string)
    {
        var result = new List<long>();
        var groups = paren_string.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        foreach (var group in groups)
        {
            long maxDepth = 0;
            long currentDepth = 0;
            foreach (char c in group)
            {
                if (c == '(')
                {
                    currentDepth++;
                    if (currentDepth > maxDepth)
                        maxDepth = currentDepth;
                }
                else if (c == ')')
                {
                    currentDepth--;
                }
            }
            result.Add(maxDepth);
        }
        return result;
    }

    // Filter an input list of strings only for ones that contain given substring
    public static List<string> FilterBySubstring(List<string> strings, string substring)
    {
        return strings.Where(s => s.Contains(substring)).ToList();
    }

    // For a given list of integers, return a tuple consisting of a sum and a product of all the integers in a list.
    public static Tuple<long, long> SumProduct(List<long> numbers)
    {
        long sum = 0;
        long prod = 1;
        foreach (long n in numbers)
        {
            sum += n;
            prod *= n;
        }
        return Tuple.Create(sum, prod);
    }

    // From a given list of integers, generate a list of rolling maximum element found until given moment in the sequence.
    public static List<long> RollingMax(List<long> numbers)
    {
        var result = new List<long>();
        if (numbers.Count == 0)
            return result;
        long currentMax = numbers[0];
        foreach (long n in numbers)
        {
            if (n > currentMax)
                currentMax = n;
            result.Add(currentMax);
        }
        return result;
    }
}
