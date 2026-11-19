import uuid

from pydantic import (BaseModel, ConfigDict, Field, StrictInt, StrictStr,
                      field_validator, model_validator)

# Decisión nuestra: max+1 debe ser exacto en doble precisión (el script Lua de Redis calcula con doubles).
# 2**53 + 1 no es representable (float(2**53 + 1) == float(2**53)), así que el tope es 2**53 - 2.
MAX_LAMPORT = 2**53 - 2


class IncomingMessage(BaseModel):
    """Mensaje que llega del central. Campos desconocidos se ignoran (extra="ignore" por defecto)."""
    model_config = ConfigDict(populate_by_name=True)

    id: StrictStr
    from_: StrictStr = Field(alias="from")  # "from" es palabra reservada en Python
    origin: StrictStr = Field(min_length=1)
    lamport: StrictInt = Field(ge=0, le=MAX_LAMPORT)
    sent_at: StrictStr
    body: StrictStr  # HIPÓTESIS H7: sin límite de largo ni mínimo

    @field_validator("id")
    @classmethod
    def id_is_uuid(cls, v):
        uuid.UUID(v)  # ValueError si está mal formado => 422
        return v

    @model_validator(mode="after")
    def from_matches_origin(self):
        user, _, group = self.from_.rpartition("@")
        if not user or group != self.origin:
            raise ValueError("'from' debe tener la forma usuario@<origin>")
        return self

    def to_dict(self) -> dict:
        # Solo guardamos los campos conocidos.
        return {"id": self.id, "from": self.from_, "origin": self.origin,
                "lamport": self.lamport, "sent_at": self.sent_at, "body": self.body}
