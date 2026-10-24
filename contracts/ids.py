"""The only place IRIs and edge IDs are made. Citations join on these, never on text."""

from __future__ import annotations

import hashlib

KG = "https://rai-hackathon.bbger.at/kg/"
ONT = "https://rai-hackathon.bbger.at/ont#"

GRAPH_IRIS = {
    "approved": "urn:g:approved",
    "proposed": "urn:g:proposed",
    "rejected": "urn:g:rejected",
}


def node_iri(cls: str, local_id: str) -> str:
    """`node_iri("Station", "ST02_SEALING")` -> `.../kg/station/ST02_SEALING`."""
    return f"{KG}{cls.lower()}/{local_id}"


def pred_iri(name: str) -> str:
    return f"{ONT}{name}"


def local_name(iri: str) -> str:
    """Display name of a class/predicate/node IRI: the part after the last `#` or `/`."""
    return iri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def edge_id(s: str, p: str, o: str) -> str:
    return hashlib.sha1(f"{s}|{p}|{o}".encode()).hexdigest()[:12]
