import { useStore } from '@nanostores/react'
import { type MutableRefObject, useCallback, useEffect } from 'react'

import { gatewayEventCompletedFileDiff } from '@/lib/gateway-events'
import {
  $previewTarget,
  $sessionPreviewRegistry,
  beginPreviewServerRestart,
  completePreviewServerRestart,
  finishAllBuildingArtifactTabs,
  getSessionPreviewRecord,
  openArtifactTab,
  progressPreviewServerRestart,
  requestPreviewReload,
  setPreviewTarget,
  setSessionPreviewTarget,
  touchArtifactTab
} from '@/store/preview'
import { $currentCwd } from '@/store/session'
import type { RpcEvent } from '@/types/hermes'

type EventHandler = (event: RpcEvent) => void

interface PreviewRoutingOptions {
  activeSessionIdRef: MutableRefObject<string | null>
  baseHandleGatewayEvent: EventHandler
  currentCwd: string
  currentView: string
  requestGateway: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>
  routedSessionId: string | null
  selectedStoredSessionId: string | null
}

function asRecord(payload: unknown): Record<string, unknown> {
  return payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {}
}

function activePreviewSessionId(
  activeSessionIdRef: MutableRefObject<string | null>,
  routedSessionId: string | null,
  selectedStoredSessionId: string | null
): string {
  return selectedStoredSessionId || routedSessionId || activeSessionIdRef.current || ''
}

function looksLikePreviewTarget(value: string): boolean {
  return /^https?:\/\//i.test(value) || /^file:\/\//i.test(value) || /^(?:\/|\.{1,2}\/|~\/).+/.test(value)
}

function stripAnsi(value: string): string {
  return value.replace(new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, 'g'), '')
}

function htmlPathFromInlineDiff(value: string): string {
  const cleaned = stripAnsi(value).replace(/^\s*┊\s*review diff\s*\n/i, '')

  for (const match of cleaned.matchAll(/(?:^|\s)(?:[ab]\/)?([^\s]+\.html?)(?=\s|$)/gi)) {
    const candidate = match[1]?.trim()

    if (candidate) {
      return candidate
    }
  }

  return ''
}

function structuredPreviewCandidate(payload: unknown): string {
  const record = asRecord(payload)
  const fields = ['url', 'target', 'path', 'file', 'filepath', 'preview']

  for (const field of fields) {
    const value = record[field]

    if (typeof value === 'string') {
      const target = value.trim()

      if (target && looksLikePreviewTarget(target)) {
        return target
      }
    }
  }

  const inlineDiff = record.inline_diff

  if (typeof inlineDiff === 'string') {
    return htmlPathFromInlineDiff(inlineDiff)
  }

  return ''
}

/** Tool names that produce HTML artifacts when they write files. */
const ARTIFACT_TOOL_NAMES = new Set(['write_file', 'patch', 'append_file', 'write'])

/** Check if a string looks like an HTML file path. */
function isHtmlPath(value: string): boolean {
  return /\.html?$/i.test(value)
}

/**
 * Extract an HTML file path from a tool call payload (tool.start / tool.progress).
 * Returns the raw path string or null.
 */
function artifactPathFromCall(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null
  const rec = payload as Record<string, unknown>

  // arguments/args may be a string (positional) or an object with named fields
  const args = rec.arguments ?? rec.args
  if (typeof args === 'string') {
    return isHtmlPath(args) ? args.trim() : null
  }
  if (typeof args === 'object' && args !== null) {
    const argsObj = args as Record<string, unknown>
    for (const key of ['path', 'file_path', 'filePath', 'file']) {
      const v = argsObj[key]
      if (typeof v === 'string' && isHtmlPath(v)) return v.trim()
    }
  }

  // Fallback: scan all string values for HTML paths
  for (const val of Object.values(rec)) {
    if (typeof val === 'string' && isHtmlPath(val)) return val.trim()
  }
  return null
}

/** Extract an HTML file path from a tool result payload (tool.complete). */
function artifactPathFromResult(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null
  const rec = payload as Record<string, unknown>
  for (const key of ['path', 'file', 'filepath', 'file_path', 'target_path', 'artifact']) {
    const v = rec[key]
    if (typeof v === 'string' && isHtmlPath(v)) return v.trim()
  }
  return null
}

/** Get the tool name from a gateway event payload. */
function getToolName(payload: unknown): string {
  if (!payload || typeof payload !== 'object') return ''
  const rec = payload as Record<string, unknown>
  return String(rec.name ?? rec.tool ?? rec.tool_name ?? '')
}

export function usePreviewRouting({
  activeSessionIdRef,
  baseHandleGatewayEvent,
  currentCwd,
  currentView,
  requestGateway,
  routedSessionId,
  selectedStoredSessionId
}: PreviewRoutingOptions) {
  const previewRegistry = useStore($sessionPreviewRegistry)
  const previewSessionId = activePreviewSessionId(activeSessionIdRef, routedSessionId, selectedStoredSessionId)

  useEffect(() => {
    if (currentView !== 'chat' || !previewSessionId) {
      setPreviewTarget(null)

      return
    }

    const record = getSessionPreviewRecord(previewSessionId)

    setPreviewTarget(record?.normalized ?? null)
  }, [currentView, previewRegistry, previewSessionId])

  const registerStructuredPreview = useCallback(
    async (event: RpcEvent) => {
      if (
        event.session_id &&
        event.session_id !== activeSessionIdRef.current &&
        event.session_id !== previewSessionId
      ) {
        return
      }

      if (!event.type.startsWith('tool.')) {
        return
      }

      if (!previewSessionId) {
        return
      }

      const candidate = structuredPreviewCandidate(event.payload)

      if (!candidate) {
        return
      }

      const desktop = window.hermesDesktop

      if (!desktop?.normalizePreviewTarget) {
        return
      }

      const sessionId = previewSessionId
      const cwd = currentCwd || ''
      const target = await desktop.normalizePreviewTarget(candidate, cwd || undefined).catch(() => null)

      if (
        !target ||
        sessionId !== activePreviewSessionId(activeSessionIdRef, routedSessionId, selectedStoredSessionId) ||
        $currentCwd.get() !== cwd
      ) {
        return
      }

      setSessionPreviewTarget(sessionId, target, 'tool-result', candidate)
    },
    [activeSessionIdRef, currentCwd, previewSessionId, routedSessionId, selectedStoredSessionId]
  )

  const restartPreviewServer = useCallback(
    async (url: string, context?: string) => {
      const sessionId = activeSessionIdRef.current

      if (!sessionId) {
        throw new Error('No active session for background restart')
      }

      const cwd = $currentCwd.get() || currentCwd || ''

      const result = await requestGateway<{ task_id?: string }>('preview.restart', {
        context: context || undefined,
        cwd: cwd || undefined,
        session_id: sessionId,
        url
      })

      const taskId = result.task_id || ''

      if (!taskId) {
        throw new Error('Background restart did not return a task id')
      }

      beginPreviewServerRestart(taskId, url)

      return taskId
    },
    [activeSessionIdRef, currentCwd, requestGateway]
  )

  const handleDesktopGatewayEvent = useCallback<EventHandler>(
    event => {
      baseHandleGatewayEvent(event)

      if (event.type === 'preview.restart.complete') {
        const { task_id, text } = asRecord(event.payload)

        if (typeof task_id === 'string' && task_id) {
          completePreviewServerRestart(task_id, typeof text === 'string' ? text : '')
        }
      } else if (event.type === 'preview.restart.progress') {
        const { task_id, text } = asRecord(event.payload)

        if (typeof task_id === 'string' && task_id) {
          progressPreviewServerRestart(task_id, typeof text === 'string' ? text : '')
        }
      }

      if (event.session_id && event.session_id !== activeSessionIdRef.current) {
        return
      }

      // Artifact sidecar: detect write_file/patch of HTML files
      const toolName = getToolName(event.payload)
      const isArtifactTool = ARTIFACT_TOOL_NAMES.has(toolName)

      if (isArtifactTool && (event.type === 'tool.start' || event.type === 'tool.progress')) {
        const artifactPath = artifactPathFromCall(event.payload)
        if (artifactPath) {
          touchArtifactTab(artifactPath)
          const desktop = window.hermesDesktop
          if (desktop?.normalizePreviewTarget) {
            const sessionId = activePreviewSessionId(activeSessionIdRef, routedSessionId, selectedStoredSessionId)
            void desktop.normalizePreviewTarget(artifactPath, currentCwd || undefined)
              .then(normalized => {
                if (normalized && normalized.kind === 'file' && normalized.previewKind === 'html') {
                  const currentSid = activePreviewSessionId(activeSessionIdRef, routedSessionId, selectedStoredSessionId)
                  if (currentSid === sessionId) openArtifactTab(normalized)
                }
              })
              .catch(() => {})
          }
        }
      } else if (isArtifactTool && event.type === 'tool.complete') {
        const artifactPath = artifactPathFromResult(event.payload)
        if (artifactPath) touchArtifactTab(artifactPath)
      }

      // Mark all building artifacts as done when the agent's turn completes
      if (event.type === 'message.complete' || event.type === 'message.cancelled') {
        finishAllBuildingArtifactTabs()
      }

      void registerStructuredPreview(event)

      if ($previewTarget.get()?.kind === 'url' && gatewayEventCompletedFileDiff(event)) {
        requestPreviewReload()
      }
    },
    [activeSessionIdRef, baseHandleGatewayEvent, currentCwd, registerStructuredPreview, routedSessionId, selectedStoredSessionId]
  )

  return { handleDesktopGatewayEvent, restartPreviewServer }
}
