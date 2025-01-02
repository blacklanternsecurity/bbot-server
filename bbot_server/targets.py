from pydantic import BaseModel


class Target(BaseModel):
    name: str = "Default Target"
    whitelist: list[str] = []
