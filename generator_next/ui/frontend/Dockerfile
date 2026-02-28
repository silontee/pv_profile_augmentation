FROM node:20-slim

RUN corepack enable && corepack prepare pnpm@9 --activate

WORKDIR /app

# 의존성 파일만 먼저 복사 (레이어 캐시)
COPY package.json pnpm-lock.yaml ./

RUN pnpm install --frozen-lockfile

# 앱 소스 복사
COPY . .

EXPOSE 5173

CMD ["pnpm", "dev", "--host", "0.0.0.0"]
