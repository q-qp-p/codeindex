"""Data models."""


class User:
    def __init__(self, name: str, email: str) -> None:
        self.name = name
        self.email = email

    def display(self) -> str:
        return f"{self.name} <{self.email}>"


class Product:
    def __init__(self, sku: str, price: float) -> None:
        self.sku = sku
        self.price = price
