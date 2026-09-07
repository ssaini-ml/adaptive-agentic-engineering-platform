from app.api.customers import get_customer, list_customers
from app.services.customer import CustomerService


def test_list_customers() -> None:
    assert list_customers(CustomerService())[0].name == "Grace"


def test_get_customer() -> None:
    assert get_customer(1, CustomerService()).customer_id == 1

