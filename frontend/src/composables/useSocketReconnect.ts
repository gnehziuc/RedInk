/**
 * WebSocket 重连管理 - 增强版
 */
import { ref } from 'vue'
import { useSocket } from './useSocket'

const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAY = 2000

export function useSocketReconnect() {
  const { socket, connected, connect, joinTask } = useSocket()
  const reconnectAttempts = ref(0)
  const isReconnecting = ref(false)
  const currentTaskId = ref<string>('')

  const setupReconnectHandlers = (taskId: string) => {
    currentTaskId.value = taskId

    if (!socket.value) return

    // 断线处理
    socket.value.on('disconnect', async (reason) => {
      console.warn('WebSocket 断开:', reason)

      if (reason === 'io server disconnect') {
        // 服务器主动断开，尝试重连
        await attemptReconnect()
      }
      // 其他情况 socket.io 会自动重连
    })

    // 重连成功
    socket.value.on('reconnect', async (attemptNumber) => {
      console.log('WebSocket 重连成功，尝试次数:', attemptNumber)
      reconnectAttempts.value = 0
      isReconnecting.value = false

      // 重新加入任务房间
      if (currentTaskId.value) {
        try {
          await joinTask(currentTaskId.value)
          console.log('重新加入任务房间:', currentTaskId.value)
        } catch (err) {
          console.error('重新加入房间失败:', err)
        }
      }
    })

    // 重连失败
    socket.value.on('reconnect_failed', () => {
      console.error('WebSocket 重连失败')
      isReconnecting.value = false
      reconnectAttempts.value = 0
    })

    // 重连尝试
    socket.value.on('reconnect_attempt', (attemptNumber) => {
      console.log('WebSocket 重连尝试:', attemptNumber)
      reconnectAttempts.value = attemptNumber
      isReconnecting.value = true
    })
  }

  const attemptReconnect = async () => {
    if (reconnectAttempts.value >= MAX_RECONNECT_ATTEMPTS) {
      console.error('达到最大重连次数')
      isReconnecting.value = false
      return false
    }

    isReconnecting.value = true
    reconnectAttempts.value++

    try {
      await new Promise(resolve => setTimeout(resolve, RECONNECT_DELAY))
      await connect()

      if (currentTaskId.value) {
        await joinTask(currentTaskId.value)
      }

      reconnectAttempts.value = 0
      isReconnecting.value = false
      return true
    } catch (err) {
      console.error('重连失败:', err)
      return attemptReconnect()
    }
  }

  return {
    reconnectAttempts,
    isReconnecting,
    setupReconnectHandlers
  }
}
