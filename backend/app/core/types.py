from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


# Every time the API returns is in UTC, whatever timezone the database connection uses.
UtcDatetime = Annotated[datetime, AfterValidator(_to_utc)]
