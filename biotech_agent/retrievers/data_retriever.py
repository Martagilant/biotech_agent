"""
Data retrieval module: PubMed, ClinicalTrials.gov, Semantic Scholar, FDA, bioRxiv
All sources queried in parallel with credibility tiering.
"""
import asyncio
import aiohttp
import requests
import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CREDIBILITY_TIERS = {
    "pubmed": 1,
    "clinicaltrials": 1,
    "fda": 1,
    "semantic_scholar": 1,
    "biorxiv": 2,
    "tavily": 3,
}

RECENCY_CUTOFF_MONTHS = 24


@dataclass
class Document:
    source: str
    title: str
    abstract: str
    authors: list = field(default_factory=list)
    date: str = ""
    url: str = ""
    doc_id: str = ""
    credibility_tier: int = 2
    recency_boost: float = 1.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "source": self.source,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "date": self.date,
            "url": self.url,
            "doc_id": self.doc_id,
            "credibility_tier": self.credibility_tier,
            "recency_boost": self.recency_boost,
            "metadata": self.metadata,
        }


def _compute_recency_boost(date_str: str) -> float:
    """1.5x boost for docs within 24 months."""
    if not date_str:
        return 1.0
    for fmt in ["%Y-%m-%d", "%Y-%m", "%Y"]:
        try:
            dt = datetime.strptime(date_str[:len(fmt)], fmt)
            cutoff = datetime.now() - timedelta(days=RECENCY_CUTOFF_MONTHS * 30)
            return 1.5 if dt >= cutoff else 1.0
        except ValueError:
            continue
    return 1.0


async def fetch_pubmed(session: aiohttp.ClientSession, terms: list[str], max_results: int = 30) -> list[Document]:
    """Fetch from PubMed E-utilities."""
    query = " OR ".join(f'"{t}"[Title/Abstract]' for t in terms[:5])
    docs = []
    try:
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed", "term": query, "retmax": max_results,
            "sort": "date", "retmode": "json", "usehistory": "y"
        }
        async with session.get(search_url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                return docs
            data = await r.json()
        ids = data.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return docs

        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed", "id": ",".join(ids),
            "rettype": "abstract", "retmode": "xml"
        }
        async with session.get(fetch_url, params=fetch_params, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200:
                return docs
            xml_text = await r.text()

        # Parse XML minimally
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            try:
                pmid_el = article.find(".//PMID")
                pmid = pmid_el.text if pmid_el is not None else ""
                title_el = article.find(".//ArticleTitle")
                title = title_el.text or "" if title_el is not None else ""
                abstract_texts = article.findall(".//AbstractText")
                abstract = " ".join((el.text or "") for el in abstract_texts)
                year_el = article.find(".//PubDate/Year")
                month_el = article.find(".//PubDate/Month")
                year = year_el.text if year_el is not None else ""
                month = month_el.text if month_el is not None else "01"
                # Normalize month
                months = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
                          "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
                month_num = months.get(month, month.zfill(2) if month.isdigit() else "01")
                date_str = f"{year}-{month_num}" if year else ""
                authors = [
                    f"{a.findtext('LastName', '')} {a.findtext('Initials', '')}".strip()
                    for a in article.findall(".//Author")
                ]
                docs.append(Document(
                    source="pubmed",
                    title=title.strip(),
                    abstract=abstract[:2000],
                    authors=authors[:5],
                    date=date_str,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    doc_id=f"pmid_{pmid}",
                    credibility_tier=1,
                    recency_boost=_compute_recency_boost(date_str),
                ))
            except Exception as e:
                logger.debug(f"PubMed parse error: {e}")
                continue
    except Exception as e:
        logger.warning(f"PubMed fetch error: {e}")
    return docs


async def fetch_clinical_trials(session: aiohttp.ClientSession, terms: list[str], max_results: int = 40) -> list[Document]:
    """Fetch from ClinicalTrials.gov API v2."""
    docs = []
    query = " OR ".join(terms[:4])
    try:
        url = "https://clinicaltrials.gov/api/v2/studies"
        params = {
            "query.cond": query,
            "pageSize": max_results,
            "format": "json",
            "fields": "NCTId,BriefTitle,OverallStatus,Phase,EnrollmentCount,StartDate,CompletionDate,BriefSummary,InterventionName,PrimaryOutcomeMeasure,Condition,StudyType,LeadSponsorName"
        }
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                logger.warning(f"ClinicalTrials.gov returned {r.status}")
                return docs
            data = await r.json()

        studies = data.get("studies", [])
        for study in studies:
            ps = study.get("protocolSection", {})
            id_mod = ps.get("identificationModule", {})
            status_mod = ps.get("statusModule", {})
            design_mod = ps.get("designModule", {})
            desc_mod = ps.get("descriptionModule", {})
            intervention_mod = ps.get("armsInterventionsModule", {})
            outcomes_mod = ps.get("outcomesModule", {})
            sponsor_mod = ps.get("sponsorCollaboratorsModule", {})
            conditions_mod = ps.get("conditionsModule", {})

            nct_id = id_mod.get("nctId", "")
            title = id_mod.get("briefTitle", "")
            status = status_mod.get("overallStatus", "")
            phases = design_mod.get("phases", [])
            phase = ", ".join(phases) if phases else "N/A"
            enrollment = design_mod.get("enrollmentInfo", {}).get("count", "N/A")
            start_date = status_mod.get("startDateStruct", {}).get("date", "")
            completion_date = status_mod.get("completionDateStruct", {}).get("date", "")
            summary = desc_mod.get("briefSummary", "")
            interventions = [i.get("name", "") for i in intervention_mod.get("interventions", [])]
            primary_outcomes = [o.get("measure", "") for o in outcomes_mod.get("primaryOutcomes", [])]
            sponsor = sponsor_mod.get("leadSponsor", {}).get("name", "")
            conditions = conditions_mod.get("conditions", [])

            abstract = (
                f"Status: {status}. Phase: {phase}. Enrollment: {enrollment}. "
                f"Sponsor: {sponsor}. Conditions: {', '.join(conditions[:3])}. "
                f"Interventions: {', '.join(interventions[:3])}. "
                f"Primary outcomes: {', '.join(primary_outcomes[:2])}. "
                f"Start: {start_date}. Completion: {completion_date}. "
                f"Summary: {summary[:800]}"
            )

            docs.append(Document(
                source="clinicaltrials",
                title=title,
                abstract=abstract,
                date=start_date,
                url=f"https://clinicaltrials.gov/study/{nct_id}",
                doc_id=f"nct_{nct_id}",
                credibility_tier=1,
                recency_boost=_compute_recency_boost(start_date),
                metadata={
                    "nct_id": nct_id,
                    "phase": phase,
                    "status": status,
                    "enrollment": enrollment,
                    "sponsor": sponsor,
                    "conditions": conditions,
                    "interventions": interventions,
                    "primary_outcomes": primary_outcomes,
                    "start_date": start_date,
                    "completion_date": completion_date,
                }
            ))
    except Exception as e:
        logger.warning(f"ClinicalTrials fetch error: {e}")
    return docs


async def fetch_semantic_scholar(session: aiohttp.ClientSession, terms: list[str], max_results: int = 20) -> list[Document]:
    """Fetch from Semantic Scholar."""
    docs = []
    query = " ".join(terms[:3])
    try:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query, "limit": max_results,
            "fields": "paperId,title,abstract,authors,year,citationCount,externalIds,publicationDate"
        }
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status != 200:
                return docs
            data = await r.json()

        for paper in data.get("data", []):
            pub_date = paper.get("publicationDate") or (str(paper.get("year", "")) if paper.get("year") else "")
            doi = paper.get("externalIds", {}).get("DOI", "")
            paper_id = paper.get("paperId", "")
            docs.append(Document(
                source="semantic_scholar",
                title=paper.get("title", ""),
                abstract=(paper.get("abstract") or "")[:2000],
                authors=[a.get("name", "") for a in paper.get("authors", [])[:5]],
                date=pub_date,
                url=f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else "",
                doc_id=f"ss_{paper_id}",
                credibility_tier=1,
                recency_boost=_compute_recency_boost(pub_date),
                metadata={"citation_count": paper.get("citationCount", 0), "doi": doi}
            ))
    except Exception as e:
        logger.warning(f"Semantic Scholar fetch error: {e}")
    return docs


async def fetch_fda(session: aiohttp.ClientSession, terms: list[str]) -> list[Document]:
    """Fetch from OpenFDA drug approvals."""
    docs = []
    query_term = terms[0] if terms else ""
    try:
        url = "https://api.fda.gov/drug/label.json"
        params = {
            "search": f'indications_and_usage:"{query_term}"',
            "limit": 15
        }
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status != 200:
                return docs
            data = await r.json()

        for result in data.get("results", []):
            openfda = result.get("openfda", {})
            brand_names = openfda.get("brand_name", ["Unknown"])
            generic_names = openfda.get("generic_name", [])
            manufacturer = openfda.get("manufacturer_name", ["Unknown"])
            indications = " ".join(result.get("indications_and_usage", []))[:1500]
            warnings = " ".join(result.get("warnings", []))[:500]

            title = f"{brand_names[0] if brand_names else 'Drug'} ({generic_names[0] if generic_names else 'N/A'}) - FDA Approved"
            abstract = (
                f"Manufacturer: {manufacturer[0] if manufacturer else 'N/A'}. "
                f"Indications: {indications}. "
                f"Warnings summary: {warnings}"
            )
            docs.append(Document(
                source="fda",
                title=title,
                abstract=abstract[:2000],
                date="",
                url="https://labels.fda.gov",
                doc_id=f"fda_{hashlib.md5(title.encode()).hexdigest()[:8]}",
                credibility_tier=1,
                recency_boost=1.0,
                metadata={
                    "brand_names": brand_names,
                    "generic_names": generic_names,
                    "manufacturer": manufacturer,
                    "approval_type": "FDA approved",
                }
            ))
    except Exception as e:
        logger.warning(f"FDA fetch error: {e}")
    return docs


async def fetch_biorxiv(session: aiohttp.ClientSession, terms: list[str], max_results: int = 10) -> list[Document]:
    """Fetch from bioRxiv preprint server."""
    docs = []
    query = "+".join(terms[:3])
    try:
        # bioRxiv search via their API
        url = f"https://api.biorxiv.org/details/biorxiv/2024-01-01/2026-12-31/0/json"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status != 200:
                return docs
            data = await r.json()

        collection = data.get("collection", [])
        # Filter by title/abstract relevance to terms
        term_lower = [t.lower() for t in terms[:3]]
        for paper in collection[:50]:
            title_lower = paper.get("title", "").lower()
            abstract_lower = paper.get("abstract", "").lower()
            if any(t in title_lower or t in abstract_lower for t in term_lower):
                date_str = paper.get("date", "")
                docs.append(Document(
                    source="biorxiv",
                    title=paper.get("title", ""),
                    abstract=(paper.get("abstract", ""))[:2000],
                    authors=paper.get("authors", "").split("; ")[:5],
                    date=date_str,
                    url=f"https://www.biorxiv.org/content/{paper.get('doi', '')}",
                    doc_id=f"biorxiv_{hashlib.md5(paper.get('doi','').encode()).hexdigest()[:8]}",
                    credibility_tier=2,
                    recency_boost=_compute_recency_boost(date_str),
                    metadata={"doi": paper.get("doi", ""), "preprint": True}
                ))
                if len(docs) >= max_results:
                    break
    except Exception as e:
        logger.warning(f"bioRxiv fetch error: {e}")
    return docs


def deduplicate(docs: list[Document]) -> list[Document]:
    """Remove duplicates by doc_id and similar titles."""
    seen_ids = set()
    seen_titles = set()
    unique = []
    for doc in docs:
        title_key = doc.title.lower()[:60]
        if doc.doc_id not in seen_ids and title_key not in seen_titles:
            seen_ids.add(doc.doc_id)
            if title_key:
                seen_titles.add(title_key)
            unique.append(doc)
    return unique


def rank_documents(docs: list[Document]) -> list[Document]:
    """Rank by credibility tier and recency boost."""
    def score(doc):
        tier_score = {1: 3, 2: 2, 3: 1}.get(doc.credibility_tier, 1)
        return tier_score * doc.recency_boost
    return sorted(docs, key=score, reverse=True)


async def retrieve_all(query_terms: list[str]) -> dict:
    """Main entry point: parallel retrieval from all sources."""
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            fetch_pubmed(session, query_terms),
            fetch_clinical_trials(session, query_terms),
            fetch_semantic_scholar(session, query_terms),
            fetch_fda(session, query_terms),
            fetch_biorxiv(session, query_terms),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    pubmed_docs = results[0] if not isinstance(results[0], Exception) else []
    ct_docs = results[1] if not isinstance(results[1], Exception) else []
    ss_docs = results[2] if not isinstance(results[2], Exception) else []
    fda_docs = results[3] if not isinstance(results[3], Exception) else []
    biorxiv_docs = results[4] if not isinstance(results[4], Exception) else []

    # Log any exceptions
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning(f"Source {i} failed: {r}")

    all_docs = pubmed_docs + ct_docs + ss_docs + fda_docs + biorxiv_docs
    all_docs = deduplicate(all_docs)
    all_docs = rank_documents(all_docs)

    return {
        "all_documents": all_docs,
        "pubmed": pubmed_docs,
        "clinical_trials": ct_docs,
        "semantic_scholar": ss_docs,
        "fda": fda_docs,
        "biorxiv": biorxiv_docs,
        "total_count": len(all_docs),
        "stats": {
            "pubmed": len(pubmed_docs),
            "clinical_trials": len(ct_docs),
            "semantic_scholar": len(ss_docs),
            "fda": len(fda_docs),
            "biorxiv": len(biorxiv_docs),
        }
    }
