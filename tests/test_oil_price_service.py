import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from data_recorder.core.database import Base
from data_recorder.models.verbrauch import HeizoelPreis
from data_recorder.services.oil_price_service import OilPriceResult, OilPriceService

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={
            "schema_translate_map": {"verbrauch": None, "wertpapiere": None}
        },
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def standard_html() -> str:
    return (FIXTURES_DIR / "heizoel_esyoil_standard.html").read_text(encoding="utf-8")


@pytest.fixture
def alternative_html() -> str:
    return (FIXTURES_DIR / "heizoel_esyoil_alternative.html").read_text(encoding="utf-8")


@pytest.fixture
def no_price_html() -> str:
    return (FIXTURES_DIR / "heizoel_no_price.html").read_text(encoding="utf-8")


@pytest.fixture
def corrupt_html() -> str:
    return (FIXTURES_DIR / "heizoel_corrupt.html").read_text(encoding="utf-8")


def test_clean_decimal_str():
    from data_recorder.services.oil_price_service import _clean_decimal_str
    assert _clean_decimal_str("2.462,50") == "2462.50"
    assert _clean_decimal_str("165,62") == "165.62"
    assert _clean_decimal_str(" 1.50 ") == "1.50"



def test_parse_oil_price_esyoil_standard(standard_html: str):
    service = OilPriceService()
    price = service.parse_oil_price(standard_html, menge_liter=2500)
    assert price is not None
    assert price == Decimal("1.6562")


def test_parse_oil_price_esyoil_alternative(alternative_html: str):
    service = OilPriceService()
    price = service.parse_oil_price(alternative_html, menge_liter=2500)
    assert price is not None
    assert price == Decimal("0.9850")


def test_parse_oil_price_nuxt_script_only():
    service = OilPriceService()
    minimal_nuxt_html = """
    <html><head></head><body>
    <script id="__NUXT_DATA__" type="application/json">
    ["Reactive", {"pricing": 2}, {"_100L": 3}, {"brutto": 4}, 145.50]
    </script>
    </body></html>
    """
    price = service.parse_oil_price(minimal_nuxt_html, menge_liter=2500)
    assert price is not None
    assert price == Decimal("1.4550")


def test_parse_oil_price_no_price(no_price_html: str):
    service = OilPriceService()
    price = service.parse_oil_price(no_price_html, menge_liter=2500)
    assert price is None


def test_parse_oil_price_corrupt(corrupt_html: str):
    service = OilPriceService()
    price = service.parse_oil_price(corrupt_html, menge_liter=2500)
    assert price is None


def test_parse_oil_price_empty_string():
    service = OilPriceService()
    assert service.parse_oil_price("", menge_liter=2500) is None
    assert service.parse_oil_price(None, menge_liter=2500) is None
    assert service.parse_oil_price("   ", menge_liter=2500) is None


def test_parse_oil_price_dom_price_text_large():
    service = OilPriceService()
    html_100l = "<html><body><div class='price-text-large'>162,50 €</div></body></html>"
    assert service.parse_oil_price(html_100l) == Decimal("1.6250")

    html_per_l = "<html><body><div class='price-text-large'>1,2500 €</div></body></html>"
    assert service.parse_oil_price(html_per_l) == Decimal("1.2500")

    html_invalid = "<html><body><div class='price-text-large'>abc €</div></body></html>"
    assert service.parse_oil_price(html_invalid) is None


def test_parse_oil_price_dom_100_liter_context():
    service = OilPriceService()
    html = "<html><body><div>100 Liter tagesaktuell 155,00 € inkl. MwSt</div></body></html>"
    assert service.parse_oil_price(html) == Decimal("1.5500")

    html_invalid = "<html><body><div>100 Liter ohne Preis</div></body></html>"
    assert service.parse_oil_price(html_invalid) is None


def test_parse_oil_price_table_100l_and_per_l():
    service = OilPriceService()
    html_100l = "<html><body><td>165,62 € / 100 Liter</td></body></html>"
    assert service.parse_oil_price(html_100l) == Decimal("1.6562")

    html_per_l = "<html><body><td>1,0500 € / l</td></body></html>"
    assert service.parse_oil_price(html_per_l) == Decimal("1.0500")

    html_invalid = "<html><body><td>99,99 € / Liter</td></body></html>"
    # 99,99 €/l is outside reasonable range 0.40 - 5.00
    assert service.parse_oil_price(html_invalid) is None


def test_parse_oil_price_regex_fallback():
    service = OilPriceService()
    html_per_l = "Eilmeldung: Heizölpreis beträgt 1,1234 € / Liter heute im Handel."
    assert service.parse_oil_price(html_per_l) == Decimal("1.1234")

    html_100l = "Aktion: 100 Liter Standard-Heizöl heute für sensationelle 159,90 € verfügbar."
    assert service.parse_oil_price(html_100l) == Decimal("1.5990")


def test_parse_oil_price_nuxt_total_fallback():
    service = OilPriceService()
    html = """
    <html><body>
    <script id="__NUXT_DATA__" type="application/json">
    ["Reactive", {"pricing": 2}, {"total": 3}, {"brutto": 4}, 2500.00]
    </script>
    </body></html>
    """
    assert service.parse_oil_price(html, menge_liter=2500) == Decimal("1.0000")


def test_parse_oil_price_nuxt_corrupt_json():
    service = OilPriceService()
    html = """
    <html><body>
    <script id="__NUXT_DATA__" type="application/json">
    [{"_100L": 1}, corrupt_json}
    </script>
    <div>100 Liter 140,00 €</div>
    </body></html>
    """
    # Should safely ignore corrupt json and fall back to DOM
    assert service.parse_oil_price(html) == Decimal("1.4000")


def test_parse_oil_price_invalid_operation_branches():
    service = OilPriceService()
    with patch("data_recorder.services.oil_price_service._clean_decimal_str", return_value="invalid_num"):
        assert service.parse_oil_price("<div class='price-text-large'>160,00 €</div>") is None
        assert service.parse_oil_price("<div>100 Liter 160,00 €</div>") is None
        assert service.parse_oil_price("<td>1,20 € / Liter</td>") is None
        assert service.parse_oil_price("<td>160,00 € / 100 Liter</td>") is None
        assert service.parse_oil_price("1,20 € / Liter") is None
        assert service.parse_oil_price("100 Liter 160,00 €") is None




@pytest.mark.asyncio
async def test_fetch_oil_price_html_success():
    service = OilPriceService()
    fake_html = "<html><body><div class='price-text-large'>160,00 €</div></body></html>"

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.is_error = False
        mock_response.text = fake_html
        mock_get.return_value = mock_response

        result = await service.fetch_oil_price_html(plz="90579", menge_liter=2500)
        assert result == fake_html
        assert mock_get.call_count == 1
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["params"] == {"zipcode": "90579", "amount": 2500}


@pytest.mark.asyncio
async def test_fetch_oil_price_html_retry_and_eventual_success():
    service = OilPriceService()
    fake_html = "<html><body>Success</body></html>"

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_err_resp = MagicMock()
        mock_err_resp.is_error = True
        mock_err_resp.status_code = 502
        mock_err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Gateway", request=MagicMock(), response=mock_err_resp
        )

        mock_ok_resp = MagicMock()
        mock_ok_resp.is_error = False
        mock_ok_resp.text = fake_html

        mock_get.side_effect = [mock_err_resp, mock_ok_resp]

        result = await service.fetch_oil_price_html(
            plz="90579", menge_liter=2500, max_retries=2, retry_delay=0.01
        )
        assert result == fake_html
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_fetch_oil_price_html_all_retries_fail_returns_none():
    service = OilPriceService()

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.ConnectTimeout("Timeout connecting to esyoil")

        result = await service.fetch_oil_price_html(
            plz="90579", menge_liter=2500, max_retries=2, retry_delay=0.01
        )
        assert result is None
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_fetch_oil_price_html_custom_url_and_params():
    service = OilPriceService()
    custom_url = "https://custom.esyoil.test/api"

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.is_error = False
        mock_resp.text = "OK"
        mock_get.return_value = mock_resp

        result = await service.fetch_oil_price_html(
            plz="90402", menge_liter=3000, url=custom_url
        )
        assert result == "OK"
        assert mock_get.call_args.args[0] == custom_url
        assert mock_get.call_args.kwargs["params"] == {"zipcode": "90402", "amount": 3000}


def test_save_price_to_db_insert_new(db_session: Session):
    service = OilPriceService()
    test_date = datetime.date(2026, 9, 27)
    result = OilPriceResult(
        datum=test_date,
        plz="90579",
        menge_liter=2500,
        preis_pro_liter=Decimal("1.6562"),
    )

    record = service.save_price_to_db(result, db_session)
    assert record.id is not None
    assert record.datum == test_date
    assert record.plz == "90579"
    assert record.menge_liter == 2500
    assert record.preis_pro_liter == Decimal("1.6562")

    # Verify query from db
    saved = db_session.execute(
        select(HeizoelPreis).where(
            HeizoelPreis.datum == test_date,
            HeizoelPreis.plz == "90579",
            HeizoelPreis.menge_liter == 2500,
        )
    ).scalar_one()
    assert saved.id == record.id


def test_save_price_to_db_idempotent_update(db_session: Session):
    service = OilPriceService()
    test_date = datetime.date(2026, 9, 27)

    res1 = OilPriceResult(
        datum=test_date,
        plz="90579",
        menge_liter=2500,
        preis_pro_liter=Decimal("1.6562"),
    )
    rec1 = service.save_price_to_db(res1, db_session)

    res2 = OilPriceResult(
        datum=test_date,
        plz="90579",
        menge_liter=2500,
        preis_pro_liter=Decimal("1.6500"),
    )
    rec2 = service.save_price_to_db(res2, db_session)

    assert rec1.id == rec2.id
    assert rec2.preis_pro_liter == Decimal("1.6500")

    # Only 1 record exists in table
    records = db_session.execute(
        select(HeizoelPreis).where(
            HeizoelPreis.datum == test_date,
            HeizoelPreis.plz == "90579",
            HeizoelPreis.menge_liter == 2500,
        )
    ).scalars().all()
    assert len(records) == 1
    assert records[0].preis_pro_liter == Decimal("1.6500")


@pytest.mark.asyncio
async def test_poll_and_save_success_with_provided_html(
    db_session: Session, standard_html: str
):
    service = OilPriceService()
    test_date = datetime.date(2026, 9, 27)

    record = await service.poll_and_save(
        session=db_session,
        html=standard_html,
        date=test_date,
        plz="90579",
        menge_liter=2500,
    )
    assert record is not None
    assert record.datum == test_date
    assert record.plz == "90579"
    assert record.menge_liter == 2500
    assert record.preis_pro_liter == Decimal("1.6562")


@pytest.mark.asyncio
async def test_poll_and_save_fetch_none_returns_none(db_session: Session):
    service = OilPriceService()
    with patch.object(service, "fetch_oil_price_html", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = None
        record = await service.poll_and_save(session=db_session)
        assert record is None
        assert mock_fetch.call_count == 1


@pytest.mark.asyncio
async def test_poll_and_save_parse_fails_returns_none(
    db_session: Session, corrupt_html: str
):
    service = OilPriceService()
    with patch.object(service, "fetch_oil_price_html", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = corrupt_html
        record = await service.poll_and_save(session=db_session)
        assert record is None


@pytest.mark.asyncio
async def test_poll_and_save_default_session_generator(standard_html: str):
    service = OilPriceService()
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={
            "schema_translate_map": {"verbrauch": None, "wertpapiere": None}
        },
    )
    Base.metadata.create_all(bind=engine)

    def dummy_session_gen(schema="verbrauch"):
        with Session(engine) as s:
            yield s

    with patch("data_recorder.services.oil_price_service.get_db_session", side_effect=dummy_session_gen):
        record = await service.poll_and_save(html=standard_html, date=datetime.date(2026, 9, 27))
        assert record is not None
        assert record.preis_pro_liter == Decimal("1.6562")


@pytest.mark.asyncio
async def test_poll_and_save_empty_generator(standard_html: str):
    service = OilPriceService()
    def empty_gen(schema="verbrauch"):
        if False:
            yield None
    with patch("data_recorder.services.oil_price_service.get_db_session", side_effect=empty_gen):
        rec = await service.poll_and_save(html=standard_html)
        assert rec is None



