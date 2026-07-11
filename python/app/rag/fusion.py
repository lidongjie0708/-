from __future__ import annotations


def reciprocal_rank_fusion(result_sets: list[list[dict]], k: int = 60) -> list[dict]:
    fused: dict[str, dict] = {}
    for result_set in result_sets:
        for rank, doc in enumerate(result_set, start=1):
            doc_id = doc["id"]
            if doc_id not in fused:
                fused[doc_id] = {**doc, "rrfScore": 0.0, "sources": []}
            fused[doc_id]["rrfScore"] += 1.0 / (k + rank)
            fused[doc_id]["sources"].append(doc.get("source", "unknown"))
    results = list(fused.values())
    for doc in results:
        doc["score"] = round(doc["rrfScore"], 6)
        doc["source"] = "+".join(sorted(set(doc.get("sources", []))))
    return sorted(results, key=lambda row: row["rrfScore"], reverse=True)
