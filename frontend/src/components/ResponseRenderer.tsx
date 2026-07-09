import type { ResponseUnion } from '../types/chat'

interface Props {
  response: ResponseUnion
}

export default function ResponseRenderer({ response }: Props) {
  switch (response.type) {
    case 'text':
      return (
        <p className={response.is_error ? 'response-error' : 'response-text'}>
          {response.message}
        </p>
      )

    case 'chart':
      // TODO (Issue #11): render recharts chart
      return (
        <div className="placeholder-card">
          <strong>{response.title}</strong>
          <p className="placeholder-text">[Chart placeholder — recharts integration in Issue #11]</p>
        </div>
      )

    case 'table':
      return (
        <div className="table-wrapper">
          <strong>{response.title}</strong>
          <table className="data-table">
            <thead>
              <tr>{response.columns.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {response.rows.map((row, i) => (
                <tr key={i}>
                  {response.columns.map((c) => <td key={c}>{String(row[c] ?? '')}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )

    case 'comparison':
      return (
        <div className="placeholder-card">
          <strong>{response.title}</strong>
          <p className="placeholder-text">[Comparison chart — Issue #11]</p>
        </div>
      )
  }
}
