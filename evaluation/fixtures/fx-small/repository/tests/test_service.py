from app.service import CustomerService


def test_lists_customers() -> None:
    customers = CustomerService().list_customers()
    assert customers[0].name == "Ada"

