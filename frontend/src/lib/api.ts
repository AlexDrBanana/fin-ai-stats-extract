// Bridge to the Python `js_api` object exposed by pywebview as
// `window.pywebview.api`. In a plain browser (e.g. tests) a mock can be
// injected on `window.pywebview` before load.

export interface OutputField {
  name: string
  description: string
}

export interface ConfigState {
  instructions: string
  model: string
  api_key_env: string
  base_url: string
  temperature: string
  top_p: string
  max_output_tokens: string
  reasoning_effort: string
  verbosity: string
  output_format: OutputField[]
}

export interface RuntimeState {
  input: string
  output: string
  api_key: string
  max_concurrency: string
  sample: string
  dry_run: boolean
  resume: boolean
  verbose: boolean
}

export interface MetaState {
  config_path: string
  reasoning_effort_choices: string[]
  verbosity_choices: string[]
}

export interface AppState {
  config: ConfigState
  runtime: RuntimeState
  meta: MetaState
}

export interface ApiResult {
  ok: boolean
  message?: string
}

export interface RunPayload {
  config: ConfigState
  runtime: RuntimeState
}

export interface PyApi {
  get_state(): Promise<AppState>
  save_config(config: ConfigState): Promise<ApiResult>
  compute_review(payload: RunPayload): Promise<ApiResult>
  browse_input_file(): Promise<string>
  browse_input_folder(): Promise<string>
  browse_output_file(): Promise<string>
  run(payload: RunPayload): Promise<ApiResult>
  cancel(): Promise<ApiResult>
}

declare global {
  interface Window {
    pywebview?: { api: PyApi }
  }
}

export function waitForApi(): Promise<PyApi> {
  return new Promise((resolve) => {
    if (window.pywebview?.api) {
      resolve(window.pywebview.api)
      return
    }
    window.addEventListener(
      "pywebviewready",
      () => resolve(window.pywebview!.api),
      { once: true },
    )
  })
}
