FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN npm install --registry=https://registry.npmmirror.com

COPY . .
RUN npm run build || npx vite build

# 使用 busybox 将构建产物复制到共享 volume
FROM busybox
COPY --from=builder /app/dist /build
CMD ["sh", "-c", "cp -r /build/* /output/ && echo 'Frontend build copied to volume'"]
