import { Input } from "@/components/ui/input"
import { Field } from "@/components/Field"
import { ChoiceSelect } from "@/components/ChoiceSelect"
import type { ConfigState, MetaState } from "@/lib/api"

interface AiSettingsTabProps {
  config: ConfigState
  onChange: <K extends keyof ConfigState>(key: K, value: ConfigState[K]) => void
  meta: MetaState
}

export function AiSettingsTab({ config, onChange, meta }: AiSettingsTabProps) {
  return (
    <div className="grid gap-5">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Model" hint="OpenAI or compatible model name.">
          <Input
            value={config.model}
            onChange={(e) => onChange("model", e.target.value)}
          />
        </Field>
        <Field label="API key env var" hint="Env variable holding the API key.">
          <Input
            value={config.api_key_env}
            onChange={(e) => onChange("api_key_env", e.target.value)}
          />
        </Field>
      </div>

      <Field
        label="Base URL"
        hint="OpenAI-compatible endpoint. Leave empty to use OpenAI."
      >
        <Input
          value={config.base_url}
          onChange={(e) => onChange("base_url", e.target.value)}
          placeholder="https://api.openai.com/v1"
        />
      </Field>

      <div className="grid grid-cols-3 gap-4">
        <Field label="Temperature" hint="0 – 2">
          <Input
            value={config.temperature}
            onChange={(e) => onChange("temperature", e.target.value)}
            placeholder="default"
          />
        </Field>
        <Field label="Top-p" hint="0 – 1">
          <Input
            value={config.top_p}
            onChange={(e) => onChange("top_p", e.target.value)}
            placeholder="default"
          />
        </Field>
        <Field label="Max output tokens" hint="Includes reasoning tokens.">
          <Input
            value={config.max_output_tokens}
            onChange={(e) => onChange("max_output_tokens", e.target.value)}
            placeholder="default"
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Reasoning effort" hint="For gpt-5 / o-series models.">
          <ChoiceSelect
            value={config.reasoning_effort}
            choices={meta.reasoning_effort_choices}
            onChange={(v) => onChange("reasoning_effort", v)}
            placeholder="(default)"
          />
        </Field>
        <Field label="Verbosity" hint="Text verbosity for supported models.">
          <ChoiceSelect
            value={config.verbosity}
            choices={meta.verbosity_choices}
            onChange={(v) => onChange("verbosity", v)}
            placeholder="(default)"
          />
        </Field>
      </div>
    </div>
  )
}
