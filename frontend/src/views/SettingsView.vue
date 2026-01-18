<template>
  <div class="container">
    <div class="page-header">
      <h1 class="page-title">系统设置</h1>
      <p class="page-subtitle">配置文本生成和图片生成的 API 服务</p>
    </div>

    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p>加载配置中...</p>
    </div>

    <div v-else class="settings-container">
      <!-- Agent 模式设置 -->
      <div class="card">
        <div class="section-header">
          <div>
            <h2 class="section-title">创作引擎</h2>
            <p class="section-desc">选择创作模式</p>
          </div>
        </div>
        <div class="agent-mode-toggle">
          <label class="toggle-label">
            <input
              type="checkbox"
              :checked="generatorStore.useAgentMode"
              @change="toggleAgentMode"
            />
            <span class="toggle-switch"></span>
            <span class="toggle-text">
              {{ generatorStore.useAgentMode ? '智能 Agent 模式（实验性）' : '传统模式' }}
            </span>
          </label>
          <p class="toggle-desc">
            {{ generatorStore.useAgentMode
              ? 'Agent 模式使用 LangChain 智能体自动规划和执行创作流程，支持实时监控思考过程'
              : '传统模式按步骤生成大纲和图片，流程可控'
            }}
          </p>
        </div>
      </div>

      <!-- 文本生成配置 -->
      <div class="card">
        <div class="section-header">
          <div>
            <h2 class="section-title">文本生成配置</h2>
            <p class="section-desc">用于生成小红书图文大纲</p>
          </div>
          <button class="btn btn-small" @click="openAddTextModal">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            添加
          </button>
        </div>

        <!-- 服务商列表表格 -->
        <ProviderTable
          :providers="textConfig.providers"
          :activeProvider="textConfig.active_provider"
          @activate="activateTextProvider"
          @edit="openEditTextModal"
          @delete="deleteTextProvider"
          @test="testTextProviderInList"
        />
      </div>

      <!-- 图片生成配置 -->
      <div class="card">
        <div class="section-header">
          <div>
            <h2 class="section-title">图片生成配置</h2>
            <p class="section-desc">用于生成小红书配图</p>
          </div>
          <button class="btn btn-small" @click="openAddImageModal">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            添加
          </button>
        </div>

        <!-- 图片生成开关 -->
        <div class="image-generation-toggle">
          <label class="toggle-label">
            <input
              type="checkbox"
              :checked="imageConfig.generate_images_enabled"
              @change="handleImageGenerationToggle"
            />
            <span class="toggle-switch"></span>
            <span class="toggle-text">
              {{ imageConfig.generate_images_enabled ? '启用图片生成' : '仅生成提示词' }}
            </span>
          </label>
          <p class="toggle-desc">
            {{ imageConfig.generate_images_enabled
              ? '调用图片生成 API 生成实际图片'
              : '仅返回图片提示词，不调用图片生成 API（可用于节省 API 费用或手动生成图片）'
            }}
          </p>
        </div>

        <!-- 服务商列表表格 -->
        <ProviderTable
          :providers="imageConfig.providers"
          :activeProvider="imageConfig.active_provider"
          @activate="activateImageProvider"
          @edit="openEditImageModal"
          @delete="deleteImageProvider"
          @test="testImageProviderInList"
        />
      </div>

      <!-- MCP 工具配置 -->
      <MCPConfigCard />
    </div>

    <!-- 文本服务商弹窗 -->
    <ProviderModal
      :visible="showTextModal"
      :isEditing="!!editingTextProvider"
      :formData="textForm"
      :testing="testingText"
      :typeOptions="textTypeOptions"
      providerCategory="text"
      @close="closeTextModal"
      @save="saveTextProvider"
      @test="testTextConnection"
      @update:formData="updateTextForm"
    />

    <!-- 图片服务商弹窗 -->
    <ImageProviderModal
      :visible="showImageModal"
      :isEditing="!!editingImageProvider"
      :formData="imageForm"
      :testing="testingImage"
      :typeOptions="imageTypeOptions"
      @close="closeImageModal"
      @save="saveImageProvider"
      @test="testImageConnection"
      @update:formData="updateImageForm"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import ProviderTable from '../components/settings/ProviderTable.vue'
import ProviderModal from '../components/settings/ProviderModal.vue'
import ImageProviderModal from '../components/settings/ImageProviderModal.vue'
import MCPConfigCard from '../components/settings/MCPConfigCard.vue'
import { useGeneratorStore } from '../stores/generator'
import {
  useProviderForm,
  textTypeOptions,
  imageTypeOptions
} from '../composables/useProviderForm'

/**
 * 系统设置页面
 *
 * 功能：
 * - 管理文本生成服务商配置
 * - 管理图片生成服务商配置
 * - 测试 API 连接
 * - 切换 Agent 模式
 */

const generatorStore = useGeneratorStore()

// 切换 Agent 模式
function toggleAgentMode(event: Event) {
  const target = event.target as HTMLInputElement
  generatorStore.setAgentMode(target.checked)
}

// 使用 composable 管理表单状态和逻辑
const {
  // 状态
  loading,
  testingText,
  testingImage,

  // 配置数据
  textConfig,
  imageConfig,

  // 文本服务商弹窗
  showTextModal,
  editingTextProvider,
  textForm,

  // 图片服务商弹窗
  showImageModal,
  editingImageProvider,
  imageForm,

  // 方法
  loadConfig,

  // 文本服务商方法
  activateTextProvider,
  openAddTextModal,
  openEditTextModal,
  closeTextModal,
  saveTextProvider,
  deleteTextProvider,
  testTextConnection,
  testTextProviderInList,
  updateTextForm,

  // 图片服务商方法
  toggleImageGeneration,
  activateImageProvider,
  openAddImageModal,
  openEditImageModal,
  closeImageModal,
  saveImageProvider,
  deleteImageProvider,
  testImageConnection,
  testImageProviderInList,
  updateImageForm
} = useProviderForm()

// 切换图片生成开关
function handleImageGenerationToggle(event: Event) {
  const target = event.target as HTMLInputElement
  toggleImageGeneration(target.checked)
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.settings-container {
  max-width: 900px;
  margin: 0 auto;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #1a1a1a;
}

.section-desc {
  font-size: 14px;
  color: #666;
  margin: 0;
}

/* 按钮样式 */
.btn-small {
  padding: 6px 12px;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* 加载状态 */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #666;
}

/* Agent 模式切换 */
.agent-mode-toggle {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 12px;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}

.toggle-label input {
  display: none;
}

.toggle-switch {
  position: relative;
  width: 48px;
  height: 26px;
  background: #ddd;
  border-radius: 13px;
  transition: background 0.3s;
}

.toggle-switch::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 20px;
  height: 20px;
  background: white;
  border-radius: 50%;
  transition: transform 0.3s;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.toggle-label input:checked + .toggle-switch {
  background: var(--primary, #ff2442);
}

.toggle-label input:checked + .toggle-switch::after {
  transform: translateX(22px);
}

.toggle-text {
  font-size: 15px;
  font-weight: 500;
  color: #333;
}

.toggle-desc {
  margin: 12px 0 0;
  font-size: 13px;
  color: #666;
  line-height: 1.5;
}

/* 图片生成开关 */
.image-generation-toggle {
  padding: 16px;
  background: #f8f9fa;
  border-radius: 12px;
  margin-bottom: 16px;
}
</style>
