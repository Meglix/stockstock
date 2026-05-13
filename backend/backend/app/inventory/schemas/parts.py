from pydantic import BaseModel, ConfigDict, Field, field_validator


class PartCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sku: str = Field(min_length=2, max_length=100)
    part_name: str = Field(min_length=2, max_length=255)
    category: str = Field(min_length=2, max_length=100)
    seasonality_profile: str | None = Field(default=None, min_length=2, max_length=100)
    base_demand: int | None = Field(default=None, ge=0, le=1000)
    supplier_id: str = Field(min_length=1, max_length=100)
    unit_price: float = Field(ge=0, le=100000)
    salary_sensitivity: float | None = Field(default=None, ge=0, le=100)
    lead_time_days: int = Field(ge=0, le=365)
    min_order_qty: int | None = Field(default=None, ge=0, le=1000)
    criticality: int = Field(ge=1, le=5)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.upper()

    @field_validator("supplier_id")
    @classmethod
    def normalize_supplier_id(cls, value: str) -> str:
        return value.upper()


class PartUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sku: str | None = Field(default=None, min_length=2, max_length=100)
    part_name: str | None = Field(default=None, min_length=2, max_length=255)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    seasonality_profile: str | None = Field(default=None, min_length=2, max_length=100)
    base_demand: int | None = Field(default=None, ge=0, le=1000)
    supplier_id: str | None = Field(default=None, min_length=1, max_length=100)
    unit_price: float | None = Field(default=None, ge=0, le=100000)
    salary_sensitivity: float | None = Field(default=None, ge=0, le=100)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    min_order_qty: int | None = Field(default=None, ge=0, le=1000)
    criticality: int | None = Field(default=None, ge=1, le=5)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.upper()

    @field_validator("supplier_id")
    @classmethod
    def normalize_supplier_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.upper()
