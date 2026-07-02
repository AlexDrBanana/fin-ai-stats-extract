import { useEffect, useRef, useState } from "react"
import {
  waitForApi,
  type ConfigState,
  type MetaState,
  type OutputField,
  type PyApi,
  type RuntimeState,
} from "@/lib/api"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { RunTab } from "@/components/tabs/RunTab"
import { AiSettingsTab } from "@/components/tabs/AiSettingsTab"
import { InstructionsTab } from "@/components/tabs/InstructionsTab"
import { OutputFormatTab } from "@/components/tabs/OutputFormatTab"
import { Check, Loader2, Play, TriangleAlert } from "lucide-react"

type SaveStatus = "idle" | "saving" | "saved" | "error"

export default function App() {
  const [api, setApi] = useState<PyApi | null>(null)
  const [config, setConfig] = useState<ConfigState | null>(null)
  const [runtime, setRuntime] = useState<RuntimeState | null>(null)
  const [meta, setMeta] = useState<MetaState | null>(null)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle")
  const [saveError, setSaveError] = useState("")
  const [review, setReview] = useState<{ ok: boolean; message: string } | null>(
    null,
  )
  const [running, setRunning] = useState(false)

  const skipFirstSave = useRef(true)
  const saveTimer = useRef<number | undefined>(undefined)
  const reviewTimer = useRef<number | undefined>(undefined)

  useEffect(() => {
    let active = true
    waitForApi().then(async (bridge) => {
      const state = await bridge.get_state()
      if (!active) return
      setApi(bridge)
      setConfig(state.config)
      setRuntime(state.runtime)
      setMeta(state.meta)
    })
    return () => {
      active = false
    }
  }, [])

  // Persist config edits to the TOML file (debounced).
  useEffect(() => {
    if (!api || !config) return
    if (skipFirstSave.current) {
      skipFirstSave.current = false
      return
    }
    setSaveStatus("saving")
    window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(async () => {
      const res = await api.save_config(config)
      if (res.ok) {
        setSaveStatus("saved")
        setSaveError("")
      } else {
        setSaveStatus("error")
        setSaveError(res.message ?? "Failed to save config")
      }
    }, 450)
    return () => window.clearTimeout(saveTimer.current)
  }, [api, config])

  // Recompute the run review (debounced) on any change.
  useEffect(() => {
    if (!api || !config || !runtime) return
    window.clearTimeout(reviewTimer.current)
    reviewTimer.current = window.setTimeout(async () => {
      const res = await api.compute_review({ config, runtime })
      setReview({ ok: res.ok, message: res.message ?? "" })
    }, 550)
    return () => window.clearTimeout(reviewTimer.current)
  }, [api, config, runtime])

  function updateConfig<K extends keyof ConfigState>(
    key: K,
    value: ConfigState[K],
  ) {
    setConfig((prev) => (prev ? { ...prev, [key]: value } : prev))
  }

  function updateRuntime<K extends keyof RuntimeState>(
    key: K,
    value: RuntimeState[K],
  ) {
    setRuntime((prev) => (prev ? { ...prev, [key]: value } : prev))
  }

  function setOutputFormat(fields: OutputField[]) {
    setConfig((prev) => (prev ? { ...prev, output_format: fields } : prev))
  }

  async function browse(kind: "input_file" | "input_folder" | "output") {
    if (!api) return
    const picked =
      kind === "input_file"
        ? await api.browse_input_file()
        : kind === "input_folder"
          ? await api.browse_input_folder()
          : await api.browse_output_file()
    if (!picked) return
    updateRuntime(kind === "output" ? "output" : "input", picked)
  }

  async function handleRun() {
    if (!api || !config || !runtime) return
    setRunning(true)
    const res = await api.run({ config, runtime })
    if (!res.ok) {
      setRunning(false)
      setReview({ ok: false, message: res.message ?? "Failed to start run" })
    }
    // On success the Python side closes this window and runs in the terminal.
  }

  async function handleCancel() {
    if (!api) return
    await api.cancel()
  }

  if (!config || !runtime || !meta) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" />
        Loading configuration…
      </div>
    )
  }

  return (
    <div className="mx-auto flex h-screen max-w-3xl flex-col gap-4 p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">fin-ai-stats-extract</h1>
          <p className="truncate text-xs text-muted-foreground">
            {meta.config_path}
          </p>
        </div>
        <SaveBadge status={saveStatus} error={saveError} />
      </header>

      <Tabs defaultValue="run" className="flex min-h-0 flex-1 flex-col">
        <TabsList>
          <TabsTrigger value="run">Run</TabsTrigger>
          <TabsTrigger value="ai">AI Settings</TabsTrigger>
          <TabsTrigger value="instructions">Instructions</TabsTrigger>
          <TabsTrigger value="output">Output Format</TabsTrigger>
        </TabsList>

        <div className="min-h-0 flex-1 overflow-y-auto py-4 pr-1">
          <TabsContent value="run">
            <RunTab
              runtime={runtime}
              onChange={updateRuntime}
              onBrowseInputFile={() => browse("input_file")}
              onBrowseInputFolder={() => browse("input_folder")}
              onBrowseOutput={() => browse("output")}
            />
          </TabsContent>
          <TabsContent value="ai">
            <AiSettingsTab config={config} onChange={updateConfig} meta={meta} />
          </TabsContent>
          <TabsContent value="instructions">
            <InstructionsTab
              value={config.instructions}
              onChange={(v) => updateConfig("instructions", v)}
            />
          </TabsContent>
          <TabsContent value="output">
            <OutputFormatTab
              fields={config.output_format}
              onChange={setOutputFormat}
            />
          </TabsContent>
        </div>
      </Tabs>

      <footer className="flex items-center justify-between gap-4 border-t pt-4">
        <p
          className={
            "min-w-0 flex-1 truncate text-xs " +
            (review && !review.ok
              ? "text-destructive"
              : "text-muted-foreground")
          }
          title={review?.message}
        >
          {review?.message || "\u00a0"}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleCancel} disabled={running}>
            Cancel
          </Button>
          <Button
            onClick={handleRun}
            disabled={running || (review ? !review.ok : false)}
          >
            {running ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Play className="size-4" />
            )}
            Run
          </Button>
        </div>
      </footer>
    </div>
  )
}

function SaveBadge({ status, error }: { status: SaveStatus; error: string }) {
  if (status === "saving") {
    return (
      <Badge variant="secondary" className="gap-1">
        <Loader2 className="size-3 animate-spin" />
        Saving…
      </Badge>
    )
  }
  if (status === "saved") {
    return (
      <Badge variant="secondary" className="gap-1">
        <Check className="size-3" />
        Saved
      </Badge>
    )
  }
  if (status === "error") {
    return (
      <Badge variant="destructive" className="gap-1" title={error}>
        <TriangleAlert className="size-3" />
        Save failed
      </Badge>
    )
  }
  return null
}
