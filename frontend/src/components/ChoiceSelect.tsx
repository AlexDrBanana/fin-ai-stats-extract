import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

// Radix Select forbids an empty-string item value, so the "unset/default"
// choice ("" from the backend) is mapped to a sentinel and back.
const UNSET = "__unset__"

interface ChoiceSelectProps {
  value: string
  choices: string[]
  onChange: (value: string) => void
  placeholder?: string
}

export function ChoiceSelect({
  value,
  choices,
  onChange,
  placeholder,
}: ChoiceSelectProps) {
  return (
    <Select
      value={value === "" ? UNSET : value}
      onValueChange={(v) => onChange(v === UNSET ? "" : v)}
    >
      <SelectTrigger className="w-full">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {choices.map((choice) => (
          <SelectItem
            key={choice === "" ? UNSET : choice}
            value={choice === "" ? UNSET : choice}
          >
            {choice === "" ? "(default)" : choice}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
