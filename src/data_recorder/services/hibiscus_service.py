import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from data_recorder.core.config import Settings, get_settings
from data_recorder.core.database import get_db_session
from data_recorder.models.hibiscus import HibiscusKonto, HibiscusUmsatz
from data_recorder.models.wertpapiere import (
    Etf,
    HibiscusImportLog,
    WknErtragDatum,
    WknInvestDatum,
)

logger = logging.getLogger(__name__)

# Regex patterns for WKN and ISIN detection
RE_WKN_EXPLICIT = re.compile(
    r"\b(?:WKN|W\.K\.N\.?)[:\s\-#]*([A-Z0-9]{6})\b",
    re.IGNORECASE,
)
RE_ISIN = re.compile(
    r"\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b",
    re.IGNORECASE,
)

# Categorization keywords
SPARPLAN_KEYWORDS = ["sparplan", "wertpapierkauf", "wertpapier-kauf", "kauf"]
DIVIDENDE_KEYWORDS = [
    "dividende",
    "ausschüttung",
    "ausschuettung",
    "ertrag",
    "kupon",
]


def extract_wkn_or_isin(
    text: str,
    known_wkns: dict[str, int] | None = None,
) -> tuple[str | None, bool]:
    """Extracts a 6-character WKN or 12-character ISIN from booking purpose text.

    Returns:
        tuple[str | None, bool]: (extracted_code, is_isin)
    """
    if not text or not text.strip():
        return None, False

    # 1. Check for explicit WKN prefix (e.g. "WKN: A1T8FV")
    wkn_matches = RE_WKN_EXPLICIT.findall(text)
    if wkn_matches:
        return wkn_matches[0].upper(), False

    # 2. Check for ISIN (e.g. "ISIN DE000A1T8FV4" or standalone ISIN)
    isin_matches = RE_ISIN.findall(text)
    if isin_matches:
        return isin_matches[0].upper(), True

    # 3. Fallback: Check 6-character tokens against known active ETFs
    if known_wkns:
        tokens = re.findall(r"\b[A-Z0-9]{6}\b", text.upper())
        for token in tokens:
            if token in known_wkns:
                return token, False

    return None, False


def categorize_transaction(
    text: str,
    betrag: Decimal,
) -> tuple[str | None, str | None]:
    """Categorizes a transaction based on keywords and amount sign.

    Returns:
        tuple[category, typ]:
        category: "SPARPLAN", "DIVIDENDE", or None
        typ: "SPARPLAN", "KAUF", "DIVIDENDE", "AUSSCHUETTUNG", "ERTRAG", or None
    """
    if not text:
        return None, None

    text_lower = text.lower()

    if betrag < Decimal("0"):
        # Sparplan or Purchase (Debit / negative amount)
        if any(kw in text_lower for kw in ["sparplan", "wertpapierkauf", "wertpapier-kauf"]):
            return "SPARPLAN", "SPARPLAN"
        elif "kauf" in text_lower:
            return "SPARPLAN", "KAUF"

    elif betrag > Decimal("0"):
        # Dividende or Distribution (Credit / positive amount)
        if "ausschüttung" in text_lower or "ausschuettung" in text_lower:
            return "DIVIDENDE", "AUSSCHUETTUNG"
        elif "ertrag" in text_lower:
            return "DIVIDENDE", "ERTRAG"
        elif any(kw in text_lower for kw in ["dividende", "kupon"]):
            return "DIVIDENDE", "DIVIDENDE"

    return None, None


@dataclass
class ScanResult:
    """Statistics and details of a Hibiscus scanning run."""

    scanned_count: int = 0
    imported_count: int = 0
    skipped_count: int = 0
    sparplaene_count: int = 0
    dividenden_count: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)


class HibiscusService:
    """Service to scan Hibiscus bank bookings and idempotently persist savings plans & dividends."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_known_etfs(self, session: Session) -> tuple[dict[str, Etf], dict[str, Etf]]:
        """Returns lookup maps for active ETFs by WKN and ISIN."""
        stmt = select(Etf).where(Etf.aktiv.is_(True))
        etfs = session.execute(stmt).scalars().all()

        wkn_map: dict[str, Etf] = {e.wkn.upper(): e for e in etfs if e.wkn}
        isin_map: dict[str, Etf] = {e.isin.upper(): e for e in etfs if e.isin}
        return wkn_map, isin_map

    def get_processed_umsatz_ids(self, session: Session) -> set[int]:
        """Returns the set of all previously imported Hibiscus booking IDs."""
        stmt = select(HibiscusImportLog.hibiscus_umsatz_id)
        return set(session.execute(stmt).scalars().all())

    def scan_and_import(
        self,
        session_wertpapiere: Session | None = None,
        session_hibiscus: Session | None = None,
        account_filters: list[str] | None = None,
    ) -> ScanResult:
        """Scans Hibiscus transactions and idempotently imports matching investment bookings."""
        if session_wertpapiere is not None and session_hibiscus is not None:
            return self._execute_scan(session_wertpapiere, session_hibiscus, account_filters)

        # Open sessions for wertpapiere and hibiscus
        for wp_session in get_db_session(self.settings.DB_NAME_WERTPAPIERE):
            for hib_session in get_db_session(self.settings.DB_NAME_HIBISCUS):
                return self._execute_scan(wp_session, hib_session, account_filters)

        return ScanResult()

    def _execute_scan(
        self,
        session_wertpapiere: Session,
        session_hibiscus: Session,
        account_filters: list[str] | None = None,
    ) -> ScanResult:
        """Executes the scanning and booking pipeline."""
        result = ScanResult()

        # Parse account filter list from arguments or config
        effective_filters: list[str] = []
        if account_filters is not None:
            effective_filters = [f.strip() for f in account_filters if f.strip()]
        elif self.settings.HIBISCUS_ACCOUNT_FILTERS:
            effective_filters = [
                f.strip() for f in self.settings.HIBISCUS_ACCOUNT_FILTERS.split(",") if f.strip()
            ]

        # Load known ETFs and previously imported transaction IDs
        wkn_map, isin_map = self.get_known_etfs(session_wertpapiere)
        known_wkns_lookup = {k: e.id for k, e in wkn_map.items()}
        processed_ids = self.get_processed_umsatz_ids(session_wertpapiere)

        # Query Hibiscus bookings
        stmt = select(HibiscusUmsatz).order_by(HibiscusUmsatz.datum.asc(), HibiscusUmsatz.id.asc())

        if effective_filters:
            stmt = stmt.join(HibiscusKonto, HibiscusUmsatz.konto_id == HibiscusKonto.id)
            stmt = stmt.where(
                or_(
                    HibiscusKonto.kontonummer.in_(effective_filters),
                    HibiscusKonto.iban.in_(effective_filters),
                    HibiscusKonto.bezeichnung.in_(effective_filters),
                )
            )

        umsatz_list = session_hibiscus.execute(stmt).scalars().all()
        result.scanned_count = len(umsatz_list)

        for umsatz in umsatz_list:
            if umsatz.id in processed_ids:
                result.skipped_count += 1
                continue

            full_text = " ".join(
                filter(
                    None,
                    [
                        umsatz.zweck,
                        umsatz.zweck2,
                        umsatz.zweck3,
                        umsatz.kommentar,
                        umsatz.empfaenger_name,
                    ],
                )
            )

            identifier, is_isin = extract_wkn_or_isin(full_text, known_wkns=known_wkns_lookup)
            if not identifier:
                continue

            # Match ETF
            etf: Etf | None = None
            if is_isin:
                etf = isin_map.get(identifier) or wkn_map.get(identifier)
            else:
                etf = wkn_map.get(identifier) or isin_map.get(identifier)

            if not etf:
                continue

            betrag_decimal = Decimal(str(umsatz.betrag))
            category, typ = categorize_transaction(full_text, betrag_decimal)
            if not category or not typ:
                continue

            booking_date = umsatz.valuta or umsatz.datum

            try:
                if category == "SPARPLAN":
                    invest_amount = abs(betrag_decimal)
                    existing_invest = session_wertpapiere.execute(
                        select(WknInvestDatum).where(
                            WknInvestDatum.wkn_id == etf.id,
                            WknInvestDatum.datum == booking_date,
                        )
                    ).scalar_one_or_none()

                    if existing_invest is None:
                        new_invest = WknInvestDatum(
                            wkn_id=etf.id,
                            datum=booking_date,
                            invest=invest_amount,
                        )
                        session_wertpapiere.add(new_invest)
                    else:
                        existing_invest.invest = invest_amount

                    result.sparplaene_count += 1

                elif category == "DIVIDENDE":
                    ertrag_amount = abs(betrag_decimal)
                    existing_ertrag = session_wertpapiere.execute(
                        select(WknErtragDatum).where(
                            WknErtragDatum.wkn_id == etf.id,
                            WknErtragDatum.datum == booking_date,
                            WknErtragDatum.typ == typ,
                        )
                    ).scalar_one_or_none()

                    if existing_ertrag is None:
                        new_ertrag = WknErtragDatum(
                            wkn_id=etf.id,
                            datum=booking_date,
                            betrag=ertrag_amount,
                            typ=typ,
                        )
                        session_wertpapiere.add(new_ertrag)
                    else:
                        existing_ertrag.betrag = ertrag_amount

                    result.dividenden_count += 1

                # Record in HibiscusImportLog for Idempotency tracking
                import_log = HibiscusImportLog(
                    hibiscus_umsatz_id=umsatz.id,
                    wkn_id=etf.id,
                    typ=typ,
                    datum=booking_date,
                    betrag=abs(betrag_decimal),
                    verwendungszweck=full_text[:1000],
                )
                session_wertpapiere.add(import_log)
                session_wertpapiere.commit()

                processed_ids.add(umsatz.id)
                result.imported_count += 1
                result.details.append(
                    {
                        "umsatz_id": umsatz.id,
                        "wkn": etf.wkn,
                        "isin": etf.isin,
                        "typ": typ,
                        "datum": booking_date.isoformat(),
                        "betrag": float(abs(betrag_decimal)),
                    }
                )

                logger.info(
                    "Hibiscus Buchung #%d erfolgreich importiert: %s für %s am %s (%.2f €)",
                    umsatz.id,
                    typ,
                    etf.wkn,
                    booking_date,
                    abs(betrag_decimal),
                )

            except Exception as exc:
                session_wertpapiere.rollback()
                logger.error(
                    "Fehler beim Importieren von Hibiscus Buchung #%d: %s",
                    umsatz.id,
                    exc,
                    exc_info=True,
                )

        return result
