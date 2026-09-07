from app.services.customer import CustomerService


def get_customer_service() -> CustomerService:
    return CustomerService()

