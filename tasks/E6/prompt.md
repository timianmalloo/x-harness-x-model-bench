# HumanEval-C# Batch of 10

Implement the 10 static methods in class `Problem` within the `Problem.cs` file in the provided C# class library project. Each method corresponds to a problem from HumanEval translated to C#.

The project targets .NET 10.0 (`net10.0`). All implementations must be self-contained and replace the `NotImplementedException` stubs.

---

### Problem 1: `HasCloseElements`
```csharp
public static bool HasCloseElements(List<float> numbers, float threshold)
```
Check if in the given list of numbers, any two numbers are closer to each other than the given threshold.
- `HasCloseElements(new List<float> { 1.0f, 2.0f, 3.0f }, 0.5f)` -> `false`
- `HasCloseElements(new List<float> { 1.0f, 2.8f, 3.0f, 4.0f, 5.0f, 2.0f }, 0.3f)` -> `true`

---

### Problem 2: `SeparateParenGroups`
```csharp
public static List<string> SeparateParenGroups(string paren_string)
```
Input to this function is a string containing multiple groups of nested parentheses. Separate those groups into individual strings and return the list of those. Separate groups are balanced (each open paren is properly closed) and not nested within each other. Ignore any spaces in the input string.
- `SeparateParenGroups("( ) (( )) (( )( ))")` -> `new List<string> { "()", "(())", "(()())" }`

---

### Problem 3: `TruncateNumber`
```csharp
public static float TruncateNumber(float number)
```
Given a positive floating point number, decompose it into integer part and decimals (leftover part always smaller than 1). Return the decimal part of the number.
- `TruncateNumber(3.5f)` -> `0.5f`

---

### Problem 4: `BelowZero`
```csharp
public static bool BelowZero(List<long> operations)
```
You are given a list of deposit and withdrawal operations on a bank account that starts with zero balance. Detect if at any point the balance of the account falls below zero. Return `true` if it does, otherwise `false`.
- `BelowZero(new List<long> { 1L, 2L, 3L })` -> `false`
- `BelowZero(new List<long> { 1L, 2L, -4L, 5L })` -> `true`

---

### Problem 5: `MeanAbsoluteDeviation`
```csharp
public static float MeanAbsoluteDeviation(List<float> numbers)
```
For a given list of input numbers, calculate the Mean Absolute Deviation around the mean of this dataset:
`MAD = average | x - x_mean |`
If the list is empty, return `0.0f`.
- `MeanAbsoluteDeviation(new List<float> { 1.0f, 2.0f, 3.0f, 4.0f })` -> `1.0f`

---

### Problem 6: `Intersperse`
```csharp
public static List<long> Intersperse(List<long> numbers, long delimeter)
```
Insert a number `delimeter` between every two consecutive elements of the input list `numbers`.
- `Intersperse(new List<long>(), 4L)` -> `new List<long>()`
- `Intersperse(new List<long> { 1L, 2L, 3L }, 4L)` -> `new List<long> { 1L, 4L, 2L, 4L, 3L }`

---

### Problem 7: `ParseNestedParens`
```csharp
public static List<long> ParseNestedParens(string paren_string)
```
Input to this function is a string representing multiple groups of nested parentheses separated by spaces. For each group, output the deepest level of nesting of parentheses.
- `ParseNestedParens("(()()) ((())) () ((())()())")` -> `new List<long> { 2L, 3L, 1L, 3L }`

---

### Problem 8: `FilterBySubstring`
```csharp
public static List<string> FilterBySubstring(List<string> strings, string substring)
```
Filter an input list of strings, returning only elements that contain the given substring.
- `FilterBySubstring(new List<string> { "abc", "bacd", "cde", "array" }, "a")` -> `new List<string> { "abc", "bacd", "array" }`

---

### Problem 9: `SumProduct`
```csharp
public static Tuple<long, long> SumProduct(List<long> numbers)
```
For a given list of integers, return a tuple consisting of a sum and a product of all integers in the list. An empty sum is equal to `0L` and an empty product is equal to `1L`.
- `SumProduct(new List<long>())` -> `Tuple.Create(0L, 1L)`
- `SumProduct(new List<long> { 1L, 2L, 3L, 4L })` -> `Tuple.Create(10L, 24L)`

---

### Problem 10: `RollingMax`
```csharp
public static List<long> RollingMax(List<long> numbers)
```
From a given list of integers, generate a list of rolling maximum element found until the given moment in the sequence.
- `RollingMax(new List<long> { 1L, 2L, 3L, 2L, 3L, 4L, 2L })` -> `new List<long> { 1L, 2L, 3L, 3L, 3L, 4L, 4L }`
