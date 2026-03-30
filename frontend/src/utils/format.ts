import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';
import { TOKEN_COST_PER_1K } from './constants';

dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

/** 格式化日期 (YYYY-MM-DD HH:mm) */
export function formatDate(dateStr: string): string {
    return dayjs(dateStr).format('YYYY-MM-DD HH:mm');
}

/** 格式化为相对时间 (如 "3天前") */
export function formatRelativeTime(dateStr: string): string {
    return dayjs(dateStr).fromNow();
}

/** 格式化 Token 数量 (如 "12.3K") */
export function formatTokens(count: number): string {
    if (count >= 1_000_000) {
        return `${(count / 1_000_000).toFixed(1)}M`;
    }
    if (count >= 1_000) {
        return `${(count / 1_000).toFixed(1)}K`;
    }
    return String(count);
}

/** Token 数转预估费用 (美元) */
export function tokensToCost(count: number): string {
    const cost = (count / 1000) * TOKEN_COST_PER_1K;
    return `$${cost.toFixed(2)}`;
}

/** 截断文本 */
export function truncate(text: string, maxLength: number): string {
    if (text.length <= maxLength) return text;
    return text.slice(0, maxLength) + '…';
}
