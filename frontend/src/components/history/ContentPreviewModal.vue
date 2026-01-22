<template>
  <!-- 内容预览模态框 - 小红书风格 -->
  <div v-if="visible && record" class="preview-modal" @click="$emit('close')">
    <div class="preview-container" @click.stop>
      <!-- 关闭按钮 -->
      <button class="close-btn" @click="$emit('close')">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>

      <!-- 图片轮播区域 -->
      <div class="carousel-section">
        <div 
          class="carousel-track" 
          ref="carouselRef"
          @scroll="onCarouselScroll"
        >
          <div 
            v-for="(img, idx) in record.images.generated" 
            :key="idx"
            class="carousel-slide"
          >
            <img 
              v-if="img"
              :src="`/api/images/${record.images.task_id}/${img}?thumbnail=false`"
              loading="lazy"
              alt=""
            />
            <div v-else class="slide-placeholder">
              <span>图片生成中...</span>
            </div>
          </div>
        </div>
        
        <!-- 页码指示器 -->
        <div class="page-indicator">
          {{ currentIndex + 1 }}/{{ record.images.generated.length }}
        </div>

        <!-- 左右切换按钮 -->
        <button 
          v-if="currentIndex > 0"
          class="nav-btn nav-prev" 
          @click="slideTo(currentIndex - 1)"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
        </button>
        <button 
          v-if="currentIndex < record.images.generated.length - 1"
          class="nav-btn nav-next" 
          @click="slideTo(currentIndex + 1)"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
        </button>
      </div>

      <!-- 文字内容区域 -->
      <div class="content-section">
        <!-- 标题 -->
        <h2 class="content-title">{{ record.title }}</h2>
        
        <!-- 页面类型标签 -->
        <div class="page-type-tag" :class="currentPage?.type || 'content'">
          {{ getTypeLabel(currentPage?.type) }}
        </div>

        <!-- 文字内容 -->
        <div class="content-text">
          <p v-html="formatContent(currentPage?.content || '')"></p>
        </div>

        <!-- 底部操作栏 -->
        <div class="action-bar">
          <button 
            class="action-btn" 
            @click="$emit('download', record.images.generated[currentIndex], currentIndex)"
            :disabled="!record.images.generated[currentIndex]"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            下载图片
          </button>
          <button 
            class="action-btn" 
            @click="$emit('regenerate', currentIndex)"
            :disabled="regeneratingImages.has(currentIndex)"
          >
            <svg 
              width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              :class="{ 'spinning': regeneratingImages.has(currentIndex) }"
            >
              <path d="M23 4v6h-6"></path>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
            </svg>
            {{ regeneratingImages.has(currentIndex) ? '生成中...' : '重新生成' }}
          </button>
          <button class="action-btn" @click="$emit('downloadAll')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            打包下载
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'

interface ViewingRecord {
  id: string
  title: string
  updated_at: string
  outline: {
    raw: string
    pages: Array<{ type: string; content: string }>
  }
  images: {
    task_id: string
    generated: string[]
  }
}

const props = defineProps<{
  visible: boolean
  record: ViewingRecord | null
  regeneratingImages: Set<number>
}>()

defineEmits<{
  (e: 'close'): void
  (e: 'download', filename: string, index: number): void
  (e: 'downloadAll'): void
  (e: 'regenerate', index: number): void
}>()

const carouselRef = ref<HTMLElement | null>(null)
const currentIndex = ref(0)

// 当前页面内容
const currentPage = computed(() => {
  if (!props.record?.outline?.pages) return null
  return props.record.outline.pages[currentIndex.value]
})

// 滚动监听
function onCarouselScroll() {
  if (!carouselRef.value) return
  const scrollLeft = carouselRef.value.scrollLeft
  const slideWidth = carouselRef.value.offsetWidth
  const newIndex = Math.round(scrollLeft / slideWidth)
  if (newIndex !== currentIndex.value && newIndex >= 0) {
    currentIndex.value = newIndex
  }
}

// 滑动到指定页
function slideTo(index: number) {
  if (!carouselRef.value) return
  const slideWidth = carouselRef.value.offsetWidth
  carouselRef.value.scrollTo({
    left: slideWidth * index,
    behavior: 'smooth'
  })
}

// 获取页面类型标签
function getTypeLabel(type: string | undefined): string {
  const labels: Record<string, string> = {
    cover: '封面',
    content: '内容',
    summary: '总结'
  }
  return labels[type || 'content'] || '内容'
}

// 格式化内容（保留换行）
function formatContent(content: string): string {
  return content
    .replace(/\[封面\]|\[内容\]|\[总结\]/g, '')
    .trim()
    .replace(/\n/g, '<br>')
}

// 重置索引
watch(() => props.visible, (visible) => {
  if (visible) {
    currentIndex.value = 0
    nextTick(() => {
      if (carouselRef.value) {
        carouselRef.value.scrollLeft = 0
      }
    })
  }
})
</script>

<style scoped>
/* 模态框遮罩 */
.preview-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.95);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

/* 预览容器 */
.preview-container {
  position: relative;
  width: 100%;
  max-width: 420px;
  height: 90vh;
  max-height: 800px;
  background: #fff;
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 关闭按钮 */
.close-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.5);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.close-btn:hover {
  background: rgba(0, 0, 0, 0.7);
}

/* 轮播区域 */
.carousel-section {
  position: relative;
  flex-shrink: 0;
  background: #f5f5f5;
}

.carousel-track {
  display: flex;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.carousel-track::-webkit-scrollbar {
  display: none;
}

.carousel-slide {
  flex-shrink: 0;
  width: 100%;
  aspect-ratio: 3/4;
  scroll-snap-align: start;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
}

.carousel-slide img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #f0f0f0;
}

.slide-placeholder {
  color: #999;
  font-size: 14px;
}

/* 页码指示器 */
.page-indicator {
  position: absolute;
  top: 12px;
  right: 56px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
}

/* 导航按钮 */
.nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 40px;
  height: 40px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  color: #333;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.nav-btn:hover {
  background: white;
  transform: translateY(-50%) scale(1.1);
}

.nav-prev {
  left: 12px;
}

.nav-next {
  right: 12px;
}

/* 内容区域 */
.content-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px 20px;
  overflow: hidden;
}

.content-title {
  flex-shrink: 0;
  font-size: 17px;
  font-weight: 600;
  color: #1a1a1a;
  margin: 0 0 12px 0;
  line-height: 1.4;
  word-break: break-word;
}

/* 页面类型标签 */
.page-type-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 12px;
}

.page-type-tag.cover {
  background: #fff0f0;
  color: #ff2442;
}

.page-type-tag.content {
  background: #f0f5ff;
  color: #1677ff;
}

.page-type-tag.summary {
  background: #f0fff4;
  color: #52c41a;
}

/* 文字内容 */
.content-text {
  flex: 1;
  overflow-y: auto;
  font-size: 15px;
  line-height: 1.7;
  color: #333;
}

.content-text p {
  margin: 0;
}

/* 操作栏 */
.action-bar {
  display: flex;
  gap: 10px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
  margin-top: 16px;
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: white;
  color: #333;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  border-color: var(--primary, #ff2442);
  color: var(--primary, #ff2442);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 旋转动画 */
.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 响应式 */
@media (max-width: 480px) {
  .preview-container {
    max-width: 100%;
    height: 100vh;
    max-height: none;
    border-radius: 0;
  }

  .action-bar {
    flex-wrap: wrap;
  }

  .action-btn {
    font-size: 12px;
    padding: 8px 10px;
  }
}
</style>
