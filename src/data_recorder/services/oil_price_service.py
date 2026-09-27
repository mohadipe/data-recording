import asyncio
from dataclasses import dataclass
import datetime
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from bs4 import BeautifulSoup
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from data_recorder.core.config import Settings, get_settings
from data_recorder.core.database import get_db_session
from data_recorder.models.verbrauch import HeizoelPreis

logger = logging.getLogger(__name__)


@dataclass
class OilPriceResult:
    """Parsed heating oil quote for a specific date, postal code and amount."""

    datum: datetime.date
    plz: str
    menge_liter: int
    preis_pro_liter: Decimal


def _clean_decimal_str(val_str: str) -> str:
    """Normalizes German number formats (e.g. '165,62' or '2.462,50' or '0.985') to standard decimal string."""
    cleaned = val_str.strip().replace("\xa0", "").replace(" ", "")
    # Remove thousand separators
    if "." in cleaned and "," in cleaned:
        # e.g. '2.462,50'
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    return cleaned


class OilPriceService:
    """Service to fetch, parse and persist regional heating oil prices."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def fetch_oil_price_html(
        self,
        plz: str | None = None,
        menge_liter: int | None = None,
        url: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> str | None:
        """Fetches the HTML response for the given PLZ and amount from oil price provider."""
        target_plz = plz or self.settings.HEIZOEL_PLZ
        target_amount = menge_liter or self.settings.HEIZOEL_MENGE_LITER
        target_url = url or self.settings.HEIZOEL_PROVIDER_URL

        headers = {
            "User-Agent": self.settings.HEIZOEL_SCRAPER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        params = {"zipcode": str(target_plz), "amount": target_amount}
        timeout = httpx.Timeout(self.settings.HEIZOEL_SCRAPER_TIMEOUT, connect=5.0)

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=timeout, follow_redirects=True, headers=headers
                ) as client:
                    response = await client.get(target_url, params=params)
                    if response.is_error:
                        response.raise_for_status()
                    return response.text
            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                if attempt < max_retries:
                    logger.warning(
                        "Heizölpreis-Abfrage fehlgeschlagen (Versuch %d/%d): %s. Wiederhole in %.1fs...",
                        attempt,
                        max_retries,
                        exc,
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.warning(
                        "Heizölpreis-Anbieter nicht erreichbar nach %d Versuchen (%s): %s.",
                        max_retries,
                        target_url,
                        exc,
                    )
                    return None

        return None

    def parse_oil_price(
        self, html: str | None, menge_liter: int = 2500
    ) -> Decimal | None:
        """Resiliently parses the gross heating oil price per liter from HTML response.

        Applies multiple parsing strategies in order of reliability:
        1. SSR Nuxt 3 JSON state (__NUXT_DATA__)
        2. Direct DOM price elements (e.g. .price-text-large, 100 Liter breakdown)
        3. Table-based results and explicit unit labels (e.g. € / Liter)
        4. Generic regex fallback patterns
        """
        if not html or not isinstance(html, str) or not html.strip():
            return None

        # Strategy 1: Nuxt 3 State in <script> tags
        price = self._parse_nuxt_state(html, menge_liter=menge_liter)
        if price is not None:
            return price

        soup = BeautifulSoup(html, "html.parser")

        # Strategy 2: DOM-based extraction
        price = self._parse_dom_elements(soup, menge_liter=menge_liter)
        if price is not None:
            return price

        # Strategy 3: Table and Unit based extraction
        price = self._parse_table_and_units(soup, menge_liter=menge_liter)
        if price is not None:
            return price

        # Strategy 4: Regex Fallback
        price = self._parse_regex_fallback(html, menge_liter=menge_liter)
        if price is not None:
            return price

        return None

    def _parse_nuxt_state(self, html: str, menge_liter: int) -> Decimal | None:
        """Extracts pricing from Nuxt 3 SSR state payload."""
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            script_content = script.string or ""
            stripped = script_content.strip()
            if not (stripped.startswith("[") and stripped.endswith("]")):
                continue
            if "_100L" not in stripped and "brutto" not in stripped:
                continue

            try:
                data = json.loads(stripped)
                if not isinstance(data, list):
                    continue

                for item in data:
                    if isinstance(item, dict) and "_100L" in item:
                        l100_idx = item["_100L"]
                        if isinstance(l100_idx, int) and 0 <= l100_idx < len(data):
                            l100_obj = data[l100_idx]
                            if isinstance(l100_obj, dict) and "brutto" in l100_obj:
                                brutto_idx = l100_obj["brutto"]
                                if isinstance(brutto_idx, int) and 0 <= brutto_idx < len(data):
                                    raw_val = data[brutto_idx]
                                    if isinstance(raw_val, (int, float)):
                                        price_per_l = Decimal(str(raw_val)) / Decimal(100)
                                        return Decimal(str(round(price_per_l, 4)))

                    # Check total brutto fallback
                    if isinstance(item, dict) and "total" in item and menge_liter > 0:
                        total_idx = item["total"]
                        if isinstance(total_idx, int) and 0 <= total_idx < len(data):
                            total_obj = data[total_idx]
                            if isinstance(total_obj, dict) and "brutto" in total_obj:
                                brutto_idx = total_obj["brutto"]
                                if isinstance(brutto_idx, int) and 0 <= brutto_idx < len(data):
                                    raw_val = data[brutto_idx]
                                    if isinstance(raw_val, (int, float)):
                                        price_per_l = Decimal(str(raw_val)) / Decimal(menge_liter)
                                        return Decimal(str(round(price_per_l, 4)))

            except (json.JSONDecodeError, KeyError, IndexError, InvalidOperation) as exc:
                logger.debug("Fehler beim Parsen des Nuxt-Script-Payloads: %s", exc)
                continue

        return None

    def _parse_dom_elements(self, soup: BeautifulSoup, menge_liter: int) -> Decimal | None:
        """Extracts price from DOM elements such as .price-text-large or '100 Liter Heizölpreis'."""
        # Check elements with class price-text-large
        for el in soup.find_all(class_=re.compile(r"price-text-large", re.I)):
            text = el.get_text().strip()
            match = re.search(r"(\d+[\.,]\d{2})", text)
            if match:
                try:
                    val = Decimal(_clean_decimal_str(match.group(1)))
                    # Typically 100L price is between ~50 and 300 €
                    if val > Decimal(30):
                        price_per_l = val / Decimal(100)
                        return Decimal(str(round(price_per_l, 4)))
                    elif Decimal("0.40") <= val <= Decimal("5.00"):
                        return Decimal(str(round(val, 4)))
                except InvalidOperation:
                    continue

        # Check for context text '100 Liter'
        for tag in soup.find_all(["div", "span", "p", "li"]):
            txt = " ".join(tag.get_text().split())
            if "100 liter" in txt.lower():
                match = re.search(r"(\d+[\.,]\d{2})\s*€", txt)
                if match:
                    try:
                        val = Decimal(_clean_decimal_str(match.group(1)))
                        if val > Decimal(30):
                            price_per_l = val / Decimal(100)
                            return Decimal(str(round(price_per_l, 4)))
                    except InvalidOperation:
                        continue

        return None

    def _parse_table_and_units(self, soup: BeautifulSoup, menge_liter: int) -> Decimal | None:
        """Extracts price from table rows or cells with explicit units (e.g. '€ / Liter')."""
        for cell in soup.find_all(["td", "th", "div", "span"]):
            txt = " ".join(cell.get_text().split())
            # Check for pattern like '0,9850 € / Liter'
            match_per_liter = re.search(
                r"(\d+[\.,]\d{2,4})\s*€?\s*(?:/|pro)?\s*(?:liter|l)\b", txt, re.IGNORECASE
            )
            if match_per_liter:
                try:
                    val = Decimal(_clean_decimal_str(match_per_liter.group(1)))
                    if Decimal("0.40") <= val <= Decimal("5.00"):
                        return Decimal(str(round(val, 4)))
                except InvalidOperation:
                    continue

            # Check for pattern like '165,62 € / 100 Liter'
            match_per_100l = re.search(
                r"(\d+[\.,]\d{2})\s*€?\s*(?:/|pro)?\s*100\s*(?:liter|l)\b", txt, re.IGNORECASE
            )
            if match_per_100l:
                try:
                    val = Decimal(_clean_decimal_str(match_per_100l.group(1)))
                    price_per_l = val / Decimal(100)
                    return Decimal(str(round(price_per_l, 4)))
                except InvalidOperation:
                    continue

        return None

    def _parse_regex_fallback(self, html: str, menge_liter: int) -> Decimal | None:
        """Regex fallback scanning the entire HTML for price markers."""
        # Match explicit €/l or € / Liter
        match_per_l = re.search(
            r"(\d+[\.,]\d{2,4})\s*€\s*/\s*Liter", html, re.IGNORECASE
        )
        if match_per_l:
            try:
                val = Decimal(_clean_decimal_str(match_per_l.group(1)))
                if Decimal("0.40") <= val <= Decimal("5.00"):
                    return Decimal(str(round(val, 4)))
            except InvalidOperation:
                pass

        # Match 100 Liter ... €
        match_100l = re.search(
            r"100\s*Liter[^\d]{1,50}(\d+[\.,]\d{2})\s*€", html, re.IGNORECASE
        )
        if match_100l:
            try:
                val = Decimal(_clean_decimal_str(match_100l.group(1)))
                if val > Decimal(30):
                    price_per_l = val / Decimal(100)
                    return Decimal(str(round(price_per_l, 4)))
            except InvalidOperation:
                pass

        return None

    def save_price_to_db(
        self, result: OilPriceResult, session: Session
    ) -> HeizoelPreis:
        """Saves or updates heating oil price in heizoel_preis table idempotently."""
        stmt = select(HeizoelPreis).where(
            HeizoelPreis.datum == result.datum,
            HeizoelPreis.plz == result.plz,
            HeizoelPreis.menge_liter == result.menge_liter,
        )
        record = session.execute(stmt).scalar_one_or_none()

        if record is None:
            record = HeizoelPreis(
                datum=result.datum,
                plz=result.plz,
                menge_liter=result.menge_liter,
                preis_pro_liter=result.preis_pro_liter,
            )
            session.add(record)
        else:
            record.preis_pro_liter = result.preis_pro_liter

        session.commit()
        session.refresh(record)
        return record

    async def poll_and_save(
        self,
        session: Session | None = None,
        date: datetime.date | None = None,
        plz: str | None = None,
        menge_liter: int | None = None,
        url: str | None = None,
        html: str | None = None,
    ) -> HeizoelPreis | None:
        """Fetches oil price, parses HTML and persists the result to the database."""
        target_date = date or datetime.date.today()
        target_plz = plz or self.settings.HEIZOEL_PLZ
        target_amount = menge_liter or self.settings.HEIZOEL_MENGE_LITER

        page_html = html
        if page_html is None:
            page_html = await self.fetch_oil_price_html(
                plz=target_plz, menge_liter=target_amount, url=url
            )

        if not page_html:
            logger.warning(
                "Keine HTML-Antwort vom Heizölpreis-Anbieter erhalten für PLZ %s.",
                target_plz,
            )
            return None

        price = self.parse_oil_price(page_html, menge_liter=target_amount)
        if price is None:
            logger.warning(
                "Konnte keinen gültigen Heizölpreis für PLZ %s aus HTML extrahieren.",
                target_plz,
            )
            return None

        result = OilPriceResult(
            datum=target_date,
            plz=target_plz,
            menge_liter=target_amount,
            preis_pro_liter=price,
        )

        if session is not None:
            return self.save_price_to_db(result, session)

        for db in get_db_session("verbrauch"):
            return self.save_price_to_db(result, db)

        return None

