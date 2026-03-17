from pydantic import BaseModel


class ValidationIssue(BaseModel):
    rule: int
    message: str
    context: dict | None = None


class ValidationResult(BaseModel):
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
