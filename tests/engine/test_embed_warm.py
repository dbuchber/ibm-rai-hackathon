import threading
import time
from pathlib import Path

import numpy as np

from contracts.rdf_store import RdfGraphStore
from engine import embed

FIX = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


class FakeModel:
    """Counts what gets embedded; slow enough that parallel callers overlap."""
    def __init__(self):
        self.seen: list[str] = []

    def embed(self, texts):
        time.sleep(0.05)
        for t in texts:
            self.seen.append(t)
            yield np.ones(4, dtype=np.float32)


def _fake(monkeypatch):
    m = FakeModel()
    monkeypatch.setattr(embed, "_load", lambda: m)
    monkeypatch.setattr(embed, "_CACHE", {})
    return m


def test_parallel_callers_embed_each_text_once(monkeypatch):
    m = _fake(monkeypatch)
    texts = [f"t{i}" for i in range(20)]
    threads = [threading.Thread(target=embed.embed, args=(texts,)) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(m.seen) == sorted(texts)


def test_warm_embeds_seed_and_baseline_texts(monkeypatch):
    from engine import seeds

    m = _fake(monkeypatch)
    store = RdfGraphStore(FIX / "mini_graph.trig")
    embed.warm(store)
    nodes = store.export({"approved"}).nodes
    want = {seeds._node_text(n) for n in nodes if n.cls not in seeds.SEED_CLASSES_EXCLUDED}
    want |= {n.text for n in nodes if n.cls == "Chunk" and n.text}
    assert want and want <= set(m.seen)
    m.seen.clear()
    embed.warm(store)   # second call: everything cached
    assert m.seen == []
