import tomllib
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_CONFIG_FILENAME = "extract.toml"


class OutputFieldConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str

    @field_validator("name", "description")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: list[OutputFieldConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_field_names(self) -> "OutputConfig":
        field_names = [field.name for field in self.format]
        if len(field_names) != len(set(field_names)):
            raise ValueError("duplicate output field names found")

        return self


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instructions: str
    model: str
    temperature: float | None = None
    top_p: float | None = None
    max_output_tokens: int | None = None
    reasoning_effort: str | None = None
    verbosity: str | None = None
    base_url: str | None = None
    api_key_env: str = "OPENAI_API_KEY"

    @field_validator("instructions", "model", "api_key_env")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class ExtractConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: LLMConfig
    output: OutputConfig


def load_packaged_config_text() -> str:
    return (
        files("fin_ai_stats_extract.resources")
        .joinpath(DEFAULT_CONFIG_FILENAME)
        .read_text(encoding="utf-8")
    )


def ensure_config_file(working_directory: Path | None = None) -> Path:
    directory = working_directory or Path.cwd()
    config_path = directory / DEFAULT_CONFIG_FILENAME
    if not config_path.exists():
        config_path.write_text(load_packaged_config_text(), encoding="utf-8")
    return config_path


def load_config(
    config_path: Path | None = None,
    working_directory: Path | None = None,
) -> ExtractConfig:
    if config_path is None:
        resolved_path = ensure_config_file(working_directory)
    else:
        resolved_path = config_path
    with resolved_path.open("rb") as handle:
        raw_config = tomllib.load(handle)
    return ExtractConfig.model_validate(raw_config)
    return ExtractConfig.model_validate(raw_config)
