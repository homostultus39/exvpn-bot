from pydantic import BaseModel


class Tariff(BaseModel):
    days: int
    stars: int
    rub: int


TARIFFS = {
    "30": Tariff(days=30, stars=48, rub=90),
    "90": Tariff(days=90, stars=136, rub=256),
    "180": Tariff(days=180, stars=266, rub=502),
    "360": Tariff(days=360, stars=515, rub=972),
}
