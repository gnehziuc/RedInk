<template>
  <div class="creation-center">
    <!-- 输入模式：没有主题时显示 -->
    <template v-if="!isTaskStarted">
      <div class="input-mode">
        <div class="input-hero">
          <div class="brand-pill">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
            </svg>
            AI 智能创作中心
          </div>
          <h1 class="hero-title">你想创作什么？</h1>
          <p class="hero-subtitle">输入你的创意主题，AI 将为你生成完整的小红书图文内容</p>
        </div>

        <div class="topic-input-card">
          <div class="input-wrapper">
            <textarea
              ref="topicInputRef"
              v-model="topicInput"
              placeholder="例如：分享一个简单的早餐食谱..."
              rows="3"
              @keydown.enter.ctrl="handleStartCreation"
              @keydown.enter.meta="handleStartCreation"
            ></textarea>
          </div>
          <div class="input-actions">
            <div class="input-tips">
              <span>Ctrl + Enter 发送</span>
            </div>
            <button
              class="start-btn"
              @click="handleStartCreation"
              :disabled="!topicInput.trim() || isStarting"
            >
              <template v-if="isStarting">
                <div class="btn-spinner"></div>
                启动中...
              </template>
              <template v-else>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>
                </svg>
                开始创作
              </template>
            </button>
          </div>
        </div>

        <div class="quick-examples">
          <span class="examples-label">试试这些：</span>
          <button
            v-for="example in quickExamples"
            :key="example"
            class="example-tag"
            @click="topicInput = example"
          >
            {{ example }}
          </button>
        </div>
      </div>
    </template>

    <!-- 执行模式：有主题时显示 -->
    <template v-else>
      <!-- 左侧执行面板 -->
      <div class="execution-panel">
        <div class="panel-header">
          <h2 class="panel-title">AI 创作执行面板</h2>
          <button class="new-task-btn" @click="handleNewTask" title="新建创作">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </button>
        </div>

        <!-- 任务信息 -->
        <div class="task-info" v-if="topic">
          <div class="task-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
            </svg>
          </div>
          <div class="task-details">
            <div class="task-name">{{ topic }}</div>
            <div class="task-meta">{{ taskStatus }}</div>
          </div>
        </div>

        <!-- 状态消息 -->
        <div class="status-card" :class="statusClass">
          <p class="status-message">{{ statusMessage }}</p>
        </div>

        <!-- 对话消息列表 -->
        <div class="messages-container" ref="messagesContainer">
          <div
            v-for="(msg, index) in messages"
            :key="index"
            class="message-item"
            :class="msg.role"
          >
            <!-- AI 消息 -->
            <template v-if="msg.role === 'assistant'">
              <div class="message-avatar">
                <span>🤖</span>
              </div>
              <div class="message-body">
                <!-- 思考过程（可折叠） -->
                <div class="thinking-block" v-if="msg.thinking" :class="{ complete: msg.thinkingComplete }">
                  <div
                    class="thinking-toggle"
                    @click="toggleThinking(index)"
                    :class="{ expanded: msg.thinkingExpanded }"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                    <span class="thinking-label">{{ msg.thinkingComplete ? '✅ 思考完成' : '💭 思考过程' }}</span>
                    <span class="thinking-preview" v-if="!msg.thinkingExpanded">
                      {{ msg.thinking.slice(0, 50) }}{{ msg.thinking.length > 50 ? '...' : '' }}
                    </span>
                  </div>
                  <div class="thinking-full" v-show="msg.thinkingExpanded">
                    <pre>{{ msg.thinking }}</pre>
                  </div>
                </div>
                <!-- 回答内容 -->
                <div class="message-content" v-if="msg.content">
                  {{ msg.content }}
                </div>
                <!-- 工具调用（可折叠） -->
                <div class="tool-call-block" v-if="msg.toolCall" :class="{ expanded: msg.toolCall.expanded }">
                  <div class="tool-call-header" @click="toggleToolCall(index)">
                    <svg class="expand-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                    <span class="tool-icon">🔧</span>
                    <span class="tool-name">{{ msg.toolCall.name }}</span>
                    <span class="tool-status">调用中...</span>
                  </div>
                  <div class="tool-call-details" v-show="msg.toolCall.expanded">
                    <div class="tool-call-input" v-if="msg.toolCall.input">
                      <div class="detail-label">输入参数:</div>
                      <pre>{{ msg.toolCall.input }}</pre>
                    </div>
                  </div>
                </div>
                <!-- 工具结果（可折叠） -->
                <div class="tool-result-block" v-if="msg.toolResult" :class="{ error: msg.toolResult.isError, expanded: msg.toolResult.expanded }">
                  <div class="tool-result-header" @click="toggleToolResult(index)">
                    <svg class="expand-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                    <span>{{ msg.toolResult.isError ? '❌ 执行失败' : '✅ 执行成功' }}</span>
                  </div>
                  <div class="tool-result-details" v-show="msg.toolResult.expanded">
                    <div class="tool-result-content" v-if="msg.toolResult.output">
                      <pre>{{ msg.toolResult.output }}</pre>
                    </div>
                  </div>
                </div>
                <div class="message-time">{{ msg.time }}</div>
              </div>
            </template>

            <!-- 系统消息（步骤） -->
            <template v-else-if="msg.role === 'system'">
              <div class="system-message">
                <span class="system-icon">{{ msg.icon || '📌' }}</span>
                <span class="system-text">{{ msg.content }}</span>
                <span class="system-time">{{ msg.time }}</span>
              </div>
            </template>
          </div>

          <!-- 当前思考中（实时流式） -->
          <div class="message-item assistant" v-if="currentThinking">
            <div class="message-avatar">
              <span>🤖</span>
            </div>
            <div class="message-body">
              <div class="thinking-block active">
                <div class="thinking-toggle expanded">
                  <span class="thinking-label">💭 正在思考</span>
                  <span class="thinking-dots">...</span>
                </div>
                <div class="thinking-full streaming">
                  <pre>{{ currentThinking }}</pre>
                </div>
              </div>
            </div>
          </div>

          <!-- 当前回复中（流式打字机效果） -->
          <div class="message-item assistant" v-if="currentResponse">
            <div class="message-avatar">
              <span>🤖</span>
            </div>
            <div class="message-body">
              <div class="message-content streaming">
                {{ currentResponse }}<span class="typing-cursor">|</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部输入框（追加指令） -->
        <div class="input-section">
          <input
            type="text"
            v-model="additionalInput"
            placeholder="向 AI 输入更多指令..."
            @keyup.enter="sendAdditionalInput"
            :disabled="!isGenerating && !isComplete"
          />
          <button class="send-btn" @click="sendAdditionalInput" :disabled="(!isGenerating && !isComplete) || !additionalInput">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </div>
      </div>

    <!-- 右侧内容预览 -->
    <div class="preview-panel">
      <!-- 状态栏 -->
      <div class="preview-header">
        <div class="status-badge" :class="statusBadgeClass">
          <span class="status-dot"></span>
          <span>{{ statusBadgeText }}</span>
        </div>
        <div class="preview-actions">
          <button class="action-btn" :class="{ active: previewMode === 'outline' }" @click="previewMode = 'outline'">
            大纲
          </button>
          <button class="action-btn" :class="{ active: previewMode === 'preview' }" @click="previewMode = 'preview'">
            预览
          </button>
          <button class="action-btn primary" @click="downloadResult" :disabled="!isComplete">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            导出
          </button>
        </div>
      </div>

      <!-- 内容区域 -->
      <div class="preview-content">
        <!-- 大纲模式 -->
        <div v-if="previewMode === 'outline'" class="outline-view">
          <!-- 生成中提示 -->
          <div class="preview-status-banner" v-if="isGenerating && hasPreviewData">
            <div class="banner-icon">
              <div class="mini-spinner"></div>
            </div>
            <span>正在生成中，以下为实时预览...</span>
          </div>

          <h1 class="content-title" v-if="generatedTitle">{{ generatedTitle }}</h1>

          <!-- 摘要 -->
          <div class="content-section" v-if="generatedSummary">
            <h3 class="section-title">摘要</h3>
            <p class="section-text">{{ generatedSummary }}</p>
          </div>

          <!-- 页面列表 -->
          <div class="pages-list" v-if="generatedPages.length > 0">
            <div
              v-for="(page, index) in generatedPages"
              :key="index"
              class="page-item"
              :class="{ generating: isGenerating }"
            >
              <div class="page-number">{{ index + 1 }}</div>
              <div class="page-content">
                <div class="page-title">{{ page.title || `第 ${index + 1} 页` }}</div>
                <div class="page-text">{{ page.content }}</div>
              </div>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="!hasPreviewData && !isGenerating" class="empty-state">
            <div class="empty-icon">📝</div>
            <p>等待 AI 生成内容...</p>
          </div>

          <!-- 生成中状态（无预览数据时） -->
          <div v-if="isGenerating && !hasPreviewData" class="generating-state">
            <div class="spinner"></div>
            <p>正在生成内容...</p>
            <p class="generating-tip">AI 正在思考和创作，请稍候</p>
          </div>
        </div>

        <!-- 预览模式 -->
        <div v-else class="preview-view">
          <!-- 生成中提示 -->
          <div class="preview-status-banner" v-if="isGenerating && generatedImages.length > 0">
            <div class="banner-icon">
              <div class="mini-spinner"></div>
            </div>
            <span>正在生成图片，以下为实时预览...</span>
          </div>

          <div class="images-grid" v-if="generatedImages.length > 0">
            <div
              v-for="(image, index) in generatedImages"
              :key="index"
              class="image-card"
              :class="{ generating: isGenerating }"
            >
              <img :src="image.url" :alt="`第 ${index + 1} 页`" />
              <div class="image-overlay">
                <span>Page {{ index + 1 }}</span>
              </div>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="generatedImages.length === 0" class="empty-state">
            <div class="empty-icon">🖼️</div>
            <p>{{ isGenerating ? '正在生成图片...' : '等待生成图片...' }}</p>
            <p class="generating-tip" v-if="isGenerating">图片将在大纲生成完成后开始生成</p>
          </div>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { useSocket } from '../composables/useSocket'
import { initAgentTask, startAgentTask, createAgentTask } from '../api/agent'
import { createHistory, updateHistory } from '../api'

// 消息类型定义
interface Message {
  role: 'assistant' | 'system'
  content?: string
  thinking?: string
  thinkingExpanded?: boolean
  thinkingComplete?: boolean  // 思考是否完成
  toolCall?: {
    name: string
    input?: string
    expanded?: boolean  // 工具调用是否展开
  }
  toolResult?: {
    output?: string
    isError?: boolean
    expanded?: boolean  // 工具结果是否展开
  }
  icon?: string
  time: string
}

interface GeneratedPage {
  index: number
  title?: string
  content: string
  type?: string
}

const route = useRoute()
const router = useRouter()
const store = useGeneratorStore()
const { connect, waitForConnection, joinTask, leaveTask, confirmRoom, sendInstruction, on, off, connected } = useSocket()

// P4-1: 标记事件监听器是否已注册（防止重复绑定）
let eventListenersRegistered = false

// 输入模式状态
const topicInput = ref('')
const topicInputRef = ref<HTMLTextAreaElement | null>(null)
const isStarting = ref(false)
const isTaskStarted = ref(false)

// 快捷示例
const quickExamples = [
  '分享一个简单的早餐食谱',
  '推荐5个小众旅行目的地',
  '新手化妆入门教程',
  '居家健身动作分享'
]

// 状态
const topic = ref('')
const taskId = ref('')
const previewMode = ref<'outline' | 'preview'>('outline')
const additionalInput = ref('')
const currentThinking = ref('')
const currentResponse = ref('')  // 流式输出：当前正在生成的回复
const isGenerating = ref(false)
const isComplete = ref(false)
const hasError = ref(false)
const errorMessage = ref('')  // P1-1: 错误消息

// 消息列表
const messages = ref<Message[]>([])
const messagesContainer = ref<HTMLElement | null>(null)

// 当前正在构建的消息（用于流式接收）
const pendingMessage = ref<Message | null>(null)

// 生成结果
const generatedTitle = ref('')
const generatedSummary = ref('')
const generatedPages = ref<GeneratedPage[]>([])
const generatedImages = ref<{ url: string; index: number }[]>([])

// 计算属性
const statusClass = computed(() => {
  if (hasError.value) return 'error'
  if (isComplete.value) return 'complete'
  if (isGenerating.value) return 'active'
  return 'pending'
})

const statusMessage = computed(() => {
  if (hasError.value) return errorMessage.value || '创作过程中发生错误，请重试'
  if (isComplete.value) return '您的创作已完成！AI 已生成全部内容，请查看右侧预览。'
  if (isGenerating.value) return '您的任务已就绪，Agent 正在创作中，请耐心等待...'
  return '准备开始创作...'
})

const statusBadgeClass = computed(() => {
  if (hasError.value) return 'error'
  if (isComplete.value) return 'complete'
  if (isGenerating.value) return 'active'
  return 'pending'
})

const statusBadgeText = computed(() => {
  if (hasError.value) return 'AGENT ERROR'
  if (isComplete.value) return 'AGENT CREATION COMPLETE'
  if (isGenerating.value) return 'AGENT WORKING...'
  return 'AGENT READY'
})

const taskStatus = computed(() => {
  if (isComplete.value) return 'Completed'
  if (isGenerating.value) return 'In Progress'
  return 'Ready'
})

// 是否有预览数据
const hasPreviewData = computed(() => {
  return generatedTitle.value || generatedSummary.value || generatedPages.value.length > 0
})

// 方法
function formatTime() {
  return new Date().toLocaleTimeString('zh-CN', { hour12: false })
}

function addSystemMessage(content: string, icon?: string) {
  messages.value.push({
    role: 'system',
    content,
    icon,
    time: formatTime()
  })
  scrollToBottom()
}

function addAssistantMessage(msg: Partial<Message>) {
  messages.value.push({
    role: 'assistant',
    thinkingExpanded: false,
    time: formatTime(),
    ...msg
  } as Message)
  scrollToBottom()
}

function toggleThinking(index: number) {
  const msg = messages.value[index]
  if (msg && msg.thinking) {
    msg.thinkingExpanded = !msg.thinkingExpanded
  }
}

function toggleToolCall(index: number) {
  const msg = messages.value[index]
  if (msg && msg.toolCall) {
    msg.toolCall.expanded = !msg.toolCall.expanded
  }
}

function toggleToolResult(index: number) {
  const msg = messages.value[index]
  if (msg && msg.toolResult) {
    msg.toolResult.expanded = !msg.toolResult.expanded
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 保存历史记录
async function saveHistoryRecord() {
  // 检查是否有生成的内容
  if (!topic.value || generatedPages.value.length === 0) {
    console.warn('无法保存历史记录：缺少主题或大纲内容')
    return
  }

  try {
    // 构建大纲数据
    const outline = {
      raw: generatedPages.value.map(p => p.content).join('\n\n<page>\n\n'),
      pages: generatedPages.value.map((page, idx) => ({
        index: page.index ?? idx,
        type: page.type || (idx === 0 ? 'cover' : 'content'),
        content: page.content
      })),
      title: generatedTitle.value || topic.value,
      summary: generatedSummary.value
    }

    // 创建历史记录
    const result = await createHistory(topic.value, outline, taskId.value)

    if (result.success && result.record_id) {
      // 保存 recordId 到 store
      store.setRecordId(result.record_id)
      console.log('历史记录已创建:', result.record_id)

      // 如果有生成的图片，更新历史记录
      if (generatedImages.value.length > 0) {
        const imageFileNames = generatedImages.value.map(img => {
          // 从 URL 提取文件名
          const urlParts = img.url.split('/')
          return urlParts[urlParts.length - 1].split('?')[0]
        })

        await updateHistory(result.record_id, {
          images: {
            task_id: taskId.value,
            generated: imageFileNames
          },
          status: 'completed',
          thumbnail: imageFileNames[0] || null
        })
        console.log('历史记录已更新（包含图片）')
      }

      addSystemMessage('历史记录已保存', '💾')
    } else {
      console.error('创建历史记录失败:', result.error)
    }
  } catch (err: any) {
    console.error('保存历史记录异常:', err.message || err)
  }
}

// P4-1: 统一的事件监听器注册函数（防止重复绑定）
function registerEventListeners() {
  if (eventListenersRegistered) {
    console.log('[CreationCenter] 事件监听器已注册，跳过重复绑定')
    return
  }

  on('agent:progress', handleProgress)
  on('agent:thought', handleThought)
  on('agent:response', handleResponse)
  on('agent:tool_call', handleToolCall)
  on('agent:tool_result', handleToolResult)

  eventListenersRegistered = true
  console.log('[CreationCenter] 事件监听器已注册')
}

// WebSocket 事件处理
function handleProgress(data: any) {
  console.log('收到进度事件:', data)
  if (data.type === 'start') {
    isGenerating.value = true
    addSystemMessage(`开始创作: ${data.topic || topic.value}`, '🚀')
  } else if (data.type === 'complete') {
    isComplete.value = true
    isGenerating.value = false
    addSystemMessage('创作完成！', '✅')

    // 创建历史记录
    saveHistoryRecord()
  } else if (data.type === 'error') {
    // P1-1: 处理错误事件
    hasError.value = true
    isGenerating.value = false
    errorMessage.value = data.error || data.message || '创作过程中发生错误'
    addSystemMessage(`错误: ${errorMessage.value}`, '❌')
  } else if (data.type === 'retry') {
    // P2-3: 处理重试事件
    addSystemMessage(`${data.message || '正在重试...'}`, '🔄')
  } else if (data.type === 'cancelled') {
    hasError.value = true
    isGenerating.value = false
    errorMessage.value = '任务已取消'
    addSystemMessage('任务已取消', '🚫')
  }
}

function handleThought(data: any) {
  console.log('收到思考事件:', data)
  if (data.type === 'start') {
    // 开始新的思考
    currentThinking.value = ''
  } else if (data.type === 'token') {
    // 流式接收思考内容
    currentThinking.value += data.token
    scrollToBottom()
  } else if (data.type === 'end') {
    // 思考结束，保存到消息列表（默认折叠，标记为完成）
    if (currentThinking.value || data.content) {
      const thinkingContent = data.content || currentThinking.value
      addAssistantMessage({
        thinking: thinkingContent,
        thinkingExpanded: false,  // 默认折叠
        thinkingComplete: true    // 标记为完成
      })
    }
    currentThinking.value = ''
  }
}

// 流式输出：处理 AI 回复
function handleResponse(data: any) {
  console.log('收到回复事件:', data)

  if (data.type === 'token') {
    // 流式接收：逐字显示
    currentResponse.value = data.content || (currentResponse.value + data.token)
    scrollToBottom()
  } else if (data.type === 'end') {
    // 流式结束：保存完整消息
    if (currentResponse.value || data.content) {
      addAssistantMessage({
        content: data.content || currentResponse.value
      })
    }
    currentResponse.value = ''
  } else if (data.content) {
    // 非流式：直接显示完整内容
    addAssistantMessage({
      content: data.content
    })
  }
}

function handleToolCall(data: any) {
  console.log('收到工具调用事件:', data)
  addAssistantMessage({
    toolCall: {
      name: data.tool,
      input: data.input,
      expanded: false  // 默认折叠
    }
  })
}

function handleToolResult(data: any) {
  console.log('收到工具结果:', data)

  // 添加工具结果消息到界面
  addAssistantMessage({
    toolResult: {
      output: data.output || data.error,
      isError: data.type === 'error',
      expanded: false  // 默认折叠
    }
  })

  // P5-1: 优先使用完整的结构化数据
  const resultData = data.data || null

  const normalizeResult = (value: any) => {
    if (!value) return null
    if (typeof value === 'object') {
      // 已经是对象，直接返回
      return value
    }
    if (typeof value === 'string') {
      try {
        return JSON.parse(value)
      } catch {
        return null
      }
    }
    return null
  }

  const applyOutlineResult = (result: any) => {
    if (result?.pages && Array.isArray(result.pages)) {
      console.log('应用大纲结果:', result)
      generatedPages.value = result.pages
      generatedTitle.value = result.title || topic.value
      generatedSummary.value = result.summary || ''
      // 切换到大纲模式
      if (previewMode.value !== 'outline') {
        previewMode.value = 'outline'
      }
    }
  }

  const applyImagesResult = (result: any) => {
    if (result?.images && Array.isArray(result.images)) {
      console.log('应用图片结果:', result)
      generatedImages.value = result.images
      // 切换到预览模式
      if (previewMode.value !== 'preview') {
        previewMode.value = 'preview'
      }
    }
  }

  // 解析数据
  const normalized = normalizeResult(resultData) || normalizeResult(data.output)
  console.log('解析后的数据:', normalized)

  if (normalized) {
    // 检查是否是大纲结果
    if (normalized.pages) {
      applyOutlineResult(normalized)
    }
    // 检查是否是图片结果
    if (normalized.images) {
      applyImagesResult(normalized)
    }
  }
}


// P2-2: 发送追加指令
async function sendAdditionalInput() {
  if (!additionalInput.value.trim() || !taskId.value) return

  const instruction = additionalInput.value.trim()
  additionalInput.value = ''

  // 添加用户消息到界面
  addSystemMessage(`追加指令: ${instruction}`, '💬')

  try {
    await sendInstruction(taskId.value, instruction)
    addSystemMessage('指令已发送', '✅')
  } catch (err: any) {
    addSystemMessage(`发送失败: ${err.message}`, '❌')
  }
}

function downloadResult() {
  if (!isComplete.value) return
  // TODO: 实现下载功能
  router.push('/result')
}

// P1-1, P1-3, P2-1: 重构创作启动流程
async function handleStartCreation() {
  if (!topicInput.value.trim() || isStarting.value) return

  isStarting.value = true
  hasError.value = false
  errorMessage.value = ''

  try {
    // P1-3: 先调用后端初始化任务，获取 task_id
    const initResult = await initAgentTask({
      topic: topicInput.value.trim()
    })

    if (!initResult.success) {
      throw new Error(initResult.error || '初始化任务失败')
    }

    const newTaskId = initResult.task_id

    // 设置状态
    topic.value = topicInput.value.trim()
    taskId.value = newTaskId
    isTaskStarted.value = true

    // 保存到 store
    store.setTopic(topic.value)
    store.taskId = newTaskId

    // P2-1: 连接 WebSocket（返回 Promise）
    await connect()

    // P4-1: 注册事件监听（统一函数，防止重复）
    registerEventListeners()

    // P2-1: 使用 Promise 等待连接
    await waitForConnection()

    // P1-3: 加入任务房间（等待确认）
    await joinTask(taskId.value)
    console.log('已加入任务房间:', taskId.value)

    // P1-3: 确认房间加入成功
    await confirmRoom(taskId.value)

    // 启动任务执行
    const startResult = await startAgentTask(taskId.value)
    if (!startResult.success) {
      throw new Error(startResult.error || '启动任务失败')
    }

    addSystemMessage(`任务已启动: ${topic.value}`, '📝')

  } catch (err: any) {
    // P1-1: 错误捕获和展示
    hasError.value = true
    errorMessage.value = err.message || '创作任务启动失败，请重试'
    console.error('任务启动失败:', err)

    // 如果任务已经启动但出错，显示错误
    if (isTaskStarted.value) {
      addSystemMessage(`启动失败: ${errorMessage.value}`, '❌')
    }
  } finally {
    isStarting.value = false
  }
}

// 新建任务（重置状态）
function handleNewTask() {
  // 清理当前任务
  if (taskId.value) {
    leaveTask(taskId.value)
  }
  off('agent:progress', handleProgress)
  off('agent:thought', handleThought)
  off('agent:response', handleResponse)
  off('agent:tool_call', handleToolCall)
  off('agent:tool_result', handleToolResult)

  // 重置状态
  topic.value = ''
  taskId.value = ''
  topicInput.value = ''
  isTaskStarted.value = false
  isGenerating.value = false
  isComplete.value = false
  hasError.value = false
  errorMessage.value = ''  // P1-1: 重置错误消息
  currentThinking.value = ''
  currentResponse.value = ''  // 流式输出状态
  messages.value = []
  generatedTitle.value = ''
  generatedSummary.value = ''
  generatedPages.value = []
  generatedImages.value = []

  // 重置 store
  store.reset()
}

// 生命周期
onMounted(async () => {
  // 获取任务信息（从路由参数或 store）
  const queryTopic = route.query.topic as string
  const queryTaskId = route.query.taskId as string
  const isInitialized = route.query.initialized === 'true'  // P4-1: 检查任务是否已初始化

  if (queryTopic && queryTaskId && isInitialized) {
    // P4-1: 有路由参数且任务已初始化，启动任务
    topic.value = queryTopic
    taskId.value = queryTaskId
    isTaskStarted.value = true

    try {
      // P2-1: 连接 WebSocket
      await connect()

      // P4-1: 注册事件监听（统一函数，防止重复）
      registerEventListeners()

      // P2-1: 等待连接
      await waitForConnection()

      // P1-3: 加入任务房间
      await joinTask(taskId.value)
      console.log('已加入任务房间:', taskId.value)

      // P1-3: 确认房间
      await confirmRoom(taskId.value)

      // 启动任务执行
      const startResult = await startAgentTask(taskId.value)
      if (!startResult.success) {
        throw new Error(startResult.error || '启动任务失败')
      }

      addSystemMessage(`任务已启动: ${topic.value}`, '📝')

    } catch (err: any) {
      hasError.value = true
      errorMessage.value = err.message || '任务启动失败'
      addSystemMessage(`启动失败: ${errorMessage.value}`, '❌')
    }
  }
  // 否则显示输入界面，不需要做任何事
})

onUnmounted(() => {
  if (taskId.value) {
    leaveTask(taskId.value)
  }
  off('agent:progress', handleProgress)
  off('agent:thought', handleThought)
  off('agent:response', handleResponse)
  off('agent:tool_call', handleToolCall)
  off('agent:tool_result', handleToolResult)
})
</script>

<style scoped>
.creation-center {
  display: flex;
  height: 100vh;
  background: #f8f9fa;
  color: var(--text-main, #1a1a2e);
}

/* ========== 输入模式样式 ========== */
.input-mode {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background: linear-gradient(135deg, #fff 0%, #f8f9fa 100%);
}

.input-hero {
  text-align: center;
  margin-bottom: 40px;
}

.brand-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(255, 36, 66, 0.08);
  color: var(--primary, #FF2442);
  border-radius: 100px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 24px;
}

.hero-title {
  font-size: 42px;
  font-weight: 700;
  color: var(--text-main, #1a1a2e);
  margin-bottom: 12px;
}

.hero-subtitle {
  font-size: 16px;
  color: #666;
}

.topic-input-card {
  width: 100%;
  max-width: 640px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
  padding: 24px;
  margin-bottom: 24px;
}

.input-wrapper textarea {
  width: 100%;
  border: none;
  outline: none;
  font-size: 16px;
  line-height: 1.6;
  resize: none;
  font-family: inherit;
  color: var(--text-main, #1a1a2e);
}

.input-wrapper textarea::placeholder {
  color: #bbb;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.input-tips {
  font-size: 12px;
  color: #999;
}

.start-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 28px;
  background: var(--primary, #FF2442);
  color: #fff;
  border: none;
  border-radius: 100px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.start-btn:hover:not(:disabled) {
  background: #e6203b;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(255, 36, 66, 0.3);
}

.start-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.quick-examples {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  max-width: 640px;
}

.examples-label {
  font-size: 13px;
  color: #999;
}

.example-tag {
  padding: 6px 14px;
  background: #fff;
  border: 1px solid #eee;
  border-radius: 100px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.example-tag:hover {
  border-color: var(--primary, #FF2442);
  color: var(--primary, #FF2442);
  background: rgba(255, 36, 66, 0.04);
}

/* ========== 执行面板样式 ========== */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.panel-header .panel-title {
  margin-bottom: 0;
}

.new-task-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 8px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
}

.new-task-btn:hover {
  background: var(--primary, #FF2442);
  border-color: var(--primary, #FF2442);
  color: #fff;
}

/* 左侧执行面板 */
.execution-panel {
  width: 480px;
  min-width: 420px;
  background: #fff;
  border-right: 1px solid #eee;
  display: flex;
  flex-direction: column;
  padding: 24px;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.03);
}

.panel-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 24px;
  color: var(--text-main, #1a1a2e);
}

.task-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #fafafa;
  border-radius: 12px;
  margin-bottom: 20px;
  border: 1px solid #f0f0f0;
}

.task-icon {
  width: 40px;
  height: 40px;
  background: rgba(255, 36, 66, 0.08);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary, #FF2442);
}

.task-details {
  flex: 1;
  overflow: hidden;
}

.task-name {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-main, #1a1a2e);
}

.task-meta {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.status-card {
  padding: 16px;
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 12px;
  margin-bottom: 20px;
}

.status-card.active {
  border-color: var(--primary, #FF2442);
  background: rgba(255, 36, 66, 0.04);
}

.status-card.complete {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.04);
}

.status-card.error {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.04);
}

.status-message {
  font-size: 14px;
  line-height: 1.6;
  color: #666;
}

/* 消息容器 */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 消息项 */
.message-item {
  display: flex;
  gap: 12px;
}

.message-item.assistant {
  align-items: flex-start;
}

.message-avatar {
  width: 32px;
  height: 32px;
  background: rgba(255, 36, 66, 0.1);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.message-body {
  flex: 1;
  min-width: 0;
}

.message-content {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-main, #1a1a2e);
  background: #f8f9fa;
  padding: 12px 16px;
  border-radius: 12px;
  border-top-left-radius: 4px;
}

/* 流式输出样式 */
.message-content.streaming {
  border-left: 3px solid var(--primary, #FF2442);
  background: linear-gradient(135deg, rgba(255, 36, 66, 0.02), #f8f9fa);
}

.typing-cursor {
  display: inline-block;
  color: var(--primary, #FF2442);
  animation: blink-cursor 0.8s infinite;
  font-weight: bold;
}

@keyframes blink-cursor {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.message-time {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
}

/* 思考块 */
.thinking-block {
  margin-bottom: 8px;
}

.thinking-block.complete .thinking-toggle {
  background: rgba(34, 197, 94, 0.06);
}

.thinking-block.complete .thinking-label {
  color: #22c55e;
}

.thinking-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: rgba(255, 36, 66, 0.06);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #666;
  transition: all 0.2s;
}

.thinking-toggle:hover {
  background: rgba(255, 36, 66, 0.1);
}

.thinking-block.complete .thinking-toggle:hover {
  background: rgba(34, 197, 94, 0.1);
}

.thinking-toggle svg {
  transition: transform 0.2s;
  color: var(--primary, #FF2442);
  flex-shrink: 0;
}

.thinking-block.complete .thinking-toggle svg {
  color: #22c55e;
}

.thinking-toggle.expanded svg {
  transform: rotate(90deg);
}

.thinking-label {
  color: var(--primary, #FF2442);
  font-weight: 500;
  white-space: nowrap;
}

.thinking-preview {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #999;
  font-size: 12px;
}

.thinking-dots {
  color: var(--primary, #FF2442);
  animation: blink 1.5s infinite;
}

.thinking-full {
  margin-top: 8px;
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #eee;
  max-height: 60vh;
  overflow-y: auto;
}

.thinking-full pre {
  font-size: 12px;
  line-height: 1.5;
  color: #666;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  font-family: inherit;
}

.thinking-full.streaming {
  border-color: rgba(255, 36, 66, 0.3);
  background: rgba(255, 36, 66, 0.02);
}

.thinking-block.active .thinking-toggle {
  background: rgba(255, 36, 66, 0.1);
}

/* 工具调用块 */
.tool-call-block {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 500;
  color: #0369a1;
  cursor: pointer;
  transition: background 0.2s;
}

.tool-call-header:hover {
  background: rgba(14, 165, 233, 0.08);
}

.tool-call-header .expand-icon {
  transition: transform 0.2s;
  color: #0369a1;
  flex-shrink: 0;
}

.tool-call-block.expanded .tool-call-header .expand-icon {
  transform: rotate(90deg);
}

.tool-name {
  font-weight: 600;
}

.tool-status {
  margin-left: auto;
  font-size: 11px;
  color: #0ea5e9;
  font-weight: normal;
}

.tool-icon {
  font-size: 14px;
}

.tool-call-details {
  border-top: 1px solid #bae6fd;
  padding: 12px;
  background: #fff;
}

.tool-call-input {
  font-size: 12px;
  color: #666;
}

.tool-call-input .detail-label {
  font-weight: 500;
  color: #0369a1;
  margin-bottom: 6px;
}

.tool-call-input pre {
  margin: 0;
  padding: 8px;
  background: #f8fafc;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 50vh;
  overflow-y: auto;
}

/* 工具结果块 */
.tool-result-block {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}

.tool-result-block.error {
  background: #fef2f2;
  border-color: #fecaca;
}

.tool-result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  font-size: 13px;
  font-weight: 500;
  color: #15803d;
  cursor: pointer;
  transition: background 0.2s;
}

.tool-result-header:hover {
  background: rgba(34, 197, 94, 0.08);
}

.tool-result-block.error .tool-result-header {
  color: #dc2626;
}

.tool-result-block.error .tool-result-header:hover {
  background: rgba(239, 68, 68, 0.08);
}

.tool-result-header .expand-icon {
  transition: transform 0.2s;
  color: #15803d;
  flex-shrink: 0;
}

.tool-result-block.error .tool-result-header .expand-icon {
  color: #dc2626;
}

.tool-result-block.expanded .tool-result-header .expand-icon {
  transform: rotate(90deg);
}

.tool-result-details {
  border-top: 1px solid #bbf7d0;
  background: #fff;
}

.tool-result-block.error .tool-result-details {
  border-top-color: #fecaca;
}

.tool-result-content {
  padding: 12px;
}

.tool-result-content pre {
  margin: 0;
  padding: 8px;
  background: #f8fafc;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', monospace;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 60vh;
  overflow-y: auto;
  color: #666;
}

/* 系统消息 */
.system-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 8px;
  font-size: 13px;
  color: #666;
}

.system-icon {
  font-size: 14px;
}

.system-text {
  flex: 1;
}

.system-time {
  font-size: 11px;
  color: #999;
}

/* 输入框 */
.input-section {
  display: flex;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid #eee;
  margin-top: auto;
}

.input-section input {
  flex: 1;
  background: #fafafa;
  border: 1px solid #eee;
  border-radius: 24px;
  padding: 12px 20px;
  color: var(--text-main, #1a1a2e);
  font-size: 14px;
}

.input-section input:focus {
  outline: none;
  border-color: var(--primary, #FF2442);
}

.input-section input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.send-btn {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--primary, #FF2442);
  border: none;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #e6203b;
  transform: scale(1.05);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 右侧预览面板 */
.preview-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid #eee;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1px;
  color: #999;
}

.status-badge .status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
}

.status-badge.active .status-dot {
  background: var(--primary, #FF2442);
  animation: pulse 1.5s infinite;
}

.status-badge.active {
  color: var(--primary, #FF2442);
}

.status-badge.complete {
  color: #22c55e;
}

.status-badge.complete .status-dot {
  background: #22c55e;
}

.status-badge.error {
  color: #ef4444;
}

.status-badge.error .status-dot {
  background: #ef4444;
}

.preview-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  padding: 8px 16px;
  background: transparent;
  border: 1px solid #ddd;
  border-radius: 8px;
  color: #666;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.action-btn:hover {
  border-color: var(--primary, #FF2442);
  color: var(--primary, #FF2442);
}

.action-btn.active {
  background: var(--primary, #FF2442);
  border-color: var(--primary, #FF2442);
  color: #fff;
}

.action-btn.primary {
  background: var(--primary, #FF2442);
  border-color: var(--primary, #FF2442);
  color: #fff;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 预览内容 */
.preview-content {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
  background: #fafafa;
}

.outline-view {
  max-width: 800px;
  margin: 0 auto;
}

/* 预览状态横幅 */
.preview-status-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(255, 36, 66, 0.08);
  border: 1px solid rgba(255, 36, 66, 0.2);
  border-radius: 8px;
  margin-bottom: 24px;
  font-size: 13px;
  color: var(--primary, #FF2442);
}

.banner-icon {
  display: flex;
  align-items: center;
}

.mini-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 36, 66, 0.2);
  border-top-color: var(--primary, #FF2442);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.content-title {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 32px;
  line-height: 1.3;
  color: var(--text-main, #1a1a2e);
}

.content-section {
  margin-bottom: 32px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--primary, #FF2442);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--primary, #FF2442);
  display: inline-block;
}

.section-text {
  font-size: 15px;
  line-height: 1.8;
  color: #666;
}

/* 页面列表 */
.pages-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-item {
  display: flex;
  gap: 16px;
  padding: 20px;
  background: #fff;
  border-radius: 12px;
  border-left: 3px solid var(--primary, #FF2442);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: all 0.2s;
}

.page-item.generating {
  opacity: 0.8;
  border-left-style: dashed;
}

.page-number {
  width: 32px;
  height: 32px;
  background: var(--primary, #FF2442);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
  color: #fff;
}

.page-content {
  flex: 1;
}

.page-title {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--text-main, #1a1a2e);
}

.page-text {
  font-size: 14px;
  color: #888;
  line-height: 1.6;
}

/* 图片网格 */
.images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 20px;
}

.image-card {
  position: relative;
  aspect-ratio: 3/4;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transition: all 0.2s;
}

.image-card.generating {
  opacity: 0.8;
}

.image-card img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px;
  background: linear-gradient(transparent, rgba(0,0,0,0.6));
  font-size: 12px;
  color: #fff;
}

/* 空状态 */
.empty-state,
.generating-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #999;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.generating-tip {
  font-size: 12px;
  color: #bbb;
  margin-top: 8px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #eee;
  border-top-color: var(--primary, #FF2442);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* 滚动条样式 */
.messages-container::-webkit-scrollbar,
.preview-content::-webkit-scrollbar,
.thinking-full::-webkit-scrollbar,
.tool-result-content::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-track,
.preview-content::-webkit-scrollbar-track,
.thinking-full::-webkit-scrollbar-track,
.tool-result-content::-webkit-scrollbar-track {
  background: transparent;
}

.messages-container::-webkit-scrollbar-thumb,
.preview-content::-webkit-scrollbar-thumb,
.thinking-full::-webkit-scrollbar-thumb,
.tool-result-content::-webkit-scrollbar-thumb {
  background: #ddd;
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover,
.preview-content::-webkit-scrollbar-thumb:hover,
.thinking-full::-webkit-scrollbar-thumb:hover,
.tool-result-content::-webkit-scrollbar-thumb:hover {
  background: #ccc;
}
</style>
