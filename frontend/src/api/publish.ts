/**
 * 发布相关 API
 * 
 * 提供小红书图文发布接口
 */
import axios from 'axios'

const API_BASE_URL = '/api/publish'

// 发布任务状态
export interface PublishTask {
    task_id: string
    status: 'pending' | 'running' | 'success' | 'failed'
    message: string
    created_at: string
    completed_at?: string
    note_id?: string
}

// 发布请求参数
export interface PublishImageRequest {
    account_id: number
    title: string
    content: string
    image_paths: string[]
    tags?: string[]
    publish_date?: string  // 格式: YYYY-MM-DD HH:MM
}

// 创建发布任务
export async function publishXhsImage(data: PublishImageRequest): Promise<{
    code: number
    msg: string
    data: { task_id: string } | null
}> {
    const response = await axios.post(`${API_BASE_URL}/xhs/image`, data)
    return response.data
}

// 获取发布任务状态
export async function getPublishStatus(taskId: string): Promise<{
    code: number
    msg: string | null
    data: PublishTask | null
}> {
    const response = await axios.get(`${API_BASE_URL}/xhs/status/${taskId}`)
    return response.data
}

// 获取所有发布任务列表
export async function getPublishTasks(): Promise<{
    code: number
    msg: string | null
    data: PublishTask[]
}> {
    const response = await axios.get(`${API_BASE_URL}/xhs/tasks`)
    return response.data
}
