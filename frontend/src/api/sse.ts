export interface SSEOptions {
    /** 最后接收到的事件 ID，用于断线续传 */
    lastEventId?: string;
    /** 各事件类型的处理函数 */
    onEvent: (event: string, data: Record<string, unknown>, id: string) => void;
    /** 连接建立回调 */
    onOpen?: () => void;
    /** 错误回调 */
    onError?: (error: Event) => void;
    /** 连接关闭回调 */
    onClose?: () => void;
    /** 最大重连次数 (默认 5) */
    maxRetries?: number;
}

/**
 * SSE 客户端封装
 *
 * 基于浏览器原生 EventSource，支持：
 * - 自动重连 (指数退避)
 * - Last-Event-ID 断线续传
 * - 多事件类型分发
 * - 手动关闭
 */
export class SSEClient {
    private eventSource: EventSource | null = null;
    private retryCount = 0;
    private maxRetries: number;
    private lastEventId: string;
    private url: string;
    private options: SSEOptions;
    private closed = false;

    constructor(url: string, options: SSEOptions) {
        this.url = url;
        this.options = options;
        this.maxRetries = options.maxRetries ?? 5;
        this.lastEventId = options.lastEventId ?? '';
    }

    connect(): void {
        this.closed = false;

        const fullUrl = this.lastEventId
            ? `${this.url}${this.url.includes('?') ? '&' : '?'}_last_id=${encodeURIComponent(this.lastEventId)}`
            : this.url;

        this.eventSource = new EventSource(fullUrl);

        this.eventSource.onopen = () => {
            this.retryCount = 0;
            this.options.onOpen?.();
        };

        this.eventSource.onmessage = (event) => {
            this.handleEvent('message', event);
        };

        // 监听后端已知事件类型
        const eventTypes = [
            'agent_start',
            'agent_complete',
            'progress',
            'paper_found',
            'paper_read',
            'hitl_pause',
            'token_update',
            'warning',
            'error',
            'complete',
        ];

        for (const type of eventTypes) {
            this.eventSource.addEventListener(type, (event) => {
                this.handleEvent(type, event as MessageEvent);
            });
        }

        this.eventSource.onerror = (error) => {
            this.options.onError?.(error);

            if (this.closed) return;

            if (this.retryCount < this.maxRetries) {
                this.retryCount++;
                const delay = Math.min(1000 * Math.pow(2, this.retryCount), 30000);
                setTimeout(() => {
                    if (!this.closed) this.connect();
                }, delay);
            } else {
                this.options.onClose?.();
                this.close();
            }
        };
    }

    private handleEvent(type: string, event: MessageEvent): void {
        if (event.lastEventId) {
            this.lastEventId = event.lastEventId;
        }

        try {
            const data = JSON.parse(event.data) as Record<string, unknown>;
            this.options.onEvent(type, data, event.lastEventId || '');

            // 收到 complete 或 error 事件后自动关闭
            if (type === 'complete' || type === 'error') {
                this.options.onClose?.();
                this.close();
            }
        } catch {
            // 非 JSON 数据忽略
        }
    }

    close(): void {
        this.closed = true;
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    get isConnected(): boolean {
        return this.eventSource?.readyState === EventSource.OPEN;
    }
}
