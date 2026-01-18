/**
 * 性能监控工具
 */

interface PerformanceMetric {
  label: string
  duration: number
  timestamp: number
}

class PerformanceMonitor {
  private marks = new Map<string, number>()
  private metrics: PerformanceMetric[] = []
  private readonly SLOW_THRESHOLD = 3000 // 3秒

  start(label: string) {
    this.marks.set(label, performance.now())
  }

  end(label: string) {
    const start = this.marks.get(label)
    if (!start) {
      console.warn(`[Performance] 未找到标记: ${label}`)
      return
    }

    const duration = performance.now() - start
    const metric: PerformanceMetric = {
      label,
      duration,
      timestamp: Date.now()
    }

    this.metrics.push(metric)
    this.marks.delete(label)

    // 记录慢操作
    if (duration > this.SLOW_THRESHOLD) {
      console.warn(`[Performance] 慢操作: ${label} 耗时 ${duration.toFixed(2)}ms`)
    } else {
      console.log(`[Performance] ${label}: ${duration.toFixed(2)}ms`)
    }

    return duration
  }

  getMetrics() {
    return [...this.metrics]
  }

  clear() {
    this.marks.clear()
    this.metrics = []
  }
}

// 全局单例
export const perfMonitor = new PerformanceMonitor()

// 便捷函数
export function measureAsync<T>(label: string, fn: () => Promise<T>): Promise<T> {
  perfMonitor.start(label)
  return fn().finally(() => perfMonitor.end(label))
}
