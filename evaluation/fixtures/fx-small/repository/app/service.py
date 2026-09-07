from app.models import Customer


class CustomerService:
    def list_customers(self) -> list[Customer]:
        return [Customer(customer_id=1, name="Ada")]

    def get_customer(self, customer_id: int) -> Customer | None:
        return next(
            (customer for customer in self.list_customers() if customer.customer_id == customer_id),
            None,
        )

