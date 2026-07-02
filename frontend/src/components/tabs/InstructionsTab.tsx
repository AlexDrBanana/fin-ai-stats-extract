import { Textarea } from "@/components/ui/textarea"

interface InstructionsTabProps {
  value: string
  onChange: (value: string) => void
}

export function InstructionsTab({ value, onChange }: InstructionsTabProps) {
  return (
    <div className="grid gap-2">
      <p className="text-sm text-muted-foreground">
        Base system instructions sent to the model. Saved to the config file as
        you type.
      </p>
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        spellCheck={false}
        className="min-h-[440px] font-mono text-xs leading-relaxed"
      />
    </div>
  )
}
