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
  // pywebview injects `window.pywebview.api` in two steps: first an empty
  // `api: {}` object, then (after introspecting the Python methods) it populates
  // the functions and fires `pywebviewready`. Checking truthiness of
  // `window.pywebview.api` is therefore not enough — during the gap it is an
  // empty object, and resolving with it yields `get_state === undefined` and a
  // permanently stuck "Loading configuration..." screen. Wait for a known method
  // to actually exist, and poll as a safety net in case the readiness event
  // fires before this listener attaches (or during the populate window).
  return new Promise((resolve) => {
    const isReady = () => typeof window.pywebview?.api?.get_state === "function"

    let settled = false
    let poll: number | undefined

    const finish = () => {
      if (settled || !isReady()) return
      settled = true
      window.removeEventListener("pywebviewready", finish)
      if (poll !== undefined) window.clearInterval(poll)
      resolve(window.pywebview!.api)
    }

    if (isReady()) {
      resolve(window.pywebview!.api)
      return
    }

    window.addEventListener("pywebviewready", finish)
    poll = window.setInterval(finish, 50)
  })
}
