import type { ComparisonResult } from './player'

export interface ParsedIntent {
  intent: 'ranking' | 'lookup' | 'comparison' | 'unknown'
  players: string[]
  metric: string | null
  league: string | null
  position: string | null
  min_age: number | null
  max_age: number | null
  limit: number
  raw_query: string
}

export interface TextResponse {
  type: 'text'
  message: string
  is_error: boolean
}

export interface ChartDataset {
  label: string
  data: number[]
  color?: string
}

export interface ChartResponse {
  type: 'chart'
  title: string
  chart_type: 'bar' | 'radar' | 'line'
  labels: string[]
  datasets: ChartDataset[]
}

export interface TableResponse {
  type: 'table'
  title: string
  columns: string[]
  rows: Array<Record<string, string | number | null>>
}

export interface ComparisonResponse {
  type: 'comparison'
  result: ComparisonResult
}

export type ResponseUnion = TextResponse | ChartResponse | TableResponse | ComparisonResponse

export interface ChatResponse {
  response: ResponseUnion
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  response?: ResponseUnion
  timestamp: Date
}

