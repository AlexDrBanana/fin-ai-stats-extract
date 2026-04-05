from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, create_model

from fin_ai_stats_extract.config import ExtractConfig, OutputFieldConfig


class AIInfrastructure(BaseModel):
    """AI infrastructure investments: data centers, chips, hardware, cloud compute, etc."""

    ai_infra_binary: int = Field(
        description="1 if the firm mentions investment in AI infrastructure, 0 otherwise"
    )
    ai_infra_types: list[str] = Field(
        description="List of unique AI infrastructure types mentioned (no repetition). "
        "Examples: GPU clusters, data centers, cloud compute, custom chips, networking hardware"
    )
    ai_infra_count: int = Field(
        description="Count of unique AI infrastructure types mentioned"
    )
    ai_infra_dollar: float | None = Field(
        description="Dollar value invested in AI infrastructure. null if not disclosed"
    )


class AIAnalytics(BaseModel):
    """AI analytics investments: models, algorithms, AI-powered applications/products, etc."""

    ai_analytics_binary: int = Field(
        description="1 if the firm mentions investment in AI analytics/models/applications, 0 otherwise"
    )
    ai_analytics_types: list[str] = Field(
        description="List of unique AI analytics types mentioned (no repetition). "
        "Examples: LLMs, recommendation engines, predictive models, computer vision, NLP, generative AI"
    )
    ai_analytics_count: int = Field(
        description="Count of unique AI analytics types mentioned"
    )
    ai_analytics_dollar: float | None = Field(
        description="Dollar value invested in AI analytics. null if not disclosed"
    )


class AITalent(BaseModel):
    """AI human capital: hiring AI/ML engineers, data scientists, AI research talent, etc."""

    ai_talent_binary: int = Field(
        description="1 if the firm mentions investment in AI talent/hiring, 0 otherwise"
    )
    ai_talent_types: list[str] = Field(
        description="List of unique AI talent roles/areas mentioned (no repetition). "
        "Examples: ML engineers, data scientists, AI researchers, prompt engineers"
    )
    ai_talent_count: int = Field(
        description="Count of unique AI talent types mentioned"
    )
    ai_talent_dollar: float | None = Field(
        description="Dollar value invested in AI talent. null if not disclosed"
    )
    ai_talent_headcount: float | None = Field(
        description="Number of AI workers mentioned. null if not disclosed"
    )


class AIRisk(BaseModel):
    """AI risks, barriers, and challenges mentioned by the firm."""

    ai_risk_binary: int = Field(
        description="1 if the firm mentions AI-related risks, barriers, or challenges, 0 otherwise"
    )
    ai_risk_types: list[str] = Field(
        description="List of unique AI risk/barrier themes (no repetition). "
        "Examples: regulatory, ethical concerns, technical debt, talent shortage, data privacy, bias, hallucination"
    )
    ai_risk_count: int = Field(
        description="Count of unique AI risk/barrier themes mentioned"
    )
    ai_risk_sentiment: str | None = Field(
        description="Overall tone: 'positive' if risks are framed as manageable/opportunities, "
        "'negative' if framed as serious threats/obstacles, 'mixed' if both, null if no risks mentioned"
    )


class TechPhysical(BaseModel):
    """Non-AI physical technology investments: R&D facilities, labs, tech equipment (excluding AI)."""

    tech_phys_binary: int = Field(
        description="1 if the firm mentions non-AI physical tech investment, 0 otherwise"
    )
    tech_phys_dollar: float | None = Field(
        description="Dollar value of non-AI physical tech investment. null if not disclosed"
    )


class TechTalent(BaseModel):
    """Non-AI tech human capital: software engineers, IT staff, non-AI tech roles."""

    tech_talent_binary: int = Field(
        description="1 if the firm mentions non-AI tech talent investment, 0 otherwise"
    )
    tech_talent_headcount: float | None = Field(
        description="Number of non-AI tech workers mentioned. null if not disclosed"
    )
    tech_talent_dollar: float | None = Field(
        description="Dollar value of non-AI tech talent investment. null if not disclosed"
    )


class EarningsCallExtraction(BaseModel):
    """Structured extraction of AI and technology investment data from an earnings call transcript."""

    ai_infrastructure: AIInfrastructure
    ai_analytics: AIAnalytics
    ai_talent: AITalent
    ai_risk: AIRisk
    tech_physical: TechPhysical
    tech_talent: TechTalent


def _field_annotation(field: OutputFieldConfig) -> tuple[Any, Any]:
    if field.type == "integer":
        annotation: Any = int
    elif field.type == "number":
        annotation = float
    elif field.type == "string":
        if field.enum:
            enum_name = f"{field.name.title().replace('_', '')}Enum"
            annotation = Enum(
                enum_name, {value.upper(): value for value in field.enum}, type=str
            )
        else:
            annotation = str
    elif field.type == "string_array":
        annotation = list[str]
    else:  # pragma: no cover - guarded by config validation
        raise ValueError(f"unsupported field type: {field.type}")

    if field.nullable:
        return annotation | None, Field(default=None, description=field.description)
    return annotation, Field(..., description=field.description)


def build_extraction_model(config: ExtractConfig) -> type[BaseModel]:
    group_models: dict[str, tuple[type[BaseModel], Any]] = {}

    for group in config.output.groups:
        field_definitions = {
            field.name: _field_annotation(field) for field in group.fields
        }
        group_model = create_model(
            f"{group.key.title().replace('_', '')}Output",
            __base__=BaseModel,
            **field_definitions,
        )
        group_models[group.key] = (
            group_model,
            Field(..., description=group.description),
        )

    return create_model(
        "ConfiguredExtractionOutput",
        __base__=BaseModel,
        **group_models,
    )
