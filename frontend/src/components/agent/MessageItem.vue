<template>
  <div class="message-item" :class="message.role">
    <template v-if="message.role === 'assistant'">
      <div class="message-avatar"><span>🤖</span></div>
      <div class="message-body">
        <ThinkingBlock v-if="message.thinking" :thinking="message.thinking" :complete="message.thinkingComplete" />
        <div v-if="message.content" class="message-content">{{ message.content }}</div>
        <ToolCallBlock v-if="message.toolCall" :tool-call="message.toolCall" />
        <ToolResultBlock v-if="message.toolResult" :tool-result="message.toolResult" />
        <div class="message-time">{{ message.time }}</div>
      </div>
    </template>
    <template v-else-if="message.role === 'system'">
      <div class="system-message">
        <span class="system-icon">{{ message.icon || '📌' }}</span>
        <span class="system-text">{{ message.content }}</span>
        <span class="system-time">{{ message.time }}</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { defineProps } from 'vue'
import ThinkingBlock from './ThinkingBlock.vue'
import ToolCallBlock from './ToolCallBlock.vue'
import ToolResultBlock from './ToolResultBlock.vue'

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

defineProps<{ message: Message }>()
</script>

<style scoped>
.message-item { display: flex; gap: 12px; }
.message-avatar { width: 32px; height: 32px; background: rgba(255, 36, 66, 0.1); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; }
.message-body { flex: 1; min-width: 0; }
.message-content { font-size: 14px; line-height: 1.6; background: #f8f9fa; padding: 12px 16px; border-radius: 12px; border-top-left-radius: 4px; }
.message-time { font-size: 11px; color: #999; margin-top: 4px; }
.system-message { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #fafafa; border-radius: 8px; font-size: 13px; color: #666; }
</style>
