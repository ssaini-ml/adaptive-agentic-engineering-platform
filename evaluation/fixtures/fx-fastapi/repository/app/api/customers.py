from fastapi import APIRouter, Depends

from app.dependencies import get_customer_service
from app.models import Customer
from app.services.customer import CustomerService


router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/", response_model=list[Customer])
def list_customers(
    service: CustomerService = Depends(get_customer_service),
) -> list[Customer]:
    return service.list_customers()


@router.get("/{customer_id}", response_model=Customer)
def get_customer(
    customer_id: int,
    service: CustomerService = Depends(get_customer_service),
) -> Customer:
    customer = service.get_customer(customer_id)
    if customer is None:
        raise LookupError(customer_id)
    return customer

