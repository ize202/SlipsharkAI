from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from slipshark.domain.models import Platform


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
    ]
    platform: Platform = Platform.MOBILE
    max_results: Annotated[int, Field(ge=1, le=10)] = 5
