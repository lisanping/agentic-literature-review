import { Skeleton, Spin } from 'antd';

interface LoadingProps {
    /** 使用骨架屏还是旋转加载器 */
    type?: 'skeleton' | 'spin';
    /** 提示文字 */
    tip?: string;
}

export default function Loading({ type = 'spin', tip = '加载中...' }: LoadingProps) {
    if (type === 'skeleton') {
        return <Skeleton active paragraph={{ rows: 4 }} />;
    }

    return (
        <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin size="large" tip={tip}>
                <div style={{ minHeight: 100 }} />
            </Spin>
        </div>
    );
}
