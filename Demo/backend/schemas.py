from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator
from .configurations import DEFAULT_PRESET, get_preset, resolve_configuration


class FeatureOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    db_on: StrictBool | None = None
    crop_dict_on: StrictBool | None = None
    progressive_filtering_on: StrictBool | None = None
    confidence_on: StrictBool | None = None
    web_search_on: StrictBool | None = None
    domain_filter_on: StrictBool | None = None
    ingestion_loop_on: StrictBool | None = None

    @model_validator(mode="before")
    @classmethod
    def no_nulls(cls, values):
        if isinstance(values, dict) and any(value is None for value in values.values()):
            raise ValueError("Feature overrides must be booleans")
        return values


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=8000)
    task_type: Literal["management", "identification"] = "management"
    state: str = Field(default="", max_length=100)
    county: str = Field(default="", max_length=100)
    month_year: str | None = Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    preset_id: str = DEFAULT_PRESET
    overrides: FeatureOverrides = Field(default_factory=FeatureOverrides)

    @field_validator("preset_id")
    @classmethod
    def valid_preset(cls, value):
        get_preset(value)
        return value

    @model_validator(mode="after")
    def location_valid(self):
        self.configuration()
        if self.county and not self.state:
            raise ValueError("Provide state with county")
        return self

    def configuration(self):
        return resolve_configuration(self.preset_id, self.overrides.model_dump(exclude_none=True))

    @property
    def location(self):
        return ", ".join(part for part in (self.state, self.county) if part)

    def prompt(self):
        # Preserve the crop enricher's recognized location prefix.
        query = self.question
        if self.month_year:
            query += f"\n\n[Context month/year: {self.month_year}]"
        return f"[User location: {self.location}]\n\n{query}" if self.location else query


class ClearRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    collection: str
    confirmation: str


class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    run_id: str = Field(min_length=1, max_length=100)
