/**
 * WebSocket 连接管理 composable
 * P2-1: 优化连接等待机制
 * P2-2: 支持追加指令
 * P3-2: 引用计数管理连接生命周期
 */
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { io, Socket } from 'socket.io-client'

// 全局共享状态
const socket = ref<Socket | null>(null)
const connected = ref(false)

// P3-2: 引用计数
const connectionRefCount = ref(0)

// P4-1: 全局事件监听器追踪（防止重复绑定）
// Map<事件名, Map<回调函数, 绑定次数>>
const globalEventListeners = new Map<string, Map<Function, number>>()

// 连接配置
const CONNECTION_TIMEOUT = 10000  // 10秒连接超时

export function useSocket() {
  // 组件级别的引用计数管理
  let componentMounted = false

  // P4-1: 组件级别的事件监听器追踪（用于组件卸载时清理）
  const componentListeners = new Map<string, Set<Function>>()

  const connect = (url: string = ''): Promise<void> => {
    return new Promise((resolve, reject) => {
      if (socket.value?.connected) {
        resolve()
        return
      }

      // 开发环境直连后端，生产环境使用同源
      const isDev = import.meta.env.DEV
      const baseUrl = url || (isDev ? 'http://127.0.0.1:12398' : '')

      console.log('WebSocket 连接到:', baseUrl || '同源')

      socket.value = io(baseUrl, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
        timeout: CONNECTION_TIMEOUT
      })

      // 设置连接超时
      const timeoutId = setTimeout(() => {
        if (!connected.value) {
          reject(new Error('WebSocket 连接超时'))
        }
      }, CONNECTION_TIMEOUT)

      socket.value.on('connect', () => {
        clearTimeout(timeoutId)
        connected.value = true
        console.log('WebSocket 已连接, id:', socket.value?.id)
        resolve()
      })

      socket.value.on('disconnect', () => {
        connected.value = false
        console.log('WebSocket 已断开')
      })

      socket.value.on('connect_error', (error) => {
        clearTimeout(timeoutId)
        console.error('WebSocket 连接错误:', error.message)
        reject(error)
      })
    })
  }

  const disconnect = () => {
    if (socket.value) {
      socket.value.disconnect()
      socket.value = null
      connected.value = false
    }
  }

  // P2-1: 优化的连接等待机制（使用 Promise + watch）
  const waitForConnection = (timeout: number = CONNECTION_TIMEOUT): Promise<void> => {
    return new Promise((resolve, reject) => {
      if (connected.value) {
        resolve()
        return
      }

      const timeoutId = setTimeout(() => {
        unwatch()
        reject(new Error('等待连接超时'))
      }, timeout)

      const unwatch = watch(connected, (isConnected) => {
        if (isConnected) {
          clearTimeout(timeoutId)
          unwatch()
          resolve()
        }
      })
    })
  }

  const joinTask = (taskId: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      if (!socket.value?.connected) {
        reject(new Error('WebSocket 未连接'))
        return
      }

      console.log('加入任务房间:', taskId)
      socket.value.emit('join_task', { task_id: taskId })

      // 等待加入确认
      const onJoined = (data: any) => {
        if (data.task_id === taskId) {
          socket.value?.off('joined', onJoined)
          console.log('已加入任务房间:', taskId)
          resolve()
        }
      }

      socket.value.on('joined', onJoined)

      // 超时处理
      setTimeout(() => {
        socket.value?.off('joined', onJoined)
        // 即使没收到确认也认为成功（兼容旧版本后端）
        resolve()
      }, 2000)
    })
  }

  const leaveTask = (taskId: string) => {
    if (socket.value?.connected) {
      socket.value.emit('leave_task', { task_id: taskId })
    }
  }

  // P2-2: 发送追加指令
  const sendInstruction = (taskId: string, instruction: string): Promise<any> => {
    return new Promise((resolve, reject) => {
      if (!socket.value?.connected) {
        reject(new Error('WebSocket 未连接'))
        return
      }

      socket.value.emit('send_instruction', {
        task_id: taskId,
        instruction
      })

      // 等待响应
      const onReceived = (data: any) => {
        if (data.task_id === taskId) {
          socket.value?.off('instruction_received', onReceived)
          socket.value?.off('instruction_error', onError)
          resolve(data)
        }
      }

      const onError = (data: any) => {
        if (data.task_id === taskId) {
          socket.value?.off('instruction_received', onReceived)
          socket.value?.off('instruction_error', onError)
          reject(new Error(data.error || '发送指令失败'))
        }
      }

      socket.value.on('instruction_received', onReceived)
      socket.value.on('instruction_error', onError)

      // 超时处理
      setTimeout(() => {
        socket.value?.off('instruction_received', onReceived)
        socket.value?.off('instruction_error', onError)
        reject(new Error('发送指令超时'))
      }, 30000)
    })
  }

  // 确认房间加入（P1-3: 解决时序问题）
  const confirmRoom = (taskId: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      if (!socket.value?.connected) {
        reject(new Error('WebSocket 未连接'))
        return
      }

      socket.value.emit('confirm_room', { task_id: taskId })

      const onConfirmed = (data: any) => {
        if (data.task_id === taskId) {
          socket.value?.off('room_confirmed', onConfirmed)
          resolve()
        }
      }

      socket.value.on('room_confirmed', onConfirmed)

      // 超时后也认为成功（兼容旧版本后端）
      setTimeout(() => {
        socket.value?.off('room_confirmed', onConfirmed)
        resolve()
      }, 1000)
    })
  }

  // P4-1: 增强的事件监听注册（防止重复绑定）
  const on = (event: string, callback: (...args: any[]) => void) => {
    if (!socket.value) {
      console.warn(`[useSocket] 尝试绑定事件 ${event}，但 socket 未初始化`)
      return
    }

    // 检查全局是否已绑定相同的回调
    if (!globalEventListeners.has(event)) {
      globalEventListeners.set(event, new Map())
    }
    const eventCallbacks = globalEventListeners.get(event)!

    if (eventCallbacks.has(callback)) {
      // 已存在相同回调，增加引用计数但不重复绑定
      const count = eventCallbacks.get(callback)!
      eventCallbacks.set(callback, count + 1)
      console.log(`[useSocket] 事件 ${event} 的监听器已存在，引用计数: ${count + 1}`)
    } else {
      // 新回调，绑定到 socket
      eventCallbacks.set(callback, 1)
      socket.value.on(event, callback)
      console.log(`[useSocket] 绑定事件 ${event}`)
    }

    // 追踪组件级别的监听器
    if (!componentListeners.has(event)) {
      componentListeners.set(event, new Set())
    }
    componentListeners.get(event)!.add(callback)
  }

  // P4-1: 增强的事件监听移除
  const off = (event: string, callback?: (...args: any[]) => void) => {
    if (!socket.value) return

    if (callback) {
      // 移除特定回调
      const eventCallbacks = globalEventListeners.get(event)
      if (eventCallbacks?.has(callback)) {
        const count = eventCallbacks.get(callback)!
        if (count > 1) {
          // 还有其他引用，只减少计数
          eventCallbacks.set(callback, count - 1)
          console.log(`[useSocket] 事件 ${event} 引用计数减少: ${count - 1}`)
        } else {
          // 最后一个引用，真正移除
          eventCallbacks.delete(callback)
          socket.value.off(event, callback)
          console.log(`[useSocket] 移除事件 ${event} 的监听器`)
        }
      }

      // 从组件追踪中移除
      componentListeners.get(event)?.delete(callback)
    } else {
      // 移除该事件的所有监听器
      socket.value.off(event)
      globalEventListeners.delete(event)
      componentListeners.delete(event)
    }
  }

  // P4-1: 清理当前组件注册的所有监听器
  const cleanupComponentListeners = () => {
    for (const [event, callbacks] of componentListeners) {
      for (const callback of callbacks) {
        off(event, callback)
      }
    }
    componentListeners.clear()
  }

  const emit = (event: string, data: any) => {
    socket.value?.emit(event, data)
  }

  // P3-2: 生命周期管理
  onMounted(() => {
    componentMounted = true
    connectionRefCount.value++
    console.log(`Socket 引用计数增加: ${connectionRefCount.value}`)
  })

  onUnmounted(() => {
    if (componentMounted) {
      componentMounted = false
      connectionRefCount.value--
      console.log(`Socket 引用计数减少: ${connectionRefCount.value}`)

      // P4-1: 清理当前组件注册的所有监听器
      cleanupComponentListeners()

      // 当没有组件使用时，延迟断开连接
      if (connectionRefCount.value === 0) {
        setTimeout(() => {
          // 再次检查，防止新组件又挂载了
          if (connectionRefCount.value === 0 && socket.value) {
            console.log('没有组件使用 Socket，断开连接')
            disconnect()
          }
        }, 5000)  // 5秒后断开
      }
    }
  })

  return {
    socket,
    connected,
    connect,
    disconnect,
    waitForConnection,
    joinTask,
    leaveTask,
    confirmRoom,
    sendInstruction,
    on,
    off,
    emit,
    cleanupComponentListeners  // P4-1: 导出清理函数
  }
}
