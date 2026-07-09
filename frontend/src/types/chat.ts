export interface ParsedIntent {
  intent: string
  entities: Record<string, string | number | null>
  raw_query: string
  confidence: number
}

export interface TextResponse {
  type: 'text'
  message: string
  is_error: boolean
}

export interface ChartDataset {
  label: string
  data: number[]
}

export interface ChartResponse {
  type: 'chart'
  chart_type: 'bar' | 'radar' | 'line'
  labels: string[]
  datasets: ChartDataset[]
  title: string
}

export interface TableResponse {
  type: 'table'
  columns: string[]
  rows: Array<Record<string, string | number | null>>
  title: string
}

export interface ComparisonResponse {
  type: 'comparison'
  title: string
  // full ComparisonResult shape comes from player.ts — imported in components
  data: unknown
}

export type ResponseUnion = TextResponse | ChartResponse | TableResponse | ComparisonResponse

export interface ChatResponse {
  response: ResponseUnion
  intent: ParsedIntent | null
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  response?: ResponseUnion
  timestamp: Date
}
