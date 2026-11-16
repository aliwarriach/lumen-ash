from pydantic import BaseModel, Field

from app.progress.review import Tone


class MetricOut(BaseModel):
    label: str
    value: int
    change: str = Field(description="Against the 7 days before, e.g. '+3 on last week'")
    rising: bool | None = Field(description="True for a rise; a fall is not marked as bad")


class StepOut(BaseModel):
    title: str
    detail: str
    progress: float | None = Field(description="0-1 when there is a bar to show")
    link: str | None = Field(description="An app route to open, e.g. '/sentences/k1-hallo'")


class ProgressReviewOut(BaseModel):
    tone: Tone
    headline: str
    message: str
    this_week: list[MetricOut]
    achievements: list[str] = Field(description="Only real positives")
    in_progress: list[StepOut]
    to_do: list[StepOut]
    improve: StepOut | None = Field(description="Points to the Mistake Log, constructively")
