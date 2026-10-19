from pydantic import BaseModel, ConfigDict


class SchemaBase(BaseModel):
    """Base configuration shared by application schemas."""

    model_config = ConfigDict(from_attributes=True)
