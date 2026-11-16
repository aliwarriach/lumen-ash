from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.coach.merge import Label
from app.grammar.catalog import PatternKey

# What fits on one book page of exercise. The AI layer rejects what is too long for it.
MAX_EXERCISE_TEXT = 2400  # plus the topic list, this stays under the AI template's input limit
MIN_WORDS = 3

ExerciseText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_EXERCISE_TEXT)
]

VERIFY_WARNING = "Verify with your teacher."


class ScanHelpIn(BaseModel):
    text: ExerciseText = Field(
        description="The exercise as the learner reviewed it. The photo itself never reaches us."
    )

    @field_validator("text")
    @classmethod
    def _enough_text(cls, v: str) -> str:
        if len(v.split()) < MIN_WORDS:
            raise ValueError("There is not enough text to work with. Take the photo again.")
        return v


class ScanItemOut(BaseModel):
    number: str = Field(description="As printed in the book, or empty")
    task: str = Field(description="The line of the exercise")
    hint: str = Field(description="Points to the rule without giving the answer")
    answer: str = Field(description="Show only when the learner asks")
    filled: str | None = Field(description="The whole German sentence with the answer in place")
    label: Label = Field(description="How much to trust the answer")
    warning: str | None = Field(description="Set for 'uncertain' answers")
    verified_by: str | None = Field(
        description="Why our own rules agree with the answer, when they do"
    )
    why: str | None
    pattern_key: PatternKey | None
    pattern_title: str | None


class ScanHelpOut(BaseModel):
    instruction: str | None = Field(description="What the exercise asks")
    items: list[ScanItemOut]
    limits: str | None = Field(description="What was left out (picture, audio, layout), and why")
    checked_by: list[Literal["ai", "languagetool"]] = Field(
        description="Which checkers looked at the answers"
    )
    cached: bool = Field(description="The same exercise was asked before: no allowance was used")
