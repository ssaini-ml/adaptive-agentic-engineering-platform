from fastapi import FastAPI

from app.api.customers import router as customer_router


app = FastAPI(title="Fixture API")
app.include_router(customer_router)

