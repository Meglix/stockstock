from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator, field_validator


class StockCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    part_id: int | None = Field(
        default=None,
        gt=0,
        validation_alias=AliasChoices("part_id", "productId", "product_id"),
    )
    sku: str | None = Field(default=None, min_length=2, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    part_name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    supplier: str | None = Field(default=None, min_length=1, max_length=255)
    supplier_id: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=2, max_length=100)
    location_id: str | None = Field(default=None, min_length=2, max_length=50)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    country_code: str | None = Field(default=None, min_length=2, max_length=3)
    current_stock: int = Field(default=0, ge=0, le=1000, validation_alias=AliasChoices("current_stock", "current"))
    reorder_point: int = Field(default=0, ge=0, le=1000, validation_alias=AliasChoices("reorder_point", "reorderPoint"))
    safety_stock: int = Field(default=0, ge=0, le=1000)
    optimal_stock: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        validation_alias=AliasChoices("optimal_stock", "recommended", "recommended_stock"),
    )
    min_order_qty: int | None = Field(default=None, ge=0, le=1000)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    pending_order_qty: int | None = Field(default=0, ge=0, le=1000)
    stockout_days_history: int | None = Field(default=None, ge=0, le=365)
    total_sales_history: int | None = Field(default=None, ge=0, le=10000)
    latent_demand_signal_history: int | None = Field(default=None, ge=0, le=10000)
    inventory_status: str | None = Field(default=None, min_length=2, max_length=50)
    avg_daily_demand_30d: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.upper()

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.upper()

    @model_validator(mode="after")
    def validate_stock_levels(self):
        if self.part_id is None and not self.sku:
            raise ValueError("part_id or sku is required")
        if self.optimal_stock is None:
            self.optimal_stock = max(self.current_stock, self.reorder_point, 1)
        if self.optimal_stock < self.safety_stock:
            raise ValueError("optimal_stock must be greater than or equal to safety_stock")
        if self.optimal_stock < self.reorder_point:
            raise ValueError("optimal_stock must be greater than or equal to reorder_point")
        return self


class StockUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    current_stock: int | None = Field(default=None, ge=0, le=1000, validation_alias=AliasChoices("current_stock", "current"))
    reorder_point: int | None = Field(default=None, ge=0, le=1000, validation_alias=AliasChoices("reorder_point", "reorderPoint"))
    safety_stock: int | None = Field(default=None, ge=0, le=1000)
    optimal_stock: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        validation_alias=AliasChoices("optimal_stock", "recommended", "recommended_stock"),
    )
    min_order_qty: int | None = Field(default=None, ge=0, le=1000)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    pending_order_qty: int | None = Field(default=None, ge=0, le=1000)
    stockout_days_history: int | None = Field(default=None, ge=0, le=365)
    total_sales_history: int | None = Field(default=None, ge=0, le=10000)
    latent_demand_signal_history: int | None = Field(default=None, ge=0, le=10000)
    inventory_status: str | None = Field(default=None, min_length=2, max_length=50)
    avg_daily_demand_30d: int | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode="after")
    def validate_stock_levels_if_provided(self):
        if self.optimal_stock is not None and self.safety_stock is not None:
            if self.optimal_stock < self.safety_stock:
                raise ValueError("optimal_stock must be greater than or equal to safety_stock")
        if self.optimal_stock is not None and self.reorder_point is not None:
            if self.optimal_stock < self.reorder_point:
                raise ValueError("optimal_stock must be greater than or equal to reorder_point")
        return self
