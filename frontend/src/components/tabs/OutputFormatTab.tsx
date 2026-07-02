import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { OutputField } from "@/lib/api"
import { Plus, Trash2 } from "lucide-react"

interface OutputFormatTabProps {
  fields: OutputField[]
  onChange: (fields: OutputField[]) => void
}

export function OutputFormatTab({ fields, onChange }: OutputFormatTabProps) {
  const update = (index: number, patch: Partial<OutputField>) => {
    onChange(fields.map((f, i) => (i === index ? { ...f, ...patch } : f)))
  }
  const remove = (index: number) => {
    onChange(fields.filter((_, i) => i !== index))
  }
  const add = () => {
    onChange([...fields, { name: "", description: "" }])
  }

  return (
    <div className="grid gap-3">
      <p className="text-sm text-muted-foreground">
        Columns the model extracts for every transcript, in order. Saved to the
        config file as you edit.
      </p>

      {fields.length === 0 ? (
        <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
          No output columns defined yet.
        </p>
      ) : null}

      {fields.map((field, index) => (
        <div
          key={index}
          className="grid gap-2 rounded-md border p-3 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto] md:items-start"
        >
          <Input
            value={field.name}
            placeholder="column_name"
            className="font-mono text-xs"
            onChange={(e) => update(index, { name: e.target.value })}
          />
          <Textarea
            value={field.description}
            placeholder="What the model should put in this column…"
            className="min-h-[64px] text-sm"
            onChange={(e) => update(index, { description: e.target.value })}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            title="Remove column"
            onClick={() => remove(index)}
          >
            <Trash2 className="size-4" />
          </Button>
        </div>
      ))}

      <div>
        <Button type="button" variant="outline" size="sm" onClick={add}>
          <Plus className="size-4" />
          Add column
        </Button>
      </div>
    </div>
  )
}
