FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
ARG NEXT_PUBLIC_API_URL=http://localhost:8210
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
