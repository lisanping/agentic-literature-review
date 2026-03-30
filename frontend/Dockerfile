# ── 阶段 1: 构建 ──
FROM node:20-alpine AS builder

WORKDIR /app

# 先复制依赖文件以利用 Docker 层缓存
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

# 复制源码并构建
COPY . .
RUN npm run build

# ── 阶段 2: 生产镜像 ──
FROM nginx:1.27-alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 移除默认配置以避免冲突
RUN rm -f /etc/nginx/conf.d/default.conf.bak

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget -q --spider http://localhost:3000/ || exit 1
