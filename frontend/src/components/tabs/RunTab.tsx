import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Field } from "@/components/Field"
import type { RuntimeState } from "@/lib/api"
import { File, Folder } from "lucide-react"

interface RunTabProps {
  runtime: RuntimeState
  onChange: <K extends keyof RuntimeState>(key: K, value: RuntimeState[K]) => void
  onBrowseInputFile: () => void
  onBrowseInputFolder: () => void
  onBrowseOutput: () => void
}

export function RunTab({
  runtime,
  onChange,
  onBrowseInputFile,
  onBrowseInputFolder,
  onBrowseOutput,
}: RunTabProps) {
  return (
    <div className="grid gap-5">
      <Field
        label="Input path"
        hint="A single XML file or a folder of XML transcripts."
      >
        <div className="flex gap-2">
          <Input
            value={runtime.input}
            onChange={(e) => onChange("input", e.target.value)}
            placeholder="/path/to/transcripts"
          />
          <Button
            type="button"
            variant="outline"
            size="icon"
            title="Choose file"
            onClick={onBrowseInputFile}
          >
            <File className="size-4" />
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            title="Choose folder"
            onClick={onBrowseInputFolder}
          >
            <Folder className="size-4" />
          </Button>
        </div>
      </Field>

      <Field label="Output CSV" hint="Where extraction rows are written.">
        <div className="flex gap-2">
          <Input
            value={runtime.output}
            onChange={(e) => onChange("output", e.target.value)}
            placeholder="output.csv"
          />
          <Button type="button" variant="outline" onClick={onBrowseOutput}>
            Browse
          </Button>
        </div>
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field
          label="API key override"
          hint="Used for this run only; never written to the config file."
        >
          <Input
            type="password"
            value={runtime.api_key}
            onChange={(e) => onChange("api_key", e.target.value)}
            placeholder="sk-…"
          />
        </Field>
        <Field label="Max concurrency" hint="Concurrent extraction jobs.">
          <Input
            value={runtime.max_concurrency}
            inputMode="numeric"
            onChange={(e) => onChange("max_concurrency", e.target.value)}
          />
        </Field>
      </div>

      <Field
        label="Sample size"
        hint="Fraction in (0, 1) or an absolute count. Empty processes every file."
      >
        <Input
          value={runtime.sample}
          onChange={(e) => onChange("sample", e.target.value)}
          placeholder="all files"
        />
      </Field>

      <div className="flex flex-wrap gap-6 pt-1">
        <Toggle
          label="Dry run"
          checked={runtime.dry_run}
          onChange={(v) => onChange("dry_run", v)}
        />
        <Toggle
          label="Resume"
          checked={runtime.resume}
          onChange={(v) => onChange("resume", v)}
        />
        <Toggle
          label="Verbose logging"
          checked={runtime.verbose}
          onChange={(v) => onChange("verbose", v)}
        />
      </div>
    </div>
  )
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string
  checked: boolean
  onChange: (value: boolean) => void
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm">
      <Switch checked={checked} onCheckedChange={onChange} />
      <span>{label}</span>
    </label>
  )
}
