import { useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Typography } from 'antd';
import type { CitationVerification } from '@/types';
import CitationBadge from './CitationBadge';

const { Title } = Typography;

interface ReviewPreviewProps {
    /** Markdown 综述内容 */
    content: string;
    /** 综述标题 */
    title?: string | null;
    /** 引用验证列表 */
    citationVerification?: CitationVerification[] | null;
}

/** 从引用文本中提取引用编号，如 "[1]" → 1 */
function extractRefIndex(text: string): number | null {
    const match = text.match(/^\[(\d+)\]$/);
    return match ? parseInt(match[1]!, 10) : null;
}

export default function ReviewPreview({
    content,
    title,
    citationVerification,
}: ReviewPreviewProps) {
    const contentRef = useRef<HTMLDivElement>(null);

    /** 跳转到指定 heading */
    const scrollToHeading = useCallback((headingId: string) => {
        const el = contentRef.current?.querySelector(`#${CSS.escape(headingId)}`);
        el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, []);

    /** 生成 heading ID */
    const headingId = (text: string) =>
        text
            .toLowerCase()
            .replace(/\s+/g, '-')
            .replace(/[^\w-]/g, '');

    return (
        <div ref={contentRef} style={{ padding: '16px 24px', overflow: 'auto', lineHeight: 1.8 }}>
            {title && (
                <Title level={3} style={{ marginBottom: 24 }}>
                    {title}
                </Title>
            )}

            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    h1: ({ children, ...props }) => {
                        const text = String(children);
                        return (
                            <h1 id={headingId(text)} {...props}>
                                {children}
                            </h1>
                        );
                    },
                    h2: ({ children, ...props }) => {
                        const text = String(children);
                        return (
                            <h2 id={headingId(text)} {...props}>
                                {children}
                            </h2>
                        );
                    },
                    h3: ({ children, ...props }) => {
                        const text = String(children);
                        return (
                            <h3 id={headingId(text)} {...props}>
                                {children}
                            </h3>
                        );
                    },
                    // 为引用标注添加验证 badge
                    sup: ({ children }) => {
                        const text = String(children);
                        const refIndex = extractRefIndex(text);
                        if (refIndex !== null && citationVerification) {
                            const verification = citationVerification.find(
                                (v) => v.reference_index === refIndex,
                            );
                            if (verification) {
                                return (
                                    <sup>
                                        {text}
                                        <CitationBadge verification={verification} />
                                    </sup>
                                );
                            }
                        }
                        return <sup>{children}</sup>;
                    },
                    table: ({ children, ...props }) => (
                        <div style={{ overflowX: 'auto', marginBottom: 16 }}>
                            <table
                                {...props}
                                style={{
                                    borderCollapse: 'collapse',
                                    width: '100%',
                                    fontSize: 13,
                                }}
                            >
                                {children}
                            </table>
                        </div>
                    ),
                    th: ({ children, ...props }) => (
                        <th
                            {...props}
                            style={{
                                border: '1px solid #d9d9d9',
                                padding: '8px 12px',
                                background: '#fafafa',
                                textAlign: 'left',
                            }}
                        >
                            {children}
                        </th>
                    ),
                    td: ({ children, ...props }) => (
                        <td
                            {...props}
                            style={{
                                border: '1px solid #d9d9d9',
                                padding: '8px 12px',
                            }}
                        >
                            {children}
                        </td>
                    ),
                    blockquote: ({ children, ...props }) => (
                        <blockquote
                            {...props}
                            style={{
                                borderLeft: '3px solid #1677ff',
                                paddingLeft: 16,
                                margin: '12px 0',
                                color: '#666',
                            }}
                        >
                            {children}
                        </blockquote>
                    ),
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );

    // Export scrollToHeading for OutlineTree usage
    void scrollToHeading;
}
