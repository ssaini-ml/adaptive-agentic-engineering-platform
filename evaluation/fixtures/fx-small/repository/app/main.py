from app.service import CustomerService


DEFAULT_PAGE_SIZE = 20


def create_service() -> CustomerService:
    return CustomerService()


def list_customer_names() -> list[str]:
    service = create_service()
    return [customer.name for customer in service.list_customers()]

