"""Dependency Injection для FastAPI."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.logging import setup_logging
from backend.services.document_service import DocumentService
from backend.services.grammar_service import GrammarService
from backend.services.validation_service import ValidationService

# Налаштування логування при імпорті
setup_logging()


def get_grammar_service() -> GrammarService:
    """
    Dependency для GrammarService.

    Returns:
        Singleton екземпляр GrammarService
    """
    return GrammarService()


def get_validation_service() -> ValidationService:
    """
    Dependency для ValidationService.

    Returns:
        Singleton екземпляр ValidationService
    """
    return ValidationService()


def get_document_service(
    db: Annotated[Session, Depends(get_db)],
    grammar: Annotated[GrammarService, Depends(get_grammar_service)],
) -> DocumentService:
    """
    Dependency для DocumentService.

    Args:
        db: Сесія бази даних
        grammar: Сервіс морфології

    Returns:
        Екземпляр DocumentService
    """
    return DocumentService(db, grammar)


# Типізовані aliases для зручності
DBSession = Annotated[Session, Depends(get_db)]
GrammarSvc = Annotated[GrammarService, Depends(get_grammar_service)]
ValidationSvc = Annotated[ValidationService, Depends(get_validation_service)]
DocumentSvc = Annotated[DocumentService, Depends(get_document_service)]
