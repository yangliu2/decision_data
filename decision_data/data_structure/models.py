from pydantic import BaseModel


class Story(BaseModel):
    title: str
    content: str
    url: str
    score: int
    comments: int
