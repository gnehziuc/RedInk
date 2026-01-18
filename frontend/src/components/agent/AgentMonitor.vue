<script setup lang="ts">
/**
 * Agent 监控面板 - 实时展示 Agent 思考过程和工具调用
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useSocket } from '@/composables/useSocket'

interface AgentEvent {
  id: string
  type: 'thought' | 'tool_call' | 'tool_result' | 'progress'
  timestamp: Date
  data: any
}

const props = defineProps<{
  taskId: string
  visible?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'pause'): void
}>()

const { connect, joinTask, leaveTask, on, off, connected } = useSocket()

const events = ref<AgentEvent[]>([])
const currentThought = ref('')
const isThinking = ref(false)
const isPaused = ref(false)
const isCollapsed = ref(false)

// 事件处理
const handleThought = (data: any) => {
  if (data.type === 'start') {
    isThinking.value = true
    currentThought.value = ''
  } else if (data.type === 'token') {
    currentThought.value += data.token
  } else if (data.type === 'end') {
    isThinking.value = false
    if (currentThought.value) {
      addEvent('thought', { content: currentThought.value })
    }
    currentThought.value = ''
  }
}

const handleToolCall = (data: any) => {
  addEvent('tool_call', data)
}

const handleToolResult = (data: any) => {
  addEvent('tool_result', data)
}

const handleProgress = (data: any) => {
  addEvent('progress', data)
}

const addEvent = (type: AgentEvent['type'], data: any) => {
  events.value.push({
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    type,
    timestamp: new Date(),
    data
  })
  // 保持最近 50 条事件
  if (events.value.length > 50) {
    events.value = events.value.slice(-50)
  }
}

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
}

const togglePause = () => {
  isPaused.value = !isPaused.value
  emit('pause')
}

const clearEvents = () => {
  events.value = []
}

// 格式化时间
const formatTime = (date: Date) => {
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

// 获取事件图标
const getEventIcon = (type: string) => {
  switch (type) {
    case 'thought': return '💭'
    case 'tool_call': return '🔧'
    case 'tool_result': return '📋'
    case 'progress': return '⏳'
    default: return '📌'
  }
}

// 监听 taskId 变化
watch(() => props.taskId, (newId, oldId) => {
  if (oldId) leaveTask(oldId)
  if (newId) joinTask(newId)
})

onMounted(() => {
  connect()
  if (props.taskId) {
    joinTask(props.taskId)
  }

  on('agent:thought', handleThought)
  on('agent:tool_call', handleToolCall)
  on('agent:tool_result', handleToolResult)
  on('agent:progress', handleProgress)
})

onUnmounted(() => {
  if (props.taskId) {
    leaveTask(props.taskId)
  }
  off('agent:thought', handleThought)
  off('agent:tool_call', handleToolCall)
  off('agent:tool_result', handleToolResult)
  off('agent:progress', handleProgress)
})
</script>

<template>
  <div
    v-if="visible"
    class="agent-monitor"
    :class="{ collapsed: isCollapsed }"
  >
    <!-- 标题栏 -->
    <div class="monitor-header" @click="toggleCollapse">
      <div class="header-left">
        <span class="status-dot" :class="{ connected }"></span>
        <span class="title">Agent 监控</span>
        <span v-if="isThinking" class="thinking-indicator">思考中...</span>
      </div>
      <div class="header-actions">
        <button
          class="action-btn"
          @click.stop="togglePause"
          :title="isPaused ? '继续' : '暂停'"
        >
          {{ isPaused ? '▶' : '⏸' }}
        </button>
        <button
          class="action-btn"
          @click.stop="clearEvents"
          title="清空"
        >
          🗑
        </button>
        <button
          class="action-btn"
          @click.stop="$emit('close')"
          title="关闭"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- 内容区域 -->
    <div v-show="!isCollapsed" class="monitor-content">
      <!-- 当前思考 -->
      <div v-if="currentThought" class="current-thought">
        <span class="thought-label">💭 正在思考:</span>
        <div class="thought-text">{{ currentThought }}</div>
      </div>

      <!-- 事件列表 -->
      <div class="events-list">
        <div
          v-for="event in events"
          :key="event.id"
          class="event-item"
          :class="event.type"
        >
          <span class="event-icon">{{ getEventIcon(event.type) }}</span>
          <span class="event-time">{{ formatTime(event.timestamp) }}</span>
          <div class="event-content">
            <template v-if="event.type === 'thought'">
              {{ event.data.content }}
            </template>
            <template v-else-if="event.type === 'tool_call'">
              <strong>{{ event.data.tool }}</strong>
              <code v-if="event.data.input">{{ event.data.input }}</code>
            </template>
            <template v-else-if="event.type === 'tool_result'">
              <span :class="{ error: event.data.type === 'error' }">
                {{ event.data.output || event.data.error }}
              </span>
            </template>
            <template v-else>
              {{ event.data.message || JSON.stringify(event.data) }}
            </template>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="events.length === 0 && !currentThought" class="empty-state">
        等待 Agent 开始工作...
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-monitor {
  position: fixed;
  right: 20px;
  top: 80px;
  width: 360px;
  max-height: 500px;
  background: var(--bg-secondary, #1a1a2e);
  border: 1px solid var(--border-color, #333);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s ease;
}

.agent-monitor.collapsed {
  max-height: 48px;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--bg-tertiary, #252540);
  cursor: pointer;
  user-select: none;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #666;
}

.status-dot.connected {
  background: #4ade80;
  box-shadow: 0 0 8px #4ade80;
}

.title {
  font-weight: 600;
  color: var(--text-primary, #fff);
}

.thinking-indicator {
  font-size: 12px;
  color: var(--text-secondary, #888);
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.header-actions {
  display: flex;
  gap: 4px;
}

.action-btn {
  background: transparent;
  border: none;
  padding: 4px 8px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 14px;
  transition: background 0.2s;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.monitor-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.current-thought {
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.thought-label {
  font-size: 12px;
  color: var(--text-secondary, #888);
  display: block;
  margin-bottom: 4px;
}

.thought-text {
  color: var(--text-primary, #fff);
  font-size: 14px;
  line-height: 1.5;
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.event-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 6px;
  font-size: 13px;
}

.event-item.tool_call {
  background: rgba(59, 130, 246, 0.1);
}

.event-item.tool_result {
  background: rgba(34, 197, 94, 0.1);
}

.event-icon {
  flex-shrink: 0;
}

.event-time {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--text-secondary, #666);
}

.event-content {
  flex: 1;
  color: var(--text-primary, #ddd);
  word-break: break-word;
}

.event-content code {
  display: block;
  margin-top: 4px;
  padding: 4px 8px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
}

.event-content .error {
  color: #f87171;
}

.empty-state {
  text-align: center;
  color: var(--text-secondary, #666);
  padding: 40px 20px;
}
</style>
