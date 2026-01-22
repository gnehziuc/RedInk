<template>
  <!-- 历史记录卡片 -->
  <div class="gallery-card" :class="{ 'is-selected': selected }" @click="handleCardClick">
    <!-- 选择框 -->
    <div v-if="selectable" class="select-checkbox" :class="{ checked: selected }" @click.stop="$emit('select', record.id)">
      <svg v-if="selected" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <polyline points="20 6 9 17 4 12" stroke="white" stroke-width="3" fill="none"></polyline>
      </svg>
    </div>

    <!-- 封面区域 -->
    <div class="card-cover" @click="!selectable && $emit('preview', record.id)">
      <img
        v-if="record.thumbnail && record.task_id"
        :src="`/api/images/${record.task_id}/${record.thumbnail}`"
        alt="cover"
        loading="lazy"
        decoding="async"
      />
      <div v-else class="cover-placeholder">
        <span>{{ record.title.charAt(0) }}</span>
      </div>

      <!-- 悬浮操作按钮 -->
      <div v-if="!selectable" class="card-overlay">
        <button class="overlay-btn" @click.stop="$emit('preview', record.id)">
          预览
        </button>
        <button class="overlay-btn primary" @click.stop="$emit('edit', record.id)">
          编辑
        </button>
      </div>

      <!-- 状态标识 -->
      <div class="status-badge" :class="record.status">
        {{ statusText }}
      </div>
    </div>

    <!-- 底部信息 -->
    <div class="card-footer">
      <div class="card-title" :title="record.title">{{ record.title }}</div>
      <div class="card-meta">
        <span>{{ record.page_count }}P</span>
        <span class="dot">·</span>
        <span>{{ formattedDate }}</span>

        <div class="more-actions-wrapper">
          <button class="more-btn" @click.stop="$emit('delete', record)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * 历史记录卡片组件
 *
 * 展示单个历史记录的封面、标题、状态等信息
 * 支持预览、编辑、删除操作
 */

// 定义记录类型
interface Record {
  id: string
  title: string
  status: 'draft' | 'completed' | 'generating'
  page_count: number
  updated_at: string
  thumbnail?: string
  task_id?: string
}

// 定义 Props
const props = defineProps<{
  record: Record
  selectable?: boolean
  selected?: boolean
}>()

// 定义 Emits
const emit = defineEmits<{
  (e: 'preview', id: string): void
  (e: 'edit', id: string): void
  (e: 'delete', record: Record): void
  (e: 'select', id: string): void
}>()

/**
 * 卡片点击处理
 */
function handleCardClick() {
  if (props.selectable) {
    emit('select', props.record.id)
  }
}

/**
 * 获取状态文本
 */
const statusText = computed(() => {
  const map: Record<string, string> = {
    draft: '草稿',
    completed: '已完成',
    generating: '生成中'
  }
  return map[props.record.status] || props.record.status
})

/**
 * 格式化日期
 */
const formattedDate = computed(() => {
  const d = new Date(props.record.updated_at)
  return `${d.getMonth() + 1}/${d.getDate()}`
})
</script>

<style scoped>
/* 卡片容器 */
.gallery-card {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(0, 0, 0, 0.04);
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  will-change: transform;
  contain: layout style paint;
}

.gallery-card:hover {
  transform: translateY(-4px) translateZ(0);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08);
}

/* 封面区域 */
.card-cover {
  aspect-ratio: 3/4;
  background: #f7f7f7;
  position: relative;
  overflow: hidden;
  cursor: pointer;
}

.card-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: transform;
  backface-visibility: hidden;
}

.gallery-card:hover .card-cover img {
  transform: scale(1.05) translateZ(0);
}

/* 封面占位符 */
.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
  color: #e0e0e0;
  font-weight: 800;
  background: #fafafa;
}

/* 悬浮遮罩层 */
.card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  opacity: 0;
  transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(2px);
  pointer-events: none;
  will-change: opacity;
}

.gallery-card:hover .card-overlay {
  opacity: 1;
  pointer-events: auto;
}

/* 遮罩层按钮 */
.overlay-btn {
  padding: 8px 24px;
  border-radius: 100px;
  border: 1px solid rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.2);
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s, transform 0.1s;
  will-change: transform;
}

.overlay-btn:hover {
  background: white;
  color: var(--text-main, #1a1a1a);
  transform: translateY(-2px);
}

.overlay-btn.primary {
  background: var(--primary, #ff2442);
  border-color: var(--primary, #ff2442);
}

.overlay-btn.primary:hover {
  background: var(--primary-hover, #e61e3a);
  color: white;
}

/* 状态标识 */
.status-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  backdrop-filter: blur(4px);
}

.status-badge.completed {
  background: rgba(82, 196, 26, 0.9);
}

.status-badge.draft {
  background: rgba(0, 0, 0, 0.5);
}

.status-badge.generating {
  background: rgba(24, 144, 255, 0.9);
}

/* 底部区域 */
.card-footer {
  padding: 16px;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-main, #1a1a1a);
}

.card-meta {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: var(--text-sub, #666);
}

.dot {
  margin: 0 6px;
}

/* 更多操作 */
.more-actions-wrapper {
  margin-left: auto;
}

.more-btn {
  background: none;
  border: none;
  color: var(--text-placeholder, #ccc);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: background-color 0.2s, color 0.2s;
}

.more-btn:hover {
  background: #fee;
  color: #ff4d4f;
}

/* 选择模式 */
.gallery-card.is-selected {
  border-color: var(--primary, #ff2442);
  box-shadow: 0 0 0 2px var(--primary-light, rgba(255, 36, 66, 0.2));
}

.select-checkbox {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  border: 2px solid #ddd;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.select-checkbox:hover {
  border-color: var(--primary, #ff2442);
}

.select-checkbox.checked {
  background: var(--primary, #ff2442);
  border-color: var(--primary, #ff2442);
}
</style>
