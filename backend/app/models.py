"""Imports every model module so Alembic sees the full schema. Add new modules here."""

from app.ai import models as ai_models
from app.capture import models as capture_models
from app.coach import models as coach_models
from app.community import models as community_models
from app.core.database import Base
from app.course import models as course_models
from app.dictionary import models as dictionary_models
from app.exams import models as exam_models
from app.grammar import models as grammar_models
from app.mistakes import models as mistake_models
from app.review import models as review_models
from app.sentences import models as sentence_models
from app.vocabulary import models as vocabulary_models

__all__ = [
    "Base",
    "ai_models",
    "capture_models",
    "coach_models",
    "community_models",
    "course_models",
    "dictionary_models",
    "exam_models",
    "grammar_models",
    "mistake_models",
    "review_models",
    "sentence_models",
    "vocabulary_models",
]
