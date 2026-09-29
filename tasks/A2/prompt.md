Write a Python 3 program in `solution.py` that solves the problem below. It reads the input from standard input and prints the answer to standard output. Use only the standard library.

If anything in the requirement is unclear, you can ask the user a question with the `ask_user` tool; it returns the user's reply.

---

You are given a string S of length N consisting of 0 and 1. 
You may perform the following operation any number of times (possibly zero):
- Choose an integer i (1 \leq i \leq N-1) and swap the i-th and (i+1)-th characters of S.
Find the minimum number of operations needed so that all 1s are contiguous.
Here, all 1s are said to be contiguous if and only if there exist integers l and r (1 \leq l \leq r \leq N) such that the i-th character of S is 1 if and only if l \leq i \leq r, and 0 otherwise.
Input
The input is given from Standard Input in the following format:
N
S
Output
Print the answer.
Constraints
- 2 \leq N \leq 5 \times 10^5
- N is an integer.
- S is a length N string of 0 and 1.
