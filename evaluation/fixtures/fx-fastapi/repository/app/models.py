from pydantic import BaseModel


class Customer(BaseModel):
    customer_id: int
    name: str

