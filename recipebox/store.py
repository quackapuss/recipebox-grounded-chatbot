"""SQLite storage, full-population filters, and exact analytical queries."""
import hashlib
import json
import re
import sqlite3
import statistics
from pathlib import Path
from .normalize import canonical, contains, steps, violations, VERSION

FILES = {"ar": "recipes_raw_nosource_ar.json", "epi": "recipes_raw_nosource_epi.json", "fn": "recipes_raw_nosource_fn.json"}
SCHEMA = """
CREATE TABLE recipe(id TEXT PRIMARY KEY, source TEXT, source_key TEXT, title TEXT,
 ingredients TEXT, instructions TEXT, raw_json TEXT, ingredient_count INTEGER,
 step_count INTEGER, valid INTEGER);
CREATE TABLE ingredient(recipe_id TEXT, position INTEGER, raw TEXT, name TEXT,
 PRIMARY KEY(recipe_id,position));
CREATE INDEX ingredient_name ON ingredient(name,recipe_id);
CREATE INDEX ingredient_recipe ON ingredient(recipe_id);
CREATE TABLE restriction(recipe_id TEXT,term TEXT, PRIMARY KEY(recipe_id,term));
CREATE INDEX restriction_term ON restriction(term,recipe_id);
CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED,title,ingredients,tokenize='porter unicode61');
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
"""


def build(raw_dir, db_path):
    """All three input files required. Build to a temporary path, then replace."""
    raw_dir, db_path = Path(raw_dir), Path(db_path)
    for filename in FILES.values():
        if not (raw_dir / filename).is_file():
            raise FileNotFoundError(f"All three files are required: missing {filename}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp = db_path.with_suffix(".building")
    temp.unlink(missing_ok=True)
    con = sqlite3.connect(temp)
    con.executescript(SCHEMA)
    report = {"normalization_version": VERSION, "sources": {}, "invalid_examples": [], "duplicate_content_records": 0}
    seen = set()
    try:
        for source, filename in FILES.items():
            payload = (raw_dir / filename).read_bytes()
            records = json.loads(payload)
            info = {"file": filename, "sha256": hashlib.sha256(payload).hexdigest(), "raw_records": len(records), "valid_records": 0, "invalid_records": 0}
            for key, raw in records.items():
                rid = source + ":" + key
                obj = raw if isinstance(raw, dict) else {}
                title = obj.get("title")
                title = title if isinstance(title, str) else ""
                ing = obj.get("ingredients")
                ing = ing if isinstance(ing, list) and all(isinstance(x, str) for x in ing) else []
                ins = obj.get("instructions")
                ins = ins if isinstance(ins, str) else ""
                normalized = [(i, line, canonical(line)) for i, line in enumerate(ing)]
                normalized = [x for x in normalized if x[2] and re.search(r"[a-z]", x[2])]
                valid = bool(title.strip() and normalized and ins.strip())
                info["valid_records" if valid else "invalid_records"] += 1
                if not valid and len(report["invalid_examples"]) < 12:
                    report["invalid_examples"].append(rid)
                content_hash = hashlib.sha256(json.dumps([title, ing, ins], ensure_ascii=False).encode()).hexdigest()
                if content_hash in seen:
                    report["duplicate_content_records"] += 1
                seen.add(content_hash)
                con.execute("INSERT INTO recipe VALUES(?,?,?,?,?,?,?,?,?,?)", (rid, source, key, title, json.dumps(ing, ensure_ascii=False), ins, json.dumps(raw, ensure_ascii=False), len(normalized), len(steps(ins)), int(valid)))
                con.executemany("INSERT INTO ingredient VALUES(?,?,?,?)", [(rid, *x) for x in normalized])
                con.executemany("INSERT INTO restriction VALUES(?,?)", [(rid, term) for term in ("dairy", "egg", "peanut") if violations(ing, [term])])
                if valid:
                    con.execute("INSERT INTO search(id,title,ingredients) VALUES(?,?,?)", (rid, title, " ".join(x[2] for x in normalized)))
            report["sources"][source] = info
            con.commit()
            print(f"Imported {source}: {info['raw_records']:,} raw / {info['valid_records']:,} searchable", flush=True)
        report["raw_records"] = sum(x["raw_records"] for x in report["sources"].values())
        report["valid_records"] = sum(x["valid_records"] for x in report["sources"].values())
        report["duplicate_policy"] = "Keep source records; no content deduplication. Counts are records, not unique dishes."
        con.execute("INSERT INTO metadata VALUES('manifest',?)", (json.dumps(report),))
        con.commit()
        con.close()
        temp.replace(db_path)
        return report
    except BaseException:
        con.close()
        temp.unlink(missing_ok=True)
        raise


class Store:
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Missing {path}. Run: python -m recipebox setup")
        self.db = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        self.db.create_function("ingredient_match", 2, lambda key, term: int(contains(key, term)), deterministic=True)
        self.db.create_function("forbidden", 2, lambda raw, exclusions: int(bool(violations(json.loads(raw), json.loads(exclusions)))), deterministic=True)

    def close(self):
        self.db.close()

    def manifest(self):
        return json.loads(self.db.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()[0])

    def recipe(self, rid):
        row = self.db.execute("SELECT * FROM recipe WHERE id=?", (rid,)).fetchone()
        if not row:
            raise ValueError(f"Unknown recipe ID: {rid}")
        obj = dict(row)
        obj["ingredients"] = json.loads(obj["ingredients"])
        obj["raw_record"] = json.loads(obj.pop("raw_json"))
        obj["normalized_ingredients"] = [dict(r) for r in self.db.execute("SELECT position,raw,name FROM ingredient WHERE recipe_id=? ORDER BY position", (rid,))]
        obj["steps"] = steps(obj["instructions"])
        return obj

    def predicate(self, filters):
        clauses, values = ["r.valid=1"], []
        if filters.get("query"):
            tokens = re.findall(r"[\w]+", filters["query"], flags=re.UNICODE)
            if tokens:
                # AND terms, title and ingredients only. No arbitrary FTS syntax.
                clauses.append("r.id IN (SELECT id FROM search WHERE search MATCH ?)")
                values.append(" AND ".join('"' + t + '"' for t in tokens))
        for term in filters.get("include", []):
            clauses.append("EXISTS(SELECT 1 FROM ingredient i WHERE i.recipe_id=r.id AND instr(' '||i.name||' ',' '||?||' ')>0)")
            values.append(canonical(term))
        if filters.get("exclude"):
            for term in filters["exclude"]:
                term = canonical(term)
                if term in {"dairy", "egg", "peanut"}:
                    clauses.append("NOT EXISTS(SELECT 1 FROM restriction x WHERE x.recipe_id=r.id AND x.term=?)")
                else:
                    clauses.append("NOT EXISTS(SELECT 1 FROM ingredient i WHERE i.recipe_id=r.id AND instr(' '||i.name||' ',' '||?||' ')>0)")
                values.append(term)
        if filters.get("max_steps") is not None:
            clauses.append("r.step_count<=?")
            values.append(filters["max_steps"])
        return " AND ".join(clauses), values

    def ids(self, filters, order="id", limit=None):
        where, values = self.predicate(filters)
        ordering = {"id": "r.id", "fewest_steps": "r.step_count,r.id", "most_steps": "r.step_count DESC,r.id"}[order]
        sql = f"SELECT r.id FROM recipe r WHERE {where} ORDER BY {ordering}"
        if limit is not None:
            sql += " LIMIT ?"
            values.append(limit)
        return [r[0] for r in self.db.execute(sql, values)]

    def search(self, filters, limit=5, order="relevance"):
        where, values = self.predicate(filters)
        total = self.db.execute(f"SELECT count(*) FROM recipe r WHERE {where}", values).fetchone()[0]
        if order == "relevance" and filters.get("query"):
            # BM25 is ranking only. It never limits the population for statistics.
            sql = f"SELECT r.id FROM recipe r JOIN search ON search.id=r.id WHERE {where} AND search MATCH ? ORDER BY bm25(search,0,5,1),r.id LIMIT ?"
            tokens = re.findall(r"[\w]+", filters["query"])
            ranked = [r[0] for r in self.db.execute(sql, values + [" AND ".join('"'+t+'"' for t in tokens), limit])]
        else:
            ranked = self.ids(filters, order if order != "relevance" else "id", limit)
        return total, [self.recipe(rid) for rid in ranked]

    def analytics(self, filters, metric="count", limit=5):
        where, values = self.predicate(filters)
        counts = [r[0] for r in self.db.execute(f"SELECT r.ingredient_count FROM recipe r WHERE {where}", values)]
        n = len(counts)
        denominator = self.db.execute("SELECT count(*) FROM recipe WHERE valid=1").fetchone()[0]
        result = {"metric": metric, "filters": filters.copy(), "recipes_analyzed": n, "denominator": denominator, "denominator_definition": "All searchable records from all three sources; source duplicates retained.", "percentage_of_dataset": 100*n/denominator if denominator else None, "step_rule": "Nonempty newline paragraphs; if one paragraph, sentence boundaries [.?!] followed by uppercase or digit.", "ingredient_rule": "Count nonempty normalized ingredient lines; repeated ingredient lines count separately. Ingredient family filters use whole-token phrases; forms such as garlic powder also match garlic."}
        if metric == "count":
            result.update(value=n, calculation="COUNT(all records satisfying the displayed filters); percentage = 100 * count / searchable records")
        elif metric in {"average", "median"}:
            result.update(value=(statistics.mean(counts) if metric == "average" else statistics.median(counts)) if n else None, calculation="sum(ingredient-line counts)/n" if metric == "average" else "sort ingredient-line counts; middle value or mean of two middle values")
        elif metric == "common":
            rows = self.db.execute(f"SELECT i.name,count(DISTINCT i.recipe_id) AS n FROM ingredient i WHERE i.recipe_id IN (SELECT r.id FROM recipe r WHERE {where}) GROUP BY i.name ORDER BY n DESC,i.name LIMIT ?", values+[limit]).fetchall()
            result.update(value=[{"ingredient": r[0], "recipe_count": r[1]} for r in rows], calculation="COUNT(DISTINCT recipe_id) per exact normalized product, over every filtered record; descending count then name")
        elif metric in {"fewest_steps", "most_steps"}:
            result.update(value=[{"id": rid, "title": (r:=self.recipe(rid))["title"], "step_count": r["step_count"]} for rid in self.ids(filters, metric, limit)], calculation=f"Sort all filtered records by step_count {'ascending' if metric=='fewest_steps' else 'descending'}, then stable ID; take {limit}")
        else:
            raise ValueError("Unknown metric")
        result["evidence_ids"] = self.ids(filters, limit=3)
        return result
