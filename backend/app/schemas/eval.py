from pydantic import BaseModel


class EvalCaseCreate(BaseModel):
    question: str
    expected_title: str


class EvalCaseOut(BaseModel):
    id: int
    question: str
    expected_title: str

    class Config:
        from_attributes = True
