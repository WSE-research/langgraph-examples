from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import unicodedata
import uuid
from enum import Enum

app = FastAPI(root_path='/pizza-api')

# Enums and Models
class OrderStatus(str, Enum):
    RECEIVED = "received"
    PREPARING = "preparing"
    ON_DELIVERY = "on_delivery"
    DELIVERED = "delivered"

class Address(BaseModel):
    city: str
    street: str
    house_number: str

class OrderCreate(BaseModel):
    pizza_id: int
    city: str
    street: str
    house_number: str

class Order(BaseModel):
    id: str
    pizza_id: int
    address: Address
    status: OrderStatus

# Mock database
pizzas = [
    {"id": 1, "name": "Margherita"},
    {"id": 2, "name": "Pepperoni"},
    {"id": 3, "name": "Hawaiian"},
    {"id": 4, "name": "Quattro Formaggi"},
    # Ids 1-4 are stable: existing course material and student code refer to
    # them. New items are appended, never inserted.
    {"id": 5, "name": "Funghi"},
    {"id": 6, "name": "Salami"},
    {"id": 7, "name": "Prosciutto"},
    {"id": 8, "name": "Diavola"},
    {"id": 9, "name": "Vegetariana"},
    {"id": 10, "name": "Calzone"}
]

# Store orders in memory (in a real application, use a proper database)
orders = {}

# Valid cities for delivery. Leipzig, Halle and Dresden serve the HTWK course;
# the French cities serve the guest lecture at Universite Jean Monnet
# Saint-Etienne, whose running example delivers to 5 Rue Michelet.
VALID_CITIES = [
    "Leipzig", "Halle", "Dresden",
    "Saint-\u00c9tienne", "Saint-Priest-en-Jarez", "Lyon"
]


def normalize_city(city: str) -> str:
    """Fold a city name for comparison: no accents, no case, no stray spaces.

    Students type "saint-etienne", "Saint-Etienne" and "Saint-\u00c9tienne" for the
    same place, and a delivery service that refuses two of the three teaches
    nothing about addresses. The stored order keeps the spelling the caller
    sent; only the comparison is folded.
    """
    stripped = unicodedata.normalize("NFKD", city or "")
    stripped = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return " ".join(stripped.replace("-", " ").split()).casefold()


VALID_CITIES_NORMALIZED = {normalize_city(city): city for city in VALID_CITIES}

@app.get("/pizza")
async def list_pizzas():
    """List all available pizzas"""
    return pizzas

@app.post("/address/validate")
async def validate_address(address: Address):
    """Validate delivery address"""
    # Check if city is serviceable (accent- and case-insensitive)
    if normalize_city(address.city) not in VALID_CITIES_NORMALIZED:
        raise HTTPException(
            status_code=400,
            detail=f"We don't deliver to {address.city}. Available cities: {', '.join(VALID_CITIES)}"
        )
    
    # Basic validation for street and house number
    if len(address.street) < 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid street name"
        )
    
    if not address.house_number:
        raise HTTPException(
            status_code=400,
            detail="House number is required"
        )

    return {"message": "Address is valid", "address": address}

@app.post("/order")
async def create_order(order: OrderCreate):
    """Create a neworder"""
    # Validate pizza_id
    if not any(pizza["id"] == order.pizza_id for pizza in pizzas):
        raise HTTPException(
            status_code=404,
            detail="Pizza not found"
        )

    # Validate address
    address = Address(
        city=order.city,
        street=order.street,
        house_number=order.house_number
    )
    await validate_address(address)

    # Create order
    order_id = str(uuid.uuid4())
    new_order = Order(
        id=order_id,
        pizza_id=order.pizza_id,
        address=address,
        status=OrderStatus.RECEIVED
    )
    
    # Save order
    orders[order_id] = new_order

    return {"order_id": order_id, "status": OrderStatus.RECEIVED}

@app.get("/order/{order_id}")
async def get_order_status(order_id: str):
    """Get order status by order ID"""
    if order_id not in orders:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )
    
    return {
        "order_id": order_id,
        "status": orders[order_id].status,
        "pizza_id": orders[order_id].pizza_id,
        "address": orders[order_id].address
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
