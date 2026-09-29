Write a Python 3 program in `solution.py` that solves the problem below. It reads the input from standard input and prints the answer to standard output. Use only the standard library.

If anything in the requirement is unclear, you can ask the user a question with the `ask_user` tool; it returns the user's reply.

---

This problem is a simplified version of Problem F.
You are given an integer sequence of length N: A = (A_1, A_2, \ldots, A_N).
When splitting A at one position into two non-empty (contiguous) subarrays, find the maximum possible sum of the counts in those subarrays.
More formally, find the maximum sum of the following two values for an integer i such that 1 \leq i \leq N-1: the count of integers in (A_1, A_2, \ldots, A_i), and the count of integers in (A_{i+1}, A_{i+2}, \ldots, A_N).
Input
The input is given from Standard Input in the following format:
N
A_1 A_2 \ldots A_N
Output
Print the answer.
Constraints
- 2 \leq N \leq 3 \times 10^5
- 1 \leq A_i \leq N (1 \leq i \leq N)
- All input values are integers.
