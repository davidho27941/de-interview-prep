# Pattern Reference

## Sliding Window

### When to Use
- Problem mentions **contiguous subarray / substring**
- Asks for longest / shortest / min / max of a subarray
- Has a window constraint (fixed length or condition-based)

### Shrink Conditions

| Problem Type | Shrink Condition | while/if | Reason |
|---|---|---|---|
| Min subarray sum >= target | `current_sum >= target` | `while` | Finding shortest → shrink aggressively |
| Longest no-repeat substring | `s[right] in seen` | `while` | Need to clean seen set until duplicate removed |
| Min window containing all chars | `have == need` | `while` | Finding shortest → shrink aggressively |
| Longest repeating char replacement | `window_size - max_freq > k` | `if` | Finding longest → slide, don't shrink |

### Key Rule
- **Finding shortest** → `while` (shrink as much as possible)
- **Finding longest** → `if` (slide the window, only shrink once)
- Always sync auxiliary state (set/dict) when removing elements during shrink

### Template
```python
left = 0
for right in range(len(s)):
    # expand: add s[right] to window state
    while/if SHRINK_CONDITION:
        # shrink: remove s[left] from window state
        left += 1
    # update answer
```

---

## Prefix Sum + HashMap

### When to Use
- Subarray sum equals K (especially with **negative numbers** — can't use sliding window)
- Count of subarrays with given property
- Pattern analogous to Two Sum: looking for a complement

### Key Rule
- Store `seen[prefix_sum] = count` (how many times this prefix sum appeared)
- Init `seen = {0: 1}` (empty prefix)
- At each step: check if `prefix_sum - k` exists in seen → add its count
- Update seen AFTER checking (to avoid using current element as both start and end)

### Template
```python
from collections import defaultdict

def subarray_sum(nums, k):
    seen = defaultdict(int)
    seen[0] = 1
    prefix = 0
    count = 0
    for num in nums:
        prefix += num
        count += seen[prefix - k]
        seen[prefix] += 1
    return count
```

### Why Not Sliding Window for Subarray Sum?
Sliding window assumes adding elements increases the sum and removing decreases it. With **negative numbers**, this assumption breaks — you can't decide when to shrink.

---

## Two Pointers

### When to Use
- Sorted array + pair/triplet finding
- Container / area problems
- Palindrome checking
- Merging sorted arrays

### Key Rule
- Both pointers moving → use `while` loop, not `for`
- Move the pointer that improves the answer

### Template (Sorted Two Sum)
```python
left, right = 0, len(nums) - 1
while left < right:
    total = nums[left] + nums[right]
    if total == target:
        return [left, right]
    elif total < target:
        left += 1
    else:
        right -= 1
```

---

## 3Sum (Three Sum)

### Dedup Strategy
Three levels of dedup — all required:

1. **Outer loop**: skip if `nums[i] == nums[i-1]` (skip duplicate first element)
2. **After finding a match**: advance left past duplicates with `while left < right and nums[left] == nums[left+1]: left += 1`
3. **After finding a match**: advance right past duplicates with `while left < right and nums[right] == nums[right-1]: right -= 1`
4. **After both while loops**: must still do `left += 1; right -= 1` to move past the last duplicate

### Common Mistake
Forgetting step 4 — the while loops stop AT the last duplicate, not past it.

---

## Binary Search

### Key Points
- `bisect_left`: first position where element could be inserted (leftmost match)
- `bisect_right`: position after the last match
- Boundary check: `left < len(nums)` (not `<=`)
- Only need to verify `nums[left] == target` (not right boundary)

### Template (Find First and Last Position)
```python
from bisect import bisect_left, bisect_right

def search_range(nums, target):
    left = bisect_left(nums, target)
    right = bisect_right(nums, target) - 1
    if left < len(nums) and nums[left] == target:
        return [left, right]
    return [-1, -1]
```

---

## SQL Pattern Signals

| Signal in Problem Statement | Pattern to Use |
|---|---|
| "each X with every Y, show 0 if none" | `CROSS JOIN` + `LEFT JOIN` |
| "latest/first record per group" | `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` + `WHERE rn = 1` |
| "running total / moving average" | `SUM/AVG OVER (ORDER BY ... ROWS BETWEEN ...)` |
| "consecutive rows / streaks" | Gap-and-Island: `id - ROW_NUMBER()` as group key |
| "ratio / percentage" | `AVG(CASE WHEN condition THEN 1 ELSE 0 END)` or `ROUND(COUNT(CASE...) / COUNT(*), 2)` |
| "find employees who..." (subject is the entity) | `JOIN` (inner — filter to matches) |
| "for each department, show..." (subject is the group) | `LEFT JOIN` (keep all groups, even empty) |
| "second highest / Nth value" | Subquery with `DENSE_RANK` or `LIMIT/OFFSET` |
| "swap adjacent rows" | Swap the ID, not the content: `CASE WHEN id % 2 = 1 AND id < max THEN id+1 WHEN id % 2 = 0 THEN id-1 ELSE id END` |
| "pivot / reshape rows to columns" | `SUM(IF(condition, value, NULL))` — use NULL not 0 to preserve missing data |

### JOIN Decision Rule
Read the problem statement subject:
- **"Find employees who have..."** → the query filters employees → `JOIN`
- **"For each department, list..."** → the query must show all departments → `LEFT JOIN`

### Window Function: RANK vs DENSE_RANK vs ROW_NUMBER
| Function | Ties | Gaps |
|---|---|---|
| `ROW_NUMBER()` | No ties (arbitrary order) | No gaps |
| `RANK()` | Same rank for ties | Gaps after ties (1,1,3) |
| `DENSE_RANK()` | Same rank for ties | No gaps (1,1,2) |

### Gap-and-Island
```sql
SELECT *, id - ROW_NUMBER() OVER (ORDER BY id) AS grp
FROM table
WHERE <filter first>  -- apply filter BEFORE computing groups
```
Important: WHERE filter must come before the ROW_NUMBER computation, or group boundaries shift.
