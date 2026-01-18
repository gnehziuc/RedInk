/**
 * 创作状态管理 - 集中管理创作中心的所有状态
 */
import { reactive, readonly, computed } from 'vue'

interface Message {
  role: 'assistant' | 'system'
  content?: string
  thinking?: string
  thinkingComplete?: boolean
  toolCall?: any
  toolResult?: any
  icon?: string
  time: string
}

interface CreationState {
  task: {
    id: string
    topic: string
    status: 'idle' | 'starting' | 'running' | 'complete' | 'error'
  }
  messages: Message[]
  result: {
    title: string
    summary: string
    pages: any[]
    images: any[]
  }
  ui: {
    currentThinking: string
    currentResponse: string
    errorMessage: string
  }
}

const state = reactive<CreationState>({
  task: { id: '', topic: '', status: 'idle' },
  messages: [],
  result: { title: '', summary: '', pages: [], images: [] },
  ui: { currentThinking: '', currentResponse: '', errorMessage: '' }
})

export function useCreationState() {
  // 计算属性
  const isGenerating = computed(() => state.task.status === 'running')
  const isComplete = computed(() => state.task.status === 'complete')
  const hasError = computed(() => state.task.status === 'error')
  const hasPreviewData = computed(() =>
    !!(state.result.title || state.result.summary || state.result.pages.length)
  )

  // 状态更新方法
  const setTask = (id: string, topic: string) => {
    state.task.id = id
    state.task.topic = topic
    state.task.status = 'starting'
  }

  const setTaskStatus = (status: CreationState['task']['status']) => {
    state.task.status = status
  }

  const addMessage = (message: Omit<Message, 'time'>) => {
    state.messages.push({
      ...message,
      time: new Date().toLocaleTimeString('zh-CN', { hour12: false })
    })
  }

  const updateResult = (data: Partial<CreationState['result']>) => {
    Object.assign(state.result, data)
  }

  const setError = (message: string) => {
    state.task.status = 'error'
    state.ui.errorMessage = message
  }

  const setCurrentThinking = (text: string) => {
    state.ui.currentThinking = text
  }

  const setCurrentResponse = (text: string) => {
    state.ui.currentResponse = text
  }

  const reset = () => {
    state.task = { id: '', topic: '', status: 'idle' }
    state.messages = []
    state.result = { title: '', summary: '', pages: [], images: [] }
    state.ui = { currentThinking: '', currentResponse: '', errorMessage: '' }
  }

  return {
    state: readonly(state),
    isGenerating,
    isComplete,
    hasError,
    hasPreviewData,
    setTask,
    setTaskStatus,
    addMessage,
    updateResult,
    setError,
    setCurrentThinking,
    setCurrentResponse,
    reset
  }
}
