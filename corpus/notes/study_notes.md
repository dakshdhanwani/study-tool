# CS301 Algorithms — Study Notes

## Week 1: Big-O and Complexity

### The Basics of Asymptotic Analysis
When analyzing algorithms, we care about growth rate as input size n → ∞. Constants and lower-order terms are dropped.

**O(g(n))**: Set of functions f(n) such that ∃ positive constants c, n₀ where f(n) ≤ c·g(n) for all n ≥ n₀.

**Common misunderstanding**: O-notation is an upper bound, not an exact bound. Saying "the algorithm is O(n²)" doesn't mean it takes exactly n² steps — it means it takes *at most* c·n² steps for some constant c.

**Practical rule**: For n = 10⁶:
- O(1): ~nanoseconds
- O(log n): ~20 operations  
- O(n): ~10⁶ operations
- O(n log n): ~2×10⁷ operations
- O(n²): ~10¹² operations — likely too slow

---

## Week 2: Recursion and Divide-and-Conquer

### Solving Recurrences — Three Methods

**Method 1: Substitution**  
Guess the form, verify with induction.
Example: T(n) = 2T(n/2) + n. Guess T(n) = O(n log n). Substitute: 2·(n/2)log(n/2) + n = n(log n - 1) + n = n log n. ✓

**Method 2: Recursion Tree**  
Draw the recursion tree and sum costs level by level.
- Root: f(n) = n
- Level 1: 2 nodes each with cost n/2 → total n  
- Level 2: 4 nodes each with cost n/4 → total n
- ...log n levels each costing n → total O(n log n)

**Method 3: Master Theorem**  
For T(n) = aT(n/b) + f(n), compare f(n) to n^log_b(a):
- Case 1: leaves dominate → T(n) = Θ(n^log_b(a))
- Case 2: equal → T(n) = Θ(n^log_b(a) · log n)
- Case 3: root dominates → T(n) = Θ(f(n))

---

## Week 3: Dynamic Programming

### When to Use DP
Signs you need DP:
1. Problem asks for optimal value (max/min/count)
2. You can break it into smaller same-type subproblems  
3. Naive recursion repeats subproblems

### DP Design Steps
1. Define the subproblem (what does dp[i] or dp[i][j] represent?)
2. Write the recurrence relation
3. Identify base cases
4. Determine evaluation order (which dp values are needed before others?)
5. Extract answer from dp table

### Edit Distance (Levenshtein)
Number of insertions, deletions, substitutions to convert string A → string B.

```
dp[i][j] = edit distance between A[0..i-1] and B[0..j-1]
Base: dp[0][j] = j (insert j chars), dp[i][0] = i (delete i chars)
Recurrence:
  if A[i-1] == B[j-1]: dp[i][j] = dp[i-1][j-1]  (no operation needed)
  else: dp[i][j] = 1 + min(dp[i-1][j],    # delete from A
                            dp[i][j-1],    # insert into A
                            dp[i-1][j-1])  # substitute
```
Time: O(mn), Space: O(mn) or O(min(m,n)) with row optimization.

---

## Week 4: Graph Algorithms

### Graph Representations
- **Adjacency Matrix**: O(V²) space, O(1) edge lookup, good for dense graphs
- **Adjacency List**: O(V+E) space, O(degree(v)) edge lookup, good for sparse graphs

### Topological Sort
Only for Directed Acyclic Graphs (DAGs). Linear ordering of vertices such that for every directed edge u→v, u comes before v.

**Algorithm (Kahn's, BFS-based)**:
1. Compute in-degree of every vertex
2. Add all in-degree 0 vertices to queue
3. Process queue: remove vertex, decrease neighbors' in-degrees; add any that reach 0 to queue
4. If processed all V vertices → DAG; if not → has cycle

**DFS-based**: after DFS from any vertex completes, push to stack. Reverse stack = topological order.

### Strongly Connected Components (SCCs)
SCC: maximal subset of vertices mutually reachable.

**Kosaraju's Algorithm**:
1. DFS on original graph; record finish times
2. Transpose (reverse) the graph
3. DFS on transposed graph in decreasing finish time order
4. Each DFS tree in step 3 is one SCC

Time: O(V + E) — two DFS passes.

**Tarjan's Algorithm**: single DFS, uses low-link values. Also O(V + E).

---

## Week 5: Greedy Algorithms

### Why Greedy Works (or Doesn't)

The exchange argument: to prove a greedy choice is safe, show you can convert any optimal solution to include the greedy choice without making it worse.

**Interval Scheduling (Activity Selection)**:
- Sort activities by finish time
- Always select earliest-finishing activity that doesn't conflict
- **Why optimal**: if OPT doesn't pick the earliest-finishing activity a₁, swap whatever OPT starts with for a₁. The rest of OPT remains valid (a₁ finishes earlier, so conflicts only decrease).

**Huffman Coding**:
- Build optimal prefix-free code for data compression
- Greedy: always merge two lowest-frequency trees
- Proof by exchange argument: merging cheapest pair first never worsens the code

### When Greedy Fails
- 0-1 Knapsack: greedy by value/weight ratio fails. Counter-example: items (weight=10,value=60), (weight=5,value=50), (weight=5,value=50), capacity=10. Greedy takes first item (ratio=6), value=60. Optimal: take two 5-weight items, value=100.

---

## Week 6: Amortized Analysis and Advanced Structures

### Fibonacci Heaps (for context only)
Used in the most efficient implementations of Dijkstra and Prim.
- decrease-key: O(1) amortized
- extract-min: O(log n) amortized
- insert: O(1)

This gives Dijkstra O(E + V log V) — optimal for dense graphs.

### B-Trees
Self-balancing search tree designed for disk access.
- Each node holds many keys (order m: between ⌈m/2⌉ and m keys)
- Height: O(log_m(n)) — much shorter than binary BST
- All leaves at same level

Used in databases (MySQL, PostgreSQL) and file systems (NTFS, ext4).
A B+ tree variant stores data only in leaves, with internal nodes as index.

---

## Exam Tips

1. **For O-notation proofs**: find the constants c and n₀, don't just handwave.
2. **For DP**: define dp[i][j] clearly before writing recurrence — examiners give partial credit if recurrence is right even if code is wrong.
3. **For graph algorithms**: always state time complexity in terms of V (vertices) and E (edges).
4. **For greedy**: always justify WHY greedy works (or show a counter-example if it doesn't).
5. **Common mistake**: Dijkstra fails on negative edges. If you see negative weights → Bellman-Ford.
6. **Heapsort is NOT stable**: this matters when equal elements must preserve original order.
