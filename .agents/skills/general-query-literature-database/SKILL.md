---
name: general-query-literature-database
description: Find relevant simulation workflows in the in-house literature database.
category: general
---

# Query Literature Databases

The in-house literature database consists of markdown (`.md`) files stored in the `.agents/workflows/` directory. Each file contains a workflow guide for a specific research topic, summarized from academic papers. 

To efficiently find the most relevant workflow guide without reading every file in full, you must rely on the short descriptions located in each file's YAML header. 

### Execution Instructions:

**Scan Database:** Because the database is currently small, use the following command to quickly extract all descriptions:

```bash
grep -rn "^description:" .agents/workflows/
```


<!-- Future work in plan: migrating the literature into a real database (e.g. ChromaDB), providing python scripts and tools to query it. NOT IMPLEMENTED YET. -->

