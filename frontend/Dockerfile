FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --fetch-retries=5 --fetch-retry-mintimeout=20000 --fetch-retry-maxtimeout=120000
ARG NEXT_PUBLIC_API_URL=/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_ALLOW_REGISTRATION=true
ENV NEXT_PUBLIC_ALLOW_REGISTRATION=$NEXT_PUBLIC_ALLOW_REGISTRATION
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
