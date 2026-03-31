from dataclasses import dataclass
from typing import Optional

@dataclass
class Product:
    name: str
    price: float
    url: str
    original_price: Optional[float] = None
    currency: str = "EUR"
    # Nové pole pro detailní rozpis (např. "Rošt: 400 + Sifon: 100")
    price_breakdown: Optional[str] = None