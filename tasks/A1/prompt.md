Write a Python 3 program in `solution.py` that solves the problem below. It reads the input from standard input and prints the answer to standard output. Use only the standard library.

If anything in the requirement is unclear, you can ask the user a question with the `ask_user` tool; it returns the user's reply.

---

There are N black balls and M white balls.
Each ball has a value. The value of the i-th black ball (1 \le i \le N) is B_i, and the value of the j-th white ball (1 \le j \le M) is W_j.
Choose zero or more balls so that the number of black balls chosen is at least the number of white balls chosen. Among all such choices, find the sum of the values of the chosen balls.
Input
The input is given from Standard Input in the following format:
N M
B_1 B_2 \ldots B_N
W_1 W_2 \ldots W_M
Output
Print the answer.
Constraints
- 1 \leq N,M \leq 2\times 10^5
- -10^9 \leq B_i, W_j \leq 10^9
- All input values are integers.
