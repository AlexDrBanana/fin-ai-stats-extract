from importlib.resources import files
from pathlib import Path
import tomllib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FieldType = Literal["integer", "number", "string", "string_array"]

DEFAULT_CONFIG_FILENAME = "extract.toml"


class OutputFieldConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: FieldType
    description: str
    nullable: bool = False
    count_of: str | None = None
    enum: list[str] | None = None

    @field_validator("name", "description")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class OutputGroupConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    description: str
    fields: list[OutputFieldConfig]

    @field_validator("key", "title", "description")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_unique_field_names(self) -> "OutputGroupConfig":
        field_names = [field.name for field in self.fields]
        if len(field_names) != len(set(field_names)):
            raise ValueError(f"duplicate field names found in group {self.key}")
        return self


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groups: list[OutputGroupConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_group_keys(self) -> "OutputConfig":
        group_keys = [group.key for group in self.groups]
        if len(group_keys) != len(set(group_keys)):
            raise ValueError("duplicate output group keys found")
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