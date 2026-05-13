from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkflowOrderLinePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    part_id: int | None = Field(None, description="Part ID")
    sku: str | None = Field(None, description="Part SKU")
    quantity: int = Field(..., gt=0, le=1000)

    @model_validator(mode="after")
    def validate_identifier(self):
        if self.part_id is None and not self.sku:
            raise ValueError("Either part_id or sku is required")
        return self


class ClientOrderCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_name: str = Field(..., min_length=1, max_length=200)
    location: str | None = Field(None, max_length=100)
    requested_time: str | None = Field(None, max_length=40)
    items: list[WorkflowOrderLinePayload] = Field(..., min_length=1)


class ClientOrderSchedulePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduled_for: str | None = None
    time: str | None = Field(None, description="HH:MM local clock time")


class SupplierOrderCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: str | None = Field(None, max_length=80)
    location: str | None = Field(None, max_length=100)
    estimated_arrival: str | None = Field(None, max_length=120)
    items: list[WorkflowOrderLinePayload] = Field(..., min_length=1)


class SupplierOrderPostponePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    postponed_until: str | None = None
    time: str | None = Field(None, description="HH:MM local clock time")

