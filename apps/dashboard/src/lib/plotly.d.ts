/** Minimal type declarations for plotly.js-dist-min. */

declare module 'plotly.js-dist-min' {
  export interface PlotlyData {
    x?: number[] | string[]
    y?: number[] | string[]
    z?: number[] | string[]
    type?: 'scatter' | 'scatter3d' | 'bar' | 'line' | 'surface' | 'mesh3d'
    mode?: 'lines' | 'markers' | 'lines+markers' | 'text'
    name?: string
    marker?: {
      size?: number[] | number
      color?: number[] | string | string[]
      colorscale?: string | string[][]
      showscale?: boolean
      colorbar?: { title?: string }
      symbol?: string
      line?: { color?: string; width?: number }
    }
    line?: { color?: string; width?: number; dash?: string }
    text?: string[]
    hovertemplate?: string
    showlegend?: boolean
    xaxis?: string
    yaxis?: string
    scene?: string
  }

  export interface PlotlyLayout {
    title?: string | { text: string }
    line?: { color?: string; width?: number; dash?: string }
    height?: number
    paper_bgcolor?: string
    plot_bgcolor?: string
    font?: { color?: string; family?: string }
    xaxis?: Record<string, unknown>
    yaxis?: Record<string, unknown>
    scene?: {
      bgcolor?: string
      xaxis?: Record<string, unknown>
      yaxis?: Record<string, unknown>
      zaxis?: Record<string, unknown>
    }
    margin?: { l?: number; r?: number; t?: number; b?: number }
    hovermode?: string
    legend?: { x?: number; y?: number; font?: { color?: string }; orientation?: string }
    showlegend?: boolean
    template?: Record<string, unknown>
    dragmode?: string
    autosize?: boolean
  }

  export interface PlotlyConfig {
    responsive?: boolean
    displayModeBar?: boolean
    displaylogo?: boolean
    modeBarButtonsToRemove?: string[]
  }

  export type PlotlyHTMLElement = HTMLElement & { removeAllListeners?: () => void }

  export function newPlot(
    root: HTMLElement | string,
    data: PlotlyData[],
    layout?: Partial<PlotlyLayout>,
    config?: Partial<PlotlyConfig>,
  ): Promise<PlotlyHTMLElement>

  export function react(
    root: HTMLElement | string,
    data: PlotlyData[],
    layout?: Partial<PlotlyLayout>,
    config?: Partial<PlotlyConfig>,
  ): Promise<PlotlyHTMLElement>

  export function purge(root: HTMLElement | string): void
}
