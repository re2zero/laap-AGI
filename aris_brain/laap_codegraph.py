"""LAAP CodeGraph — 代码知识图谱"""
import logging, time, json
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("laap_codegraph")

class LAAPCodeGraph:
    def __init__(self, state_dir: Optional[str] = None):
        self._entities: Dict[str, dict] = {}
        self._relations: List[dict] = []
        self._built = False
        logger.info("[CodeGraph] initialized (lightweight mode)")

    def add_entity(self, name: str, etype: str = "module", meta: dict = None):
        self._entities[name] = {"type": etype, "meta": meta or {}, "added": time.time()}
        self._built = True

    def add_relation(self, src: str, dst: str, rtype: str = "imports"):
        self._relations.append({"src": src, "dst": dst, "type": rtype, "time": time.time()})

    def query(self, entity: str) -> dict:
        return self._entities.get(entity, {})

    def get_stats(self) -> dict:
        return {"entities": len(self._entities), "relations": len(self._relations), "built": self._built}

    def __len__(self): return len(self._entities)

def get_codegraph() -> LAAPCodeGraph:
    cg = LAAPCodeGraph()
    cg.add_entity("laap", "project")
    return cg
