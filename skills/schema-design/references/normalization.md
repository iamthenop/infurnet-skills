# Database Normalization Reference: 0NF to 6NF

Database normalization is the formal process of structuring relational data to minimize redundancy, eliminate anomalous update/insertion/deletion behaviors, and guarantee data integrity. Higher normal forms address increasingly subtle forms of dependency.

---

## 1. The Normal Forms (0NF to 6NF)

### 0NF (Unnormalized Form)

* **Definition:** A relation that does not meet the basic criteria of a relational table. It may contain repeating groups, multi-valued attributes, nested relations, or lack a defined primary key.
* **Characteristics:** Cells contain multiple values (lists or sets), or tables contain embedded arrays/structures.
* **Anomaly Exposure:** Highly prone to all anomalies (insertion, update, deletion) and impossible to query effectively using standard relational algebra without flattening functions.

### 1NF (First Normal Form)

* **Definition:** A relation where every attribute domain is atomic (indivisible), and every cell contains a single scalar value. Furthermore, the relation must have a defined primary key, and the order of rows and columns must be semantically insignificant.
* **Characteristics:** Elimination of repeating groups; every intersection of a row and column contains exactly one value.
* **Anomaly Exposure:** Still vulnerable to functional dependencies between non-key attributes, leading to redundancy.

### 2NF (Second Normal Form)

* **Definition:** A relation that is in 1NF *and* every non-prime attribute is fully functionally dependent on the entire primary key.
* **Characteristics:** Eliminates partial functional dependencies. This applies exclusively to tables with composite primary keys (keys consisting of two or more columns). If a table has a single-column primary key, it is automatically in 2NF if it is in 1NF.
* **Anomaly Exposure:** Vulnerable to transitive dependencies (where a non-key attribute depends on another non-key attribute).

### 3NF (Third Normal Form)

* **Definition:** A relation that is in 2NF *and* every non-prime attribute is non-transitively dependent on the primary key. Formally, for every non-trivial functional dependency $X \to Y$, either:
1. $X$ is a superkey, or
2. $Y$ is a prime attribute (part of a candidate key).


* **Characteristics:** All attributes are dependent on the key, the whole key, and nothing but the key.
* **Anomaly Exposure:** Vulnerable to Boyce-Codd anomalies if a table contains multiple overlapping candidate keys that share attributes.

### BCNF (Boyce-Codd Normal Form / "3.5NF")

* **Definition:** A stronger version of 3NF. A relation is in BCNF if and only if, for every non-trivial functional dependency $X \to Y$, $X$ is a superkey.
* **Characteristics:** Removes every remaining anomaly caused by functional dependencies where a non-key attribute determines a key attribute. Every BCNF table is in 3NF, but not vice versa.
* **Anomaly Exposure:** Vulnerable to *multivalued dependencies* (MVDs) when independent many-to-one relationships share the same table scope.

### 4NF (Fourth Normal Form)

* **Definition:** A relation that is in BCNF *and* contains no non-trivial multivalued dependencies (MVDs). An MVD $X \to\to Y$ specifies that for a given value of $X$, a set of values for $Y$ is independent of a set of values for $Z$ (where $Y$ and $Z$ partition the remaining attributes).
* **Characteristics:** Eliminates independent multi-valued facts from being forced into the same relation, preventing combinatorial explosion and redundant row duplication.
* **Anomaly Exposure:** Vulnerable to *join dependencies* that cannot be decomposed into simpler binary projections without loss of semantic constraint.

### 5NF (Fifth Normal Form / Project-Join Normal Form - PJNF)

* **Definition:** A relation is in 5NF if and only if every non-trivial join dependency in the relation is implied by the candidate keys.
* **Characteristics:** Ensures that a table cannot be reconstructed by joining multiple smaller tables unless those tables are subsets of the original relation constrained by candidate keys. It prevents data loss or phantom row generation upon multi-way decomposition.
* **Anomaly Exposure:** Vulnerable to temporal or structural fragmentation where independent semantic attributes vary across separate orthogonal axes over time.

### 6NF (Sixth Normal Form)

* **Definition:** A relation is in 6NF if and only if it satisfies every trivial join dependency (i.e., it cannot be decomposed any further without losing temporal validity or collapsing into irreducibility).
* **Characteristics:** Decomposes every non-key attribute into its own binary temporal relation (Entity-Attribute-Value architecture applied at the schema level: `[Entity ID, Timestamp, Value]`). Typically used in temporal databases, columnar data warehousing, and extreme historical tracking systems.

---

## 2. Balancing Normalization Levels

Strict adherence to high normal forms (such as BCNF or 6NF) optimizes data integrity and write performance by eliminating duplication, but it introduces operational trade-offs:

* **Read Amplification (Join Cost):** Highly normalized schemas require extensive `JOIN` operations across numerous tables to reconstruct business entities, degrading read performance for transactional workloads (OLTP).
* **Denormalization for Performance:** In practice, systems often introduce controlled denormalization (such as precomputed rollups, materialized views, or redundant caching columns) to bypass expensive joins in hot query paths.
* **Analytic Workloads (OLAP):** Analytical databases favor star or snowflake schemas (typically bounded around 3NF) or column-oriented storage (akin to 6NF decomposition) to maximize scan efficiency over aggregations.

### Decision Matrix

| Normal Form Target | Primary Benefit | Primary Drawback | Optimal Use Case |
| --- | --- | --- | --- |
| **3NF / BCNF** | Standard balance of integrity and query simplicity | Potential redundancy with overlapping keys | Standard OLTP application databases |
| **4NF / 5NF** | Zero independent multi-valued duplication | Extreme join overhead | Complex multi-parent structural modeling |
| **6NF** | Ultimate temporal flexibility, minimal write conflicts | Massive join explosion, complex schema management | Temporal auditing, historical data stores, high-frequency telemetry |

---

## 3. Mechanisms for Constraining Membership

To enforce structural boundaries and relational integrity across these normal forms, databases utilize specific declarative and procedural constraints:

1. **Primary Key Constraints (`PRIMARY KEY`):** Guarantees entity integrity by enforcing uniqueness and non-nullability, establishing the foundational determinant ($X$) for all functional dependencies.
2. **Unique Constraints (`UNIQUE`):** Enforces candidate key membership, ensuring alternative access paths meet uniqueness requirements without serving as the primary cluster key.
3. **Foreign Key Constraints (`FOREIGN KEY ... REFERENCES`):** Enforces referential integrity between decomposed relations, maintaining valid links across normalized boundaries (critical for 2NF through 5NF decompositions).
4. **Check Constraints (`CHECK`):** Restricts domain membership and enforces intra-row business rules, preserving atomicity required for 1NF.
5. **Exclusion Constraints (`EXCLUDE`):** Generalizes unique constraints to support complex overlapping predicates (e.g., temporal or spatial ranges), assisting in higher-order structural integrity.
6. **Trigger-Based and Assertion Rules:** Procedural or declarative assertions used to enforce inter-table constraints and multivalued dependencies that standard SQL DDL cannot natively express without complex serialization logic.
