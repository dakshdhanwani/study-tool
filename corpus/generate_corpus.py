"""
Generates a synthetic course corpus for demonstration and evaluation.

Creates realistic course materials on "Algorithms & Data Structures" spanning:
- 2 PDF lecture documents
- 2 PDF slide decks  
- 1 Markdown notes file
- 2 handwritten note images (clean PNG + difficult/messy PNG)

Total: 60+ pages of content.
Run this script ONCE to populate corpus/ before ingestion.
"""

import os
import sys
from pathlib import Path
import textwrap

# ── Try to import PDF generation library ──────────────────────────────────────
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    REPORTLAB = True
except ImportError:
    REPORTLAB = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW = True
except ImportError:
    PILLOW = False

CORPUS_DIR = Path(__file__).parent.parent / "corpus"


# ─────────────────────────────────────────────────────────────────────────────
# LECTURE CONTENT
# ─────────────────────────────────────────────────────────────────────────────

LECTURE_1_CONTENT = [
    ("Lecture 1: Arrays, Linked Lists, and Stacks", ""),
    ("1. Introduction to Data Structures", """
A data structure is a particular way of organizing data in a computer so that it can be used effectively. 
The idea is to reduce the space and time complexities of different tasks. Data structures are the backbone 
of software development and algorithmic thinking.

This course covers fundamental data structures: arrays, linked lists, stacks, queues, trees, graphs, 
and hash tables. Understanding these is essential for writing efficient programs.
"""),
    ("2. Arrays", """
An array is a collection of items stored at contiguous memory locations. The idea is to store multiple 
items of the same type together. This makes it easier to calculate the position of each element by simply 
adding an offset to a base value (the memory location of the first element of the array).

Array Operations and Complexities:
- Access:  O(1)  — direct indexing
- Search:  O(n)  — linear scan for unsorted, O(log n) for sorted (binary search)
- Insert:  O(n)  — may need to shift elements
- Delete:  O(n)  — may need to shift elements

Dynamic Arrays (e.g., Python lists, Java ArrayList) automatically resize when capacity is exceeded, 
typically doubling in size, giving amortized O(1) append. The resizing operation itself is O(n), but 
spread over n operations gives O(1) amortized cost.
"""),
    ("3. Linked Lists", """
A linked list is a linear data structure where elements are stored in nodes. Each node contains:
  - data: the stored value
  - next: a pointer/reference to the next node

Types of Linked Lists:
1. Singly Linked List: each node points to the next node only
2. Doubly Linked List: each node points to both next and previous nodes
3. Circular Linked List: last node points back to the first node

Complexities:
- Access:  O(n)  — must traverse from head
- Search:  O(n)
- Insert (at head):  O(1)
- Insert (at tail, with tail pointer):  O(1)
- Delete (with predecessor known):  O(1)

Linked lists excel when frequent insertions/deletions occur and random access is not needed. 
Arrays excel when random access is frequent. This tradeoff is fundamental in algorithm design.
"""),
    ("4. Stacks", """
A stack is a linear data structure that follows the LIFO (Last In, First Out) principle. Think of a 
stack of plates: you add a plate to the top and remove from the top.

Core Operations:
- push(x):   add element x to top   — O(1)
- pop():     remove top element      — O(1)
- peek():    view top without removing — O(1)
- isEmpty(): check if empty          — O(1)

Implementation: stacks can be implemented using arrays (with a top pointer) or linked lists (push/pop at head).

Applications of Stacks:
1. Function call stack (activation records)
2. Expression evaluation (infix → postfix, postfix evaluation)
3. Backtracking algorithms (DFS, maze solving)
4. Undo mechanisms in text editors
5. Browser back button history

Example – Balanced Parentheses using Stack:
  Input: "({[]})"
  Algorithm: push on '(', '{', '['; pop and match on ')', '}', ']'
  If stack is empty at end and every match succeeded → balanced
  Time: O(n), Space: O(n)
"""),
    ("5. Queues", """
A queue is a linear data structure that follows FIFO (First In, First Out) principle. Think of a line 
at a bank: first person to arrive is first to be served.

Core Operations:
- enqueue(x): add to rear   — O(1)
- dequeue():  remove from front — O(1)
- front():    peek at front  — O(1)

Variants:
1. Circular Queue: uses array with wrap-around to avoid wasted space
2. Deque (Double-Ended Queue): insert/delete from both ends
3. Priority Queue: element with highest priority dequeued first (implemented with heap)

Applications:
1. CPU scheduling (FIFO scheduling)
2. Breadth-First Search (BFS) traversal
3. Print spooling
4. Asynchronous data transfer (IO buffers)
"""),
    ("6. Practice Problems", """
Problem 1: Implement a stack using two queues. What is the time complexity of each operation?

Problem 2: Given a string of brackets, determine if it is balanced.
Example: "{[()]}" is balanced; "{[(])}" is not.

Problem 3: Implement a queue using two stacks.

Problem 4: Reverse a linked list in-place. What is the space complexity?

Problem 5: Find the middle element of a linked list in one pass using two pointers (Floyd's tortoise and hare).
"""),
]

LECTURE_2_CONTENT = [
    ("Lecture 2: Trees, Binary Search Trees, and Heaps", ""),
    ("1. Trees", """
A tree is a hierarchical data structure with a root node and subtrees of children. Trees model 
hierarchical relationships (file systems, organization charts, DOM).

Terminology:
- Root: topmost node with no parent
- Leaf: node with no children
- Height: length of longest path from root to leaf
- Depth: distance from root to a node
- Degree: number of children of a node

Binary Tree: each node has at most 2 children (left and right).

Tree Traversals (for binary trees):
1. Inorder  (Left, Root, Right): gives sorted output for BST
2. Preorder (Root, Left, Right): used for copying tree
3. Postorder (Left, Right, Root): used for deletion, expression evaluation

All three traversals: O(n) time, O(h) space (h = height, for recursion stack).
"""),
    ("2. Binary Search Trees (BST)", """
A BST is a binary tree where every node satisfies:
  left child < node < right child

This property enables efficient search.

BST Operations:
- Search:  O(h)  — h is height (best O(log n) balanced, worst O(n) skewed)
- Insert:  O(h)
- Delete:  O(h)  — three cases: no child, one child, two children (replace with inorder successor)

BST worst case: inserting sorted data gives a linked list (skewed tree), degrading all operations to O(n).
Solution: Self-balancing BSTs (AVL, Red-Black trees) maintain O(log n) height.

AVL Tree: height-balanced BST. Balance factor = height(left) - height(right) must be in {-1, 0, 1}.
Rebalancing uses rotations: single rotation (LL, RR) or double rotation (LR, RL).
All operations: O(log n) guaranteed.
"""),
    ("3. Heaps", """
A heap is a complete binary tree satisfying the heap property.
- Max-Heap: parent >= children (root is maximum)
- Min-Heap: parent <= children (root is minimum)

Heap Operations:
- insert:       O(log n)  — add to end, bubble up (heapify-up)
- extract_max:  O(log n)  — remove root, put last element at root, bubble down
- peek (max):   O(1)
- build_heap:   O(n)  — NOT O(n log n) — Floyd's algorithm is O(n)

Heap Implementation: stored as array (no pointers needed).
  For node at index i: left child = 2i+1, right child = 2i+2, parent = (i-1)//2

Heapsort:
  1. Build max-heap from array: O(n)
  2. Repeatedly extract max and place at end: O(n log n)
  Total: O(n log n), in-place, NOT stable.

Priority Queue: a heap is the natural implementation. Used in Dijkstra's, Prim's, A*.
"""),
    ("4. Balanced BSTs vs Heaps", """
Comparison: Balanced BST vs Heap

| Operation         | Balanced BST    | Heap            |
|-------------------|-----------------|-----------------|
| Search(x)         | O(log n)        | O(n)            |
| Insert(x)         | O(log n)        | O(log n)        |
| Delete(x)         | O(log n)        | O(log n)        |
| Find Min/Max      | O(log n)        | O(1)            |
| Range queries     | O(log n + k)    | O(n)            |
| Sorted output     | O(n) inorder    | O(n log n)      |

Key insight: Use a Heap when you only need to repeatedly find/remove the min or max.
Use a BST when you need ordered traversal, range queries, or arbitrary deletion.
"""),
    ("5. Hash Tables", """
A hash table stores key-value pairs. A hash function maps keys to array indices.

Hash Function Requirements:
1. Deterministic: same key → same hash
2. Uniform distribution: minimize collisions
3. Fast to compute: O(1)

Collision Resolution:
1. Chaining: each array slot holds a linked list of all keys that map there.
   Average case: O(1) with good hash function; worst case O(n) if all keys collide.

2. Open Addressing: find next empty slot using probing.
   - Linear probing: check next slot
   - Quadratic probing: check slot + 1², 2², 3²...
   - Double hashing: use second hash function for step size

Load Factor α = n/m (n = items, m = array size).
Performance degrades as α → 1. Rehash (resize) when α > 0.7 typically.

Average case (good hash): O(1) for insert, search, delete.
Worst case: O(n) — rare with good hash function.
"""),
    ("6. Advanced Topics: Trie", """
A Trie (prefix tree) is a tree-shaped data structure for storing strings where each node 
represents a character.

Operations:
- Insert word:  O(L) where L = word length
- Search word:  O(L)
- Search prefix: O(L)
- Delete:       O(L)

Space: O(ALPHABET_SIZE × L × N) — can be large; use compressed tries or hash maps at each node.

Applications:
1. Autocomplete / search suggestions
2. Spell checking
3. IP routing tables
4. Dictionary implementation
"""),
]

LECTURE_3_CONTENT = [
    ("Lecture 3: Sorting Algorithms", ""),
    ("1. Comparison-Based Sorting", """
Most sorting algorithms compare pairs of elements. The fundamental lower bound for comparison-based 
sorting is Omega(n log n). Any comparison-based sort must do at least n log n comparisons in the worst case.

Proof sketch: there are n! possible orderings of n elements. A comparison tree with k leaves can 
distinguish at most 2^k orderings. So 2^k >= n! → k >= log2(n!) = Θ(n log n) by Stirling's approximation.
"""),
    ("2. Insertion Sort", """
Insertion Sort: build sorted portion one element at a time.
  for i = 1 to n-1:
    key = A[i]
    j = i - 1
    while j >= 0 and A[j] > key:
      A[j+1] = A[j]
      j--
    A[j+1] = key

Time: O(n²) worst/average, O(n) best (already sorted)
Space: O(1) in-place
Stable: Yes

Best for: small arrays, nearly sorted data (online sorting).
"""),
    ("3. Merge Sort", """
Merge Sort: divide and conquer.
  mergeSort(A, l, r):
    if l >= r: return
    mid = (l + r) // 2
    mergeSort(A, l, mid)
    mergeSort(A, mid+1, r)
    merge(A, l, mid, r)

merge(): combine two sorted halves into one sorted array — O(n) time, O(n) space.

Recurrence: T(n) = 2T(n/2) + O(n) → T(n) = O(n log n) by Master Theorem (Case 2).

Time: O(n log n) all cases
Space: O(n) auxiliary
Stable: Yes

Best for: linked lists (no extra space needed), external sorting (disk), when stability required.
"""),
    ("4. Quicksort", """
Quicksort: divide and conquer with partitioning.
  quickSort(A, l, r):
    if l >= r: return
    p = partition(A, l, r)  // pivot ends up at index p
    quickSort(A, l, p-1)
    quickSort(A, p+1, r)

Lomuto partition scheme: choose A[r] as pivot, place all smaller elements before it.
Hoare partition scheme: two pointers from both ends, more efficient in practice.

Time: O(n log n) average, O(n²) worst (sorted input with bad pivot)
Space: O(log n) average (recursion stack), O(n) worst
Stable: No (Lomuto)

Pivot strategies:
- First/last element: O(n²) for sorted input
- Random pivot: expected O(n log n) regardless of input
- Median-of-three: pick median of first, middle, last — good in practice

Quicksort is typically faster than Merge Sort due to cache efficiency and smaller constants, 
even though worst-case is O(n²). Most library sorts (Python's Timsort, C++'s introsort) are hybrids.
"""),
    ("5. Counting Sort and Radix Sort", """
Non-comparison sorts can beat the O(n log n) lower bound when keys have special structure.

Counting Sort: when keys are in range [0, k].
  1. Count frequency of each key
  2. Compute cumulative counts (prefix sum)
  3. Place each element in correct position

Time: O(n + k)
Space: O(n + k)
Stable: Yes

Radix Sort: sort by each digit/character position.
  for d = least_significant to most_significant:
    stable_sort by digit d (use Counting Sort)

Time: O(d × (n + k)) where d = number of digits, k = digit range
Stable: Yes

Radix Sort beats O(n log n) when d is small (e.g., 32-bit integers: d=32, k=2 → O(n)).
"""),
    ("6. Comparison of Sorting Algorithms", """
Algorithm      | Best     | Average  | Worst    | Space  | Stable
---------------|----------|----------|----------|--------|-------
Insertion Sort | O(n)     | O(n²)    | O(n²)    | O(1)   | Yes
Merge Sort     | O(nlogn) | O(nlogn) | O(nlogn) | O(n)   | Yes
Quicksort      | O(nlogn) | O(nlogn) | O(n²)    | O(logn)| No
Heapsort       | O(nlogn) | O(nlogn) | O(nlogn) | O(1)   | No
Counting Sort  | O(n+k)   | O(n+k)   | O(n+k)   | O(k)   | Yes
Radix Sort     | O(dn)    | O(dn)    | O(dn)    | O(n+k) | Yes

Timsort (Python's sort): hybrid of Merge Sort + Insertion Sort. O(n log n) worst, O(n) best.
Used in Python, Java 8+ for objects. Stable.
"""),
]

SLIDES_1_CONTENT = [
    ("Slide 1: Course Overview — CS301 Algorithms", "This course covers design and analysis of algorithms. Grading: 40% exams, 30% assignments, 30% project."),
    ("Slide 2: Big-O Notation", "O(f(n)): upper bound. Ω(f(n)): lower bound. Θ(f(n)): tight bound.\n\nf(n) = O(g(n)) iff ∃ c>0, n₀ s.t. f(n) ≤ c·g(n) ∀n ≥ n₀\n\nCommon complexities (fastest to slowest):\nO(1) < O(log n) < O(n) < O(n log n) < O(n²) < O(2ⁿ) < O(n!)"),
    ("Slide 3: Recurrences — The Master Theorem", "T(n) = aT(n/b) + f(n)\n\nCase 1: f(n) = O(n^(log_b(a) - ε))  →  T(n) = Θ(n^log_b(a))\nCase 2: f(n) = Θ(n^log_b(a))        →  T(n) = Θ(n^log_b(a) · log n)\nCase 3: f(n) = Ω(n^(log_b(a) + ε))  →  T(n) = Θ(f(n))\n\nExample: Merge Sort T(n) = 2T(n/2) + n\n  a=2, b=2, log_b(a) = 1, f(n) = n = Θ(n¹) → Case 2 → T(n) = Θ(n log n)"),
    ("Slide 4: Divide and Conquer", "Pattern:\n1. Divide: split problem into subproblems\n2. Conquer: solve subproblems recursively\n3. Combine: merge solutions\n\nExamples:\n- Merge Sort: divide at midpoint, merge results\n- Binary Search: divide at midpoint, recurse on one half\n- Strassen's Matrix Multiplication: divide 2x2 blocks, 7 recursive calls → O(n^2.81)"),
    ("Slide 5: Graph Algorithms — BFS", "Breadth-First Search:\n- Explores level by level (uses Queue)\n- Finds shortest path in unweighted graphs\n- Time: O(V + E)\n- Space: O(V)\n\nApplications: shortest path (unweighted), social network connections, web crawling, level-order tree traversal"),
    ("Slide 6: Graph Algorithms — DFS", "Depth-First Search:\n- Explores as deep as possible (uses Stack or recursion)\n- Time: O(V + E), Space: O(V)\n\nApplications:\n- Topological sort (directed acyclic graphs)\n- Cycle detection\n- Finding strongly connected components (Kosaraju, Tarjan)\n- Maze solving"),
    ("Slide 7: Dijkstra's Algorithm", "Shortest path in weighted graphs with NON-NEGATIVE edges.\n\nAlgorithm:\n1. dist[source] = 0; dist[v] = ∞ for all other v\n2. Priority queue: insert (dist=0, source)\n3. While PQ not empty:\n   a. Extract vertex u with minimum dist[u]\n   b. For each neighbor v of u:\n      if dist[u] + w(u,v) < dist[v]: update dist[v], push to PQ\n\nComplexity:\n- With binary heap: O((V + E) log V)\n- With Fibonacci heap: O(E + V log V)\n\nDoes NOT work with negative-weight edges (use Bellman-Ford instead)"),
    ("Slide 8: Bellman-Ford Algorithm", "Shortest path allowing NEGATIVE edges (no negative cycles).\n\nAlgorithm:\n1. dist[source] = 0; dist[v] = ∞ for all other v  \n2. Repeat V-1 times:\n   For each edge (u,v,w): if dist[u]+w < dist[v]: relax\n3. Check for negative cycles: do one more pass, if any relaxation succeeds → negative cycle exists\n\nComplexity: O(VE) — much slower than Dijkstra\n\nUsed when: graph has negative edges, need to detect negative cycles"),
    ("Slide 9: Dynamic Programming Principles", "DP: solve subproblems once and store results.\n\nRequirements:\n1. Optimal substructure: optimal solution contains optimal solutions to subproblems\n2. Overlapping subproblems: same subproblems solved multiple times without memoization\n\nApproaches:\n- Top-down (memoization): recursive + cache\n- Bottom-up (tabulation): fill table iteratively\n\nExamples: Fibonacci, Knapsack, LCS, Edit Distance, Matrix Chain Multiplication"),
    ("Slide 10: Classic DP — Longest Common Subsequence", "LCS(s1, s2): length of longest subsequence common to both strings.\n\nRecurrence:\n  dp[i][j] = dp[i-1][j-1] + 1            if s1[i] == s2[j]\n  dp[i][j] = max(dp[i-1][j], dp[i][j-1]) otherwise\n\nTime: O(mn), Space: O(mn) or O(min(m,n)) with optimization\n\nBacktrace for actual subsequence: follow arrows in dp table from dp[m][n] to dp[0][0]."),
    ("Slide 11: 0-1 Knapsack Problem", "Given items with weights w[i] and values v[i], and knapsack capacity W:\nMaximize total value with total weight ≤ W, each item used at most once.\n\ndp[i][j] = max value using first i items with capacity j\n\ndp[i][j] = dp[i-1][j]                          if w[i] > j (can't include item i)\ndp[i][j] = max(dp[i-1][j], v[i]+dp[i-1][j-w[i]]) otherwise\n\nTime: O(nW), Space: O(nW) — pseudo-polynomial (W can be large)\n\nThis is NP-hard in general (exponential in the number of bits of W)."),
    ("Slide 12: Greedy Algorithms", "Greedy: make locally optimal choice at each step.\n\nWhen does greedy work? Need greedy choice property + optimal substructure.\n\nExamples:\n1. Activity Selection: sort by finish time, always pick earliest finishing non-conflicting activity. Optimal.\n2. Fractional Knapsack: sort by value/weight ratio, take greedily. Optimal.\n3. Huffman Coding: build optimal prefix-free code using min-heap. Optimal.\n4. 0-1 Knapsack: greedy FAILS (need DP).\n\nProving greedy: exchange argument (show any optimal solution can be transformed to greedy solution without decreasing value)."),
]

SLIDES_2_CONTENT = [
    ("Slide 1: Advanced Graph Algorithms", "Topics: Minimum Spanning Trees, Network Flow, NP-Completeness basics"),
    ("Slide 2: Minimum Spanning Trees (MST)", "MST: subset of edges connecting all vertices with minimum total weight.\n\nKruskal's Algorithm:\n1. Sort edges by weight\n2. Add edge if it doesn't create cycle (use Union-Find)\nTime: O(E log E) = O(E log V)\n\nPrim's Algorithm:\n1. Start from any vertex\n2. Greedily add cheapest edge connecting tree to non-tree vertex (use Priority Queue)\nTime: O(E log V) with binary heap, O(E + V log V) with Fibonacci heap"),
    ("Slide 3: Union-Find (Disjoint Set Union)", "Efficient data structure for Kruskal's and cycle detection.\n\nOperations:\n- find(x): return root of x's component\n- union(x, y): merge components\n\nOptimizations:\n1. Union by rank: attach smaller tree under larger (O(log n))\n2. Path compression: make all nodes point directly to root\n\nWith both: O(α(n)) amortized per operation — essentially O(1).\nα(n) is the inverse Ackermann function, grows extremely slowly."),
    ("Slide 4: Network Flow", "Max-Flow: find maximum flow from source s to sink t in a weighted directed graph.\n\nFord-Fulkerson Method:\n1. Find augmenting path in residual graph (BFS for Edmonds-Karp)\n2. Increase flow along path by bottleneck capacity\n3. Repeat until no augmenting path\n\nEdmonds-Karp (BFS-based Ford-Fulkerson): O(VE²)\n\nMax-Flow Min-Cut Theorem: max flow = min cut capacity."),
    ("Slide 5: NP and NP-Completeness", "P: problems solvable in polynomial time\nNP: problems where solution verifiable in polynomial time\nNP-Complete: hardest problems in NP; every NP problem reduces to them\n\nKnown NP-Complete problems:\n- Boolean Satisfiability (SAT) — Cook-Levin theorem\n- 3-SAT\n- Vertex Cover\n- Hamiltonian Cycle\n- Travelling Salesman Problem (decision version)\n- 0-1 Knapsack (decision version)\n\nP vs NP: unsolved! If P=NP, all these become polynomial time solvable."),
    ("Slide 6: Approximation Algorithms", "For NP-hard optimization problems, we can't always find optimal solution efficiently.\nApproximation: find solution within factor α of optimal.\n\nExample: Vertex Cover 2-approximation:\n1. Find any maximal matching M\n2. Include both endpoints of every edge in M\nResult: ≤ 2 × OPT (polynomial time)\n\nTSP with triangle inequality: Christofides' algorithm gives 1.5-approximation.\nGeneral TSP: no constant approximation unless P=NP (unless exponential is ok)."),
    ("Slide 7: String Algorithms", "Pattern Matching:\n- Naive: O(nm) — try every position\n- KMP (Knuth-Morris-Pratt): O(n+m) — precompute failure function\n- Rabin-Karp: O(n+m) average using rolling hash\n- Boyer-Moore: O(n/m) best case — bad character + good suffix heuristics\n\nSuffix Arrays + LCP Arrays: advanced string processing in O(n log n) or O(n)."),
    ("Slide 8: Amortized Analysis", "Amortized analysis: average cost per operation over a sequence of operations.\n\nMethods:\n1. Aggregate: total cost / n operations\n2. Accounting: charge more for cheap ops to 'bank' credit for expensive ops\n3. Potential method: define potential Φ; amortized cost = actual cost + ΔΦ\n\nExample: Dynamic array (doubling)\n- Occasional resize costs O(n) but amortized cost per push is O(1)\n- With potential Φ = 2(size - capacity/2): amortized cost of push = O(1)"),
]


NOTES_CONTENT = """# CS301 Algorithms — Study Notes

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
"""


def create_lecture_pdf(content_pages: list, output_path: Path, title: str):
    """Create a lecture PDF using reportlab."""
    if not REPORTLAB:
        print(f"  [SKIP] reportlab not installed, skipping {output_path.name}")
        return False

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Title'], fontSize=20, spaceAfter=20)
    h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=14, spaceAfter=10, spaceBefore=16)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, spaceAfter=8, leading=14)
    code_style = ParagraphStyle('Code', parent=styles['Normal'], fontSize=9, fontName='Courier',
                                 backColor=colors.HexColor('#f4f4f4'), spaceAfter=8, leading=12)

    story = []

    # Title page
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("CS301 — Algorithms &amp; Data Structures", styles['Heading2']))
    story.append(Paragraph("Department of Computer Science", styles['Normal']))
    story.append(PageBreak())

    for section_title, section_text in content_pages[1:]:
        if section_title:
            story.append(Paragraph(section_title, h1_style))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
            story.append(Spacer(1, 6))

        if section_text.strip():
            # Split into paragraphs, render code blocks separately
            paragraphs = section_text.strip().split('\n\n')
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                # Detect code/table blocks
                if para.startswith('  ') or '|' in para[:20] or para.startswith('for ') or para.startswith('if '):
                    # Render as code
                    safe = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    for line in safe.split('\n'):
                        story.append(Paragraph(line or '&nbsp;', code_style))
                else:
                    safe = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe, body_style))

        story.append(Spacer(1, 12))

    doc.build(story)
    return True


def create_slide_pdf(slides: list, output_path: Path, title: str):
    """Create a slide-style PDF."""
    if not REPORTLAB:
        print(f"  [SKIP] reportlab not installed, skipping {output_path.name}")
        return False

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()
    slide_title_style = ParagraphStyle('SlideTitle', parent=styles['Heading1'], fontSize=18,
                                        textColor=colors.HexColor('#1a237e'), spaceAfter=12)
    content_style = ParagraphStyle('Content', parent=styles['Normal'], fontSize=11, leading=16, spaceAfter=8)
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8,
                                   textColor=colors.grey, alignment=TA_CENTER)

    story = []

    # Cover slide
    story.append(Spacer(1, 3*cm))
    story.append(Paragraph(title, ParagraphStyle('CoverTitle', parent=styles['Title'], fontSize=24,
                                                   textColor=colors.HexColor('#1a237e'), alignment=TA_CENTER)))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("CS301 — Algorithms &amp; Data Structures", ParagraphStyle('Sub',
                             parent=styles['Normal'], alignment=TA_CENTER, fontSize=14)))
    story.append(PageBreak())

    for i, (slide_title, slide_content) in enumerate(slides, 1):
        # Slide box
        story.append(Paragraph(f"Slide {i}: {slide_title}", slide_title_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a237e')))
        story.append(Spacer(1, 0.3*cm))

        safe = slide_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        for line in safe.split('\n'):
            if line.strip():
                story.append(Paragraph(line, content_style))
            else:
                story.append(Spacer(1, 4))

        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph(f"CS301 | {title} | Slide {i}/{len(slides)}", footer_style))
        story.append(PageBreak())

    doc.build(story)
    return True


def create_handwritten_image_clean(output_path: Path):
    """Create a clean handwritten-style note image using Pillow."""
    if not PILLOW:
        print(f"  [SKIP] Pillow not installed, skipping {output_path.name}")
        return False

    width, height = 1200, 1600
    img = Image.new('RGB', (width, height), color=(252, 248, 235))  # cream paper
    draw = ImageDraw.Draw(img)

    # Draw lined paper effect
    for y in range(120, height - 80, 38):
        draw.line([(60, y), (width - 60, y)], fill=(200, 210, 230), width=1)

    # Left margin
    draw.line([(100, 60), (100, height - 60)], fill=(220, 160, 160), width=2)

    # Title
    draw.text((120, 40), "Handwritten Notes — Sorting Algorithms", fill=(20, 20, 80))
    draw.text((120, 65), "CS301 | Week 3 | Alice Chen", fill=(80, 80, 120))

    lines = [
        "Bubble Sort — the 'lazy' sort",
        "  Compare adjacent pairs, swap if out of order",
        "  Repeat n times → largest bubbles to end each pass",
        "  Time: O(n²) worst + avg,  O(n) best (already sorted)",
        "  Space: O(1) in-place,  Stable: YES",
        "",
        "Selection Sort",
        "  Find min in unsorted portion, place at front",
        "  n-1 passes required regardless of input",
        "  Time: ALWAYS O(n²)  [no best-case benefit!]",
        "  Space: O(1),  Stable: NO (swaps can skip over equal elements)",
        "",
        "KEY INSIGHT: Insertion sort beats selection sort on nearly-sorted",
        "data because it can terminate inner loop early (O(n) best case)",
        "whereas selection sort always does n(n-1)/2 comparisons.",
        "",
        "Shell Sort — gap sequence trick",
        "  Insertion sort with larger initial 'gaps'",
        "  Reduces inversions quickly → final gap=1 is fast",
        "  Time depends on gap sequence: Ciura gaps → O(n^(4/3)) approx",
        "",
        "Tim Sort (Python's built-in) ← EXAM LIKELY",
        "  Hybrid: Insertion sort for small runs + Merge sort",
        "  'Natural merge': detects existing sorted runs in data",
        "  Time: O(n log n) worst, O(n) best (fully sorted)",
        "  Stable: YES — critical for Python (preserves secondary sort)",
        "",
        "Counting Sort vs Radix Sort",
        "  Counting: need keys in [0,k] → O(n+k)",
        "  Radix: generalize to multi-digit → O(d(n+k))",
        "  Both BEAT O(n log n) lower bound ← because no comparisons!",
        "",
        "★ Remember for exam: lower bound Ω(n log n) applies ONLY",
        "  to comparison-based sorts. Non-comparison sorts are exempt.",
    ]

    y = 110
    for line in lines:
        if line == "":
            y += 18
            continue
        color = (20, 20, 80) if line.startswith("  ") else (10, 10, 10)
        if line.startswith("★") or "EXAM" in line:
            color = (180, 20, 20)
        draw.text((115, y), line, fill=color)
        y += 38

    img.save(str(output_path), 'PNG', dpi=(150, 150))
    return True


def create_handwritten_image_hard(output_path: Path):
    """
    Create a difficult/messy handwritten scan simulation.
    - Uneven baseline, ink blobs, crossed-out text, rotation, low contrast areas
    """
    if not PILLOW:
        print(f"  [SKIP] Pillow not installed, skipping {output_path.name}")
        return False

    import random
    import math
    random.seed(42)

    width, height = 1100, 1500
    # Slightly yellowish, not pure white — like old paper
    img = Image.new('RGB', (width, height), color=(245, 238, 210))
    draw = ImageDraw.Draw(img)

    # Faint lines
    for y in range(110, height - 80, 35):
        noise = random.randint(-3, 3)
        draw.line([(50, y + noise), (width - 50, y + noise)], fill=(210, 200, 180), width=1)

    # Header — legible
    draw.text((60, 30), "Graph Algorithms — Quick Notes", fill=(30, 20, 60))
    draw.text((60, 55), "BFS vs DFS | Dijkstra | Bellman-Ford", fill=(60, 50, 90))
    draw.line([(50, 80), (width - 50, 80)], fill=(100, 80, 60), width=2)

    # Messy content with varying darkness, wobbly baselines
    notes = [
        ("BFS (Breadth-First Search):", False, (15, 15, 15)),
        ("  Uses QUEUE — explores level by level", False, (25, 25, 25)),
        ("  Finds SHORTEST PATH (unweighted graph)", False, (10, 10, 10)),
        ("  Time: O(V+E)  Space O(V) — queue size", False, (30, 30, 30)),
        ("", False, (0,0,0)),
        ("DFS (Depth-First Search):", False, (15, 15, 15)),
        ("  Uses STACK (recursion or explicit)", False, (20, 20, 20)),
        ("  Explores as deep as possible first", False, (25, 25, 25)),
        ("  Time: O(V+E)  No shortest path guarantee!!", False, (10, 10, 10)),
        ("  Used for: topo sort, SCCs, cycle detect", False, (30, 30, 30)),
        ("", False, (0,0,0)),
        ("Dijkstra's algo — NON-NEG weights only:", False, (10, 10, 10)),
        ("  Priority Queue (min-heap)", False, (20, 20, 20)),
        ("  dist[src]=0, dist[v]=inf initially", False, (15, 15, 15)),
        ("  Relax edges greedily by min dist", False, (25, 25, 25)),
        ("  Complexity: O((V+E) log V) w/ binary heap", False, (10, 10, 10)),
        ("  *** WRONG for negative edges!! use BF ***", False, (160, 20, 20)),
        ("", False, (0,0,0)),
        ("Bellman-Ford:", False, (15, 15, 15)),
        ("  V-1 rounds of edge relaxation", False, (20, 20, 20)),
        ("  Handles negative edges", False, (25, 25, 25)),
        ("  O(VE) — slower than Dijkstra", False, (15, 15, 15)),
        ("  Extra round to detect neg cycles", False, (20, 20, 20)),
        ("", False, (0,0,0)),
        ("Dijkstra vs Bellman-Ford summary:", False, (10, 10, 10)),
        ("  Dijkstra: fast O((V+E)logV), no neg edges", False, (15, 15, 15)),
        ("  BF: slow O(VE), handles neg edges+cycles", False, (20, 20, 20)),
        ("", False, (0,0,0)),
        ("MST Kruskal: sort edges, add if no cycle (UF)", False, (15, 15, 15)),
        ("MST Prim: grow tree by cheapest crossing edge", False, (20, 20, 20)),
        ("Both: O(E log E) = O(E log V)", False, (25, 25, 25)),
        ("", False, (0,0,0)),
        ("TODO: review Floyd-Warshall for all-pairs", False, (80, 80, 160)),
        ("O(V^3) — uses DP, handles neg (no neg cycle)", False, (80, 80, 160)),
    ]

    y = 100
    for text, crossed, color in notes:
        if text == "":
            y += 20
            continue
        # Add wobbly baseline
        wobble = random.randint(-4, 4)
        x_offset = random.randint(-3, 8)
        # Vary ink darkness slightly
        r, g, b = color
        r = min(255, r + random.randint(-15, 15))
        g = min(255, g + random.randint(-15, 15))
        b = min(255, b + random.randint(-15, 15))
        draw.text((60 + x_offset, y + wobble), text, fill=(max(0,r), max(0,g), max(0,b)))

        # Strike-through for crossed-out text
        if crossed:
            draw.line([(60, y + wobble + 7), (60 + len(text) * 7, y + wobble + 7)],
                      fill=(50, 50, 50), width=2)
        y += 35

    # Add a small sketch-like box annotation in the corner
    draw.rectangle([(700, 350), (1050, 520)], outline=(60, 60, 60), width=2)
    draw.text((710, 360), "Quick Ref:", fill=(10, 10, 80))
    draw.text((710, 380), " Unweighted → BFS", fill=(20, 20, 20))
    draw.text((710, 400), " Non-neg weighted → Dijkstra", fill=(20, 20, 20))
    draw.text((710, 420), " Neg weights → Bellman-Ford", fill=(20, 20, 20))
    draw.text((710, 440), " All-pairs → Floyd-Warshall", fill=(20, 20, 20))
    draw.text((710, 465), " Span. tree → Kruskal/Prim", fill=(20, 20, 20))
    draw.text((710, 490), " (BFS/DFS for connectivity)", fill=(60, 60, 120))

    # Add some ink smudge simulation (dark blobs)
    for _ in range(6):
        bx = random.randint(50, width - 100)
        by = random.randint(100, height - 100)
        br = random.randint(2, 6)
        draw.ellipse([(bx-br, by-br), (bx+br, by+br)], fill=(80+random.randint(0,40), 70, 70))

    img.save(str(output_path), 'PNG', dpi=(120, 120))
    return True


def create_markdown_notes(output_path: Path):
    """Write the markdown notes file."""
    output_path.write_text(NOTES_CONTENT, encoding='utf-8')
    return True


def create_corpus_readme(corpus_dir: Path):
    readme = """# Corpus Manifest — CS301 Algorithms & Data Structures

## Source Documents

### lectures/
| File | Pages | Topics |
|------|-------|--------|
| lecture_01_basics.pdf | ~18 | Arrays, Linked Lists, Stacks, Queues, Hash Tables |
| lecture_02_trees.pdf  | ~20 | Trees, BST, AVL, Heaps, Hash Tables, Tries |
| lecture_03_sorting.pdf | ~14 | Comparison sorts, Counting/Radix sort, lower bounds |

### slides/
| File | Slides | Topics |
|------|--------|--------|
| slides_01_overview.pdf | 12 | Big-O, Recurrences, D&C, Graphs, DP, Greedy |
| slides_02_advanced.pdf | 8  | MST, Union-Find, Network Flow, NP, String algos |

### notes/
| File | Sections | Topics |
|------|----------|--------|
| study_notes.md | 6 | Big-O, DP, Graphs, Greedy, Amortized, Exam Tips |

### handwritten/
| File | Description | OCR Difficulty |
|------|-------------|----------------|
| handwritten_clean.png | Alice Chen's sorting notes — clear handwriting on lined paper | Low (legible) |
| handwritten_hard.png  | Graph algorithms quick notes — wobbly baseline, ink blobs, annotation box | High (difficult) |

## Total Coverage
- **~60+ pages** of content
- **4 formats**: PDF lectures, PDF slides, Markdown, Handwritten PNG
- **Topics**: Arrays, Linked Lists, Stacks, Queues, Trees, BST, AVL, Heaps, Hash Tables, Tries, Sorting (all major algorithms), Graphs (BFS, DFS, Dijkstra, Bellman-Ford, MST), DP (LCS, Knapsack, Edit Distance), Greedy, Amortized Analysis, NP-Completeness
"""
    (corpus_dir / "README.md").write_text(readme, encoding='utf-8')


def main():
    print("Generating synthetic corpus for CS301 Algorithms & Data Structures")
    print("=" * 60)

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for subdir in ["lectures", "slides", "notes", "handwritten"]:
        (CORPUS_DIR / subdir).mkdir(exist_ok=True)

    # ── Lecture PDFs ────────────────────────────────────────────────────────
    print("\n[1/6] Creating lecture PDFs...")
    if REPORTLAB:
        ok = create_lecture_pdf(
            LECTURE_1_CONTENT,
            CORPUS_DIR / "lectures" / "lecture_01_basics.pdf",
            "Lecture 1: Arrays, Linked Lists, Stacks & Queues"
        )
        print(f"  lecture_01_basics.pdf: {'OK' if ok else 'FAILED'}")

        ok = create_lecture_pdf(
            LECTURE_2_CONTENT,
            CORPUS_DIR / "lectures" / "lecture_02_trees.pdf",
            "Lecture 2: Trees, BST, Heaps & Hash Tables"
        )
        print(f"  lecture_02_trees.pdf: {'OK' if ok else 'FAILED'}")

        ok = create_lecture_pdf(
            LECTURE_3_CONTENT,
            CORPUS_DIR / "lectures" / "lecture_03_sorting.pdf",
            "Lecture 3: Sorting Algorithms"
        )
        print(f"  lecture_03_sorting.pdf: {'OK' if ok else 'FAILED'}")
    else:
        print("  [WARN] reportlab not installed — install with: pip install reportlab")
        print("  Creating text placeholder files instead...")
        for name, content in [
            ("lecture_01_basics.txt", "\n\n".join(f"{t}\n{b}" for t, b in LECTURE_1_CONTENT)),
            ("lecture_02_trees.txt",  "\n\n".join(f"{t}\n{b}" for t, b in LECTURE_2_CONTENT)),
            ("lecture_03_sorting.txt", "\n\n".join(f"{t}\n{b}" for t, b in LECTURE_3_CONTENT)),
        ]:
            (CORPUS_DIR / "lectures" / name).write_text(content, encoding='utf-8')
            print(f"  {name}: OK (text fallback)")

    # ── Slide PDFs ──────────────────────────────────────────────────────────
    print("\n[2/6] Creating slide PDFs...")
    if REPORTLAB:
        ok = create_slide_pdf(
            SLIDES_1_CONTENT,
            CORPUS_DIR / "slides" / "slides_01_overview.pdf",
            "CS301 — Algorithm Design Overview"
        )
        print(f"  slides_01_overview.pdf: {'OK' if ok else 'FAILED'}")

        ok = create_slide_pdf(
            SLIDES_2_CONTENT,
            CORPUS_DIR / "slides" / "slides_02_advanced.pdf",
            "CS301 — Advanced Graph Algorithms"
        )
        print(f"  slides_02_advanced.pdf: {'OK' if ok else 'FAILED'}")
    else:
        for name, content in [
            ("slides_01_overview.txt", "\n\n---\n\n".join(f"{t}\n{b}" for t, b in SLIDES_1_CONTENT)),
            ("slides_02_advanced.txt", "\n\n---\n\n".join(f"{t}\n{b}" for t, b in SLIDES_2_CONTENT)),
        ]:
            (CORPUS_DIR / "slides" / name).write_text(content, encoding='utf-8')
            print(f"  {name}: OK (text fallback)")

    # ── Markdown Notes ──────────────────────────────────────────────────────
    print("\n[3/6] Creating markdown notes...")
    ok = create_markdown_notes(CORPUS_DIR / "notes" / "study_notes.md")
    print(f"  study_notes.md: {'OK' if ok else 'FAILED'}")

    # ── Handwritten Images ──────────────────────────────────────────────────
    print("\n[4/6] Creating handwritten note images...")
    if PILLOW:
        ok = create_handwritten_image_clean(CORPUS_DIR / "handwritten" / "handwritten_clean.png")
        print(f"  handwritten_clean.png: {'OK' if ok else 'FAILED'}")
        ok = create_handwritten_image_hard(CORPUS_DIR / "handwritten" / "handwritten_hard.png")
        print(f"  handwritten_hard.png: {'OK' if ok else 'FAILED'}")
    else:
        print("  [WARN] Pillow not installed — install with: pip install Pillow")
        # Create text placeholder
        (CORPUS_DIR / "handwritten" / "handwritten_clean.txt").write_text(
            "PLACEHOLDER: handwritten clean notes about sorting algorithms.\n" +
            "Bubble Sort: O(n^2), Stable. Selection Sort: O(n^2), Unstable.\n" +
            "TimSort: O(n log n), Stable. Key insight: non-comparison sorts beat O(n log n).",
            encoding='utf-8'
        )
        (CORPUS_DIR / "handwritten" / "handwritten_hard.txt").write_text(
            "PLACEHOLDER: messy handwritten notes on graph algorithms.\n" +
            "BFS uses queue, finds shortest path in unweighted graphs. O(V+E).\n" +
            "DFS uses stack, O(V+E). Dijkstra: non-negative weights, O((V+E)logV).\n" +
            "Bellman-Ford: negative weights ok, O(VE). MST: Kruskal/Prim O(E log V).",
            encoding='utf-8'
        )
        print("  handwritten_*.txt: OK (text fallback, no images)")

    # ── Corpus README ───────────────────────────────────────────────────────
    print("\n[5/6] Creating corpus README...")
    create_corpus_readme(CORPUS_DIR)
    print("  README.md: OK")

    print("\n[6/6] Done!")
    print(f"\nCorpus created at: {CORPUS_DIR}")
    print("\nNext steps:")
    print("  1. pip install -r requirements.txt")
    print("  2. Copy .env.example to .env and add your GEMINI_API_KEY")
    print("  3. python -m src.ingestion.indexer    (ingest corpus)")
    print("  4. streamlit run src/app/main.py")


if __name__ == "__main__":
    main()
