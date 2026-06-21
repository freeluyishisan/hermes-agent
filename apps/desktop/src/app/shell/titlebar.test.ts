import { describe, expect, it } from 'vitest'

import {
  MACOS_TRAFFIC_LIGHTS_SAFE_WIDTH,
  TITLEBAR_CONTROL_OFFSET_X,
  TITLEBAR_EDGE_INSET,
  TITLEBAR_FALLBACK_WINDOW_BUTTON_X,
  titlebarControlsPosition,
  titlebarSafeArea
} from './titlebar'

describe('titlebarControlsPosition', () => {
  it('offsets controls from visible traffic lights', () => {
    expect(titlebarControlsPosition({ x: 24, y: 10 }).left).toBe(24 + TITLEBAR_CONTROL_OFFSET_X)
  })

  it('pins to the edge when macOS fullscreen hides traffic lights', () => {
    expect(titlebarControlsPosition({ x: 24, y: 10 }, true).left).toBe(TITLEBAR_EDGE_INSET)
  })

  it('pins to the edge on Windows/Linux where native controls render on the right', () => {
    expect(titlebarControlsPosition(null).left).toBe(TITLEBAR_EDGE_INSET)
  })

  it('uses the macOS fallback while the initial window state is unknown', () => {
    expect(titlebarControlsPosition(undefined).left).toBe(TITLEBAR_FALLBACK_WINDOW_BUTTON_X + TITLEBAR_CONTROL_OFFSET_X)
  })
})

describe('titlebarSafeArea', () => {
  it('models visible macOS traffic lights as left reserved chrome', () => {
    expect(titlebarSafeArea({ x: 24, y: 10 })).toEqual({
      left: 24 + MACOS_TRAFFIC_LIGHTS_SAFE_WIDTH,
      right: 0
    })
  })

  it('models Windows/Linux titleBarOverlay controls as right reserved chrome', () => {
    expect(titlebarSafeArea(null, 138)).toEqual({ left: 0, right: 138 })
  })

  it('clears the macOS left reservation while fullscreen hides traffic lights', () => {
    expect(titlebarSafeArea({ x: 24, y: 10 }, 0, true)).toEqual({ left: 0, right: 0 })
  })
})
